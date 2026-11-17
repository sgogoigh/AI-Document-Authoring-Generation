# Cloud Deployment Plan — Vercel Frontend + Cloud FastAPI Backend + Managed PostgreSQL

This plan details how to deploy **DocCraft AI** as two standalone cloud services:
1. **Frontend:** Next.js App Router (`frontend/`) hosted on **Vercel**
2. **Backend:** FastAPI (`backend/Dockerfile`) hosted on **Render**, **Railway**, **Fly.io**, or **Google Cloud Run**
3. **Database:** Managed **PostgreSQL** (Neon, Supabase, Render Postgres, or Cloud SQL)

---

## 1. Target Cloud Architecture

```text
+-----------------------------------+       HTTPS REST + Bearer JWT       +-------------------------------------+
|        Vercel (Frontend)          | ----------------------------------> |   Cloud Container Host (Backend)    |
|  - Root Directory: frontend/      |                                     |  - Context: backend/Dockerfile      |
|  - Next.js 15 App Router          | <---------------------------------- |  - FastAPI + Uvicorn                |
|  - Domain: https://app.domain.com |   JSON + Blob (.docx / .pptx / png) |  - Domain: https://api.domain.com   |
+-----------------------------------+                                     +------------------+------------------+
                                                                                             |
                                                            +--------------------------------+--------------------------------+
                                                            |                                                                 |
                                                            v                                                                 v
                                            +-------------------------------+                                 +-------------------------------+
                                            |   Managed PostgreSQL (TLS)    |                                 |  Persistent Volume / Storage  |
                                            |  - Neon / Supabase / Render   |                                 |  - Mounted at /app/storage    |
                                            |  - Alembic migrations on boot |                                 |  - Gemini PNG visual assets   |
                                            +-------------------------------+                                 +-------------------------------+
```

---

## 2. Step-by-Step Deployment Guide

### Phase A — Provision Managed PostgreSQL
1. Create a PostgreSQL 16 database on **Neon**, **Supabase**, **Render PostgreSQL**, or **Google Cloud SQL**.
2. Copy the connection string and format it for SQLAlchemy + `psycopg` (v3):
   ```text
   postgresql+psycopg://<USER>:<PASSWORD>@<HOST>:5432/<DB_NAME>?sslmode=require
   ```
3. Verify connectivity and schema migration from your local machine or CI runner:
   ```bash
   cd backend
   DATABASE_URL="postgresql+psycopg://..." alembic upgrade head
   ```

---

### Phase B — Deploy Standalone Backend (`backend/`)
Because `backend/Dockerfile` is completely self-contained and runs `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000` on startup, you can deploy it cleanly to any container platform:

#### Option 1: Render (Web Service + Persistent Disk) — Simplest All-in-One
1. Create a **New Web Service** connected to your Git repository.
2. Set **Root Directory** to `backend` and **Runtime** to `Docker` (auto-detects `backend/Dockerfile`).
3. Attach a **Persistent Disk** mounted at `/app/storage` (e.g., 5 GB) so Gemini-generated PNG assets persist across restarts and redeploys.
4. Set environment variables:
   - `ENVIRONMENT=production`
   - `DEBUG=false`
   - `DATABASE_URL=postgresql+psycopg://...`
   - `JWT_SECRET_KEY=<64-char cryptographically random hex string>`
   - `GEMINI_API_KEY=<your-gemini-key>`
   - `GEMINI_TEXT_MODEL=gemini-2.5-flash`
   - `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image`
   - `ENABLE_IMAGE_GENERATION=true`
   - `STORAGE_DIR=/app/storage`
   - `CORS_ORIGINS=https://<your-vercel-prod-domain>,https://<your-preview-domain>`
   - `GOOGLE_CLIENT_ID=<from Google Cloud Console>` *(if enabling Google Login)*
   - `GOOGLE_CLIENT_SECRET=<from Google Cloud Console>`
   - `GOOGLE_REDIRECT_URI=https://<your-vercel-prod-domain>/auth/google/callback`
5. Health check path: `/api/v1/health`.

