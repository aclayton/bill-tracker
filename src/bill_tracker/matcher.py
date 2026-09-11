"""Receipt-to-bill matching logic."""

from __future__ import annotations

from bill_tracker.models import Bill, Receipt, VendorStore


def match_receipt_to_bill(
    receipt: Receipt,
    bills: list[Bill],
    tolerance: float,
    vendors: VendorStore | None = None,
) -> str | None:
    """Try to match a receipt to an unpaid bill.

    Matching criteria:
    1. Vendor match (case-insensitive, via vendor aliases if VendorStore given)
    2. Amount within tolerance
    3. Receipt payment date >= bill received date

    Args:
        receipt: The receipt to match.
        bills: List of bills to search (typically unpaid ones).
        tolerance: Amount tolerance (e.g., 0.50 means ±$0.50).
        vendors: Optional VendorStore for alias-based vendor matching.

    Returns:
        Matched bill_id, or None if no unique match.
    """
    candidates: list[str] = []
    receipt_vendor_lower = receipt.vendor.strip().lower()

    for bill in bills:
        if bill.paid:
            continue

        # Vendor match
        if not _vendor_matches(receipt_vendor_lower, bill.vendor.strip().lower(), vendors):
            continue

        # Amount within tolerance
        if abs(receipt.amount - bill.amount) > tolerance:
            continue

        # Date ordering: receipt payment date >= bill received date
        if receipt.paymentDate < bill.receivedDate:
            continue

        candidates.append(bill.id)

    # Only return if exactly one match (avoid ambiguity)
    if len(candidates) == 1:
        return candidates[0]
    return None


def _vendor_matches(
    receipt_vendor: str,
    bill_vendor: str,
    vendors: VendorStore | None,
) -> bool:
    """Check if receipt vendor matches bill vendor, using aliases if available."""
    # Direct match
    if receipt_vendor == bill_vendor:
        return True
    if receipt_vendor in bill_vendor or bill_vendor in receipt_vendor:
        return True

    # Use vendor aliases if available
    if vendors is not None:
        from bill_tracker.vendors import match_vendor

        receipt_match = match_vendor(receipt_vendor, vendors)
        bill_match = match_vendor(bill_vendor, vendors)
        if receipt_match is not None and bill_match is not None:
            if receipt_match.name == bill_match.name:
                return True

    return False


def auto_match_receipts(
    receipts: list[Receipt],
    bills: list[Bill],
    tolerance: float,
    vendors: VendorStore | None = None,
) -> dict:
    """Auto-match receipts to unpaid bills.

    Args:
        receipts: List of receipts to match.
        bills: List of bills (all, including already paid).
        tolerance: Amount tolerance for matching.
        vendors: Optional VendorStore for alias matching.

    Returns:
        Dict with "matched" (receipt_id -> bill_id) and "unmatched" (list of receipt_ids).
    """
    matched: dict[str, str] = {}
    unmatched: list[str] = []

    unpaid_bills = [b for b in bills if not b.paid]

    for receipt in receipts:
        result = match_receipt_to_bill(receipt, unpaid_bills, tolerance, vendors)
        if result:
            matched[receipt.id] = result
            # Remove matched bill from candidates to avoid double-matching
            unpaid_bills = [b for b in unpaid_bills if b.id != result]
        else:
            unmatched.append(receipt.id)

    return {"matched": matched, "unmatched": unmatched}