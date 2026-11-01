import pytest
from utils.text_utils import clean_text, combine_job_text, extract_salary_numbers
from utils.company_utils import normalize_company_name, extract_domain, is_free_mail_provider

def test_clean_text():
    raw_html = "<p>Join our <b>Engineering</b> team at https://example.com! Email us: jobs@example.com</p>"
    cleaned = clean_text(raw_html)
    assert "<p>" not in cleaned
    assert "<b>" not in cleaned
    assert "engineering" in cleaned
    assert "url" in cleaned
    assert "email" in cleaned

def test_combine_job_text():
    sample = {
        "title": "Software Engineer",
        "job_description": "Building cloud native microservices.",
        "requirements": "Proficiency in Python and Docker.",
        "benefits": "Health insurance and 401(k)."
    }
    combined = combine_job_text(sample)
    assert "title: Software Engineer" in combined
    assert "description: Building cloud native microservices." in combined
    assert "requirements: Proficiency in Python and Docker." in combined
    assert "benefits: Health insurance and 401(k)." in combined

def test_extract_salary_numbers():
    assert extract_salary_numbers("$120,000 / year") == [120000.0]
    assert extract_salary_numbers("$45 - $65 per hour") == [45.0, 65.0]
    assert extract_salary_numbers("85k - 95k") == [85000.0, 95000.0]
    assert extract_salary_numbers("Competitive salary") == []

def test_normalize_company_name():
    assert normalize_company_name("Google LLC") == "google"
    assert normalize_company_name("Microsoft Corporation") == "microsoft"
    assert normalize_company_name("Acme Technologies Inc.") == "acme technologies"
    assert normalize_company_name("Sunrise Artisanal Breads, Ltd.") == "sunrise artisanal breads"

def test_extract_domain():
    assert extract_domain("https://www.google.com/careers") == "google.com"
    assert extract_domain("http://subdomain.example.org:8080/path") == "subdomain.example.org"
    assert extract_domain("recruiter@cyberdefense.com") == "cyberdefense.com"

def test_is_free_mail_provider():
    assert is_free_mail_provider("gmail.com") is True
    assert is_free_mail_provider("yahoo.com") is True
    assert is_free_mail_provider("protonmail.com") is True
    assert is_free_mail_provider("microsoft.com") is False
    assert is_free_mail_provider("acme-tech.org") is False
