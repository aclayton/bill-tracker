"""Tests for Pydantic models."""

from bill_tracker.models import (
    Bill,
    Receipt,
    Vendor,
    BillStore,
    ReceiptStore,
    VendorStore,
    ReportSection,
    ReportConfig,
)


class TestBill:
    def test_create_bill_minimal(self):
        bill = Bill(
            id="test-1",
            vendor="TestCo",
            amount=50.00,
            dueDate="2026-09-30",
            receivedDate="2026-09-10",
            emailId="abc123",
            emailSubject="Test bill",
        )
        assert bill.id == "test-1"
        assert bill.vendor == "TestCo"
        assert bill.amount == 50.00
        assert bill.currency == "CAD"
        assert bill.paid is False
        assert bill.paidDate is None
        assert bill.receiptId is None
        assert bill.category == "uncategorized"
        assert bill.notes == ""

    def test_create_bill_full(self):
        bill = Bill(
            id="test-2",
            vendor="ACME Inc",
            amount=99.99,
            currency="USD",
            dueDate="2026-10-15",
            receivedDate="2026-10-01",
            paid=True,
            paidDate="2026-10-02",
            receiptId="rec-123",
            emailId="def456",
            emailSubject="ACME invoice",
            category="software",
            notes="Annual subscription",
        )
        assert bill.paid is True
        assert bill.paidDate == "2026-10-02"
        assert bill.receiptId == "rec-123"
        assert bill.category == "software"

    def test_bill_defaults(self):
        bill = Bill(
            id="t",
            vendor="v",
            amount=1.0,
            dueDate="2026-01-01",
            receivedDate="2026-01-01",
            emailId="e",
            emailSubject="s",
        )
        assert bill.currency == "CAD"
        assert bill.paid is False
        assert bill.category == "uncategorized"
        assert bill.notes == ""


class TestReceipt:
    def test_create_receipt_minimal(self):
        receipt = Receipt(
            id="r-1",
            vendor="TestCo",
            amount=50.00,
            paymentDate="2026-09-15",
            emailId="ghi789",
            emailSubject="Payment confirmation",
        )
        assert receipt.id == "r-1"
        assert receipt.amount == 50.00
        assert receipt.currency == "CAD"
        assert receipt.matchedBillId is None
        assert receipt.paymentMethod is None
        assert receipt.category == "uncategorized"

    def test_create_receipt_full(self):
        receipt = Receipt(
            id="r-2",
            vendor="ACME",
            amount=99.99,
            currency="USD",
            paymentDate="2026-10-02",
            paymentMethod="credit",
            emailId="jkl012",
            emailSubject="ACME payment receipt",
            matchedBillId="b-123",
            category="software",
            notes="Matched automatically",
        )
        assert receipt.paymentMethod == "credit"
        assert receipt.matchedBillId == "b-123"
        assert receipt.category == "software"


class TestVendor:
    def test_create_vendor(self):
        v = Vendor(
            name="Enbridge Gas",
            patterns=["enbridge", "enbridge gas"],
            category="utilities",
            currency="CAD",
            expected_range=[25, 180],
            parser_hint="Hint",
        )
        assert v.name == "Enbridge Gas"
        assert len(v.patterns) == 2
        assert v.category == "utilities"
        assert v.expected_range == [25, 180]
        assert v.parser_hint == "Hint"

    def test_vendor_defaults(self):
        v = Vendor(name="TestCo")
        assert v.patterns == []
        assert v.category == "uncategorized"
        assert v.currency == "CAD"
        assert v.expected_range is None
        assert v.parser_hint is None


class TestBillStore:
    def test_create_empty(self):
        store = BillStore()
        assert store.version == 3
        assert store.bills == []

    def test_create_with_bills(self):
        bill = Bill(
            id="b-1",
            vendor="TestCo",
            amount=10.0,
            dueDate="2026-09-30",
            receivedDate="2026-09-01",
            emailId="abc",
            emailSubject="Bill",
        )
        store = BillStore(bills=[bill])
        assert len(store.bills) == 1
        assert store.bills[0].id == "b-1"


class TestReceiptStore:
    def test_create_empty(self):
        store = ReceiptStore()
        assert store.version == 3
        assert store.receipts == []


class TestVendorStore:
    def test_create_empty(self):
        store = VendorStore()
        assert store.known == []
        assert store.discovered == []

    def test_create_with_vendors(self):
        v = Vendor(name="TestCo")
        store = VendorStore(known=[v], discovered=[{"name": "NewCo", "first_seen": "", "occurrences": 1, "sample_amount": 50.0, "sample_currency": "CAD"}])
        assert len(store.known) == 1
        assert len(store.discovered) == 1
        assert store.discovered[0]["name"] == "NewCo"


class TestReportSection:
    def test_create(self):
        s = ReportSection(
            id="unpaid",
            title="Unpaid Bills",
            filter="paid:false",
            sort="dueDate:asc",
            columns=["vendor", "amount"],
            delivery=["telegram"],
        )
        assert s.id == "unpaid"
        assert s.columns == ["vendor", "amount"]


class TestReportConfig:
    def test_create(self):
        cfg = ReportConfig()
        assert cfg.sections == []
        assert cfg.output["formats"] == ["md"]

    def test_create_with_sections(self):
        s = ReportSection(id="s1", title="Section 1")
        cfg = ReportConfig(sections=[s])
        assert len(cfg.sections) == 1