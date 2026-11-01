from typing import Dict, Any
from utils.text_utils import extract_salary_numbers

class SalaryAgent:
    """
    Evaluates compensation realism relative to role complexity,
    experience level, and labor market benchmarks.
    High salary alone is never proof of fraud.
    """

    LOW_SKILL_KEYWORDS = [
        "data entry", "virtual assistant", "copy paste", "typist",
        "envelope", "clerk", "package inspector", "receptionist", "customer service"
    ]

    HIGH_SKILL_KEYWORDS = [
        "engineer", "architect", "lead", "director", "manager", "physician",
        "scientist", "attorney", "consultant", "developer", "cybersecurity"
    ]

    def analyze(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        salary_str = job_data.get("salary", "") or job_data.get("salary_range", "")
        job_title = (job_data.get("job_title", "") or "").lower()
        desc = (job_data.get("job_description", "") or "").lower()

        if not salary_str:
            return {
                "category": "salary",
                "status": "unknown",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 0.7,
                "quality": 0.5,
                "confidence": 0.5,
                "explanation": "No compensation figures provided to evaluate salary realism.",
                "signals": ["Salary omitted from posting"]
            }

        numbers = extract_salary_numbers(salary_str)
        if not numbers:
            return {
                "category": "salary",
                "status": "unknown",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 0.6,
                "quality": 0.5,
                "confidence": 0.5,
                "explanation": f"Salary text '{salary_str}' could not be parsed into standardized metrics.",
                "signals": ["Non-standard compensation format"]
            }

        max_val = max(numbers)
        s_lower = salary_str.lower()
        
        # Estimate annualized value
        annual_val = max_val
        is_hourly = "hr" in s_lower or "hour" in s_lower or "/h" in s_lower
        is_monthly = "month" in s_lower or "mo" in s_lower or "/m" in s_lower
        is_weekly = "week" in s_lower or "/w" in s_lower
        is_daily = "day" in s_lower or "daily" in s_lower

        if is_hourly and max_val < 500:
            annual_val = max_val * 2080
        elif is_daily and max_val < 3000:
            annual_val = max_val * 260
        elif is_weekly and max_val < 15000:
            annual_val = max_val * 52
        elif is_monthly and max_val < 50000:
            annual_val = max_val * 12

        is_low_skill_entry = any(k in job_title for k in self.LOW_SKILL_KEYWORDS) or "no experience" in desc
        is_high_skill = any(k in job_title for k in self.HIGH_SKILL_KEYWORDS)

        # Severe Anomaly: Low-skill / entry-level / no-experience job offering >= $80k/yr or >= $45/hr
        if is_low_skill_entry and (annual_val >= 80000 or (is_hourly and max_val >= 45)):
            return {
                "category": "salary",
                "status": "suspicious",
                "evidence_state": "negative",
                "score": -0.70,
                "weight": 1.0,
                "quality": 0.85,
                "confidence": 0.85,
                "explanation": f"Compensation '{salary_str}' (~${int(annual_val):,}/yr) is severely detached from standard market rates for '{job_title}'. High phishing risk.",
                "signals": ["Disproportionately high pay for low-complexity role", "Common hook in employment phishing"]
            }

        # Plausible High Salary for High-Skill Role
        if is_high_skill and annual_val > 80000:
            return {
                "category": "salary",
                "status": "verified",
                "evidence_state": "positive",
                "score": 0.60,
                "weight": 0.8,
                "quality": 0.80,
                "confidence": 0.80,
                "explanation": f"Compensation '{salary_str}' is consistent with enterprise market rates for specialized '{job_title}'.",
                "signals": ["Market-aligned compensation for senior/technical role"]
            }

        # Moderate Realistic Salary
        return {
            "category": "salary",
            "status": "verified",
            "evidence_state": "positive",
            "score": 0.40,
            "weight": 0.7,
            "quality": 0.75,
            "confidence": 0.75,
            "explanation": f"Compensation '{salary_str}' falls within realistic expected ranges.",
            "signals": ["Reasonable market compensation range"]
        }
