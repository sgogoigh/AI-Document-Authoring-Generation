# Comprehensive Test & Verification Plan

This document defines the multi-layer testing, validation, and visual verification strategy to guarantee every requirement (functional, AI, database observability/reconstruction, security, UI/UX, document quality, and standalone Docker deployment) is thoroughly tested.

---

## 1. Backend Test Suite (`backend/tests/`, `pytest`)

### 1.1 Unit Tests (`backend/tests/unit/`)
1. **`test_security_and_jwt.py`**
   - Password hashing & verification (wrong password fails, strong hash generated).
   - Access token creation, expiration claims, tampered token rejection, invalid signature rejection.
   - Google OIDC token verifier unit tests (valid RSA-signed mock ID token -> claims extracted; expired/wrong `aud`/unverified email -> rejected).
2. **`test_schemas_and_diff.py`**
   - Pydantic validation for `DocxSectionSchema` and `PptxSlideSchema` (enforces bullet limits, table dimension caps, layout variants).
   - Structured diff helper accurately computes field-level changes and word count deltas between revisions.
3. **`test_docx_builder_unit.py`**
   - Generates `.docx` from synthetic multi-section payloads (cover page, TOC, callouts, paragraphs, bullets, tables, embedded PNG images).
   - Re-opens output via `python-docx` and asserts: valid ZIP/OOXML, expected section headings in exact order, table cell values, embedded media count (`inline_shapes`), and header/footer presence.
4. **`test_pptx_builder_unit.py`**
   - Generates `.pptx` from synthetic multi-slide payloads across all layout variants (`bullets_only`, `bullets_with_visual`, `two_column`, `metrics_cards`).
   - Re-opens output via `python-pptx` and asserts: 16:9 slide dimensions (`13.333" x 7.5"`), exact slide count (cover + agenda + N content slides), non-overlapping bounding boxes, embedded picture shapes, populated speaker notes, and no empty placeholders.
5. **`test_reconstruction_unit.py`**
   - Tests snapshot + event replay reconstruction logic across multiple revisions, outline reorders, comment additions/deletions, and feedback toggles.
   - Verifies reconstructing version `v1`, `v2`, `v3` returns exact historical state without mutating current state.

### 1.2 Integration Tests (`backend/tests/integration/`)
Using FastAPI `TestClient` / `httpx.AsyncClient` with isolated SQLite test DB and mocked Gemini service (plus separate live Gemini suite):
1. **`test_auth_and_google_oauth_api.py`**
   - `POST /api/v1/auth/register` (happy path, duplicate email 409, weak password 422).
   - `POST /api/v1/auth/login` (happy path, invalid credentials 401).
   - `POST /api/v1/auth/google` (valid ID token creates user with `auth_provider=google`, subsequent login updates `last_login_at`, existing local user with same verified email links safely as `hybrid`).
   - `GET /api/v1/auth/me` (valid JWT vs missing/expired/invalid JWT).
2. **`test_projects_and_outline_api.py`**
   - Create `.docx` and `.pptx` projects, list user's projects, enforce cross-user isolation (User B gets 403/404 on User A's project).
   - Update `.docx` outline (add, remove, reorder section headers) and `.pptx` slide count + slide titles.
   - **Bonus feature:** `POST /api/v1/projects/suggest-outline` (with main topic only) returns structured headers/slide titles; verify user can accept, edit, or discard.
3. **`test_generation_and_refinement_api.py`**
   - Section-by-section / slide-by-slide generation stores `section_revisions` (`revision_number=1`), `llm_call_metrics`, and `document_assets` (when image generated).
   - Per-section refinement (`POST /api/v1/sections/{id}/refine`) updates only the targeted section, increments `revision_number`, preserves `previous_content_json`, leaves sibling sections untouched, and records `refinement_prompt`.
   - Feedback (`like` / `dislike` / `none`) writes to `feedback_events` and updates `like_status`.
   - Comments (`POST`, `GET`, `DELETE`) persist and enforce ownership.
