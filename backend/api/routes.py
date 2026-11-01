import json
import logging
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.config import settings
from app.db import get_db
from app.models import (
    Analysis,
    EvidenceItem,
    CompanyReview,
    CompanyClaim,
    ReputationSummary,
    CompanyInvestigation,
    InvestigationEntity,
    InvestigationRelationship,
    InvestigationRelationshipEvidence,
    User,
    ExternalVerificationConsent,
)
from api.auth_dependencies import get_current_user, require_csrf
from app.schemas import (
    HealthResponse,
    ModelStatusResponse,
    DatasetStatusResponse,
    JobAnalysisRequest,
    JobAnalysisResponse,
    HistoryResponse,
    AnalysisHistoryItem,
    CompanyReputationRequest,
    CompanyReputationResponse,
    CompanyClaimRequest,
    CompanyClaimResponse,
    CompanyInvestigationRequest,
    CompanyInvestigationResponse,
    CompanyInvestigationListItem,
    InvestigationGraphResponse,
    EvidenceContribution,
    ReviewAnalysisRequest,
    ExternalVerificationConsentRequest,
)

# Services
from services.ml_service import ml_service
from services.transformer_service import transformer_service
from services.reputation_service import reputation_service
from services.job_analysis_service import (
    analyze_job_pipeline,
    company_agent,
    domain_agent,
    recruiter_agent,
    salary_agent,
    scam_agent,
    website_agent,
)
from services.claim_service import claim_service
from services.review_credibility_service import review_credibility_service
from services.company_investigation_service import (
    create_investigation,
    get_owned_investigation,
)
from services.rate_limit_service import get_client_ip, rate_limiter
from services.external_verification_service import (
    EXTERNAL_VERIFICATION_HEARTBEAT_INTERVAL_SECONDS,
    EXTERNAL_VERIFICATION_LEASE_SECONDS,
    MAX_EXTERNAL_VERIFICATION_ATTEMPTS,
    build_consent_section,
    execute_approved_checks,
    extract_verification_details,
    result_statuses,
    validate_selected_checks,
)

from sqlalchemy import text

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    db_status = "Available"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "Degraded"

    return {
        "status": "ok",
        "service": "CareerShield Security Engine",
        "version": "1.0.0",
        "database": db_status
    }


@router.get("/model/status", response_model=ModelStatusResponse)
def get_model_status():
    ml_ready = ml_service.is_ready()
    return {
        "job_model_status": "Available" if ml_ready else "Unavailable",
        "job_model_name": "TF-IDF + Balanced Logistic Regression",
        "svm_model_status": "Available" if settings.SVM_MODEL_PATH.exists() else "Unavailable",
        "vectorizer_status": "Available" if settings.VECTORIZER_PATH.exists() else "Unavailable",
        "transformer_status": "Available" if (settings.HF_TOKEN and settings.HF_TOKEN.strip()) else "Unavailable",
        "transformer_model": settings.HF_MODEL
    }


@router.get("/datasets/status", response_model=DatasetStatusResponse)
def get_datasets_status():
    emscad_avail = settings.PROCESSED_JOBS_FILE.exists()
    emscad_rows = 0
    emscad_fraud_ratio = "0%"

    if emscad_avail:
        try:
            import pandas as pd
            df_jobs = pd.read_csv(settings.PROCESSED_JOBS_FILE)
            emscad_rows = len(df_jobs)
            if "fraudulent" in df_jobs.columns:
                fraud_count = int(df_jobs["fraudulent"].sum())
                emscad_fraud_ratio = f"{round((fraud_count / emscad_rows) * 100, 1)}%"
        except Exception:
            pass

    reviews_avail = settings.PROCESSED_REVIEWS_FILE.exists()
    reviews_rows = 0
    reviews_companies = 0
    if reviews_avail:
        try:
            import pandas as pd
            df_revs = pd.read_csv(settings.PROCESSED_REVIEWS_FILE)
            reviews_rows = len(df_revs)
            reviews_companies = int(df_revs["company"].nunique())
        except Exception:
            pass

    return {
        "emscad_available": emscad_avail,
        "emscad_rows": emscad_rows,
        "emscad_features": 18,
        "emscad_fraud_ratio": emscad_fraud_ratio,
        "additional_job_available": (settings.RAW_DATA_DIR / "job_fraud" / "additional_jobs_raw.csv").exists(),
        "additional_job_rows": 4,
        "reviews_available": reviews_avail,
        "reviews_rows": reviews_rows,
        "reviews_companies_count": reviews_companies,
        "reviews_status": "Available" if reviews_avail else "Unavailable"
    }


