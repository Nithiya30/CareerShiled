import datetime
from sqlalchemy import (
    CheckConstraint,
    Column,
    Integer,
    String,
    Float,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.db import Base

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(120), nullable=True, index=True)
    analysis_mode = Column(String(20), nullable=False, default="job")
    job_title = Column(String(255), nullable=False, index=True)
    company_name = Column(String(255), nullable=True, index=True)
    recruiter_email = Column(String(255), nullable=True)
    company_website = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    employment_type = Column(String(100), nullable=True)
    salary = Column(String(100), nullable=True)
    job_description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)
    
    # Computed Intelligence
    trust_score = Column(Float, nullable=False)
    risk_level = Column(String(50), nullable=False)  # Likely Legitimate, Uncertain, Likely Fraudulent
    fraud_probability = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    
    # Structured Evidence JSONs
    positive_evidence = Column(JSON, default=list)
    negative_evidence = Column(JSON, default=list)
    unknown_evidence = Column(JSON, default=list)
    evidence_contributions = Column(JSON, default=list)
    evidence_details = Column(JSON, default=dict)
    
    # Detailed Agent Outputs
    ml_result = Column(JSON, default=dict)
    transformer_result = Column(JSON, default=dict)
    recruiter_result = Column(JSON, default=dict)
    company_result = Column(JSON, default=dict)
    website_result = Column(JSON, default=dict)
    domain_result = Column(JSON, default=dict)
    salary_result = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    evidence_items = relationship("EvidenceItem", back_populates="analysis", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="analysis", cascade="all, delete-orphan")
    external_verification_consent = relationship(
        "ExternalVerificationConsent",
        back_populates="analysis",
        cascade="all, delete-orphan",
        uselist=False,
    )
    linkedin_verifications = relationship(
        "LinkedInVerification", back_populates="analysis", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String(320), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    sessions = relationship("AuthSession", back_populates="user", cascade="all, delete-orphan")
    gmail_oauth_states = relationship(
        "GmailOAuthState", back_populates="user", cascade="all, delete-orphan"
    )
    connected_gmail_account = relationship(
        "ConnectedGmailAccount", back_populates="user", cascade="all, delete-orphan",
        uselist=False,
    )
    email_monitoring_setting = relationship(
        "EmailMonitoringSetting", back_populates="user", cascade="all, delete-orphan",
        uselist=False,
    )
    processed_gmail_messages = relationship(
        "ProcessedGmailMessage", back_populates="user", cascade="all, delete-orphan"
    )
    suspicious_email_alerts = relationship(
        "SuspiciousEmailAlert", back_populates="user", cascade="all, delete-orphan"
    )
    linkedin_verifications = relationship(
        "LinkedInVerification", back_populates="user", cascade="all, delete-orphan"
    )
    external_verification_consents = relationship(
        "ExternalVerificationConsent", back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash = Column(String(64), primary_key=True)
    csrf_token_hash = Column(String(64), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    expires_at = Column(DateTime, nullable=False, index=True)

    user = relationship("User", back_populates="sessions")


class GmailOAuthState(Base):
    __tablename__ = "gmail_oauth_states"

    state_hash = Column(String(64), primary_key=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    consumed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="gmail_oauth_states")


class ConnectedGmailAccount(Base):
    __tablename__ = "connected_gmail_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_connected_gmail_accounts_user_id"),
        UniqueConstraint("google_subject", name="uq_connected_gmail_accounts_google_subject"),
        UniqueConstraint("id", "user_id", name="uq_connected_gmail_accounts_id_user_id"),
        CheckConstraint(
            "status IN ('connected', 'reauth_required', 'revoked')",
            name="ck_connected_gmail_accounts_status",
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    google_subject = Column(String(255), nullable=False)
    gmail_address = Column(String(320), nullable=False)
    refresh_token_ciphertext = Column(Text, nullable=False)
    token_key_version = Column(String(64), nullable=False)
    granted_scopes = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="connected")
    connected_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    user = relationship("User", back_populates="connected_gmail_account")
    monitoring_setting = relationship(
        "EmailMonitoringSetting",
        back_populates="account",
        cascade="all, delete-orphan",
        uselist=False,
        foreign_keys="EmailMonitoringSetting.account_id",
    )
    processed_messages = relationship(
        "ProcessedGmailMessage",
        back_populates="account",
        cascade="all, delete-orphan",
        foreign_keys="ProcessedGmailMessage.account_id",
    )


class EmailMonitoringSetting(Base):
    __tablename__ = "email_monitoring_settings"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_email_monitoring_settings_account_id"),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["connected_gmail_accounts.id", "connected_gmail_accounts.user_id"],
            ondelete="CASCADE",
            name="fk_email_monitoring_settings_account_user",
        ),
        CheckConstraint(
            "enabled = false OR (consented_at IS NOT NULL AND consent_version IS NOT NULL)",
            name="ck_email_monitoring_settings_enabled_has_consent",
        ),
        CheckConstraint(
            "(poll_lock_token IS NULL AND poll_lock_expires_at IS NULL) OR "
            "(poll_lock_token IS NOT NULL AND poll_lock_expires_at IS NOT NULL)",
            name="ck_email_monitoring_settings_poll_lock_pair",
        ),
    )

    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    account_id = Column(String(36), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=False)
    consent_version = Column(String(64), nullable=True)
    consented_at = Column(DateTime, nullable=True)
    baseline_history_id = Column(String(64), nullable=True)
    last_history_id = Column(String(64), nullable=True)
    last_polled_at = Column(DateTime, nullable=True, index=True)
    last_successful_sync_at = Column(DateTime, nullable=True)
    scanned_count = Column(Integer, nullable=False, default=0)
    recruitment_count = Column(Integer, nullable=False, default=0)
    suspicious_count = Column(Integer, nullable=False, default=0)
    last_error_code = Column(String(64), nullable=True)
    poll_lock_token = Column(String(64), nullable=True)
    poll_lock_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    user = relationship("User", back_populates="email_monitoring_setting")
    account = relationship(
        "ConnectedGmailAccount",
        back_populates="monitoring_setting",
        foreign_keys=[account_id],
    )


