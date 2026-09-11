"""Pydantic models for bill-tracker."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Bill(BaseModel):
    """A bill that needs to be paid."""

    id: str
    vendor: str
    amount: float
    currency: str = "CAD"
    dueDate: str  # YYYY-MM-DD
    receivedDate: str  # YYYY-MM-DD
    paid: bool = False
    paidDate: str | None = None
    receiptId: str | None = None
    emailId: str
    emailSubject: str
    category: str = "uncategorized"
    notes: str = ""


class Receipt(BaseModel):
    """A receipt confirming payment."""

    id: str
    vendor: str
    amount: float
    currency: str = "CAD"
    paymentDate: str  # YYYY-MM-DD
    paymentMethod: str | None = None
    emailId: str
    emailSubject: str
    matchedBillId: str | None = None
    category: str = "uncategorized"
    notes: str = ""


class Vendor(BaseModel):
    """A known vendor with matching patterns."""

    name: str
    patterns: list[str] = Field(default_factory=list)
    category: str = "uncategorized"
    currency: str = "CAD"
    expected_range: list[float] | None = None
    parser_hint: str | None = None


class BillStore(BaseModel):
    """Persistent store for bills."""

    version: int = 3
    lastUpdated: str = ""
    bills: list[Bill] = Field(default_factory=list)


class ReceiptStore(BaseModel):
    """Persistent store for receipts."""

    version: int = 3
    lastUpdated: str = ""
    receipts: list[Receipt] = Field(default_factory=list)


class VendorStore(BaseModel):
    """Persistent store for vendors (known + discovered)."""

    known: list[Vendor] = Field(default_factory=list)
    discovered: list[dict] = Field(default_factory=list)


class ReportSection(BaseModel):
    """A section within a report."""

    id: str
    title: str
    filter: str = ""
    sort: str = ""
    columns: list[str] = Field(default_factory=list)
    delivery: list[str] = Field(default_factory=list)


class ReportConfig(BaseModel):
    """Configuration for report generation."""

    sections: list[ReportSection] = Field(default_factory=list)
    output: dict = Field(default_factory=lambda: {
        "formats": ["md"],
        "file_dir": "./reports",
        "file_pattern": "bill-tracker-report-{date}.{ext}",
    })
    delivery: dict = Field(default_factory=lambda: {
        "telegram": True,
        "telegram_target": "",
    })