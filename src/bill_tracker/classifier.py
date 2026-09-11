"""Email classification: bill, receipt, or neither.

Uses an injectable LLM call so tests can pass a mock.
"""

from __future__ import annotations

import json
import re
from typing import Callable

CLASSIFIER_PROMPT = """Classify this email. You must return ONLY valid JSON, no other text.

Determine if this email is:
- "bill": An invoice, statement, or payment request (money someone wants you to pay)
- "receipt": A payment confirmation, thank-you-for-paying, or proof of payment
- "neither": Everything else (promotions, newsletters, account notices, etc.)

Return JSON with exactly these fields:
{{
  "type": "bill" | "receipt" | "neither",
  "confidence": 0.0 to 1.0,
  "reason": "1-2 sentence explanation"
}}

Email:
Subject: {subject}

{body}

Classification:"""


def classify_email(
    subject: str,
    body: str,
    model: str,
    llm_call: Callable[[str, str], str] | None = None,
) -> dict:
    """Classify an email as bill, receipt, or neither.

    Args:
        subject: Email subject line.
        body: Email body text.
        model: LLM model name to use.
        llm_call: Optional callable(prompt, model) -> str.
                  If None, raises NotImplementedError.

    Returns:
        Dict with keys: type, confidence, reason.

    Raises:
        NotImplementedError: If no llm_call is provided.
    """
    if llm_call is None:
        raise NotImplementedError(
            "No LLM callable provided. Pass llm_call=your_function to wire up the LLM. "
            "Example: llm_call=lambda prompt, model: openai_call(prompt, model)"
        )

    prompt = CLASSIFIER_PROMPT.format(subject=subject, body=body)
    raw = llm_call(prompt, model)
    return parse_classifier_response(raw)


def parse_classifier_response(raw: str) -> dict:
    """Parse the raw LLM response into a classification dict.

    Args:
        raw: Raw string response from the LLM.

    Returns:
        Dict with type, confidence, reason. Falls back to "neither" on error.
    """
    default = {"type": "neither", "confidence": 0.0, "reason": "Failed to parse LLM response"}

    # Try to extract JSON from the response (may be wrapped in markdown or other text)
    json_match = re.search(r'\{[^{}]*"type"[^{}]*\}', raw, re.DOTALL)
    if json_match:
        raw = json_match.group(0)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return default

    if not isinstance(result, dict):
        return default

    result_type = result.get("type", "neither")
    if result_type not in ("bill", "receipt", "neither"):
        result_type = "neither"

    confidence = result.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    reason = result.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)

    return {
        "type": result_type,
        "confidence": confidence,
        "reason": reason,
    }