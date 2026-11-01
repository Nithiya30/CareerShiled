from typing import List, Dict, Any, Optional
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
class AuthRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)
class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class AuthUserResponse(BaseModel):
    id: str
    name: str
    email: str


class ExtensionPairingResponse(BaseModel):
    code: str
    expires_in: int


class ExtensionPairingExchangeRequest(BaseModel):
    code: str = Field(min_length=20, max_length=100)


class ExtensionTokenResponse(BaseModel):
    access_token: str
    csrf_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserResponse


class GmailOAuthStartResponse(BaseModel):
    authorization_url: str
    expires_in: int


class GmailAccountStatusResponse(BaseModel):
    connected: bool
    gmail_address: Optional[str] = None
    status: Literal["connected", "reauth_required", "disconnected"] = "disconnected"
    connected_at: Optional[datetime] = None
    monitoring_enabled: bool = False


class GmailDisconnectResponse(BaseModel):
    disconnected: bool
    remote_revocation: Literal["confirmed", "unconfirmed", "not_applicable"]


class GmailMonitoringConsentRequest(BaseModel):
    consent: bool = Field(..., strict=True)


class GmailMonitoringStatusResponse(BaseModel):
    enabled: bool = False
    consented_at: Optional[datetime] = None
    last_successful_sync_at: Optional[datetime] = None
    scanned_count: int = 0
    recruitment_count: int = 0
    suspicious_count: int = 0
    last_error_code: Optional[str] = None


class JobAnalysisRequest(BaseModel):
    job_title: str = Field(..., description="Job role or vacancy title")
    analysis_mode: Literal["job", "private_email"] = Field(
        default="job",
        description="Use private_email to skip external inference and verification.",
    )
    company_name: Optional[str] = Field(default="", description="Name of hiring company")
    recruiter_email: Optional[str] = Field(default="", description="Contact email of the recruiter")
    company_website: Optional[str] = Field(default="", description="Official corporate website URL")
    location: Optional[str] = Field(default="", description="Job location or remote status")
    employment_type: Optional[str] = Field(default="Full-time", description="Full-time, Part-time, Contract, etc.")
    salary: Optional[str] = Field(default="", description="Offered salary or wage range")
    job_description: str = Field(..., description="Job responsibilities and description text")
    requirements: Optional[str] = Field(default="", description="Candidate requirements and qualifications")
    benefits: Optional[str] = Field(default="", description="Compensation benefits and perks")
    document_source: bool = Field(
        default=False,
        description="Keep extracted document text local by skipping external semantic inference.",
    )


class DocumentExtractionResponse(BaseModel):
    filename: str
    content_type: str
    file_size_bytes: int
    text: str
    extraction_method: str
    pages_processed: int = 0
    ocr_pages: List[int] = []


class EvidenceItemSchema(BaseModel):
    category: str
    signal: str
    description: str
    evidence_state: str  # positive, negative, unknown
    score: float
    weight: float
    quality: float
class EvidenceContribution(BaseModel):
    category: str
    contribution: float
    state: str
# Analysis Response
class JobAnalysisResponse(BaseModel):
    id: Optional[int] = None
    job_title: str
    company_name: Optional[str] = None
    trust_score: float
    risk_level: str
    fraud_probability: float
    confidence: float
    positive_evidence: List[str] = []
    negative_evidence: List[str] = []
    unknown_evidence: List[str] = []
    evidence_contributions: List[EvidenceContribution] = []
    evidence_details: Dict[str, Any] = {}
    advanced_ai_analysis: Dict[str, Any] = {}
    live_verification: Dict[str, Any] = {}

    # Structured summary fields required by the upgraded architecture while preserving
    # the legacy flattened response contract.
    job_assessment: Dict[str, Any] = {}
    company_reputation: Dict[str, Any] = {}
    
    # Modular agent breakdown
    ml_result: Dict[str, Any] = {}
    transformer_result: Dict[str, Any] = {}
    recruiter_result: Dict[str, Any] = {}
    company_result: Dict[str, Any] = {}
    website_result: Dict[str, Any] = {}
    domain_result: Dict[str, Any] = {}
    salary_result: Dict[str, Any] = {}
    external_verification: Dict[str, Any] = {}
    
    created_at: Optional[datetime] = None


