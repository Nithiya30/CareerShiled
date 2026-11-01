import hashlib
import ipaddress
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from agents.recruiter_agent import RecruiterAgent
from app.models import (
    CompanyInvestigation,
    InvestigationEntity,
    InvestigationEvidence,
    InvestigationRelationship,
    InvestigationRelationshipEvidence,
    User,
)
from app.schemas import CompanyInvestigationRequest
from services.reputation_service import reputation_service
from utils.company_utils import normalize_company_name


_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def _redact_emails(value: str) -> str:
    return _EMAIL_PATTERN.sub("[email redacted]", value)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_source_url(value: Any) -> Optional[str]:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        host = parsed.hostname.lower().rstrip(".")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and (
            address.is_private or address.is_loopback or address.is_link_local
        ):
            return None
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except ValueError:
        return None


def _evidence(
    *,
    finding: str,
    source_name: str,
    factual_summary: str,
    status: str,
    source_reliability: str,
    relevance: str,
    explanation: str,
    limitations: str,
    source_url: Optional[str] = None,
    retrieved_at: Optional[str] = None,
) -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", factual_summary).strip().lower()
    return {
        "finding": finding,
        "source_name": source_name,
        "source_url": _safe_source_url(source_url),
        "retrieved_at": retrieved_at,
        "factual_summary": factual_summary[:3000],
        "status": status,
        "source_reliability": source_reliability,
        "relevance": relevance,
        "explanation": explanation,
        "limitations": limitations,
        "content_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }


def _review_date_range(reviews: Any) -> dict[str, Optional[str]]:
    if "date" not in reviews.columns:
        return {"start": None, "end": None}
    values = []
    for raw_value in reviews["date"].dropna().astype(str):
        parsed = None
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(raw_value.strip(), fmt).date()
                break
            except ValueError:
                continue
        if parsed is not None:
            values.append(parsed)
    if not values:
        return {"start": None, "end": None}
    return {"start": min(values).isoformat(), "end": max(values).isoformat()}


def _candidate_sources(company_name: str, source_evidence: list[dict]) -> list[dict[str, Any]]:
    normalized_query = normalize_company_name(company_name)
    candidates: dict[str, dict[str, Any]] = {}
    for item in source_evidence:
        title = _redact_emails(str(item.get("title", "")))
        normalized_title = normalize_company_name(title)
        if normalized_query not in normalized_title:
            continue
        source_url = _safe_source_url(item.get("source_url"))
        candidates.setdefault(normalized_title, {
            "source_title": title[:500],
            "source_url": source_url,
            "status": "inconclusive",
        })
    return list(candidates.values())[:6]


async def create_investigation(
    db: Session,
    user: User,
    request: CompanyInvestigationRequest,
    timeout_seconds: float = 10.0,
) -> CompanyInvestigation:
    company_name = request.company_name.strip()
    normalized_name = normalize_company_name(company_name)
    if not normalized_name:
        raise HTTPException(status_code=422, detail="Enter a valid company name.")

    domain = request.domain
    contact_domain = (
        request.recruiter_email.rsplit("@", 1)[1].lower()
        if request.recruiter_email
        else None
    )

    live: dict[str, Any]
    try:
        import asyncio

        live = await asyncio.wait_for(
            reputation_service.analyze_live_verification(company_name, domain),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        live = {
            "domain": {"status": "unavailable", "verified": False},
            "company_reputation": {
                "status": "unavailable",
                "source_evidence": [],
                "explanation": "Configured company and domain lookups exceeded the request time limit.",
            },
        }

    company_result = live.get("company_reputation") or {}
    domain_result = live.get("domain") or {}
    source_evidence = company_result.get("source_evidence")
    if not isinstance(source_evidence, list):
        source_evidence = []

    reviews = reputation_service.get_company_reviews(company_name)
    if len(reviews):
        ratings = []
        if "rating" in reviews.columns:
            import pandas as pd

            ratings = pd.to_numeric(reviews["rating"], errors="coerce").dropna().tolist()
        date_range = _review_date_range(reviews)
        workplace = {
            "status": "inconclusive",
            "label": "Available feedback; not an identity or recruitment-risk finding",
            "review_count": int(len(reviews)),
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "date_range": date_range,
            "source_names": (
                sorted({
                    str(value).strip()
                    for value in reviews["source"].dropna().tolist()
                    if str(value).strip()
                })[:10]
                if "source" in reviews.columns
                else []
            ),
            "limitations": [
                "The local review corpus is matched by normalized company name and can include similarly named entities.",
                "Source URLs and independent verification are not available for these aggregate records.",
            ],
        }
        review_finding = _evidence(
            finding="Local employee-review dataset contains matching records.",
            source_name="Processed employee-review dataset",
            factual_summary=(
                f"{len(reviews)} name-matched review records; "
                f"date range {date_range['start'] or 'unavailable'} to {date_range['end'] or 'unavailable'}."
            ),
            status="inconclusive",
            source_reliability="unknown",
            relevance="workplace_reputation",
            explanation="This describes the local dataset only and does not verify company identity or the truth of individual reviews.",
            limitations="No source URLs, independent-source analysis, or identity disambiguation are available.",
            retrieved_at=_utc_now().isoformat(),
        )
    else:
        workplace = {
            "status": "unavailable",
            "label": "Insufficient evidence",
            "review_count": 0,
            "average_rating": None,
            "date_range": {"start": None, "end": None},
            "source_names": [],
            "limitations": ["No matching local review records were available."],
        }
        review_finding = _evidence(
            finding="No matching records were available in the local employee-review dataset.",
            source_name="Processed employee-review dataset",
            factual_summary="No matching review records were returned.",
            status="unavailable",
            source_reliability="unknown",
            relevance="workplace_reputation",
            explanation="Absence from this dataset does not indicate poor reputation or fraud.",
            limitations="The local dataset may be incomplete or use a different company name.",
            retrieved_at=_utc_now().isoformat(),
        )

    evidence_rows = [review_finding]
    seen_hashes = {review_finding["content_hash"]}
    for item in source_evidence[:6]:
        title = _redact_emails(str(item.get("title", "")).strip())
        snippet = _redact_emails(str(item.get("snippet", "")).strip())
        summary = " — ".join(part for part in (title, snippet) if part)
        if not summary:
            continue
        row = _evidence(
            finding="Search result reports information about the queried company.",
            source_name="Serper web search result",
            source_url=item.get("source_url"),
            factual_summary=summary,
            status="inconclusive",
            source_reliability="secondary",
            relevance="company_identity",
            explanation="A search result is a lead, not independent verification that the result or domain belongs to this company.",
            limitations="Search snippets may be incomplete, outdated, duplicated, or about a similarly named entity.",
            retrieved_at=company_result.get("retrieved_at"),
        )
        duplicate_text = re.sub(r"\s+", " ", snippet).strip().lower() or re.sub(
            r"\s+", " ", summary
        ).strip().lower()
        row["content_hash"] = hashlib.sha256(
            duplicate_text.encode("utf-8")
        ).hexdigest()
        if row["content_hash"] not in seen_hashes:
            evidence_rows.append(row)
            seen_hashes.add(row["content_hash"])
    if not source_evidence:
        evidence_rows.append(_evidence(
            finding="No citable company-search result was available.",
            source_name="Serper web search",
            factual_summary="The configured company search returned no usable cited result.",
            status="unavailable",
            source_reliability="unknown",
            relevance="company_identity",
            explanation="No source was available to support a company identity finding.",
            limitations=str(
                company_result.get("explanation")
                or "The search provider returned no citable result."
            ),
            retrieved_at=_utc_now().isoformat(),
        ))

    if domain:
        registration_summary = (
            f"Domain lookup for {domain}: "
            f"registered={bool(domain_result.get('registered'))}; "
            f"creation_date={domain_result.get('creation_date') or 'unavailable'}; "
            f"registrar={domain_result.get('registrar') or 'unavailable'}."
        )
        has_registration_data = bool(
            domain_result.get("registered")
            or domain_result.get("creation_date")
            or domain_result.get("registrar")
        )
        evidence_rows.append(_evidence(
            finding="Domain registration metadata was queried.",
            source_name="WHOIS/domain lookup",
            factual_summary=registration_summary,
            status="inconclusive" if has_registration_data else "unavailable",
            source_reliability="secondary" if has_registration_data else "unknown",
            relevance="company_identity",
            explanation="Domain registration or DNS availability does not establish corporate ownership or recruiter authorization.",
            limitations="No authoritative company registry relationship was checked; raw WHOIS contact data is deliberately not retained.",
            retrieved_at=_utc_now().isoformat(),
        ))

    recruiter_assessment = None
    if request.recruiter_email:
        recruiter_input = {
            "company_name": company_name,
            "company_website": f"https://{domain}" if domain else "",
            "recruiter_email": request.recruiter_email,
        }
        recruiter_result = RecruiterAgent().analyze(recruiter_input)
        recruiter_assessment = {
            "status": "inconclusive",
            "kind": "model_interpretation",
            "indicator": recruiter_result.get("status", "unknown"),
            "summary": recruiter_result.get("explanation", "Recruiter signal unavailable."),
            "contact_domain": contact_domain,
            "limitations": "Email-domain matching is heuristic and does not verify employment or authorization.",
        }
        evidence_rows.append(_evidence(
            finding="Recruiter email-domain heuristic was evaluated.",
            source_name="CareerShield recruiter heuristic",
            factual_summary=recruiter_assessment["summary"],
            status="inconclusive",
            source_reliability="not_applicable",
            relevance="job_recruiter_risk",
            explanation="This is a model-generated interpretation, not an independently verified fact.",
            limitations=recruiter_assessment["limitations"],
            retrieved_at=_utc_now().isoformat(),
        ))

    candidates = _candidate_sources(company_name, source_evidence)
    unique_titles = {normalize_company_name(item["source_title"]) for item in candidates}
    ambiguity_status = (
        "potentially_ambiguous" if len(unique_titles) > 1 else "not_resolved"
    )
    is_ambiguous = len(unique_titles) > 1
    identity_assessment = {
        "status": "inconclusive",
        "label": "Potentially ambiguous source mentions" if is_ambiguous else "Identity not independently verified",
        "ambiguity_status": ambiguity_status,
        "candidate_sources": candidates,
        "summary": (
            "Several source titles mention this name; current sources cannot distinguish similarly named organizations."
            if is_ambiguous
            else "Available name/domain signals do not establish the legal identity or ownership of a company."
        ),
    }
    coverage_status = "inconclusive" if evidence_rows else "unavailable"
    report = {
        "assessments": {
            "job_recruiter_risk": recruiter_assessment or {
                "status": "unavailable",
                "summary": "No recruiter/contact information was supplied.",
            },
            "company_identity": identity_assessment,
            "workplace_reputation": workplace,
            "evidence_coverage": {
                "status": coverage_status,
                "evidence_count": len(evidence_rows),
                "source_count": len({
                    row["source_name"] for row in evidence_rows
                }),
                "summary": (
                    "Evidence is present but does not establish identity or independent corroboration."
                    if evidence_rows
                    else "No useful evidence sources were available."
                ),
            },
        },
        "information_types": {
            "verified_facts": [],
            "source_reported": [
                row["id"] if "id" in row else index
                for index, row in enumerate(evidence_rows)
                if row["source_reliability"] in {"primary", "secondary"}
            ],
            "model_interpretations": [
                index for index, row in enumerate(evidence_rows)
                if row["source_reliability"] == "not_applicable"
            ],
            "conflicting_evidence": [],
            "unknown_or_unavailable": [
                index for index, row in enumerate(evidence_rows)
                if row["status"] == "unavailable"
            ],
        },
        "limitations": [
            "Search-result pages are leads only; they do not establish company ownership.",
            "No government/company registry source was consulted.",
            "Workplace review matching uses a local dataset and is not evidence of recruitment fraud.",
            "The full recruiter email was used for in-memory analysis only and is not persisted.",
        ],
    }

    now = _utc_now().replace(tzinfo=None)
    investigation = CompanyInvestigation(
        id=str(uuid4()),
        user_id=user.id,
        company_name=company_name,
        normalized_name=normalized_name,
        domain=domain,
        contact_domain=contact_domain,
        status="completed",
        created_at=now,
        completed_at=now,
        report=report,
    )
    investigation.evidence = [
        InvestigationEvidence(**row) for row in evidence_rows
    ]
    db.add(investigation)
    db.flush()

    company_entity = InvestigationEntity(
        id=str(uuid4()),
        investigation_id=investigation.id,
        entity_type="company",
        display_name=company_name,
        normalized_value=normalized_name,
        attributes={"identity_status": "inconclusive"},
    )
    investigation.entities.append(company_entity)

    evidence_by_source: dict[str, list[InvestigationEvidence]] = {}
    for evidence in investigation.evidence:
        evidence_by_source.setdefault(evidence.source_name, []).append(evidence)

    relationships = []
    if domain:
        domain_entity = InvestigationEntity(
            id=str(uuid4()),
            investigation_id=investigation.id,
            entity_type="domain",
            display_name=domain,
            normalized_value=domain,
            attributes={"origin": "user_supplied"},
        )
        investigation.entities.append(domain_entity)
        domain_evidence = evidence_by_source.get("WHOIS/domain lookup", [])
        relationships.append(InvestigationRelationship(
            id=str(uuid4()),
            investigation_id=investigation.id,
            source_entity=company_entity,
            target_entity=domain_entity,
            relationship_type="user_claimed_company_domain",
            status="inconclusive",
            explanation="The domain was submitted as associated with the company.",
            limitations="User input and domain registration data do not prove company ownership.",
            evidence_links=[
                InvestigationRelationshipEvidence(evidence=item)
                for item in domain_evidence
            ],
        ))

    if contact_domain:
        contact_entity = InvestigationEntity(
            id=str(uuid4()),
            investigation_id=investigation.id,
            entity_type="contact_domain",
            display_name=contact_domain,
            normalized_value=contact_domain,
            attributes={"retained_value": "domain_only"},
        )
        investigation.entities.append(contact_entity)
        recruiter_evidence = evidence_by_source.get(
            "CareerShield recruiter heuristic",
            [],
        )
        relationships.append(InvestigationRelationship(
            id=str(uuid4()),
            investigation_id=investigation.id,
            source_entity=contact_entity,
            target_entity=company_entity,
            relationship_type="contact_claimed_for_company",
            status="inconclusive",
            explanation="Contact domain was submitted for assessment against the company.",
            limitations="This does not verify the contact's identity, employment, or authorization.",
            evidence_links=[
                InvestigationRelationshipEvidence(evidence=item)
                for item in recruiter_evidence
            ],
        ))

    source_entities: dict[str, InvestigationEntity] = {}
    for evidence in investigation.evidence:
        identity = f"{evidence.source_name}|{evidence.source_url or ''}"
        source_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        source_entity = source_entities.get(source_key)
        if source_entity is None:
            source_entity = InvestigationEntity(
                id=str(uuid4()),
                investigation_id=investigation.id,
                entity_type="evidence_source",
                display_name=evidence.source_name,
                normalized_value=source_key,
                attributes={"source_url": evidence.source_url},
            )
            source_entities[source_key] = source_entity
            investigation.entities.append(source_entity)
        relationships.append(InvestigationRelationship(
            id=str(uuid4()),
            investigation_id=investigation.id,
            source_entity=source_entity,
            target_entity=company_entity,
            relationship_type="source_reports_finding",
            status=evidence.status,
            explanation=evidence.explanation,
            limitations=evidence.limitations,
            evidence_links=[
                InvestigationRelationshipEvidence(evidence=evidence)
            ],
        ))
    investigation.relationships = relationships
    db.commit()
    db.refresh(investigation)
    return (
        db.query(CompanyInvestigation)
        .options(
            selectinload(CompanyInvestigation.evidence),
            selectinload(CompanyInvestigation.entities),
        )
        .filter(CompanyInvestigation.id == investigation.id)
        .one()
    )


def get_owned_investigation(
    db: Session,
    investigation_id: str,
    user: User,
) -> CompanyInvestigation:
    investigation = (
        db.query(CompanyInvestigation)
        .options(selectinload(CompanyInvestigation.evidence))
        .filter(
            CompanyInvestigation.id == investigation_id,
            CompanyInvestigation.user_id == user.id,
        )
        .first()
    )
    if investigation is None:
        raise HTTPException(status_code=404, detail="Company investigation not found.")
    return investigation
