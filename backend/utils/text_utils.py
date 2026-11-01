import re
from typing import Dict, Any, List

def clean_text(text: str) -> str:
    """Clean text by stripping HTML, excessive whitespace, and special characters."""
    if not text or not isinstance(text, str):
        return ""
    
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Replace URLs with token
    text = re.sub(r"https?://\S+|www\.\S+", " url ", text)
    # Replace email addresses with token
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", " email ", text)
    # Keep alphanumeric characters and basic punctuation
    text = re.sub(r"[^\w\s\$\%\-]", " ", text)
    # Normalize whitespaces
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text

def combine_job_text(fields: Dict[str, Any]) -> str:
    """
    Safely combine available job fields into a single text representation
    for NLP feature extraction.
    """
    parts = []
    
    # Priority ordered fields
    field_order = [
        "title",
        "job_title",
        "company_profile",
        "description",
        "job_description",
        "requirements",
        "benefits",
        "employment_type",
        "location",
        "salary_range",
        "salary",
        "department",
        "industry",
        "function",
        "required_experience",
        "required_education"
    ]
    
    for f in field_order:
        val = fields.get(f)
        if val and isinstance(val, str) and val.strip():
            # Label the field for NLP awareness
            parts.append(f"{f}: {val.strip()}")
            
    return " \n ".join(parts)

def extract_salary_numbers(salary_str: str) -> List[float]:
    """Extract numeric values from salary string."""
    if not salary_str:
        return []
    
    # Find all numeric patterns with optional commas or decimals
    # e.g., $120,000, 45.50, 75k, 9000
    cleaned = salary_str.lower().replace(",", "")
    
    # Expand 'k' notation: 75k -> 75000
    cleaned = re.sub(r"(\d+(?:\.\d+)?)\s*k\b", lambda m: str(float(m.group(1)) * 1000), cleaned)
    
    matches = re.findall(r"\b\d+(?:\.\d+)?\b", cleaned)
    numbers = []
    for m in matches:
        try:
            val = float(m)
            if val > 0:
                numbers.append(val)
        except ValueError:
            continue
    return numbers
