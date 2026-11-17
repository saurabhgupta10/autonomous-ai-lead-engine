"""
discovery_schemas.py
--------------------
Pydantic data models for business discovery queries, raw records, and result batches.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class DiscoveryQuery(BaseModel):
    country: str = Field(..., min_length=2, description="Target country name or ISO code, e.g. 'USA', 'UK', 'Australia', 'UAE'")
    city: str = Field(..., min_length=2, description="Target city name, e.g. 'New York', 'London', 'Sydney'")
    industry: str = Field("Restaurants", min_length=2, description="Industry or business category, e.g. 'Restaurants', 'Salons', 'Dentists'")
    keyword: Optional[str] = Field(None, description="Optional search keyword to refine the query")
    limit: int = Field(25, ge=1, le=100, description="Maximum number of business records to discover (1-100)")

    def __init__(self, **data: Any):
        # Support max_results as an alias for limit
        if "max_results" in data and "limit" not in data:
            data["limit"] = data.pop("max_results")
        super().__init__(**data)

    @field_validator("country", "city", "industry", mode="before")
    @classmethod
    def strip_strings(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return str(v)


class BusinessRecord(BaseModel):
    provider_id: str
    business_name: str
    business_category: str
    country: str
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    website: Optional[str] = None
    email: Optional[str] = None
    email_source: Optional[str] = None
    phone: Optional[str] = None
    discovery_provider: str = "OpenStreetMap (ODbL)"
    source_url: str
    discovery_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Fields populated during pipeline
    website_audit: Optional[dict[str, Any]] = None
    ai_evaluation: Optional[dict[str, Any]] = None
    priority: str = "Medium"
    reason: str = ""
    is_ai_qualified: bool = False

    def to_crm_dict(self) -> dict[str, Any]:
        """Convert to dict matching CRM sheet storage requirements."""
        audit = self.website_audit or {}
        ai = self.ai_evaluation or {}

        evidence_list = ai.get("evidence", [])
        evidence_str = "; ".join(evidence_list) if isinstance(evidence_list, list) else str(evidence_list)

        return {
            "Timestamp (UTC)": self.discovery_timestamp,
            "Business Name": self.business_name,
            "Country": self.country,
            "City": self.city,
            "Industry": self.business_category,
            "Website": self.website or "",
            "Email": self.email or "",
            "Phone": self.phone or "",
            "Website Status": audit.get("website_status", "missing" if not self.website else "unverified"),
            "Opportunity Type": ai.get("opportunity_type", "General Automation"),
            "Priority": self.priority,
            "AI Score": ai.get("score", 50),
            "AI Reasoning": self.reason,
            "Evidence": evidence_str,
            "Source URL": self.source_url,
            "Discovery Provider": self.discovery_provider,
            "Discovery Date": self.discovery_timestamp[:10],
            "Last Updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }


class DiscoveryResult(BaseModel):
    session_id: str
    query: DiscoveryQuery
    status: str  # "complete" | "failed" | "running"
    total_discovered: int = 0
    with_website_count: int = 0
    without_website_count: int = 0
    duplicates_skipped: int = 0
    high_priority_count: int = 0
    leads: list[BusinessRecord] = []
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
