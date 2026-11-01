import os
import ipaddress
import json
import re
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

# Load root or local .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")


def _database_url() -> str:
    configured_url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR.parent / 'careershield.db'}",
    )
    parsed_url = make_url(configured_url)
    if parsed_url.get_backend_name() != "sqlite" or not parsed_url.database:
        return configured_url
    if parsed_url.database == ":memory:":
        return configured_url

    database_path = Path(parsed_url.database)
    if not database_path.is_absolute():
        database_path = BASE_DIR.parent / database_path
    return parsed_url.set(database=str(database_path.resolve())).render_as_string(
        hide_password=False
    )


class Settings(BaseModel):
    PROJECT_NAME: str = "CareerShield"
    API_V1_PREFIX: str = "/api"
    
    # Database
    DATABASE_URL: str = _database_url()

    # Authentication and browser security
    AUTH_SESSION_COOKIE: str = "careershield_session"
    AUTH_CSRF_COOKIE: str = "careershield_csrf"
    MAX_UPLOAD_SIZE_BYTES: int = int(
        os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024))
    )
    TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "").strip()
    AUTH_SESSION_TTL_HOURS: int = int(os.getenv("AUTH_SESSION_TTL_HOURS", "12"))
    AUTH_COOKIE_SECURE: bool = os.getenv(
        "AUTH_COOKIE_SECURE",
        "true" if os.getenv("ENVIRONMENT", "development").lower() in {"prod", "production"} else "false",
    ).lower() == "true"
    AUTH_COOKIE_SAMESITE: str = os.getenv("AUTH_COOKIE_SAMESITE", "lax").lower()
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = int(
        os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "900")
    )
    AUTH_LOGIN_IP_LIMIT: int = int(os.getenv("AUTH_LOGIN_IP_LIMIT", "30"))
    AUTH_LOGIN_ACCOUNT_IP_LIMIT: int = int(
        os.getenv("AUTH_LOGIN_ACCOUNT_IP_LIMIT", "5")
    )
    AUTH_REGISTRATION_WINDOW_SECONDS: int = int(
        os.getenv("AUTH_REGISTRATION_WINDOW_SECONDS", "3600")
    )
    AUTH_REGISTRATION_IP_LIMIT: int = int(os.getenv("AUTH_REGISTRATION_IP_LIMIT", "5"))
    COMPANY_INVESTIGATION_LIMIT: int = int(
        os.getenv("COMPANY_INVESTIGATION_LIMIT", "5")
    )
    COMPANY_INVESTIGATION_WINDOW_SECONDS: int = int(
        os.getenv("COMPANY_INVESTIGATION_WINDOW_SECONDS", "3600")
    )
    WORKLIFE_MIN_OVERALL_REVIEWS: int = int(os.getenv("WORKLIFE_MIN_OVERALL_REVIEWS", "5"))
    WORKLIFE_MIN_CATEGORY_REVIEWS: int = int(os.getenv("WORKLIFE_MIN_CATEGORY_REVIEWS", "2"))
    WORKLIFE_REVIEW_LIMIT: int = int(os.getenv("WORKLIFE_REVIEW_LIMIT", "5"))
    WORKLIFE_REVIEW_WINDOW_SECONDS: int = int(
        os.getenv("WORKLIFE_REVIEW_WINDOW_SECONDS", "3600")
    )
    WORKLIFE_MODERATOR_EMAILS: list[str] = [
        email.strip().lower()
        for email in os.getenv("WORKLIFE_MODERATOR_EMAILS", "").split(",")
        if email.strip()
    ]
    WORKLIFE_SCORE_WEIGHTS: dict[str, float] = json.loads(
        os.getenv(
            "WORKLIFE_SCORE_WEIGHTS",
            (
                '{"work_life_balance":0.125,"salary_satisfaction":0.125,'
                '"management":0.125,"career_growth":0.125,'
                '"learning_opportunities":0.125,"work_pressure":0.125,'
                '"job_security":0.125,"overall_satisfaction":0.125}'
            ),
        )
    )
    TRUSTED_PROXY_IPS: list[str] = [
        address.strip()
        for address in os.getenv("TRUSTED_PROXY_IPS", "").split(",")
        if address.strip()
    ]
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
    EXTENSION_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("EXTENSION_ORIGINS", "").split(",")
        if origin.strip()
    ]
    GMAIL_OAUTH_CLIENT_ID: str = os.getenv("GMAIL_OAUTH_CLIENT_ID", "").strip()
    GMAIL_OAUTH_CLIENT_SECRET: str = os.getenv("GMAIL_OAUTH_CLIENT_SECRET", "").strip()
    GMAIL_OAUTH_REDIRECT_URI: str = os.getenv("GMAIL_OAUTH_REDIRECT_URI", "").strip()
    GMAIL_OAUTH_RETURN_URL: str = os.getenv("GMAIL_OAUTH_RETURN_URL", "").strip()
    GMAIL_TOKEN_ENCRYPTION_KEYS: str = os.getenv(
        "GMAIL_TOKEN_ENCRYPTION_KEYS", ""
    ).strip()
    GMAIL_TOKEN_ACTIVE_KEY_VERSION: str = os.getenv(
        "GMAIL_TOKEN_ACTIVE_KEY_VERSION", ""
    ).strip()
    
    # Hugging Face
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    HF_MODEL: str = os.getenv("HF_MODEL", "distilbert/distilbert-base-uncased-finetuned-sst-2-english")
    
    # Paths
    BASE_DIR: Path = BASE_DIR
    RAW_DATA_DIR: Path = BASE_DIR / "data" / "raw"
    PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"
    MODELS_DIR: Path = BASE_DIR / "models"
    ARTIFACTS_DIR: Path = BASE_DIR / "artifacts"
    SAMPLE_DATA_DIR: Path = BASE_DIR / "sample_data"
    
    # ML Artifacts
    JOB_MODEL_PATH: Path = BASE_DIR / "models" / "fraud_model.joblib"
    SVM_MODEL_PATH: Path = BASE_DIR / "models" / "linear_svm_model.joblib"
    VECTORIZER_PATH: Path = BASE_DIR / "models" / "tfidf_vectorizer.joblib"
    METRICS_PATH: Path = BASE_DIR / "artifacts" / "job_metrics.json"
    DATASET_REPORT_PATH: Path = BASE_DIR / "artifacts" / "dataset_report.json"
    
    # Processed Data Files
    PROCESSED_JOBS_FILE: Path = BASE_DIR / "data" / "processed" / "job_fraud" / "processed_jobs.csv"
    PROCESSED_REVIEWS_FILE: Path = BASE_DIR / "data" / "processed" / "reviews" / "processed_reviews.csv"
    
    # Scoring Thresholds
    TRUST_THRESHOLD_LEGITIMATE: float = 75.0
    TRUST_THRESHOLD_UNCERTAIN: float = 50.0

