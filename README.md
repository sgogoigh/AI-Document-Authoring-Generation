# DocCraft AI — AI-Assisted Document Authoring & Generation Platform

A full-stack, standalone-deployable AI document authoring platform built with **FastAPI**, **Next.js (App Router + TypeScript + Tailwind CSS)**, **SQLAlchemy / Alembic (SQLite & PostgreSQL)**, and **Google Gemini** (`google-genai`).

Authenticated users configure structured business documents (**Microsoft Word `.docx`** and **PowerPoint `.pptx`**), optionally scaffold outlines with **AI-Suggest Outline**, generate context-aware prose/slides and custom editorial visuals via Gemini, iteratively refine individual sections with feedback and comments, inspect database audit telemetry and point-in-time state reconstruction, and export publication-grade `.docx` and `.pptx` files.

---

## Key Features

- **Authentication & Security**
  - Email & password registration/login using Argon2 password hashing and signed JWT access + refresh tokens.
  - **Google Sign-In (OAuth2 / OIDC):** Full authorization code flow (`/auth/google/url`, `/auth/google/callback`) and ID token verification (`/auth/google`) with automatic `local` -> `hybrid` account linking.
- **Document Configuration (Scaffolding)**
  - **Word (`.docx`):** Define main topic, editorial tone/palette/audience, and add, remove, rename, or reorder section headers.
  - **PowerPoint (`.pptx`):** Define slide count and custom title/heading for each slide.
  - **Bonus Feature — AI-Suggest Outline:** Provide only a main topic and click **AI-Suggest Outline** to receive tailored section headers or slide titles that you can accept, edit inline, or discard.
- **Structured AI Generation + Gemini Visuals**
  - Section-by-section / slide-by-slide Gemini generation constrained to strict Pydantic JSON schemas (`DocxSectionSchema`, `PptxSlideSchema`) so layouts stay structured and slides never overflow.
  - Custom editorial PNG illustrations generated via Gemini image models (`gemini-2.5-flash-image`), served via authenticated endpoints and embedded cleanly in both `.docx` and `.pptx` exports.
- **Interactive Refinement Studio**
  - Split-pane editor with outline navigator, structured content & image previews, per-section **AI Refinement Prompt** (plus quick-refine chips), persisted **Like / Dislike** toggles, review **Comment threads**, and per-section revision diffs.
- **Database Logging, Monitoring & Point-in-Time Reconstruction**
  - Immutable `audit_event_logs` stream with correlation `X-Trace-Id` and before/after JSON snapshots.
  - `llm_call_metrics` table tracking input/output/total tokens, latency (`avg`, `p50`, `p95`), operation breakdown, and error rates.
  - `project_snapshots` + `ReconstructionService` supporting point-in-time reconstruction by version number, timestamp, or audit `seq_id`, live diff comparison, and non-destructive version restore.
- **Executive `.docx` & `.pptx` Export**
  - `python-docx`: Cover banner, metadata table, Document Outline overview, shaded Key Takeaway callouts, bold-lead bullets, repeating-header zebra tables, captioned visuals, and running header/page-number footer.
  - `python-pptx`: 16:9 widescreen dark cover slide, Presentation Roadmap agenda slide, layout-dispatched content slides (`bullets_with_visual`, `two_column`, `metrics_cards`, `bullets_only`) with hanging-indent bullets, footer/slide numbers, and presenter speaker notes.

---

## Architecture & Documentation

- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Architecture & Database Schema](docs/ARCHITECTURE_AND_DB_SCHEMA.md)
- [Test & Verification Plan](docs/TEST_AND_VERIFICATION_PLAN.md)
- [Live E2E & Visual QA Report](docs/E2E_AND_VISUAL_QA_REPORT.md)
- [Scenario Testing & DB Performance Report](docs/SCENARIOS_AND_PERFORMANCE_REPORT.md)
- [Cloud Deployment Plan (Vercel + Cloud Backend)](docs/CLOUD_DEPLOYMENT_PLAN.md)

```text
AI-Document-Authoring-Generation/
├── backend/                 # Standalone FastAPI service (+ .venv, Alembic, Dockerfile)
├── frontend/                # Standalone Next.js App Router service (+ Dockerfile)
├── docs/                    # Architecture, DB schema, test plan, QA reports
├── docker-compose.yml       # Optional multi-service local/prod orchestration
└── README.md
```

---

## Environment Variables

### Backend (`backend/.env` or root `.env`)

