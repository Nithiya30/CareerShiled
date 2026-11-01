from typing import List, Dict, Any, Tuple
from app.config import settings


def _is_model_diagnostic(category: str, explanation: str) -> bool:
    lowered = (category + " " + (explanation or "")).lower()
    technical_markers = [
        "hf_token",
        "transformer api",
        "supervised nlp model",
        "predicted fraud probability",
        "local nlp active",
        "fallback to local intelligence",
        "model is not trained",
        "model standby",
        "inference api",
        "network probe timed out",
        "api timeout",
        "api unavailable",
        "remote inference",
        "internal model",
        "model status",
        "backend",
        "system error",
        "api returned status",
        "local ml",
        "classifier"
    ]
    return category in {"ml", "transformer"} or any(marker in lowered for marker in technical_markers)


def calculate_evidence_fusion(evidence_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Implements CareerShield Evidence Fusion Formula:
    Ef = Σ(wi × qi × ei) / Σ(wi × qi)
    Trust Score = 50 + 50 * Ef
    
    Where:
    - wi is the agent weight (importance)
    - qi is observation quality / confidence in [0, 1]
    - ei is the directional score (-1.0 to +1.0)
    
    Unknown state items have ei=0 or damped weight to ensure they never unfairly penalize a company.
    """
    total_weighted_product = 0.0
    total_normalization = 0.0

    contributions = []
    positive_evidence = []
    negative_evidence = []
    unknown_evidence = []
    risk_penalties = []

    # Map category display names
    display_names = {
        "ml": "Job ML",
        "transformer": "Transformer",
        "scam": "Scam Signals",
        "recruiter": "Recruiter",
        "company": "Company",
        "website": "Website",
        "domain": "Domain",
        "salary": "Salary"
    }

    for item in evidence_items:
        category = item.get("category", "unknown")
        state = item.get("evidence_state", "unknown")
        score = float(item.get("score", 0.0))
        weight = float(item.get("weight", 1.0))
        quality = float(item.get("quality", 0.8))
        explanation = item.get("explanation", "")

        domain_age_days = item.get("domain_age_days")
        if category == "domain" and isinstance(domain_age_days, (int, float)) and domain_age_days < 30:
            state = "negative"
            score = min(score, -0.85)
            explanation = (explanation + " Newly registered domain under 30 days old.").strip()
            risk_penalties.append("newly_registered_domain")

        risk_keywords = item.get("detected_risk_keywords", [])
        if category == "company" and item.get("impersonation_detected"):
            state = "negative"
            score = min(score, -0.95)
            explanation = (explanation + " Company/domain impersonation detected.").strip()
            risk_penalties.append("company_impersonation")
        elif category == "company" and len(risk_keywords) >= 2:
            state = "negative"
            score = min(score, -0.75)
            explanation = (explanation + " Multiple scam-risk keywords found in live search.").strip()
            risk_penalties.append("multiple_scam_keywords")

        # User-facing evidence must describe real-world findings, not internal model diagnostics.
        is_technical = _is_model_diagnostic(category, explanation)
        if not is_technical:
            if state == "positive":
                if explanation:
                    positive_evidence.append(explanation)
            elif state == "negative":
                if explanation:
                    negative_evidence.append(explanation)
            else:
                if explanation:
                    unknown_evidence.append(explanation)

        # Calculate numerator & denominator for fusion
        # If state is unknown, score is 0.0, so it neither increases nor decreases trust blindly
        effective_score = score if state != "unknown" else 0.0
        weighted_val = weight * quality * effective_score
        norm_factor = weight * quality

        total_weighted_product += weighted_val
        total_normalization += norm_factor

        # Individual contribution metric for chart visualization
        # Contribution in [-1.0, 1.0]
        contrib_val = (weighted_val / norm_factor) if norm_factor > 0 else 0.0
        contributions.append({
            "category": display_names.get(category, category.title()),
            "contribution": round(contrib_val, 3),
            "state": state
        })

    # Fused evidence score Ef in [-1.0, 1.0]
    Ef = (total_weighted_product / total_normalization) if total_normalization > 0 else 0.0
    Ef = max(-1.0, min(1.0, Ef))

    # Trust Score TS = 50 + 50 * Ef (bounded 0 to 100)
    raw_trust_score = 50.0 + (50.0 * Ef)
    trust_score = round(max(0.0, min(100.0, raw_trust_score)), 1)

    # Classify Risk based on backend configuration thresholds
    if trust_score >= settings.TRUST_THRESHOLD_LEGITIMATE:
        risk_level = "Likely Legitimate"
    elif trust_score >= settings.TRUST_THRESHOLD_UNCERTAIN:
        risk_level = "Needs Verification"
    else:
        risk_level = "Likely Fraudulent"

    # Overall synthesized confidence
    total_quality = sum(float(i.get("quality", 0.8)) for i in evidence_items)
    avg_confidence = (total_quality / len(evidence_items)) if evidence_items else 0.5
    confidence = round(max(0.1, min(1.0, avg_confidence)), 2)

    advanced_ai_analysis = {
        "total_signals_evaluated": len(evidence_items),
        "model_fusion": {
            "evidence_index": round(Ef, 4),
            "trust_score": trust_score,
            "risk_level": risk_level,
            "confidence": confidence,
            "weights": {item.get("category", "unknown"): float(item.get("weight", 1.0)) for item in evidence_items},
        },
        "feature_contributions": contributions,
        "model_outputs": [
            item for item in evidence_items if item.get("category") in {"ml", "transformer"}
        ],
    }

    return {
        "trust_score": trust_score,
        "risk_level": risk_level,
        "evidence_index": round(Ef, 4),
        "confidence": confidence,
        "positive_evidence": positive_evidence,
        "negative_evidence": negative_evidence,
        "unknown_evidence": unknown_evidence,
        "risk_penalties": risk_penalties,
        "evidence_contributions": contributions,
        "advanced_ai_analysis": advanced_ai_analysis
    }
