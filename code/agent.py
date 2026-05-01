"""
SupportBrain — agent.py
Core per-ticket pipeline: classify → risk check → retrieve → generate → log.
"""

import classifier
import llm_router
import logger
from prompts import ESCALATE_MSG


def run(
    ticket: dict,
    ticket_id: int,
    retriever,
    repo_root: str,
) -> dict:
    """
    Process a single support ticket end-to-end.

    Args:
        ticket:    dict with keys Issue, Subject, Company
        ticket_id: 1-based index for logging
        retriever: Retriever instance (already loaded)
        repo_root: absolute path to repo root

    Returns:
        dict with original ticket fields + response, product_area,
        status, request_type, justification, provider_used
    """
    # 1. Detect company
    company = classifier.detect_company(ticket)
    ticket_with_company = {**ticket, "Company": company}

    # 2. Classify request type
    req_type = classifier.get_request_type(ticket_with_company)

    # 3. Risk check
    high_risk, risk_reason = classifier.is_high_risk(ticket_with_company)

    if high_risk:
        # Escalate immediately — no LLM call
        area = classifier.get_product_area(ticket_with_company, [])
        result = {
            **ticket_with_company,
            "response": ESCALATE_MSG,
            "product_area": area,
            "status": "Escalated",
            "request_type": req_type if req_type != "bug" else "product_issue",
            "justification": risk_reason,
            "provider_used": "none",
            "tokens_used": 0,
        }
        logger.log_to_file(ticket_id, result, "none", "Escalated", risk_reason)
        logger.log_to_sqlite(repo_root, ticket_id, result)
        return result

    # 4. Retrieve relevant corpus chunks
    query = f"{ticket_with_company.get('Subject', '')} {ticket_with_company.get('Issue', '')}"
    chunks = retriever.search(query, company, top_k=3)

    # 5. Generate response via LLM
    llm_response, provider = llm_router.call(ticket_with_company, chunks)

    # 6. Determine product area
    area = classifier.get_product_area(ticket_with_company, chunks)

    # Build final result — LLM fields take precedence but we ensure all keys exist
    status = llm_response.get("status", "Replied")
    justification = llm_response.get("justification", "")

    # Override area from LLM if provided and non-empty
    llm_area = llm_response.get("product_area", "")
    if llm_area and llm_area.strip():
        area = llm_area.strip()

    result = {
        **ticket_with_company,
        "response": llm_response.get("response", ESCALATE_MSG),
        "product_area": area,
        "status": status,
        "request_type": llm_response.get("request_type", req_type),
        "justification": justification,
        "provider_used": provider,
        "tokens_used": llm_response.get("tokens_used", 0),
    }

    logger.log_to_file(ticket_id, result, provider, status, justification)
    logger.log_to_sqlite(repo_root, ticket_id, result)
    return result
