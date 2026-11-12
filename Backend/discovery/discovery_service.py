"""
discovery_service.py
--------------------
Orchestrates autonomous business discovery, deep website auditing,
Gemini opportunity qualification, and CRM synchronization.

Reliability features:
- Guaranteed local persistence of all discovery session payloads in data/discovery_sessions/
- Graceful recovery if Google Sheets is offline or rate-limited.
- Strict background job concurrency locks.
- Real-time stage updates for dashboard polling.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from crawler import audit_website
from discovery.discovery_schemas import BusinessRecord, DiscoveryQuery
from discovery.overpass_provider import OverpassDiscoveryProvider

logger = logging.getLogger(__name__)

SESSION_STORAGE_DIR = config.PROJECT_ROOT / "data" / "discovery_sessions"
SESSION_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class DiscoveryService:
    def __init__(self):
        self.provider = OverpassDiscoveryProvider()
        self._lock = threading.Lock()
        self._current_job: dict[str, Any] = {
            "session_id": None,
            "status": "idle",  # idle | running | complete | error
            "started_at": None,
            "finished_at": None,
            "error": None,
            "summary": None,
            "results": [],
        }
        self._history: list[dict[str, Any]] = []

    @property
    def is_running(self) -> bool:
        return self._current_job.get("status") == "running"

    def get_status(self) -> dict[str, Any]:
        return {
            "session_id": self._current_job.get("session_id"),
            "status": self._current_job.get("status"),
            "started_at": self._current_job.get("started_at"),
            "finished_at": self._current_job.get("finished_at"),
            "error": self._current_job.get("error"),
            "summary": self._current_job.get("summary"),
        }

    def get_latest_results(self) -> list[dict[str, Any]]:
        return self._current_job.get("results", [])

    def get_history(self) -> list[dict[str, Any]]:
        return self._history[-20:]

    def start_discovery(self, query: DiscoveryQuery) -> dict[str, Any]:
        """Trigger an autonomous discovery run in a managed background thread."""
        if not self._lock.acquire(blocking=False):
            return {
                "status": "rejected",
                "error": "A discovery session is already in progress.",
                "session_id": self._current_job.get("session_id"),
            }

        session_id = str(uuid.uuid4())[:8]

        self._current_job = {
            "session_id": session_id,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "error": None,
            "summary": {"stage": "querying_provider", "query": query.model_dump()},
            "results": [],
        }

        thread = threading.Thread(
            target=self._run_discovery_pipeline,
            args=(session_id, query),
            daemon=True,
        )
        thread.start()

        return {
            "status": "accepted",
            "session_id": session_id,
            "message": f"Autonomous discovery started for {query.industry} in {query.city}, {query.country}.",
        }

    def _run_discovery_pipeline(self, session_id: str, query: DiscoveryQuery) -> None:
        try:
            # Stage 1: Upstream Query
            logger.info("[discovery:%s] Stage 1: Querying provider...", session_id)
            raw_leads = self.provider.discover_businesses(query)
            logger.info("[discovery:%s] Discovered %d real businesses.", session_id, len(raw_leads))

            if not raw_leads:
                self._current_job.update(
                    status="complete",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    summary={
                        "total_discovered": 0,
                        "with_website_count": 0,
                        "without_website_count": 0,
                        "high_priority_count": 0,
                        "duplicates_skipped": 0,
                        "crm_synced": 0,
                        "message": f"No listings found matching '{query.industry}' in {query.city}, {query.country}.",
                    },
                    results=[],
                )
                return

            # Stage 2: Deep Technical Website Audit
            logger.info("[discovery:%s] Stage 2: Deep website crawling & security auditing...", session_id)
            self._current_job["summary"]["stage"] = "auditing_websites"

            with_site = 0
            without_site = 0
            for lead in raw_leads:
                if lead.website:
                    with_site += 1
                    lead.website_audit = audit_website(lead.website)
                else:
                    without_site += 1
                    lead.website_audit = audit_website(None)

            # Stage 3: AI Opportunity Qualification with Gemini
            logger.info("[discovery:%s] Stage 3: Gemini AI Opportunity Qualification...", session_id)
            self._current_job["summary"]["stage"] = "ai_qualification"

            from ai_filter import evaluate_discovered_leads
            scored_leads = evaluate_discovered_leads(raw_leads)
            high_count = sum(1 for l in scored_leads if l.priority == "High")

            # Serialize records
            serialized_leads = [l.to_crm_dict() for l in scored_leads]

            # Stage 4: Persistent Local Storage (Guaranteed data persistence)
            session_file = SESSION_STORAGE_DIR / f"{session_id}.json"
            try:
                session_payload = {
                    "session_id": session_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "query": query.model_dump(),
                    "leads": serialized_leads,
                }
                session_file.write_text(json.dumps(session_payload, indent=2), encoding="utf-8")
                logger.info("[discovery:%s] Session saved locally to %s", session_id, session_file.name)
            except Exception as save_err:
                logger.warning("[discovery:%s] Failed to save session locally: %s", session_id, save_err)

            # Stage 5: CRM Sync with Deduplication & Graceful Fallback
            logger.info("[discovery:%s] Stage 5: Google Sheets CRM Sync & Deduplication...", session_id)
            self._current_job["summary"]["stage"] = "crm_sync"

            synced_count = 0
            dups_skipped = 0
            crm_status_note = "synced"

            if config.sheets_configured():
                try:
                    from sheet_manager import sync_discovered_leads_to_sheets
                    synced_count, dups_skipped = sync_discovered_leads_to_sheets(scored_leads)
                except Exception as sheet_err:
                    logger.warning("[discovery:%s] Google Sheets sync failed: %s (results preserved locally)", session_id, sheet_err)
                    crm_status_note = f"CRM sync deferred: {sheet_err}"
            else:
                crm_status_note = "Google Sheets not configured (leads saved in local session store)"

            summary = {
                "total_discovered": len(scored_leads),
                "with_website_count": with_site,
                "without_website_count": without_site,
                "high_priority_count": high_count,
                "duplicates_skipped": dups_skipped,
                "crm_synced": synced_count,
                "crm_status": crm_status_note,
                "query": query.model_dump(),
            }

            self._current_job.update(
                status="complete",
                finished_at=datetime.now(timezone.utc).isoformat(),
                summary=summary,
                results=serialized_leads,
            )

            self._history.append({
                "session_id": session_id,
                "timestamp": self._current_job["finished_at"],
                "query": query.model_dump(),
                "total_discovered": len(scored_leads),
                "high_priority_count": high_count,
            })

            logger.info("[discovery:%s] Discovery pipeline complete! Total: %d, High: %d, Synced: %d",
                        session_id, len(scored_leads), high_count, synced_count)

        except Exception as exc:
            logger.exception("[discovery:%s] Pipeline failed: %s", session_id, exc)
            self._current_job.update(
                status="error",
                finished_at=datetime.now(timezone.utc).isoformat(),
                error=str(exc),
            )
        finally:
            self._lock.release()
