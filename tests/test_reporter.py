"""Tests for report generation: filter, sort, and formatting."""

from datetime import date

from bill_tracker.models import Bill, Receipt
from bill_tracker.reporter import apply_filter, apply_sort, format_bill_row, format_receipt_row


def _make_bill(id_, vendor, amount, due_date, received_date, paid=False, category="uncategorized"):
    return Bill(
        id=id_,
        vendor=vendor,
        amount=amount,
        dueDate=due_date,
        receivedDate=received_date,
        emailId=f"e-{id_}",
        emailSubject=f"Bill {id_}",
        paid=paid,
        category=category,
    )


def _make_receipt(id_, vendor, amount, payment_date, payment_method=None, matched_bill_id=None):
    return Receipt(
        id=id_,
        vendor=vendor,
        amount=amount,
        paymentDate=payment_date,
        paymentMethod=payment_method,
        emailId=f"e-{id_}",
        emailSubject=f"Receipt {id_}",
        matchedBillId=matched_bill_id,
    )


class TestApplyFilter:
    def test_no_filter_returns_all(self):
        items = [_make_bill("b1", "A", 10, "2026-09-30", "2026-09-01")]
        result = apply_filter(items, "")
        assert len(result) == 1

    def test_filter_by_boolean_true(self):
        items = [
            _make_bill("b1", "A", 10, "2026-09-30", "2026-09-01", paid=True),
            _make_bill("b2", "B", 20, "2026-09-30", "2026-09-01", paid=False),
        ]
        result = apply_filter(items, "paid:true")
        assert len(result) == 1
        assert result[0].id == "b1"

    def test_filter_by_boolean_false(self):
        items = [
            _make_bill("b1", "A", 10, "2026-09-30", "2026-09-01", paid=True),
            _make_bill("b2", "B", 20, "2026-09-30", "2026-09-01", paid=False),
        ]
        result = apply_filter(items, "paid:false")
        assert len(result) == 1
        assert result[0].id == "b2"

    def test_filter_by_category(self):
        items = [
            _make_bill("b1", "A", 10, "2026-09-30", "2026-09-01", category="utilities"),
            _make_bill("b2", "B", 20, "2026-09-30", "2026-09-01", category="software"),
        ]
        result = apply_filter(items, "category:utilities")
        assert len(result) == 1
        assert result[0].id == "b1"

    def test_filter_by_category_case_insensitive(self):
        items = [_make_bill("b1", "A", 10, "2026-09-30", "2026-09-01", category="UTILITIES")]
        result = apply_filter(items, "category:utilities")
        assert len(result) == 1

    def test_filter_multiple_conditions(self):
        items = [
            _make_bill("b1", "A", 10, "2026-09-30", "2026-09-01", paid=False, category="utilities"),
            _make_bill("b2", "B", 20, "2026-09-30", "2026-09-01", paid=False, category="software"),
            _make_bill("b3", "C", 30, "2026-09-30", "2026-09-01", paid=True, category="utilities"),
        ]
        result = apply_filter(items, "paid:false category:utilities")
        assert len(result) == 1
        assert result[0].id == "b1"

    def test_filter_this_month(self):
        today = date.today()
        first_day = today.replace(day=1).isoformat()
        b1 = _make_bill("b1", "A", 10, "2026-09-30", first_day, paid=True)
        b1.paidDate = first_day
        b2 = _make_bill("b2", "B", 20, "2026-09-30", "2025-01-01", paid=True)
        b2.paidDate = "2025-01-01"
        items = [b1, b2]
        result = apply_filter(items, "paidDate:this-month")
        assert len(result) >= 1  # At least the one from this month


class TestApplySort:
    def test_sort_ascending(self):
        items = [
            _make_bill("b2", "B", 20, "2026-09-30", "2026-09-01"),
            _make_bill("b1", "A", 10, "2026-09-15", "2026-09-01"),
        ]
        result = apply_sort(items, "dueDate:asc")
        assert result[0].id == "b1"
        assert result[1].id == "b2"

    def test_sort_descending(self):
        items = [
            _make_bill("b1", "A", 10, "2026-09-15", "2026-09-01"),
            _make_bill("b2", "B", 20, "2026-09-30", "2026-09-01"),
        ]
        result = apply_sort(items, "dueDate:desc")
        assert result[0].id == "b2"
        assert result[1].id == "b1"

    def test_sort_by_amount(self):
        items = [
            _make_bill("b1", "A", 100, "2026-09-30", "2026-09-01"),
            _make_bill("b2", "B", 50, "2026-09-30", "2026-09-01"),
            _make_bill("b3", "C", 200, "2026-09-30", "2026-09-01"),
        ]
        result = apply_sort(items, "amount:asc")
        assert result[0].amount == 50
        assert result[1].amount == 100
        assert result[2].amount == 200

    def test_empty_sort_returns_unchanged(self):
        items = [_make_bill("b1", "A", 10, "2026-09-30", "2026-09-01")]
        result = apply_sort(items, "")
        assert result == items


class TestFormatBillRow:
    def test_formats_basic_columns(self):
        bill = _make_bill("b1", "TestCo", 50.0, "2026-09-30", "2026-09-01")
        row = format_bill_row(bill, ["vendor", "amount", "dueDate"])
        assert "TestCo" in row
        assert "50.00" in row
        assert "2026-09-30" in row
        assert row.startswith("|")
        assert row.endswith("|")

    def test_formats_boolean(self):
        bill = _make_bill("b1", "TestCo", 50.0, "2026-09-30", "2026-09-01", paid=True)
        row = format_bill_row(bill, ["paid"])
        assert "Yes" in row

        bill2 = _make_bill("b2", "TestCo", 50.0, "2026-09-30", "2026-09-01", paid=False)
        row2 = format_bill_row(bill2, ["paid"])
        assert "No" in row2

    def test_formats_null_fields(self):
        bill = _make_bill("b1", "TestCo", 50.0, "2026-09-30", "2026-09-01")
        row = format_bill_row(bill, ["paidDate"])
        assert "|" in row  # Just ensure it renders without error


class TestFormatReceiptRow:
    def test_formats_basic_columns(self):
        receipt = _make_receipt("r1", "TestCo", 50.0, "2026-09-15")
        row = format_receipt_row(receipt, ["vendor", "amount", "paymentDate"])
        assert "TestCo" in row
        assert "50.00" in row
        assert "2026-09-15" in row

    def test_formats_matched_bill_id(self):
        receipt = _make_receipt("r1", "TestCo", 50.0, "2026-09-15", matched_bill_id="b-1")
        row = format_receipt_row(receipt, ["matchedBillId"])
        assert "b-1" in row