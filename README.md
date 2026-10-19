# SurplusSync — Enterprise Surplus Food Logistics & Waste Prevention

SurplusSync is an enterprise food surplus redistribution and inventory conservation platform built for hotels, restaurants, supermarket chains, and food redistribution NGO networks. It implements strict First-Expired-First-Out (FEFO) batch tracking, automated spoilage horizon alerts, barcode scanning, CSV manifest ingestion, background task processing, and secure logistics claiming workflows.

---

## Architecture Overview

- **Backend**: Django 6.1 + Django REST Framework (DRF) + SimpleJWT (`/api/v1/`) + django-q2
- **Background Tasks & Scheduling**: `django-q2` using the PostgreSQL ORM broker (`django_q_ormq`). **No Redis or Celery**.
- **Frontend**: React 19 + Vite + TypeScript + Tailwind CSS v4 + TanStack Query
- **Design System**: Dark-first SaaS aesthetic (CSS custom properties tokens in `src/tokens.css`, Inter tabular numerals, Lucide icons, Recharts)
- **Data Modes**:
  - **Live Mode (`VITE_DATA_MODE=live`)**: Directly interacts with the Django REST API at `http://127.0.0.1:8000/api/v1/`. Strict JWT bearer token authentication, no persona switcher, no demo controls. Role and organization type come exclusively from `GET /accounts/me/`.
  - **Demo Mode (`VITE_DATA_MODE=demo`)**: Autonomous in-browser simulation engine with FEFO stock deduction, interactive virtual clock, persona switcher (Business vs NGO vs Unverified NGO), async CSV import simulation, and zero backend dependency.

---

## Virtual Environment Location

> [!IMPORTANT]
> The Python virtual environment is located at the **repository root**:
> - Windows: `.\venv\`
> - macOS/Linux: `./venv/`
>
> *(There is **no** virtual environment inside `backend/venv`.)*

### Activate Virtual Environment

**Windows (PowerShell)**:
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt)**:
```cmd
venv\Scripts\activate.bat
```

**macOS / Linux**:
```bash
source venv/bin/activate
```

---

## Backend Setup (Django, DRF & Django-Q2)

### 1. Install Dependencies
From the repository root (with virtual environment active):
```bash
pip install -r backend/requirements.txt
```

### 2. Configure Environment Variables
Copy the sample environment file in `backend/`:
```bash
# Windows
copy backend\.env.example backend\.env

# macOS / Linux
cp backend/.env.example backend/.env
```

Default settings in `backend/.env`:
```ini
SECRET_KEY=change-this-to-a-secure-random-key-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
USE_POSTGRES=False
CORS_ALLOW_ALL_ORIGINS=True
```
*(Set `USE_POSTGRES=False` to use SQLite locally, or `USE_POSTGRES=True` if connecting to PostgreSQL).*

### 3. Apply Database Migrations
```bash
python backend/manage.py migrate
```

### 4. Load Initial Fixtures
Load the verified standard food categories and shelf-life horizons into the database:
```bash
python backend/manage.py loaddata backend/inventory/fixtures/categories.json
```

> [!NOTE]
> Do **NOT** run any external seed script like `seed_data.py`. Standard initial data is loaded exclusively through `loaddata backend/inventory/fixtures/categories.json`, new user registrations via `/api/v1/accounts/register/`, or `createsuperuser`.

### 5. Create an Administrative Owner
```bash
python backend/manage.py createsuperuser
```

### 6. Start Django API Server
In terminal 1:
```bash
python backend/manage.py runserver 127.0.0.1:8000
```
The REST API will be accessible at `http://127.0.0.1:8000/api/v1/`.

### 7. Run Background Worker (Django-Q2 Cluster)
In terminal 2 (with virtual environment active), start the background worker cluster:
```bash
python backend/manage.py qcluster
```
The worker processes queued tasks (asynchronous CSV manifest imports, asynchronous email notifications, and scheduled batch jobs).

### 8. Initialize Periodic Background Schedules
In terminal 3 (or once during initial setup):
```bash
python backend/manage.py setup_schedules
```
This idempotently configures the daily expiry check and 15-minute marketplace cleanup schedules in the database.

### 9. Real Backend Management Commands
- **Run Backend Test Suite** (All 95 unit and integration tests):
  ```bash
  python backend/manage.py test
  ```
- **Configure Django-Q2 Schedules**:
  ```bash
  python backend/manage.py setup_schedules
  ```
