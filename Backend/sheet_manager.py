"""
sheet_manager.py
----------------
Authenticate with a Google Cloud service account via gspread and append
High-priority leads to a Google Sheet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_SHEET_ID,
    GOOGLE_WORKSHEET_NAME,
)

# Spreadsheets API + Drive (needed to open a sheet shared with the service account).
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW = [
    "Timestamp (UTC)",
    "Company Name",
    "Website",
    "Email",
    "Priority",
    "Reason",
]


def get_client() -> gspread.Client:
    key_path = Path(GOOGLE_SERVICE_ACCOUNT_FILE)
    if not key_path.exists():
        raise FileNotFoundError(
            f"Service account JSON not found at {key_path}. "
            "Follow the setup steps in README.md."
        )
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
        raise RuntimeError(
            "GOOGLE_SHEET_ID is missing. Copy .env.example to .env and set it."
        )

    client = client or get_client()
    spreadsheet = client.open_by_key(sheet_id)

    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=worksheet_name, rows=1000, cols=len(HEADER_ROW)
        )

    _ensure_header(worksheet)
    return worksheet


def append_high_priority_leads(leads: list[dict]) -> int:
    """
    Append only High-priority leads. Returns how many rows were written.
    """
    high_leads = [lead for lead in leads if lead.get("priority") == "High"]
    if not high_leads:
        return 0

    worksheet = get_worksheet()
    rows = [_lead_to_row(lead) for lead in high_leads]
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)


def _ensure_header(worksheet) -> None:
    existing = worksheet.row_values(1)
    if existing:
        return
    worksheet.append_row(HEADER_ROW, value_input_option="USER_ENTERED")


def _lead_to_row(lead: dict) -> list[str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return [
        timestamp,
        lead.get("company_name", ""),
        lead.get("website", ""),
        lead.get("email", ""),
        lead.get("priority", ""),
        lead.get("reason", ""),
    ]
