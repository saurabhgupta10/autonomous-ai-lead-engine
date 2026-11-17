# LEAD ENGINE IMPLEMENTATION ROADMAP

**Project:** Autonomous AI Lead Generation & Website Intelligence Engine  
**Version:** 2.1.0 → Target: 3.0.0 (Professional)  
**Start Date:** After roadmap approval  
**Philosophy:** Fix before adding. Reliability before features. Free before paid.

> [!IMPORTANT]
> Do NOT begin implementation until this roadmap is reviewed and approved.
> The existing frontend design must NOT be changed. API response formats must remain backward-compatible.

---

## PHASE 1 — Critical Bug Fixes & Data Quality (Priority: IMMEDIATE)
**Estimated Effort:** 1–2 days  
**Objective:** Fix known bugs that reduce data quality and email recall before anything else.

### 1.1 Fix Gmail/Personal Email Blocking

**Problem:** `gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com` are in `DISALLOWED_DOMAINS` in `email_extractor.py`. Many small businesses (the target audience) use Gmail as their primary contact. This silently drops valid emails.

**Files to modify:** `Backend/email_extractor.py`

**Change:**
```python
# Remove from DISALLOWED_DOMAINS (line ~52):
# "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",

# Add to a new PERSONAL_EMAIL_DOMAINS set (for scoring deprioritization only):
PERSONAL_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "yahoo.co.uk", "yahoo.com.au", "live.com", "icloud.com",
}
# Score personal emails lower in prioritize_lead_email() — don't discard them
```

**Expected result:** Personal email addresses are captured but ranked below domain-matched business emails. Email recall improves for SMBs.

**Testing:** Update `test_comprehensive.py` — test that `name@gmail.com` now returns a valid email.

**Risk:** May increase false positives (personal Gmail of unrelated person). Mitigated by scoring priority.

---

### 1.2 Fix Name Variant Deduplication

**Problem:** "Flour Bakery + Cafe" and "Flour Bakery & Cafe" appear as two separate leads from two OSM nodes. The business key normalization doesn't strip `+`, `&`, punctuation.

**Files to modify:** `Backend/sheet_manager.py`

**Change to `normalize_business_key()`:**
```python
def normalize_business_key(name: Any, city: Any) -> str:
    # Normalize special chars before stripping
    import re
    name_str = str(name or "").lower()
    name_str = re.sub(r"[&+/\\|@#]", " ", name_str)  # normalize separators
    clean_name = "".join(c for c in name_str if c.isalnum() or c.isspace()).strip()
    clean_name = " ".join(clean_name.split())  # collapse whitespace
    ...
```

**Testing:** Add test case with `+` vs `&` variant.

---

### 1.3 Calibrate Priority Scoring

**Problem:** 79% of leads score "High Priority." This creates priority fatigue. The issue is in `_assign_heuristic_opportunity()` — any business without a website scores High=85 by default, and 68% of OSM businesses lack websites.

**Files to modify:** `Backend/ai_filter.py`

**Change:** Add a composite scoring system:
- High (≥ 70): Active service business (restaurant/salon/clinic) with no website OR broken website
- Medium (40–69): Has basic website but missing key signals (mobile viewport, booking, contact form)  
- Low (< 40): Has working website with modern features — AI opportunity still exists but weaker

Also update Gemini prompt to anchor the High/Medium/Low threshold:
```
High = Strong, immediate revenue opportunity (broken site in busy sector; active restaurant with 0 digital presence)
Medium = Improvement opportunity worth pursuing in 30–60 days
Low = Advanced optimization opportunity (AI chatbot, analytics) for already-digital business
```

**Expected result:** High priority drops from 79% to approximately 25–35%.

---

### 1.4 Fix Session History Persistence

**Problem:** `_history` list in `DiscoveryService` is in-memory only. Server restart loses history.

**Files to modify:** `Backend/discovery/discovery_service.py`

**Change:** On startup, scan `data/discovery_sessions/*.json` and rebuild `_history` from persisted files.

```python
def __init__(self):
    ...
    self._history = self._load_history_from_disk()

def _load_history_from_disk(self) -> list:
    history = []
    for f in sorted(SESSION_STORAGE_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            history.append({
                "session_id": d["session_id"],
                "timestamp": d["created_at"],
                "query": d["query"],
                ...
            })
        except Exception:
            pass
    return history[-20:]
```

---

## PHASE 2 — Email MX Record Verification
**Estimated Effort:** 1 day  
**Objective:** Distinguish "syntactically valid email" from "email with working mail server."

