"""LLM-assisted parsing of bill and receipt fields.

Uses injectable LLM call so tests can pass a mock.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from bill_tracker.models import VendorStore

BILL_PROMPT = """Extract bill information from this email. Return ONLY valid JSON, no other text.

Extract:
- vendor: Company name that sent the bill
- amount: The amount due (just the number, no currency symbol)
- dueDate: Due date in YYYY-MM-DD format, or null if not found
- currency: "CAD" or "USD" or null if unclear

Vendor hints: {vendor_hints}

Return JSON:
{{
  "vendor": "string",
  "amount": number,
  "dueDate": "YYYY-MM-DD" or null,
  "currency": "CAD" | "USD" | null
}}

Email:
Subject: {subject}

{body}

Extraction:"""


RECEIPT_PROMPT = """Extract receipt/payment confirmation information from this email. Return ONLY valid JSON, no other text.

Extract:
- vendor: Company name that received payment
- amount: The payment amount (just the number, no currency symbol)
- paymentDate: Date payment was made in YYYY-MM-DD format, or null if not found
- currency: "CAD" or "USD" or null if unclear
- paymentMethod: "credit", "debit", "transfer", or null

Vendor hints: {vendor_hints}

Return JSON:
{{
  "vendor": "string",
  "amount": number,
  "paymentDate": "YYYY-MM-DD" or null,
  "currency": "CAD" | "USD" | null,
  "paymentMethod": "credit" | "debit" | "transfer" | null
}}

Email:
Subject: {subject}

{body}

Extraction:"""


def _build_hint_text(vendor_hints: list[str] | None) -> str:
    """Build vendor hints text for prompt injection."""
    if not vendor_hints:
        return "None"
    return "\n".join(f"- {h}" for h in vendor_hints)


def parse_bill(
    subject: str,
    body: str,
    model: str,
    vendor_hints: list[str] | None = None,
    llm_call: Callable[[str, str], str] | None = None,
) -> dict:
    """Parse bill fields from an email.

    Args:
        subject: Email subject.
        body: Email body text.
        model: LLM model name.
        vendor_hints: Optional list of vendor-specific parsing hints.
        llm_call: Optional callable(prompt, model) -> str.

    Returns:
        Dict with vendor, amount, dueDate, currency.

    Raises:
        NotImplementedError: If no llm_call is provided.
    """
    if llm_call is None:
        raise NotImplementedError(
            "No LLM callable provided. Pass llm_call=your_function to wire up the LLM."
        )

    prompt = BILL_PROMPT.format(
        subject=subject,
        body=body,
        vendor_hints=_build_hint_text(vendor_hints),
    )
    raw = llm_call(prompt, model)
    return parse_parser_response(raw)


def parse_receipt(
    subject: str,
    body: str,
    model: str,
    vendor_hints: list[str] | None = None,
    llm_call: Callable[[str, str], str] | None = None,
) -> dict:
    """Parse receipt fields from an email.

    Args:
        subject: Email subject.
        body: Email body text.
        model: LLM model name.
        vendor_hints: Optional list of vendor-specific parsing hints.
        llm_call: Optional callable(prompt, model) -> str.

    Returns:
        Dict with vendor, amount, paymentDate, currency, paymentMethod.

    Raises:
        NotImplementedError: If no llm_call is provided.
    """
    if llm_call is None:
        raise NotImplementedError(
            "No LLM callable provided. Pass llm_call=your_function to wire up the LLM."
        )

    prompt = RECEIPT_PROMPT.format(
        subject=subject,
        body=body,
        vendor_hints=_build_hint_text(vendor_hints),
    )
    raw = llm_call(prompt, model)
    return parse_parser_response(raw)


def parse_parser_response(raw: str) -> dict:
    """Parse the raw LLM response into a field dict.

    Args:
        raw: Raw string response from the LLM.

    Returns:
        Dict of extracted fields. Falls back to empty/None values on error.
    """
    # Try to extract JSON from the response
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        raw = json_match.group(0)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if not isinstance(result, dict):
        return {}

    # Normalize amount
    amount = result.get("amount")
    try:
        amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount = None

    # Normalize currency
    currency = result.get("currency")
    if currency not in ("CAD", "USD"):
        currency = None

    # Normalize payment method
    payment_method = result.get("paymentMethod")
    if payment_method not in ("credit", "debit", "transfer"):
        payment_method = None

    return {
        "vendor": result.get("vendor"),
        "amount": amount,
        "dueDate": result.get("dueDate"),
        "paymentDate": result.get("paymentDate"),
        "currency": currency,
        "paymentMethod": payment_method,
    }


def validate_bill_fields(fields: dict, vendors: VendorStore) -> list[str]:
    """Validate parsed bill fields against vendor configuration.

    Args:
        fields: Dict from parse_bill.
        vendors: VendorStore for expected range checks.

    Returns:
        List of warning strings (empty if all good).
    """
    warnings = []

    if not fields.get("vendor"):
        warnings.append("Missing vendor name")
    if fields.get("amount") is None:
        warnings.append("Missing amount")
    if not fields.get("dueDate"):
        warnings.append("Missing due date")
    if not fields.get("currency"):
        warnings.append("Missing or unknown currency")

    # Check against expected range if vendor is known
    vendor_name = fields.get("vendor", "")
    if vendor_name:
        from bill_tracker.vendors import match_vendor

        vendor = match_vendor(vendor_name, vendors)
        if vendor and vendor.expected_range and fields.get("amount") is not None:
            lo, hi = vendor.expected_range
            if fields["amount"] < lo or fields["amount"] > hi:
                warnings.append(
                    f"Amount {fields['amount']} outside expected range "
                    f"[{lo}, {hi}] for vendor {vendor.name}"
                )

    return warnings


def validate_receipt_fields(fields: dict, vendors: VendorStore) -> list[str]:
    """Validate parsed receipt fields against vendor configuration.

    Args:
        fields: Dict from parse_receipt.
        vendors: VendorStore for expected range checks.

    Returns:
        List of warning strings (empty if all good).
    """
    warnings = []

    if not fields.get("vendor"):
        warnings.append("Missing vendor name")
    if fields.get("amount") is None:
        warnings.append("Missing amount")
    if not fields.get("paymentDate"):
        warnings.append("Missing payment date")
    if not fields.get("currency"):
        warnings.append("Missing or unknown currency")

    return warnings