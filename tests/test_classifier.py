"""Tests for classifier response parsing."""

import pytest

from bill_tracker.classifier import parse_classifier_response, classify_email


class TestParseClassifierResponse:
    def test_parses_valid_bill_json(self):
        raw = '{"type": "bill", "confidence": 0.95, "reason": "It is an invoice"}'
        result = parse_classifier_response(raw)
        assert result["type"] == "bill"
        assert result["confidence"] == 0.95
        assert result["reason"] == "It is an invoice"

    def test_parses_valid_receipt_json(self):
        raw = '{"type": "receipt", "confidence": 0.9, "reason": "Payment confirmation"}'
        result = parse_classifier_response(raw)
        assert result["type"] == "receipt"
        assert result["confidence"] == 0.9

    def test_parses_valid_neither_json(self):
        raw = '{"type": "neither", "confidence": 0.99, "reason": "Promotional email"}'
        result = parse_classifier_response(raw)
        assert result["type"] == "neither"

    def test_invalid_json_returns_neither_default(self):
        raw = "not json at all"
        result = parse_classifier_response(raw)
        assert result["type"] == "neither"
        assert result["confidence"] == 0.0

    def test_missing_type_returns_neither(self):
        raw = '{"confidence": 0.5}'
        result = parse_classifier_response(raw)
        assert result["type"] == "neither"

    def test_unknown_type_returns_neither(self):
        raw = '{"type": "spam", "confidence": 0.9}'
        result = parse_classifier_response(raw)
        assert result["type"] == "neither"

    def test_non_numeric_confidence(self):
        raw = '{"type": "bill", "confidence": "high"}'
        result = parse_classifier_response(raw)
        assert result["confidence"] == 0.0

    def test_parses_json_wrapped_in_text(self):
        raw = 'Here is the classification: {"type": "bill", "confidence": 0.85, "reason": "invoice"} thanks'
        result = parse_classifier_response(raw)
        assert result["type"] == "bill"
        assert result["confidence"] == 0.85

    def test_parses_indented_json(self):
        raw = '''{
            "type": "receipt",
            "confidence": 0.88,
            "reason": "Payment received"
        }'''
        result = parse_classifier_response(raw)
        assert result["type"] == "receipt"
        assert result["confidence"] == 0.88

    def test_empty_string(self):
        result = parse_classifier_response("")
        assert result["type"] == "neither"


class TestClassifyEmail:
    def test_raises_not_implemented_without_llm_call(self):
        with pytest.raises(NotImplementedError, match="No LLM callable"):
            classify_email("Subject", "Body", "model")

    def test_uses_injected_llm_call(self):
        def mock_llm(prompt: str, model: str) -> str:
            return '{"type": "bill", "confidence": 0.95, "reason": "invoice"}'

        result = classify_email("Subject", "Body", "model", llm_call=mock_llm)
        assert result["type"] == "bill"
        assert result["confidence"] == 0.95