"""Tests for vendor matching and discovery."""

from bill_tracker.models import Vendor, VendorStore
from bill_tracker.vendors import match_vendor, discover_vendor


class TestMatchVendor:
    def test_exact_name_match(self):
        vendors = VendorStore(known=[Vendor(name="Enbridge Gas")])
        result = match_vendor("Enbridge Gas", vendors)
        assert result is not None
        assert result.name == "Enbridge Gas"

    def test_case_insensitive_match(self):
        vendors = VendorStore(known=[Vendor(name="Enbridge Gas")])
        result = match_vendor("enbridge gas", vendors)
        assert result is not None
        assert result.name == "Enbridge Gas"

    def test_pattern_match(self):
        vendors = VendorStore(
            known=[Vendor(name="Enbridge Gas", patterns=["enbridge", "enbridge gas"])]
        )
        result = match_vendor("enbridge", vendors)
        assert result is not None
        assert result.name == "Enbridge Gas"

    def test_substring_match(self):
        vendors = VendorStore(known=[Vendor(name="Enbridge Gas")])
        result = match_vendor("Enbridge", vendors)
        assert result is not None

    def test_no_match(self):
        vendors = VendorStore(known=[Vendor(name="Enbridge Gas")])
        result = match_vendor("Hydro Ottawa", vendors)
        assert result is None

    def test_empty_vendors(self):
        vendors = VendorStore()
        result = match_vendor("Anything", vendors)
        assert result is None

    def test_multiple_vendors_finds_first(self):
        v1 = Vendor(name="Enbridge Gas", patterns=["enbridge"])
        v2 = Vendor(name="NPEI", patterns=["npei", "niagara"])
        vendors = VendorStore(known=[v1, v2])
        result = match_vendor("npei", vendors)
        assert result is not None
        assert result.name == "NPEI"


class TestDiscoverVendor:
    def test_discovers_new_vendor(self):
        vendors = VendorStore()
        discover_vendor("New Vendor Inc", vendors, 50.0, "CAD")
        assert len(vendors.discovered) == 1
        assert vendors.discovered[0]["name"] == "New Vendor Inc"
        assert vendors.discovered[0]["sample_amount"] == 50.0
        assert vendors.discovered[0]["sample_currency"] == "CAD"
        assert vendors.discovered[0]["occurrences"] == 1

    def test_does_not_duplicate_discovered(self):
        vendors = VendorStore(
            discovered=[{
                "name": "Already Seen",
                "first_seen": "",
                "occurrences": 1,
                "sample_amount": 100.0,
                "sample_currency": "USD",
            }]
        )
        discover_vendor("Already Seen", vendors, 200.0, "CAD")
        assert len(vendors.discovered) == 1
        assert vendors.discovered[0]["occurrences"] == 2

    def test_case_insensitive_discovery_dedup(self):
        vendors = VendorStore(
            discovered=[{
                "name": "SomeVendor",
                "first_seen": "",
                "occurrences": 1,
                "sample_amount": 10.0,
                "sample_currency": "CAD",
            }]
        )
        discover_vendor("somevendor", vendors, 20.0, "CAD")
        assert len(vendors.discovered) == 1
        assert vendors.discovered[0]["occurrences"] == 2

    def test_does_not_discover_known_vendor(self):
        vendors = VendorStore(known=[Vendor(name="KnownCo", patterns=["known"])])
        discover_vendor("knownco", vendors, 100.0, "CAD")
        assert len(vendors.discovered) == 0