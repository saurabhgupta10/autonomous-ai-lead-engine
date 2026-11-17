"""
test_phase5.py
--------------
Automated test suite for Phase 5 Autonomous Business Discovery & Website Intelligence.
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import unittest
from unittest.mock import patch
from discovery.discovery_schemas import DiscoveryQuery
from discovery.overpass_provider import OverpassDiscoveryProvider
from crawler import audit_website, is_ssrf_safe_url
from discovery.discovery_service import DiscoveryService
from sheet_manager import normalize_domain, normalize_business_key


class TestWebsiteAuditing(unittest.TestCase):
    def test_ssrf_protection(self):
        # Localhost and private IPs should be blocked
        safe, _ = is_ssrf_safe_url("http://127.0.0.1:8000")
        self.assertFalse(safe)

        safe, _ = is_ssrf_safe_url("http://localhost/admin")
        self.assertFalse(safe)

        safe, _ = is_ssrf_safe_url("http://192.168.1.1/router")
        self.assertFalse(safe)

        safe, _ = is_ssrf_safe_url("ftp://example.com")
        self.assertFalse(safe)

        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("142.250.190.46", 443))]):
            safe, _ = is_ssrf_safe_url("https://www.google.com")
            self.assertTrue(safe)

    def test_missing_website(self):
        result = audit_website(None)
        self.assertEqual(result["website_status"], "missing")
        self.assertFalse(result["https_enabled"])

        result_empty = audit_website("")
        self.assertEqual(result_empty["website_status"], "missing")

    def test_broken_website(self):
        # 192.0.2.1 is TEST-NET-1 (non-routable/reserved) -> SSRF guard or connection error
        result = audit_website("https://this-is-a-completely-invalid-domain-123456789.com")
        self.assertIn(result["website_status"], ["broken", "unverified"])

    def test_working_website(self):
        result = audit_website("https://example.com")
        self.assertEqual(result["website_status"], "working")
        self.assertTrue(result["https_enabled"])
        self.assertIsNotNone(result["page_title"])


class TestDeduplication(unittest.TestCase):
    def test_domain_normalization(self):
        self.assertEqual(normalize_domain("https://www.JoesPizza.com/menu"), "joespizza.com")
        self.assertEqual(normalize_domain("http://joespizza.com"), "joespizza.com")
        self.assertEqual(normalize_domain(""), "")

    def test_business_key_normalization(self):
        self.assertEqual(
            normalize_business_key("Joe's Pizza & Pasta", "New York"),
            normalize_business_key("joes pizza  pasta", "new york "),
        )


class TestRealBusinessDiscovery(unittest.TestCase):
    def test_real_discovery_restaurants_ny(self):
        provider = OverpassDiscoveryProvider()
        q = DiscoveryQuery(country="USA", city="New York", industry="Restaurants", limit=5)
        leads = provider.discover_businesses(q)

        self.assertGreater(len(leads), 0, "Should discover real businesses in New York")
        for lead in leads:
            self.assertTrue(lead.business_name, "Business must have a name")
            self.assertTrue(lead.source_url.startswith("https://www.openstreetmap.org/"), "Must have verifiable OSM source URL")
            self.assertIn("OpenStreetMap", lead.discovery_provider)
            self.assertEqual(lead.country, "United States")

    def test_real_discovery_salons_sydney(self):
        provider = OverpassDiscoveryProvider()
        q = DiscoveryQuery(country="Australia", city="Sydney", industry="Salons", limit=5)
        leads = provider.discover_businesses(q)

        self.assertGreater(len(leads), 0, "Should discover real businesses in Sydney")
        for lead in leads:
            self.assertTrue(lead.business_name)
            self.assertEqual(lead.country, "Australia")


if __name__ == "__main__":
    unittest.main()
