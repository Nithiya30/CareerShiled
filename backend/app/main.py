import sys
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
import logging
import threading

# Allow the application to run both from the backend folder and from the repository root.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect
from app.config import settings
from app.db import engine, Base
from app.models import Analysis, EvidenceItem, Feedback, CompanyReview, CompanyClaim, ReputationSummary
from api.routes import router
from api.auth_routes import router as auth_router
from api.document_routes import router as document_router
from api.gmail_oauth_routes import router as gmail_oauth_router
from services.gmail_monitoring_service import run_monitoring_scheduler

# Retain bootstrap behavior for existing application tables; auth schema is migrated explicitly.
Base.metadata.create_all(
    bind=engine,
    tables=[
        Analysis.__table__,
        EvidenceItem.__table__,
        Feedback.__table__,
        CompanyReview.__table__,
        CompanyClaim.__table__,
        ReputationSummary.__table__,
    ],
)


def verify_auth_schema() -> None:
    tables = set(inspect(engine).get_table_names())
    missing = {"users", "auth_sessions"} - tables
    if missing:
        raise RuntimeError(
            "Authentication database schema is missing. Back up the database, "
            "then run `python -m alembic upgrade head`."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_auth_schema()
    stop_event = threading.Event()
    scheduler_task = asyncio.create_task(run_monitoring_scheduler(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await scheduler_task


app = FastAPI(
    title="CareerShield API",
    description="Explainable Multi-Evidence AI Framework for Recruitment Fraud Detection and Company Reputation Assessment",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def redact_auth_validation_input(
    request: Request,
    exc: RequestValidationError,
):
    if request.url.path.startswith(f"{settings.API_V1_PREFIX}/auth/"):
        errors = [
            {key: value for key, value in error.items() if key != "input"}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})
    return await request_validation_exception_handler(request, exc)


# Mount API routes
app.include_router(router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(document_router, prefix=settings.API_V1_PREFIX)
app.include_router(gmail_oauth_router, prefix=settings.API_V1_PREFIX)


class RedactGmailOAuthCallbackQuery(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access" and isinstance(record.args, tuple):
            args = list(record.args)
            if (
                len(args) >= 3
                and isinstance(args[2], str)
                and args[2].split("?", 1)[0].endswith("/api/gmail/oauth/callback")
                and "?" in args[2]
            ):
                args[2] = f"{args[2].split('?', 1)[0]}?[REDACTED]"
                record.args = tuple(args)
        return True


logging.getLogger("uvicorn.access").addFilter(RedactGmailOAuthCallbackQuery())


@app.middleware("http")
async def enforce_allowed_origins(request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and origin
        and origin not in allowed_origins
    ):
        return JSONResponse(status_code=403, content={"detail": "Request origin is not allowed."})
    return await call_next(request)


def configure_cors(
    target_app: FastAPI,
    web_origins: list[str],
    extension_origins: list[str],
) -> list[str]:
    origins = list(
        dict.fromkeys(
            origin.strip()
            for origin in [*web_origins, *extension_origins]
            if origin.strip()
        )
    )
    if "*" in origins:
        raise ValueError("CORS origins cannot contain a wildcard when credentials are enabled.")
    target_app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return origins


# Register CORS after the application middleware so it wraps origin enforcement
# and handles preflight requests before they reach authentication or routes.
allowed_origins = configure_cors(app, settings.CORS_ORIGINS, settings.EXTENSION_ORIGINS)


@app.get("/")
def root():
    return {
        "message": "Welcome to CareerShield API",
        "documentation": "/docs",
        "version": "1.0.0",
        "dual_axis_separation": "Recruitment Risk != Company Reputation"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