ExternalVerificationCategory = Literal[
    "company_reputation",
    "website_domain",
    "recruiter",
    "salary",
]


class ExternalVerificationConsentRequest(BaseModel):
    consent: bool = Field(..., strict=True)
    selected_checks: List[ExternalVerificationCategory] = Field(
        default_factory=list, max_length=4
    )

    @model_validator(mode="after")
    def validate_consent_selection(self):
        if len(set(self.selected_checks)) != len(self.selected_checks):
            raise ValueError("Verification checks must be unique.")
        if self.consent and not self.selected_checks:
            raise ValueError("Select at least one check or decline external verification.")
        if not self.consent and self.selected_checks:
            raise ValueError("Declined consent cannot include selected checks.")
        return self

class AnalysisHistoryItem(BaseModel):
    id: int
    job_title: str
    company_name: Optional[str]
    recruiter_email: Optional[str] = None
    company_website: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    salary: Optional[str] = None
    job_description: str = ""
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    trust_score: float
    risk_level: str
    fraud_probability: float
    confidence: float
    created_at: datetime

class HistoryResponse(BaseModel):
    total: int
    analyses: List[AnalysisHistoryItem]

# Company Intelligence & Claims
class CompanyReputationRequest(BaseModel):
    company_name: str
    domain: Optional[str] = None

class AspectDetail(BaseModel):
    status: str  # positive, mixed, negative, insufficient_evidence
    score: float
    evidence: str
    mention_count: int

class CompanyReputationResponse(BaseModel):
    company_name: str
    total_reviews: int
    average_rating: float
    sentiment_distribution: Dict[str, int]
    aspects: Dict[str, AspectDetail]
    confidence: float
    website: Optional[str] = None
    domain_status: Optional[str] = None
    career_page: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    dataset_available: bool = True
    is_verified_entity: bool = False
    official_domain: Optional[str] = None
    reputation_score: int = 50
    sentiment_polarity: float = 0.0
    detected_risk_keywords: List[str] = []
    impersonation_detected: bool = False
    search_snippets_sample: List[str] = []
    live_verification: Dict[str, Any] = {}

    # Upgraded reputation summary fields.
    identity_confidence: float = 0.0
    workplace_reputation: str = "Insufficient Evidence"
    public_reputation: str = "Insufficient Evidence"
    evidence_confidence: float = 0.0
    evidence: List[Dict[str, Any]] = []

class CompanyClaimRequest(BaseModel):
    company_name: str
    claim: str

class CompanyClaimResponse(BaseModel):
    company: str
    claim: str
    aspect: Optional[str] = None
    sentiment: Optional[str] = None
    evidence_status: str  # Supported, Partially Supported, Contradicted, Unverified, Insufficient Evidence
    confidence: float
    supporting_evidence: List[str] = []
    contradicting_evidence: List[str] = []
    total_relevant_reviews: int = 0
    explanation: Optional[str] = None


class ReviewAnalysisRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255, description="Name of company being reviewed")
    review_text: str = Field(min_length=1, description="Content of the employee review")
    source_type: Optional[str] = Field(default=None, max_length=100)
    source_name: Optional[str] = Field(default=None, max_length=150)
    source_url: Optional[str] = Field(default=None, max_length=2048)
    role: Optional[str] = Field(default=None, max_length=150)
    location: Optional[str] = Field(default=None, max_length=150)
    review_date: Optional[str] = Field(default=None, max_length=50)

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Company name is required.")
        return cleaned

    @field_validator("review_text")
    @classmethod
    def validate_review_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Review text is required.")
        return cleaned


ReviewCredibilityRequest = ReviewAnalysisRequest


