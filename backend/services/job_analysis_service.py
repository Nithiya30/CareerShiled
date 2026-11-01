import asyncio
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import Analysis, EvidenceItem, User
from app.schemas import EvidenceContribution, JobAnalysisRequest
from agents.company_agent import CompanyAgent
from agents.domain_agent import DomainAgent
from agents.recruiter_agent import RecruiterAgent
from agents.salary_agent import SalaryAgent
from agents.scam_agent import ScamAgent
from agents.website_agent import WebsiteAgent
from scoring import calculate_evidence_fusion
from services.ml_service import ml_service
from services.reputation_service import reputation_service
from services.transformer_service import transformer_service
from services.external_verification_service import (
    build_consent_section,
    extract_verification_details,
)
from utils.company_utils import extract_domain
from utils.text_utils import combine_job_text


scam_agent = ScamAgent()
recruiter_agent = RecruiterAgent()
company_agent = CompanyAgent()
website_agent = WebsiteAgent()
domain_agent = DomainAgent()
salary_agent = SalaryAgent()


def analyze_job_pipeline(
    req: JobAnalysisRequest,
    db: Session,
    current_user: User,
    *,
    persist: bool = True,
) -> Dict[str, Any]:
    """Run the existing recruitment pipeline, optionally without persistence."""
    job_dict = req.model_dump()

    combined_text = combine_job_text(job_dict)
    ml_res = ml_service.predict(combined_text)

    private_email = req.analysis_mode == "private_email"
    if private_email:
        transformer_res = {
            "category": "transformer",
            "status": "unavailable",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.5,
            "quality": 0.5,
            "confidence": 0.0,
            "label": "SKIPPED",
            "explanation": (
                "External semantic inference was skipped to keep private email "
                "content and sender details local."
            ),
            "signals": ["External inference skipped for private email privacy"],
        }
    elif req.document_source:
        transformer_res = transformer_service.local_only_result()
    else:
        transformer_res = transformer_service.analyze_text(req.job_description)

    scam_res = scam_agent.analyze(job_dict)
    if private_email:
        domain_result = {
            "category": "domain",
            "status": "unavailable",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.6,
            "quality": 0.5,
            "confidence": 0.0,
            "explanation": (
                "DNS and WHOIS checks were skipped for private email analysis."
            ),
            "signals": ["External domain verification skipped"],
            "verified": False,
        }
        company_reputation = {
            "company_name": req.company_name or "",
            "is_verified_entity": False,
            "reputation_score": 50,
            "sentiment_polarity": 0.0,
            "detected_risk_keywords": [],
            "impersonation_detected": False,
            "confidence": 0.0,
            "category": "company",
            "status": "unavailable",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.7,
            "quality": 0.5,
            "explanation": (
                "Company search and reputation verification were skipped for "
                "private email analysis."
            ),
            "signals": ["External company verification skipped"],
        }
        live_verification = {
            "domain": domain_result,
            "company_reputation": company_reputation,
        }
        recruiter_res = {
            "category": "recruiter",
            "status": "unavailable",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 1.0,
            "quality": 0.5,
            "confidence": 0.0,
            "explanation": (
                "Recruiter identity verification was skipped for private email analysis."
            ),
            "signals": ["External recruiter verification skipped"],
        }
        company_res = company_reputation
        website_res = {
            "category": "website",
            "status": "unavailable",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.6,
            "quality": 0.5,
            "confidence": 0.0,
            "explanation": (
                "Website reachability checks were skipped for private email analysis."
            ),
            "signals": ["External website verification skipped"],
        }
        domain_res = domain_result
    else:
        recruiter_res = recruiter_agent.analyze(job_dict)
        target_domain = extract_domain(req.company_website) or extract_domain(req.recruiter_email)
        if req.document_source:
            live_verification = {
                "domain": {
                    "category": "domain",
                    "status": "unavailable",
                    "evidence_state": "unknown",
                    "score": 0.0,
                    "weight": 0.6,
                    "quality": 0.5,
                    "confidence": 0.0,
                    "explanation": (
                        "Live domain verification was skipped for user-selected private content."
                    ),
                    "signals": ["Live domain verification unavailable"],
                    "verified": False,
                },
                "company_reputation": {
                    "company_name": req.company_name or "",
                    "is_verified_entity": False,
                    "reputation_score": 50,
                    "sentiment_polarity": 0.0,
                    "detected_risk_keywords": [],
                    "impersonation_detected": False,
                    "confidence": 0.0,
                    "category": "company",
                    "status": "unknown",
                    "evidence_state": "unknown",
                    "score": 0.0,
                    "weight": 0.7,
                    "quality": 0.5,
                    "explanation": (
                        "Live company verification was skipped for user-selected private content."
                    ),
                    "signals": ["Live company verification unavailable"],
                },
            }
        else:
            live_verification = asyncio.run(
                reputation_service.analyze_live_verification(
                    req.company_name or "", target_domain
                )
            )
        company_res = company_agent.analyze_with_reputation(
            job_dict, live_verification["company_reputation"]
        )
        website_res = website_agent.analyze(job_dict)
        domain_res = (
            live_verification["domain"]
            if req.document_source
            else domain_agent.analyze(job_dict, whois_result=live_verification["domain"])
        )
    salary_res = salary_agent.analyze(job_dict)

    evidence_bundle = [
        ml_res,
        transformer_res,
        scam_res,
        recruiter_res,
        company_res,
        website_res,
        domain_res,
        salary_res,
    ]

    fusion_result = calculate_evidence_fusion(evidence_bundle)

    trust_score = fusion_result["trust_score"]
    risk_level = fusion_result["risk_level"]
    fraud_prob = ml_res.get("fraud_probability", 0.1)
    confidence = fusion_result["confidence"]
    contributions = [
        EvidenceContribution(**contribution)
        for contribution in fusion_result["evidence_contributions"]
    ]

    if private_email:
        company_profile_summary = {
            "company_name": req.company_name or "",
            "dataset_available": False,
            "total_reviews": 0,
            "aspects": {},
            "confidence": 0.0,
            "workplace_reputation": "Insufficient Evidence",
            "public_reputation": "Insufficient Evidence",
            "identity_confidence": 0.0,
            "evidence_confidence": 0.0,
            "evidence": [],
            "explanation": (
                "Company review lookup was skipped for private email analysis."
            ),
        }
    else:
        company_profile_summary = reputation_service.analyze_company(req.company_name or "")
    job_assessment = {
        "trust_score": trust_score,
        "risk_level": risk_level,
        "confidence": confidence,
        "evidence": [
            {
                "source": item.get("category", "unknown"),
                "signal": item.get("signals", ["unknown"])[0]
                if item.get("signals")
                else "unknown",
                "score": float(item.get("score", 0.0)),
                "confidence": float(item.get("confidence", 0.5)),
                "status": item.get("evidence_state", "unknown"),
                "explanation": item.get("explanation", ""),
            }
            for item in evidence_bundle
        ],
        "summary": (
            "Likely legitimate and internally consistent."
            if risk_level == "Likely Legitimate"
            else "Needs additional verification before making a hiring decision."
            if risk_level == "Needs Verification"
            else "High-risk indicators detected. Additional verification is strongly recommended."
        ),
    }

    db_analysis = None
    if persist:
        db_analysis = Analysis(
            user_id=current_user.id,
            analysis_mode=req.analysis_mode,
            job_title=req.job_title,
            company_name=req.company_name,
            recruiter_email=req.recruiter_email,
            company_website=req.company_website,
            location=req.location,
            employment_type=req.employment_type,
            salary=req.salary,
            job_description=req.job_description,
            requirements=req.requirements,
            benefits=req.benefits,
            trust_score=trust_score,
            risk_level=risk_level,
            fraud_probability=fraud_prob,
            confidence=confidence,
            positive_evidence=fusion_result["positive_evidence"],
            negative_evidence=fusion_result["negative_evidence"],
            unknown_evidence=fusion_result["unknown_evidence"],
            evidence_contributions=[
                contribution.model_dump() for contribution in contributions
            ],
            ml_result=ml_res,
            transformer_result=transformer_res,
            recruiter_result=recruiter_res,
            company_result=company_res,
            website_result=website_res,
            domain_result=domain_res,
            salary_result=salary_res,
        )
        db.add(db_analysis)
        db.commit()
        db.refresh(db_analysis)

        for item in evidence_bundle:
            evidence = EvidenceItem(
                analysis_id=db_analysis.id,
                category=item.get("category", "unknown"),
                signal="; ".join(item.get("signals", [])),
                description=item.get("explanation", ""),
                evidence_state=item.get("evidence_state", "unknown"),
                score=float(item.get("score", 0.0)),
                weight=float(item.get("weight", 1.0)),
                quality=float(item.get("quality", 0.8)),
            )
            db.add(evidence)
        db.commit()

    return {
        "id": db_analysis.id if db_analysis is not None else None,
        "job_title": req.job_title,
        "company_name": req.company_name,
        "trust_score": trust_score,
        "risk_level": risk_level,
        "fraud_probability": fraud_prob,
        "confidence": confidence,
        "positive_evidence": fusion_result["positive_evidence"],
        "negative_evidence": fusion_result["negative_evidence"],
        "unknown_evidence": fusion_result["unknown_evidence"],
        "evidence_contributions": contributions,
        "evidence_details": {
            "evidence_index": fusion_result["evidence_index"],
            "total_signals_evaluated": len(evidence_bundle),
        },
        "advanced_ai_analysis": fusion_result.get("advanced_ai_analysis", {}),
        "live_verification": live_verification,
        "job_assessment": job_assessment,
        "company_reputation": company_profile_summary,
        "ml_result": ml_res,
        "transformer_result": transformer_res,
        "recruiter_result": recruiter_res,
        "company_result": company_res,
        "website_result": website_res,
        "domain_result": domain_res,
        "salary_result": salary_res,
        "external_verification": (
            build_consent_section(
                db_analysis.id,
                extract_verification_details(job_dict),
            )
            if private_email and db_analysis is not None
            else {}
        ),
        "created_at": db_analysis.created_at if db_analysis is not None else None,
    }