Copy `backend/.env.example` to `backend/.env` (or populate root `.env`):

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key used for outline suggestion, section generation, refinement, and image generation. |
| `GEMINI_TEXT_MODEL` | No | Gemini text model ID (default: `gemini-2.5-flash`). |
| `GEMINI_IMAGE_MODEL` | No | Gemini image model ID (default: `gemini-2.5-flash-image`). |
| `ENABLE_IMAGE_GENERATION` | No | Set `true` / `false` to enable or disable AI image generation (default: `true`). |
| `DATABASE_URL` | No | SQLAlchemy connection string (default: `sqlite:///./storage/app.db`; supports `postgresql+psycopg://...`). |
| `JWT_SECRET_KEY` | **Prod Yes** | Secret key for signing JWT access and refresh tokens. |
| `GOOGLE_CLIENT_ID` | Optional | Google OAuth2 Client ID for live Google Sign-In. |
| `GOOGLE_CLIENT_SECRET` | Optional | Google OAuth2 Client Secret for OAuth code exchange. |
| `GOOGLE_REDIRECT_URI` | Optional | OAuth callback URL (default: `http://localhost:3000/auth/google/callback`). |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `http://localhost:3000,http://127.0.0.1:3000`). |
| `STORAGE_DIR` | No | Directory for SQLite DB, generated PNG assets, and exports (default: `./storage`). |

### Frontend (`frontend/.env.local`)

Copy `frontend/.env.example` to `frontend/.env.local`:

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend API base URL (default: `http://localhost:8000/api/v1`). |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Optional Google OAuth Client ID. |
| `NEXT_PUBLIC_APP_URL` | Frontend public URL (default: `http://localhost:3000`). |

---

## Local Development Setup (Standalone Services)

### 1. Backend (FastAPI + Virtual Environment)

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive Swagger docs are available at `http://localhost:8000/docs`.

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## Standalone Docker & Compose Deployment

Each service ships with an independent production `Dockerfile`:

- **Build & run Backend standalone:**
  ```bash
  docker build -t doccraft-backend ./backend
  docker run -p 8000:8000 -e GEMINI_API_KEY=your-key -e JWT_SECRET_KEY=your-secret doccraft-backend
  ```
- **Build & run Frontend standalone:**
  ```bash
  docker build -t doccraft-frontend --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 ./frontend
  docker run -p 3000:3000 doccraft-frontend
  ```
- **Full stack with PostgreSQL via Docker Compose:**
  ```bash
  GEMINI_API_KEY=your-key docker compose up --build
  ```

---

## Cloud Deployment (Vercel Frontend + Cloud Backend)

For production cloud hosting (**Next.js on Vercel** + **FastAPI container on Render / Railway / Fly.io / Google Cloud Run** + **Managed PostgreSQL**), see the step-by-step [Cloud Deployment Plan](docs/CLOUD_DEPLOYMENT_PLAN.md) covering environment variables, persistent storage for generated PNGs, CORS origin configuration, Alembic startup migrations, and Google OAuth production setup.

---

## API Usage Examples

```bash
# 1. Register & obtain JWT token
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"analyst@example.com","full_name":"Alex Morgan","password":"StrongPassword123!"}'

# 2. Bonus: AI-Suggest Outline
curl -X POST http://localhost:8000/api/v1/projects/suggest-outline \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"doc_type":"docx","main_topic":"A market analysis of the EV industry in 2025"}'

# 3. Create project, generate content, refine a section, and export
curl -X POST http://localhost:8000/api/v1/projects/<PROJECT_ID>/generate \
  -H "Authorization: Bearer <TOKEN>"

curl -X POST http://localhost:8000/api/v1/sections/<SECTION_ID>/refine \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"refinement_prompt":"Make this more formal and concise under 100 words"}'

curl -L http://localhost:8000/api/v1/projects/<PROJECT_ID>/export \
  -H "Authorization: Bearer <TOKEN>" -o report.docx
```

---

## Running Tests

### Backend (`pytest` + `ruff`)
```bash
cd backend
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m pytest -m "not live_ai"
# Isolated 57-case scenario & DB performance benchmark suite:
.\.venv\Scripts\python.exe -m pytest tests/scenarios -s
# Including live Gemini API + Document Quality tests (uses GEMINI_API_KEY):
.\.venv\Scripts\python.exe -m pytest
```

### Frontend (`tsc`, `vitest`, `playwright`)
```bash
cd frontend
npm run typecheck
npm test
npm run build
# Browser E2E against running backend (:8000) & frontend (:3000):
npx playwright test
```
