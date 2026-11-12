"""
api.py
------
FastAPI REST server for the Lead Generation Engine.

Endpoints:
  GET  /health          — liveness check and config status
  GET  /api/leads       — return leads from Google Sheets (or error)
  POST /api/scan        — trigger a lead-generation pipeline run
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import threading
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

import config
from scraper import scrape_businesses
from ai_filter import score_lead
from sheet_manager import append_high_priority_leads, get_worksheet
from discovery.discovery_schemas import DiscoveryQuery
from discovery.discovery_service import DiscoveryService

# ── Singleton discovery coordinator ──────────────────────────────────────────
discovery_service = DiscoveryService()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Lead Generation Engine API",
    version="2.0.0",
    description="Autonomous AI-Powered Lead Generation & Enrichment Engine",
)

origins = list({config.FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Scan state ────────────────────────────────────────────────────────────────
_scan_lock = threading.Lock()

_scan_status: dict = {
    "scan_id": None,
    "status": "idle",          # idle | running | complete | error
    "started_at": None,
    "finished_at": None,
    "error": None,
    "summary": None,
}


# ── URL validation ────────────────────────────────────────────────────────────
_PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_private_host(hostname: str) -> bool:
    if hostname.lower() in {"localhost", "localhost.localdomain"}:
        return True
    try:
        addr = ipaddress.ip_address(hostname)
        return any(addr in net for net in _PRIVATE_RANGES)
    except ValueError:
        return False


def _validate_scan_url(url: str) -> str:
    """
    Validate a user-supplied scan URL.
    - Must be http or https.
    - Hostname must not be a private/localhost address.
    - Hostname must be in ALLOWED_SCAN_HOSTS (if that list is non-empty).
    Returns the url unchanged if valid, raises HTTPException otherwise.
    """
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=400,
            detail=f"Only http/https URLs are permitted. Got scheme: {parsed.scheme!r}",
        )

    hostname = parsed.hostname or ""
    if _is_private_host(hostname):
        raise HTTPException(
            status_code=400,
            detail=f"Scanning private/localhost addresses is not permitted: {hostname!r}",
        )

    if config.ALLOWED_SCAN_HOSTS and hostname.lower() not in config.ALLOWED_SCAN_HOSTS:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Host {hostname!r} is not in the ALLOWED_SCAN_HOSTS allowlist. "
                "Add it to your .env to permit scanning."
            ),
        )

    return url


# ── Pydantic models ───────────────────────────────────────────────────────────
class ScanRequest(BaseModel):
    urls: Optional[list[str]] = None   # None → use mock/default source
    dry_run: bool = False

    @field_validator("urls", mode="before")
    @classmethod
    def _validate_urls(cls, v):
        if v is None:
            return v
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError("urls must be a non-empty list or null")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────
def _run_pipeline_sync(scan_id: str, urls: list[str], dry_run: bool) -> None:
    """Runs the full pipeline in a background thread."""
    global _scan_status

    _scan_status.update(
        scan_id=scan_id,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        error=None,
        summary=None,
    )

    try:
        logger.info("[scan:%s] Scraping %d source(s).", scan_id, len(urls))
        leads = scrape_businesses(urls)
        logger.info("[scan:%s] Scraped %d leads.", scan_id, len(leads))

        scored = score_lead(leads)
        high_count = sum(1 for lead in scored if lead.get("priority") == "High")

        written = 0
        if not dry_run:
            if config.sheets_configured():
                written = append_high_priority_leads(scored)
                logger.info("[scan:%s] Wrote %d High rows to Sheets.", scan_id, written)
            else:
                logger.warning("[scan:%s] Google Sheets not configured — skipping write.", scan_id)

        _scan_status.update(
            status="complete",
            finished_at=datetime.now(timezone.utc).isoformat(),
            summary={
                "scraped": len(leads),
                "high": high_count,
                "written": written,
                "dry_run": dry_run,
                "sheets_configured": config.sheets_configured(),
            },
        )
    except Exception as exc:
        logger.exception("[scan:%s] Pipeline error: %s", scan_id, exc)
        _scan_status.update(
            status="error",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
        )
    finally:
        _scan_lock.release()


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
def health():
    """Liveness check. Reports which integrations are configured."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "integrations": {
            "gemini": {
                "configured": config.gemini_configured(),
                "model": config.GEMINI_MODEL if config.gemini_configured() else None,
            },
            "google_sheets": {
                "configured": config.sheets_configured(),
                "sheet_id": config.GOOGLE_SHEET_ID or None,
                "worksheet": config.GOOGLE_WORKSHEET_NAME,
            },
        },
    }