@router.get("/metrics")
def get_metrics():
    if not settings.METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="Model metrics not generated. Please run train_model.py.")
    with open(settings.METRICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/analyze", response_model=JobAnalysisResponse)
def analyze_job(
    req: JobAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    """Run the shared recruitment analysis pipeline for an authenticated request."""
    return analyze_job_pipeline(req, db, current_user)


@router.get("/analysis/{analysis_id}", response_model=JobAnalysisResponse)
def get_analysis_by_id(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id,
    )
    analysis = query.first()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis ID {analysis_id} not found.")

    contributions = [
        EvidenceContribution(**c) for c in (analysis.evidence_contributions or [])
    ]
    summary = {
        "trust_score": analysis.trust_score,
        "risk_level": analysis.risk_level,
        "confidence": analysis.confidence,
        "evidence": [
            {
                "source": item.get("category", "unknown"),
                "signal": item.get("state", "unknown"),
                "score": float(item.get("contribution", 0.0)),
                "confidence": 0.5,
                "status": item.get("state", "unknown"),
                "explanation": "Stored analysis contribution",
            }
            for item in (analysis.evidence_contributions or [])
        ],
        "summary": (
            "Likely legitimate and internally consistent."
            if analysis.risk_level == "Likely Legitimate"
            else "Needs additional verification before making a hiring decision."
            if analysis.risk_level == "Needs Verification"
            else "High-risk indicators detected. Additional verification is strongly recommended."
        )
    }

    return {
        "id": analysis.id,
        "job_title": analysis.job_title,
        "company_name": analysis.company_name,
        "trust_score": analysis.trust_score,
        "risk_level": analysis.risk_level,
        "fraud_probability": analysis.fraud_probability,
        "confidence": analysis.confidence,
        "positive_evidence": analysis.positive_evidence or [],
        "negative_evidence": analysis.negative_evidence or [],
        "unknown_evidence": analysis.unknown_evidence or [],
        "evidence_contributions": contributions,
        "evidence_details": analysis.evidence_details or {},
        "advanced_ai_analysis": {
            "total_signals_evaluated": len(analysis.evidence_contributions or []),
            "model_fusion": {
                "evidence_index": analysis.evidence_details.get("evidence_index", 0.0) if analysis.evidence_details else 0.0,
                "trust_score": analysis.trust_score,
                "risk_level": analysis.risk_level,
                "confidence": analysis.confidence,
            },
            "feature_contributions": contributions,
            "model_outputs": [
                analysis.ml_result or {},
                analysis.transformer_result or {},
            ],
        },
        "live_verification": {
            "domain": analysis.domain_result or {},
            "company_reputation": analysis.company_result or {},
        },
        "job_assessment": summary,
        "company_reputation": {
            "company_name": analysis.company_name or "",
            "workplace_reputation": "Insufficient Evidence",
            "public_reputation": "Insufficient Evidence",
            "identity_confidence": 0.0,
            "evidence_confidence": 0.0,
            "aspects": analysis.company_result.get("aspects", {}) if isinstance(analysis.company_result, dict) else {},
            "evidence": [],
        },
        "ml_result": analysis.ml_result or {},
        "transformer_result": analysis.transformer_result or {},
        "recruiter_result": analysis.recruiter_result or {},
        "company_result": analysis.company_result or {},
        "website_result": analysis.website_result or {},
        "domain_result": analysis.domain_result or {},
        "salary_result": analysis.salary_result or {},
        "external_verification": (
            build_consent_section(
                analysis.id,
                extract_verification_details(
                    {
                        "job_title": analysis.job_title,
                        "company_name": analysis.company_name,
                        "recruiter_email": analysis.recruiter_email,
                        "company_website": analysis.company_website,
                        "location": analysis.location,
                        "salary": analysis.salary,
                        "job_description": analysis.job_description,
                    }
                ),
                analysis.external_verification_consent,
            )
            if analysis.analysis_mode == "private_email"
            else {}
        ),
        "created_at": analysis.created_at
    }


def _owned_private_analysis(
    db: Session, analysis_id: int, current_user: User
) -> Analysis:
    analysis = (
        db.query(Analysis)
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
        )
        .first()
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if analysis.analysis_mode != "private_email":
        raise HTTPException(
            status_code=400,
            detail="External verification consent is available only for private email analysis.",
        )
    return analysis


def _external_verification_stale_filter(now: datetime):
    legacy_expired_before = now - timedelta(
        seconds=EXTERNAL_VERIFICATION_LEASE_SECONDS
    )
    return or_(
        ExternalVerificationConsent.execution_lease_expires_at <= now,
        and_(
            ExternalVerificationConsent.execution_lease_expires_at.is_(None),
            or_(
                ExternalVerificationConsent.execution_started_at.is_(None),
                ExternalVerificationConsent.execution_started_at
                <= legacy_expired_before,
            ),
        ),
    )


def _recover_expired_external_verification(
    db: Session,
    record: ExternalVerificationConsent,
    now: datetime,
) -> bool:
    selected = list(record.selected_checks or [])
    results = record.results or {}
    all_results_saved = bool(selected) and all(check in results for check in selected)
    has_unavailable = any(
        results.get(check, {}).get("status") == "Unavailable"
        for check in selected
    )
    recovered_status = (
        result_statuses(results, selected) if all_results_saved else "failed"
    )
    recovery_reason = (
        "lease_expired_after_results_saved"
        if all_results_saved and not has_unavailable
        else "lease_expired_recovered"
    )

    updated = (
        db.query(ExternalVerificationConsent)
        .filter(
            ExternalVerificationConsent.id == record.id,
            ExternalVerificationConsent.status == "running",
            _external_verification_stale_filter(now),
        )
        .update(
            {
                ExternalVerificationConsent.status: recovered_status,
                ExternalVerificationConsent.execution_lease_expires_at: None,
                ExternalVerificationConsent.execution_id: None,
                ExternalVerificationConsent.failure_reason: recovery_reason,
                ExternalVerificationConsent.executed_at: now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    db.refresh(record)
    return updated == 1


@router.get("/analyses/{analysis_id}/external-verification")
def get_external_verification_status(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = _owned_private_analysis(db, analysis_id, current_user)
    record = (
        db.query(ExternalVerificationConsent)
        .filter(
            ExternalVerificationConsent.analysis_id == analysis.id,
            ExternalVerificationConsent.user_id == current_user.id,
        )
        .first()
    )
    if record is None:
        return build_consent_section(
            analysis.id,
            extract_verification_details(
                {
                    "job_title": analysis.job_title,
                    "company_name": analysis.company_name,
                    "recruiter_email": analysis.recruiter_email,
                    "company_website": analysis.company_website,
                    "location": analysis.location,
                    "salary": analysis.salary,
                    "job_description": analysis.job_description,
                }
            ),
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if record.status == "running":
        _recover_expired_external_verification(db, record, now)
    details = extract_verification_details(
        {
            "job_title": analysis.job_title,
            "company_name": analysis.company_name,
            "recruiter_email": analysis.recruiter_email,
            "company_website": analysis.company_website,
            "location": analysis.location,
            "salary": analysis.salary,
            "job_description": analysis.job_description,
        }
    )
    return build_consent_section(analysis.id, details, record)


@router.post("/analyses/{analysis_id}/external-verification/consent")
def submit_external_verification_consent(
    analysis_id: int,
    request: ExternalVerificationConsentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    analysis = _owned_private_analysis(db, analysis_id, current_user)
    details = extract_verification_details(
        {
            "job_title": analysis.job_title,
            "company_name": analysis.company_name,
            "recruiter_email": analysis.recruiter_email,
            "company_website": analysis.company_website,
            "location": analysis.location,
            "salary": analysis.salary,
            "job_description": analysis.job_description,
        }
    )
    if request.consent:
        try:
            validate_selected_checks(request.selected_checks, details)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = (
        db.query(ExternalVerificationConsent)
        .filter(
            ExternalVerificationConsent.analysis_id == analysis.id,
            ExternalVerificationConsent.user_id == current_user.id,
        )
        .first()
    )
    if record is not None and record.status in {
        "running",
        "completed",
        "partial",
        "failed",
    }:
        raise HTTPException(
            status_code=409,
            detail="Verification consent can no longer be changed for this analysis.",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if record is None:
        record = ExternalVerificationConsent(
            analysis_id=analysis.id,
            user_id=current_user.id,
            selected_checks=request.selected_checks if request.consent else [],
            status="consented" if request.consent else "declined",
            consented_at=now if request.consent else None,
            created_at=now,
        )
        db.add(record)
    else:
        updated = (
            db.query(ExternalVerificationConsent)
            .filter(
                ExternalVerificationConsent.analysis_id == analysis.id,
                ExternalVerificationConsent.user_id == current_user.id,
                ExternalVerificationConsent.status.in_(("consented", "declined")),
            )
            .update(
                {
                    ExternalVerificationConsent.selected_checks:
                        request.selected_checks if request.consent else [],
                    ExternalVerificationConsent.status:
                        "consented" if request.consent else "declined",
                    ExternalVerificationConsent.consented_at:
                        now if request.consent else None,
                    ExternalVerificationConsent.execution_started_at: None,
                    ExternalVerificationConsent.executed_at: None,
                    ExternalVerificationConsent.results: {},
                },
                synchronize_session=False,
            )
        )
        if updated != 1:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Verification consent can no longer be changed for this analysis.",
            )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Verification consent changed concurrently. Reload the analysis.",
        ) from exc
    db.refresh(record)
    return build_consent_section(analysis.id, details, record)


@router.post("/analyses/{analysis_id}/external-verification/run")
def run_external_verification(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    analysis = _owned_private_analysis(db, analysis_id, current_user)
    details = extract_verification_details(
        {
            "job_title": analysis.job_title,
            "company_name": analysis.company_name,
            "recruiter_email": analysis.recruiter_email,
            "company_website": analysis.company_website,
            "location": analysis.location,
            "salary": analysis.salary,
            "job_description": analysis.job_description,
        }
    )
    record = (
        db.query(ExternalVerificationConsent)
        .filter(
            ExternalVerificationConsent.analysis_id == analysis.id,
            ExternalVerificationConsent.user_id == current_user.id,
        )
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=409,
            detail="Explicit consent is required before external verification.",
        )
    if record.status == "declined":
        return build_consent_section(analysis.id, details, record)
    if record.status == "completed":
        return build_consent_section(analysis.id, details, record)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if record.status == "running":
        if _recover_expired_external_verification(db, record, now):
            return build_consent_section(analysis.id, details, record)
        raise HTTPException(
            status_code=409,
            detail="External verification is already in progress.",
        )
    if record.status not in {"consented", "partial", "failed"}:
        raise HTTPException(status_code=409, detail="External verification cannot be run.")
    if record.consented_at is None or not record.selected_checks:
        raise HTTPException(
            status_code=409,
            detail="Valid explicit consent is required before external verification.",
        )
    if record.execution_attempts >= MAX_EXTERNAL_VERIFICATION_ATTEMPTS:
        return build_consent_section(analysis.id, details, record)
    try:
        validate_selected_checks(record.selected_checks, details)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="The consented checks no longer have the required information.",
        ) from exc

    execution_id = secrets.token_hex(32)
    started_at = now
    claimed = (
        db.query(ExternalVerificationConsent)
        .filter(
            ExternalVerificationConsent.analysis_id == analysis.id,
            ExternalVerificationConsent.user_id == current_user.id,
            ExternalVerificationConsent.status == record.status,
            ExternalVerificationConsent.consented_at.is_not(None),
            ExternalVerificationConsent.execution_attempts
            < MAX_EXTERNAL_VERIFICATION_ATTEMPTS,
        )
        .update(
            {
                ExternalVerificationConsent.status: "running",
                ExternalVerificationConsent.execution_started_at: started_at,
                ExternalVerificationConsent.execution_lease_expires_at: started_at
                + timedelta(seconds=EXTERNAL_VERIFICATION_LEASE_SECONDS),
                ExternalVerificationConsent.execution_id: execution_id,
                ExternalVerificationConsent.execution_attempts:
                    ExternalVerificationConsent.execution_attempts + 1,
                ExternalVerificationConsent.failure_reason: None,
                ExternalVerificationConsent.executed_at: None,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if claimed != 1:
        db.refresh(record)
        if record.status in {"completed", "partial", "failed", "declined"}:
            return build_consent_section(analysis.id, details, record)
        raise HTTPException(
            status_code=409,
            detail="External verification is already in progress.",
        )

    selected_checks = list(record.selected_checks or [])
    existing_results = dict(record.results or {})
    checks_to_run = [
        check for check in selected_checks
        if check not in existing_results
        or existing_results[check].get("status") == "Unavailable"
    ]
    lease_lost = threading.Event()
    heartbeat_stop = threading.Event()
    lease_session_factory = sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )

    def renew_execution(_: str) -> bool:
        if lease_lost.is_set():
            return False
        renewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        lease_db = lease_session_factory()
        try:
            renewed = (
                lease_db.query(ExternalVerificationConsent)
                .filter(
                    ExternalVerificationConsent.id == record.id,
                    ExternalVerificationConsent.status == "running",
                    ExternalVerificationConsent.execution_id == execution_id,
                    ExternalVerificationConsent.execution_lease_expires_at
                    > renewed_at,
                )
                .update(
                    {
                        ExternalVerificationConsent.execution_lease_expires_at:
                            renewed_at + timedelta(
                                seconds=EXTERNAL_VERIFICATION_LEASE_SECONDS
                            ),
                    },
                    synchronize_session=False,
                )
            )
            lease_db.commit()
        except Exception as exc:
            lease_db.rollback()
            lease_lost.set()
            logger.warning(
                "External verification lease renewal failed (%s).",
                type(exc).__name__,
            )
            return False
        finally:
            lease_db.close()
        if renewed != 1:
            lease_lost.set()
            return False
        return True

    def maintain_execution_lease() -> None:
        while not heartbeat_stop.wait(
            EXTERNAL_VERIFICATION_HEARTBEAT_INTERVAL_SECONDS
        ):
            if not renew_execution("heartbeat"):
                return

    def persist_check_result(check: str, result: dict[str, Any]) -> bool:
        persist_at = datetime.now(timezone.utc).replace(tzinfo=None)
        current = (
            db.query(ExternalVerificationConsent)
            .filter(
                ExternalVerificationConsent.id == record.id,
                ExternalVerificationConsent.status == "running",
                ExternalVerificationConsent.execution_id == execution_id,
                ExternalVerificationConsent.execution_lease_expires_at > persist_at,
            )
            .first()
        )
        if current is None:
            db.rollback()
            return False
        saved_results = dict(current.results or {})
        saved_results[check] = result
        updated = (
            db.query(ExternalVerificationConsent)
            .filter(
                ExternalVerificationConsent.id == record.id,
                ExternalVerificationConsent.status == "running",
                ExternalVerificationConsent.execution_id == execution_id,
                ExternalVerificationConsent.execution_lease_expires_at > persist_at,
            )
            .update(
                {
                    ExternalVerificationConsent.results: saved_results,
                    ExternalVerificationConsent.execution_lease_expires_at:
                        persist_at + timedelta(
                            seconds=EXTERNAL_VERIFICATION_LEASE_SECONDS
                        ),
                },
                synchronize_session=False,
            )
        )
        db.commit()
        return updated == 1

    try:
        if checks_to_run:
            heartbeat = threading.Thread(
                target=maintain_execution_lease,
                name="external-verification-lease",
                daemon=True,
            )
            heartbeat.start()
            try:
                execute_approved_checks(
                    checks_to_run,
                    details,
                    before_check=renew_execution,
                    on_result=persist_check_result,
                )
            finally:
                heartbeat_stop.set()
                heartbeat.join()
        db.refresh(record)
        stored_results = dict(record.results or {})
        all_results_saved = all(check in stored_results for check in selected_checks)
        next_status = (
            result_statuses(stored_results, selected_checks)
            if all_results_saved
            else "failed"
        )
        failure_reason = (
            "provider_unavailable"
            if next_status in {"failed", "partial"}
            else None
        )
        if not all_results_saved:
            failure_reason = "execution_interrupted"
    except Exception as exc:
        logger.warning(
            "External verification execution failed (%s).",
            type(exc).__name__,
        )
        db.rollback()
        next_status = "failed"
        failure_reason = "execution_interrupted"

    finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    finalized = (
        db.query(ExternalVerificationConsent)
        .filter(
            ExternalVerificationConsent.id == record.id,
            ExternalVerificationConsent.status == "running",
            ExternalVerificationConsent.execution_id == execution_id,
            ExternalVerificationConsent.execution_lease_expires_at > finished_at,
        )
        .update(
            {
                ExternalVerificationConsent.status: next_status,
                ExternalVerificationConsent.failure_reason: failure_reason,
                ExternalVerificationConsent.execution_lease_expires_at: None,
                ExternalVerificationConsent.execution_id: None,
                ExternalVerificationConsent.executed_at: finished_at,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if finalized != 1:
        db.refresh(record)
        if record.status == "running":
            _recover_expired_external_verification(db, record, finished_at)
    db.refresh(record)
    return build_consent_section(analysis.id, details, record)


@router.get("/history", response_model=HistoryResponse)
def get_history(
    risk: Optional[str] = Query(None, description="Filter by risk level"),
    search: Optional[str] = Query(None, description="Search by title or company"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Analysis).filter(Analysis.user_id == current_user.id)
    if risk and risk != "ALL":
        if risk.upper() in {"UNCERTAIN", "NEEDS VERIFICATION", "NEEDS_VERIFICATION"}:
            query = query.filter(
                (Analysis.risk_level.ilike("%uncertain%")) | (Analysis.risk_level.ilike("%verification%"))
            )
        else:
            query = query.filter(Analysis.risk_level.ilike(f"%{risk}%"))
    if search and search.strip():
        term = search.strip()
        query = query.filter(
            (Analysis.job_title.ilike(f"%{term}%")) | (Analysis.company_name.ilike(f"%{term}%"))
        )

    records = query.order_by(Analysis.created_at.desc()).all()
    items = [
        AnalysisHistoryItem(
            id=r.id,
            job_title=r.job_title,
            company_name=r.company_name,
            recruiter_email=r.recruiter_email,
            company_website=r.company_website,
            location=r.location,
            employment_type=r.employment_type,
            salary=r.salary,
            job_description=r.job_description,
            requirements=r.requirements,
            benefits=r.benefits,
            trust_score=r.trust_score,
            risk_level=r.risk_level,
            fraud_probability=r.fraud_probability,
            confidence=r.confidence,
            created_at=r.created_at
        ) for r in records
    ]
    return {"total": len(items), "analyses": items}


@router.post("/company/reputation", response_model=CompanyReputationResponse)
async def analyze_company_reputation(req: CompanyReputationRequest):
    base = reputation_service.analyze_company(req.company_name)
    live = await reputation_service.analyze_live_verification(req.company_name, req.domain)
    merged = {**base, **live["company_reputation"], "live_verification": live}

    public_signal = 0.0
    if merged.get("detected_risk_keywords"):
        public_signal = -0.2 * len(merged["detected_risk_keywords"])
    if merged.get("is_verified_entity"):
        public_signal += 0.35
    if merged.get("sentiment_polarity", 0.0) > 0:
        public_signal += 0.25
    elif merged.get("sentiment_polarity", 0.0) < 0:
        public_signal -= 0.25

    if merged.get("average_rating", 0.0) >= 4.0:
        workplace_reputation = "Positive"
    elif merged.get("average_rating", 0.0) >= 2.5:
        workplace_reputation = "Mixed"
    elif merged.get("total_reviews", 0) > 0:
        workplace_reputation = "Negative"
    else:
        workplace_reputation = "Insufficient Evidence"

    public_reputation = "Positive" if public_signal >= 0.2 else "Mixed" if public_signal > -0.1 else "Negative" if merged.get("total_reviews", 0) > 0 else "Insufficient Evidence"
    if merged.get("total_reviews", 0) == 0 and not merged.get("is_verified_entity"):
        public_reputation = "Insufficient Evidence"

    merged.update({
        "identity_confidence": round(max(0.0, min(1.0, float(merged.get("reputation_score", 50)) / 100.0)), 2),
        "workplace_reputation": workplace_reputation,
        "public_reputation": public_reputation,
        "evidence_confidence": round(max(0.0, min(1.0, float(merged.get("confidence", 0.0)) + (0.15 if merged.get("official_domain") else 0.0))), 2),
        "evidence": [
            {
                "source_name": "Employee Review Dataset",
                "source_type": "dataset",
                "evidence_text": f"{merged.get('total_reviews', 0)} employee reviews analyzed.",
                "confidence": merged.get("confidence", 0.0),
                "status": "available",
            },
            {"source_name": "Live Company Search", "source_type": "search", "evidence_text": merged.get("explanation", "No public search result available."), "confidence": float(merged.get("confidence", 0.0)) or 0.5, "status": "available"},
        ]
    })
    return merged


@router.get("/company/{company_name}/reputation", response_model=CompanyReputationResponse)
async def get_company_reputation(company_name: str, domain: Optional[str] = Query(None)):
    base = reputation_service.analyze_company(company_name)
    live = await reputation_service.analyze_live_verification(company_name, domain)
    merged = {**base, **live["company_reputation"], "live_verification": live}

    public_signal = 0.0
    if merged.get("detected_risk_keywords"):
        public_signal = -0.2 * len(merged["detected_risk_keywords"])
    if merged.get("is_verified_entity"):
        public_signal += 0.35
    if merged.get("sentiment_polarity", 0.0) > 0:
        public_signal += 0.25
    elif merged.get("sentiment_polarity", 0.0) < 0:
        public_signal -= 0.25

    if merged.get("average_rating", 0.0) >= 4.0:
        workplace_reputation = "Positive"
    elif merged.get("average_rating", 0.0) >= 2.5:
        workplace_reputation = "Mixed"
    elif merged.get("total_reviews", 0) > 0:
        workplace_reputation = "Negative"
    else:
        workplace_reputation = "Insufficient Evidence"

    public_reputation = "Positive" if public_signal >= 0.2 else "Mixed" if public_signal > -0.1 else "Negative" if merged.get("total_reviews", 0) > 0 else "Insufficient Evidence"
    if merged.get("total_reviews", 0) == 0 and not merged.get("is_verified_entity"):
        public_reputation = "Insufficient Evidence"

    merged.update({
        "identity_confidence": round(max(0.0, min(1.0, float(merged.get("reputation_score", 50)) / 100.0)), 2),
        "workplace_reputation": workplace_reputation,
        "public_reputation": public_reputation,
        "evidence_confidence": round(max(0.0, min(1.0, float(merged.get("confidence", 0.0)) + (0.15 if merged.get("official_domain") else 0.0))), 2),
        "evidence": [
            {
                "source_name": "Employee Review Dataset",
                "source_type": "dataset",
                "evidence_text": f"{merged.get('total_reviews', 0)} employee reviews analyzed.",
                "confidence": merged.get("confidence", 0.0),
                "status": "available",
            },
            {"source_name": "Live Company Search", "source_type": "search", "evidence_text": merged.get("explanation", "No public search result available."), "confidence": float(merged.get("confidence", 0.0)) or 0.5, "status": "available"},
        ]
    })
    return merged


def _investigation_response(investigation: Any) -> dict:
    report = investigation.report or {}
    return {
        "id": investigation.id,
        "company_name": investigation.company_name,
        "domain": investigation.domain,
        "status": investigation.status,
        "created_at": investigation.created_at,
        "completed_at": investigation.completed_at,
        "assessments": report.get("assessments", {}),
        "evidence": investigation.evidence,
        "information_types": report.get("information_types", {}),
        "limitations": report.get("limitations", []),
    }


@router.post(
    "/company/investigations",
    response_model=CompanyInvestigationResponse,
    status_code=201,
)
async def create_company_investigation(
    payload: CompanyInvestigationRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    client_ip = get_client_ip(request, settings.TRUSTED_PROXY_IPS)
    rate_keys = (
        f"company-investigation:user:{current_user.id}",
        f"company-investigation:ip:{client_ip}",
    )
    for key in rate_keys:
        retry_after = rate_limiter.consume(
            key,
            settings.COMPANY_INVESTIGATION_LIMIT,
            settings.COMPANY_INVESTIGATION_WINDOW_SECONDS,
        )
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Too many investigation requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    investigation = await create_investigation(db, current_user, payload)
    return _investigation_response(investigation)


@router.get(
    "/company/investigations",
    response_model=list[CompanyInvestigationListItem],
)
def list_company_investigations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigations = (
        db.query(CompanyInvestigation)
        .filter(CompanyInvestigation.user_id == current_user.id)
        .order_by(CompanyInvestigation.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": item.id,
            "company_name": item.company_name,
            "domain": item.domain,
            "status": item.status,
            "created_at": item.created_at,
            "assessments": (item.report or {}).get("assessments", {}),
        }
        for item in investigations
    ]


@router.get(
    "/company/investigations/{investigation_id}",
    response_model=CompanyInvestigationResponse,
)
def get_company_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = get_owned_investigation(db, investigation_id, current_user)
    return _investigation_response(investigation)


@router.get(
    "/company/investigations/{investigation_id}/graph",
    response_model=InvestigationGraphResponse,
)
def get_company_investigation_graph(
    investigation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_investigation(db, investigation_id, current_user)
    entities = (
        db.query(InvestigationEntity)
        .filter(InvestigationEntity.investigation_id == investigation_id)
        .order_by(InvestigationEntity.entity_type, InvestigationEntity.display_name)
        .all()
    )
    relationships = (
        db.query(InvestigationRelationship)
        .options(
            selectinload(InvestigationRelationship.evidence_links).selectinload(
                InvestigationRelationshipEvidence.evidence
            )
        )
        .filter(InvestigationRelationship.investigation_id == investigation_id)
        .order_by(InvestigationRelationship.relationship_type)
        .all()
    )
    return {
        "investigation_id": investigation_id,
        "entities": [
            {
                "id": entity.id,
                "entity_type": entity.entity_type,
                "display_name": entity.display_name,
                "attributes": entity.attributes or {},
            }
            for entity in entities
        ],
        "relationships": [
            {
                "id": relationship.id,
                "source_entity_id": relationship.source_entity_id,
                "target_entity_id": relationship.target_entity_id,
                "relationship_type": relationship.relationship_type,
                "status": relationship.status,
                "explanation": relationship.explanation,
                "limitations": relationship.limitations,
                "evidence": [
                    {
                        "id": link.evidence.id,
                        "finding": link.evidence.finding,
                        "source_name": link.evidence.source_name,
                        "source_url": link.evidence.source_url,
                        "retrieved_at": link.evidence.retrieved_at,
                        "status": link.evidence.status,
                        "factual_summary": link.evidence.factual_summary,
                        "source_reliability": link.evidence.source_reliability,
                        "relevance": link.evidence.relevance,
                        "explanation": link.evidence.explanation,
                        "limitations": link.evidence.limitations,
                    }
                    for link in relationship.evidence_links
                ],
            }
            for relationship in relationships
        ],
    }


@router.delete("/company/investigations/{investigation_id}", status_code=204)
def delete_company_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    investigation = get_owned_investigation(db, investigation_id, current_user)
    db.delete(investigation)
    db.commit()
    return None


@router.post("/company/claims", response_model=CompanyClaimResponse)
def analyze_company_claim(req: CompanyClaimRequest):
    return claim_service.evaluate_claim(req.company_name, req.claim)


@router.post("/reviews/analyze")
def analyze_review_credibility(req: ReviewAnalysisRequest):
    return review_credibility_service.analyze_review(
        company_name=req.company_name,
        review_text=req.review_text,
        source_type=req.source_type,
        source_name=req.source_name,
        source_url=req.source_url,
        role=req.role,
        location=req.location,
        review_date=req.review_date,
    )