### 2.1 Add dnspython Dependency

**Files to modify:** `Backend/requirements.txt`
```
dnspython>=2.6.0
```

### 2.2 Add MX Verification Function

**Files to modify:** `Backend/email_extractor.py`

**New function:**
```python
def verify_email_mx(email: str) -> dict:
    """
    Check if the email domain has valid MX records.
    Returns: {
        "has_mx": bool,
        "mx_records": list[str],
        "is_catch_all": None,  # Cannot determine without SMTP probe
        "verification_method": "dns_mx",
        "verified_at": ISO timestamp
    }
    Never performs SMTP probing (privacy/spam concerns).
    """
    import dns.resolver
    domain = email.split("@")[-1] if "@" in email else ""
    if not domain:
        return {"has_mx": False, "mx_records": [], "verification_method": "dns_mx"}
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=3.0)
        mx_records = sorted([str(r.exchange).rstrip(".") for r in answers])
        return {
            "has_mx": bool(mx_records),
            "mx_records": mx_records[:3],  # Store top 3
            "verification_method": "dns_mx",
            "verified_at": datetime.now(timezone.utc).isoformat()
        }
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
        return {"has_mx": False, "mx_records": [], "verification_method": "dns_mx"}
```

### 2.3 Integrate MX Check into Discovery Pipeline

**Files to modify:** `Backend/discovery/discovery_service.py`

After extracting an email, call `verify_email_mx()` and store result in `BusinessRecord.email_mx_verified`.

Add field to `BusinessRecord` schema:
```python
email_mx_verified: Optional[bool] = None
email_mx_records: Optional[list[str]] = None
```

**Rate limiting:** DNS MX checks are fast (~50–200ms per domain). Cache results per domain within a session to avoid duplicate lookups.

**Expected result:** Each email now carries `email_mx_verified: true/false`. Leads with `has_mx=True` can be classified with higher confidence.

---

## PHASE 3 — Lead Verification Status System
**Estimated Effort:** 2–3 days  
**Objective:** Assign VERIFIED / NEEDS_REVIEW / REJECTED to every lead based on evidence.

### 3.1 Verification Schema

**Files to modify:** `Backend/discovery/discovery_schemas.py`

```python
class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"  
    REJECTED = "REJECTED"
    UNVERIFIED = "UNVERIFIED"  # Not yet assessed

# Add to BusinessRecord:
verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
verification_score: int = 0  # 0-100
verification_timestamp: Optional[str] = None
verification_evidence: list[str] = []
verification_flags: list[str] = []  # Issues found
```

### 3.2 Verification Logic

**New file:** `Backend/verification_engine.py`

**Scoring rubric:**
| Check | Points | Evidence |
|---|---|---|
| OSM source URL exists | +10 | Required baseline |
| Website found (any status) | +10 | Has digital presence |
| Website status = "working" | +20 | Live website confirmed |
| Email extracted (any) | +15 | Contact channel available |
| Email domain has MX records | +20 | Email deliverable |
| Phone number present | +10 | Secondary contact |
| AI qualification done (not heuristic) | +10 | AI-verified opportunity |
| Business name ≥ 3 words (specific) | +5 | Real business name |
| **Total possible** | **100** | |

**Thresholds:**
- VERIFIED: ≥ 60 points
- NEEDS_REVIEW: 30–59 points
- REJECTED: < 30 points (or flagged for: generic name, no website + no phone + no email)

### 3.3 Integrate into Pipeline

After AI qualification (Stage 3), call verification engine on each record:
```python
from verification_engine import classify_lead
for lead in scored_leads:
    classify_lead(lead)
```

### 3.4 Add to CRM Output

Add verification columns to `sheet_manager.py RICH_HEADER_ROW`:
```python
"Verification Status",   # VERIFIED / NEEDS_REVIEW / REJECTED
"Verification Score",    # 0-100
"Verification Date",     # ISO date
```

**Expected result:** Every lead has a machine-readable verification tier. Users can filter the dashboard by verification status.

---

## PHASE 4 — Persistent SQLite Database
**Estimated Effort:** 2–3 days  
**Objective:** Replace JSON file sessions with queryable persistent storage.

### 4.1 Add Dependencies
```
sqlalchemy>=2.0
aiosqlite>=0.20
```

### 4.2 Database Schema

**New file:** `Backend/database.py`

