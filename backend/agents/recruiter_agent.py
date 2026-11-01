from typing import Dict, Any
from utils.company_utils import extract_domain, is_free_mail_provider, normalize_company_name

class RecruiterAgent:
    """
    Validates recruiter email identity, comparing recruiter's email domain
    against the claimed company's corporate domain.
    """

    KNOWN_ENTERPRISES = {
        "google": "google.com",
        "microsoft": "microsoft.com",
        "amazon": "amazon.com",
        "apple": "apple.com",
        "meta": "meta.com",
        "netflix": "netflix.com",
        "ibm": "ibm.com",
        "oracle": "oracle.com"
    }

    def analyze(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        email = job_data.get("recruiter_email", "").strip()
        website = job_data.get("company_website", "").strip()
        return self.analyze_domains(
            extract_domain(email),
            extract_domain(website) if website else "",
            job_data.get("company_name", "").strip(),
        )

    def analyze_domains(
        self, recruiter_domain: str, company_domain: str, company_name: str
    ) -> Dict[str, Any]:
        recruiter_domain = recruiter_domain.strip().lower()
        company_domain = company_domain.strip().lower()
        company_name = company_name.strip()
        if not recruiter_domain:
            return {
                "category": "recruiter",
                "status": "unknown",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 1.0,
                "quality": 0.5,
                "confidence": 0.5,
                "explanation": "No recruiter contact email provided to verify identity.",
                "signals": ["Recruiter email unprovided"]
            }

        norm_company = normalize_company_name(company_name)

        is_free_mail = is_free_mail_provider(recruiter_domain)

        # Check if claiming to be a prominent Fortune enterprise while using a free Gmail/Yahoo/Proton address
        is_impersonating_big_corp = False
        for corp_key in self.KNOWN_ENTERPRISES:
            if corp_key in norm_company and is_free_mail:
                is_impersonating_big_corp = True
                break

        if is_impersonating_big_corp:
            return {
                "category": "recruiter",
                "status": "suspicious",
                "evidence_state": "negative",
                "score": -0.85,
                "weight": 1.2,
                "quality": 0.9,
                "confidence": 0.9,
                "explanation": f"Recruiter uses free email domain '{recruiter_domain}' while claiming to represent top enterprise '{company_name}'. Severe impersonation risk.",
                "signals": ["Corporate impersonation signal", f"Free email service '{recruiter_domain}' for enterprise recruiter"]
            }

        # Domain match: recruiter email matches company website domain
        if company_domain and (recruiter_domain == company_domain or recruiter_domain.endswith("." + company_domain)):
            return {
                "category": "recruiter",
                "status": "verified",
                "evidence_state": "positive",
                "score": 0.85,
                "weight": 1.1,
                "quality": 0.95,
                "confidence": 0.95,
                "explanation": f"Recruiter email domain '{recruiter_domain}' matches official company domain '{company_domain}'.",
                "signals": ["Verified domain correlation", "Authentic enterprise mail host"]
            }

        # Free mail provider for generic/smaller company
        if is_free_mail:
            return {
                "category": "recruiter",
                "status": "uncertain",
                "evidence_state": "unknown",
                "score": -0.15,
                "weight": 0.8,
                "quality": 0.65,
                "confidence": 0.65,
                "explanation": f"Recruiter is using a public consumer email provider ({recruiter_domain}). Common for sole proprietorships, but caution advised.",
                "signals": ["Consumer email provider used for hiring communication"]
            }

        # Corporate email, but company website was omitted or slightly different
        if not company_domain:
            return {
                "category": "recruiter",
                "status": "partially_verified",
                "evidence_state": "positive",
                "score": 0.40,
                "weight": 0.9,
                "quality": 0.70,
                "confidence": 0.70,
                "explanation": f"Recruiter uses professional custom domain '{recruiter_domain}', though official company website was omitted for confirmation.",
                "signals": ["Custom business domain detected"]
            }

        # Explicit domain mismatch
        return {
            "category": "recruiter",
            "status": "suspicious",
            "evidence_state": "negative",
            "score": -0.55,
            "weight": 1.1,
            "quality": 0.85,
            "confidence": 0.85,
            "explanation": f"Recruiter domain '{recruiter_domain}' does not align with company website domain '{company_domain}'. Potential third-party or spoofed identity.",
            "signals": ["Domain mismatch between recruiter email and stated corporate website"]
        }
