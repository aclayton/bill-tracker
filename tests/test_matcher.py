"""Tests for receipt-to-bill matching logic."""

from bill_tracker.models import Bill, Receipt, Vendor, VendorStore
from bill_tracker.matcher import match_receipt_to_bill, auto_match_receipts


def _make_bill(
    id_: str,
    vendor: str,
    amount: float,
    received_date: str,
    due_date: str,
    paid: bool = False,
) -> Bill:
    return Bill(
        id=id_,
        vendor=vendor,
        amount=amount,
        dueDate=due_date,
        receivedDate=received_date,
        emailId=f"email-{id_}",
        emailSubject=f"Bill from {vendor}",
        paid=paid,
    )


def _make_receipt(
    id_: str,
    vendor: str,
    amount: float,
    payment_date: str,
) -> Receipt:
    return Receipt(
        id=id_,
        vendor=vendor,
        amount=amount,
        paymentDate=payment_date,
        emailId=f"email-{id_}",
        emailSubject=f"Receipt from {vendor}",
    )


class TestMatchReceiptToBill:
    def test_exact_match(self):
        bill = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-10", "2026-09-28")
        receipt = _make_receipt("r-1", "Enbridge Gas", 92.45, "2026-09-15")

        result = match_receipt_to_bill(receipt, [bill], 0.50)
        assert result == "b-1"

    def test_amount_within_tolerance(self):
        bill = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-10", "2026-09-28")
        receipt = _make_receipt("r-1", "Enbridge Gas", 92.80, "2026-09-15")

        result = match_receipt_to_bill(receipt, [bill], 0.50)
        assert result == "b-1"

    def test_amount_outside_tolerance(self):
        bill = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-10", "2026-09-28")
        receipt = _make_receipt("r-1", "Enbridge Gas", 100.00, "2026-09-15")

        result = match_receipt_to_bill(receipt, [bill], 0.50)
        assert result is None

    def test_vendor_mismatch(self):
        bill = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-10", "2026-09-28")
        receipt = _make_receipt("r-1", "Hydro Ottawa", 92.45, "2026-09-15")

        result = match_receipt_to_bill(receipt, [bill], 0.50)
        assert result is None

    def test_date_ordering_violation(self):
        # Receipt payment date is before bill received date
        bill = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-20", "2026-09-28")
        receipt = _make_receipt("r-1", "Enbridge Gas", 92.45, "2026-09-15")

        result = match_receipt_to_bill(receipt, [bill], 0.50)
        assert result is None

    def test_skips_already_paid_bills(self):
        bill = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-10", "2026-09-28", paid=True)
        receipt = _make_receipt("r-1", "Enbridge Gas", 92.45, "2026-09-15")

        result = match_receipt_to_bill(receipt, [bill], 0.50)
        assert result is None

    def test_ambiguous_multiple_matches_returns_none(self):
        bill1 = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-10", "2026-09-28")
        bill2 = _make_bill("b-2", "Enbridge", 92.45, "2026-09-12", "2026-09-28")
        receipt = _make_receipt("r-1", "Enbridge Gas", 92.45, "2026-09-15")

        result = match_receipt_to_bill(receipt, [bill1, bill2], 0.50)
        # Both match since "Enbridge" is substring of "Enbridge Gas"
        assert result is None

    def test_vendor_alias_match(self):
        vendors = VendorStore(
            known=[Vendor(name="Enbridge Gas", patterns=["enbridge", "enbridge gas"])]
        )
        bill = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-10", "2026-09-28")
        receipt = _make_receipt("r-1", "enbridge", 92.45, "2026-09-15")

        result = match_receipt_to_bill(receipt, [bill], 0.50, vendors=vendors)
        assert result == "b-1"

    def test_no_bills(self):
        receipt = _make_receipt("r-1", "TestCo", 50.0, "2026-09-15")
        result = match_receipt_to_bill(receipt, [], 0.50)
        assert result is None


class TestAutoMatchReceipts:
    def test_matches_and_returns_unmatched(self):
        bill = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-10", "2026-09-28")
        receipt1 = _make_receipt("r-1", "Enbridge Gas", 92.45, "2026-09-15")
        receipt2 = _make_receipt("r-2", "Unknown Vendor", 50.0, "2026-09-15")

        result = auto_match_receipts([receipt1, receipt2], [bill], 0.50)
        assert result["matched"] == {"r-1": "b-1"}
        assert result["unmatched"] == ["r-2"]

    def test_does_not_double_match(self):
        bill = _make_bill("b-1", "Enbridge Gas", 92.45, "2026-09-10", "2026-09-28")
        receipt1 = _make_receipt("r-1", "Enbridge Gas", 92.45, "2026-09-15")
        receipt2 = _make_receipt("r-2", "Enbridge Gas", 92.45, "2026-09-16")

        result = auto_match_receipts([receipt1, receipt2], [bill], 0.50)
        assert len(result["matched"]) == 1
        assert len(result["unmatched"]) == 1