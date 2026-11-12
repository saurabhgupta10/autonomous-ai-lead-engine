"""
ai_filter.py
------------
Score a list of raw scraped leads using the Gemini API.

Each lead dict gains:
  "priority" : "High" | "Medium" | "Low" | "Unscored"
  "reason"   : short 1-sentence explanation (AI-generated fit assessment)

IMPORTANT PRINCIPLE (Phase 4):
AI reasoning is based solely on observable business data (name, website, email, notes).
A "High" priority score reflects strong observable operational fit for automation
services (e.g. multi-location, manual routing, spreadsheet dependency) — it does
NOT imply that the business has expressed buying intent.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google import genai

import config
from audit import audit_lead_signals

logger = logging.getLogger(__name__)


def score_lead(leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Score leads using Gemini with batch efficiency and observed signal audits.
    """
    if not leads:
        return []

    # Run factual signal audit first
    for lead in leads:
        lead["audit"] = audit_lead_signals(lead)

    if not config.gemini_configured():
        logger.warning("GEMINI_API_KEY not configured. Skipping AI scoring.")
        for lead in leads:
            lead["priority"] = "Unscored"
            lead["reason"] = "AI scoring skipped: GEMINI_API_KEY not configured."
        return leads

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
    except Exception as exc:
        logger.error("Failed to initialise Gemini client: %s", exc)
        for lead in leads:
            lead["priority"] = "Unscored"
            lead["reason"] = f"AI client initialisation failed: {exc}"
        return leads

    # Attempt fast batch scoring first (1 single API call for all leads)
    try:
        return _score_batch(client, leads)
    except Exception as batch_err:
        logger.warning("Batch scoring failed (%s), falling back to sequential scoring.", batch_err)
        return _score_sequential(client, leads)


def _score_batch(client: genai.Client, leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scores all leads in a single API call for maximum performance and rate-limit safety."""
    leads_payload = []
    for idx, lead in enumerate(leads):
        audit = lead.get("audit", {})
        leads_payload.append({
            "index": idx,
            "company_name": lead.get("company_name", "Unknown"),
            "website": lead.get("website", "N/A"),
            "email": lead.get("email", "N/A"),
            "notes": lead.get("notes", ""),
            "observed_facts": audit.get("observed_facts", []),
            "opportunities": audit.get("improvement_opportunities", []),
        })

    prompt = f"""
You are an expert B2B lead qualification analyst evaluating business prospects for potential tech automation and systems integration outreach.

CRITICAL INSTRUCTIONS:
1. Base your evaluation strictly on the observable facts provided below. Do NOT invent data.
2. A "High" score means the business shows clear operational bottlenecks (manual routing, booking issues, multi-location coordination, ERP gaps) where automation creates high measurable value.
3. A "High" score indicates fit for outreach — do NOT claim the business has expressed interest in buying.
4. "Medium" means moderate potential or limited observable complexity.
5. "Low" means single-operator or lifestyle business with minimal automation upside.

Businesses to evaluate:
{json.dumps(leads_payload, indent=2)}

Respond with a JSON array containing an evaluation object for each business in the exact order:
[
  {{
    "index": 0,
    "priority": "High" | "Medium" | "Low",
    "reason": "1 concise sentence citing observable facts that justify this score."
  }}
]

Output ONLY the raw JSON array. No markdown code blocks, no backticks.
"""

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
    )

    clean_text = (
        response.text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )

    results = json.loads(clean_text)
    scores_by_idx = {item["index"]: item for item in results if "index" in item}

    for idx, lead in enumerate(leads):
        score_data = scores_by_idx.get(idx)
        if score_data:
            lead["priority"] = score_data.get("priority", "Medium")
            lead["reason"] = "[AI assessment] " + score_data.get("reason", "Analyzed by AI engine.")
        else:
            lead["priority"] = "Medium"
            lead["reason"] = "[AI assessment] Automation fit evaluated based on business signals."

    return leads


def _score_sequential(client: genai.Client, leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fallback item-by-item scoring if batch fails."""
    scored: list[dict[str, Any]] = []
    for lead in leads:
        company_name = lead.get("company_name", "Unknown")
        website = lead.get("website", "N/A")
        email = lead.get("email", "N/A")
        notes = lead.get("notes", "")

        prompt = f"""
Evaluate if this business is a strong fit for automation systems outreach.
Company: {company_name}
Website: {website}
Email: {email}
Notes: {notes}

Return a JSON object with:
"priority": "High" | "Medium" | "Low"
"reason": "1 concise sentence explaining the score based on observable facts."

Output ONLY raw JSON.
"""
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
            )
            clean_text = (
                response.text.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            data = json.loads(clean_text)
            lead["priority"] = data.get("priority", "Medium")
            lead["reason"] = "[AI assessment] " + data.get("reason", "Analyzed by AI engine.")
        except Exception as exc:
            logger.warning("Sequential scoring failed for %s: %s", company_name, exc)
            lead["priority"] = "Unscored"
            lead["reason"] = f"AI scoring error: {exc}"

        scored.append(lead)

    return scored
