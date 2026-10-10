# Autonomous AI-Powered Lead Generation & Enrichment Engine

An enterprise-grade, full-stack automation pipeline that extracts raw business data from web directories, scores prospects using advanced AI models, and automatically streams qualified sales leads into both a cloud-based Google Sheets CRM and a premium React analytics dashboard.

---

## ⚡ The Business Value (For Clients)

### The Problem
Sales and marketing teams spend over **20+ manual hours every week** manually looking up business directories, copying emails, and guessing which companies are a good fit for their services. This is slow, repetitive, and expensive.

### The Solution
This automation engine completely eliminates manual outreach research, driving a **90% operational efficiency gain**:
* **Instant Extraction:** Automatically parses hundreds of target business listings in under 5 seconds.
* **Intelligent AI Filtering:** Uses **Gemini 3.5-Flash / 3.5-Flash** models to evaluate each business type and filter out low-value prospects automatically.
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

lead-gen-engine/                 # 💎 Main Root Project Directory
├── .gitignore                   # Main rule file to block credentials upload
├── README.md                    # Professional documentation for clients & devs
│
├── Backend/                     # 🐍 Robust Python Automation Engine
│   ├── .env                     # Private storage (Gemini API Key, Google Sheet ID)
│   ├── .env.example             # Safe template placeholder file for deployment
│   ├── api.py                   # FastAPI Live Server with async caching gateway
│   ├── main.py                  # Core pipeline manager (scrapes → AI scores → pushes)
│   ├── ai_filter.py             # Custom Gemini 3.5-Flash text evaluation engine
│   ├── scraper.py               # BeautifulSoup4 high-speed directory parser
│   ├── sheet_manager.py         # Google Sheets Cloud gspread connector scripts
│   ├── requirements.txt         # Package dependency manifest (fastapi, google-genai)
│   │
│   ├── credentials/             # 🔒 Cryptographic Access Vault
│   │   ├── .gitkeep             # Ensures folder tracking without exposing raw keys
│   │   └── service_account.json # Private Google Service Account IAM Secret Key
│   │
│   └── data/                    # Local Sandbox Environment
│       └── mock_leads.html      # Local HTML baseline for automated testing
│
└── Frontend/                    # ⚛️ Next.js Enterprise SaaS Analytics Dashboard
    ├── package.json             # Application scripts scheduler & package configs
    ├── tsconfig.json            # Strict TypeScript architectural definitions
    ├── postcss.config.mjs       # CSS style compilers configuration file
    ├── tailwind.config.mjs      # Premium UI custom color framework layouts
    ├── next.config.mjs          # Next.js engine runtime settings controller
    ├── components.json          # Modern Shadcn UI component trackers layout
    ├── .gitignore               # Frontend local modules protection parameters
    └── .next/                   # Next.js production compiler automated cache


---

## 🚀 How to Run the Project Locally

### 1. Fire Up the Backend API Server
Ensure your python virtual environment (`.venv`) is activated:
```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload
```
*The live API server will start broadcasting raw data at `http://localhost:8000/api/leads`.*

### 2. Launch the Frontend Dashboard View
Open a new terminal tab and install Node dependencies:
```bash
cd frontend
npm install
npm run dev
```
*Click the local URL generated in your terminal (usually `http://localhost:3000`) to view the interactive live tracking workspace!*

---

## 🔒 Security Policy
All cryptographic private keys, Google Cloud IAM credential files (`service_account.json`), and system `.env` environmental variables are strictly locked via a project-wide `.gitignore` manifest. Secret configurations are never exposed to public repositories.
