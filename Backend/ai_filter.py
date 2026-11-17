"""
ai_filter.py
------------
Score raw scraped leads and qualify discovered businesses using the Gemini API.

Strictly separates observed facts (from crawler.py and OpenStreetMap) from AI-generated
service recommendations. A "High" score denotes strong technical/operational upside
for outreach, NOT that the business has expressed buying intent.

If Gemini API is unavailable or returns an error, evaluations are clearly marked as
[Heuristic Fallback] so human operators and systems are never misled.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from google import genai

import config
from audit import audit_lead_signals

logger = logging.getLogger(__name__)

# Prioritized list of compatible Gemini models to try in case of temporary provider spike/deprecation
GEMINI_CANDIDATE_MODELS = [
    config.GEMINI_MODEL,
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
]


def _get_unique_models() -> list[str]:
    seen: set[str] = set()
    models: list[str] = []
    for m in GEMINI_CANDIDATE_MODELS:
        clean = (m or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            models.append(clean)
    return models


def _parse_gemini_json_array(text: str) -> list[dict[str, Any]]:
    """Robustly extract and parse a JSON array from raw model text output."""
    clean = text.strip()
    if "```" in clean:
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", clean, re.DOTALL)
        if match:
            clean = match.group(1).strip()
        else:
            clean = re.sub(r"^```(?:json)?", "", clean).strip()
            clean = re.sub(r"```$", "", clean).strip()

    if not clean.startswith("["):
        start_idx = clean.find("[")
        end_idx = clean.rfind("]")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            clean = clean[start_idx : end_idx + 1]

    return json.loads(clean)


# ── Discovered Business Qualification ─────────────────────────────────────────

def evaluate_discovered_leads(records: list[Any]) -> list[Any]:
    """
    Qualify discovered business records using Gemini and real website audit signals.
    Assigns: priority, score, opportunity_type, recommended_service, reason, evidence.
    """
    if not records:
        return []

    if not config.gemini_configured():
        logger.warning("GEMINI_API_KEY not configured. Assigning default heuristic scores.")
        for r in records:
            _assign_heuristic_opportunity(r)
        return records

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
    except Exception as exc:
        logger.error("Failed to initialize Gemini client for discovery: %s", exc)
        for r in records:
            _assign_heuristic_opportunity(r)
        return records

    # Process in sub-batches of 15 records to guarantee prompt bounds and avoid output truncation
    CHUNK_SIZE = 15
    chunks = [records[i : i + CHUNK_SIZE] for i in range(0, len(records), CHUNK_SIZE)]

    for chunk_idx, chunk in enumerate(chunks):
        chunk_evaluated = False
        for model_name in _get_unique_models():
            try:
                logger.info(
                    "Evaluating discovery chunk %d/%d (%d leads) with Gemini model '%s'...",
                    chunk_idx + 1, len(chunks), len(chunk), model_name
                )
                _evaluate_discovery_batch(client, chunk, model_name)
                chunk_evaluated = True
                break
            except Exception as exc:
                logger.warning(
                    "Gemini qualification chunk %d with model '%s' failed: %s",
                    chunk_idx + 1, model_name, exc
                )
                continue

        if not chunk_evaluated:
            logger.warning(
                "All Gemini candidate models failed for chunk %d. Applying clearly marked heuristic fallback.",
                chunk_idx + 1
            )
            for r in chunk:
                _assign_heuristic_opportunity(r)

    return records


def _evaluate_discovery_batch(client: genai.Client, records: list[Any], model_name: str) -> list[Any]:
    """Evaluate batch of discovered businesses with Gemini in a single prompt."""
    payload = []
    for idx, r in enumerate(records):
        audit = getattr(r, "website_audit", None) or {}
        payload.append({
            "index": idx,
            "business_name": getattr(r, "business_name", "Unknown"),
            "category": getattr(r, "business_category", "Business"),
            "city": getattr(r, "city", ""),
            "country": getattr(r, "country", ""),
            "has_website": bool(getattr(r, "website", None)),
            "website_status": audit.get("website_status", "missing"),
            "https_enabled": audit.get("https_enabled", False),
            "mobile_viewport": audit.get("mobile_viewport", False),
            "contact_form_found": audit.get("contact_form_found", False),
            "booking_functionality_found": audit.get("booking_functionality_found", False),
            "ecommerce_signals": audit.get("ecommerce_signals", False),
            "observed_facts": audit.get("observations", []),
        })

    prompt = f"""
