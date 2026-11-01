from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.main import app, configure_cors


FRONTEND_ORIGIN = "http://127.0.0.1:5173"


def test_frontend_preflight_allows_csrf_headers_and_credentials():
    with TestClient(app) as client:
        response = client.options(
            "/api/auth/me",
            headers={
                "Origin": FRONTEND_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "x-csrf-token" in response.headers["access-control-allow-headers"].lower()


def test_unconfigured_origin_is_rejected_by_preflight():
    with TestClient(app) as client:
        response = client.options(
            "/api/auth/me",
            headers={
                "Origin": "https://not-configured.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_exact_extension_origin_is_allowed_with_credentials():
    extension_origin = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
    test_app = FastAPI()
    configure_cors(test_app, [FRONTEND_ORIGIN], [extension_origin])
    test_app.get("/api/auth/me")(lambda: {"authenticated": True})

    with TestClient(test_app) as client:
        response = client.options(
            "/api/auth/me",
            headers={
                "Origin": extension_origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == extension_origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_configured_extension_origin_passes_real_application_preflight():
    extension_origin = "chrome-extension://ineohmdghfadcgjgedpfchpbfmoacpga"
    assert extension_origin in settings.EXTENSION_ORIGINS

    with TestClient(app) as client:
        response = client.options(
            "/api/auth/me",
            headers={
                "Origin": extension_origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == extension_origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_configuration_never_allows_wildcard_credentials():
    test_app = FastAPI()

    with pytest.raises(ValueError, match="wildcard"):
        configure_cors(test_app, ["*"], [])


def test_extension_origins_are_loaded_as_exact_origins():
    assert all(
        origin.startswith("chrome-extension://")
        and len(origin.removeprefix("chrome-extension://")) == 32
        for origin in settings.EXTENSION_ORIGINS
    )