```sql
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT UNIQUE,  -- OSM node/way ID
    business_name TEXT,
    business_category TEXT,
    country TEXT,
    city TEXT,
    website TEXT,
    website_status TEXT,
    email TEXT,
    email_mx_verified BOOLEAN,
    phone TEXT,
    priority TEXT,
    ai_score INTEGER,
    verification_status TEXT,
    verification_score INTEGER,
    source_url TEXT,
    discovery_session_id TEXT,
    created_at TEXT,
    last_updated TEXT
);

CREATE TABLE discovery_sessions (
    session_id TEXT PRIMARY KEY,
    query_country TEXT,
    query_city TEXT,
    query_industry TEXT,
    query_limit INTEGER,
    total_discovered INTEGER,
    high_priority_count INTEGER,
    crm_synced INTEGER,
    status TEXT,
    started_at TEXT,
    finished_at TEXT
);
```

### 4.3 Migrate Existing Sessions to DB

Write a one-time migration script that reads all `data/discovery_sessions/*.json` files and inserts into SQLite.

### 4.4 New API Endpoints

Add to `api.py`:
```python
GET /api/leads/search?query=...&status=VERIFIED&priority=High&city=London
GET /api/leads/{provider_id}
GET /api/sessions
GET /api/sessions/{session_id}/leads
GET /api/stats
```

**Note:** Keep existing `/api/leads` (Google Sheets) endpoint working for backward compatibility.

---

## PHASE 5 — Advanced AI Qualification
**Estimated Effort:** 2 days  
**Objective:** Improve Gemini prompt quality and scoring accuracy.

### 5.1 Industry-Specific Prompt Templates

**Files to modify:** `Backend/ai_filter.py`

Replace generic prompt with industry-specific system instructions:

```python
INDUSTRY_PROMPT_CONTEXT = {
    "restaurants": """
Focus on: online booking/reservation systems, menu digitalization, delivery platform integration, 
table management, review response automation. 
High priority: Restaurants with ≥50 seats and no booking widget, or zero online presence.
""",
    "salons": """
Focus on: appointment booking (Fresha/Booksy), client SMS reminders, loyalty programs, online payments.
High priority: Salons without self-service booking or with no website.
""",
    # ... 13 industry contexts
}
```

### 5.2 Add Few-Shot Examples to Prompt

Add 2–3 concrete examples per industry type showing the expected High/Medium/Low classification with reasoning.

### 5.3 Add Prompt Versioning

Track which prompt version was used in each evaluation:
```python
PROMPT_VERSION = "v2.1"
# Store in ai_evaluation dict: "prompt_version": PROMPT_VERSION
```

### 5.4 Cross-Validate AI Against Observed Facts

After Gemini returns results, validate:
```python
# If Gemini says "booking_opportunity" but website_audit says booking_found=True → downgrade priority
# If Gemini says "website" opportunity but website is "working" → flag inconsistency
```

---

## PHASE 6 — Automated Scheduling
**Estimated Effort:** 1–2 days  
**Objective:** Allow scheduled discovery runs without manual triggers.

### 6.1 Add APScheduler

```
apscheduler>=3.10.0
```

### 6.2 Scheduled Discovery Config

**New file:** `Backend/scheduler.py`

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Example: Schedule daily restaurant discovery for London
scheduler.add_job(
    func=run_scheduled_discovery,
    trigger="cron",
    hour=6, minute=0,  # 6 AM UTC
    args=[{"country": "UK", "city": "London", "industry": "Restaurants", "limit": 25}],
    id="london_restaurants_daily"
)
```

### 6.3 New API Endpoints

```python
POST /api/schedule/create    # Create a scheduled discovery job
GET  /api/schedule           # List all scheduled jobs
DELETE /api/schedule/{job_id}  # Cancel a job
```

---

## PHASE 7 — Monitoring & Structured Logging
**Estimated Effort:** 2 days  
**Objective:** Make failures visible and measurable.

### 7.1 Structured JSON Logging

**Files to modify:** `Backend/api.py`

```python
import json
class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "session_id": getattr(record, "session_id", None),
        })