#### Option 2: Railway / Fly.io (with Persistent Volume)
- **Railway:** Create service from repo with Root Directory `backend`, attach a Railway Volume at `/app/storage`, set `PORT=8000` (or override `CMD` to use `$PORT`), and paste the same env vars.
- **Fly.io:** `cd backend && fly launch --dockerfile Dockerfile`, create a volume (`fly volumes create doccraft_storage --size 5`), mount at `/app/storage` in `fly.toml`, and set secrets with `fly secrets set ...`.

#### Option 3: Google Cloud Run (+ Cloud Storage / Cloud SQL)
- Build and push `backend/Dockerfile` to Artifact Registry.
- Note: Cloud Run container filesystems are ephemeral—mount a **Cloud Storage FUSE volume** at `/app/storage` (or refactor `storage_dir` to GCS/S3) so generated images survive instance scaling.
- Configure `--timeout=300` (allows multi-section Gemini generation + image generation requests up to 5 minutes without gateway timeouts) and `--min-instances=1` if cold-start latency matters.

> **Important Timeout Note:** Multi-section + image generation calls (`POST /api/v1/projects/{id}/generate`) can take 20–60 seconds depending on section count. Ensure your backend platform HTTP request timeout is **>= 120 seconds** (Render supports up to 100 minutes; Cloud Run supports up to 60 minutes).

---

### Phase C — Deploy Frontend on Vercel (`frontend/`)
1. Import the Git repository in **Vercel Dashboard → Add New Project**.
2. Set **Root Directory** to `frontend`.
3. Framework Preset: **Next.js** (Vercel natively builds Next.js without needing the Docker standalone output; leave `NEXT_OUTPUT` unset on Vercel).
4. Configure **Environment Variables** in Vercel (Production & Preview):
   - `NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com/api/v1`
   - `NEXT_PUBLIC_APP_URL=https://app.yourdomain.com`
   - `NEXT_PUBLIC_GOOGLE_CLIENT_ID=<your-google-client-id>` *(optional, matching backend)*
5. Deploy! Note the assigned Vercel URL (e.g., `https://doccraft-ai.vercel.app`) and update `CORS_ORIGINS` + `GOOGLE_REDIRECT_URI` on the backend to match.

---

### Phase D — Configure Google OAuth2 (Production)
1. In **Google Cloud Console → APIs & Services → Credentials**, open your OAuth 2.0 Client ID (Web application).
2. Add **Authorized JavaScript origins**:
   - `https://app.yourdomain.com` (and `http://localhost:3000` for local dev)
3. Add **Authorized redirect URIs**:
   - `https://app.yourdomain.com/auth/google/callback`
4. Verify `GET https://api.yourdomain.com/api/v1/health` returns `"google_oauth_configured": true`.

---

## 3. Production Hardening & Observability Checklist
- [ ] **TLS / HTTPS Only:** Both Vercel and backend host serve strictly over HTTPS; verify `CORS_ORIGINS` contains exact HTTPS origins (no `*` wildcard when `allow_credentials=True`).
- [ ] **CORS Exposed Headers:** Confirm `Content-Disposition`, `X-Trace-Id`, and `X-Response-Time-Ms` are exposed so browser `.docx` / `.pptx` downloads preserve exact filenames (already configured in `backend/app/main.py`).
- [ ] **Secrets Hygiene:** Generate fresh `JWT_SECRET_KEY` (`openssl rand -hex 32`), never reuse dev keys, and restrict `GEMINI_API_KEY` quota/alerts in Google AI Studio.
- [ ] **Database Backups & Telemetry:** Enable automated daily PostgreSQL snapshots and monitor `llm_call_metrics` error rates & latency percentiles via `/monitoring`.
- [ ] **Post-Deploy Smoke Verification:**
  1. `curl https://api.yourdomain.com/api/v1/health` → `{"status":"ok","database":"connected","gemini_configured":true,...}`
  2. Open `https://app.yourdomain.com` → Register / Sign In (and test Google Sign-In)
  3. Create a `.docx` project with **AI-Suggest Outline** → Generate + Visual → Refine → Export `.docx`
  4. Create a `.pptx` project → Generate → Refine → Export `.pptx`
  5. Open `/monitoring` → Confirm `audit_event_logs`, `llm_call_metrics`, and Project Reconstruction work against PostgreSQL.
