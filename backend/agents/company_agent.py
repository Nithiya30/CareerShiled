import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from utils.company_utils import extract_domain, normalize_company_name


SERPER_URL = "https://google.serper.dev/search"
RISK_KEYWORDS = ("check deposit", "crypto pay", "telegram", "wire transfer")
NON_OFFICIAL_DOMAINS = {
    "facebook.com", "glassdoor.com", "indeed.com", "linkedin.com",
    "reddit.com", "trustpilot.com", "wikipedia.org", "x.com",
}


def _domain_matches(left: str, right: str) -> bool:
    return bool(left and right) and (
        left == right or left.endswith("." + right) or right.endswith("." + left)
    )


def _official_domain(search_results: list, company_name: str) -> Optional[str]:
    normalized_name = normalize_company_name(company_name)
    for result in search_results:
        title = str(result.get("title", "")).lower()
        domain = extract_domain(str(result.get("link", "")))
        if not domain or any(
            domain == blocked or domain.endswith("." + blocked)
            for blocked in NON_OFFICIAL_DOMAINS
        ):
            continue
        if normalized_name and normalized_name in normalize_company_name(title):
            return domain
    return None


def _evidence_result(
    company_name: str,
    target_domain: Optional[str],
    official_domain: Optional[str],
    sentiment: float,
    keywords: list,
    snippets: list,
    lookup_error: Optional[str] = None,
    source_evidence: Optional[list] = None,
    retrieved_at: Optional[str] = None,
) -> Dict[str, Any]:
    impersonation = bool(
        target_domain and official_domain and not _domain_matches(target_domain, official_domain)
    )
    verified = bool(official_domain)
    reputation_score = round(max(0, min(
        100,
        60 + (20 if verified else 0) + 20 * sentiment - 8 * len(keywords),
    )))

    if impersonation:
        status, state, score = "suspicious", "negative", -0.95
        explanation = (
            f"Listing domain '{target_domain}' does not match the company search domain '{official_domain}'."
        )
    elif len(keywords) >= 2:
        status, state, score = "suspicious", "negative", -0.75
        explanation = f"Search results contain multiple scam-risk terms for '{company_name}'."
    elif verified:
        status, state, score = "verified", "positive", 0.65
        explanation = f"Live search identified '{official_domain}' as a likely official domain for '{company_name}'."
    else:
        status, state, score = "unknown", "unknown", 0.0
        explanation = lookup_error or f"No official company domain could be verified for '{company_name}'."

    signals = []
    if verified:
        signals.append(f"Likely official domain identified: {official_domain}")
    if impersonation:
        signals.append("Listing domain does not match the likely official company domain")
    if keywords:
        signals.append("Risk keywords found: " + ", ".join(keywords))
    if lookup_error:
        signals.append(lookup_error)

    return {
        "company_name": company_name,
        "is_verified_entity": verified,
        "official_domain": official_domain,
        "reputation_score": reputation_score,
        "sentiment_polarity": round(sentiment, 4),
        "detected_risk_keywords": keywords,
        "impersonation_detected": impersonation,
        "search_snippets_sample": snippets[:6],
        "source_evidence": source_evidence or [],
        "retrieved_at": retrieved_at,
        "category": "company",
        "status": status,
        "evidence_state": state,
        "score": score,
        "weight": 1.0 if verified or impersonation else 0.7,
        "quality": 0.85 if verified or impersonation else 0.5,
        "confidence": 0.85 if verified or impersonation else 0.5,
        "explanation": explanation,
        "signals": signals or ["No live company-search evidence available"],
    }