settings = Settings()

if settings.MAX_UPLOAD_SIZE_BYTES < 1:
    raise ValueError("MAX_UPLOAD_SIZE_BYTES must be a positive integer.")
if settings.AUTH_SESSION_TTL_HOURS < 1:
    raise ValueError("AUTH_SESSION_TTL_HOURS must be at least 1.")
if settings.AUTH_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise ValueError("AUTH_COOKIE_SAMESITE must be lax, strict, or none.")
if settings.AUTH_COOKIE_SAMESITE == "none" and not settings.AUTH_COOKIE_SECURE:
    raise ValueError("AUTH_COOKIE_SECURE must be true when AUTH_COOKIE_SAMESITE is none.")
if "*" in settings.CORS_ORIGINS:
    raise ValueError("CORS_ORIGINS cannot contain a wildcard when credentials are enabled.")
if "*" in settings.EXTENSION_ORIGINS:
    raise ValueError("EXTENSION_ORIGINS cannot contain a wildcard.")
if any(
    not re.fullmatch(r"chrome-extension://[a-p]{32}", origin)
    for origin in settings.EXTENSION_ORIGINS
):
    raise ValueError("EXTENSION_ORIGINS must contain exact Chrome extension origins.")
if min(
    settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    settings.AUTH_LOGIN_IP_LIMIT,
    settings.AUTH_LOGIN_ACCOUNT_IP_LIMIT,
    settings.AUTH_REGISTRATION_WINDOW_SECONDS,
    settings.AUTH_REGISTRATION_IP_LIMIT,
    settings.COMPANY_INVESTIGATION_LIMIT,
    settings.COMPANY_INVESTIGATION_WINDOW_SECONDS,
    settings.WORKLIFE_MIN_OVERALL_REVIEWS,
    settings.WORKLIFE_MIN_CATEGORY_REVIEWS,
    settings.WORKLIFE_REVIEW_LIMIT,
    settings.WORKLIFE_REVIEW_WINDOW_SECONDS,
) < 1:
    raise ValueError("Authentication rate-limit values must be positive integers.")
if set(settings.WORKLIFE_SCORE_WEIGHTS) != {
    "work_life_balance",
    "salary_satisfaction",
    "management",
    "career_growth",
    "learning_opportunities",
    "work_pressure",
    "job_security",
    "overall_satisfaction",
} or any(
    not isinstance(weight, (int, float)) or weight <= 0
    for weight in settings.WORKLIFE_SCORE_WEIGHTS.values()
):
    raise ValueError("WORKLIFE_SCORE_WEIGHTS must define positive weights for all eight categories.")
for trusted_proxy in settings.TRUSTED_PROXY_IPS:
    ipaddress.ip_network(trusted_proxy, strict=False)

# Ensure directories exist
for p in [
    settings.RAW_DATA_DIR / "job_fraud",
    settings.RAW_DATA_DIR / "reviews",
    settings.PROCESSED_DATA_DIR / "job_fraud",
    settings.PROCESSED_DATA_DIR / "reviews",
    settings.MODELS_DIR,
    settings.ARTIFACTS_DIR,
    settings.SAMPLE_DATA_DIR
]:
    p.mkdir(parents=True, exist_ok=True)