class ProcessedGmailMessage(Base):
    __tablename__ = "processed_gmail_messages"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "gmail_message_id",
            name="uq_processed_gmail_messages_account_message",
        ),
        UniqueConstraint("id", "user_id", name="uq_processed_gmail_messages_id_user_id"),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["connected_gmail_accounts.id", "connected_gmail_accounts.user_id"],
            ondelete="CASCADE",
            name="fk_processed_gmail_messages_account_user",
        ),
        CheckConstraint(
            "status IN ('processing', 'not_recruitment', 'analyzed', 'failed', 'skipped')",
            name="ck_processed_gmail_messages_status",
        ),
    )

    id = Column(String(36), primary_key=True)
    account_id = Column(String(36), nullable=False, index=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gmail_message_id = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="processing", index=True)
    is_recruitment = Column(Boolean, nullable=True)
    analysis_id = Column(
        Integer, ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    last_error_code = Column(String(64), nullable=True)

    user = relationship("User", back_populates="processed_gmail_messages")
    account = relationship(
        "ConnectedGmailAccount",
        back_populates="processed_messages",
        foreign_keys=[account_id],
    )
    analysis = relationship("Analysis")
    alert = relationship(
        "SuspiciousEmailAlert",
        back_populates="processed_message",
        cascade="all, delete-orphan",
        uselist=False,
        foreign_keys="SuspiciousEmailAlert.processed_message_id",
    )


class SuspiciousEmailAlert(Base):
    __tablename__ = "suspicious_email_alerts"
    __table_args__ = (
        UniqueConstraint(
            "processed_message_id",
            name="uq_suspicious_email_alerts_processed_message_id",
        ),
        ForeignKeyConstraint(
            ["processed_message_id", "user_id"],
            ["processed_gmail_messages.id", "processed_gmail_messages.user_id"],
            ondelete="CASCADE",
            name="fk_suspicious_email_alerts_message_user",
        ),
        CheckConstraint(
            "severity IN ('medium', 'high')",
            name="ck_suspicious_email_alerts_severity",
        ),
        Index(
            "ix_suspicious_email_alerts_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_suspicious_email_alerts_user_read_created",
            "user_id",
            "is_read",
            "created_at",
        ),
        Index(
            "ix_suspicious_email_alerts_user_severity_created",
            "user_id",
            "severity",
            "created_at",
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    processed_message_id = Column(String(36), nullable=False)
    severity = Column(String(16), nullable=False)
    risk_level = Column(String(50), nullable=False)
    trust_score = Column(Float, nullable=False)
    subject = Column(String(500), nullable=True)
    sender_email = Column(String(320), nullable=True)
    company_name = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)
    indicators = Column(JSON, nullable=False, default=list)
    explanation = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    read_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="suspicious_email_alerts")
    processed_message = relationship(
        "ProcessedGmailMessage",
        back_populates="alert",
        foreign_keys=[processed_message_id],
    )


class LinkedInVerification(Base):
    __tablename__ = "linkedin_verifications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('MATCH FOUND', 'PARTIAL MATCH', 'NO MATCH FOUND', "
            "'UNAVAILABLE', 'INSUFFICIENT INFORMATION')",
            name="ck_linkedin_verifications_status",
        ),
        Index(
            "ix_linkedin_verifications_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_linkedin_verifications_analysis_created",
            "analysis_id",
            "created_at",
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id = Column(
        Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_url = Column(Text, nullable=True)
    status = Column(String(32), nullable=False)
    source_name = Column(String(255), nullable=True)
    source_url = Column(Text, nullable=True)
    matched_job_title = Column(String(255), nullable=True)
    matched_company = Column(String(255), nullable=True)
    matched_location = Column(String(255), nullable=True)
    field_comparisons = Column(JSON, nullable=False, default=dict)
    explanation = Column(Text, nullable=False)
    checked_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="linkedin_verifications")
    analysis = relationship("Analysis", back_populates="linkedin_verifications")


class ExternalVerificationConsent(Base):
    __tablename__ = "external_verification_consents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('declined', 'consented', 'running', 'completed', 'partial', 'failed')",
            name="ck_external_verification_consents_status",
        ),
        UniqueConstraint("analysis_id", name="uq_external_verification_analysis_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(
        Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected_checks = Column(JSON, nullable=False, default=list)
    status = Column(String(16), nullable=False)
    consented_at = Column(DateTime, nullable=True)
    execution_started_at = Column(DateTime, nullable=True)
    execution_lease_expires_at = Column(DateTime, nullable=True)
    execution_id = Column(String(64), nullable=True)
    execution_attempts = Column(Integer, nullable=False, default=0)
    failure_reason = Column(String(64), nullable=True)
    executed_at = Column(DateTime, nullable=True)
    results = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="external_verification_consents")
    analysis = relationship("Analysis", back_populates="external_verification_consent")


