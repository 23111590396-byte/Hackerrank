"""
SupportBrain — llm_router.py
Groq (primary) + Google Gemini (fallback) LLM routing with retry logic.
"""

import json
import os

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from prompts import SYSTEM_PROMPT, build_user_prompt

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "llama-3.3-70b-versatile")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini-2.0-flash")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "800"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))

_groq_client = None
_gemini_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        import httpx
        from groq import Groq
        # Set a 20-second timeout to avoid indefinite hangs
        http_client = httpx.Client(timeout=20.0)
        _groq_client = Groq(api_key=os.environ["GROQ_API_KEY"], http_client=http_client)
    return _groq_client


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _gemini_client


def _parse_json_response(text: str) -> dict:
    """Extract the first JSON object from an LLM response string."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find {...} block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _groq_call(ticket: dict, chunks: list[str]) -> tuple[dict, str]:
    """Call the Groq API and return (parsed_response_dict, provider_name)."""
    client = _get_groq_client()
    user_prompt = build_user_prompt(ticket, chunks)
    response = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    content = response.choices[0].message.content
    tokens_used = getattr(response.usage, "total_tokens", 0)
    parsed = _parse_json_response(content)
    parsed["tokens_used"] = tokens_used
    return parsed, "groq"


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _gemini_call(ticket: dict, chunks: list[str]) -> tuple[dict, str]:
    """Call the Gemini API and return (parsed_response_dict, provider_name)."""
    from google.genai import types as genai_types
    client = _get_gemini_client()
    user_prompt = build_user_prompt(ticket, chunks)
    full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt
    response = client.models.generate_content(
        model=FALLBACK_MODEL,
        contents=full_prompt,
        config=genai_types.GenerateContentConfig(
            max_output_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        ),
    )
    content = response.text
    parsed = _parse_json_response(content)
    parsed.setdefault("tokens_used", 0)
    return parsed, "gemini"


def call(ticket: dict, chunks: list[str]) -> tuple[dict, str]:
    """
    Route an LLM call: try Groq first, fall back to Gemini on rate limit or error.
    Returns: (response_dict, provider_used)
    """
    groq_available = bool(os.getenv("GROQ_API_KEY", "").strip())
    gemini_available = bool(os.getenv("GEMINI_API_KEY", "").strip())

    if groq_available:
        try:
            return _groq_call(ticket, chunks)
        except Exception as groq_err:
            # Fall through to Gemini
            pass

    if gemini_available:
        try:
            return _gemini_call(ticket, chunks)
        except Exception:
            pass

    # Both providers failed — return a safe escalation response
    from prompts import ESCALATE_MSG
    return {
        "response": ESCALATE_MSG,
        "product_area": "general_support",
        "status": "Escalated",
        "request_type": "product_issue",
        "justification": "All LLM providers failed. Escalating for manual review.",
        "tokens_used": 0,
    }, "none"
