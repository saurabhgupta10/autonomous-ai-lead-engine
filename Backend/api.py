"""
api.py
------
FastAPI REST server for the Autonomous AI-Powered Lead Generation & Enrichment Engine.

Endpoints:
  GET  /health                  — liveness check, version, and integration status
  GET  /api/leads               — return verified leads from Google Sheets
  POST /api/scan                — trigger directory scraper & AI scoring pipeline
  GET  /api/scan/status         — poll status of directory scraper run
  POST /api/discovery/start     — start autonomous OpenStreetMap discovery & website audit
  GET  /api/discovery/status    — poll discovery progress and stage counters
  GET  /api/discovery/results   — retrieve latest discovered and qualified leads
  GET  /api/discovery/history   — history log of recent discovery sessions
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

from fastapi import Depends, FastAPI, HTTPException, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator

import config
from scraper import scrape_businesses
from ai_filter import score_lead
from sheet_manager import append_high_priority_leads, get_worksheet
from discovery.discovery_schemas import DiscoveryQuery
from discovery.discovery_service import DiscoveryService

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

# ── Singleton discovery coordinator ──────────────────────────────────────────
discovery_service = DiscoveryService()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Autonomous AI Lead Generation Engine API",
    version="2.1.0",
    description="Autonomous Business Discovery, Technical Website Auditing, and CRM Automation Engine",
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Security Headers Middleware ──────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ── Optional API Key Authentication ──────────────────────────────────────────
security_bearer = HTTPBearer(auto_error=False)


async def verify_api_auth(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Validates API key when API_BEARER_TOKEN is configured in .env.
    In open development mode (API_BEARER_TOKEN=""), all requests pass.
    """
    if not config.is_auth_required():
        return True

    token = None
    if auth and auth.credentials:
        token = auth.credentials.strip()
    elif x_api_key:
        token = x_api_key.strip()

    expected = config.API_BEARER_TOKEN.strip()
    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Unauthorized: Invalid or missing API key."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


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


# ── URL validation (SSRF Protection) ─────────────────────────────────────────
_PRIVATE_RANGES = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_host(hostname: str) -> bool:
    if hostname.lower() in {"localhost", "localhost.localdomain", "broadcasthost", "metadata.google.internal"}:
        return True
    try:
        addr = ipaddress.ip_address(hostname)
        return any(addr in net for net in _PRIVATE_RANGES)
    except ValueError:
        return False


def _validate_scan_url(url: str) -> str:
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
            detail=f"Scanning private/localhost addresses is strictly blocked: {hostname!r}",
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
    urls: Optional[list[str]] = None
    dry_run: bool = False

    @field_validator("urls", mode="before")
    @classmethod
    def _validate_urls(cls, v):
        if v is None:
            return v
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError("urls must be a non-empty list or null")
        return v


# ── Background Pipeline Worker ────────────────────────────────────────────────
def _run_pipeline_sync(scan_id: str, urls: list[str], dry_run: bool) -> None:
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
    """Liveness & readiness probe reporting system and integration status."""
    return {
        "status": "ok",
        "service": "Autonomous AI Lead Generation Engine",
        "version": "2.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "auth_required": config.is_auth_required(),
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
            "discovery_provider": {
                "name": "OpenStreetMap (ODbL)",
                "osm_contact_email": config.OSM_CONTACT_EMAIL,
                "cache_ttl_hours": config.CACHE_TTL_HOURS,
            },
        },
    }


@app.get("/api/leads", tags=["leads"])
def get_leads():
    """Return lead records from the persistent Google Sheets CRM."""
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
                "hint": "Set GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_FILE in Backend/.env.",
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
def trigger_scan(body: ScanRequest, _authorized: bool = Depends(verify_api_auth)):
    """Trigger a lead-generation pipeline run against target URLs."""
    if not _scan_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "A scan is already in progress.",
                "scan_id": _scan_status.get("scan_id"),
            },
        )

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
    """Return the status of the directory scraper run."""
    return _scan_status


# ── Autonomous Business Discovery Endpoints (Phase 5 & 6) ─────────────────────

@app.post("/api/discovery/start", status_code=202, tags=["discovery"])
def start_business_discovery(
    query: DiscoveryQuery,
    _authorized: bool = Depends(verify_api_auth),
):
    """
    Launch autonomous discovery of genuine businesses by location and industry.
    Discovers via OpenStreetMap, conducts deep website audits with SSRF security,
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
    """Poll real-time status and stage progress of the discovery job."""
    return discovery_service.get_status()


@app.get("/api/discovery/results", tags=["discovery"])
def get_discovery_results():
    """Return enriched business records discovered in the latest session."""
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
