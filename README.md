# Autonomous AI-Powered Lead Generation & Enrichment Engine

An enterprise-grade, autonomous B2B lead discovery, intelligence enrichment, and CRM qualification platform.

The system combines global OpenStreetMap geospatial business search, deep automated website intelligence auditing, Gemini multimodal opportunity qualification, and zero-loss Google Sheets CRM synchronization inside a Next.js analytics dashboard.

---

## ⚡ Core Capabilities

1. **Autonomous Geospatial Discovery:** Discovers real-world businesses across any country, city, and industry using OpenStreetMap Overpass API and Nominatim directory indexing without paid third-party APIs.
2. **Deep Website Intelligence & Opportunity Auditing:** Automatically audits discovered business websites for mobile responsiveness, meta tags, social links, booking widgets, modern frameworks, and SSL status. Businesses without websites are automatically flagged for high-value web development outreach.
3. **SSRF Defense-in-Depth:** Features hop-by-hop redirect verification, DNS-level IP filtering blocking private RFC-1918 networks, loopbacks, link-local addresses, and cloud instance metadata (`169.254.169.254`), with strict 500 KB response caps.
4. **Gemini AI Opportunity Qualification:** Evaluates extracted business data and web audit findings using Google Gemini (`gemini-flash-lite-latest`), assigning High/Medium/Low priority ratings with strategic agency pitch angles.
5. **Resilient CRM Sync & Deduplication:** Synchronizes qualified leads into Google Sheets with exponential backoff retry wrappers and persistent duplicate detection across discovery runs.
6. **Dual-View Next.js Dashboard:** Toggle effortlessly between All CRM Leads and Latest Batch Leads, filter by priority, search by keyword, view live stage polling, and inspect verifiable OpenStreetMap node/way source links.

---

## 🛠️ Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Next.js 16.4 Dashboard (:3000)                       │
│      [Live Stage Polling] [Dual View] [Filter] [Search] [OSM Links]     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ HTTP / JSON
┌──────────────────────────────────▼─────────────────────────────────────┐
│                       FastAPI Backend (:8000)                          │
│   [Security Headers] [Token Auth] [CORS] [Background Job Lock]         │
└──────┬───────────────────────────┬───────────────────────────────┬─────┘
       │                           │                               │
       ▼                           ▼                               ▼
┌──────────────────┐     ┌──────────────────┐            ┌──────────────────┐
│  OSM Discovery   │     │ Crawler & Audit  │            │  Gemini Scoring  │
│ Overpass API     │     │ SSRF Hop Defense │            │ gemini-flash-    │
│ Nominatim Index  │     │ 500 KB Limit     │            │ lite-latest      │
│ 24h JSON Cache   │     │ HTML Signals     │            │ Strategy Pitch   │
└──────────────────┘     └──────────────────┘            └──────────────────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │ Google Sheets    │
                         │ Exponential      │
                         │ Backoff Retry    │
                         │ Deduplication    │
                         └──────────────────┘
```

---

## 🚀 Quick Start

### 1. Backend Setup
```bash
cd Backend
python -m venv .venv
source .venv/bin/activate  # Or .\.venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
cp .env.example .env       # Configure GEMINI_API_KEY and SPREADSHEET_ID
uvicorn api:app --reload
```

### 2. Frontend Setup
```bash
cd Frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to launch the autonomous discovery platform.

---

## 🔒 Security Hardening

- **SSRF Immunity:** Direct IP check via `crawler.py` before and after every redirect hop.
- **API Token Authentication:** Optional `API_BEARER_TOKEN` authorization header protection.
- **Security Headers:** Enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.
- **Zero Secret Leakage:** Service account credentials and API keys are strictly confined to backend environments.
- **Safe Outgoing Outreach:** The platform strictly qualifies leads and prepares strategic pitches; it never transmits automated emails, WhatsApp messages, or spam outreach.

---

## 📚 Documentation Links

- [Environment Setup Guide](ENVIRONMENT_SETUP.md)
- [API Documentation & OpenAPI Specs](API_DOCUMENTATION.md)
- [Production Deployment Guide (Docker & Cloud)](DEPLOYMENT.md)

---

## 📜 OpenStreetMap Attribution & Licensing
Data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), licensed under the Open Database License (ODbL). All discovered records include canonical OpenStreetMap source URLs.
