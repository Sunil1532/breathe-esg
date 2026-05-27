# Breathe ESG — Emissions Ingestion Platform

A Django REST + React prototype for ingesting, normalizing, and reviewing emissions data from three enterprise sources: SAP fuel/procurement, utility electricity, and corporate travel.

## Live Demo

> Deploy to Render using the steps below. Share the URL with evaluators.

**Demo credentials** (created by `create_demo_data` command):
- Analyst: `analyst` / `analyst123`
- Admin: `admin_user` / `admin123`

## Sample data files

Located in `backend/sample_data/`:
- `sap_fuel_procurement.csv` — SAP MB51 export, semicolon-delimited, German headers
- `utility_electricity.csv` — Utility portal CSV with meter readings
- `travel_concur.csv` — Concur-style travel segment CSV

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### 1. Clone and set up backend

```bash
git clone <your-repo-url>
cd breathe-esg/backend

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp ../.env.example .env           # edit as needed
python manage.py migrate
python manage.py create_demo_data
python manage.py runserver
```

The Django API will be available at `http://localhost:8000`.

### 2. Set up and run frontend

```bash
cd ../frontend
npm install
npm run dev
```

The React app will be at `http://localhost:5173` (proxies API calls to Django).

### 3. Upload sample data

1. Log in as `analyst` / `analyst123`
2. Go to **Ingest** → upload files from `backend/sample_data/`
3. Go to **Review** → approve or reject records

---

## Deployment on Render

### One-click setup

1. Fork this repo to your GitHub account
2. Create a new **Web Service** on [Render](https://render.com):
   - **Root directory**: `backend`
   - **Build command**: see below
   - **Start command**: `gunicorn breathe_esg.wsgi:application`
3. Add environment variables (see below)
4. Add a **PostgreSQL** database via Render's Add-on

Alternatively, use `render.yaml` at the repo root for automatic configuration.

### Build command

```bash
pip install -r requirements.txt && \
cd ../frontend && npm install && npm run build && \
cp -r dist/* ../backend/staticfiles/frontend/ && \
cd ../backend && python manage.py collectstatic --no-input && \
python manage.py migrate && \
python manage.py create_demo_data
```

### Environment variables (Render)

| Variable | Value |
|---|---|
| `SECRET_KEY` | Generate with `python -c "import secrets; print(secrets.token_hex(50))"` |
| `DEBUG` | `False` |
| `DATABASE_URL` | Auto-populated by Render PostgreSQL add-on |
| `ALLOWED_HOSTS` | Your Render domain (e.g. `my-app.onrender.com`) |
| `DEMO_ANALYST_PASSWORD` | Set to something secure (optional, defaults to `analyst123`) |
| `DEMO_ADMIN_PASSWORD` | Set to something secure (optional, defaults to `admin123`) |

---

## Architecture

```
backend/
├── breathe_esg/          Django project (settings, urls, wsgi)
├── core/                 Data models, serializers, review API
│   ├── models.py         Organization, IngestionJob, EmissionRecord, AuditLog
│   ├── views.py          Auth, dashboard, record review endpoints
│   └── management/
│       └── commands/
│           └── create_demo_data.py
├── ingestion/            Parsers and upload endpoints
│   ├── emission_factors.py   DEFRA 2023 factors + airport coordinates
│   ├── parsers/
│   │   ├── sap.py        MB51 CSV → EmissionRecord
│   │   ├── utility.py    Portal CSV → EmissionRecord
│   │   └── travel.py     Concur CSV → EmissionRecord (haversine)
│   └── views.py          /api/ingest/sap|utility|travel/
└── sample_data/          Realistic test files

frontend/
├── src/
│   ├── pages/
│   │   ├── Login.jsx     JWT login form
│   │   ├── Dashboard.jsx Summary stats + recent jobs
│   │   ├── Ingest.jsx    File upload UI for 3 sources
│   │   └── Review.jsx    Filterable table + bulk approve/reject + record modal
│   ├── components/
│   │   ├── Layout.jsx    Nav sidebar
│   │   └── StatusBadge.jsx
│   └── api/client.js     Axios + JWT refresh interceptor
```

## API Endpoints

```
POST /api/auth/login/           JWT login
POST /api/auth/refresh/         Token refresh
GET  /api/auth/me/              Current user

GET  /api/dashboard/summary/    Aggregated stats

GET  /api/records/              List (filter: status, scope, source_type, search)
GET  /api/records/:id/          Detail
PATCH /api/records/:id/         Edit (quantity only)
POST /api/records/:id/approve/  Approve with notes
POST /api/records/:id/reject/   Reject with notes
POST /api/records/bulk-approve/ Bulk approve by IDs
POST /api/records/bulk-reject/  Bulk reject by IDs
GET  /api/records/:id/audit_log/ Audit trail

POST /api/ingest/sap/           Upload SAP CSV
POST /api/ingest/utility/       Upload utility CSV
POST /api/ingest/travel/        Upload travel CSV
GET  /api/ingest/jobs/          Job history
GET  /api/ingest/jobs/:id/      Job detail
```

## Documentation

- `MODEL.md` — Data model design and rationale
- `DECISIONS.md` — Every ambiguity resolved with justification
- `TRADEOFFS.md` — Three deliberate non-builds
- `SOURCES.md` — Research on each data source format