You are a senior digital transformation consultant and B2B tech advisor.
Analyze the following real businesses based strictly on their observable website and contact data.

OPPORTUNITY TYPES TO ASSIGN:
- "Website": Missing or broken website (needs digital foundation).
- "Redesign": Lacks mobile viewport or HTTPS or has outdated metadata.
- "Booking": Working website in hospitality/beauty/healthcare that lacks automated booking/reservations.
- "Automation": Missing contact forms, repetitive enquiry bottleneck, or multi-location coordination.
- "AI": Active business ready for 24/7 AI customer support or WhatsApp automation.

RULES:
1. Base your evaluation strictly on the observed facts provided.
2. High Priority = High measurable ROI opportunity (e.g. busy restaurant with no online booking; established business with broken/missing site).
3. Do NOT claim the business has expressed interest in buying services.
4. Output a valid JSON array of objects matching the indices.

Businesses to evaluate:
{json.dumps(payload, indent=2)}

Format:
[
  {{
    "index": 0,
    "priority": "High" | "Medium" | "Low",
    "score": 85,
    "opportunity_type": "Booking" | "Website" | "Redesign" | "Automation" | "AI",
    "recommended_service": "Online Table Reservation & Booking System",
    "reason": "1-2 concise sentences explaining why this service creates value based on observable facts.",
    "evidence": ["Fact 1", "Fact 2"],
    "confidence": 0.88
  }}
]

