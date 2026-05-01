"""
SupportBrain — classifier.py
Company detection, risk classification, request type, and product area.
"""

import re

# ---------------------------------------------------------------------------
# Company vocabulary
# ---------------------------------------------------------------------------
COMPANY_KEYWORDS = {
    "HackerRank": [
        "hackerrank", "assessment", "code challenge", "test window",
        "recruiter", "coding test", "proctored test", "skill test",
        "score", "leaderboard", "badge", "certification", "code editor",
        "screen share", "webcam", "candidate",
    ],
    "Claude": [
        "claude", "anthropic", "claude pro", "claude ai", "conversation",
        "chat history", "api key", "anthropic api", "gemini", "llm",
        "ai assistant", "context window", "memory",
    ],
    "Visa": [
        "visa", "card", "transaction", "payment", "billing",
        "debit", "credit card", "atm", "merchant", "refund",
        "chargeback", "foreign transaction", "travel insurance",
        "stolen card", "fraud", "pin", "cvv", "chip",
    ],
}

# ---------------------------------------------------------------------------
# High-risk keyword list (FR-04)
# ---------------------------------------------------------------------------
HIGH_RISK_KEYWORDS = [
    # billing / payments
    "order id", "cs_live", "refund", "charge", "transaction",
    "payment", "billing", "money back", "invoice",
    # account / access (non-authorized)
    "not the owner", "not the admin", "restore my access",
    "remove employee", "seat", "workspace owner",
    # fraud / security
    "identity theft", "stolen", "fraud", "unauthorized",
    "security vulnerability", "breach", "hack",
    # legal / compliance
    "infosec", "security form", "compliance", "gdpr",
    "fill in the forms", "legal", "erasure",
    # prompt injection (English + French)
    "ignore previous", "reveal internal", "show all rules",
    "display your prompt", "system prompt", "logique exacte",
    "documents récupérés", "affiche toutes", "règles internes",
    # harmful / malicious
    "delete all files", "rm -rf", "urgent cash",
    "code to delete", "exploit", "supprimer",
    # other
    "stolen card", "suspended", "duplicate charge",
    "unrecognized", "unauthorized transaction",
]

# Regex patterns for prompt injection
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"reveal\s+(your\s+)?(internal|system|prompt|rules)",
    r"show\s+(me\s+)?(all\s+)?(rules|instructions|prompt)",
    r"display\s+(your\s+)?(prompt|logic|rules)",
    r"(system|internal)\s+prompt",
    r"logique\s+exacte",
    r"documents\s+récupérés",
    r"affiche\s+toutes",
    r"règles\s+internes",
    r"rm\s+-rf",
    r"delete\s+all\s+files",
    r"supprimer\s+tous",
    r"exécuter",
]

# ---------------------------------------------------------------------------
# Product area keyword mapping
# ---------------------------------------------------------------------------
AREA_KEYWORDS = {
    "screen": ["screen", "webcam", "proctored", "browser", "editor", "display"],
    "privacy": ["privacy", "gdpr", "data", "erasure", "delete data", "personal data"],
    "billing": ["billing", "charge", "invoice", "subscription", "payment", "refund", "charged"],
    "general_support": ["help", "question", "how to", "support", "contact"],
    "travel_support": ["travel", "abroad", "international", "foreign", "trip", "atm", "currency", "rental"],
    "conversation_management": ["conversation", "chat", "history", "message", "context", "session"],
    "account_access": ["account", "login", "password", "access", "suspend", "locked", "2fa"],
    "community": ["community", "forum", "discuss", "badge", "leaderboard", "contest"],
    "assessment": ["assessment", "test", "score", "challenge", "submission", "timer", "code"],
    "fraud": ["fraud", "stolen", "unauthorized", "hack", "identity", "phish", "skimm"],
}


def detect_company(ticket: dict) -> str:
    """
    Detect the company from the Company field or ticket content.
    Returns: 'HackerRank' | 'Claude' | 'Visa' | 'Unknown'
    """
    raw = str(ticket.get("Company", "")).strip()
    # Accept if already valid
    if raw in ("HackerRank", "Claude", "Visa"):
        return raw

    # Try to detect from content
    text = (
        str(ticket.get("Issue", "")) + " " + str(ticket.get("Subject", ""))
    ).lower()

    scores: dict[str, int] = {k: 0 for k in COMPANY_KEYWORDS}
    for company, keywords in COMPANY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                scores[company] += 1

    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best
    return "Unknown"


def is_high_risk(ticket: dict) -> tuple[bool, str]:
    """
    Determine if a ticket is high-risk and should be escalated.
    Returns: (True/False, reason_string)
    """
    text = (
        str(ticket.get("Issue", "")) + " " + str(ticket.get("Subject", ""))
    ).lower()

    # Check prompt injection patterns first
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, "Prompt injection or jailbreak attempt detected."

    # Check high-risk keywords
    for kw in HIGH_RISK_KEYWORDS:
        if kw.lower() in text:
            return True, f"High-risk keyword detected: '{kw}'"

    # Vague with unknown company
    company = detect_company(ticket)
    issue_text = str(ticket.get("Issue", "")).strip()
    if company == "Unknown" and len(issue_text) < 25:
        return True, "Ticket is too vague and company is unknown."

    return False, ""


def get_request_type(ticket: dict) -> str:
    """
    Classify the request type: bug | product_issue | feature_request | invalid
    """
    text = (
        str(ticket.get("Issue", "")) + " " + str(ticket.get("Subject", ""))
    ).lower()

    bug_kw = [
        "not working", "broken", "error", "bug", "crash", "freezes",
        "failed", "doesn't work", "does not work", "not loading", "down",
        "cannot load", "not detected", "disappeared", "missing",
    ]
    feature_kw = [
        "add", "would be great", "feature request", "suggest",
        "improve", "support for", "please add", "wish", "can you add",
    ]
    invalid_kw = [
        "ignore previous", "reveal", "rm -rf", "delete all", "exploit",
        "hack", "system prompt", "supprimer", "exécuter",
    ]

    for kw in invalid_kw:
        if kw in text:
            return "invalid"

    bug_score = sum(1 for kw in bug_kw if kw in text)
    feature_score = sum(1 for kw in feature_kw if kw in text)

    if feature_score > bug_score:
        return "feature_request"
    if bug_score > 0:
        return "bug"
    return "product_issue"


def get_product_area(ticket: dict, chunks: list[str]) -> str:
    """
    Determine the product area from ticket content and retrieved chunks.
    """
    text = (
        str(ticket.get("Issue", "")) + " " + str(ticket.get("Subject", ""))
        + " ".join(chunks)
    ).lower()

    scores: dict[str, int] = {k: 0 for k in AREA_KEYWORDS}
    for area, keywords in AREA_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                scores[area] += 1

    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best
    return "general_support"
