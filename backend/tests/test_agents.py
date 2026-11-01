import asyncio
import ipaddress
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import agents.website_agent as website_agent_module
from agents.scam_agent import ScamAgent
from agents.recruiter_agent import RecruiterAgent
from agents.company_agent import CompanyAgent
from agents.website_agent import WebsiteAgent
from agents.domain_agent import DomainAgent
from agents.salary_agent import SalaryAgent
from agents.domain_agent import analyze_domain
from agents.company_agent import analyze_company_reputation

def test_scam_agent_detects_payment():
    agent = ScamAgent()
    job = {
        "job_title": "Virtual Assistant",
        "job_description": "Candidate must pay a mandatory $200 equipment registration fee via wire transfer or zelle.",
    }
    result = agent.analyze(job)
    assert result["evidence_state"] == "negative"
    assert result["status"] == "suspicious"
    assert result["score"] < 0
    assert any("Upfront payment" in s for s in result["signals"])

def test_scam_agent_clean_posting():
    agent = ScamAgent()
    job = {
        "job_title": "Junior Python Developer",
        "job_description": "Collaborate with senior developers on building backend microservices and unit tests.",
    }
    result = agent.analyze(job)
    assert result["evidence_state"] == "positive"
    assert result["status"] == "verified"
    assert result["score"] > 0

def test_recruiter_agent_domain_match():
    agent = RecruiterAgent()
    job = {
        "company_name": "Acme Technologies",
        "company_website": "https://acme-tech.org",
        "recruiter_email": "careers@acme-tech.org"
    }
    result = agent.analyze(job)
    assert result["status"] == "verified"
    assert result["evidence_state"] == "positive"

def test_recruiter_agent_big_corp_impersonation():
    agent = RecruiterAgent()
    job = {
        "company_name": "Google",
        "recruiter_email": "google.recruiting.talent@gmail.com"
    }
    result = agent.analyze(job)
    assert result["status"] == "suspicious"
    assert result["evidence_state"] == "negative"

def test_recruiter_agent_missing():
    agent = RecruiterAgent()
    job = {"company_name": "Acme"}
    result = agent.analyze(job)
    assert result["status"] == "unknown"
    assert result["score"] == 0.0

def test_company_agent_unknown_rule():
    agent = CompanyAgent()
    job = {
        "company_name": "Sunrise Artisanal Breads",
        "job_description": "Family bakery hiring night shift baker."
    }
    result = agent.analyze(job)
    # Important Unknown Rule: Missing web info must NOT be marked fraudulent
    assert result["status"] == "unknown"
    assert result["evidence_state"] == "unknown"
    assert result["score"] == 0.0

def test_salary_agent_unrealistic_entry_level():
    agent = SalaryAgent()
    job = {
        "job_title": "Data Entry Clerk",
        "salary": "$8,500 monthly ($100,000 / year)",
        "job_description": "No experience needed for simple data typing."
    }
    result = agent.analyze(job)
    assert result["status"] == "suspicious"
    assert result["evidence_state"] == "negative"

def test_salary_agent_realistic_tech_role():
    agent = SalaryAgent()
    job = {
        "job_title": "Senior Solutions Architect",
        "salary": "$160,000 - $190,000",
        "job_description": "Enterprise cloud architecture design."
    }
    result = agent.analyze(job)
    assert result["status"] == "verified"
    assert result["evidence_state"] == "positive"

def test_website_agent_suspicious_tld(monkeypatch):
    agent = WebsiteAgent()
    monkeypatch.setattr(website_agent_module, "_probe_website", lambda url: 200)
    job = {"company_website": "http://scam-careers-urgent.xyz"}
    result = agent.analyze(job)
    assert result["status"] == "suspicious"
    assert result["evidence_state"] == "negative"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://localhost.localdomain",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.100.100.200",
        "http://192.0.2.1",
        "http://[::1]",
        "http://[fd00::1]",
        "http://[fe80::1]",
        "http://[::ffff:127.0.0.1]",
        "http://metadata.google.internal",
        "http://metadata",
        "http://user:pass@example.com",
        "http://127.0.0.1:8080",
        "file:///etc/passwd",
    ],
)
def test_website_probe_rejects_unsafe_urls(url):
    with pytest.raises(website_agent_module.WebsiteProbeError):
        website_agent_module._probe_website(url)


@pytest.mark.parametrize(
    "address",
    [
        "0.0.0.0",
        "10.1.2.3",
        "100.64.0.1",
        "127.0.0.1",
        "169.254.1.2",
        "192.168.1.1",
        "240.0.0.1",
        "::",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:192.168.1.1",
        "64:ff9b::a00:1",
        "2002:0a00:0001::",
    ],
)
def test_website_probe_rejects_private_or_reserved_dns_addresses(monkeypatch, address):
    monkeypatch.setattr(
        website_agent_module,
        "_resolve_host_addresses",
        lambda host: [address],
    )

    with pytest.raises(website_agent_module.WebsiteProbeError):
        website_agent_module._public_addresses("company.example.com")


