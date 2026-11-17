# Master Implementation Plan — AI-Assisted Document Authoring & Generation Platform

## Git & Delivery Workflow Rules
- **Branch:** Create and work on `feat/platform-implementation` (branched from `main`).
- **Commit Cadence:** Commit once per completed step/subtask with a clear conventional commit message.
- **Push Cadence:** Push to `origin feat/platform-implementation` **every 5 commits** (Steps 5, 10, 15, 20, 25, ... and at final completion).
- **Standalone Services:** `backend/` (FastAPI + Python `.venv`) and `frontend/` (Next.js + Node) must each have independent dependency manifests, `.env.example`, and `Dockerfile`s so they can deploy separately.
- **All Assignment Features Included:** Core requirements + Bonus **"AI-Suggest Outline"** + Gemini Image Generation + DB Logging/Monitoring/Reconstruction + Google Login + Comprehensive Automated Tests + Live E2E & Visual Output Inspection.

---

## Phase 0 — Planning, Repo Setup & Environment Scaffolding

### Step 1: Create Architecture, Test, and Implementation Plan Docs (`docs/`)
- [x] Author `docs/ARCHITECTURE_AND_DB_SCHEMA.md`
- [x] Author `docs/TEST_AND_VERIFICATION_PLAN.md`
- [x] Author `docs/IMPLEMENTATION_PLAN.md`
- [x] Create feature branch `feat/platform-implementation` and commit plan documents (`Commit #1`)

### Step 2: Repository Hygiene, `.gitignore` & Standalone Service Skeletons
- [x] Update root `.gitignore` for Next.js (`node_modules/`, `.next/`, `out/`, `.env.local`), SQLite (`*.db`, `*.sqlite*`), generated artifacts (`storage/`), coverage, and Playwright outputs while keeping `.env.example` tracked.
- [x] Scaffold `backend/` and `frontend/` directories with `.env.example` files and verify root `.env` `GEMINI_API_KEY` availability without ever committing secrets.
- [x] Commit Step 2 (`Commit #2`)

---

## Phase 1 — Backend Core, Database Schema, Logging, Monitoring & Reconstruction

### Step 3: FastAPI Foundation & Isolated Python Virtual Environment (`backend/.venv`)
- [x] Create `backend/.venv` using Python 3.13.
- [x] Create `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pyproject.toml`.
  - Runtime: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`, `alembic`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]` / `argon2-cffi`, `google-auth`, `google-genai`, `python-docx`, `python-pptx`, `pillow`, `httpx`, `python-multipart`.
  - Dev/Test: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`, `ruff`, `pymupdf` (for PDF/PNG rendering checks if needed).
- [x] Implement `backend/app/core/config.py` (Pydantic Settings loading `GEMINI_API_KEY`, `DATABASE_URL`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `CORS_ORIGINS`, `STORAGE_DIR`).
- [x] Implement `backend/app/core/database.py` (SQLAlchemy engine supporting SQLite WAL mode & PostgreSQL, session dependency) + `/api/v1/health` endpoint.
- [x] Write & run unit test `tests/unit/test_health_and_config.py`.
- [x] Commit Step 3 (`Commit #3`)

### Step 4: Database Models & Alembic Migrations (Domain + Observability + Reconstruction)
- [x] Implement ORM models:
  - `users`, `projects`, `document_sections`, `section_revisions`, `section_comments`, `feedback_events`, `document_assets`, `export_records`
  - `audit_event_logs`, `llm_call_metrics`, `project_snapshots`
- [x] Initialize Alembic (`backend/alembic/`) and generate initial migration cleanly applied to SQLite.
- [x] Write & run `tests/unit/test_models_and_migrations.py` verifying foreign keys, indexes, cascade/soft-delete behavior, and migration upgrade/downgrade.
- [x] Commit Step 4 (`Commit #4`)

### Step 5: Audit Logging Middleware, Monitoring Service & Reconstruction Engine
- [x] Implement `backend/app/core/logging_middleware.py` assigning `X-Trace-Id` to every request and recording HTTP timings/errors.
- [x] Implement `backend/app/services/audit_service.py`:
  - `record_event(...)` writing immutable `audit_event_logs` with `before_state_json`, `after_state_json`, `trace_id`
  - `record_llm_metric(...)` writing token counts, latency, model, status
  - `query_logs(...)` supporting multi-facet filtering (`project_id`, `user_id`, `event_type`, `severity`, `trace_id`, `date_from`, `date_to`, `search`)
  - `compute_analytics(...)` returning aggregated LLM usage, latency percentiles, error rate, like/dislike ratios, and project activity timelines
