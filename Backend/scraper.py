"""
scraper.py
----------
Fetch HTML from one or more URLs (or local file:// paths) and extract
mock business records: company name, website, and email.

Designed for a controlled mock directory page (see data/mock_leads.html)
and other simple tables that use the same CSS classes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.request import url2pathname

import requests
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def scrape_businesses(urls: Iterable[str]) -> list[dict]:
    """
    Scrape every URL and return a de-duplicated list of business dicts.

    Each record looks like:
        {"company_name": "...", "website": "...", "email": "...", "notes": "..."}
    """
    leads: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for url in urls:
        html = _load_html(url)
        for row in _parse_directory(html):
            key = (row["company_name"].lower(), row["email"].lower())
            if key in seen:
                continue
            seen.add(key)
            leads.append(row)

    return leads


def _load_html(url: str) -> str:
    """Load HTML from http(s) or a local file:// URI / filesystem path."""
    parsed = urlparse(url)

    if parsed.scheme in {"http", "https"}:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.text

    if parsed.scheme == "file":
        path = Path(url2pathname(parsed.path))
        return path.read_text(encoding="utf-8")

    # Allow passing a relative/absolute path instead of a URL.
    path = Path(url)
    if path.exists():
        return path.read_text(encoding="utf-8")

    raise ValueError(f"Unsupported source (not a URL or existing file): {url}")


def _parse_directory(html: str) -> list[dict]:
    """
    Extract businesses from:
      1) rows with class="business" (preferred mock format)
      2) fallback: any table whose headers include Company / Website / Email
    """
    soup = BeautifulSoup(html, "html.parser")
    records = [_row_to_record(row) for row in soup.select("tr.business")]
    records = [r for r in records if r["company_name"]]

    if records:
        return records

    return _parse_generic_tables(soup)


def _row_to_record(row) -> dict:
    company = _text(row.select_one(".company"))
    website = _href_or_text(row.select_one(".website"))
    email = _email_from(_text(row.select_one(".email")))
    notes = _text(row.select_one("td.notes")) or _nth_cell(row, 3)
    return {
        "company_name": company,
        "website": website,
        "email": email,
        "notes": notes,
    }


def _parse_generic_tables(soup: BeautifulSoup) -> list[dict]:
    results: list[dict] = []

    for table in soup.find_all("table"):
        headers = [_normalize(_text(th)) for th in table.find_all("th")]
        if not headers:
            continue

        name_idx = _find_col(headers, ("company", "name", "business"))
        site_idx = _find_col(headers, ("website", "url", "site"))
        email_idx = _find_col(headers, ("email", "e-mail", "mail"))
        notes_idx = _find_col(headers, ("notes", "description", "about"))

        if name_idx is None:
            continue

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            name = _text(cells[name_idx]) if name_idx < len(cells) else ""
            if not name:
                continue
            website = ""
            if site_idx is not None and site_idx < len(cells):
                website = _href_or_text(cells[site_idx])
            email = ""
            if email_idx is not None and email_idx < len(cells):
                email = _email_from(_text(cells[email_idx]))
            notes = ""
            if notes_idx is not None and notes_idx < len(cells):
                notes = _text(cells[notes_idx])
            results.append(
                {
                    "company_name": name,
                    "website": website,
                    "email": email,
                    "notes": notes,
                }
            )

    return results


def _find_col(headers: list[str], keywords: tuple[str, ...]) -> int | None:
    for i, header in enumerate(headers):
        if any(keyword in header for keyword in keywords):
            return i
    return None


def _nth_cell(row, index: int) -> str:
    cells = row.find_all("td")
    if index < len(cells):
        return _text(cells[index])
    return ""


def _href_or_text(node) -> str:
    if node is None:
        return ""
    link = node.find("a") if hasattr(node, "find") else None
    if link and link.get("href"):
        return link["href"].strip()
    return _text(node)


def _email_from(value: str) -> str:
    match = EMAIL_RE.search(value or "")
    return match.group(0) if match else (value or "").strip()


def _text(node) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def _normalize(value: str) -> str:
    return value.lower().strip()
