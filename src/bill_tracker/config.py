"""Configuration loading with sensible defaults."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from bill_tracker.models import ReportConfig, ReportSection, Vendor, VendorStore

DEFAULT_CONFIG = {
    "gmail": {
        "account": "",
        "search_window": "1d",
        "bill_query": "bill OR invoice OR due OR statement",
        "receipt_query": 'receipt OR "payment confirmation" OR "thank you for your payment"',
    },
    "storage": {
        "data_dir": "./data",
    },
    "matching": {
        "amount_tolerance": 0.50,
        "confidence_threshold": 0.7,
    },
    "parser": {
        "model": "google/gemini-3-flash-preview",
        "max_tokens": 200,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str = "config.yaml") -> dict:
    """Load config from YAML file, filling in defaults for missing keys.

    Args:
        path: Path to config.yaml file.

    Returns:
        Merged config dictionary with all defaults applied.
    """
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        with open(path, "r") as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, user_config)
    return config


def load_vendors(path: str = "vendors.yaml") -> VendorStore:
    """Load vendors from YAML file.

    Args:
        path: Path to vendors.yaml file.

    Returns:
        VendorStore with known and discovered vendors.
    """
    if not os.path.exists(path):
        return VendorStore()

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    known = []
    raw_vendors = data.get("vendors", data.get("known", []))
    for v in raw_vendors:
        known.append(Vendor(**v))

    discovered = data.get("discovered", [])
    return VendorStore(known=known, discovered=discovered)


def load_report_config(path: str = "report.yaml") -> ReportConfig:
    """Load report configuration from YAML file.

    Args:
        path: Path to report.yaml file.

    Returns:
        ReportConfig with sections, output, and delivery settings.
    """
    if not os.path.exists(path):
        return ReportConfig()

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    sections = []
    for s in data.get("sections", []):
        sections.append(ReportSection(**s))

    return ReportConfig(
        sections=sections,
        output=data.get("output", ReportConfig.model_fields["output"].default),
        delivery=data.get("delivery", ReportConfig.model_fields["delivery"].default),
    )