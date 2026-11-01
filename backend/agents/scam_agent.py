import re
from typing import Dict, Any, List

class ScamAgent:
    """
    Evaluates recruitment text for high-risk fraud triggers, predatory fee clauses,
    unauthorized communication channels, and identity harvesting.
    """
    
    PATTERNS = {
        "payment_upfront": [
            r"\b(wire transfer|western union|moneygram|zelle|cashapp|venmo|crypto|bitcoin)\b",
            r"\b(send|pay|deposit)\s+(money|fee|cash|\$|funds|payment)\b",
            r"\b(application|registration|processing|interview)\s+fee\b",
            r"\b(equipment|laptop|check)\s+(deposit|fee|insurance)\b",
            r"\b(cashiers? check|buy your own equipment)\b"
        ],
        "sensitive_pii": [
            r"\b(social security|ssn|passport|driver\'?s? license|bank account|routing number)\b",
            r"\b(credit report fee|background check fee)\b",
            r"\b(send photo of id|front and back of card)\b"
        ],
        "suspicious_comms": [
            r"\b(telegram|whatsapp|signal|google hangouts|viber|wechat)\b",
            r"\b(contact via @\w+|chat on telegram)\b"
        ],
        "unrealistic_urgency": [
            r"\b(urgent hiring|immediate start|start today|no interview required|guaranteed job|guaranteed employment)\b",
            r"\b(no experience needed|make \$?\d+000\s+(daily|weekly)|earn money fast)\b"
        ]
    }

    def analyze(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        text_corpus = " ".join([
            str(job_data.get("job_title", "")),
            str(job_data.get("job_description", "")),
            str(job_data.get("requirements", "")),
            str(job_data.get("benefits", ""))
        ]).lower()

        detected_signals = []
        severity_score = 0.0

        # 1. Payment / Fee Requests (Highest Severity)
        payment_triggers = []
        for pat in self.PATTERNS["payment_upfront"]:
            matches = re.findall(pat, text_corpus)
            if matches:
                payment_triggers.append(pat)
        if payment_triggers:
            detected_signals.append("Upfront payment, registration fee, or equipment check request detected")
            severity_score += 0.55

        # 2. Sensitive PII Demands before Hire
        pii_triggers = []
        for pat in self.PATTERNS["sensitive_pii"]:
            if re.search(pat, text_corpus):
                pii_triggers.append(pat)
        if pii_triggers:
            detected_signals.append("Sensitive identity information (SSN, ID, bank details) requested prematurely")
            severity_score += 0.35

        # 3. Off-platform Anonymous Communication
        comms_triggers = []
        for pat in self.PATTERNS["suspicious_comms"]:
            if re.search(pat, text_corpus):
                comms_triggers.append(pat)
        if comms_triggers:
            detected_signals.append("Directs applicant to anonymous messaging platform (Telegram / WhatsApp / Signal)")
            severity_score += 0.25

        # 4. Excessive Urgency & Unrealistic Guarantees
        urgency_triggers = []
        for pat in self.PATTERNS["unrealistic_urgency"]:
            if re.search(pat, text_corpus):
                urgency_triggers.append(pat)
        if urgency_triggers:
            detected_signals.append("Extreme urgency or guaranteed employment without technical evaluation")
            severity_score += 0.20

        # Directional scoring: -1.0 is severe risk, +1.0 is clean
        if severity_score >= 0.5:
            state = "negative"
            score = -min(1.0, severity_score)
            status = "suspicious"
            explanation = f"Critical scam signals detected: {'; '.join(detected_signals[:2])}."
        elif severity_score > 0.15:
            state = "negative"
            score = -severity_score
            status = "suspicious"
            explanation = f"Potential recruitment risk flags: {'; '.join(detected_signals[:2])}."
        else:
            state = "positive"
            score = 0.75
            status = "verified"
            explanation = "No predatory fee requirements, suspicious messaging redirects, or credential harvesting patterns identified."

        return {
            "category": "scam",
            "status": status,
            "evidence_state": state,
            "score": round(score, 3),
            "weight": 1.4,  # High weight because direct payment/fee requests are primary fraud indicators
            "quality": 0.90,
            "explanation": explanation,
            "signals": detected_signals
        }