def test_website_probe_rejects_public_and_private_mixed_dns_answers(monkeypatch):
    monkeypatch.setattr(
        website_agent_module,
        "_resolve_host_addresses",
        lambda host: ["93.184.216.34", "10.0.0.1"],
    )

    with pytest.raises(website_agent_module.WebsiteProbeError):
        website_agent_module._public_addresses("company.example.com")


@pytest.mark.parametrize(
    "redirect_url",
    ["http://127.0.0.1/admin", "http://[::1]/admin"],
)
def test_website_probe_rejects_private_redirect(monkeypatch, redirect_url):
    requests = []
    monkeypatch.setattr(
        website_agent_module,
        "_resolve_host_addresses",
        lambda host: ["93.184.216.34"],
    )
    monkeypatch.setattr(
        website_agent_module,
        "_send_head_request",
        lambda scheme, host, port, address, path, query: (
            requests.append((host, str(address))) or (302, redirect_url)
        ),
    )

    with pytest.raises(website_agent_module.WebsiteProbeError):
        website_agent_module._probe_website("https://company.example.com")

    assert requests == [("company.example.com", "93.184.216.34")]


def test_website_probe_rechecks_dns_on_redirect_and_blocks_rebinding(monkeypatch):
    resolutions = iter((["93.184.216.34"], ["10.0.0.1"]))
    requests = []
    monkeypatch.setattr(
        website_agent_module,
        "_resolve_host_addresses",
        lambda host: next(resolutions),
    )
    monkeypatch.setattr(
        website_agent_module,
        "_send_head_request",
        lambda scheme, host, port, address, path, query: (
            requests.append(str(address)) or (302, "/next")
        ),
    )

    with pytest.raises(website_agent_module.WebsiteProbeError):
        website_agent_module._probe_website("https://company.example.com")

    assert requests == ["93.184.216.34"]


def test_website_probe_follows_only_validated_public_redirects(monkeypatch):
    resolutions = []
    requests = []

    def resolve(host):
        resolutions.append(host)
        return ["93.184.216.34"] if host == "company.example.com" else ["2606:4700:4700::1111"]

    def send(scheme, host, port, address, path, query):
        requests.append((scheme, host, str(address), path))
        if host == "company.example.com":
            return 301, "https://careers.example.org/jobs"
        return 200, None

    monkeypatch.setattr(website_agent_module, "_resolve_host_addresses", resolve)
    monkeypatch.setattr(website_agent_module, "_send_head_request", send)

    status = website_agent_module._probe_website("https://company.example.com")

    assert status == 200
    assert resolutions == ["company.example.com", "careers.example.org"]
    assert requests == [
        ("https", "company.example.com", "93.184.216.34", "/"),
        ("https", "careers.example.org", "2606:4700:4700::1111", "/jobs"),
    ]


def test_website_probe_allows_legitimate_public_url(monkeypatch):
    requested = []
    monkeypatch.setattr(
        website_agent_module,
        "_resolve_host_addresses",
        lambda host: ["93.184.216.34"],
    )
    monkeypatch.setattr(
        website_agent_module,
        "_send_head_request",
        lambda scheme, host, port, address, path, query: (
            requested.append((host, str(address), port, path, query)) or (200, None)
        ),
    )

    result = WebsiteAgent().analyze(
        {"company_website": "https://www.example.com/careers?team=engineering"}
    )

    assert result["status"] == "verified"
    assert requested == [
        ("www.example.com", "93.184.216.34", 443, "/careers", "team=engineering")
    ]


def test_website_probe_preserves_legitimate_public_custom_port(monkeypatch):
    requested = []
    monkeypatch.setattr(
        website_agent_module,
        "_resolve_host_addresses",
        lambda host: ["93.184.216.34"],
    )
    monkeypatch.setattr(
        website_agent_module,
        "_send_head_request",
        lambda scheme, host, port, address, path, query: (
            requested.append((host, port, path)) or (200, None)
        ),
    )

    assert website_agent_module._probe_website(
        "https://careers.example.com:8443/jobs"
    ) == 200
    assert requested == [("careers.example.com", 8443, "/jobs")]


def test_website_probe_connects_to_pinned_numeric_ip(monkeypatch):
    class FakeSocket:
        def __init__(self):
            self.timeout = None
            self.destination = None

        def settimeout(self, timeout):
            self.timeout = timeout

        def connect(self, destination):
            self.destination = destination

    fake_socket = FakeSocket()
    monkeypatch.setattr(
        website_agent_module.socket,
        "socket",
        lambda family, kind: fake_socket,
    )

    connection = website_agent_module._connect_to_address(
        ipaddress.ip_address("93.184.216.34"),
        443,
    )

    assert connection is fake_socket
    assert fake_socket.timeout == website_agent_module.CONNECT_TIMEOUT_SECONDS
    assert fake_socket.destination == ("93.184.216.34", 443)


