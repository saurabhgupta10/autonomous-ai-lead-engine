# Production Deployment Guide

This guide covers production deployment strategies for the **Autonomous AI-Powered Lead Generation & Enrichment Engine**, including Docker containerization, cloud PaaS deployment, and scaling strategies for web intelligence providers.

---

## 1. Containerized Deployment (Docker Compose)

The repository provides a multi-container Docker configuration with healthchecks, non-root user execution, and volume persistence.

### 1.1 Prerequisites
- Docker Engine 24.0+ & Docker Compose v2.20+
- GCP Service Account JSON in `Backend/credentials/service_account.json`
- `.env` file populated with secrets in repository root

### 1.2 Configuration
Create a `.env` file at the root:
```ini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-flash-lite-latest
SPREADSHEET_ID=your_spreadsheet_id
API_BEARER_TOKEN=generate_a_secure_token
OSM_CONTACT_EMAIL=admin@yourdomain.com
```

### 1.3 Build and Launch
```bash
docker compose up -d --build
```

Check status and logs:
```bash
docker compose ps
docker compose logs -f backend
```

- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **Healthcheck:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 2. Cloud Platform Deployment (Render / Railway / Fly.io)

### 2.1 Backend Deployment (FastAPI)
The backend includes a `Procfile` for containerless or containerized PaaS runtimes:
```
web: uvicorn Backend.api:app --host 0.0.0.0 --port $PORT
```

**Required Environment Variables on PaaS:**
- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-flash-lite-latest`
- `SPREADSHEET_ID`
- `SERVICE_ACCOUNT_FILE=/etc/secrets/service_account.json` (or mounted Secret File)
- `API_BEARER_TOKEN` (strongly recommended in public cloud)
- `ALLOWED_ORIGINS=https://your-frontend-domain.com`
- `OSM_CONTACT_EMAIL=ops@yourdomain.com`

### 2.2 Frontend Deployment (Vercel / Netlify / Render)
Deploy the `Frontend` directory as a Next.js application:
- Build command: `npm run build`
- Output directory: `.next`
- Node version: `20.x`
- Environment variables:
  - `NEXT_PUBLIC_API_URL=https://your-backend-api.onrender.com`
  - `NEXT_PUBLIC_API_TOKEN=your_secure_token`

---

## 3. Web Intelligence Provider Scaling & OSM Policy Compliance

### 3.1 Public OpenStreetMap Policy
The default discovery engine uses the public Overpass API and Nominatim servers under Open Database License (ODbL):
- Enforces strict <= 1 request/second rate-limiting.
- Uses persistent disk caching (`CACHE_TTL_HOURS=24`) to eliminate duplicate queries.
- Sends identifying `User-Agent` and `From` contact headers.
- Automatically fails over between multiple Overpass public mirrors.

### 3.2 Enterprise Scaling Options
Public OSM infrastructure is intended for moderate community workloads and not high-volume harvesting. For enterprise scale:

1. **Self-Hosted Overpass API:**
   Deploy a dedicated Overpass Docker container using `wiktorn/overpass-api`:
   ```bash
   docker run -d --name overpass -p 8088:80 -v /data/overpass:/db wiktorn/overpass-api
   ```
   Set mirror in `Backend/discovery/overpass_provider.py`:
   `http://localhost:8088/api/interpreter`

2. **Commercial Provider Adapters:**
   The `DiscoveryService` is built on a modular provider interface. Plug-and-play adapters can be registered for:
   - Google Places API (New)
   - Yelp Fusion API
   - Outscraper / TomTom Business Search
