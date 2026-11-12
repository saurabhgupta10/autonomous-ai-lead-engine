"""
crawler.py
----------
Deep Website Discovery & Technical Audit Module.

Conducts non-invasive, evidence-based technical audits of discovered business homepages.
Strictly enforces SSRF protection, strict timeouts, response-size limits, and protocol constraints.
Does NOT execute automated penetration tests or bypass access controls.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Security parameters
MAX_CONTENT_BYTES = 500 * 1024  # 500 KB limit for homepage HTML
REQUEST_TIMEOUT_SECONDS = 6
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeadEngineAudit/2.0 (respectful bot; +https://leadengine.local)"

# Known booking widgets, scripts, platforms, or embed patterns
BOOKING_SIGNALS = [
    "calendly.com", "appointy.com", "opentable.com", "resy.com",
    "acuityscheduling.com", "mindbodyonline.com", "booksy.com", "fresha.com",
    "setmore.com", "simplybook.me", "timely.com", "vagaro.com",
    "tablecheck.com", "sevenrooms.com", "toasttab.com", "chownow.com",
    "booking", "reservation", "book-online", "appointment", "schedule-now"
]

# E-commerce and payment indicators
ECOMMERCE_SIGNALS = [
    "shopify.com", "myshopify", "woocommerce", "wp-content/plugins/woocommerce",
    "bigcommerce", "magento", "stripe.com", "checkout.stripe.com",
    "paypal.com", "add-to-cart", "shopping-cart"
]

# Private IP networks blocked for SSRF prevention
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_ssrf_safe_url(url: str) -> tuple[bool, str]:
    """
    Validate that target URL does not resolve to localhost, private, or reserved addresses.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"Disallowed scheme: {parsed.scheme}"

    if parsed.port and parsed.port not in ALLOWED_PORTS:
        return False, f"Disallowed port: {parsed.port}"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname"

    if hostname.lower() in {"localhost", "localhost.localdomain", "broadcasthost"}:
        return False, "Localhost addresses are blocked"

    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            for private_net in PRIVATE_IP_RANGES:
                if ip_obj in private_net:
                    return False, f"Resolved to restricted private IP: {ip_obj}"
    except socket.gaierror as dns_err:
        return False, f"DNS resolution failed: {dns_err}"
    except Exception as exc:
        return False, f"IP validation error: {exc}"

    return True, "Safe"