- **Run Background Worker**:
  ```bash
  python backend/manage.py qcluster
  ```
- **Check Expiry Horizons & Generate Alerts Manually**:
  Evaluates active batches against their category `AlertRule` thresholds (default lookahead: 7 days) and generates critical/warning alerts:
  ```bash
  python backend/manage.py check_expiry --days 7
  ```
- **Generate POS API Key for External POS Terminals**:
  ```bash
  python backend/manage.py create_pos_key <org_id> "Terminal 1 Cash Register"
  ```

---

## Background Jobs Architecture (Django-Q2)

SurplusSync uses **django-q2** with the **ORM broker** (PostgreSQL / SQLite database queue).

```
   ┌────────────────────────────────────────────────────────┐
   │                  SurplusSync Web API                   │
   │      (Django 6.1 + Django REST Framework)              │
   └─────────────┬───────────────────────────┬──────────────┘
                 │                           │
  HTTP 202 Async │                           │ Async Email
  CSV Upload (>50)                           │ Task Enqueue
                 ▼                           ▼
   ┌────────────────────────────────────────────────────────┐
   │           Database Queue (django_q_ormq)               │
   │     • No Redis daemon       • No Celery required       │
   │     • Fully transactional   • ACID durable in Postgres │
   └─────────────────────────────┬──────────────────────────┘
                                 │
                     Pulls tasks │ Polls schedules
                                 ▼
   ┌────────────────────────────────────────────────────────┐
   │            Django-Q2 Worker (qcluster)                 │
   │  ┌──────────────────────────────────────────────────┐  │
   │  │ Async CSV Ingestion (Batching, Deduplication)    │  │
   │  ├──────────────────────────────────────────────────┤  │
   │  │ Async Email Sender (Exponential Backoff Retries) │  │
   │  ├──────────────────────────────────────────────────┤  │
   │  │ Scheduled Expiry Check (Daily 00:05 IST)         │  │
   │  ├──────────────────────────────────────────────────┤  │
   │  │ Expire Stale Listings (Every 15 minutes)         │  │
   │  └──────────────────────────────────────────────────┘  │
   └────────────────────────────────────────────────────────┘
```

### Why ORM Broker (No Redis or Celery)?
1. **Lean Infrastructure Footprint**: SurplusSync runs on PostgreSQL without requiring standalone Redis instances, cache daemons, or Celery workers.
2. **Transaction Integrity**: Background job records (`ImportJob`), tasks, and inventory transactions share the exact same database.
3. **Cross-Platform Compatibility**: Fully compatible with Windows, macOS, and Linux out-of-the-box using standard Python multiprocessing.

### Scheduled Recurring Tasks
Schedules are managed via `python backend/manage.py setup_schedules`:
1. **`daily_expiry_check`**: Runs daily at **00:05 local time (`Asia/Kolkata` IST / UTC+05:30)**.
   - Evaluates all active batches against shelf-life horizons.
   - Generates high/medium/low priority `Alert` items.
   - Compiles and sends a consolidated daily email digest to each business organization with `email_alerts_enabled=True`.
2. **`expire_stale_marketplace_listings`**: Runs **every 15 minutes**.
   - Finds active surplus marketplace listings whose batches have expired or reached zero remaining quantity.
   - Transitions their status to `EXPIRED` to prevent NGOs from reserving spoiled inventory.

> [!NOTE]
> **Timezone Configuration**: Django's global `TIME_ZONE` is `UTC`, while `Q_CLUSTER['time_zone']` is explicitly set to `Asia/Kolkata` (IST, UTC+05:30). Running at 00:05 IST corresponds to 18:35 UTC of the preceding day.

### Asynchronous CSV Manifest Ingestion
The CSV ingestion pipeline adapts dynamically based on file size:
- **$\le 50$ rows (Synchronous)**: Processed inline immediately. Returns `201 Created` with the completed `ImportJob` payload.
- **$> 50$ rows (Asynchronous)**: Enqueued to `django-q2`. Returns `202 Accepted` with `task_id` and the `ImportJob` record in `PENDING` status.
- **Progress Polling**: Clients query `GET /api/v1/inventory/import-jobs/<id>/` every 1500ms. The background worker reports progress in real-time (`processed_rows`, `total_rows`, `rows_ok`, `rows_failed`).
- **Safe Deduplication Rule**: Existing inventory is matched by `(organization, product, batch_code)`. If matched, the batch quantity is safely incremented without creating duplicate `Batch` entries or duplicate transactions.
- **Worker Downtime Alert**: If an async job remains in `PENDING` status for more than 2 minutes, `worker_may_be_down: true` is returned and a warning banner appears on the frontend prompting the operator to start `python manage.py qcluster`.

