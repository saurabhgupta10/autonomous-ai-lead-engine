"""
crawler.py
----------
Deep Website Discovery & Technical Audit Module.

Hardened security:
- DNS-level SSRF prevention blocking private, reserved, loopback, and cloud metadata ranges.
- Manual redirect hop validation to prevent SSRF through redirect chains.
- Strict response size limits (500 KB) and timeouts.
- Allowed protocols restricted to HTTP and HTTPS on standard ports (80, 443).
- Non-invasive inspection of mobile viewports, meta tags, forms, and booking signals.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from email_extractor import (
    clean_and_validate_email,
    discover_contact_links,
    extract_emails_from_html,
    prioritize_lead_email,
)

logger = logging.getLogger(__name__)

# Security parameters
MAX_CONTENT_BYTES = 500 * 1024  # 500 KB
REQUEST_TIMEOUT_SECONDS = 6
MAX_REDIRECTS = 3
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443, None}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeadEngineAudit/2.0 "
    "(+https://github.com/saurabhgupta10/autonomous-ai-lead-engine; respectful crawler)"
)

# Known booking widgets, platforms, and signature patterns
BOOKING_SIGNALS = [
    "calendly.com", "appointy.com", "opentable.com", "resy.com",
    "acuityscheduling.com", "mindbodyonline.com", "booksy.com", "fresha.com",
    "setmore.com", "simplybook.me", "timely.com", "vagaro.com",
    "tablecheck.com", "sevenrooms.com", "toasttab.com", "chownow.com",
    "booking", "reservation", "book-online", "appointment", "schedule-now"
]

# E-commerce and checkout platform signals
ECOMMERCE_SIGNALS = [
    "shopify.com", "myshopify", "woocommerce", "wp-content/plugins/woocommerce",
    "bigcommerce", "magento", "stripe.com", "checkout.stripe.com",
    "paypal.com", "add-to-cart", "shopping-cart"
]

# Private, link-local, loopback, and cloud metadata IP ranges blocked for SSRF
RESTRICTED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),       # Shared address space / CGNAT
    ipaddress.ip_network("127.0.0.0/8"),         # Loopback
    ipaddress.ip_network("169.254.0.0/16"),      # Link-local / Cloud metadata (AWS, GCP, Azure)
    ipaddress.ip_network("172.16.0.0/12"),       # RFC 1918 Private
    ipaddress.ip_network("192.0.0.0/24"),        # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),        # Documentation (TEST-NET-1)
    ipaddress.ip_network("192.168.0.0/16"),      # RFC 1918 Private
    ipaddress.ip_network("198.18.0.0/15"),       # Benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),     # Documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),      # Documentation (TEST-NET-3)
    ipaddress.ip_network("224.0.0.0/4"),         # Multicast
    ipaddress.ip_network("240.0.0.0/4"),         # Reserved
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    ipaddress.ip_network("::/128"),              # Unspecified
    ipaddress.ip_network("::1/128"),             # Loopback IPv6
    ipaddress.ip_network("fc00::/7"),            # Unique local IPv6
    ipaddress.ip_network("fe80::/10"),           # Link-local IPv6
]


def is_ssrf_safe_url(url: str) -> tuple[bool, str]:
    """
    Validate that target URL does not resolve to localhost, private, or reserved addresses.
    Re-resolves DNS and checks all returned IP socket addresses.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"Disallowed scheme '{parsed.scheme}'. Only http and https permitted."

    port = parsed.port
    if port not in ALLOWED_PORTS:
        return False, f"Disallowed port {port}. Only standard ports (80, 443) permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname"

    lower_host = hostname.lower()
    if lower_host in {"localhost", "localhost.localdomain", "broadcasthost", "metadata.google.internal"}:
        return False, "Internal hostnames are blocked"

    try:
        addr_info = socket.getaddrinfo(hostname, port or 443, proto=socket.IPPROTO_TCP)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            for restricted_net in RESTRICTED_IP_NETWORKS:
                if ip_obj in restricted_net:
                    return False, f"Resolved to restricted private/cloud IP: {ip_obj}"
    except socket.gaierror as dns_err:
        return False, f"DNS resolution failed: {dns_err}"
    except Exception as exc:
        return False, f"IP validation error: {exc}"

    return True, "Safe"