class WorkLifeReviewSubmission(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    job_role: str = Field(min_length=1, max_length=150)
    department: Optional[str] = Field(default=None, max_length=150)
    employment_status: Literal["current", "former"]
    work_life_balance: int = Field(ge=1, le=5)
    salary_satisfaction: int = Field(ge=1, le=5)
    management_rating: int = Field(ge=1, le=5)
    career_growth: int = Field(ge=1, le=5)
    learning_opportunities: int = Field(ge=1, le=5)
    work_pressure: int = Field(
        ge=1,
        le=5,
        description="Higher values mean a more manageable workload and lower pressure.",
    )
    job_security: int = Field(ge=1, le=5)
    overall_rating: int = Field(ge=1, le=5)
    review_text: str = Field(min_length=20, max_length=4000)

    @field_validator("company_name", "job_role", "department", "review_text")
    @classmethod
    def trim_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field must not be blank.")
        return cleaned

    @model_validator(mode="after")
    def require_review_details(self):
        if len(self.review_text) < 20:
            raise ValueError("Please provide at least 20 characters of workplace feedback.")
        return self


class WorkLifeReviewUpdate(WorkLifeReviewSubmission):
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class WorkLifeReviewReportRequest(BaseModel):
    reason: Literal[
        "spam",
        "personal_information",
        "abusive_content",
        "misleading",
        "other",
    ]
    details: Optional[str] = Field(default=None, max_length=500)

    @field_validator("details")
    @classmethod
    def trim_report_details(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class WorkLifeModerationRequest(BaseModel):
    action: Literal["approve", "reject", "dismiss_report"]
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def trim_moderation_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None



class CompanyInvestigationRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    domain: Optional[str] = Field(default=None, max_length=255)
    recruiter_email: Optional[str] = Field(default=None, max_length=320)

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Company name is required.")
        return cleaned

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        from urllib.parse import urlsplit
        import ipaddress
        import re

        candidate = value.strip()
        parsed = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 80, 443)
        ):
            raise ValueError("Enter a valid public website or domain.")
        host = parsed.hostname.rstrip(".").lower()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None or host in {"localhost", "localhost.localdomain"}:
            raise ValueError("Enter a public DNS domain, not an IP address or local host.")
        if len(host) > 253 or not re.fullmatch(
            r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))+",
            host,
        ):
            raise ValueError("Enter a valid public website or domain.")
        return host

    @field_validator("recruiter_email")
    @classmethod
    def validate_recruiter_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        import re

        cleaned = value.strip()
        if len(cleaned) > 320 or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned
        ):
            raise ValueError("Enter a valid contact email address.")
        return cleaned


class InvestigationEvidenceResponse(BaseModel):
    id: int
    finding: str
    source_name: str
    source_url: Optional[str]
    retrieved_at: Optional[str]
    factual_summary: str
    status: str
    source_reliability: str
    relevance: str
    explanation: str
    limitations: str

    model_config = {"from_attributes": True}


class CompanyInvestigationResponse(BaseModel):
    id: str
    company_name: str
    domain: Optional[str]
    status: str
    created_at: datetime
    completed_at: datetime
    assessments: Dict[str, Any]
    evidence: List[InvestigationEvidenceResponse]
    information_types: Dict[str, Any]
    limitations: List[str]


class CompanyInvestigationListItem(BaseModel):
    id: str
    company_name: str
    domain: Optional[str]
    status: str
    created_at: datetime
    assessments: Dict[str, Any]


class InvestigationGraphEntity(BaseModel):
    id: str
    entity_type: str
    display_name: str
    attributes: Dict[str, Any]


class InvestigationGraphEvidence(BaseModel):
    id: int
    finding: str
    source_name: str
    source_url: Optional[str]
    retrieved_at: Optional[str]
    status: str
    factual_summary: str
    source_reliability: str
    relevance: str
    explanation: str
    limitations: str


class InvestigationGraphRelationship(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    status: str
    explanation: str
    limitations: str
    evidence: List[InvestigationGraphEvidence]


class InvestigationGraphResponse(BaseModel):
    investigation_id: str
    entities: List[InvestigationGraphEntity]
    relationships: List[InvestigationGraphRelationship]

# System & Health
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str

class ModelStatusResponse(BaseModel):
    job_model_status: str
    job_model_name: str
    svm_model_status: str
    vectorizer_status: str
    transformer_status: str
    transformer_model: str

class DatasetStatusResponse(BaseModel):
    emscad_available: bool
    emscad_rows: int
    emscad_features: int
    emscad_fraud_ratio: str
    additional_job_available: bool
    additional_job_rows: int
    reviews_available: bool
    reviews_rows: int
    reviews_companies_count: int
    reviews_status: str
