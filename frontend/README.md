# SurplusSync — Enterprise Frontend Architecture

The frontend for SurplusSync is a production-grade single-page application built with React 19, Vite, TypeScript, and Tailwind CSS v4. It delivers a dark-first SaaS aesthetic (Linear/Vercel/Stripe quality) with support for an ambient warm light theme, strict First-Expired-First-Out (FEFO) inventory management, real-time alerting, barcode scanning, and logistics workflows.

---

## Technical Stack

- **Core Framework**: React 19 + TypeScript
- **Bundler**: Vite (Rolldown engine) with dynamic route code-splitting (`React.lazy` + `Suspense`)
- **State Management & Caching**: TanStack React Query v5
- **Styling**: Tailwind CSS v4 + pure CSS tokens (`src/tokens.css`)
- **Components & Icons**: shadcn/ui primitives + Lucide React + Radix UI
- **Typography & Numerals**: Inter with tabular numerals (`tabular-nums`) for jitter-free counters
- **Charts & Mapping**: Recharts + Leaflet (`react-leaflet`)
- **Barcode & QR Scanner**: html5-qrcode
- **Testing & Quality**: Vitest + React Testing Library + Axe-Core (WCAG 2.1 AA certified)

---

## Operating Modes

SurplusSync supports two operation modes controlled via the `VITE_DATA_MODE` environment variable in `frontend/.env`:

### 1. Live Mode (`VITE_DATA_MODE=live`)
Connects directly to the Django REST Framework API at `/api/v1/`:
- **Authentication**: JWT Access Token kept strictly in-memory; Refresh Token persisted in `localStorage` only if "Remember Me" is selected (otherwise `sessionStorage`).
- **Role Derivation**: User permissions, organization type (`BUSINESS` vs `NGO`), and verification status come exclusively from `GET /api/v1/accounts/me/`.
- **Clean Interface**: The floating demo controls panel, simulation clock, "Demo data" pill, and "Switch Demo Persona" menu are completely absent.
- **Route Guards**: Unauthenticated users are automatically redirected to `#login`. Unverified NGOs are held at `#pending-verification`. Unauthorized role actions trigger `#forbidden` (403).

### 2. Demo Mode (`VITE_DATA_MODE=demo`)
An autonomous, zero-dependency in-browser environment:
- **Simulation Engine**: Realistic FEFO stock consumption, barcode deduction, and inventory reconciliation.
- **Interactive Clock**: Fast-forward time (1x, 5x, 20x, +24 hours) to test spoilage horizon transitions.
- **Instant Persona Switcher**: Switch between Business Owner, Verified NGO, and Unverified NGO from the header dropdown in demo mode.

---

## Quick Start

### 1. Environment Configuration

Copy `.env.example` to `.env`:
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Set your desired mode:
```ini
# For Live Mode (requires Django API running at port 8000)
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_DATA_MODE=live

# For Standalone Demo Mode (no backend required)
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_DATA_MODE=demo
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Start Development Server
```bash
npm run dev
```
Open `http://localhost:5173/` in your browser.

---

## Testing & Quality Assurance

### Vitest Unit & Integration Suites
Runs all 42 automated tests covering route guards, login/register forms, single-flight token refresh mutex, NGO claims flow, FEFO reconciliation invariants, live mode guards, and accessibility audits:
```bash
npx vitest run
```

### Accessibility Audits (Axe-Core)
Automated WCAG 2.1 AA compliance testing on Login, Register, Business Dashboard, Inventory, and Barcode Scan:
```bash
npx vitest run src/test/accessibility.test.tsx
```

### Linting
Validates TypeScript and React hook rules:
```bash
npm run lint
```

### Production Build & Bundle Metrics
Generates production assets with manual chunking (Leaflet, Recharts, TanStack Query, html5-qrcode):
```bash
npm run build
```
*(All production chunks are strictly < 500 kB).*

---

## Backend Connectivity (When running Live Mode)

The Django backend virtual environment is located at the **repository root**:
- Windows PowerShell: `..\venv\Scripts\Activate.ps1`
- Start server: `python ..\backend\manage.py runserver 127.0.0.1:8000`
- Load initial categories: `python ..\backend\manage.py loaddata backend/inventory/fixtures/categories.json`
- Create superuser: `python ..\backend\manage.py createsuperuser`
