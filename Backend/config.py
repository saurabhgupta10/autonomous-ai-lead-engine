"""
Central configuration loaded from environment variables / .env.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root regardless of where main.py is launched.
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "Leads")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    str(PROJECT_ROOT / "credentials" / "service_account.json"),
)

# Default local mock page used when no URLs are passed on the CLI.
DEFAULT_SOURCE_URLS = [
    (PROJECT_ROOT / "data" / "mock_leads.html").as_uri(),
]

REQUEST_TIMEOUT_SECONDS = 15
REQUEST_HEADERS = {
    "User-Agent": "LeadGenEngine/1.0 (+local research bot; respectful crawler)",
    "Accept": "text/html,application/xhtml+xml",
}