### Asynchronous Email System
- **Django 6.1 `MAILERS` Configuration**: Utilizes Django 6.1's native `MAILERS` setting in `SURPLUSSYNC/settings.py`.
- **Serializable Task Signatures**: Background tasks accept only primitive, serializable arguments (strings, lists, dicts, integers). Model instances are never passed into `async_task`.
- **Exponential Backoff**: If SMTP transmission fails, `send_email_task` retries up to 3 times with exponential backoff delays ($0.5\text{s}$, $1.0\text{s}$, $2.0\text{s}$).
- **Transactional Notifications**:
  - **Welcome Email**: Dispatched asynchronously upon new business or NGO registration.
  - **NGO Verification / Rejection**: Dispatched asynchronously when platform admins review verification tickets.
  - **Daily Expiry Digest**: Dispatched daily after the midnight FEFO expiry check (1 email per organization).
  - **Alert Opt-Out**: Respected via the `Organization.email_alerts_enabled` boolean flag.

### Troubleshooting & Windows Multiprocessing
- **Worker May Be Down Warning**: If the frontend displays *"Background worker may be down"*, ensure `python backend/manage.py qcluster` is running in a terminal.
- **Direct Fallback Command**: If the worker cluster cannot be run during local testing, you can execute the expiry check directly with:
  ```bash
  python backend/manage.py check_expiry --days 7
  ```
- **Windows Multiprocessing**: On Windows, Python uses `spawn` for multiprocessing. The `Q_CLUSTER` configuration uses `workers: 2`, `recycle: 500`, and `timeout: 120`.

---

## Frontend Setup (React + Vite)

Navigate into the `frontend/` directory:
```bash
cd frontend
```

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment

Copy `.env.example` to `.env`:
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

#### A. To run in LIVE MODE (Connecting to Django):
```ini
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_DATA_MODE=live
```
In Live Mode:
- The floating demo controls panel and virtual clock simulation are disabled.
- The "Demo data" pill and "Switch Demo Persona" dropdown are absent.
- The user's role and organization type come exclusively from `GET /accounts/me/`.
- Protected routes require valid credentials obtained from `/accounts/login/` or `/accounts/register/`.
- Background imports poll the live Django REST API (`GET /api/v1/inventory/import-jobs/<id>/`).

#### B. To run in DEMO MODE (Autonomous In-Browser Simulation):
```ini
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_DATA_MODE=demo
```
In Demo Mode:
- Interactive virtual clock controls (Pause, 1x, 5x, 20x, Fast-Forward 24h).
- Instant persona switcher in header (Business, NGO Partner, Unverified NGO).
- In-memory FEFO stock deduction and random POS sale simulations.
- Asynchronous CSV import simulation with animated progress bar and downtime triggers.
- Zero external backend required.

### 3. Start Development Server
```bash
npm run dev
```
Open `http://localhost:5173/` in your browser.

### 4. Run Automated Test Suite (Vitest)
Executes all 104 automated unit and integration tests across 14 test suites covering async CSV polling, admin workflows, route guards, NGO profile, donor rating flow, accessibility (axe-core WCAG AA), simulation invariants, and live mode behavior:
```bash
npm test -- --run
```

### 5. Run Linter
Validates zero errors across React 19, TypeScript, and hook invariants:
```bash
npm run lint
```

### 6. Production Build
Validates bundle compilation, TypeScript types (`tsc -b`), and code-splitting (all chunks strictly < 500 kB):
```bash
npm run build
```

---

## Real Backend REST API Endpoints

The backend strictly implements the following endpoints at `/api/v1/`:

### Accounts (`/api/v1/accounts/`)
- `POST /register/` — Register a new user and organization (`BUSINESS` or `NGO`). Dispatches async welcome email.
- `POST /login/` — SimpleJWT token pair generation (`access`, `refresh`).
- `POST /token/refresh/` — Single-flight JWT access token refresh.
- `GET /me/` — Retrieve authenticated user profile, assigned role, and organization status.
- `GET /organizations/` — List active organizations (tenant-scoped).
- `GET /users/` — List users within organization.

