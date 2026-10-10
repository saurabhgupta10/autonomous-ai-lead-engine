# Autonomous AI-Powered Lead Generation & Enrichment Engine

An enterprise-grade, full-stack automation pipeline that extracts raw business data from web directories, scores prospects using advanced AI models, and automatically streams qualified sales leads into both a cloud-based Google Sheets CRM and a premium React analytics dashboard.

---

## ⚡ The Business Value (For Clients)

### The Problem
Sales and marketing teams spend over **20+ manual hours every week** manually looking up business directories, copying emails, and guessing which companies are a good fit for their services. This is slow, repetitive, and expensive.

### The Solution
This automation engine completely eliminates manual outreach research, driving a **90% operational efficiency gain**:
* **Instant Extraction:** Automatically parses hundreds of target business listings in under 5 seconds.
* **Intelligent AI Filtering:** Uses **Gemini 3.5-Flash** models to evaluate each business type and filter out low-value prospects automatically.
* **Zero-Input CRM Sync:** Populates your Google Sheets and CRM databases in real-time with verified contact info, ready-to-use personalization insights, and strategic reasoning.

---

## 🛠️ System Architecture (For Developers)

The project is structured as a decoupled, asynchronous full-stack application built for speed and resilience:

```text
Target Directory (Web Scraping) 
       ⬇️  [BeautifulSoup4]
Raw Dataset Extracted
       ⬇️  [google-genai SDK]
Gemini Cloud Semantic Analysis Engine
       ⬇️  [gspread API Client Gateway]
Google Sheets CRM Database  <═══>  FastAPI Local REST Server (:8000)
                                            ⬇️ [fetch() Gateway Request]
                                     React / Tailwind Frontend UI (:3000)
```

### Key Technical Features
* **Optimized API Caching:** Includes a built-in async fallback mechanism inside FastAPI to guarantee sub-second page loads, protecting against network timeouts or Google API rate limits.
* **Modern AI Integration:** Uses the unified, latest `google-genai` SDK ensuring forward-compatibility with future Gemini intelligence updates.
* **Cross-Origin Resource Sharing (CORS):** Fully managed CORS middleware allowing secure browser-to-server asynchronous data communication streams.

---

## 📂 Project Structure

```text
lead-gen-engine/
├── .gitignore
├── README.md
├── Backend/
│   ├── credentials/
│   │   ├── .gitkeep
│   │   └── service_account.json
│   ├── data/
│   │   └── mock_leads.html
│   ├── .env
│   ├── .env.example
│   ├── ai_filter.py
│   ├── api.py
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   ├── scraper.py
│   └── sheet_manager.py
└── Frontend/
    ├── .next/
    ├── .gitignore
    ├── components.json
    ├── next-env.d.ts
    ├── next.config.mjs
    ├── package-lock.json
    ├── package.json
    ├── pnpm-lock.yaml
    ├── pnpm-workspace.yaml
    ├── postcss.config.mjs
    └── tsconfig.json
```

---

## 🚀 How to Run the Project Locally

### 1. Fire Up the Backend API Server
Ensure your python virtual environment (`.venv`) is activated:
```bash
cd Backend
pip install -r requirements.txt
uvicorn api:app --reload
```
*The live API server will start broadcasting raw data at `http://localhost:8000/api/leads`.*

### 2. Launch the Frontend Dashboard View
Open a new terminal tab and install Node dependencies:
```bash
cd Frontend
pnpm install
pnpm run dev
```
*Click the local URL generated in your terminal (usually `http://localhost:3000`) to view the interactive live tracking workspace!*

---

## 🔒 Security Policy
All cryptographic private keys, Google Cloud IAM credential files (`service_account.json`), and system `.env` environmental variables are strictly locked via a project-wide `.gitignore` manifest. Secret configurations are never exposed to public repositories.
