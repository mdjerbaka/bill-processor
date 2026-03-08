# Bill Processor

Automated invoice processing for construction companies. Polls email for bills, extracts data via OCR, matches to jobs, and optionally syncs to QuickBooks Online.

## Features

- **Email Polling** — Monitors an IMAP mailbox (Gmail / Outlook) for incoming invoices
- **OCR Extraction** — Extracts vendor, amounts, line items via OpenAI Vision, Azure Doc Intelligence, or AWS Textract
- **Job Matching** — Learns vendor → job mappings and auto-assigns future invoices
- **Payables Dashboard** — Track outstanding bills, bank balance, and "real available" cash
- **QuickBooks Online** — OAuth 2.0 integration to send approved bills as QBO Bills
- **Multi-Provider OCR** — Swap OCR providers from the Settings page without redeploying

## Tech Stack

| Layer     | Technology |
|-----------|------------|
| Backend   | FastAPI 0.115, Python 3.12, SQLAlchemy 2.0 (async) |
| Frontend  | React 18, Vite 6, Tailwind CSS 3 |
| Database  | PostgreSQL 17 (Neon recommended) |
| Queue     | Redis 7 + ARQ worker |
| Auth      | JWT (python-jose) + bcrypt + Fernet encryption |
| Deploy    | Docker Compose, Railway.app (or any VPS) |

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.9+ and Node.js 18+
- Docker & Docker Compose (for Redis)
- A Neon Postgres database (free tier works): https://neon.tech

### 1. Clone & configure

```bash
git clone <your-repo-url> bill-processor
cd bill-processor
cp .env.example .env
```

Edit `.env` and fill in the three **required** values:

```dotenv
DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname?ssl=require
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
ENCRYPTION_KEY=<run: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
```

### 2. Start Redis

```bash
docker compose up redis -d
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In a second terminal, start the background worker:

```bash
cd backend
arq app.workers.worker.WorkerSettings
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

### 5. Initial setup

Open http://localhost:5173 — you'll see the Setup Wizard.

1. Create your admin username & password  
2. Configure Email (IMAP) settings for the mailbox to poll  
3. Configure an OCR provider (OpenAI recommended)  
4. Done! Incoming emails will be polled automatically every minute.

---

## Running Tests

```bash
cd backend
pip install pytest pytest-asyncio aiosqlite httpx
python -m pytest tests/ -v
```

Tests use an in-memory SQLite database — no external services required.  
**78 tests** covering auth, invoices, jobs, payables, settings, QuickBooks, and service logic.

---

## Docker Compose (Full Stack)

### Development

```bash
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| API      | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

### Production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Differences from dev: no source volume mounts, 2 uvicorn workers, JSON log rotation, persistent Redis volume.

---

## Deploying to Railway.app

Railway is the recommended hosting platform. You'll create 4 services from one repo:

### 1. Create a Railway project

- Go to https://railway.app and create a **New Project**
- Connect your GitHub repo

### 2. Add a Neon database

- In your Neon dashboard, copy the connection string
- In Railway, add a variable `DATABASE_URL` with the Neon URL  
  (change `postgresql://` to `postgresql+asyncpg://` in the scheme)

### 3. Add Redis

- Railway → **New** → **Database** → **Redis**
- Copy the `REDIS_URL` from the Redis service's Variables tab

### 4. Create services

Create **3 services** from the same GitHub repo:

#### API Service
- **Root Directory**: `backend`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Variables**: all values from `.env.example`, plus `PORT` (Railway sets this)
- Generate a public domain (e.g., `api-billprocessor.up.railway.app`)

#### Worker Service
- **Root Directory**: `backend`
- **Start Command**: `arq app.workers.worker.WorkerSettings`
- **Variables**: same as API service (copy the variable group)

#### Frontend Service
- **Root Directory**: `frontend`
- **Build Command**: `npm run build`
- Uses the Dockerfile (nginx)
- Generate a public domain

### 5. Configure API URL in frontend

Before building frontend, set the `VITE_API_URL` env var to your Railway API domain:

```
VITE_API_URL=https://api-billprocessor.up.railway.app/api/v1
```

### 6. Generate secrets

