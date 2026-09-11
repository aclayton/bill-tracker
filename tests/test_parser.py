"""Tests for parser response parsing and field validation."""

import pytest

from bill_tracker.models import Vendor, VendorStore
from bill_tracker.parser import (
    parse_parser_response,
    validate_bill_fields,
    validate_receipt_fields,
    parse_bill,
    parse_receipt,
)


class TestParseParserResponse:
    def test_parses_bill_fields(self):
        raw = '{"vendor": "Enbridge", "amount": 92.45, "dueDate": "2026-09-28", "currency": "CAD"}'
        result = parse_parser_response(raw)
        assert result["vendor"] == "Enbridge"
        assert result["amount"] == 92.45
        assert result["dueDate"] == "2026-09-28"
        assert result["currency"] == "CAD"

    def test_parses_receipt_fields(self):
        raw = '{"vendor": "Enbridge", "amount": 92.45, "paymentDate": "2026-09-15", "currency": "CAD", "paymentMethod": "credit"}'
        result = parse_parser_response(raw)
        assert result["vendor"] == "Enbridge"
        assert result["amount"] == 92.45
        assert result["paymentDate"] == "2026-09-15"
        assert result["paymentMethod"] == "credit"

    def test_invalid_json_returns_empty_dict(self):
        result = parse_parser_response("not json")
        assert result == {}

    def test_non_numeric_amount_returns_none(self):
        raw = '{"vendor": "Test", "amount": "twelve", "dueDate": null, "currency": null}'
        result = parse_parser_response(raw)
        assert result["amount"] is None

    def test_unknown_currency_returns_none(self):
        raw = '{"vendor": "Test", "amount": 10.0, "dueDate": null, "currency": "EUR"}'
        result = parse_parser_response(raw)
        assert result["currency"] is None

    def test_invalid_payment_method_returns_none(self):
        raw = '{"vendor": "Test", "amount": 10.0, "paymentDate": null, "currency": "CAD", "paymentMethod": "cash"}'
        result = parse_parser_response(raw)
        assert result["paymentMethod"] is None

    def test_parses_json_wrapped_in_text(self):
        raw = 'Extracted: {"vendor": "Enbridge", "amount": 92.45, "dueDate": "2026-09-28", "currency": "CAD"} Done.'
        result = parse_parser_response(raw)
        assert result["vendor"] == "Enbridge"
        assert result["amount"] == 92.45

    def test_null_amount_handled(self):
        raw = '{"vendor": "Test", "amount": null, "dueDate": null, "currency": null}'
        result = parse_parser_response(raw)
        assert result["amount"] is None


class TestValidateBillFields:
    def test_valid_bill_no_warnings(self):
        vendors = VendorStore()
        fields = {"vendor": "Enbridge", "amount": 92.45, "dueDate": "2026-09-28", "currency": "CAD"}
        warnings = validate_bill_fields(fields, vendors)
        assert warnings == []

    def test_missing_vendor(self):
        vendors = VendorStore()
        fields = {"amount": 50.0, "dueDate": "2026-09-28", "currency": "CAD"}
        warnings = validate_bill_fields(fields, vendors)
        assert any("vendor" in w.lower() for w in warnings)

    def test_missing_amount(self):
        vendors = VendorStore()
        fields = {"vendor": "Test", "amount": None, "dueDate": "2026-09-28", "currency": "CAD"}
        warnings = validate_bill_fields(fields, vendors)
        assert any("amount" in w.lower() for w in warnings)

    def test_missing_due_date(self):
        vendors = VendorStore()
        fields = {"vendor": "Test", "amount": 50.0, "dueDate": None, "currency": "CAD"}
        warnings = validate_bill_fields(fields, vendors)
        assert any("due date" in w.lower() for w in warnings)

    def test_missing_currency(self):
        vendors = VendorStore()
        fields = {"vendor": "Test", "amount": 50.0, "dueDate": "2026-09-28", "currency": None}
        warnings = validate_bill_fields(fields, vendors)
        assert any("currency" in w.lower() for w in warnings)

    def test_amount_outside_expected_range(self):
        vendor = Vendor(
            name="Enbridge Gas",
            patterns=["enbridge"],
            expected_range=[25, 180],
            currency="CAD",
        )
        vendors = VendorStore(known=[vendor])
        fields = {"vendor": "Enbridge Gas", "amount": 500.0, "dueDate": "2026-09-28", "currency": "CAD"}
        warnings = validate_bill_fields(fields, vendors)
        assert any("outside expected range" in w for w in warnings)

    def test_amount_within_expected_range(self):
        vendor = Vendor(
            name="Enbridge Gas",
            patterns=["enbridge"],
            expected_range=[25, 180],
            currency="CAD",
        )
        vendors = VendorStore(known=[vendor])
        fields = {"vendor": "Enbridge Gas", "amount": 100.0, "dueDate": "2026-09-28", "currency": "CAD"}
        warnings = validate_bill_fields(fields, vendors)
        # No range warning
        assert not any("outside expected range" in w for w in warnings)


class TestValidateReceiptFields:
    def test_valid_receipt_no_warnings(self):
        vendors = VendorStore()
        fields = {"vendor": "Enbridge", "amount": 92.45, "paymentDate": "2026-09-15", "currency": "CAD"}
        warnings = validate_receipt_fields(fields, vendors)
        assert warnings == []

    def test_missing_vendor(self):
        vendors = VendorStore()
        fields = {"amount": 50.0, "paymentDate": "2026-09-15", "currency": "CAD"}
        warnings = validate_receipt_fields(fields, vendors)
        assert any("vendor" in w.lower() for w in warnings)

    def test_missing_payment_date(self):
        vendors = VendorStore()
        fields = {"vendor": "Test", "amount": 50.0, "currency": "CAD"}
        warnings = validate_receipt_fields(fields, vendors)
        assert any("payment date" in w.lower() for w in warnings)


class TestParseBillFunction:
    def test_raises_not_implemented_without_llm(self):
        with pytest.raises(NotImplementedError, match="No LLM callable"):
            parse_bill("Subject", "Body", "model")

    def test_with_injected_llm(self):
        def mock_llm(prompt: str, model: str) -> str:
            return '{"vendor": "Test", "amount": 50.0, "dueDate": "2026-09-28", "currency": "CAD"}'

        result = parse_bill("S", "B", "model", llm_call=mock_llm)
        assert result["vendor"] == "Test"
        assert result["amount"] == 50.0


class TestParseReceiptFunction:
    def test_raises_not_implemented_without_llm(self):
        with pytest.raises(NotImplementedError, match="No LLM callable"):
            parse_receipt("Subject", "Body", "model")

    def test_with_injected_llm(self):
        def mock_llm(prompt: str, model: str) -> str:
            return '{"vendor": "Test", "amount": 50.0, "paymentDate": "2026-09-15", "currency": "CAD", "paymentMethod": "credit"}'

        result = parse_receipt("S", "B", "model", llm_call=mock_llm)
        assert result["vendor"] == "Test"
        assert result["amount"] == 50.0
        assert result["paymentMethod"] == "credit"