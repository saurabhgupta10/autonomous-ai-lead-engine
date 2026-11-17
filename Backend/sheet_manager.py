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
from email_extractor import clean_and_validate_email

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


def get_column_letter(col_idx: int) -> str:
    """Convert 1-based column index to A1 notation letter (1 -> A, 18 -> R, 27 -> AA)."""
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


class SyncStats(dict):
    """
    Rich synchronization statistics with backward-compatible tuple unpacking:
    synced_count, dups_skipped = sync_discovered_leads_to_sheets(...)
    """

    @property
    def total_synced(self) -> int:
        return self.get("records_inserted", 0) + self.get("records_updated", 0)

    def __iter__(self):
        yield self.total_synced
        yield self.get("duplicates_skipped", 0)


def sync_discovered_leads_to_sheets(records: list[Any]) -> SyncStats:
    """
    Insert new business leads and update existing business records in Google Sheets CRM.

    Behaviors:
      NEW BUSINESS:
        - Insert a new spreadsheet row.
        - Preserves all discovery metadata.
      EXISTING BUSINESS:
        - Identify existing row by normalized domain, business name + city, or source URL.
        - Enrich missing email, phone, website, and updated AI opportunity analysis.
        - Never replace an existing valid email with an empty or invalid value.
        - Never create duplicate rows.

    Returns:
      SyncStats dictionary containing:
        records_inserted, records_updated, duplicates_skipped,
        records_failed, emails_added, emails_updated
    """
    stats = SyncStats({
        "records_inserted": 0,
        "records_updated": 0,
        "duplicates_skipped": 0,
        "records_failed": 0,
        "emails_added": 0,
        "emails_updated": 0,
    })

    if not records:
        return stats

    worksheet = get_worksheet()
    existing_headers = _ensure_header(worksheet)
    num_cols = len(existing_headers)
    end_col_letter = get_column_letter(num_cols)

    # Read all existing sheet values in 1 call (Row 1 = headers, Rows 2..N = data)
    try:
        all_rows = with_retry(lambda: worksheet.get_all_values())
    except Exception as exc:
        logger.error("Failed to read CRM spreadsheet values: %s", exc)
        stats["records_failed"] = len(records)
        return stats

    if not all_rows:
        all_rows = [existing_headers]

    header_row = all_rows[0]
    header_to_idx = {h.strip(): i for i, h in enumerate(header_row)}

    # Map aliases for legacy compatibility
    def get_cell(row_vals: list[str], col_name: str) -> str:
        idx = header_to_idx.get(col_name)
        if idx is not None and idx < len(row_vals):
            return row_vals[idx].strip()
        # Aliases
        if col_name == "Business Name":
            idx = header_to_idx.get("Company Name")
            if idx is not None and idx < len(row_vals):
                return row_vals[idx].strip()
        elif col_name == "Company Name":
            idx = header_to_idx.get("Business Name")
            if idx is not None and idx < len(row_vals):
                return row_vals[idx].strip()
        elif col_name == "AI Reasoning":
            idx = header_to_idx.get("Reason")
            if idx is not None and idx < len(row_vals):
                return row_vals[idx].strip()
        elif col_name == "Reason":
            idx = header_to_idx.get("AI Reasoning")
            if idx is not None and idx < len(row_vals):
                return row_vals[idx].strip()
        return ""

    def set_cell(row_vals: list[str], col_name: str, val: str) -> None:
        idx = header_to_idx.get(col_name)
        if idx is None:
            # Check alias
            if col_name == "Business Name":
                idx = header_to_idx.get("Company Name")
            elif col_name == "Company Name":
                idx = header_to_idx.get("Business Name")
            elif col_name == "AI Reasoning":
                idx = header_to_idx.get("Reason")
            elif col_name == "Reason":
                idx = header_to_idx.get("AI Reasoning")

        if idx is not None:
            while len(row_vals) <= idx:
                row_vals.append("")
            row_vals[idx] = val

    # Build row index for existing CRM records: key -> sheet_row_num (1-based), row_vals
    # Keys tracked: domain, business_key, source_url
    existing_row_map: dict[str, int] = {}
    row_data_cache: dict[int, list[str]] = {}

    for row_idx in range(1, len(all_rows)):
        sheet_row_num = row_idx + 1
        r_vals = list(all_rows[row_idx])
        row_data_cache[sheet_row_num] = r_vals

        website_val = get_cell(r_vals, "Website")
        dom = normalize_domain(website_val)
        if dom and "example.com" not in dom:
            existing_row_map[f"dom:{dom}"] = sheet_row_num

        name_val = get_cell(r_vals, "Business Name")
        city_val = get_cell(r_vals, "City")
        if name_val:
            bkey = normalize_business_key(name_val, city_val)
            existing_row_map[f"key:{bkey}"] = sheet_row_num

        src_val = get_cell(r_vals, "Source URL").lower()
        if src_val:
            existing_row_map[f"src:{src_val}"] = sheet_row_num

    staged_updates: list[dict[str, Any]] = []
    to_insert: list[list[str]] = []
    updated_row_nums: set[int] = set()

    for rec in records:
        try:
            crm_dict = rec.to_crm_dict() if hasattr(rec, "to_crm_dict") else dict(rec)

            website = crm_dict.get("Website", "")
            domain = normalize_domain(website)
            name = crm_dict.get("Business Name") or crm_dict.get("Company Name", "")
            city = crm_dict.get("City", "")
            bkey = normalize_business_key(name, city)
            source_url = crm_dict.get("Source URL", "").strip().lower()

            matched_row_num: int | None = None
            if domain and f"dom:{domain}" in existing_row_map:
                matched_row_num = existing_row_map[f"dom:{domain}"]
            elif bkey and f"key:{bkey}" in existing_row_map:
                matched_row_num = existing_row_map[f"key:{bkey}"]
            elif source_url and f"src:{source_url}" in existing_row_map:
                matched_row_num = existing_row_map[f"src:{source_url}"]

            new_email = clean_and_validate_email(crm_dict.get("Email")) or ""
            new_phone = str(crm_dict.get("Phone") or "").strip()
            new_web = str(crm_dict.get("Website") or "").strip()

            if matched_row_num is not None:
                # ── EXISTING BUSINESS: Inspect and Enrich ───────────────────
                current_vals = row_data_cache[matched_row_num]
                row_changed = False

                curr_email = get_cell(current_vals, "Email")
                curr_valid_email = clean_and_validate_email(curr_email)

                # Email update logic
                if new_email:
                    if not curr_email or not curr_valid_email:
                        # Existing email was missing or invalid; populate with newly discovered valid email
                        set_cell(current_vals, "Email", new_email)
                        row_changed = True
                        stats["emails_added"] += 1
                        logger.info("Enriched missing email for row %d: %s", matched_row_num, new_email)
                    elif curr_valid_email and curr_valid_email != new_email:
                        # If existing email is already valid, preserve it
                        logger.debug("Preserving existing valid email '%s' over '%s'", curr_valid_email, new_email)

                # Phone update logic
                curr_phone = get_cell(current_vals, "Phone")
                if not curr_phone and new_phone:
                    set_cell(current_vals, "Phone", new_phone)
                    row_changed = True

                # Website update logic
                curr_web = get_cell(current_vals, "Website")
                if not curr_web and new_web:
                    set_cell(current_vals, "Website", new_web)
                    row_changed = True

                # AI and opportunity metadata updates
                enrichment_fields = [
                    "Opportunity Type", "Priority", "AI Score",
                    "AI Reasoning", "Evidence", "Website Status"
                ]
                for fld in enrichment_fields:
                    new_fld_val = str(crm_dict.get(fld) or "").strip()
                    curr_fld_val = get_cell(current_vals, fld)
                    if new_fld_val and new_fld_val != curr_fld_val and (not curr_fld_val or curr_fld_val in {"Unscored", "General Automation", "50", "unverified"}):
                        set_cell(current_vals, fld, new_fld_val)
                        row_changed = True

                if row_changed:
                    set_cell(current_vals, "Last Updated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
                    if matched_row_num not in updated_row_nums:
                        updated_row_nums.add(matched_row_num)
                        stats["records_updated"] += 1
                        # Pad row to full header length
                        while len(current_vals) < num_cols:
                            current_vals.append("")
                        staged_updates.append({
                            "range": f"A{matched_row_num}:{end_col_letter}{matched_row_num}",
                            "values": [current_vals[:num_cols]],
                        })
                else:
                    stats["duplicates_skipped"] += 1

            else:
                # ── NEW BUSINESS: Insert Fresh CRM Row ──────────────────────
                row_vals: list[str] = []
                for col in existing_headers:
                    val = crm_dict.get(col)
                    if val is None:
                        # Check aliases
                        if col == "Company Name":
                            val = crm_dict.get("Business Name", "")
                        elif col == "Business Name":
                            val = crm_dict.get("Company Name", "")
                        elif col == "Reason":
                            val = crm_dict.get("AI Reasoning", "")
                        elif col == "AI Reasoning":
                            val = crm_dict.get("Reason", "")
                        else:
                            val = ""
                    row_vals.append(str(val))

                to_insert.append(row_vals)
                stats["records_inserted"] += 1
                if new_email:
                    stats["emails_added"] += 1

                # Register in local map to prevent duplication within same batch
                projected_row_num = len(all_rows) + len(to_insert)
                if domain:
                    existing_row_map[f"dom:{domain}"] = projected_row_num
                if bkey:
                    existing_row_map[f"key:{bkey}"] = projected_row_num
                if source_url:
                    existing_row_map[f"src:{source_url}"] = projected_row_num
                row_data_cache[projected_row_num] = row_vals

        except Exception as rec_err:
            logger.error("Error processing lead record for CRM sync: %s", rec_err)
            stats["records_failed"] += 1

    # Execute batch updates for modified existing rows
    if staged_updates:
        try:
            logger.info("Executing batch update for %d modified CRM rows...", len(staged_updates))
            with_retry(
                lambda: worksheet.batch_update(staged_updates, value_input_option="USER_ENTERED")
            )
        except Exception as update_err:
            logger.error("Failed to batch update existing CRM rows: %s", update_err)
            stats["records_failed"] += len(staged_updates)

    # Execute batch append for new rows
    if to_insert:
        try:
            logger.info("Executing batch append for %d new CRM rows...", len(to_insert))
            with_retry(
                lambda: worksheet.append_rows(to_insert, value_input_option="USER_ENTERED")
            )
        except Exception as insert_err:
            logger.error("Failed to batch append new CRM rows: %s", insert_err)
            stats["records_failed"] += len(to_insert)

    logger.info(
        "CRM Sync complete: %d inserted, %d updated, %d skipped, %d failed. Emails: +%d added, %d updated.",
        stats["records_inserted"],
        stats["records_updated"],
        stats["duplicates_skipped"],
        stats["records_failed"],
        stats["emails_added"],
        stats["emails_updated"],
    )

    return stats


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
