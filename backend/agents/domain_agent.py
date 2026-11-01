import asyncio
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

import httpx

from utils.company_utils import extract_domain


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, (list, tuple)):
        value = next((item for item in value if item), None)
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _first_value(record: Any, *keys: str) -> Any:
    for key in keys:
        value = record.get(key) if hasattr(record, "get") else None
        if isinstance(value, (list, tuple)):
            value = next((item for item in value if item), None)
        if value:
            return value
    return None


def _build_result(domain: str, record: Any, source: str) -> Dict[str, Any]:
    if isinstance(record, dict) and isinstance(record.get("data"), dict):
        record = record["data"]

    creation = _as_datetime(_first_value(record, "creation_date", "created", "createdDate"))
    expiration = _as_datetime(_first_value(
        record, "expiration_date", "expiry_date", "expires", "expiresDate"
    ))
    registrar_value = _first_value(record, "registrar", "registrar_name")
    registrar = str(registrar_value) if registrar_value else None
    raw_value = _first_value(record, "raw", "whois_raw")
    raw_text = str(raw_value if raw_value is not None else record)

    now = datetime.now(timezone.utc)
    age_days = max(0, (now - creation).days) if creation else None
    expiry_days = (expiration - now).days if expiration else None
    is_new = age_days is not None and age_days < 90
    privacy_redacted = bool(re.search(
        r"privacy|redact|whoisguard|proxy registration|domains by proxy",
        f"{record} {raw_text}",
        re.IGNORECASE,
    ))

    risk_factors = []
    risk_score = 0
    if is_new:
        risk_factors.append("Domain was registered less than 90 days ago")
        risk_score += 60
    if expiration and expiry_days is not None and expiry_days <= 30:
        risk_factors.append("Domain expires within 30 days or is already expired")
        risk_score += 40
    if privacy_redacted:
        risk_factors.append("WHOIS registrant details are privacy-protected or redacted")
        risk_score += 10
    if not registrar:
        risk_factors.append("WHOIS registrar name is unavailable")
        risk_score += 5

    registered = bool(creation or expiration or registrar or raw_value)
    verified = source != "unverified"
    signals = [f"WHOIS metadata retrieved via {source}"]
    signals.extend(risk_factors)
    score = max(-1.0, min(1.0, 0.8 - min(risk_score, 100) / 100))
    if not verified:
        status, evidence_state, score = "unknown", "unknown", 0.0
    elif risk_score >= 60:
        status, evidence_state, score = "suspicious", "negative", -score
    else:
        status, evidence_state = "verified", "positive"

    return {
        "domain": domain,
        "registered": registered,
        "creation_date": creation.isoformat() if creation else None,
        "expiration_date": expiration.isoformat() if expiration else None,
        "domain_age_days": age_days,
        "is_newly_registered": is_new,
        "registrar": registrar,
        "whois_raw": raw_text,
        "verified": verified,
        "risk_score": min(risk_score, 100),
        "risk_factors": risk_factors,
        "category": "domain",
        "status": status,
        "evidence_state": evidence_state,
        "score": score,
        "weight": 1.0 if verified else 0.6,
        "quality": 0.9 if verified else 0.5,
        "confidence": 0.9 if verified else 0.5,
        "explanation": (
            f"WHOIS data for '{domain}' was retrieved."
            if verified else
            f"WHOIS data for '{domain}' could not be verified; registration details are unavailable."
        ),
        "signals": signals,
    }


def _query_whois(domain: str) -> Any:
    import whois

    return whois.whois(domain)


async def analyze_domain(domain: str) -> Dict[str, Any]:
    """Retrieve WHOIS registration details, falling back to WHOISJSON when configured."""
    domain = extract_domain(domain)
    if not domain:
        return _build_result("", {}, "unverified")

    try:
        record = await asyncio.wait_for(
            asyncio.to_thread(_query_whois, domain),
            timeout=4.0,
        )
        if record:
            return _build_result(domain, record, "WHOIS")
    except Exception:
        pass

    api_key = os.getenv("WHOISJSON_API_KEY", "").strip()
    if api_key:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "X-API-Key": api_key,
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    "https://whoisjson.com/api/v1/whois",
                    params={"domain": domain},
                    headers=headers,
                )
                response.raise_for_status()
                record = response.json()
                if record:
                    return _build_result(domain, record, "WHOISJSON")
        except Exception:
            pass

    result = _build_result(domain, {}, "unverified")
    warning = "WHOIS lookup unavailable; domain age and registration metadata could not be verified."
    result["explanation"] = warning
    result["signals"] = [warning]
    result["risk_factors"] = [warning]
    return result


class DomainAgent:
    """
    Combines DNS reachability evidence with live WHOIS registration metadata.
    """

    def analyze(
        self, job_data: Dict[str, Any], whois_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        email = job_data.get("recruiter_email", "").strip()
        website = job_data.get("company_website", "").strip()

        target_domain = ""
        if website:
            target_domain = extract_domain(website)
        elif email and "@" in email:
            target_domain = extract_domain(email)

        if not target_domain:
            result = _build_result("", {}, "unverified")
            result["explanation"] = "No domain or email address supplied for verification."
            result["signals"] = ["Domain omitted from submission"]
            return result

        result = whois_result or asyncio.run(analyze_domain(target_domain))
        signals = result["signals"]
        has_dns_a = False
        has_mx = False

        # Attempt DNS resolution using dnspython
        try:
            import dns.resolver
            resolver = dns.resolver.Resolver()
            resolver.timeout = 1.5
            resolver.lifetime = 1.5

            try:
                a_answers = resolver.resolve(target_domain, "A")
                if a_answers:
                    has_dns_a = True
                    signals.append(f"DNS A record resolved: {len(a_answers)} IP(s)")
            except Exception:
                pass

            try:
                mx_answers = resolver.resolve(target_domain, "MX")
                if mx_answers:
                    has_mx = True
                    signals.append(f"Valid MX mail exchanger confirmed: {len(mx_answers)} host(s)")
            except Exception:
                pass

        except Exception as e:
            signals.append("DNS query engine fallback triggered")

        # DNS can provide limited positive evidence when WHOIS is unavailable.
        if has_dns_a and has_mx:
            signals.append(f"DNS A and MX records resolve for '{target_domain}'")
            if not result["verified"]:
                result.update({
                    "status": "partially_verified",
                    "evidence_state": "positive",
                    "score": 0.75,
                    "weight": 1.0,
                    "quality": 0.9,
                    "confidence": 0.9,
                    "explanation": f"Domain '{target_domain}' is operational with verified DNS A and MX records; WHOIS is unavailable.",
                })
        elif has_dns_a:
            signals.append(f"DNS A record resolves for '{target_domain}', but MX was not confirmed")
            if not result["verified"]:
                result.update({
                    "status": "partially_verified",
                    "evidence_state": "positive",
                    "score": 0.3,
                    "weight": 0.8,
                    "quality": 0.7,
                    "confidence": 0.7,
                    "explanation": f"Domain '{target_domain}' resolves to an IP; WHOIS and MX could not be confirmed.",
                })

        if not result["verified"] and not has_dns_a:
            result["explanation"] = f"Domain '{target_domain}' could not be verified via WHOIS or DNS."
        return result
