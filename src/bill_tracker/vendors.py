"""Vendor matching, discovery, and persistence."""

from __future__ import annotations

import yaml

from bill_tracker.models import Vendor, VendorStore


def match_vendor(name: str, vendors: VendorStore) -> Vendor | None:
    """Match an extracted vendor name against known vendors.

    Checks against vendor.name and all vendor.patterns (case-insensitive).

    Args:
        name: The vendor name extracted from an email.
        vendors: VendorStore containing known vendors.

    Returns:
        Matching Vendor or None.
    """
    name_lower = name.strip().lower()
    for vendor in vendors.known:
        candidates = [vendor.name.lower()] + [p.lower() for p in vendor.patterns]
        if name_lower in candidates:
            return vendor
        # Also check if any candidate is a substring of name or vice versa
        for candidate in candidates:
            if candidate in name_lower or name_lower in candidate:
                return vendor
    return None


def discover_vendor(
    name: str,
    vendors: VendorStore,
    amount: float,
    currency: str,
) -> None:
    """Add a vendor to the discovered list if not already known or discovered.

    Args:
        name: Vendor name to discover.
        vendors: VendorStore to modify (mutated in place).
        amount: Sample amount for the vendor.
        currency: Sample currency for the vendor.
    """
    name = name.strip()
    # Skip if already known
    if match_vendor(name, vendors) is not None:
        return

    # Skip if already discovered
    for d in vendors.discovered:
        if d.get("name", "").lower() == name.lower():
            d["occurrences"] = d.get("occurrences", 0) + 1
            return

    vendors.discovered.append({
        "name": name,
        "first_seen": "",  # caller should set this
        "occurrences": 1,
        "sample_amount": amount,
        "sample_currency": currency,
    })


def save_vendors(path: str, vendors: VendorStore) -> None:
    """Write VendorStore to a YAML file.

    Args:
        path: Path to write vendors.yaml.
        vendors: VendorStore to persist.
    """
    data = {
        "vendors": [v.model_dump() for v in vendors.known],
        "discovered": vendors.discovered,
    }
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)