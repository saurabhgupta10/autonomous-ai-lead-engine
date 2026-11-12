"""
Central configuration loaded from environment variables / .env.
All modules should import from here rather than reading os.getenv directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the Backend directory regardless of where the process starts.
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Gemini ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
# Default model: gemini-flash-lite-latest or gemini-3.5-flash-lite (high availability & speed).
# Override with GEMINI_MODEL=<model-name> in .env if needed.
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

# ── Google Sheets ─────────────────────────────────────────────────────────────
GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_WORKSHEET_NAME: str = os.getenv("GOOGLE_WORKSHEET_NAME", "Leads")
GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    str(PROJECT_ROOT / "credentials" / "service_account.json"),
)

# ── Scraper ───────────────────────────────────────────────────────────────────
# Default local mock page used when no URLs are passed on the CLI.
DEFAULT_SOURCE_URLS: list[str] = [
    (PROJECT_ROOT / "data" / "mock_leads.html").as_uri(),
]

REQUEST_TIMEOUT_SECONDS: int = 15
REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": "LeadGenEngine/2.0 (+https://github.com/saurabhgupta10/autonomous-ai-lead-engine; respectful crawler)",
    "Accept": "text/html,application/xhtml+xml",
}

# ── OpenStreetMap Compliance ─────────────────────────────────────────────────
OSM_CONTACT_EMAIL: str = os.getenv("OSM_CONTACT_EMAIL", "leadengine-operator@leadengine.local")
OSM_USER_AGENT: str = (
    f"LeadGenEngineApp/2.0 (+https://github.com/saurabhgupta10/autonomous-ai-lead-engine; contact: {OSM_CONTACT_EMAIL})"
)
CACHE_DIR: Path = PROJECT_ROOT / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_HOURS: int = int(os.getenv("CACHE_TTL_HOURS", "24"))

# ── Security & Authentication ────────────────────────────────────────────────
# Optional API Key for securing discovery and scan execution endpoints in production.
# If unset, the server permits open development requests.
API_BEARER_TOKEN: str = os.getenv("API_BEARER_TOKEN", "")

# Comma-separated list of hostnames that the /api/scan endpoint is allowed to fetch.
ALLOWED_SCAN_HOSTS_RAW: str = os.getenv("ALLOWED_SCAN_HOSTS", "")
ALLOWED_SCAN_HOSTS: set[str] = (
    {h.strip().lower() for h in ALLOWED_SCAN_HOSTS_RAW.split(",") if h.strip()}
    if ALLOWED_SCAN_HOSTS_RAW
    else set()
)

# Frontend origins for CORS (comma-separated if multiple)
FRONTEND_ORIGIN_RAW: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
ALLOWED_ORIGINS: list[str] = list({
    orig.strip()
    for orig in (FRONTEND_ORIGIN_RAW + ",http://localhost:3000,http://127.0.0.1:3000").split(",")
    if orig.strip()
})


# ── Validation helpers ────────────────────────────────────────────────────────
def gemini_configured() -> bool:
    return bool(GEMINI_API_KEY)


def sheets_configured() -> bool:
    return bool(GOOGLE_SHEET_ID) and Path(GOOGLE_SERVICE_ACCOUNT_FILE).exists()


def is_auth_required() -> bool:
    return bool(API_BEARER_TOKEN.strip())
