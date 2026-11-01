import re
from urllib.parse import urlparse

def normalize_company_name(name: str) -> str:
    """Normalize company name for robust fuzzy and exact matching."""
    if not name or not isinstance(name, str):
        return ""
    
    cleaned = name.lower().strip()
    
    # Remove common corporate suffixes
    suffixes = [
        r"\binc\.?\b",
        r"\bllc\.?\b",
        r"\bltd\.?\b",
        r"\bcorp\.?\b",
        r"\bcorporation\b",
        r"\bco\.?\b",
        r"\bcompany\b",
        r"\bgmbh\b",
        r"\bpvt\.?\b",
        r"\bprivate\b",
        r"\blimited\b",
        r"\bholdings\b",
        r"\bgroup\b"
    ]
    for s in suffixes:
        cleaned = re.sub(s, "", cleaned)
        
    # Remove non-alphanumeric
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def extract_domain(input_str: str) -> str:
    """Extract clean second-level and top-level domain from URL or email."""
    if not input_str or not isinstance(input_str, str):
        return ""
    
    input_str = input_str.strip().lower()
    
    # If it's an email
    if "@" in input_str:
        parts = input_str.split("@")
        if len(parts) > 1:
            input_str = parts[1].strip()
            
    # If it's a URL
    if not input_str.startswith("http://") and not input_str.startswith("https://"):
        input_str = "https://" + input_str
        
    try:
        parsed = urlparse(input_str)
        netloc = parsed.netloc or parsed.path
        # Strip port if any
        netloc = netloc.split(":")[0]
        # Strip www.
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc.strip()
    except Exception:
        return ""

def is_free_mail_provider(domain: str) -> bool:
    """Check if domain belongs to a public free consumer email service."""
    free_domains = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "aol.com",
        "icloud.com",
        "mail.com",
        "zoho.com",
        "proton.me",
        "protonmail.com",
        "yandex.com",
        "gmx.com",
        "fastmail.com"
    }
    return domain.lower().strip() in free_domains