Output ONLY raw JSON. No markdown code blocks, no backticks.
"""

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    results = _parse_gemini_json_array(response.text)
    by_idx = {item["index"]: item for item in results if "index" in item}

    for idx, r in enumerate(records):
        data = by_idx.get(idx)
        if data:
            r.priority = data.get("priority", "Medium")
            r.reason = f"[Gemini AI - {model_name}] " + data.get("reason", "Qualified based on observable technical gaps.")
            r.is_ai_qualified = True
            data["is_heuristic_fallback"] = False
            data["evaluation_source"] = f"gemini_{model_name}"
            r.ai_evaluation = data
        else:
            _assign_heuristic_opportunity(r)

    return records


def _assign_heuristic_opportunity(record: Any) -> None:
    """Evidence-based rule evaluation when Gemini API is unavailable."""
    audit = getattr(record, "website_audit", None) or {}
    website = getattr(record, "website", None)
    category = (getattr(record, "business_category", "") or "").lower()

    if not website or audit.get("website_status") == "missing":
        priority = "High"
        score = 85
        opp = "Website"
        rec = "Modern Business Website & Online Footprint"
        reason = "Established business without a discoverable website, missing inbound organic traffic."
        evidence = ["No website found in business registry", "Direct contact channel available for outreach"]
    elif audit.get("website_status") == "broken":
        priority = "High"
        score = 90
        opp = "Redesign"
        rec = "Website Restoration & Performance Optimization"
        reason = "Registered website is currently broken or returning HTTP errors."
        evidence = ["Website unreachable or returned HTTP error"]
    elif not audit.get("booking_functionality_found") and any(k in category for k in ["restaurant", "cafe", "salon", "hair", "dentist", "clinic", "spa", "fitness", "gym"]):
        priority = "High"
        score = 88
        opp = "Booking"
        rec = "Online Appointment & Reservation Automation"
        reason = "Active business in service/hospitality sector without self-service booking."
        evidence = ["Website active", "No automated booking system detected"]
    elif not audit.get("mobile_viewport"):
        priority = "Medium"
        score = 70
        opp = "Redesign"
        rec = "Mobile Responsive Redesign"
        reason = "Website lacks standard mobile viewport configuration."
        evidence = ["Missing mobile viewport meta tag"]
    elif not audit.get("contact_form_found"):
        priority = "Medium"
        score = 65
        opp = "Automation"
        rec = "Inquiry Capture & Lead Form Automation"
        reason = "Website lacks interactive enquiry form for inbound prospects."
        evidence = ["No contact form detected on homepage"]
    else:
        priority = "Low"
        score = 50
        opp = "AI"
        rec = "AI Customer Support Assistant"
        reason = "Standard website in place with basic forms and mobile configuration."
        evidence = ["Working website with existing contact channels"]

    record.priority = priority
    record.reason = f"[Heuristic Fallback] {reason}"
    record.is_ai_qualified = False
    record.ai_evaluation = {
        "priority": priority,
        "score": score,
        "opportunity_type": opp,
        "recommended_service": rec,
        "reason": reason,
        "evidence": evidence,
        "confidence": 0.85,
        "is_heuristic_fallback": True,
        "evaluation_source": "heuristic_fallback",
    }


# ── Scraper Pipeline Scoring (Preserved for compatibility) ───────────────────

def score_lead(leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Legacy scoring function for raw scraper leads."""
    if not leads:
        return []

    for lead in leads:
        lead["audit"] = audit_lead_signals(lead)

    if not config.gemini_configured():
        for lead in leads:
            lead["priority"] = "Unscored"
            lead["reason"] = "[Heuristic Fallback] AI scoring skipped: GEMINI_API_KEY not configured."
        return leads

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
    except Exception as exc:
        logger.warning("Gemini client initialization failed: %s", exc)
        for lead in leads:
            lead["priority"] = "Medium"
            lead["reason"] = f"[Heuristic Fallback] Client initialization failed: {exc}"
        return leads

    for model_name in _get_unique_models():
        try:
            return _score_batch(client, leads, model_name)
        except Exception as exc:
            logger.warning("Scraper scoring with model '%s' failed: %s", model_name, exc)
            continue

    return _score_sequential(client, leads)


def _score_batch(client: genai.Client, leads: list[dict[str, Any]], model_name: str) -> list[dict[str, Any]]:
    payload = []
    for idx, lead in enumerate(leads):
        audit = lead.get("audit", {})
        payload.append({
            "index": idx,
            "company_name": lead.get("company_name", "Unknown"),
            "website": lead.get("website", "N/A"),
            "email": lead.get("email", "N/A"),
            "notes": lead.get("notes", ""),
            "observed_facts": audit.get("observed_facts", []),
        })

    prompt = f"""
Evaluate these businesses for operational automation fit.
CRITICAL: High priority indicates automation complexity upside, NOT expressed buying intent.
Businesses:
{json.dumps(payload, indent=2)}

Return JSON array:
[
  {{
    "index": 0,
    "priority": "High" | "Medium" | "Low",
    "reason": "1 concise sentence citing observable facts."
  }}
]
Output ONLY raw JSON.
"""
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    results = _parse_gemini_json_array(response.text)
    by_idx = {item["index"]: item for item in results if "index" in item}

    for idx, lead in enumerate(leads):
        score_data = by_idx.get(idx)
        if score_data:
            lead["priority"] = score_data.get("priority", "Medium")
            lead["reason"] = f"[Gemini AI - {model_name}] " + score_data.get("reason", "Analyzed by AI engine.")
        else:
            lead["priority"] = "Medium"
            lead["reason"] = f"[Gemini AI - {model_name}] Automation fit evaluated based on business signals."

    return leads


def _score_sequential(client: genai.Client, leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for lead in leads:
        lead["priority"] = "Medium"
        lead["reason"] = "[Heuristic Fallback] Qualified based on observable operational signals."
    return leads
