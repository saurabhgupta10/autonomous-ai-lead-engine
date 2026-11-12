"""
audit.py
--------
Website Audit & Signal Detection Module.

Prepares observable signal detection and website opportunity scoring.
Strictly separates directly observed facts (missing website, non-standard email,
reported operational bottlenecks) from AI-generated fit assessments.

Rule: A "High" score indicates strong fit for automation outreach based on
observable operational complexity, NOT that the prospect has expressed buying intent.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

# Indicators of manual workflows or technical debt in notes
WORKFLOW_SIGNALS = {
    "booking": ["appointment", "booking", "scheduling", "calendar", "reminders", "no-show"],
    "operations": ["warehouse", "routing", "spreadsheets", "logistics", "delivery", "inventory"],
    "procurement": ["erp", "invoice", "procurement", "manufacturing", "supply chain", "production"],
    "scale": ["branches", "clinics", "locations", "employees", "staff"],
}


def audit_lead_signals(lead: dict[str, Any]) -> dict[str, Any]:
    """
    Inspect a raw lead and produce a factual audit of observable website and business signals.
    Does NOT hallucinate details not present in the record.
    """
    website = (lead.get("website") or "").strip()
    email = (lead.get("email") or "").strip()
    notes = (lead.get("notes") or "").strip()
    company_name = (lead.get("company_name") or "Unknown").strip()

    observed_facts: list[str] = []
    improvement_opportunities: list[str] = []
    
    # 1. Website Status Check
    parsed = urlparse(website)
    has_website = bool(parsed.scheme in {"http", "https"} and parsed.netloc)
    is_mock_or_example = "example" in website.lower()
    
    if not website or website.lower() in {"n/a", "none", "null"}:
        observed_facts.append("No discoverable website URL provided")
        improvement_opportunities.append("Website presence creation & digital footprint setup")
    elif is_mock_or_example:
        observed_facts.append("Mock / staging domain detected")
    else:
        observed_facts.append(f"Domain active ({parsed.netloc})")

    # 2. Email Channel Assessment
    if "@" in email:
        domain = email.split("@")[-1].lower()
        if domain in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}:
            observed_facts.append(f"Using generic email provider (@{domain})")
            improvement_opportunities.append("Custom business domain email & branding")
        else:
            observed_facts.append("Custom branded business email in place")
    else:
        observed_facts.append("No direct email address captured")

    # 3. Operational Signals from notes / description
    notes_lower = notes.lower()
    for category, keywords in WORKFLOW_SIGNALS.items():
        matched = [k for k in keywords if re.search(r"\b" + re.escape(k) + r"\b", notes_lower)]
        if matched:
            if category == "booking":
                observed_facts.append("Reports manual client appointment / calendar scheduling")
                improvement_opportunities.append("Automated booking and self-service calendar integration")
            elif category == "operations":
                observed_facts.append("Reports manual spreadsheet or routing coordination")
                improvement_opportunities.append("Real-time operational dashboard & route optimization")
            elif category == "procurement":
                observed_facts.append("Reports invoice, ERP, or supply chain bottlenecks")
                improvement_opportunities.append("Automated invoice processing and ERP synchronization")
            elif category == "scale":
                observed_facts.append("Multi-site or distributed team footprint identified")
                improvement_opportunities.append("Centralized team automation and workflow orchestration")

    return {
        "company_name": company_name,
        "website": website,
        "has_website": has_website,
        "observed_facts": observed_facts,
        "improvement_opportunities": improvement_opportunities,
        "audit_timestamp": lead.get("timestamp") or "N/A",
    }