```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add both to the API and Worker service variables.

### 7. Update QBO callback URL

If using QuickBooks, update `QBO_REDIRECT_URI` to:
```
https://api-billprocessor.up.railway.app/api/v1/quickbooks/callback
```

---

## QuickBooks Online Setup

### 1. Create a Developer Account

- Go to https://developer.intuit.com
- Sign in or create an account
- Click **Dashboard** → **Create an app** → **QuickBooks Online and Payments**

### 2. Get Credentials

- In your app's **Keys & credentials** tab:
  - Copy **Client ID** → `QBO_CLIENT_ID`
  - Copy **Client Secret** → `QBO_CLIENT_SECRET`

### 3. Set Redirect URI

- Under **Redirect URIs**, add:
  - Local: `http://localhost:8000/api/v1/quickbooks/callback`
  - Production: `https://your-api-domain/api/v1/quickbooks/callback`

### 4. Connect in the App

- Go to **Settings** in the Bill Processor UI
- Click **Connect QuickBooks** → authorize in the Intuit popup
- Once connected, approved invoices can be sent to QBO as Bills

### 5. Switch to Production

- In the Intuit Developer portal, submit your app for review (or use development keys for personal use)
- Change `QBO_ENVIRONMENT=production` in your `.env`

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/setup` | No | Create initial admin user |
| GET | `/api/v1/auth/setup-status` | No | Check if setup is complete |
| POST | `/api/v1/auth/login` | No | Login (returns JWT) |
| GET | `/api/v1/invoices` | Yes | List invoices (paginated, filterable) |
| GET | `/api/v1/invoices/:id` | Yes | Get invoice detail + line items |
| PUT | `/api/v1/invoices/:id` | Yes | Update invoice fields |
| POST | `/api/v1/invoices/:id/approve` | Yes | Approve → creates payable |
| POST | `/api/v1/invoices/:id/mark-paid` | Yes | Mark as paid |
| GET | `/api/v1/jobs` | Yes | List jobs |
| POST | `/api/v1/jobs` | Yes | Create job |
| PUT | `/api/v1/jobs/:id` | Yes | Update job |
| DELETE | `/api/v1/jobs/:id` | Yes | Soft-delete (deactivate) |
| POST | `/api/v1/jobs/import-csv` | Yes | Import jobs from CSV |
| GET | `/api/v1/jobs/vendor-mappings` | Yes | List vendor → job mappings |
| POST | `/api/v1/jobs/vendor-mappings` | Yes | Create mapping |
| DELETE | `/api/v1/jobs/vendor-mappings/:id` | Yes | Delete mapping |
| GET | `/api/v1/payables` | Yes | List payables |
| POST | `/api/v1/payables/:id/mark-paid` | Yes | Mark payable as paid |
| POST | `/api/v1/payables/bank-balance` | Yes | Set bank balance |
| GET | `/api/v1/payables/real-balance` | Yes | Get real available balance |
| GET | `/api/v1/payables/export` | Yes | Export payables CSV |
| GET/POST | `/api/v1/settings/email` | Yes | Email (IMAP) config |
| POST | `/api/v1/settings/email/test` | Yes | Test email connection |
| GET/POST | `/api/v1/settings/ocr` | Yes | OCR provider config |
| POST | `/api/v1/settings/ocr/test` | Yes | Test OCR provider |
| GET | `/api/v1/quickbooks/connect` | Yes | Get QBO OAuth URL |
| GET | `/api/v1/quickbooks/callback` | No | QBO OAuth callback |
| GET | `/api/v1/quickbooks/status` | Yes | Check QBO connection |
| POST | `/api/v1/quickbooks/disconnect` | Yes | Remove QBO tokens |
| GET | `/api/v1/quickbooks/vendors` | Yes | List QBO vendors |
| GET | `/api/v1/quickbooks/accounts` | Yes | List QBO accounts |
| POST | `/api/v1/quickbooks/send-bill/:id` | Yes | Send invoice to QBO |
| GET | `/api/v1/health` | No | System health check |

---

## Project Structure

```
bill-processor/
├── docker-compose.yml          # Dev stack
├── docker-compose.prod.yml     # Production overrides
├── .env.example                # Environment template
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app + health check
│   │   ├── api/                # Route handlers
│   │   ├── core/               # Config, DB, security
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic
│   │   └── workers/            # ARQ background worker
│   ├── tests/                  # 78 pytest tests
│   ├── alembic/                # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── pages/              # React page components
    │   ├── components/         # Shared components
    │   ├── hooks/              # Auth hook
    │   └── services/           # Axios API client
    ├── Dockerfile
    └── package.json
```

---

## License

Private — all rights reserved.
