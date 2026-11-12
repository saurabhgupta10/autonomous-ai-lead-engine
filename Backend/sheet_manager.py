"""
sheet_manager.py
----------------
Google Sheets CRM Database integration.

Features:
- Authenticates securely via service account credentials.
- Exponential backoff retry logic for Google API rate limits and network transients.
- Persistent cross-scan deduplication using normalized domain and business name + city.
- Non-destructive header migration ensuring backwards compatibility with existing CRM data.
- Batch row appending to conserve Google API rate limits.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse

import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_SHEET_ID,
    GOOGLE_WORKSHEET_NAME,
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Standard CRM Columns for Autonomous Discovery
RICH_HEADER_ROW = [
    "Timestamp (UTC)",
    "Business Name",
    "Country",
    "City",
    "Industry",
    "Website",
    "Email",
    "Phone",
    "Website Status",
    "Opportunity Type",
    "Priority",
    "AI Score",
    "AI Reasoning",
    "Evidence",
    "Source URL",
    "Discovery Provider",
    "Discovery Date",
    "Last Updated",
]

# Legacy CRM columns for backwards compatibility
LEGACY_HEADER_ROW = [
    "Timestamp (UTC)",
    "Company Name",
    "Website",
    "Email",
    "Priority",
    "Reason",
]

T = TypeVar("T")


def with_retry(func: Callable[..., T], max_retries: int = 3, initial_delay: float = 2.0) -> T:
    """Execute a Google Sheets API operation with exponential backoff on rate limits."""
    delay = initial_delay
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except gspread.exceptions.APIError as err:
            last_err = err
            code = getattr(err.response, "status_code", None)
            if code in {429, 500, 502, 503}:
                logger.warning(
                    "Google Sheets API transient %s (attempt %d/%d). Retrying in %.1fs...",
                    code, attempt, max_retries, delay
                )
                time.sleep(delay)
                delay *= 2.0
            else:
                raise
        except Exception as exc:
            last_err = exc
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2.0
            else:
                raise

    if last_err:
        raise last_err
    raise RuntimeError("Retry attempts exhausted without result.")


def get_client() -> gspread.Client:
    key_path = Path(GOOGLE_SERVICE_ACCOUNT_FILE)
    if not key_path.exists():
        raise FileNotFoundError(f"Service account JSON not found at {key_path}.")
    creds = Credentials.from_service_account_file(str(key_path), scopes=SCOPES)
    return gspread.authorize(creds)


def get_worksheet(
    client: gspread.Client | None = None,
    sheet_id: str | None = None,
    worksheet_name: str | None = None,
):
    sheet_id = sheet_id or GOOGLE_SHEET_ID
    worksheet_name = worksheet_name or GOOGLE_WORKSHEET_NAME

    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID is missing from .env configuration.")

    client = client or get_client()
    spreadsheet = with_retry(lambda: client.open_by_key(sheet_id))

    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = with_retry(
            lambda: spreadsheet.add_worksheet(
                title=worksheet_name, rows=1000, cols=len(RICH_HEADER_ROW)
            )
        )

    _ensure_header(worksheet)
    return worksheet


def _ensure_header(worksheet: gspread.Worksheet) -> list[str]:
    """Ensure headers exist and non-destructively upgrade if legacy."""
    existing = with_retry(lambda: worksheet.row_values(1))
    if not existing:
        with_retry(lambda: worksheet.append_row(RICH_HEADER_ROW, value_input_option="USER_ENTERED"))
        return RICH_HEADER_ROW

    # If already rich header
    if "Business Name" in existing or "Industry" in existing:
        return existing

    # Non-destructive upgrade: Append missing rich columns to row 1
    missing_cols = [col for col in RICH_HEADER_ROW if col not in existing]
    if missing_cols:
        logger.info("Migrating Google Sheets headers to support discovery fields: +%s", missing_cols)
        new_headers = existing + missing_cols
        with_retry(
            lambda: worksheet.update(values=[new_headers], range_name=f"A1:{chr(64 + len(new_headers))}1")
        )
        return new_headers

    return existing


def normalize_domain(url: Any) -> str:
    """Extract clean domain for duplicate prevention."""
    if not url:
        return ""
    clean = str(url).strip().lower()
    if not clean.startswith(("http://", "https://")):
        clean = f"https://{clean}"
    try:
        netloc = urlparse(clean).netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def normalize_business_key(name: Any, city: Any) -> str:
    """Generate normalized business identity key."""
    clean_name = "".join(c for c in str(name or "").lower() if c.isalnum() or c.isspace()).strip()
    clean_city = "".join(c for c in str(city or "").lower() if c.isalnum() or c.isspace()).strip()
    return f"{clean_name}|{clean_city}"


def get_existing_crm_identifiers(worksheet: gspread.Worksheet) -> tuple[set[str], set[str], set[str]]:
    """
    Extract existing domain, business keys, and provider IDs from CRM in 1 batch read.
    Returns: (domains_set, business_keys_set, source_urls_set)
    """
    try:
        records = with_retry(lambda: worksheet.get_all_records())
    except Exception as exc:
        logger.warning("Could not read existing CRM rows: %s", exc)
        return set(), set(), set()

    existing_domains: set[str] = set()
    existing_keys: set[str] = set()
    existing_sources: set[str] = set()

    for r in records:
        website = str(r.get("Website") or r.get("website") or "")
        dom = normalize_domain(website)
        if dom and "example.com" not in dom:
            existing_domains.add(dom)

        name = str(r.get("Business Name") or r.get("Company Name") or r.get("company_name") or "")
        city = str(r.get("City") or r.get("city") or "")
        if name:
            existing_keys.add(normalize_business_key(name, city))

        src = str(r.get("Source URL") or r.get("source_url") or "")
        if src:
            existing_sources.add(src.strip().lower())

    return existing_domains, existing_keys, existing_sources


def sync_discovered_leads_to_sheets(records: list[Any]) -> tuple[int, int]:
    """
    Store newly discovered leads with persistent deduplication.
    Returns: (appended_count, duplicates_skipped)
    """
    if not records:
        return 0, 0

    worksheet = get_worksheet()
    existing_headers = _ensure_header(worksheet)
    existing_domains, existing_keys, existing_sources = get_existing_crm_identifiers(worksheet)

    to_append: list[list[str]] = []
    duplicates_skipped = 0

    for rec in records:
        crm_dict = rec.to_crm_dict() if hasattr(rec, "to_crm_dict") else rec

        website = crm_dict.get("Website", "")
        domain = normalize_domain(website)
        name = crm_dict.get("Business Name") or crm_dict.get("Company Name", "")
        city = crm_dict.get("City", "")
        bkey = normalize_business_key(name, city)
        source_url = crm_dict.get("Source URL", "").strip().lower()

        # Check duplicate
        is_dup = False
        if domain and domain in existing_domains:
            is_dup = True
        elif bkey and bkey in existing_keys:
            is_dup = True
        elif source_url and source_url in existing_sources:
            is_dup = True

        if is_dup:
            duplicates_skipped += 1
            continue

        # Add to local seen sets
        if domain:
            existing_domains.add(domain)
        if bkey:
            existing_keys.add(bkey)
        if source_url:
            existing_sources.add(source_url)

        # Map to current worksheet column order
        row = [str(crm_dict.get(col, "")) for col in existing_headers]
        to_append.append(row)

    if to_append:
        with_retry(
            lambda: worksheet.append_rows(to_append, value_input_option="USER_ENTERED")
        )
        logger.info("Successfully appended %d new leads (%d duplicates skipped).", len(to_append), duplicates_skipped)

    return len(to_append), duplicates_skipped


# ── Legacy Scraper Pipeline Compatibility ─────────────────────────────────────

def append_high_priority_leads(leads: list[dict]) -> int:
    """Legacy helper: appends High priority leads from URL scraper."""
    high_leads = [lead for lead in leads if lead.get("priority") == "High"]
    if not high_leads:
        return 0

    worksheet = get_worksheet()
    headers = with_retry(lambda: worksheet.row_values(1))

    rows = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for lead in high_leads:
        lead_dict = {
            "Timestamp (UTC)": timestamp,
            "Business Name": lead.get("company_name", ""),
            "Company Name": lead.get("company_name", ""),
            "Website": lead.get("website", ""),
            "Email": lead.get("email", ""),
            "Priority": lead.get("priority", "High"),
            "Reason": lead.get("reason", ""),
            "AI Reasoning": lead.get("reason", ""),
            "Source URL": lead.get("source_url", "Local Directory Scraper"),
            "Discovery Provider": "local_scraper",
            "Discovery Date": timestamp[:10],
            "Last Updated": timestamp,
        }
        row = [str(lead_dict.get(h, "")) for h in headers]
        rows.append(row)

    with_retry(
        lambda: worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    )
    return len(rows)
