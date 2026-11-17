"""
Backend unit tests for Lead Generation Engine.
Tests: imports, SSRF protection, website auditing, deduplication, 
       discovery schemas, industry configs, Gemini model fallback.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Backend'))
import unittest

class TestSSRFProtection(unittest.TestCase):
    def setUp(self):
        from crawler import is_ssrf_safe_url
        self.check = is_ssrf_safe_url

    def test_localhost_blocked(self):
        safe, _ = self.check("http://127.0.0.1:8000")
        self.assertFalse(safe)

    def test_localhost_hostname_blocked(self):
        safe, _ = self.check("http://localhost/admin")
        self.assertFalse(safe)

    def test_private_ip_blocked(self):
        safe, _ = self.check("http://192.168.1.1/router")
        self.assertFalse(safe)

    def test_ftp_scheme_blocked(self):
        safe, _ = self.check("ftp://example.com")
        self.assertFalse(safe)

    def test_public_url_allowed(self):
        from unittest.mock import patch
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("142.250.190.46", 443))]):
            safe, _ = self.check("https://www.google.com")
            self.assertTrue(safe)

    def test_dns_rebinding_blocked(self):
        from unittest.mock import patch
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
            safe, _ = self.check("https://evil-rebind.com")
            self.assertFalse(safe)

    def test_link_local_blocked(self):
        safe, _ = self.check("http://169.254.169.254/metadata")
        self.assertFalse(safe)


class TestWebsiteAuditing(unittest.TestCase):
    def setUp(self):
        from crawler import audit_website
        self.audit = audit_website

    def test_none_url(self):
        result = self.audit(None)
        self.assertEqual(result["website_status"], "missing")
        self.assertFalse(result["https_enabled"])

    def test_empty_url(self):
        result = self.audit("")
        self.assertEqual(result["website_status"], "missing")

    def test_invalid_domain(self):
        result = self.audit("https://this-domain-absolutely-does-not-exist-xyzxyz.invalid")
        self.assertIn(result["website_status"], ["broken", "unverified"])


class TestDeduplication(unittest.TestCase):
    def setUp(self):
        from sheet_manager import normalize_domain, normalize_business_key
        self.normalize_domain = normalize_domain
        self.normalize_key = normalize_business_key

    def test_domain_www_stripped(self):
        self.assertEqual(self.normalize_domain("https://www.JoesPizza.com/menu"), "joespizza.com")

    def test_domain_http_normalized(self):
        self.assertEqual(self.normalize_domain("http://joespizza.com"), "joespizza.com")

    def test_empty_domain(self):
        self.assertEqual(self.normalize_domain(""), "")

    def test_business_key_case_insensitive(self):
        k1 = self.normalize_key("Joe's Pizza & Pasta", "New York")
        k2 = self.normalize_key("JOES PIZZA  PASTA", "NEW YORK")
        self.assertEqual(k1, k2)


class TestDiscoverySchemas(unittest.TestCase):
    def test_discovery_query_validation(self):
        from discovery.discovery_schemas import DiscoveryQuery
        q = DiscoveryQuery(country="India", city="Mumbai", industry="Restaurants", limit=10)
        self.assertEqual(q.country, "India")
        self.assertEqual(q.limit, 10)

    def test_discovery_query_max_results_alias(self):
        from discovery.discovery_schemas import DiscoveryQuery
        q = DiscoveryQuery(country="UK", city="London", industry="Salons", max_results=15)
        self.assertEqual(q.limit, 15)

    def test_business_record_to_crm_dict(self):
        from discovery.discovery_schemas import BusinessRecord
        rec = BusinessRecord(
            provider_id="osm_node_123",
            business_name="Test Restaurant",
            business_category="Restaurants",
            country="India",
            city="Mumbai",
            website="https://test.com",
            source_url="https://www.openstreetmap.org/node/123",
        )
        d = rec.to_crm_dict()
        self.assertEqual(d["Business Name"], "Test Restaurant")
        self.assertEqual(d["Website"], "https://test.com")
        self.assertIn("Timestamp (UTC)", d)
        self.assertIn("Source URL", d)
        self.assertIn("Priority", d)


class TestIndustryConfig(unittest.TestCase):
    def test_restaurants(self):
        from discovery.discovery_validator import get_industry_config
        cfg = get_industry_config("Restaurants")
        self.assertIn("search_terms", cfg)
        self.assertIn("restaurant", cfg["search_terms"])

    def test_fitness(self):
        from discovery.discovery_validator import get_industry_config
        cfg = get_industry_config("Fitness")
        self.assertIn("gym", cfg["search_terms"])

    def test_logistics(self):
        from discovery.discovery_validator import get_industry_config
        cfg = get_industry_config("Logistics")
        self.assertIn("logistics", cfg["search_terms"])

    def test_salons(self):
        from discovery.discovery_validator import get_industry_config
        cfg = get_industry_config("Salons")
        self.assertIn("salon", cfg["search_terms"])

    def test_dentists(self):
        from discovery.discovery_validator import get_industry_config
        cfg = get_industry_config("Dentists")
        self.assertIn("dentist", cfg["search_terms"])

    def test_real_estate(self):
        from discovery.discovery_validator import get_industry_config
        cfg = get_industry_config("Real Estate")
        self.assertIn("real estate", cfg["search_terms"])


class TestGeminiCandidateModels(unittest.TestCase):
    def test_unique_candidate_models(self):
        from ai_filter import _get_unique_models
        models = _get_unique_models()
        self.assertGreater(len(models), 0)
        # All should be unique
        self.assertEqual(len(models), len(set(models)))

    def test_heuristic_fallback_assigned(self):
        from ai_filter import _assign_heuristic_opportunity
        from discovery.discovery_schemas import BusinessRecord
        rec = BusinessRecord(
            provider_id="test_1",
            business_name="No Website Business",
            business_category="Restaurants",
            country="India",
            city="Mumbai",
            website=None,
            source_url="https://www.openstreetmap.org/node/1",
        )
        rec.website_audit = {"website_status": "missing"}
        _assign_heuristic_opportunity(rec)
        self.assertEqual(rec.priority, "High")
        self.assertFalse(rec.is_ai_qualified)
        self.assertIn("[Heuristic Fallback]", rec.reason)
        self.assertTrue(rec.ai_evaluation.get("is_heuristic_fallback"))


class TestCountryNormalization(unittest.TestCase):
    def test_usa_aliases(self):
        from discovery.discovery_validator import normalize_country
        self.assertEqual(normalize_country("usa"), "United States")
        self.assertEqual(normalize_country("US"), "United States")
        self.assertEqual(normalize_country("united states"), "United States")

    def test_uk_aliases(self):
        from discovery.discovery_validator import normalize_country
        self.assertEqual(normalize_country("uk"), "United Kingdom")
        self.assertEqual(normalize_country("GB"), "United Kingdom")

    def test_india(self):
        from discovery.discovery_validator import normalize_country
        self.assertEqual(normalize_country("india"), "India")


class TestEmailExtraction(unittest.TestCase):
    def setUp(self):
        from email_extractor import (
            clean_and_validate_email,
            extract_emails_from_html,
            discover_contact_links,
            prioritize_lead_email,
        )
        self.clean_email = clean_and_validate_email
        self.extract = extract_emails_from_html
        self.contact_links = discover_contact_links
        self.prioritize = prioritize_lead_email

    def test_valid_emails(self):
        self.assertEqual(self.clean_email("info@joespizza.com"), "info@joespizza.com")
        self.assertEqual(self.clean_email("contact.us@sub.domain.co.uk"), "contact.us@sub.domain.co.uk")

    def test_mailto_extraction(self):
        html = '<a href="mailto:hello@bakery.com?subject=Inquiry">Email us</a>'
        res = self.extract(html, "test")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["email"], "hello@bakery.com")
        self.assertEqual(res[0]["source"], "test_mailto")

    def test_visible_text_extraction(self):
        html = '<p>Reach our support team at support@clinic.com during office hours.</p>'
        res = self.extract(html, "test")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["email"], "support@clinic.com")

    def test_false_positives_rejected(self):
        self.assertIsNone(self.clean_email("avatar@2x.png"))
        self.assertIsNone(self.clean_email("styles@main.css"))
        self.assertIsNone(self.clean_email("dummy@example.com"))
        self.assertIsNone(self.clean_email("info@sentry.io"))
        self.assertIsNone(self.clean_email("test@domain.com"))
        self.assertIsNone(self.clean_email("invalid-email-address"))

    def test_contact_page_discovery(self):
        html = '''
        <html><body>
          <nav>
            <a href="/about-us">About Us</a>
            <a href="/contact">Contact</a>
            <a href="https://external-social.com/share">Share</a>
          </nav>
        </body></html>
        '''
        links = self.contact_links("https://joespizza.com", html, max_links=2)
        self.assertIn("https://joespizza.com/about-us", links)
        self.assertIn("https://joespizza.com/contact", links)
        self.assertNotIn("https://external-social.com/share", links)

    def test_email_prioritization(self):
        candidates = [
            {"email": "generic@gmail.com", "source": "homepage_visible_text"},
            {"email": "contact@joespizza.com", "source": "contact_page_mailto"},
            {"email": "support@joespizza.com", "source": "contact_page_visible_text"},
        ]
        best_email, source = self.prioritize(candidates, "https://joespizza.com")
        self.assertEqual(best_email, "contact@joespizza.com")


class TestSheetsUpsertAndSync(unittest.TestCase):
    def test_sync_stats_unpacking(self):
        from sheet_manager import SyncStats
        stats = SyncStats({
            "records_inserted": 3,
            "records_updated": 2,
            "duplicates_skipped": 1,
            "records_failed": 0,
            "emails_added": 4,
            "emails_updated": 1,
        })
        synced, skipped = stats
        self.assertEqual(synced, 5)
        self.assertEqual(skipped, 1)
        self.assertEqual(stats["emails_added"], 4)
        self.assertEqual(stats["records_updated"], 2)

    def test_sync_upsert_logic_mocked(self):
        from unittest.mock import MagicMock, patch
        from discovery.discovery_schemas import BusinessRecord
        import sheet_manager

        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = [
            ["Timestamp (UTC)", "Business Name", "Country", "City", "Industry", "Website", "Email", "Phone", "Website Status", "Opportunity Type", "Priority", "AI Score", "AI Reasoning", "Evidence", "Source URL", "Discovery Provider", "Discovery Date", "Last Updated"],
            ["2026-11-10 10:00:00", "Existing Restaurant", "United States", "New York", "Restaurants", "https://existing.com", "", "", "working", "Website", "Medium", "50", "Reason", "Evidence", "https://osm.org/node/10", "OpenStreetMap (ODbL)", "2026-11-10", "2026-11-10"],
        ]

        with patch("sheet_manager.get_worksheet", return_value=mock_worksheet), \
             patch("sheet_manager._ensure_header", return_value=sheet_manager.RICH_HEADER_ROW):

            lead_existing_with_new_email = BusinessRecord(
                provider_id="osm_node_10",
                business_name="Existing Restaurant",
                business_category="Restaurants",
                country="United States",
                city="New York",
                website="https://existing.com",
                email="info@existing.com",
                phone="+1-555-0100",
                source_url="https://osm.org/node/10",
                priority="High",
                reason="Enriched with online booking gap",
            )
            lead_new = BusinessRecord(
                provider_id="osm_node_20",
                business_name="Brand New Bakery",
                business_category="Bakeries",
                country="United States",
                city="New York",
                website="https://newbakery.com",
                email="orders@newbakery.com",
                phone="+1-555-0200",
                source_url="https://osm.org/node/20",
                priority="High",
            )

            stats = sheet_manager.sync_discovered_leads_to_sheets([lead_existing_with_new_email, lead_new])

            self.assertEqual(stats["records_updated"], 1, "Existing row should be updated")
            self.assertEqual(stats["records_inserted"], 1, "New business should be inserted")
            self.assertEqual(stats["emails_added"], 2, "Both leads contributed emails")
            mock_worksheet.batch_update.assert_called_once()
            mock_worksheet.append_rows.assert_called_once()

    def test_preserve_existing_email(self):
        from unittest.mock import MagicMock, patch
        from discovery.discovery_schemas import BusinessRecord
        import sheet_manager

        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = [
            ["Timestamp (UTC)", "Business Name", "Country", "City", "Industry", "Website", "Email", "Phone", "Website Status", "Opportunity Type", "Priority", "AI Score", "AI Reasoning", "Evidence", "Source URL", "Discovery Provider", "Discovery Date", "Last Updated"],
            ["2026-11-10 10:00:00", "Cafe Alpha", "United States", "New York", "Cafes", "https://cafealpha.com", "original@cafealpha.com", "+1-555-1111", "working", "Website", "Medium", "50", "Reason", "Evidence", "https://osm.org/node/99", "OpenStreetMap (ODbL)", "2026-11-10", "2026-11-10"],
        ]

        with patch("sheet_manager.get_worksheet", return_value=mock_worksheet), \
             patch("sheet_manager._ensure_header", return_value=sheet_manager.RICH_HEADER_ROW):

            # Lead with empty email should NOT wipe out the original email
            lead_no_email = BusinessRecord(
                provider_id="osm_node_99",
                business_name="Cafe Alpha",
                business_category="Cafes",
                country="United States",
                city="New York",
                website="https://cafealpha.com",
                email=None,
                source_url="https://osm.org/node/99",
            )

            stats = sheet_manager.sync_discovered_leads_to_sheets([lead_no_email])
            self.assertEqual(stats["duplicates_skipped"], 1, "Unchanged record should count as duplicate skipped")
            mock_worksheet.batch_update.assert_not_called()


class TestGeminiJSONParsing(unittest.TestCase):
    def test_json_array_parser_with_fences(self):
        from ai_filter import _parse_gemini_json_array
        raw = '```json\n[{"index": 0, "priority": "High", "score": 90}]\n```'
        parsed = _parse_gemini_json_array(raw)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["priority"], "High")

    def test_json_array_parser_with_surrounding_text(self):
        from ai_filter import _parse_gemini_json_array
        raw = 'Here is the analysis:\n[{"index": 0, "priority": "Medium"}]\nHope this helps!'
        parsed = _parse_gemini_json_array(raw)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["priority"], "Medium")


class TestFastAPIEndpoints(unittest.TestCase):
    def test_health_endpoint(self):
        from api import health
        data = health()
        self.assertEqual(data["status"], "ok")
        self.assertIn("integrations", data)
        self.assertIn("gemini", data["integrations"])
        self.assertIn("google_sheets", data["integrations"])

    def test_discovery_status_endpoint(self):
        from api import get_discovery_status
        data = get_discovery_status()
        self.assertIn("status", data)

    def test_discovery_results_endpoint(self):
        from api import get_discovery_results
        data = get_discovery_results()
        self.assertEqual(data["status"], "ok")
        self.assertIn("results", data)

    def test_scan_status_endpoint(self):
        from api import scan_status
        data = scan_status()
        self.assertIn("status", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
