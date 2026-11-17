# LEAD ENGINE FEATURE GAP MATRIX

**Last Updated:** 2026-11-13  
**Version Audited:** 2.1.0  

This matrix compares the current implementation against professional lead generation platforms and identifies missing features with priority, effort, and cost classification.

---

## A. Business Discovery

| Feature | Current State | Apollo | ZoomInfo | Hunter.io | Priority | Effort | Cost |
|---|---|---|---|---|---|---|---|
| Geospatial SMB discovery (OSM) | ✅ Working | ❌ | ❌ | ❌ | — (advantage) | — | Free |
| B2B corporate database | ❌ Missing | ✅ 250M+ | ✅ 100M+ | ❌ | Low | Very High | Paid |
| Google Places / Google Business API | ❌ Missing | ❌ | ❌ | ❌ | High | Medium | Free quota |
| Yelp / TripAdvisor scraping | ❌ Missing | ❌ | ❌ | ❌ | High | Medium | Free (scraping) |
| Multi-industry batch discovery | ❌ Missing | ✅ | ✅ | ❌ | Medium | Low | Free |
| Country coverage expansion | ✅ Partial | ✅ Global | ✅ Global | ✅ | Medium | Low | Free |
| Keyword-based search refinement | ✅ Supported | ✅ | ✅ | ✅ | — | — | Free |
| Business operating status check | ❌ Missing | ✅ | ✅ | ❌ | Critical | Medium | Free (heuristic) |
| Closed/stale business filtering | ❌ Missing | ✅ | ✅ | ❌ | High | Medium | Free (heuristic) |

---

## B. Contact Discovery

| Feature | Current State | Apollo | ZoomInfo | Hunter.io | Priority | Effort | Cost |
|---|---|---|---|---|---|---|---|
| Homepage email extraction | ✅ Working | ❌ | ❌ | Partial | — | — | Free |
| Contact page crawling (2 subpages) | ✅ Working | ❌ | ❌ | ❌ | — | — | Free |
| Gmail/Yahoo/Hotmail email acceptance | ❌ Bug (blocked) | ✅ | ✅ | ✅ | Critical | Trivial | Free |
| OSM phone number extraction | ✅ Working | ❌ | ❌ | ❌ | — | — | Free |
| Phone number normalization | ❌ Missing | ✅ | ✅ | ❌ | Medium | Low | Free (phonenumbers lib) |
| Domain-based email discovery | ❌ Missing | ✅ | ✅ | ✅ (core) | High | Medium | Free (Hunter free tier) |
| LinkedIn contact scraping | ❌ Missing | ✅ | ✅ | ❌ | Low | High | Paid (or ToS risk) |
| Email pattern guessing (firstname@) | ❌ Missing | ✅ | ✅ | ✅ | Medium | Medium | Free (heuristic) |
| Contact name extraction from site | ❌ Missing | ✅ | ✅ | Partial | Medium | Medium | Free |
| WhatsApp number detection | ❌ Missing | ❌ | ❌ | ❌ | Medium | Low | Free |

---

## C. Email Verification

| Feature | Current State | Apollo | Hunter.io | ZeroBounce | Priority | Effort | Cost |
|---|---|---|---|---|---|---|---|
| Email syntax validation | ✅ Working | ✅ | ✅ | ✅ | — | — | Free |
| Placeholder/vendor domain filtering | ✅ Working | ✅ | ✅ | ✅ | — | — | Free |
| DNS MX record verification | ❌ Missing | ✅ | ✅ | ✅ | Critical | Low (dnspython) | Free |
| Catch-all domain detection | ❌ Missing | ✅ | ✅ | ✅ | High | Medium | Free (SMTP probe) |
| SMTP deliverability probe | ❌ Missing | ✅ | ✅ | ✅ | Medium | Medium | Free (with risks) |
| Email age / freshness tracking | ❌ Missing | ✅ | ❌ | ✅ | Low | Medium | Paid |
| Disposable email detection | ❌ Missing | ✅ | ✅ | ✅ | Medium | Low | Free (open lists) |
| Role-account detection (info@, noreply@) | ✅ Partial (scoring) | ✅ | ✅ | ✅ | — | — | Free |
| Email verification status field | ❌ Missing | ✅ | ✅ | ✅ | High | Low | Free |

---

## D. Website Intelligence

