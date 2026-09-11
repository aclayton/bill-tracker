"""Email scanning pipeline: classify → parse → validate → match → store."""

from __future__ import annotations

from datetime import date
from typing import Callable

from bill_tracker.models import Bill, BillStore, Receipt, ReceiptStore, VendorStore
from bill_tracker.classifier import classify_email, parse_classifier_response
from bill_tracker.parser import (
    parse_bill,
    parse_receipt,
    parse_parser_response,
    validate_bill_fields,
    validate_receipt_fields,
)
from bill_tracker.matcher import auto_match_receipts
from bill_tracker.store import mark_bill_paid, upsert_bill, upsert_receipt
from bill_tracker.vendors import discover_vendor, match_vendor


def _generate_bill_id(vendor: str, email_id: str, due_date: str) -> str:
    """Generate a unique bill ID."""
    vendor_slug = vendor.strip().lower().replace(" ", "-")[:20]
    return f"{vendor_slug}-{due_date}-{email_id[:8]}"


def _generate_receipt_id(vendor: str, email_id: str, payment_date: str) -> str:
    """Generate a unique receipt ID."""
    vendor_slug = vendor.strip().lower().replace(" ", "-")[:20]
    return f"{vendor_slug}-{payment_date}-{email_id[:8]}"


def scan_email(
    subject: str,
    body: str,
    email_id: str,
    config: dict,
    vendors: VendorStore,
    llm_call: Callable[[str, str], str] | None = None,
) -> dict:
    """Run the full scan pipeline on a single email.

    Steps:
    1. Classify as bill/receipt/neither
    2. Parse fields based on classification
    3. Validate against vendor config
    4. Return structured result

    Args:
        subject: Email subject.
        body: Email body text.
        email_id: Unique email identifier.
        config: Configuration dict (from load_config).
        vendors: VendorStore.
        llm_call: Optional LLM callable.

    Returns:
        Dict with type, fields, warnings, and metadata.
    """
    model = config.get("parser", {}).get("model", "google/gemini-3-flash-preview")
    confidence_threshold = config.get("matching", {}).get("confidence_threshold", 0.7)

    result: dict = {
        "email_id": email_id,
        "subject": subject,
        "type": "neither",
        "fields": {},
        "warnings": [],
        "classification": {},
    }

    # Step 1: Classify
    if llm_call:
        classification = classify_email(subject, body, model, llm_call=llm_call)
    else:
        classification = parse_classifier_response(
            '{"type": "neither", "confidence": 0.0, "reason": "No LLM callable"}'
        )
    result["classification"] = classification

    if classification["type"] == "neither":
        result["type"] = "neither"
        return result

    if classification["confidence"] < confidence_threshold:
        result["type"] = "neither"
        result["warnings"].append(
            f"Classification confidence ({classification['confidence']}) below threshold ({confidence_threshold})"
        )
        return result

    # Step 2: Parse
    vendor_hints = _get_vendor_hints(classification.get("vendor_hint", ""), vendors)

    if classification["type"] == "bill":
        if llm_call:
            fields = parse_bill(subject, body, model, vendor_hints, llm_call=llm_call)
        else:
            fields = parse_parser_response("{}")
        result["type"] = "bill"
        result["warnings"].extend(validate_bill_fields(fields, vendors))
    elif classification["type"] == "receipt":
        if llm_call:
            fields = parse_receipt(subject, body, model, vendor_hints, llm_call=llm_call)
        else:
            fields = parse_parser_response("{}")
        result["type"] = "receipt"
        result["warnings"].extend(validate_receipt_fields(fields, vendors))
    else:
        result["type"] = "neither"
        return result

    result["fields"] = fields
    return result


def _get_vendor_hints(vendor_name: str, vendors: VendorStore) -> list[str] | None:
    """Get vendor hints for matching vendor."""
    if not vendor_name:
        return None
    matched = match_vendor(vendor_name, vendors)
    if matched and matched.parser_hint:
        return [matched.parser_hint]
    return None