def audit_website(url: str | None) -> dict[str, Any]:
    """
    Perform a complete security-validated technical audit of a business homepage.
    """
    if not url or url.strip().lower() in {"none", "n/a", "null", ""}:
        return {
            "website_status": "missing",
            "https_enabled": False,
            "mobile_viewport": False,
            "contact_form_found": False,
            "booking_functionality_found": False,
            "metadata_complete": False,
            "page_title": None,
            "meta_description": None,
            "ecommerce_signals": False,
            "observations": ["No discoverable website URL registered."],
            "analysis_status": "completed",
        }

    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"https://{clean_url}"

    # 1. SSRF and DNS check
    is_safe, reason = is_ssrf_safe_url(clean_url)
    if not is_safe:
        return {
            "website_status": "unverified",
            "https_enabled": clean_url.startswith("https://"),
            "mobile_viewport": False,
            "contact_form_found": False,
            "booking_functionality_found": False,
            "metadata_complete": False,
            "page_title": None,
            "meta_description": None,
            "ecommerce_signals": False,
            "observations": [f"Security validation blocked request: {reason}"],
            "analysis_status": "failed",
        }

    observations: list[str] = []
    https_enabled = clean_url.startswith("https://")
    mobile_viewport = False
    contact_form_found = False
    booking_functionality_found = False
    ecommerce_signals = False
    metadata_complete = False
    page_title = None
    meta_description = None

    try:
        session = requests.Session()
        session.max_redirects = 3
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

        # Stream request to enforce size limits
        with session.get(
            clean_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            stream=True,
            allow_redirects=True,
        ) as response:
            # Recheck destination URL after redirects
            dest_safe, dest_reason = is_ssrf_safe_url(response.url)
            if not dest_safe:
                return {
                    "website_status": "unverified",
                    "https_enabled": False,
                    "mobile_viewport": False,
                    "contact_form_found": False,
                    "booking_functionality_found": False,
                    "metadata_complete": False,
                    "page_title": None,
                    "meta_description": None,
                    "ecommerce_signals": False,
                    "observations": [f"Redirect destination blocked: {dest_reason}"],
                    "analysis_status": "failed",
                }

            if response.status_code >= 400:
                observations.append(f"HTTP error status {response.status_code} returned.")
                return {
                    "website_status": "broken",
                    "https_enabled": response.url.startswith("https://"),
                    "mobile_viewport": False,
                    "contact_form_found": False,
                    "booking_functionality_found": False,
                    "metadata_complete": False,
                    "page_title": None,
                    "meta_description": None,
                    "ecommerce_signals": False,
                    "observations": observations,
                    "analysis_status": "completed",
                }

            https_enabled = response.url.startswith("https://")
            if https_enabled:
                observations.append("Secure HTTPS connection verified.")
            else:
                observations.append("Website served over insecure HTTP (no HTTPS redirect).")

            # Read content up to byte limit
            content_chunks = []
            total_read = 0
            for chunk in response.iter_content(chunk_size=16384):
                total_read += len(chunk)
                content_chunks.append(chunk)
                if total_read > MAX_CONTENT_BYTES:
                    observations.append("HTML response truncated at 500 KB limit.")
                    break

            raw_html = b"".join(content_chunks).decode("utf-8", errors="replace")

        # 2. Deep HTML Inspection
        soup = BeautifulSoup(raw_html, "html.parser")

        # Page Title
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            page_title = title_tag.string.strip()
            observations.append(f"Page title captured: '{page_title[:60]}'")
        else:
            observations.append("Missing <title> tag on homepage.")

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if meta_desc and meta_desc.get("content"):
            meta_description = meta_desc["content"].strip()
            metadata_complete = bool(page_title and meta_description)
            observations.append("Search meta description present.")
        else:
            observations.append("Missing meta description (SEO gap).")

        # Viewport configuration
        viewport_meta = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        if viewport_meta and viewport_meta.get("content"):
            mobile_viewport = True
            observations.append("Mobile viewport meta tag configured.")
        else:
            observations.append("Missing mobile viewport tag (poor mobile experience).")

        # Contact form detection
        forms = soup.find_all("form")
        for form in forms:
            inputs = form.find_all(["input", "textarea", "button"])
            has_submit = form.find(["button", "input"], attrs={"type": re.compile(r"submit", re.I)})
            has_text_fields = any(inp.name == "textarea" or inp.get("type") in {"text", "email"} for inp in inputs)
            if has_submit or has_text_fields:
                contact_form_found = True
                break

        if contact_form_found:
            observations.append("Interactive contact/enquiry form detected.")
        else:
            observations.append("No visible contact enquiry form on homepage.")

        # Booking functionality detection
        html_lower = raw_html.lower()
        for signal in BOOKING_SIGNALS:
            if signal in html_lower:
                booking_functionality_found = True
                observations.append(f"Booking/reservation system signal detected ({signal}).")
                break

        if not booking_functionality_found:
            observations.append("No online appointment or table reservation widget detected.")

        # E-commerce and payment signals
        for sig in ECOMMERCE_SIGNALS:
            if sig in html_lower:
                ecommerce_signals = True
                observations.append(f"E-commerce / checkout integration detected ({sig}).")
                break

        return {
            "website_status": "working",
            "https_enabled": https_enabled,
            "mobile_viewport": mobile_viewport,
            "contact_form_found": contact_form_found,
            "booking_functionality_found": booking_functionality_found,
            "metadata_complete": metadata_complete,
            "page_title": page_title,
            "meta_description": meta_description,
            "ecommerce_signals": ecommerce_signals,
            "observations": observations,
            "analysis_status": "completed",
        }

    except requests.exceptions.Timeout:
        observations.append(f"Connection timed out after {REQUEST_TIMEOUT_SECONDS}s.")
        return {
            "website_status": "broken",
            "https_enabled": https_enabled,
            "mobile_viewport": False,
            "contact_form_found": False,
            "booking_functionality_found": False,
            "metadata_complete": False,
            "page_title": None,
            "meta_description": None,
            "ecommerce_signals": False,
            "observations": observations,
            "analysis_status": "completed",
        }
    except Exception as exc:
        observations.append(f"Crawl error: {type(exc).__name__} - {str(exc)[:100]}")
        return {
            "website_status": "broken",
            "https_enabled": https_enabled,
            "mobile_viewport": False,
            "contact_form_found": False,
            "booking_functionality_found": False,
            "metadata_complete": False,
            "page_title": None,
            "meta_description": None,
            "ecommerce_signals": False,
            "observations": observations,
            "analysis_status": "failed",
        }