| Feature | Current State | Apollo | Hunter.io | Screaming Frog | Priority | Effort | Cost |
|---|---|---|---|---|---|---|---|
| Website availability check | ✅ Working | ❌ | ❌ | ✅ | — | — | Free |
| HTTPS detection | ✅ Working | ❌ | ❌ | ✅ | — | — | Free |
| Mobile viewport detection | ✅ Working | ❌ | ❌ | ✅ | — | — | Free |
| Contact form detection | ✅ Working | ❌ | ❌ | Partial | — | — | Free |
| Booking widget detection | ✅ Working (30+ signals) | ❌ | ❌ | ❌ | — | — | Free |
| E-commerce signal detection | ✅ Working | ❌ | ❌ | ❌ | — | — | Free |
| Page speed / Core Web Vitals | ❌ Missing | ❌ | ❌ | ✅ | Low | Medium | Free (PageSpeed API) |
| Technology stack detection (Wappalyzer) | ❌ Missing | ✅ (Apollo) | ❌ | ✅ | Medium | Medium | Free (Wappalyzer OSS) |
| Social media profile detection | ❌ Missing | ✅ | ❌ | ❌ | Medium | Low | Free |
| Google Analytics / Tag Manager detection | ❌ Missing | ❌ | ❌ | Partial | Low | Low | Free |
| JavaScript-rendered content (Playwright) | ❌ Missing | N/A | N/A | ✅ | Low | High | Free |
| Last-modified / website freshness | ❌ Missing | ❌ | ❌ | ✅ | Medium | Low | Free |

---

## E. AI Qualification

| Feature | Current State | Apollo | ZoomInfo | Clay | Priority | Effort | Cost |
|---|---|---|---|---|---|---|---|
| Opportunity type classification | ✅ Working (5 types) | Partial | ✅ | ✅ Claygent | — | — | Free (Gemini) |
| Industry-specific prompt adaptation | ❌ Missing | ✅ | ✅ | ✅ | High | Medium | Free (Gemini) |
| Priority calibration (non-inflated) | ❌ Bug (79% High) | ✅ | ✅ | ✅ | Critical | Low | Free |
| Confidence score validation | ❌ Unvalidated | ✅ | ✅ | Partial | Medium | Medium | Free |
| False positive / hallucination guard | ❌ Missing | ✅ | ✅ | ✅ | High | Medium | Free |
| Prompt versioning / A/B testing | ❌ Missing | ✅ | ✅ | ✅ | Low | Low | Free |
| Few-shot examples in prompt | ❌ Missing | N/A | N/A | N/A | Medium | Low | Free |
| Buying intent signals | ❌ Missing | ✅ | ✅ | ✅ | Low | High | Paid (intent data) |
| AI email sequence generation | ❌ Missing | ✅ | ✅ | ✅ | Low | Medium | Free (Gemini) |

---

## F. Lead Scoring

| Feature | Current State | Apollo | ZoomInfo | Priority | Effort | Cost |
|---|---|---|---|---|---|---|
| AI opportunity score (0–100) | ✅ Working | ✅ | ✅ | — | — | Free |
| Score calibration (meaningful distribution) | ❌ Inflated | ✅ | ✅ | Critical | Low | Free |
| Composite verification score | ❌ Missing | ✅ | ✅ | High | Medium | Free |
| Lead quality tier (VERIFIED/REVIEW/REJECTED) | ❌ Missing | ✅ | ✅ | High | Medium | Free |
| Email score contribution | ❌ Missing | ✅ | ✅ | High | Low | Free |
| Website score contribution | ✅ Partial | ✅ | ✅ | — | — | Free |
| Recency / freshness score | ❌ Missing | ✅ | ✅ | Medium | Low | Free |
| Manual score override | ❌ Missing | ✅ | ✅ | Medium | Low | Free |
| Competitor / lookalike scoring | ❌ Missing | ✅ | ✅ | Low | High | Paid |

---

## G. CRM & Data Management

| Feature | Current State | HubSpot | Salesforce | Priority | Effort | Cost |
|---|---|---|---|---|---|---|
| Google Sheets CRM | ✅ Working | — | — | — | — | Free |
| Deduplication by domain | ✅ Working | ✅ | ✅ | — | — | Free |
| Deduplication by name+city | ✅ Working | ✅ | ✅ | — | — | Free |
| Upsert (insert + enrich existing) | ✅ Working | ✅ | ✅ | — | — | Free |
| Persistent SQLite/PostgreSQL database | ❌ Missing | ✅ | ✅ | High | Medium | Free |
| Cross-session search/filter | ❌ Missing | ✅ | ✅ | High | Medium | Free |
| Lead status workflow (New→Contacted→Won) | ❌ Missing | ✅ | ✅ | Medium | Medium | Free |
| CSV / Excel export | ❌ Missing | ✅ | ✅ | Medium | Low | Free |
| Bulk lead import | ❌ Missing | ✅ | ✅ | Low | Low | Free |
| Tags / custom labels | ❌ Missing | ✅ | ✅ | Low | Low | Free |
| Notes / activity log per lead | ❌ Missing | ✅ | ✅ | Low | Medium | Free |
| Native HubSpot / Salesforce integration | ❌ Missing | ✅ | ✅ | Low | High | Paid |