### Inventory & Operations (`/api/v1/inventory/`)
- `GET /dashboard/summary/` — Summary metrics (total SKUs, expiring batches, active alerts, total stock value).
- `GET /categories/` — Hierarchical product categories and default shelf-life parameters.
- `GET /storage-locations/` — Chilled, frozen, and dry storage facilities.
- `GET /products/` — Product catalog with SKU and barcode indexes.
- `GET /products/barcode/<barcode>/` — Direct barcode scanner SKU resolution.
- `GET /batches/` — Batch inventory with expiry dates and remaining quantities.
- `GET /batches/expiring_soon/` — Imminent spoilage horizon batches.
- `POST /batches/deduct/` — Strict FEFO quantity deduction.
- `GET /transactions/` — Auditable stock movement ledger.
- `GET /alerts/` & `POST /alerts/<id>/acknowledge/` — Spoilage horizon warnings and acknowledgments.
- `GET /alert-rules/` — Category-specific shelf-life alert thresholds.
- `POST /import-jobs/` — Multipart CSV manifest upload (201 synchronous $\le 50$ rows; 202 async $> 50$ rows).
- `GET /import-jobs/` — List organization import jobs and history.
- `GET /import-jobs/<id>/` — Query progress, timing, and `worker_may_be_down` status for async job.
- `GET /pos-keys/` & `POST /pos-keys/<id>/rotate/` — External POS terminal API keys.

### Marketplace & Donor Ratings (`/api/v1/marketplace/`)
- `GET /ratings/pending/` — Picked-up claims the authenticated NGO has not rated yet (donor organization, item, quantity, pickup date).
- `POST /claims/<id>/rate/` — Rate donor partner {stars (1-5), comment (max 500 chars)}. Enforces claim status `PICKED_UP`, NGO ownership, and single rating per claim.
- `GET /ratings/mine/` — Ratings submitted by the authenticated NGO, newest first, paginated.
- `PATCH /ratings/<id>/` — Update stars and comment within the strict 7-day edit window (`is_editable` check).
- `GET /businesses/<id>/ratings/` — Community rating summary: average stars (`rating_avg`), count (`rating_count`), star breakdown (1-5 counts), and latest 5 non-hidden reviews.
- `GET /listings/` — Surplus food listings annotated with donor `rating_avg` and `rating_count`.
- `GET /claims/` & `POST /claims/` — NGO reservation claims on surplus food listings.

### Incident & Issue Reporting (`/api/v1/issues/`)
- `POST /` — Authenticated tenant issue submission (category, target org, optional claim link, description, priority).
- `GET /` — List issues reported by the authenticated user's organization.

### Platform Administration (`/api/v1/admin/`)
*Guarded strictly by `IsPlatformAdmin` (`is_staff=True, organization=None`).*
- `GET /stats/` — Aggregated metrics: total businesses, total NGOs, pending NGO approvals, open issues, total kg rescued, average ratings, weekly signups series (`TruncWeek`), and priority queues.
- `GET /verifications/pending/` — Pending NGO authorization queue.
- `POST /organizations/<id>/verify/` — Authorize NGO, activate relief access, and dispatch async confirmation email.
- `POST /organizations/<id>/reject/` — Reject NGO with mandatory rationale and async rejection email.
- `GET /organizations/` & `GET /organizations/<id>/` — Comprehensive organization directory with filters, user lists, and activity feeds.
- `POST /organizations/<id>/suspend/` & `POST /organizations/<id>/reinstate/` — Operational killswitch with claim and login blocks.
- `GET /issues/` & `PATCH /issues/<id>/` — Incident dispute management, assignment, resolution notes, and status transitions (`OPEN` -> `IN_REVIEW` -> `RESOLVED` / `DISMISSED`).
- `GET /ratings/` — Complete dual-party ratings feed including hidden reviews.
- `POST /ratings/<id>/hide/` & `POST /ratings/<id>/unhide/` — Content moderation with mandatory reason and live score recalculation.
- `GET /audit-logs/` — Append-only administrative compliance trail with structured JSON details.
- `GET /settings/` — Operational parameters and platform configuration.

---

## Page-to-Endpoint Mapping Table