```

### 7.2 Prometheus Metrics

```
prometheus-fastapi-instrumentator>=6.0
```

**Metrics to expose:**
- `discovery_jobs_total{status}` — total jobs by status
- `emails_extracted_total` — total emails found
- `gemini_calls_total{model,status}` — API call counts
- `osm_records_found_total{country,city,industry}` — discovery yield
- `sheets_sync_total{status}` — CRM sync results
- `lead_priority_distribution{priority}` — priority histogram

**New endpoint:** `GET /metrics` (Prometheus format)

### 7.3 Enable API Bearer Token by Default

**Files to modify:** `Backend/.env.example`, `ENVIRONMENT_SETUP.md`

Document clearly that `API_BEARER_TOKEN` should be set before production deployment.

---

## PHASE 8 — Reporting & Analytics
**Estimated Effort:** 3–4 days  
**Objective:** Give users meaningful metrics on lead quality and system performance.

### 8.1 New Analytics API Endpoints

```python
GET /api/analytics/summary          # Overall stats
GET /api/analytics/email_rates      # Email extraction rates by country/industry
GET /api/analytics/priority_dist    # Priority distribution over time
GET /api/analytics/verification     # Verification status breakdown
GET /api/analytics/sessions         # Discovery session history with metrics
```

### 8.2 Frontend Analytics Tab Enhancement

The existing "AI Insights" tab can be extended (not replaced) with charts from the new endpoints.

**Note:** No frontend changes without explicit approval. Propose chart data structures for review first.

---

## PHASE 9 — Multi-Source Discovery
**Estimated Effort:** 1 week+  
**Objective:** Supplement OSM with additional free data sources to increase coverage.

### 9.1 Google Places API (Free Tier)

Google Places API provides **\$200 free credit/month** (≈ 5,000 Nearby Search calls/month).

```python
# Backend/discovery/google_places_provider.py
class GooglePlacesProvider(BaseDiscoveryProvider):
    GOOGLE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    
    def discover_businesses(self, query: DiscoveryQuery) -> list[BusinessRecord]:
        # Use geocoded lat/lon from existing Nominatim result
        # Request: type=restaurant|salon|dentist, radius=5000m
        # Returns: name, website, phone, rating, address
```

**Requires:** `GOOGLE_PLACES_API_KEY` env var (free tier)

### 9.2 Merge Multi-Source Results

Enhance `OverpassDiscoveryProvider` into a `MultiSourceDiscoveryOrchestrator`:
1. Query OSM Overpass (primary)
2. If result count < limit: query Nominatim
3. If result count still < limit: query Google Places (if configured)
4. Merge and deduplicate across sources

---

## DEPENDENCY ADDITIONS SUMMARY

| Phase | Library | Version | Purpose | License |
|---|---|---|---|---|
| 1 | None — | — | Config changes only | — |
| 2 | `dnspython` | ≥2.6.0 | MX record verification | ISC |
| 4 | `sqlalchemy` | ≥2.0 | SQLite ORM | MIT |
| 4 | `aiosqlite` | ≥0.20 | Async SQLite | MIT |
| 6 | `apscheduler` | ≥3.10.0 | Scheduled jobs | MIT |
| 7 | `prometheus-fastapi-instrumentator` | ≥6.0 | Metrics | MIT |
| 9 | None (urllib only) | — | Google Places HTTP calls | — |

**All additions are free and open-source.**

---

## API BACKWARD COMPATIBILITY GUARANTEE

| Endpoint | Status | Contract |
|---|---|---|
| `GET /health` | PRESERVED | No breaking changes |
| `GET /api/leads` | PRESERVED | No breaking changes |
| `POST /api/scan` | PRESERVED | No breaking changes |
| `GET /api/scan/status` | PRESERVED | No breaking changes |
| `POST /api/discovery/start` | PRESERVED + extended | May add new response fields |
| `GET /api/discovery/status` | PRESERVED + extended | May add new summary fields |
| `GET /api/discovery/results` | PRESERVED + extended | May add new lead fields |
| `GET /api/discovery/history` | PRESERVED + extended | May add new history fields |
| **New endpoints** | ADDED | Additive only |

---

## MILESTONE TIMELINE ESTIMATE

| Phase | Duration | Cumulative |
|---|---|---|
| Phase 1: Bug fixes | 1–2 days | Day 2 |
| Phase 2: MX verification | 1 day | Day 3 |
| Phase 3: Verification status | 2–3 days | Day 6 |
| Phase 4: SQLite database | 2–3 days | Day 9 |
| Phase 5: Improved AI | 2 days | Day 11 |
| Phase 6: Scheduling | 1–2 days | Day 13 |
| Phase 7: Monitoring | 2 days | Day 15 |
| Phase 8: Reporting | 3–4 days | Day 19 |
| Phase 9: Multi-source | 5–7 days | Day 26 |

**Total estimated calendar time:** 4–5 weeks (part-time) or 2 weeks (full-time)

---

*Review this roadmap carefully. After approval, implementation begins with Phase 1 — no changes will be made before then.*
