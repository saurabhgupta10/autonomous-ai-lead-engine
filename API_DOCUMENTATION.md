# API Documentation

The **Autonomous AI-Powered Lead Generation & Enrichment Engine** provides a RESTful API powered by FastAPI with OpenAPI 3.1 documentation, strict Pydantic v2 validation, security headers middleware, and optional Bearer token authentication.

Interactive Swagger Docs: `http://localhost:8000/docs`  
ReDoc: `http://localhost:8000/redoc`

---

## Security & Authentication

### Security Headers Middleware
Every response includes:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`

### Bearer Token Authentication
When `API_BEARER_TOKEN` is configured in `Backend/.env`, all mutating endpoints (`POST /api/scan`, `POST /api/discovery/start`) and data export endpoints require the `Authorization` header:

```http
Authorization: Bearer <API_BEARER_TOKEN>
```
If no token is configured, the API operates in open local development mode.

---

## Endpoints Summary

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health` | System liveness, Gemini model, Sheets connectivity | No |
| `GET` | `/api/leads` | Read enriched leads from Google Sheets CRM | If Token Set |
| `POST` | `/api/scan` | Trigger direct URL directory scraper job | If Token Set |
| `GET` | `/api/scan/status` | Poll direct URL scraper job status | If Token Set |
| `POST` | `/api/discovery/start` | Trigger autonomous OpenStreetMap B2B discovery | If Token Set |
| `GET` | `/api/discovery/status` | Poll discovery job status & stage metrics | If Token Set |
| `GET` | `/api/discovery/results` | Retrieve leads from latest discovery run | If Token Set |
| `GET` | `/api/discovery/history` | Historical summary of discovery sessions | If Token Set |

---

## Detailed Endpoint Specifications

### 1. Health Check
`GET /health`

**Response `200 OK`:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "environment": "production",
  "integrations": {
    "gemini": {
      "status": "connected",
      "model": "gemini-flash-lite-latest"
    },
    "google_sheets": {
      "status": "connected",
      "configured": true
    },
    "osm_discovery": {
      "status": "ready",
      "provider": "OpenStreetMap Overpass + Nominatim"
    }
  },
  "auth_required": false
}
```

---

### 2. Autonomous Discovery

#### Start Discovery Job
`POST /api/discovery/start`

Initiates autonomous business discovery via OpenStreetMap Overpass/Nominatim, crawls discovered websites (with hop-by-hop SSRF validation), extracts contact emails/phones, runs Gemini opportunity qualification, and synchronizes to Google Sheets.

**Request Body:**
```json
{
  "country": "USA",
  "city": "New York",
  "industry": "Restaurants",
  "category": "amenity=restaurant",
  "keyword": "bistro",
  "max_results": 25
}
```

**Response `202 Accepted`:**
```json
{
  "status": "accepted",
  "session_id": "a1b2c3d4",
  "message": "Autonomous discovery started for Restaurants in New York, USA."
}
```

**Response `409 Conflict` (Job in progress):**
```json
{
  "detail": "A discovery session is already in progress. Poll /api/discovery/status."
}
```

#### Poll Discovery Status
`GET /api/discovery/status`

**Response `200 OK` (During Execution):**
```json
{
  "session_id": "a1b2c3d4",
  "status": "running",
  "started_at": "2026-11-13T02:00:00Z",
  "finished_at": null,
  "error": null,
  "summary": {
    "stage": "auditing_websites",
    "query": {
      "country": "USA",
      "city": "New York",
      "industry": "Restaurants",
      "max_results": 25
    }
  }
}
```

**Response `200 OK` (Completed):**
```json
{
  "session_id": "a1b2c3d4",
  "status": "complete",
  "started_at": "2026-11-13T02:00:00Z",
  "finished_at": "2026-11-13T02:00:35Z",
  "error": null,
  "summary": {
    "stage": "finished",
    "total_discovered": 10,
    "high_priority_count": 7,
    "duplicates_skipped": 0,
    "crm_synced": 10,
    "crm_status": "synced"
  }
}
```

#### Get Discovered Results
`GET /api/discovery/results`

**Response `200 OK`:**
```json
[
  {
    "name": "Hudson Clearwater",
    "category": "restaurant",
    "city": "New York",
    "country": "USA",
    "website": "https://www.hudsonclearwater.com",
    "email": "info@hudsonclearwater.com",
    "phone": "+1 212-989-3255",
    "priority": "High",
    "opportunity": "Modernize online reservation flow and improve mobile responsiveness.",
    "source_url": "https://www.openstreetmap.org/node/12345678",
    "crawler_status": "success",
    "discovered_at": "2026-11-13T02:00:15Z"
  }
]
```

---

### 3. CRM Lead Retrieval
`GET /api/leads`

Returns verified leads from the connected Google Sheet.

**Response `200 OK`:**
```json
{
  "leads": [
    {
      "Company Name": "Hudson Clearwater",
      "Website": "https://www.hudsonclearwater.com",
      "Email": "info@hudsonclearwater.com",
      "Phone": "+1 212-989-3255",
      "Lead Priority": "High",
      "Opportunity Angle": "Modernize online reservation flow and improve mobile responsiveness.",
      "Source URL": "https://www.openstreetmap.org/node/12345678"
    }
  ],
  "total": 14,
  "high_priority_count": 10
}
```

---

### 4. Direct URL Scraper Pipeline
`POST /api/scan`

Scrapes direct HTML directories or pages supplied by the user, runs AI lead scoring, and appends to Google Sheets.

**Security Constraints:**
- Blocks loopback, private RFC-1918 IPs, link-local, multicast, and AWS/GCP cloud metadata IP `169.254.169.254`.
- Enforces maximum response limit of 500 KB.

**Request Body:**
```json
{
  "source_urls": ["https://example.com/business-directory"],
  "dry_run": false
}
```

**Response `202 Accepted`:**
```json
{
  "job_id": "c7d8e9f0",
  "status": "accepted",
  "message": "Scan job initiated."
}
```