def audit_website(url: str | None) -> dict[str, Any]:
    """
    Perform a security-validated technical audit of a business homepage.
    Follows redirects manually while verifying each hop against SSRF rules.
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
            "emails_found": [],
            "primary_email": None,
            "email_source": None,
        }

    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"https://{clean_url}"

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
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

        current_url = clean_url
        final_response: requests.Response | None = None

        # Manual redirect following with SSRF check at EVERY hop
        for redirect_hop in range(MAX_REDIRECTS + 1):
            is_safe, reason = is_ssrf_safe_url(current_url)
            if not is_safe:
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
                    "observations": [f"SSRF guard blocked request to {current_url}: {reason}"],
                    "analysis_status": "failed",
                    "emails_found": [],
                    "primary_email": None,
                    "email_source": None,
                }

            resp = session.get(
                current_url,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
                stream=True,
                allow_redirects=False,
            )

            if resp.is_redirect or resp.status_code in {301, 302, 303, 307, 308}:
                location = resp.headers.get("Location")
                if not location:
                    break
                next_url = urljoin(current_url, location)
                current_url = next_url
                resp.close()
            else:
                final_response = resp
                break

        if final_response is None:
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
                "observations": ["Exceeded maximum redirects (potential redirect loop)."],
                "analysis_status": "completed",
                "emails_found": [],
                "primary_email": None,
                "email_source": None,
            }

        with final_response as response:
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
                    "emails_found": [],
                    "primary_email": None,
                    "email_source": None,
                }

            https_enabled = response.url.startswith("https://")
            if https_enabled:
                observations.append("Secure HTTPS connection verified.")
            else:
                observations.append("Website served over insecure HTTP.")

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

        # HTML Inspection
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

        # E-commerce detection
        for sig in ECOMMERCE_SIGNALS:
            if sig in html_lower:
                ecommerce_signals = True
                observations.append(f"E-commerce / checkout integration detected ({sig}).")
                break

        # ── Public Business Email Extraction ─────────────────────────────────
        candidate_emails: list[dict[str, str]] = extract_emails_from_html(raw_html, "homepage")

        # Inspect Contact / About subpages (up to 2 subpages to respect performance & bandwidth)
        contact_urls = discover_contact_links(clean_url, raw_html, max_links=2)
        for c_url in contact_urls:
            is_c_safe, _ = is_ssrf_safe_url(c_url)
            if not is_c_safe:
                continue
            try:
                sub_resp = session.get(
                    c_url,
                    headers=headers,
                    timeout=4,
                    stream=True,
                    allow_redirects=False,
                )
                if sub_resp.status_code == 200:
                    sub_chunks = []
                    sub_read = 0
                    for chunk in sub_resp.iter_content(chunk_size=16384):
                        sub_read += len(chunk)
                        sub_chunks.append(chunk)
                        if sub_read > MAX_CONTENT_BYTES:
                            break
                    sub_html = b"".join(sub_chunks).decode("utf-8", errors="replace")
                    sub_emails = extract_emails_from_html(sub_html, "contact_page")
                    candidate_emails.extend(sub_emails)

                    # Secondary check for contact forms on dedicated contact page
                    if not contact_form_found:
                        sub_soup = BeautifulSoup(sub_html, "html.parser")
                        for s_form in sub_soup.find_all("form"):
                            s_inputs = s_form.find_all(["input", "textarea", "button"])
                            s_has_submit = s_form.find(["button", "input"], attrs={"type": re.compile(r"submit", re.I)})
                            s_has_fields = any(inp.name == "textarea" or inp.get("type") in {"text", "email"} for inp in s_inputs)
                            if s_has_submit or s_has_fields:
                                contact_form_found = True
                                observations.append("Interactive contact form discovered on dedicated contact page.")
                                break
            except Exception as sub_err:
                logger.debug("Contact subpage crawl error for %s: %s", c_url, sub_err)

        primary_email, email_source = prioritize_lead_email(candidate_emails, clean_url)
        unique_emails = list(dict.fromkeys(e["email"] for e in candidate_emails if e.get("email")))

        if primary_email:
            observations.append(f"Public business email identified: {primary_email} ({email_source}).")
        else:
            observations.append("No public business email found on homepage or contact pages.")

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
            "emails_found": unique_emails,
            "primary_email": primary_email,
            "email_source": email_source,
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
            "emails_found": [],
            "primary_email": None,
            "email_source": None,
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
            "emails_found": [],
            "primary_email": None,
            "email_source": None,
        }
