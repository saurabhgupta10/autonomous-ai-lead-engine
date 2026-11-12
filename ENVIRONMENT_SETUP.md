# Environment Setup Guide

This guide walks through configuring and running the **Autonomous AI-Powered Lead Generation & Enrichment Engine** on a local development machine or production host.

---

## Prerequisites

- **Python 3.10+** (Python 3.11 recommended)
- **Node.js 18+** (Node.js 20 LTS recommended)
- **Git**
- **Google Cloud Platform Project** with Google Sheets API enabled & Service Account JSON credentials.
- **Google Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/)).

---

## 1. Backend Setup

### 1.1 Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
cd Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
cd Backend
python3 -m venv .venv
source .venv/bin/activate
```

### 1.2 Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Verified core dependencies include:
- `fastapi` & `uvicorn[standard]`
- `google-genai` (official modern SDK)
- `gspread` & `google-auth`
- `pydantic` & `pydantic-settings`
- `requests` & `beautifulsoup4`
- `dnspython` (for SSRF DNS resolution defense)

### 1.3 Configure Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `Backend/.env` with your actual credentials:
```ini
# Google Gemini AI Integration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-flash-lite-latest

# Google Sheets CRM Integration
SPREADSHEET_ID=your_google_sheet_id_here
SHEET_NAME=Sheet1
SERVICE_ACCOUNT_FILE=credentials/service_account.json

# Security & Access Control
API_BEARER_TOKEN=your_secure_random_token_here
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# OpenStreetMap & Web Intelligence
OSM_USER_AGENT=AutonomousLeadEngine/2.0
OSM_CONTACT_EMAIL=admin@yourdomain.com
CACHE_DIR=data/cache
CACHE_TTL_HOURS=24
```

### 1.4 Place Google Service Account Credentials

Ensure your Service Account JSON is saved at:
`Backend/credentials/service_account.json`

Ensure the target Google Sheet is shared with the client email address in `service_account.json` with **Editor** permissions.

### 1.5 Start the Backend Server

```bash
uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

Verify backend health at: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 2. Frontend Setup

### 2.1 Install Node Dependencies

```bash
cd ../Frontend
npm install
```

### 2.2 Configure Frontend Environment

Create `Frontend/.env.local`:
```ini
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
# Optional: API bearer token if required by backend configuration
# NEXT_PUBLIC_API_TOKEN=your_secure_random_token_here
```

### 2.3 Start Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 3. Production Verification Commands

Run unit & discovery tests:
```bash
cd Backend
python -m pytest test_phase5.py -v
```

Verify Next.js production build:
```bash
cd ../Frontend
npm run build
```