class EvidenceItem(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(100), nullable=False)  # ml, transformer, scam, recruiter, company, website, domain, salary
    signal = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    evidence_state = Column(String(50), nullable=False)  # positive, negative, unknown
    score = Column(Float, nullable=False)  # -1.0 to 1.0
    weight = Column(Float, nullable=False)
    quality = Column(Float, nullable=False)  # 0.0 to 1.0
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    analysis = relationship("Analysis", back_populates="evidence_items")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_label = Column(String(50), nullable=False)  # legitimate, fraudulent, unsure
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    analysis = relationship("Analysis", back_populates="feedbacks")


class CompanyReview(Base):
    __tablename__ = "company_reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    review_id = Column(String(100), unique=True, index=True, nullable=True)
    company = Column(String(255), nullable=False, index=True)
    date = Column(String(50), nullable=True)
    rating = Column(Float, nullable=False)
    review_text = Column(Text, nullable=False)
    
    # Aspect Ratings (1.0 - 5.0)
    work_life_balance = Column(Float, nullable=True)
    salary_benefits = Column(Float, nullable=True)
    career_growth = Column(Float, nullable=True)
    job_security = Column(Float, nullable=True)
    management = Column(Float, nullable=True)
    work_satisfaction = Column(Float, nullable=True)
    skill_development = Column(Float, nullable=True)
    culture = Column(Float, nullable=True)
    workload = Column(Float, nullable=True)
    
    likes = Column(Text, nullable=True)
    dislikes = Column(Text, nullable=True)
    source = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class CompanyClaim(Base):
    __tablename__ = "company_claims"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company = Column(String(255), nullable=False, index=True)
    claim = Column(Text, nullable=False)
    aspect = Column(String(100), nullable=True)
    sentiment = Column(String(50), nullable=True)
    evidence_status = Column(String(50), nullable=False)  # Supported, Partially Supported, Contradicted, Unverified, Insufficient Evidence
    confidence = Column(Float, nullable=False)
    supporting_evidence = Column(JSON, default=list)
    contradicting_evidence = Column(JSON, default=list)
    total_relevant_reviews = Column(Integer, default=0)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ReputationSummary(Base):
    __tablename__ = "reputation_summaries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company = Column(String(255), unique=True, index=True, nullable=False)
    total_reviews = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    positive_reviews_count = Column(Integer, default=0)
    neutral_reviews_count = Column(Integer, default=0)
    negative_reviews_count = Column(Integer, default=0)
    aspects = Column(JSON, default=dict)
    confidence = Column(Float, default=0.0)
    website = Column(String(255), nullable=True)
    domain_status = Column(String(100), nullable=True)
    career_page = Column(String(255), nullable=True)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)


