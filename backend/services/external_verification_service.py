import asyncio
import ipaddress
import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable
from urllib.parse import urlsplit, urlunsplit

from agents.company_agent import analyze_company_reputation
from agents.domain_agent import DomainAgent
from agents.recruiter_agent import RecruiterAgent
from agents.salary_agent import SalaryAgent
from agents.website_agent import WebsiteAgent, WebsiteProbeError, resolve_public_host


logger = logging.getLogger(__name__)

CHECK_LABELS = {
    "company_reputation": "Company reputation",
    "website_domain": "Website and domain",
    "recruiter": "Recruiter verification",
    "salary": "Salary verification",
}
DECLINED_STATUS = "Not Checked – User Declined"
EXTERNAL_VERIFICATION_LEASE_SECONDS = 120
EXTERNAL_VERIFICATION_HEARTBEAT_INTERVAL_SECONDS = (
    EXTERNAL_VERIFICATION_LEASE_SECONDS / 3
)
MAX_EXTERNAL_VERIFICATION_ATTEMPTS = 2

_COMPANY_LINE = re.compile(
    r"(?im)^\s*(?:company|employer|hiring company)\s*:\s*([^\r\n]{1,200})"
)
_TITLE_LINE = re.compile(r"(?im)^\s*(?:job title|position|role)\s*:\s*([^\r\n]{1,200})")
_LOCATION_LINE = re.compile(r"(?im)^\s*(?:job )?location\s*:\s*([^\r\n]{1,200})")
_SALARY_LINE = re.compile(
    r"(?im)^\s*(?:salary|compensation|pay range|salary range)\s*:\s*([^\r\n]{1,200})"
)
_SENDER_NAME_LINE = re.compile(r"(?im)^\s*sender name\s*:\s*([^\r\n]{1,200})")
_URL = re.compile(r"https?://[^\s<>\"']{1,2048}", re.IGNORECASE)
_DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")


def _clean(value: Any, limit: int = 255) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x1f\x7f]", "", value).strip()[:limit]


def _clean_multiline(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value).strip()[:limit]