- [x] Implement `backend/app/services/reconstruction_service.py`:
  - `capture_snapshot(project_id, trigger_event)`
  - `reconstruct_project(project_id, version | at_timestamp | event_seq_id)` returning exact outline, section content, comments, feedback, and diff vs. current state
  - `restore_project_to_version(project_id, version, user_id)` creating forward `restore` revisions without deleting history
- [x] Write & run comprehensive unit tests `tests/unit/test_audit_and_reconstruction.py`.
- [x] Commit Step 5 (`Commit #5`) -> **Push to `origin feat/platform-implementation` (Push #1)**

---

## Phase 2 — Authentication (JWT + Google OAuth) & Project Configuration APIs

### Step 6: Security Utilities, Email/Password Auth & Google OAuth2/OIDC Verification
- [x] Implement `backend/app/core/security.py`:
  - Argon2/bcrypt password hashing & verification
  - JWT creation/decoding (`access_token`, `refresh_token`)
- [x] Implement `backend/app/services/google_oauth_service.py`:
  - Google ID Token verification (`google.oauth2.id_token.verify_oauth2_token`) + OAuth2 authorization code exchange flow (`/auth/google/url`, `/auth/google/callback`, `/auth/google/token`)
  - Account linking rules (`local` -> `hybrid`, new `google` user creation, avatar sync)
- [x] Implement `backend/app/api/v1/auth.py` (`register`, `login`, `google`, `google/url`, `google/callback`, `refresh`, `me`) with audit logging on every auth event.
- [x] Write & run comprehensive tests `tests/integration/test_auth_and_google_oauth_api.py` (including cryptographic RSA-signed OIDC ID token verification tests and Google OAuth code-exchange tests).
- [x] Commit Step 6 (`Commit #6`)

### Step 7: Project Management & Document Configuration (Scaffolding) APIs
- [x] Implement `backend/app/services/project_service.py` and `backend/app/api/v1/projects.py`:
  - `POST /api/v1/projects` (create `.docx` or `.pptx` project with main topic & theme config)
  - `GET /api/v1/projects` (list user's projects with search/filter/sort + section counts & feedback stats)
  - `GET /api/v1/projects/{id}` (full project detail with sections, latest revisions, feedback, comments, assets)
  - `PATCH /api/v1/projects/{id}` & `DELETE /api/v1/projects/{id}` (soft delete + audit log)
  - `PUT /api/v1/projects/{id}/outline` (add, remove, reorder `.docx` section headers OR update `.pptx` slide count & slide titles, incrementing project version & capturing snapshot)
- [x] Enforce strict user ownership checks on all endpoints.
- [x] Write & run `tests/integration/test_projects_and_outline_api.py`.
- [x] Commit Step 7 (`Commit #7`)

---

## Phase 3 — Gemini AI Engine (Structured Text + Image Generation) & Document Builders

### Step 8: Gemini LLM Service (Outline Suggestion, Context-Aware Generation, Refinement & Image Generation)
- [x] Verify active Gemini text & image models via `GEMINI_API_KEY` from `.env`.
- [x] Implement `backend/app/schemas/llm_structured.py` (`OutlineSuggestionSchema`, `DocxSectionSchema`, `PptxSlideSchema`).
- [x] Implement `backend/app/services/gemini_service.py` using `google-genai`:
  - `suggest_outline(doc_type, main_topic, target_count)` -> **Bonus Feature** ("AI-Suggest Outline")
  - `generate_section_content(project, section, sibling_titles)` -> structured JSON specific to `.docx` vs `.pptx`
  - `refine_section_content(project, section, current_json, refinement_prompt)` -> section-scoped revision
  - `generate_section_image(image_prompt, aspect_ratio)` -> generates crisp PNG visual via Gemini image model, saves to `storage/assets/`, returns dimensions & metadata
  - Every LLM call records `llm_call_metrics` (tokens, latency, model, status) and handles retries/clean fallbacks.
- [x] Write & run unit tests (`tests/unit/test_gemini_service_unit.py`) AND live Gemini verification tests (`tests/live_ai/test_gemini_live.py`).
- [x] Commit Step 8 (`Commit #8`)

### Step 9: Generation, Refinement, Feedback, Comments & Monitoring/Reconstruction APIs
- [x] Implement `backend/app/api/v1/generation.py`:
  - `POST /api/v1/projects/suggest-outline` (Bonus feature)
  - `POST /api/v1/projects/{id}/generate` (sequential/structured section-by-section & slide-by-slide generation with optional image generation toggle and progress state)
  - `POST /api/v1/sections/{section_id}/refine` (AI refinement prompt scoped to that section, creates `section_revisions` + snapshot + audit log)
  - `POST /api/v1/sections/{section_id}/feedback` (`like` | `dislike` | `none`, writes `feedback_events` + updates section)
  - `POST /api/v1/sections/{section_id}/comments`, `GET .../comments`, `DELETE /api/v1/comments/{comment_id}`
  - `GET /api/v1/sections/{section_id}/revisions`
- [x] Implement `backend/app/api/v1/monitoring.py`:
  - `GET /api/v1/monitoring/logs` (filtered audit logs)
  - `GET /api/v1/monitoring/metrics` (LLM & satisfaction analytics)
  - `GET /api/v1/projects/{id}/timeline` (chronological project events & snapshots)
  - `GET /api/v1/projects/{id}/reconstruct` (reconstruct by `version`, `at_timestamp`, or `event_seq_id` + diff)
  - `POST /api/v1/projects/{id}/restore/{version}` (restore historical version cleanly)
- [x] Write & run `tests/integration/test_generation_and_refinement_api.py` and `tests/integration/test_monitoring_and_reconstruction_api.py`.
- [x] Commit Step 9 (`Commit #9`)

### Step 10: Structured `.docx` and `.pptx` Builders & Export API
- [x] Implement `backend/app/services/doc_builder/theme.py` (curated cohesive executive palettes, typography constants, spacing rules).
- [x] Implement `backend/app/services/doc_builder/docx_builder.py` (`python-docx`):
  - Styled cover page, executive outline/TOC summary, Heading 1 numbered sections, shaded summary callout boxes, well-spaced paragraphs, bold-lead-in bullets, styled tables, centered captioned Gemini-generated images, running header & page footer.
- [x] Implement `backend/app/services/doc_builder/pptx_builder.py` (`python-pptx`):
  - 16:9 widescreen slides, cohesive dark/editorial title slide, Agenda slide, layout-dispatched content slides (`bullets_only`, `bullets_with_visual`, `two_column`, `metrics_cards`), text-fit/overflow safeguards, embedded Gemini-generated visuals with clean framing & caption, footer & slide numbers, and presenter speaker notes.
- [x] Implement `backend/app/api/v1/export.py`:
  - `GET /api/v1/projects/{id}/export` (fetches latest refined content & active assets, builds valid `.docx` or `.pptx`, records `export_records` + `audit_event_logs`, streams file download).
  - `GET /api/v1/projects/{id}/exports` (export history list) and `GET /api/v1/assets/{asset_id}` (authenticated image serving for UI preview).
- [x] Write & run `tests/unit/test_docx_builder_unit.py`, `tests/unit/test_pptx_builder_unit.py`, and `tests/integration/test_export_api.py`.
- [x] Commit Step 10 (`Commit #10`) -> **Push to `origin feat/platform-implementation` (Push #2)**

---

## Phase 4 — Next.js Frontend (Aesthetic Editorial UI & Full Feature Set)

### Step 11: Next.js App Foundation, Design System & Auth Context
- [x] Initialize standalone Next.js 15+ (App Router, TypeScript, Tailwind CSS) inside `frontend/`.
- [x] Configure `next.config.ts` (`output: 'standalone'`), typography (`Plus Jakarta Sans` / `Newsreader` / `JetBrains Mono`), refined editorial color tokens, glass/card surfaces, subtle motion, and responsive layout primitives.
- [x] Implement `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts` (typed fetch wrapper with JWT refresh/error handling), and `frontend/src/lib/auth-context.tsx`.
- [x] Write & run Vitest setup + `src/__tests__/api_and_auth.test.tsx`.
- [x] Commit Step 11 (`Commit #11`)

### Step 12: Landing Page, Login, Registration & Google Sign-In UI
- [x] Build aesthetic product landing page (`/`) showcasing the `Configure → Generate → Refine → Export` workflow with clear CTAs.
- [x] Build `/login`, `/register`, and `/auth/google/callback` pages:
  - Email/password login & registration with inline validation and loading feedback.
  - **"Continue with Google"** button triggering Google OAuth flow + graceful feedback when OAuth client credentials are/aren't configured.
- [x] Write & run component tests `src/__tests__/auth_pages.test.tsx`.
- [x] Commit Step 12 (`Commit #12`)

### Step 13: Project Dashboard & Document Configuration Wizard (+ Bonus AI-Suggest Outline)
- [x] Build `/dashboard`:
  - Stats bar (total projects, `.docx` vs `.pptx`, exports, satisfaction metrics), search & format filters, responsive project cards showing status, version, section count, last updated, quick open/export/delete.
- [x] Build `/projects/new` (Multi-step Configuration Wizard):
  - Step A: Choose Format (`.docx` Word Report vs `.pptx` Presentation Deck) + Main Topic/Prompt + Theme/Tone & Visual Image Generation toggle.
  - Step B (**Bonus Feature**): **"AI-Suggest Outline"** button (requires only main topic) -> displays suggested section headers or slide titles with **Accept All**, **Edit Inline**, **Add/Remove/Reorder**, or **Discard** controls.
  - Step C: Manual outline editor (`.docx`: add/remove/drag-or-button reorder section headers; `.pptx`: set slide count & edit each slide title) -> Save & Launch Generation.
- [x] Write & run component tests `src/__tests__/dashboard_and_configurator.test.tsx`.
- [x] Commit Step 13 (`Commit #13`)

### Step 14: Interactive Refinement Studio, Revision History & Export UI
- [x] Build `/projects/[id]` (Split-pane Editorial Studio):
  - **Left Sidebar:** Document outline / slide navigator with feedback badges (`like`/`dislike`), comment counts, revision counts, and quick jump.
  - **Main Editor Canvas:** Clean, rich structured rendering of each section/slide (callout summary, paragraphs, bullets, tables, embedded Gemini-generated image preview, speaker notes for `.pptx`).
  - **Per-Section/Slide Refinement Controls:**
    - AI Refinement Prompt box + quick-chip suggestions (*"Make more formal"*, *"Convert to bullet points"*, *"Shorten to 100 words"*, *"Add executive metrics"*) + Regenerate Visual button.
    - Like / Dislike feedback buttons with persisted active states.
    - Comment Box + persisted comment thread per section/slide.
  - **Version History & Point-in-Time Reconstruction Drawer:** View section revisions with field diffs, inspect project reconstruction at any version/timestamp, and restore prior versions.
  - **Top Action Bar:** Export `.docx` / `.pptx` button with instant download + Project Monitoring shortcut.
- [x] Write & run component tests `src/__tests__/refinement_studio.test.tsx`.
- [x] Commit Step 14 (`Commit #14`)

### Step 15: Monitoring, Audit Log Explorer & Reconstruction Analytics Page
- [ ] Build `/monitoring` page:
  - KPI Cards: Total LLM calls, total tokens, average/p95 latency, success rate, like/dislike ratio, total exports.
  - Filterable Audit Event Log table (filter by project, event type, severity, trace ID, date range, search text; expandable before/after JSON diff inspector).
  - LLM Call Metrics table (operation, model, tokens, latency, status).
  - Interactive Project State Reconstruction viewer (pick a project + version/timestamp -> view reconstructed state & diff).
- [ ] Write & run component tests `src/__tests__/monitoring_page.test.tsx`.
- [ ] Commit Step 15 (`Commit #15`) -> **Push to `origin feat/platform-implementation` (Push #3)**

---

## Phase 5 — Standalone Dockerization, E2E Verification & Visual Quality Audit

### Step 16: Standalone Dockerfiles, Compose & Health Verification
- [ ] Create `backend/Dockerfile` and `backend/.dockerignore` (multi-stage/slim Python image, runs Alembic migrations + Uvicorn).
- [ ] Create `frontend/Dockerfile` and `frontend/.dockerignore` (multi-stage Node build using Next.js `output: 'standalone'`).
- [ ] Create root `docker-compose.yml` (optional orchestration for backend + frontend + PostgreSQL + LibreOffice renderer if needed, while verifying both Dockerfiles build and run standalone).
- [ ] Build & smoke-test both standalone Docker images.
- [ ] Commit Step 16 (`Commit #16`)

### Step 17: Playwright Browser E2E Suite (Auth, Google Login Flow, `.docx`, `.pptx`, Monitoring)
- [ ] Configure Playwright in `frontend/playwright.config.ts`.
- [ ] Write & run `frontend/e2e/auth_and_google.spec.ts` (registration, login, Google OAuth callback & token login flow).
- [ ] Write & run `frontend/e2e/docx_workflow.spec.ts` (`.docx` config + AI-Suggest Outline + generate + refine + like/dislike + comment + reconstruct + export).
- [ ] Write & run `frontend/e2e/pptx_workflow.spec.ts` (`.pptx` config + slide count/titles + generate + refine + feedback + comment + export).
- [ ] Write & run `frontend/e2e/monitoring_and_reconstruction.spec.ts`.
- [ ] Commit Step 17 (`Commit #17`)

### Step 18: Extensive Live End-to-End Runs & Visual Document Quality Inspection
- [ ] Execute live end-to-end runs using the real `GEMINI_API_KEY` for:
  - Full `.docx` business report (with AI-Suggest Outline, Gemini-generated images, iterative refinements, feedback, comments, export).
  - Full `.pptx` executive deck (with slide titles, Gemini-generated slide visuals, iterative refinements, speaker notes, export).
- [ ] Run programmatic structural checks (`tests/doc_quality/`) validating XML integrity, refined content accuracy, embedded images, and zero `.pptx` bounding-box overlap.
- [ ] Render exported `.docx` and `.pptx` pages/slides to PNG images (via LibreOffice headless / Docker container + `pdftoppm` or `pymupdf`) and **perform visual quality inspection** on the rendered pages, fixing any spacing, contrast, overflow, or layout issues discovered.
- [ ] Save visual inspection summary & metrics report in `docs/E2E_AND_VISUAL_QA_REPORT.md`.
- [ ] Commit Step 18 (`Commit #18`)

### Step 19: Comprehensive `README.md` & Final Verification Pass
- [ ] Write comprehensive root `README.md` covering:
  - Architecture overview & features (including Bonus AI-Suggest Outline, Gemini image generation, DB logging/monitoring/reconstruction)
  - Prerequisites & environment variable descriptions (`backend/.env.example`, `frontend/.env.example`)
  - Local setup (venv + npm) & standalone Docker deployment instructions
  - API & usage examples + Demo walkthrough guide aligned with Assignment 3 submission checklist
- [ ] Run full regression suite: backend `pytest` + frontend `vitest` + `next build` + Playwright E2E + Docker build checks.
- [ ] Commit Step 19 (`Commit #19`) -> **Push to `origin feat/platform-implementation` (Final Push)**

---

## Final Assignment & User Requirements Checklist

| Category | Requirement | Planned Step | Status |
|---|---|---|---|
| **Core Flow** | `Login → Configure → Generate → Refine → Export` end-to-end | Steps 6–18 | Pending |
| **Auth** | Secure email/password registration & JWT login | Step 6, 12 | Pending |
| **Google Auth** | Google Sign-In / OAuth2 + comprehensive tests | Step 6, 12, 17 | Pending |
| **Dashboard** | View existing projects & create new project | Step 7, 13 | Pending |
| **Config (`.docx`)** | Topic + add, remove, reorder section headers | Step 7, 13 | Pending |
| **Config (`.pptx`)** | Topic + slide count + title/heading per slide | Step 7, 13 | Pending |
| **Bonus Feature** | "AI-Suggest Outline" (topic only -> accept/edit/discard) | Step 8, 9, 13 | Pending |
| **AI Generation** | Context-aware section-by-section / slide-by-slide via Gemini | Step 8, 9 | Pending |
| **AI Images** | Gemini image generation embedded cleanly into docs | Step 8, 10, 18 | Pending |
| **Refinement UI** | Per-section AI refinement prompt, Like/Dislike, Comment box | Step 9, 14 | Pending |
| **DB Observability** | Logging (`audit_event_logs`), monitoring (`llm_call_metrics`), filtering & analytics | Step 4, 5, 9, 15 | Pending |
| **Reconstruction** | Point-in-time / version reconstruction & restore with diffs | Step 4, 5, 9, 14, 15 | Pending |
| **Export & Quality** | `python-docx` & `python-pptx` export + programmatic & visual QA | Step 10, 18 | Pending |
| **Standalone Deploy** | Independent `backend/` & `frontend/` deps + Dockerfiles + venv | Step 3, 11, 16 | Pending |
| **Docs & Repo** | Plans in `docs/`, comprehensive `README.md`, 1 commit/step, push/5 commits | Step 1–19 | In Progress |
