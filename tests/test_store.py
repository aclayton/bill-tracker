"""Tests for JSON store operations."""

import os
import tempfile

from bill_tracker.models import Bill, BillStore, Receipt, ReceiptStore
from bill_tracker.store import (
    load_bills,
    save_bills,
    load_receipts,
    save_receipts,
    upsert_bill,
    upsert_receipt,
    mark_bill_paid,
    backup_store,
)


class TestBillStore:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BillStore()
            bill = Bill(
                id="b-1",
                vendor="TestCo",
                amount=50.0,
                dueDate="2026-09-30",
                receivedDate="2026-09-10",
                emailId="abc123",
                emailSubject="Test bill",
            )
            store.bills.append(bill)

            save_bills(tmpdir, store)
            assert os.path.exists(os.path.join(tmpdir, "bills.json"))

            loaded = load_bills(tmpdir)
            assert loaded.version == 3
            assert len(loaded.bills) == 1
            assert loaded.bills[0].id == "b-1"
            assert loaded.bills[0].vendor == "TestCo"
            assert loaded.bills[0].amount == 50.0

    def test_load_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = load_bills(tmpdir)
            assert store.version == 3
            assert store.bills == []

    def test_atomic_write_does_not_corrupt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BillStore()
            bill = Bill(
                id="b-1",
                vendor="TestCo",
                amount=100.0,
                dueDate="2026-10-01",
                receivedDate="2026-09-01",
                emailId="abc",
                emailSubject="Bill",
            )
            store.bills.append(bill)
            save_bills(tmpdir, store)

            # No .tmp file should remain after atomic write
            assert not os.path.exists(os.path.join(tmpdir, "bills.json.tmp"))

            loaded = load_bills(tmpdir)
            assert len(loaded.bills) == 1
            assert loaded.bills[0].amount == 100.0

    def test_upsert_bill_new(self):
        store = BillStore()
        bill = Bill(
            id="b-new",
            vendor="NewCo",
            amount=25.0,
            dueDate="2026-09-30",
            receivedDate="2026-09-01",
            emailId="abc",
            emailSubject="New bill",
        )
        upsert_bill(store, bill)
        assert len(store.bills) == 1
        assert store.bills[0].id == "b-new"

    def test_upsert_bill_existing(self):
        store = BillStore()
        bill1 = Bill(
            id="b-1",
            vendor="TestCo",
            amount=50.0,
            dueDate="2026-09-30",
            receivedDate="2026-09-01",
            emailId="abc",
            emailSubject="Original",
        )
        store.bills.append(bill1)

        bill2 = Bill(
            id="b-1",
            vendor="TestCo",
            amount=75.0,
            dueDate="2026-09-30",
            receivedDate="2026-09-01",
            emailId="abc",
            emailSubject="Updated",
        )
        upsert_bill(store, bill2)
        assert len(store.bills) == 1
        assert store.bills[0].amount == 75.0
        assert store.bills[0].emailSubject == "Updated"

    def test_mark_bill_paid(self):
        store = BillStore()
        bill = Bill(
            id="b-1",
            vendor="TestCo",
            amount=50.0,
            dueDate="2026-09-30",
            receivedDate="2026-09-01",
            emailId="abc",
            emailSubject="Bill",
        )
        store.bills.append(bill)

        result = mark_bill_paid(store, "b-1", "2026-09-15", "r-1")
        assert result is True
        assert store.bills[0].paid is True
        assert store.bills[0].paidDate == "2026-09-15"
        assert store.bills[0].receiptId == "r-1"

    def test_mark_bill_paid_not_found(self):
        store = BillStore()
        result = mark_bill_paid(store, "nonexistent", "2026-09-15")
        assert result is False

    def test_mark_bill_paid_no_receipt(self):
        store = BillStore()
        bill = Bill(
            id="b-1",
            vendor="TestCo",
            amount=50.0,
            dueDate="2026-09-30",
            receivedDate="2026-09-01",
            emailId="abc",
            emailSubject="Bill",
        )
        store.bills.append(bill)
        mark_bill_paid(store, "b-1", "2026-09-15")
        assert store.bills[0].paid is True
        assert store.bills[0].receiptId is None


class TestReceiptStore:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReceiptStore()
            receipt = Receipt(
                id="r-1",
                vendor="TestCo",
                amount=50.0,
                paymentDate="2026-09-15",
                emailId="def456",
                emailSubject="Payment",
            )
            store.receipts.append(receipt)

            save_receipts(tmpdir, store)
            loaded = load_receipts(tmpdir)
            assert len(loaded.receipts) == 1
            assert loaded.receipts[0].id == "r-1"
            assert loaded.receipts[0].vendor == "TestCo"

    def test_load_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = load_receipts(tmpdir)
            assert store.version == 3
            assert store.receipts == []

    def test_upsert_receipt_new(self):
        store = ReceiptStore()
        receipt = Receipt(
            id="r-new",
            vendor="NewCo",
            amount=25.0,
            paymentDate="2026-09-15",
            emailId="abc",
            emailSubject="New receipt",
        )
        upsert_receipt(store, receipt)
        assert len(store.receipts) == 1

    def test_upsert_receipt_existing(self):
        store = ReceiptStore()
        r1 = Receipt(
            id="r-1",
            vendor="Co",
            amount=10.0,
            paymentDate="2026-09-01",
            emailId="abc",
            emailSubject="Old",
        )
        store.receipts.append(r1)
        r2 = Receipt(
            id="r-1",
            vendor="Co",
            amount=20.0,
            paymentDate="2026-09-01",
            emailId="abc",
            emailSubject="Updated",
        )
        upsert_receipt(store, r2)
        assert len(store.receipts) == 1
        assert store.receipts[0].amount == 20.0


class TestBackup:
    def test_backup_creates_bak_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create bills.json
            store = BillStore()
            bill = Bill(
                id="b-1",
                vendor="Test",
                amount=1.0,
                dueDate="2026-01-01",
                receivedDate="2026-01-01",
                emailId="x",
                emailSubject="s",
            )
            store.bills.append(bill)
            save_bills(tmpdir, store)

            # Create receipts.json
            rstore = ReceiptStore()
            save_receipts(tmpdir, rstore)

            backup_store(tmpdir)

            assert os.path.exists(os.path.join(tmpdir, "bills.json.bak"))
            assert os.path.exists(os.path.join(tmpdir, "receipts.json.bak"))