async def analyze_company_reputation(
    company_name: str, domain: Optional[str] = None
) -> Dict[str, Any]:
    """Search live web results and assess company identity, sentiment, and risk terms."""
    company_name = (company_name or "").strip()
    target_domain = extract_domain(domain or "")
    if not company_name:
        return _evidence_result("", target_domain, None, 0.0, [], [], "No company name supplied.")

    api_key = os.getenv("SERPER_API_KEY", "").strip()
    if not api_key:
        return _evidence_result(
            company_name,
            target_domain,
            None,
            0.0,
            [],
            [],
            "Live company search is unavailable because SERPER_API_KEY is not configured.",
        )

    queries = [
        f'"{company_name}" scam OR fraud OR "fake job" OR "telegram interview"',
        f'"{company_name}" reviews Trustpilot Glassdoor',
    ]
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            async def search(query: str) -> Dict[str, Any]:
                response = await client.post(
                    SERPER_URL,
                    json={"q": query},
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()

            search_responses = await asyncio.gather(
                *(search(query) for query in queries)
            )
    except Exception:
        return _evidence_result(
            company_name,
            target_domain,
            None,
            0.0,
            [],
            [],
            "Live company search failed; reputation evidence is unavailable.",
        )

    organic_by_query = [response.get("organic", []) for response in search_responses]
    all_organic = [item for results in organic_by_query for item in results]
    knowledge_graph = search_responses[1].get("knowledgeGraph", {})
    official_domain = extract_domain(str(knowledge_graph.get("website", ""))) or None
    if not official_domain:
        official_domain = _official_domain(
            organic_by_query[1] + organic_by_query[0], company_name
        )

    snippets = [
        " ".join(part for part in (
            str(item.get("title", "")).strip(),
            str(item.get("snippet", "")).strip(),
        ) if part)
        for item in all_organic
    ]
    snippets = [snippet for snippet in snippets if snippet]
    source_evidence = []
    for item in all_organic[:6]:
        title = str(item.get("title", "")).strip()[:500]
        snippet = str(item.get("snippet", "")).strip()[:1500]
        source_url = str(item.get("link", "")).strip()
        if title or snippet:
            source_evidence.append({
                "title": title,
                "snippet": snippet,
                "source_url": source_url or None,
            })
    try:
        from textblob import TextBlob

        polarities = [float(TextBlob(snippet).sentiment.polarity) for snippet in snippets]
        sentiment = sum(polarities) / len(polarities) if polarities else 0.0
    except ImportError:
        sentiment = 0.0
    combined_text = " ".join(snippets).lower()
    keywords = [keyword for keyword in RISK_KEYWORDS if keyword in combined_text]

    return _evidence_result(
        company_name,
        target_domain,
        official_domain,
        sentiment,
        keywords,
        snippets,
        source_evidence=source_evidence,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )


class CompanyAgent:
    """Evaluates provided company identity signals and live reputation evidence."""

    def analyze(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        company_name = job_data.get("company_name", "").strip()
        company_profile = job_data.get("company_profile", "") or job_data.get("job_description", "")
        website = job_data.get("company_website", "").strip()

        if not company_name:
            return {
                "category": "company",
                "status": "unknown",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 0.8,
                "quality": 0.5,
                "confidence": 0.5,
                "explanation": "No company name specified in recruitment details.",
                "signals": ["Anonymous or unlisted hiring organization"],
            }

        profile_len = len(company_profile.strip())
        if website and profile_len > 80:
            return {
                "category": "company",
                "status": "verified",
                "evidence_state": "positive",
                "score": 0.65,
                "weight": 1.0,
                "quality": 0.85,
                "confidence": 0.85,
                "explanation": f"Established organizational profile with active web presence for '{company_name}'.",
                "signals": ["Corporate web profile provided", "Detailed mission and organizational overview"],
            }
        if website:
            return {
                "category": "company",
                "status": "partially_verified",
                "evidence_state": "positive",
                "score": 0.35,
                "weight": 0.9,
                "quality": 0.70,
                "confidence": 0.70,
                "explanation": f"Corporate website listed for '{company_name}', though organizational description is brief.",
                "signals": ["Website provided with minimal background text"],
            }
        return {
            "category": "company",
            "status": "unknown",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.7,
            "quality": 0.60,
            "confidence": 0.60,
            "explanation": f"Limited public entity information for '{company_name}'. Typical for emerging startups or local small enterprises.",
            "signals": ["Sparse corporate footprint; not penalizing under Unknown Rule"],
        }

    def analyze_with_reputation(
        self, job_data: Dict[str, Any], reputation: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = self.analyze(job_data)
        result.update({key: value for key, value in reputation.items() if key not in {
            "category", "status", "evidence_state", "score", "weight", "quality",
            "confidence", "explanation", "signals",
        }})
        result["signals"] = list(dict.fromkeys(result.get("signals", []) + reputation.get("signals", [])))
        if reputation.get("impersonation_detected"):
            result.update({
                "status": "suspicious",
                "evidence_state": "negative",
                "score": -0.95,
                "explanation": reputation["explanation"],
            })
        elif len(reputation.get("detected_risk_keywords", [])) >= 2:
            result.update({
                "status": "suspicious",
                "evidence_state": "negative",
                "score": -0.75,
                "explanation": reputation["explanation"],
            })
        elif reputation.get("is_verified_entity"):
            result["status"] = "verified"
            result["evidence_state"] = "positive"
            result["score"] = max(float(result.get("score", 0.0)), 0.65)
            result["explanation"] = reputation["explanation"]
        elif reputation.get("explanation"):
            result["explanation"] = result.get("explanation", "") + " " + reputation["explanation"]
        return result