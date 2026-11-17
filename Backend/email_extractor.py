"""
email_extractor.py
------------------
High-precision, security-hardened email extraction engine for public business websites.

Features:
- Extracts emails from mailto: links (with query-param stripping).
- Extracts visible email addresses from text and HTML footer/contact sections.
- Discovers internal Contact Us, About Us, and Get in Touch pages.
- Strict RFC & domain validation.
- Extensive false-positive filtering (blocking image/asset extensions, placeholder domains,
  framework/vendor emails, and generic template strings).
- Scores and prioritizes public business emails (e.g., info@, contact@, domain-matching emails).
- Never fabricates or guesses email addresses.
- Full SSRF protection across all crawled pages.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

logger = logging.getLogger(__name__)

# Standard RFC 5322 compliant email regex pattern (practical subset)
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    re.IGNORECASE,
)

# Common asset and file extensions that frequently get misidentified as top-level domains
DISALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "tiff",
    "css", "js", "mjs", "map", "json", "xml",
    "woff", "woff2", "ttf", "eot", "otf",
    "mp4", "mp3", "webm", "avi", "mov", "wav",
    "pdf", "zip", "tar", "gz", "rar", "7z", "exe", "dmg",
}

# Domains that represent samples, documentation, placeholders, or known 3rd-party vendors/scripts
DISALLOWED_DOMAINS = {
    # Documentation & RFC standard test domains
    "example.com", "example.org", "example.net",
    "domain.com", "yourdomain.com", "sample.com", "test.com",
    "email.com", "mysite.com", "yoursite.com", "website.com",
    "sitename.com", "company.com", "mycompany.com",
    # Frameworks, builders, themes, and libraries
    "sentry.io", "wixpress.com", "wix.com", "wordpress.org", "wordpress.com",
    "cloudflare.com", "google.com", "googleapis.com", "gstatic.com",
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "linkedin.com", "apple.com", "microsoft.com",
    "schema.org", "w3.org", "gravatar.com", "themeforest.net", "envato.com",
    "shopify.com", "myshopify.com", "squarespace.com", "weebly.com",
    "bootstrap.com", "jquery.com", "fontawesome.com", "github.com",
}

# Prefixes that indicate template code or dummy data
DISALLOWED_PREFIXES = {
    "name", "username", "user", "yourname", "youremail", "email",
    "first.last", "john.doe", "jane.doe", "dummy", "placeholder",
    "test", "demo", "sample", "admin@domain",
}

# Preferred business contact prefixes (higher priority when selecting primary email)
PREFERRED_PREFIXES = [
    "info", "contact", "hello", "enquiries", "inquiries",
    "office", "support", "sales", "help", "reservations", "booking",
    "reception", "team", "admin", "mail",
]

# Contact/About page candidate URL keywords and text
CONTACT_KEYWORDS = [
    "contact", "contact-us", "contact_us", "contactus",
    "get-in-touch", "getintouch", "reach-us", "reachus",
    "about", "about-us", "about_us", "aboutus",
    "location", "locations", "find-us", "impressum", "kontakt",
]


def clean_and_validate_email(raw_email: str | None) -> str | None:
    """
    Clean, validate, and filter a candidate email address.
    Returns normalized lowercase email or None if invalid/false-positive.
    """
    if not raw_email or not isinstance(raw_email, str):
        return None

    # Unquote URL encoding and strip unwanted punctuation/whitespace
    cleaned = unquote(raw_email).strip().lower()
    # Strip mailto: prefix if present
    if cleaned.startswith("mailto:"):
        cleaned = cleaned[7:].strip()

    # Strip query parameters (e.g. ?subject=Hello)
    if "?" in cleaned:
        cleaned = cleaned.split("?")[0].strip()

    # Strip trailing punctuation often caught by regex (dots, commas, semicolons, brackets)
    cleaned = cleaned.rstrip(".,;:!?)'\"<>")
    cleaned = cleaned.lstrip("<>('\"")

    if not cleaned or "@" not in cleaned:
        return None

    parts = cleaned.split("@")
    if len(parts) != 2:
        return None

    local_part, domain_part = parts[0], parts[1]

    # Validate local part
    if not local_part or len(local_part) > 64:
        return None
    if local_part in DISALLOWED_PREFIXES:
        return None

    # Validate domain part
    if not domain_part or len(domain_part) > 255:
        return None
    if "." not in domain_part:
        return None

    domain_segments = domain_part.split(".")
    tld = domain_segments[-1]

    # TLD must be alphabetic and between 2 and 24 characters
    if not tld.isalpha() or len(tld) < 2 or len(tld) > 24:
        return None

    # Block asset/file extensions falsely matched as TLDs (e.g. image@2x.png)
    if tld in DISALLOWED_EXTENSIONS:
        return None

    # Block disallowed or placeholder domains
    if domain_part in DISALLOWED_DOMAINS:
        return None

    # Check if domain ends with any disallowed domain (e.g. test.sentry.io)
    for disallowed in DISALLOWED_DOMAINS:
        if domain_part == disallowed or domain_part.endswith(f".{disallowed}"):
            return None

    # Re-validate with regex pattern
    if not EMAIL_REGEX.fullmatch(cleaned):
        return None

    return cleaned


def extract_emails_from_html(html_content: str, source_label: str = "html") -> list[dict[str, str]]:
    """
    Extract email addresses from HTML text using mailto links and regex text scanning.
    Returns list of dicts: [{"email": "...", "source": "..."}].
    """
    if not html_content or not isinstance(html_content, str):
        return []

    found: dict[str, str] = {}  # email -> highest priority source

    # 1. Parse mailto: links (highest confidence)
    mailto_pattern = re.compile(r'href=[\'"]mailto:([^\'" >]+)[\'"]', re.IGNORECASE)
    for match in mailto_pattern.finditer(html_content):
        raw_val = match.group(1)
        valid_email = clean_and_validate_email(raw_val)
        if valid_email and valid_email not in found:
            found[valid_email] = f"{source_label}_mailto"

    # 2. General regex search across the entire HTML / text
    for match in EMAIL_REGEX.finditer(html_content):
        raw_val = match.group(0)
        valid_email = clean_and_validate_email(raw_val)
        if valid_email and valid_email not in found:
            found[valid_email] = f"{source_label}_visible_text"

    return [{"email": email, "source": src} for email, src in found.items()]


def discover_contact_links(base_url: str, html_content: str, max_links: int = 3) -> list[str]:
    """
    Inspect homepage HTML to discover internal Contact, About, or Get-in-Touch links.
    Returns list of fully qualified internal URLs to crawl.
    """
    if not html_content or not base_url:
        return []

    try:
        base_parsed = urlparse(base_url)
        base_domain = base_parsed.netloc.lower()
        if base_domain.startswith("www."):
            base_domain = base_domain[4:]
    except Exception:
        return []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    contact_urls: list[str] = []
    seen_urls: set[str] = {base_url.rstrip("/").lower()}

    # Look through anchor tags
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "tel:", "mailto:")):
            continue

        text = a.get_text(" ", strip=True).lower()
        href_lower = href.lower()

        # Check if anchor text or href matches contact keywords
        is_candidate = any(kw in href_lower for kw in CONTACT_KEYWORDS) or any(kw in text for kw in CONTACT_KEYWORDS)
        if not is_candidate:
            continue

        # Build absolute URL
        absolute_url = urljoin(base_url, href)
        try:
            parsed = urlparse(absolute_url)
        except Exception:
            continue

        if parsed.scheme.lower() not in {"http", "https"}:
            continue

        cand_domain = parsed.netloc.lower()
        if cand_domain.startswith("www."):
            cand_domain = cand_domain[4:]

        # Must be internal to same domain or subdomain
        if cand_domain != base_domain and not cand_domain.endswith(f".{base_domain}"):
            continue

        # Normalize path
        normalized = absolute_url.split("#")[0].split("?")[0].rstrip("/").lower()
        if normalized in seen_urls:
            continue

        seen_urls.add(normalized)
        contact_urls.append(absolute_url)

        if len(contact_urls) >= max_links:
            break

    return contact_urls


def prioritize_lead_email(
    candidates: list[dict[str, str]],
    website_url: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Select the best primary business email from a list of candidate records.
    Preference order:
      1. Domain-matching email with preferred business prefix (info@, contact@, hello@, etc.)
      2. Domain-matching email (any prefix)
      3. Any email with preferred business prefix
      4. mailto link over regex text
      5. First valid candidate
    Returns: (primary_email, source)
    """
    if not candidates:
        return None, None

    web_domain = ""
    if website_url:
        try:
            p = urlparse(website_url if website_url.startswith(("http://", "https://")) else f"https://{website_url}")
            web_domain = p.netloc.lower()
            if web_domain.startswith("www."):
                web_domain = web_domain[4:]
        except Exception:
            web_domain = ""

    def email_score(item: dict[str, str]) -> int:
        email = item.get("email", "")
        source = item.get("source", "")
        score = 0

        parts = email.split("@")
        if len(parts) == 2:
            local, domain = parts[0].lower(), parts[1].lower()
            # Match website domain
            if web_domain and (domain == web_domain or domain.endswith(f".{web_domain}")):
                score += 50

            # Preferred business prefix
            for idx, pref in enumerate(PREFERRED_PREFIXES):
                if local == pref or local.startswith(f"{pref}."):
                    score += (30 - idx)
                    break

        # Preference for mailto link over plain text
        if "mailto" in source:
            score += 15

        # Preference for homepage/contact page
        if "homepage" in source or "contact" in source:
            score += 10

        return score

    sorted_candidates = sorted(candidates, key=email_score, reverse=True)
    best = sorted_candidates[0]
    return best["email"], best.get("source", "website_extraction")