---

## H. Automation & Scheduling

| Feature | Current State | Zapier | n8n | Priority | Effort | Cost |
|---|---|---|---|---|---|---|
| Manual discovery trigger (API + UI) | ✅ Working | — | — | — | — | Free |
| Scheduled automated discovery (cron) | ❌ Missing | ✅ | ✅ | High | Low | Free (APScheduler) |
| Background job queue | ❌ Missing | ✅ | ✅ | Medium | Medium | Free (Celery/RQ) |
| Multi-job concurrency | ❌ Missing | ✅ | ✅ | Medium | Medium | Free |
| Webhook outbound (notify on completion) | ❌ Missing | ✅ | ✅ | Medium | Low | Free |
| Email notification on completion | ❌ Missing | ✅ | ✅ | Medium | Low | Free (SMTP) |
| Re-enrichment of stale leads | ❌ Missing | ✅ | ✅ | Medium | Medium | Free |
| Zapier integration | ❌ Missing | — | — | Low | Medium | Paid |

---

## I. Monitoring & Reliability

| Feature | Current State | Datadog | Sentry | Priority | Effort | Cost |
|---|---|---|---|---|---|---|
| Structured JSON logging | ❌ Missing | ✅ | ✅ | High | Low | Free |
| Health endpoint | ✅ Working (/health) | — | — | — | — | Free |
| Prometheus metrics | ❌ Missing | ✅ | — | Medium | Low | Free |
| Error tracking (Sentry-style) | ❌ Missing | ✅ | ✅ | Medium | Low | Free (Sentry OSS) |
| API rate limit tracking | ❌ Missing | ✅ | — | Medium | Low | Free |
| Discovery success/failure rate | ❌ Missing | ✅ | — | High | Low | Free |
| Email extraction rate tracking | ❌ Missing | ✅ | — | High | Low | Free |
| Alerting on job failures | ❌ Missing | ✅ | ✅ | Medium | Medium | Free (email/webhook) |
| Uptime monitoring | ❌ Missing | ✅ | — | Medium | Low | Free (UptimeRobot) |
| Docker health check | ✅ Working | — | — | — | — | Free |

---

## J. Security

| Feature | Current State | Best Practice | Priority | Effort | Cost |
|---|---|---|---|---|---|
| SSRF defense (DNS-level) | ✅ Excellent | ✅ Required | — | — | Free |
| Security headers | ✅ Working | ✅ Required | — | — | Free |
| API authentication (optional) | ⚠️ Disabled by default | ✅ Required | Critical | Trivial | Free |
| Rate limiting on API endpoints | ❌ Missing | ✅ Required | High | Low | Free (slowapi) |
| HTTPS / TLS in production | ❌ Requires reverse proxy | ✅ Required | High | Low | Free (Let's Encrypt) |
| Input sanitization | ⚠️ Pydantic only | ✅ Required | Medium | Low | Free |
| Secrets scanning (CI) | ❌ Missing | ✅ Required | Medium | Low | Free (truffleHog) |
| GDPR / Privacy policy | ❌ Missing | ✅ Required | Medium | Medium | Free (documentation) |
| SQL injection protection | N/A (no SQL) | — | — | — | — |

---

## Priority Summary

| Priority | Features | Count |
|---|---|---|
| **Critical** | Gmail email fix, MX verification, priority calibration, API auth enabled | 4 |
| **High** | Lead verification tiers, persistent DB, structured logging, rate limiting, operating status check, domain email discovery | ~15 |
| **Medium** | Phone validation, social media detection, tech stack detection, scheduling, webhook notifications, CSV export | ~20 |
| **Low** | LinkedIn enrichment, email sequences, Zapier integration, B2B corporate database | ~10 |

---

## Features Buildable at ₹0

| Feature | Library / Method |
|---|---|
| MX record verification | `dnspython` |
| Gmail/personal email acceptance | Config change (1 line) |
| Phone normalization | `phonenumbers` |
| Technology stack detection | `Wappalyzer` (OSS version) |
| Social media link detection | HTML parsing |
| Automated scheduling | `APScheduler` |
| Rate limiting | `slowapi` |
| Structured logging | Python `logging.Formatter` JSON |
| Prometheus metrics | `prometheus-fastapi-instrumentator` |
| SQLite database | `SQLAlchemy` + `aiosqlite` |
| CSV export | `csv` stdlib |
| Priority calibration | Config/scoring change |
| Lead verification tiers | Business logic + schema change |

---

*All features verified against actual codebase inspection. "Working" means code exists and passes tests. "Missing" means no implementation found.*