def _label_value(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return _clean(match.group(1)) if match else ""


def _safe_website(value: str, text: str) -> str:
    candidate = _clean(value, 2048)
    if not candidate:
        match = _URL.search(text)
        candidate = match.group(0).rstrip(".,;:!?)]}") if match else ""
    if not candidate:
        return ""
    if not candidate.lower().startswith(("http://", "https://")):
        candidate = f"https://{candidate}"
    try:
        parsed = urlsplit(candidate)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return ""
        host = parsed.hostname.encode("idna").decode("ascii").lower()
        port = parsed.port
    except (UnicodeError, ValueError):
        return ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not _DOMAIN_LABEL.fullmatch(host.rstrip(".")):
            return ""
        host = host.rstrip(".")
    else:
        host = f"[{address.compressed}]" if address.version == 6 else address.compressed
    authority = f"{host}:{port}" if port is not None else host
    return urlunsplit((parsed.scheme.lower(), authority, parsed.path or "/", "", ""))


def _email_domain(value: str) -> str:
    email = _clean(value, 320)
    if email.count("@") != 1:
        return ""
    domain = email.rsplit("@", 1)[1].rstrip(".").lower()
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return ""
    if not _DOMAIN_LABEL.fullmatch(domain):
        return ""
    return domain


def extract_verification_details(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only the small set of fields the user can approve for sharing."""
    text = _clean_multiline(job_data.get("job_description"), 110_000)
    subject = _label_value(re.compile(r"(?im)^\s*email subject\s*:\s*([^\r\n]{1,500})"), text)
    job_title = _clean(job_data.get("job_title")) or subject
    if job_title.lower() in {"recruitment email", "email content – private analysis"} and subject:
        job_title = subject
    company_name = _clean(job_data.get("company_name")) or _label_value(_COMPANY_LINE, text)
    company_website = _safe_website(
        _clean(job_data.get("company_website"), 2048), text
    )
    recruiter_domain = _email_domain(_clean(job_data.get("recruiter_email"), 320))
    try:
        company_domain = urlsplit(company_website).hostname or ""
    except ValueError:
        company_domain = ""
    recruiter_name = _label_value(_SENDER_NAME_LINE, text)
    return {
        "company_name": company_name,
        "company_website": company_website,
        "company_domain": company_domain,
        "recruiter_email_domain": recruiter_domain,
        "recruiter_name": recruiter_name,
        "job_title": job_title,
        "location": _clean(job_data.get("location")) or _label_value(_LOCATION_LINE, text),
        "salary": _clean(job_data.get("salary")) or _label_value(_SALARY_LINE, text),
    }


def _eligibility(details: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    has_company = bool(details["company_name"])
    has_website_or_domain = bool(details["company_website"] or details["recruiter_email_domain"])
    has_recruiter = bool(details["recruiter_email_domain"])
    has_salary_inputs = bool(details["job_title"] and details["salary"])
    return {
        "company_reputation": {
            "available": has_company,
            "reason": "" if has_company else "Company name is not available.",
            "information_shared": [details["company_name"]] if has_company else [],
            "processed_locally": (
                [details["company_domain"]] if details["company_domain"] else []
            ),
        },
        "website_domain": {
            "available": has_website_or_domain,
            "reason": "" if has_website_or_domain else "No website URL or recruiter domain is available.",
            "information_shared": [
                value for value in (
                    details["company_website"] or details["company_domain"]
                    or details["recruiter_email_domain"],
                ) if value
            ],
            "processed_locally": (
                [details["company_domain"]] if details["company_domain"] else []
            ),
        },
        "recruiter": {
            "available": has_recruiter,
            "reason": "" if has_recruiter else "Recruiter email domain is not available.",
            "information_shared": [],
            "processed_locally": [
                value for value in (
                    details["recruiter_email_domain"],
                    details["company_domain"],
                    details["company_name"],
                ) if value
            ],
        },
        "salary": {
            "available": has_salary_inputs,
            "reason": "" if has_salary_inputs else "Job title or salary information is not available.",
            "information_shared": [],
            "processed_locally": [
                value for value in (details["job_title"], details["location"], details["salary"])
                if value
            ],
        },
    }


def build_consent_section(
    analysis_id: int,
    details: Dict[str, Any],
    consent: Any = None,
) -> Dict[str, Any]:
    eligible = _eligibility(details)
    stored_results = (consent.results or {}) if consent is not None else {}
    checks = {}
    selected = set(consent.selected_checks or []) if consent is not None else set()
    for key, metadata in eligible.items():
        result = stored_results.get(key)
        if result:
            status = result.get("status", "Unknown")
        elif consent is not None and consent.status == "declined":
            status = DECLINED_STATUS
        elif consent is not None and key not in selected:
            status = DECLINED_STATUS
        elif not metadata["available"]:
            status = "Unknown"
        elif consent is not None and consent.status == "running":
            status = "Pending"
        else:
            status = "Pending"
        checks[key] = {
            "label": CHECK_LABELS[key],
            "available": metadata["available"],
            "reason": metadata["reason"],
            "information_shared": metadata["information_shared"],
            "processed_locally": metadata["processed_locally"],
            "status": status,
            "result": result,
        }

    return {
        "analysis_id": analysis_id,
        "details": details,
        "checks": checks,
        "consent_status": consent.status if consent is not None else "required",
        "selected_checks": list(selected),
        "consented_at": consent.consented_at if consent is not None else None,
        "execution_started_at": consent.execution_started_at if consent is not None else None,
        "execution_lease_expires_at": (
            consent.execution_lease_expires_at if consent is not None else None
        ),
        "execution_attempts": (
            consent.execution_attempts if consent is not None else 0
        ),
        "failure_reason": consent.failure_reason if consent is not None else None,
        "can_retry": bool(
            consent is not None
            and consent.status in {"failed", "partial"}
            and consent.consented_at is not None
            and consent.selected_checks
            and consent.execution_attempts < MAX_EXTERNAL_VERIFICATION_ATTEMPTS
        ),
        "executed_at": consent.executed_at if consent is not None else None,
    }


def validate_selected_checks(
    selected_checks: Iterable[str], details: Dict[str, Any]
) -> None:
    eligibility = _eligibility(details)
    unavailable = [
        check for check in selected_checks
        if check not in eligibility or not eligibility[check]["available"]
    ]
    if unavailable:
        raise ValueError("Selected verification checks require information that is unavailable.")


def _normalized_status(result: Dict[str, Any]) -> str:
    status = str(result.get("status", "")).lower()
    explanation = str(result.get("explanation", "")).lower()
    if status == "unavailable" or "unavailable because" in explanation or "lookup failed" in explanation:
        return "Unavailable"
    if status in {"verified", "partially_verified", "match found", "partial match"}:
        return "Verified"
    if status in {"suspicious", "unverified", "no match found"}:
        return "Unverified"
    return "Unknown"


def _public_result(result: Dict[str, Any], status: str) -> Dict[str, Any]:
    safe_result = dict(result)
    safe_result.pop("whois_raw", None)
    return {
        "status": status,
        "evidence": safe_result.get("signals", []),
        "source": safe_result.get("source") or safe_result.get("source_name"),
        "explanation": safe_result.get("explanation", ""),
        "confidence": safe_result.get("confidence"),
        "retrieved_at": safe_result.get("retrieved_at"),
        "details": safe_result,
    }


def _not_checked_result() -> Dict[str, Any]:
    return {
        "status": DECLINED_STATUS,
        "evidence": [],
        "source": None,
        "explanation": "This check was not selected for this analysis.",
        "confidence": None,
        "retrieved_at": None,
        "details": {},
    }


def execute_approved_checks(
    selected_checks: Iterable[str],
    details: Dict[str, Any],
    *,
    before_check: Callable[[str], bool] | None = None,
    on_result: Callable[[str, Dict[str, Any]], bool] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Run only explicitly selected checks, using category-specific data objects."""
    selected = set(selected_checks)
    outputs = {key: _not_checked_result() for key in CHECK_LABELS}
    for check in selected:
        if before_check is not None and not before_check(check):
            break
        try:
            if check == "company_reputation":
                raw = asyncio.run(
                    analyze_company_reputation(
                        details["company_name"],
                        details["company_domain"] or None,
                    )
                )
                status = (
                    "Unavailable"
                    if "unavailable" in str(raw.get("explanation", "")).lower()
                    else _normalized_status(raw)
                )
            elif check == "website_domain":
                raw_results = {}
                domain_input = details["company_website"] or details["recruiter_email_domain"]
                if details["company_website"]:
                    raw_results["website"] = WebsiteAgent().analyze(
                        {"company_website": details["company_website"]}
                    )
                try:
                    host = urlsplit(domain_input).hostname if "://" in domain_input else domain_input
                    if not host:
                        raise WebsiteProbeError("Website host is invalid")
                    resolve_public_host(host)
                    raw_results["domain"] = DomainAgent().analyze(
                        {"company_website": host}
                    )
                except WebsiteProbeError:
                    raw_results["domain"] = {
                        "status": "unavailable",
                        "signals": ["Domain verification skipped because the host is not publicly routable."],
                        "explanation": "The domain could not be verified using a public destination.",
                        "confidence": 0.0,
                    }
                statuses = [_normalized_status(item) for item in raw_results.values()]
                status = (
                    "Verified" if "Verified" in statuses
                    else "Unverified" if "Unverified" in statuses
                    else "Unavailable" if "Unavailable" in statuses
                    else "Unknown"
                )
                raw = {
                    "status": status.lower(),
                    "signals": [
                        signal
                        for item in raw_results.values()
                        for signal in item.get("signals", [])
                    ],
                    "explanation": "Website and domain checks completed.",
                    "confidence": max(
                        (float(item.get("confidence", 0.0)) for item in raw_results.values()),
                        default=0.0,
                    ),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "checks": {
                        name: _public_result(item, _normalized_status(item))
                        for name, item in raw_results.items()
                    },
                }
            elif check == "recruiter":
                raw = RecruiterAgent().analyze_domains(
                    details["recruiter_email_domain"],
                    details["company_domain"],
                    details["company_name"],
                )
                status = _normalized_status(raw)
            elif check == "salary":
                raw = SalaryAgent().analyze(
                    {
                        "job_title": details["job_title"],
                        "location": details["location"],
                        "salary": details["salary"],
                    }
                )
                status = _normalized_status(raw)
            else:
                continue
            outputs[check] = _public_result(raw, status)
        except Exception as exc:
            logger.warning(
                "External verification check %s failed (%s).",
                check,
                type(exc).__name__,
            )
            outputs[check] = {
                "status": "Unavailable",
                "evidence": [],
                "source": None,
                "explanation": "This verification service is unavailable.",
                "confidence": None,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "details": {},
            }
        if on_result is not None and not on_result(check, outputs[check]):
            break
    return outputs


def result_statuses(results: Dict[str, Dict[str, Any]], selected: Iterable[str]) -> str:
    selected_results = [results[key]["status"] for key in selected]
    if not selected_results:
        return "declined"
    unavailable = sum(status == "Unavailable" for status in selected_results)
    if unavailable == len(selected_results):
        return "failed"
    if unavailable:
        return "partial"
    return "completed"