| Frontend Route / View | Feature / User Interaction | Backend REST Endpoint | Method | Status |
| :--- | :--- | :--- | :---: | :---: |
| `/login` | User Authentication | `/api/v1/accounts/login/` | `POST` | **LIVE** |
| `/register` | Organization & Lead Registration | `/api/v1/accounts/register/` | `POST` | **LIVE** |
| `/dashboard` | Business Inventory & FEFO Overview | `/api/v1/inventory/dashboard/summary/` | `GET` | **LIVE** |
| `/dashboard` | "Your Rating" Business Card | `/api/v1/marketplace/businesses/<id>/ratings/` | `GET` | **LIVE** |
| `/impact` (Business) | Environmental & Social ESG Analytics | `/api/v1/inventory/transactions/` | `GET` | **LIVE** |
| `/impact` (Business) | Donor Community Rating & Breakdown | `/api/v1/marketplace/businesses/<id>/ratings/` | `GET` | **LIVE** |
| `/inventory` | Batch Shelf-Life & FEFO Allocation | `/api/v1/inventory/batches/` | `GET` | **LIVE** |
| `/scan` | Real-time POS Barcode Lookup | `/api/v1/inventory/products/barcode/<barcode>/` | `GET` | **LIVE** |
| `/import` | CSV Manifest Multipart Ingestion | `/api/v1/inventory/import-jobs/` | `POST` | **LIVE** |
| `/import` | Ingestion Job Progress Polling | `/api/v1/inventory/import-jobs/<id>/` | `GET` | **LIVE** |
| `/feed` (NGO) | Live Surplus Offers with Donor Rating | `/api/v1/marketplace/listings/` | `GET` | **LIVE** |
| `/claims` (NGO) | Rescue Milestone Tracking | `/api/v1/marketplace/claims/` | `GET` | **LIVE** |
| `/claims` (NGO) | Mark Rescue Picked Up | `/api/v1/marketplace/claims/<id>/` | `PATCH` | **LIVE** |
| `/claims` (NGO) | Rate Donor Handover Modal | `/api/v1/marketplace/claims/<id>/rate/` | `POST` | **LIVE** |
| `/ngo/profile` | Header Profile & Rating Statistics | `/api/v1/accounts/me/` | `GET` | **LIVE** |
| `/ngo/profile` | "Rate Donors" Pending Tab | `/api/v1/marketplace/ratings/pending/` | `GET` | **LIVE** |
| `/ngo/profile` | Interactive Rate Dialog (1-5★) | `/api/v1/marketplace/claims/<id>/rate/` | `POST` | **LIVE** |
| `/ngo/profile` | "My Ratings" Tab (Paginated History) | `/api/v1/marketplace/ratings/mine/` | `GET` | **LIVE** |
| `/ngo/profile` | Edit Review Modal (7-day window) | `/api/v1/marketplace/ratings/<id>/` | `PATCH` | **LIVE** |
| `/admin/overview` | Platform Overview Cockpit & Action Queues | `/api/v1/admin/stats/` | `GET` | **LIVE** |
| `/admin/verifications` | NGO Verification Queue | `/api/v1/admin/verifications/pending/` | `GET` | **LIVE** |
| `/admin/verifications` | Single & Bulk NGO Authorization | `/api/v1/admin/organizations/<id>/verify/` | `POST` | **LIVE** |
| `/admin/verifications` | Single NGO Rejection with Mandatory Reason | `/api/v1/admin/organizations/<id>/reject/` | `POST` | **LIVE** |
| `/admin/organizations` | Organizations Directory & Filtering | `/api/v1/admin/organizations/` | `GET` | **LIVE** |
| `/admin/organizations` | Organization Detail Inspector | `/api/v1/admin/organizations/<id>/` | `GET` | **LIVE** |
| `/admin/organizations` | Suspend / Reinstate Organization | `/api/v1/admin/organizations/<id>/suspend/` | `POST` | **LIVE** |
| `/admin/issues` | Incident & Dispute Console | `/api/v1/admin/issues/` | `GET` | **LIVE** |
| `/admin/issues` | Review & Update Ticket Status / Notes | `/api/v1/admin/issues/<id>/` | `PATCH` | **LIVE** |
| `/admin/ratings` | Ratings Moderation Console & Metrics | `/api/v1/admin/ratings/` | `GET` | **LIVE** |
| `/admin/ratings` | Hide / Unhide Rating with Reason | `/api/v1/admin/ratings/<id>/hide/` | `POST` | **LIVE** |
| `/admin/audit-log` | Append-Only Compliance Trail | `/api/v1/admin/audit-logs/` | `GET` | **LIVE** |
| `/admin/settings` | Operational Parameters & Platform Config | `/api/v1/admin/settings/` | `GET` | **LIVE** |

---

## License

Proprietary & Confidential — SurplusSync Enterprise Food Logistics.