4. **`test_export_api.py`**
   - Exporting `.docx` returns `200`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, valid downloadable attachment header, and latest refined text (not initial stale text).
   - Exporting `.pptx` returns `200`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`, valid slides reflecting latest refined text + embedded images.
   - Verifies `export_records` row is created with accurate `project_version`, `file_size_bytes`, `section_count`, and `asset_count`.
5. **`test_monitoring_and_reconstruction_api.py`**
   - Tests `GET /api/v1/monitoring/logs` filtering by `project_id`, `event_type`, `severity`, `trace_id`, `date_from`/`date_to`, and search query.
   - Tests `GET /api/v1/monitoring/metrics` returns accurate token totals, latency stats, operation breakdowns, and feedback ratios.
   - Tests `GET /api/v1/projects/{id}/reconstruct?version=1` vs `?version=2` vs `?at_timestamp=...` and `POST /api/v1/projects/{id}/restore/1`.

---

## 2. Live Gemini API & Document Quality Tests (`backend/tests/live_ai/`)
Executed using the real `GEMINI_API_KEY` from `.env`:
1. **Live Outline Suggestion:** Word topic + PowerPoint topic -> verify clean structured headings/slide titles.
2. **Live Content Generation + Image Generation:**
   - Full `.docx` run (e.g., *"A market analysis of the EV industry in 2025"* with 4–5 sections + generated images).
   - Full `.pptx` run (e.g., *"Enterprise AI Adoption Strategy 2026"* with 5 slides + generated images).
3. **Live Iterative Refinement:**
   - Run refinements like *"Make this more formal"*, *"Convert to bullet points"*, *"Shorten to 80 words"* and verify semantic & structural adherence.
4. **Structural & Visual Output Quality Check (`doc_quality`):**
   - Programmatic inspection of exported `.docx` and `.pptx` files:
     - All sections/slides present in exact configured order
     - Latest refined content matches exported text
     - Embedded Gemini images are non-empty valid PNGs with proper dimensions
     - No bounding-box overlap or out-of-slide coordinates in `.pptx`
   - **Visual Inspection:** Convert exported `.docx` and `.pptx` to PDF/PNG pages (via LibreOffice/rendering container or local renderer) and visually inspect the rendered pages/slides to confirm typography, alignment, contrast, margins, table styling, and image quality.

---

## 3. Frontend Test Suite (`frontend/`)

### 3.1 Unit & Component Tests (`Vitest` + `React Testing Library`)
1. Auth forms (`LoginForm`, `RegisterForm`, `GoogleSignInButton` rendering & callback handling, validation errors).
2. Dashboard (`ProjectCard`, filter/search by doc type/status, empty state, delete confirmation).
3. Document Configurator (`DocTypeSelector`, `DocxOutlineEditor` add/remove/reorder, `PptxSlidePlanner` slide count + titles, `AISuggestOutlineModal` accept/edit/discard).
4. Interactive Refinement Studio (`SectionEditorCard`, refinement prompt submission & loading state, Like/Dislike toggle state, Comment box add/delete, Revision History & Reconstruction diff drawer).
5. Monitoring & Analytics Console (audit log filter bar, LLM metrics summary cards, timeline reconstruction preview).

### 3.2 End-to-End Browser Tests (`Playwright`)
Full-stack browser runs against live Next.js + live FastAPI + real SQLite DB + real Gemini API:
1. **Auth & Google Login Flow:**
   - Standard user registration -> logout -> login -> dashboard load.
   - Google Sign-In flow test: verifies Google OAuth redirect/token exchange endpoint + UI session establishment (with real OAuth callback route and signed OIDC token test harness; plus live Google button verification if client ID is configured).
2. **Word (`.docx`) End-to-End Flow:**
   - Create `.docx` project -> test **"AI-Suggest Outline"** -> edit/reorder sections -> generate content + images -> refine section 1 ("Shorten to 100 words") -> Like section 1 -> Dislike section 2 -> add comments -> inspect Revision History & Reconstruction -> Export `.docx` -> verify non-empty valid `.docx` downloaded.
3. **PowerPoint (`.pptx`) End-to-End Flow:**
   - Create `.pptx` project -> set slide count & custom slide titles -> generate slides + images -> refine slide 2 ("Convert to concise executive bullet points") -> toggle feedback & add comment -> Export `.pptx` -> verify valid `.pptx` downloaded.
4. **Monitoring & Reconstruction Flow:**
   - Open Monitoring Console -> filter audit logs by project & event type -> inspect LLM token/latency metrics -> reconstruct historical version and verify diff.

---

## 4. Standalone Deployment & Docker Verification
1. Build `backend` standalone Docker image (`docker build -t docgen-backend ./backend`) and run healthcheck + API smoke test.
2. Build `frontend` standalone Docker image (`docker build -t docgen-frontend ./frontend`) and run HTTP smoke test.
3. Verify `docker-compose up --build` starts backend + frontend (+ optional PostgreSQL) cleanly and serves end-to-end traffic.