class WorkLifeCompany(Base):
    __tablename__ = "worklife_companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )

    reviews = relationship(
        "WorkLifeReview",
        back_populates="company",
        cascade="all, delete-orphan",
    )


class WorkLifeReview(Base):
    __tablename__ = "worklife_reviews"
    __table_args__ = (
        CheckConstraint(
            "employment_status IN ('current', 'former')",
            name="ck_worklife_review_employment_status",
        ),
        CheckConstraint(
            "moderation_status IN ('pending', 'approved', 'rejected', 'withdrawn')",
            name="ck_worklife_review_moderation_status",
        ),
        *(
            CheckConstraint(
                f"{column} IS NULL OR ({column} >= 1 AND {column} <= 5)",
                name=f"ck_worklife_review_{column}",
            )
            for column in (
                "work_life_balance",
                "salary_satisfaction",
                "management_rating",
                "career_growth",
                "learning_opportunities",
                "work_pressure",
                "job_security",
                "overall_rating",
            )
        ),
        UniqueConstraint("company_id", "user_id", name="uq_worklife_review_company_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("worklife_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_role = Column(String(150), nullable=False)
    department = Column(String(150), nullable=True)
    employment_status = Column(String(16), nullable=False)
    work_life_balance = Column(Integer, nullable=False)
    salary_satisfaction = Column(Integer, nullable=False)
    management_rating = Column(Integer, nullable=False)
    career_growth = Column(Integer, nullable=False)
    learning_opportunities = Column(Integer, nullable=False)
    work_pressure = Column(Integer, nullable=False)
    job_security = Column(Integer, nullable=False)
    overall_rating = Column(Integer, nullable=False)
    review_text = Column(Text, nullable=False)
    moderation_status = Column(String(16), nullable=False, default="pending", index=True)
    sentiment = Column(String(16), nullable=True)
    topics = Column(JSON, nullable=False, default=list)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    moderated_at = Column(DateTime, nullable=True)
    moderated_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    moderation_note = Column(String(500), nullable=True)

    company = relationship("WorkLifeCompany", back_populates="reviews")
    reports = relationship(
        "WorkLifeReviewReport",
        back_populates="review",
        cascade="all, delete-orphan",
    )


class WorkLifeReviewReport(Base):
    __tablename__ = "worklife_review_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'reviewed', 'dismissed')",
            name="ck_worklife_review_report_status",
        ),
        UniqueConstraint(
            "review_id",
            "reporter_user_id",
            name="uq_worklife_review_report_review_reporter",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(
        Integer,
        ForeignKey("worklife_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason = Column(String(64), nullable=False)
    details = Column(String(500), nullable=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    review = relationship("WorkLifeReview", back_populates="reports")


class CompanyInvestigation(Base):
    __tablename__ = "company_investigations"

    id = Column(String(36), primary_key=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True)
    contact_domain = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="completed")
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    completed_at = Column(DateTime, nullable=False)
    report = Column(JSON, nullable=False)

    relationships = relationship(
        "InvestigationRelationship",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    evidence = relationship(
        "InvestigationEvidence",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    entities = relationship(
        "InvestigationEntity",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )


class InvestigationEvidence(Base):
    __tablename__ = "investigation_evidence"
    __table_args__ = (
        CheckConstraint(
            "status IN ('supported', 'contradicted', 'inconclusive', 'unavailable')",
            name="ck_investigation_evidence_status",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    investigation_id = Column(
        String(36),
        ForeignKey("company_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding = Column(Text, nullable=False)
    source_name = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=True)
    retrieved_at = Column(String(40), nullable=True)
    factual_summary = Column(Text, nullable=False)
    status = Column(String(32), nullable=False)
    source_reliability = Column(String(32), nullable=False)
    relevance = Column(String(32), nullable=False)
    explanation = Column(Text, nullable=False)
    limitations = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)

    investigation = relationship("CompanyInvestigation", back_populates="evidence")


class InvestigationEntity(Base):
    __tablename__ = "investigation_entities"
    __table_args__ = (
        UniqueConstraint(
            "investigation_id",
            "entity_type",
            "normalized_value",
            name="uq_investigation_entity_value",
        ),
        CheckConstraint(
            "entity_type IN ('company', 'domain', 'contact_domain', 'evidence_source')",
            name="ck_investigation_entity_type",
        ),
    )

    id = Column(String(36), primary_key=True)
    investigation_id = Column(
        String(36),
        ForeignKey("company_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type = Column(String(32), nullable=False)
    display_name = Column(String(500), nullable=False)
    normalized_value = Column(String(1000), nullable=False)
    attributes = Column(JSON, nullable=False, default=dict)

    investigation = relationship("CompanyInvestigation", back_populates="entities")
    outgoing_relationships = relationship(
        "InvestigationRelationship",
        foreign_keys="InvestigationRelationship.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    incoming_relationships = relationship(
        "InvestigationRelationship",
        foreign_keys="InvestigationRelationship.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )


class InvestigationRelationship(Base):
    __tablename__ = "investigation_relationships"
    __table_args__ = (
        CheckConstraint(
            "status IN ('supported', 'contradicted', 'inconclusive', 'unavailable')",
            name="ck_investigation_relationship_status",
        ),
    )

    id = Column(String(36), primary_key=True)
    investigation_id = Column(
        String(36),
        ForeignKey("company_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_entity_id = Column(
        String(36),
        ForeignKey("investigation_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id = Column(
        String(36),
        ForeignKey("investigation_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    explanation = Column(Text, nullable=False)
    limitations = Column(Text, nullable=False)

    investigation = relationship(
        "CompanyInvestigation",
        back_populates="relationships",
    )
    source_entity = relationship(
        "InvestigationEntity",
        foreign_keys=[source_entity_id],
        back_populates="outgoing_relationships",
    )
    target_entity = relationship(
        "InvestigationEntity",
        foreign_keys=[target_entity_id],
        back_populates="incoming_relationships",
    )
    evidence_links = relationship(
        "InvestigationRelationshipEvidence",
        back_populates="relationship_record",
        cascade="all, delete-orphan",
    )


class InvestigationRelationshipEvidence(Base):
    __tablename__ = "investigation_relationship_evidence"

    relationship_id = Column(
        String(36),
        ForeignKey("investigation_relationships.id", ondelete="CASCADE"),
        primary_key=True,
    )
    evidence_id = Column(
        Integer,
        ForeignKey("investigation_evidence.id", ondelete="CASCADE"),
        primary_key=True,
    )

    relationship_record = relationship(
        "InvestigationRelationship",
        back_populates="evidence_links",
    )
    evidence = relationship("InvestigationEvidence")
