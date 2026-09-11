"""JSON file storage with atomic writes."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone

from bill_tracker.models import Bill, BillStore, Receipt, ReceiptStore


def _atomic_write(path: str, data: dict) -> None:
    """Write JSON data atomically: write to .tmp then rename."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp_path, path)


def _make_path(data_dir: str, filename: str) -> str:
    """Ensure data_dir exists and return full path to filename."""
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)


def load_bills(data_dir: str) -> BillStore:
    """Load bills from data_dir/bills.json.

    Args:
        data_dir: Directory containing bills.json.

    Returns:
        BillStore (empty if file missing or unreadable).
    """
    path = os.path.join(data_dir, "bills.json")
    if not os.path.exists(path):
        return BillStore()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        bills = [Bill(**b) for b in data.get("bills", [])]
        return BillStore(
            version=data.get("version", 3),
            lastUpdated=data.get("lastUpdated", ""),
            bills=bills,
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return BillStore()


def save_bills(data_dir: str, store: BillStore) -> None:
    """Save BillStore to data_dir/bills.json (atomic write).

    Args:
        data_dir: Directory to write bills.json into.
        store: BillStore to persist.
    """
    path = _make_path(data_dir, "bills.json")
    store.lastUpdated = datetime.now(timezone.utc).isoformat()
    data = store.model_dump()
    _atomic_write(path, data)


def load_receipts(data_dir: str) -> ReceiptStore:
    """Load receipts from data_dir/receipts.json.

    Args:
        data_dir: Directory containing receipts.json.

    Returns:
        ReceiptStore (empty if file missing or unreadable).
    """
    path = os.path.join(data_dir, "receipts.json")
    if not os.path.exists(path):
        return ReceiptStore()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        receipts = [Receipt(**r) for r in data.get("receipts", [])]
        return ReceiptStore(
            version=data.get("version", 3),
            lastUpdated=data.get("lastUpdated", ""),
            receipts=receipts,
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return ReceiptStore()


def save_receipts(data_dir: str, store: ReceiptStore) -> None:
    """Save ReceiptStore to data_dir/receipts.json (atomic write).

    Args:
        data_dir: Directory to write receipts.json into.
        store: ReceiptStore to persist.
    """
    path = _make_path(data_dir, "receipts.json")
    store.lastUpdated = datetime.now(timezone.utc).isoformat()
    data = store.model_dump()
    _atomic_write(path, data)


def upsert_bill(store: BillStore, bill: Bill) -> BillStore:
    """Add or update a bill by id.

    Args:
        store: Existing BillStore.
        bill: Bill to insert or update.

    Returns:
        Modified BillStore (same object, mutated in place).
    """
    for i, existing in enumerate(store.bills):
        if existing.id == bill.id:
            store.bills[i] = bill
            return store
    store.bills.append(bill)
    return store


def upsert_receipt(store: ReceiptStore, receipt: Receipt) -> ReceiptStore:
    """Add or update a receipt by id.

    Args:
        store: Existing ReceiptStore.
        receipt: Receipt to insert or update.

    Returns:
        Modified ReceiptStore (same object, mutated in place).
    """
    for i, existing in enumerate(store.receipts):
        if existing.id == receipt.id:
            store.receipts[i] = receipt
            return store
    store.receipts.append(receipt)
    return store


def mark_bill_paid(
    store: BillStore,
    bill_id: str,
    paid_date: str,
    receipt_id: str | None = None,
) -> bool:
    """Mark a bill as paid.

    Args:
        store: BillStore to modify.
        bill_id: ID of the bill to mark paid.
        paid_date: Date payment was made (YYYY-MM-DD).
        receipt_id: Optional receipt ID that matched this bill.

    Returns:
        True if the bill was found and marked, False otherwise.
    """
    for bill in store.bills:
        if bill.id == bill_id:
            bill.paid = True
            bill.paidDate = paid_date
            if receipt_id:
                bill.receiptId = receipt_id
            return True
    return False


def backup_store(data_dir: str) -> None:
    """Backup bills.json and receipts.json by renaming to .bak.

    Args:
        data_dir: Directory containing the JSON files.
    """
    for name in ("bills.json", "receipts.json"):
        src = os.path.join(data_dir, name)
        dst = os.path.join(data_dir, name + ".bak")
        if os.path.exists(src):
            shutil.copy2(src, dst)