def test_website_probe_fails_when_dns_resolution_fails(monkeypatch):
    def fail_resolution(host):
        raise website_agent_module.dns.exception.Timeout()

    monkeypatch.setattr(website_agent_module, "_resolve_host_addresses", fail_resolution)

    with pytest.raises(website_agent_module.WebsiteProbeError):
        website_agent_module._public_addresses("company.example.com")


def test_website_probe_limits_response_header_size():
    class FakeSocket:
        def __init__(self):
            self.response = (
                b"HTTP/1.1 200 OK\r\nX-Long: "
                + b"a" * website_agent_module.MAX_RESPONSE_BYTES
            )

        def recv(self, size):
            chunk, self.response = self.response[:size], self.response[size:]
            return chunk

    with pytest.raises(website_agent_module.WebsiteProbeError):
        website_agent_module._read_head_response(FakeSocket())

def test_domain_whois_parses_creation_date_list(monkeypatch):
    created = datetime.now(timezone.utc) - timedelta(days=30)
    record = {
        "creation_date": [created, created + timedelta(seconds=1)],
        "expiration_date": datetime.now(timezone.utc) + timedelta(days=300),
        "registrar": "Example Registrar",
        "raw": {"domain_name": "example.com"},
    }
    monkeypatch.setitem(sys.modules, "whois", SimpleNamespace(whois=lambda domain: record))

    result = asyncio.run(analyze_domain("https://www.example.com"))

    assert result["domain"] == "example.com"
    assert result["verified"] is True
    assert result["domain_age_days"] < 90
    assert result["is_newly_registered"] is True
    assert result["registrar"] == "Example Registrar"
    assert result["risk_score"] >= 60

def test_domain_whois_failure_returns_degraded_result(monkeypatch):
    monkeypatch.setitem(sys.modules, "whois", SimpleNamespace(
        whois=lambda domain: (_ for _ in ()).throw(OSError("lookup failed"))
    ))
    monkeypatch.delenv("WHOISJSON_API_KEY", raising=False)

    result = asyncio.run(analyze_domain("example.com"))

    assert result["verified"] is False
    assert result["status"] == "unknown"
    assert result["domain"] == "example.com"
    assert "could not be verified" in result["explanation"]

def test_domain_whoisjson_fallback(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "created": (datetime.now(timezone.utc) - timedelta(days=400)).isoformat(),
                "registrar": "Fallback Registrar",
            }

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            pass

        async def get(self, url, params, headers):
            assert url == "https://whoisjson.com/api/v1/whois"
            assert params == {"domain": "example.com"}
            assert headers["X-API-Key"] == "test-key"
            return FakeResponse()

    monkeypatch.setitem(sys.modules, "whois", SimpleNamespace(
        whois=lambda domain: (_ for _ in ()).throw(OSError("lookup failed"))
    ))
    monkeypatch.setenv("WHOISJSON_API_KEY", "test-key")
    monkeypatch.setattr("agents.domain_agent.httpx.AsyncClient", FakeClient)

    result = asyncio.run(analyze_domain("example.com"))

    assert result["verified"] is True
    assert result["registrar"] == "Fallback Registrar"
    assert result["domain_age_days"] >= 399

def test_company_live_reputation_uses_mocked_serper(monkeypatch):
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            pass

        async def post(self, url, json, headers):
            assert url == "https://google.serper.dev/search"
            assert headers["X-API-KEY"] == "test-serper-key"
            if "reviews Trustpilot Glassdoor" in json["q"]:
                return FakeResponse({
                    "knowledgeGraph": {"website": "https://acme.com"},
                    "organic": [{
                        "title": "Acme Corp reviews",
                        "link": "https://trustpilot.com/review/acme.com",
                        "snippet": "Employees report helpful leadership.",
                    }],
                })
            return FakeResponse({
                "organic": [{
                    "title": "Acme Corp job warning",
                    "link": "https://example.net/warning",
                    "snippet": "Avoid telegram interviews and wire transfer requests.",
                }],
            })

    monkeypatch.setenv("SERPER_API_KEY", "test-serper-key")
    monkeypatch.setattr("agents.company_agent.httpx.AsyncClient", FakeClient)

    result = asyncio.run(analyze_company_reputation("Acme Corp", "acme-jobs.net"))

    assert result["official_domain"] == "acme.com"
    assert result["is_verified_entity"] is True
    assert result["impersonation_detected"] is True
    assert set(result["detected_risk_keywords"]) == {"telegram", "wire transfer"}
    assert result["search_snippets_sample"]