@app.get("/api/leads", tags=["leads"])
def get_leads():
    """
    Return lead records from Google Sheets.

    If Sheets is not configured this returns a clear error — it does NOT
    silently serve mock data as if the integration were working.
    """
    if not config.sheets_configured():
        missing = []
        if not config.GOOGLE_SHEET_ID:
            missing.append("GOOGLE_SHEET_ID")
        if not config.sheets_configured():
            missing.append("GOOGLE_SERVICE_ACCOUNT_FILE (file not found)")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Google Sheets integration is not configured.",
                "missing": missing,
                "hint": "Copy Backend/.env.example to Backend/.env and fill in the required values.",
            },
        )

    try:
        worksheet = get_worksheet()
        records = worksheet.get_all_records()
    except Exception as exc:
        logger.exception("Failed to read Google Sheets: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "Failed to read data from Google Sheets.",
                "detail": str(exc),
            },
        )

    high_count = sum(
        1 for r in records if str(r.get("Priority", "")).strip().lower() == "high"
    )

    return {
        "status": "ok",
        "total_leads": len(records),
        "high_priority_count": high_count,
        "data": records,
    }


@app.post("/api/scan", status_code=202, tags=["scan"])
def trigger_scan(body: ScanRequest):
    """
    Trigger a lead-generation pipeline run.

    - Validates all source URLs before starting.
    - Prevents concurrent runs.
    - Returns a scan_id you can use to poll /api/scan/status.
    - Set dry_run=true to score leads without writing to Google Sheets.
    """
    if not _scan_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "A scan is already in progress.",
                "scan_id": _scan_status.get("scan_id"),
            },
        )

    # Validate supplied URLs (releases lock on failure)
    urls: list[str]
    if body.urls:
        try:
            urls = [_validate_scan_url(u) for u in body.urls]
        except HTTPException:
            _scan_lock.release()
            raise
    else:
        urls = [str(u) for u in config.DEFAULT_SOURCE_URLS]

    scan_id = str(uuid.uuid4())[:8]

    thread = threading.Thread(
        target=_run_pipeline_sync,
        args=(scan_id, urls, body.dry_run),
        daemon=True,
    )
    thread.start()

    return {
        "status": "accepted",
        "scan_id": scan_id,
        "message": "Scan started. Poll /api/scan/status for progress.",
        "dry_run": body.dry_run,
        "sources": len(urls),
    }


@app.get("/api/scan/status", tags=["scan"])
def scan_status():
    """Return the current (or last) scan status."""
    return _scan_status


# ── Autonomous Business Discovery Endpoints (Phase 5) ─────────────────────────

@app.post("/api/discovery/start", status_code=202, tags=["discovery"])
def start_business_discovery(query: DiscoveryQuery):
    """
    Launch autonomous discovery of genuine businesses by location and industry.
    Discovers via OpenStreetMap Overpass/Nominatim, conducts deep website audits,
    scores opportunities with Gemini, and syncs high-fit leads to Google Sheets.
    """
    res = discovery_service.start_discovery(query)
    if res.get("status") == "rejected":
        raise HTTPException(
            status_code=409,
            detail={"error": res.get("error"), "session_id": res.get("session_id")},
        )
    return res


@app.get("/api/discovery/status", tags=["discovery"])
def get_discovery_status():
    """Poll the real-time status of the current or latest discovery job."""
    return discovery_service.get_status()


@app.get("/api/discovery/results", tags=["discovery"])
def get_discovery_results():
    """Return the enriched business records discovered in the latest session."""
    results = discovery_service.get_latest_results()
    return {
        "status": "ok",
        "total_results": len(results),
        "results": results,
    }


@app.get("/api/discovery/history", tags=["discovery"])
def get_discovery_history():
    """Return history log of recent discovery runs."""
    return {
        "status": "ok",
        "history": discovery_service.get_history(),
    }