def process_scan_result(
    result: dict,
    store_bills: BillStore,
    store_receipts: ReceiptStore,
    vendors: VendorStore,
    config: dict,
) -> dict:
    """Store a scan result and handle auto-matching.

    Args:
        result: Result dict from scan_email.
        store_bills: Current BillStore (mutated in place).
        store_receipts: Current ReceiptStore (mutated in place).
        vendors: VendorStore (mutated in place).
        config: Configuration dict.

    Returns:
        Processing summary dict.
    """
    today = date.today().isoformat()
    tolerance = config.get("matching", {}).get("amount_tolerance", 0.50)

    summary: dict = {
        "action": "none",
        "details": "",
    }

    if result["type"] == "neither":
        summary["action"] = "skipped"
        summary["details"] = result.get("classification", {}).get("reason", "not a bill or receipt")
        return summary

    fields = result["fields"]
    vendor_name = fields.get("vendor", "Unknown")
    email_id = result["email_id"]
    subject = result["subject"]

    if result["type"] == "bill":
        due_date = fields.get("dueDate") or today
        bill_id = _generate_bill_id(vendor_name, email_id, due_date)

        # Auto-discover vendor if not known
        if not match_vendor(vendor_name, vendors):
            discover_vendor(
                vendor_name,
                vendors,
                fields.get("amount", 0.0),
                fields.get("currency", "CAD"),
            )

        matched_vendor = match_vendor(vendor_name, vendors)
        category = matched_vendor.category if matched_vendor else "uncategorized"

        bill = Bill(
            id=bill_id,
            vendor=vendor_name,
            amount=fields.get("amount", 0.0),
            currency=fields.get("currency", "CAD"),
            dueDate=due_date,
            receivedDate=today,
            paid=False,
            emailId=email_id,
            emailSubject=subject,
            category=category,
            notes="",
        )
        upsert_bill(store_bills, bill)
        summary["action"] = "bill_stored"
        summary["details"] = f"Bill from {vendor_name}: {fields.get('currency', 'CAD')} {fields.get('amount', 0.0)} due {due_date}"
        summary["bill_id"] = bill_id

    elif result["type"] == "receipt":
        payment_date = fields.get("paymentDate") or today
        receipt_id = _generate_receipt_id(vendor_name, email_id, payment_date)

        if not match_vendor(vendor_name, vendors):
            discover_vendor(
                vendor_name,
                vendors,
                fields.get("amount", 0.0),
                fields.get("currency", "CAD"),
            )

        matched_vendor = match_vendor(vendor_name, vendors)
        category = matched_vendor.category if matched_vendor else "uncategorized"

        receipt = Receipt(
            id=receipt_id,
            vendor=vendor_name,
            amount=fields.get("amount", 0.0),
            currency=fields.get("currency", "CAD"),
            paymentDate=payment_date,
            paymentMethod=fields.get("paymentMethod"),
            emailId=email_id,
            emailSubject=subject,
            category=category,
            notes="",
        )
        upsert_receipt(store_receipts, receipt)

        # Auto-match receipt to unpaid bill
        unpaid_bills = [b for b in store_bills.bills if not b.paid]
        from bill_tracker.matcher import match_receipt_to_bill

        matched_bill_id = match_receipt_to_bill(receipt, unpaid_bills, tolerance, vendors)
        if matched_bill_id:
            receipt.matchedBillId = matched_bill_id
            mark_bill_paid(store_bills, matched_bill_id, payment_date, receipt_id)
            summary["action"] = "receipt_matched"
            summary["details"] = (
                f"Receipt from {vendor_name} matched to bill {matched_bill_id}. "
                f"Bill marked paid."
            )
        else:
            summary["action"] = "receipt_stored"
            summary["details"] = (
                f"Receipt from {vendor_name}: {fields.get('currency', 'CAD')} {fields.get('amount', 0.0)} "
                f"(unmatched)"
            )
        summary["receipt_id"] = receipt_id

    return summary