# Architecture & Database Schema Specification

## 1. High-Level System Architecture

The platform is designed as two **standalone, independently deployable services** with separate dependency manifests, virtual environments / build pipelines, and Dockerfiles:

1. **Backend Service (`backend/`)** — **FastAPI** (Python 3.13)
   - Handles authentication (JWT email/password + Google OAuth2/OIDC verification), project/outline management, Gemini LLM orchestration (outline suggestion, context-aware section/slide generation, iterative section refinement, and image generation), audit logging, monitoring metrics, point-in-time reconstruction, and `.docx` / `.pptx` document assembly (`python-docx`, `python-pptx`).
   - Packaged with its own `requirements.txt`, `pyproject.toml`, `.venv`, and `backend/Dockerfile`.
2. **Frontend Service (`frontend/`)** — **Next.js (App Router, TypeScript, Tailwind CSS)**
   - Provides a responsive, high-craft editorial workspace UI: landing/auth pages (including "Continue with Google"), Project Dashboard, Document Configuration Wizard (`.docx` outline builder, `.pptx` slide planner, and **"AI-Suggest Outline"** bonus workflow), Interactive Section/Slide Refinement Studio (refinement prompt, Like/Dislike, comments, inline image preview, revision history & point-in-time reconstruction drawer), Monitoring & Audit Analytics Console, and Export controls.
   - Packaged with its own `package.json`, `next.config.ts` (`output: "standalone"`), and `frontend/Dockerfile`.
3. **Database Layer**
   - SQLAlchemy 2.0 + Alembic migrations supporting **SQLite** (zero-config local/CI dev) and **PostgreSQL** (production/Docker Compose) via `DATABASE_URL`.

```text
+--------------------------+        HTTPS / REST (JSON + Blob)        +-------------------------------+
|   Frontend (Next.js)     | <--------------------------------------> |     Backend (FastAPI)         |
|  - App Router + TS       |                                          |  - Auth (JWT + Google OIDC)   |
|  - Tailwind + Motion     |                                          |  - Gemini Service (Text+Img)  |
|  - Standalone Dockerfile |                                          |  - Doc Builders (docx/pptx)   |
+--------------------------+                                          |  - Audit & Reconstruction     |
                                                                      |  - Standalone Dockerfile      |
                                                                      +---------------+---------------+
                                                                                      |
                                                      +-------------------------------+-------------------------------+
                                                      |                               |                               |
                                                      v                               v                               v
                                          +-----------------------+       +-----------------------+       +-----------------------+
                                          |  SQLite / PostgreSQL  |       |  Gemini API (Google)  |       |  Asset Storage        |
                                          |  - Core Domain        |       |  - Text (JSON Schema) |       |  - Generated PNGs     |
                                          |  - Audit Event Logs   |       |  - Image Generation   |       |  - Export Artifacts   |
                                          |  - LLM Metrics        |       +-----------------------+       +-----------------------+
                                          |  - Snapshots          |
                                          +-----------------------+
```

---

## 2. Standalone Repository Structure

```text
AI-Document-Authoring-Generation/
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── .env.example
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   └── logging_middleware.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── section.py
│   │   │   ├── audit.py
│   │   │   └── metrics.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── project.py
│   │   │   ├── generation.py
│   │   │   ├── llm_structured.py
│   │   │   └── monitoring.py
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── google_oauth_service.py
│   │   │   ├── gemini_service.py
│   │   │   ├── project_service.py
│   │   │   ├── audit_service.py
│   │   │   ├── reconstruction_service.py
│   │   │   └── doc_builder/
│   │   │       ├── __init__.py
│   │   │       ├── theme.py
│   │   │       ├── docx_builder.py
│   │   │       └── pptx_builder.py
│   │   └── api/
│   │       └── v1/
│   │           ├── router.py
│   │           ├── health.py
│   │           ├── auth.py
│   │           ├── projects.py
│   │           ├── generation.py
│   │           ├── export.py
│   │           └── monitoring.py
│   └── tests/
│       ├── conftest.py
│       ├── unit/
│       ├── integration/
│       ├── doc_quality/
│       └── e2e/
├── frontend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── .env.example
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── login/page.tsx
│   │   │   ├── register/page.tsx
│   │   │   ├── auth/google/callback/page.tsx
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── projects/new/page.tsx
│   │   │   ├── projects/[id]/page.tsx
│   │   │   └── monitoring/page.tsx
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   ├── auth/
│   │   │   ├── dashboard/
│   │   │   ├── configurator/
│   │   │   ├── studio/
│   │   │   └── monitoring/
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── auth-context.tsx
│   │   │   └── types.ts
│   │   └── __tests__/
│   └── e2e/
├── docs/
│   ├── IMPLEMENTATION_PLAN.md
│   ├── ARCHITECTURE_AND_DB_SCHEMA.md
│   └── TEST_AND_VERIFICATION_PLAN.md
├── docker-compose.yml
└── README.md
```

---

## 3. Database Schema (Core + Logging, Monitoring & Reconstruction)

### 3.1 Core Domain Tables

#### `users`
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `email` | `String(255)` | Unique, indexed, not null |
| `full_name` | `String(255)` | Not null |
| `password_hash` | `String(255)` | Nullable (null for pure Google OAuth accounts) |
| `auth_provider` | `String(32)` | `local` \| `google` \| `hybrid` |
| `google_sub` | `String(255)` | Unique, nullable, indexed |
| `avatar_url` | `String(1024)` | Nullable |
| `is_active` | `Boolean` | Default `true` |
| `last_login_at` | `DateTime(tz)` | Nullable |
| `created_at` | `DateTime(tz)` | Not null |
| `updated_at` | `DateTime(tz)` | Not null |

#### `projects`
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `user_id` | `String(36)` | FK -> `users.id`, indexed |
| `title` | `String(255)` | Not null |
| `doc_type` | `String(16)` | `docx` \| `pptx` |
| `main_topic` | `Text` | Not null |
| `status` | `String(32)` | `draft` \| `configured` \| `generating` \| `ready` \| `error` |
| `theme_config_json` | `JSON` | Color theme, tone, target audience, image preference |
| `ai_outline_suggested` | `Boolean` | Tracks bonus feature usage |
| `current_version` | `Integer` | Monotonic version counter incremented on state changes |
| `created_at` | `DateTime(tz)` | Not null |
| `updated_at` | `DateTime(tz)` | Not null |
| `deleted_at` | `DateTime(tz)` | Nullable (soft delete for auditability) |

#### `document_sections`
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `project_id` | `String(36)` | FK -> `projects.id`, indexed |
| `order_index` | `Integer` | 0-based order (`section_index` / `slide_index`) |
| `title` | `String(255)` | Section header or slide title |
| `section_kind` | `String(32)` | `section` \| `slide` |
| `current_revision_id` | `String(36)` | Nullable FK -> `section_revisions.id` |
| `current_content_json` | `JSON` | Latest structured LLM/refined payload |
| `current_content_text` | `Text` | Rendered readable markdown/plain text |
| `like_status` | `String(16)` | `none` \| `like` \| `dislike` |
| `is_deleted` | `Boolean` | Default `false` (preserves history on outline edits) |
| `created_at` | `DateTime(tz)` | Not null |
| `updated_at` | `DateTime(tz)` | Not null |

#### `section_revisions`
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `section_id` | `String(36)` | FK -> `document_sections.id`, indexed |
| `project_id` | `String(36)` | FK -> `projects.id`, indexed |
| `revision_number` | `Integer` | 1, 2, 3... per section |
| `project_version` | `Integer` | Ties revision to project timeline version |
| `source` | `String(32)` | `initial_generation` \| `ai_refinement` \| `manual_edit` \| `restore` |
| `refinement_prompt` | `Text` | Nullable (prompt entered by user) |
| `previous_content_json` | `JSON` | Nullable snapshot before change |
| `new_content_json` | `JSON` | Snapshot after change |
| `diff_summary_json` | `JSON` | Field-level delta summary (word count delta, changed keys) |
| `llm_metric_id` | `String(36)` | Nullable FK -> `llm_call_metrics.id` |
| `created_by` | `String(36)` | FK -> `users.id` |
| `created_at` | `DateTime(tz)` | Not null, indexed |

#### `section_comments`
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `section_id` | `String(36)` | FK -> `document_sections.id`, indexed |
| `project_id` | `String(36)` | FK -> `projects.id`, indexed |
| `user_id` | `String(36)` | FK -> `users.id` |
| `body` | `Text` | Not null |
| `created_at` | `DateTime(tz)` | Not null |
| `updated_at` | `DateTime(tz)` | Not null |
| `deleted_at` | `DateTime(tz)` | Nullable |

#### `feedback_events`
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `section_id` | `String(36)` | FK -> `document_sections.id`, indexed |
| `project_id` | `String(36)` | FK -> `projects.id`, indexed |
| `user_id` | `String(36)` | FK -> `users.id` |
| `revision_id` | `String(36)` | Nullable FK -> `section_revisions.id` |
| `rating` | `String(16)` | `like` \| `dislike` \| `none` |
| `note` | `Text` | Nullable |
| `created_at` | `DateTime(tz)` | Not null, indexed |

#### `document_assets`
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `project_id` | `String(36)` | FK -> `projects.id`, indexed |
| `section_id` | `String(36)` | Nullable FK -> `document_sections.id`, indexed |
| `asset_type` | `String(32)` | `generated_image` |
| `prompt` | `Text` | Image generation prompt |
| `mime_type` | `String(64)` | e.g., `image/png` |
| `storage_path` | `String(1024)` | Local/volume relative path |
| `caption` | `String(512)` | Caption rendered below image |
| `width` | `Integer` | Pixels |
| `height` | `Integer` | Pixels |
| `is_active` | `Boolean` | Default `true` |
| `llm_metric_id` | `String(36)` | Nullable FK -> `llm_call_metrics.id` |
| `created_at` | `DateTime(tz)` | Not null |

#### `export_records`
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `project_id` | `String(36)` | FK -> `projects.id`, indexed |
| `user_id` | `String(36)` | FK -> `users.id` |
| `doc_type` | `String(16)` | `docx` \| `pptx` |
| `project_version` | `Integer` | Exact project version exported |
| `file_name` | `String(255)` | Output filename |
| `file_size_bytes` | `Integer` | Output size |
| `section_count` | `Integer` | Sections/slides included |
| `asset_count` | `Integer` | Embedded images included |
| `status` | `String(32)` | `success` \| `error` |
| `created_at` | `DateTime(tz)` | Not null, indexed |

---

### 3.2 Logging, Monitoring & Reconstruction Tables

#### `audit_event_logs` (Append-Only Event Stream)
| Column | Type | Constraints / Notes |
|---|---|---|
| `seq_id` | `Integer` | Auto-increment monotonic sequence for strict ordering |
| `event_id` | `String(36)` | Unique UUID |
| `trace_id` | `String(64)` | Request correlation ID from middleware, indexed |
| `user_id` | `String(36)` | Nullable FK -> `users.id`, indexed |
| `project_id` | `String(36)` | Nullable FK -> `projects.id`, indexed |
| `section_id` | `String(36)` | Nullable FK -> `document_sections.id`, indexed |
| `event_type` | `String(64)` | e.g., `AUTH_REGISTER`, `AUTH_LOGIN`, `AUTH_GOOGLE`, `PROJECT_CREATE`, `OUTLINE_SUGGEST`, `OUTLINE_CONFIGURE`, `CONTENT_GENERATE`, `SECTION_REFINE`, `FEEDBACK_RECORD`, `COMMENT_CREATE`, `IMAGE_GENERATE`, `DOC_EXPORT`, `PROJECT_RESTORE`, `HTTP_ERROR` |
| `severity` | `String(16)` | `INFO` \| `WARN` \| `ERROR` |
| `entity_type` | `String(64)` | `user` \| `project` \| `section` \| `comment` \| `asset` \| `export` |
| `entity_id` | `String(36)` | Target entity UUID |
| `http_method` | `String(16)` | Nullable |
| `endpoint` | `String(255)` | Nullable |
| `status_code` | `Integer` | Nullable |
| `duration_ms` | `Float` | Nullable |
| `before_state_json` | `JSON` | Nullable state before mutation |
| `after_state_json` | `JSON` | Nullable state after mutation |
| `metadata_json` | `JSON` | Additional filterable attributes |
| `created_at` | `DateTime(tz)` | Not null, indexed |

#### `llm_call_metrics` (AI Observability & Cost/Latency Monitoring)
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `trace_id` | `String(64)` | Indexed |
| `user_id` | `String(36)` | FK -> `users.id`, indexed |
| `project_id` | `String(36)` | Nullable FK -> `projects.id`, indexed |
| `section_id` | `String(36)` | Nullable FK -> `document_sections.id`, indexed |
| `operation` | `String(64)` | `outline_suggest` \| `section_generate` \| `section_refine` \| `image_generate` |
| `provider` | `String(32)` | `gemini` |
| `model_name` | `String(128)` | e.g., `gemini-2.5-flash`, `gemini-2.5-flash-image` |
| `input_tokens` | `Integer` | Default `0` |
| `output_tokens` | `Integer` | Default `0` |
| `total_tokens` | `Integer` | Default `0` |
| `latency_ms` | `Float` | End-to-end API latency |
| `status` | `String(32)` | `success` \| `fallback` \| `error` |
| `error_message` | `Text` | Nullable |
| `prompt_preview` | `String(500)` | Truncated prompt for quick inspection |
| `created_at` | `DateTime(tz)` | Not null, indexed |

#### `project_snapshots` (Materialized Version Checkpoints for Reconstruction)
| Column | Type | Constraints / Notes |
|---|---|---|
| `id` | `String(36)` (UUID) | Primary key |
| `project_id` | `String(36)` | FK -> `projects.id`, indexed |
| `version_number` | `Integer` | Matches `projects.current_version` at capture time |
| `trigger_event_type` | `String(64)` | What triggered this checkpoint |
| `trigger_event_id` | `String(36)` | Reference to `audit_event_logs.event_id` |
| `snapshot_json` | `JSON` | Full serialized project config, sections, revisions, comments, feedback, active asset IDs |
| `created_at` | `DateTime(tz)` | Not null, indexed |

### 3.3 Reconstruction & Analytics Design
1. **Point-in-Time Reconstruction (`ReconstructionService`):**
   - Given `(project_id, target_version)` or `(project_id, at_timestamp)` or `(project_id, event_seq_id)`:
   - Finds the closest `project_snapshots` checkpoint at or before the target, or replays `audit_event_logs` + `section_revisions` + `feedback_events` + `section_comments` up to the target cutoff.
   - Returns:
     - Reconstructed document outline & every section's exact content at that point
     - Comments & feedback active at that point
     - Structured diff against the current live state
     - Optional **Restore** action (`POST /api/v1/projects/{id}/restore/{version}`) which creates a new `restore` revision (preserving forward audit history—never erasing past events).
2. **Filtering & Analysis (`AuditService` + Monitoring APIs):**
   - Multi-facet filtering on `audit_event_logs` and `llm_call_metrics`: by `project_id`, `event_type`, `operation`, `severity`, `status`, `model_name`, `date_from`, `date_to`, `trace_id`, and keyword search.
   - Aggregated analytics endpoints: total/average LLM tokens, latency percentiles (`p50`, `p95`), error rate, feedback ratios (`like` vs `dislike`), refinement frequency per section, and export counts.

---

## 4. Structured AI Generation & Document Assembly Design

### 4.1 LLM Creativity vs. Deterministic Code Structure
The **LLM generates structured JSON content**, while **Python backend builders enforce strict layout, visual hierarchy, and pagination/bounds**:

* **For `.docx` sections (`DocxSectionSchema`):**
  * `summary_callout`: 1–2 sentence executive takeaway rendered in an accented callout block.
  * `paragraphs`: 2–3 well-formed body paragraphs.
  * `bullet_points`: 3–6 structured bullets with bold lead-ins (`label`, `detail`).
  * `data_table`: Optional structured table (`headers[]`, `rows[][]`) capped at <= 4 columns and <= 6 rows.
  * `should_generate_image` + `image_prompt` + `image_caption`: Selective visual generation for sections where a conceptual diagram or editorial illustration adds high value.
* **For `.pptx` slides (`PptxSlideSchema`):**
  * `layout_variant`: `bullets_only` | `bullets_with_visual` | `two_column` | `metrics_cards`
  * `kicker`: Short 2–4 word section eyebrow label.
  * `subtitle`: Concise 1-line slide takeaway (<= 14 words).
  * `bullets`: 3–5 concise bullets (<= 18 words each) to guarantee zero text overflow.
  * `key_stat`: Optional highlight metric (`value`, `label`).
  * `speaker_notes`: Detailed presenter notes written into the PowerPoint notes pane.
  * `should_generate_image` + `image_prompt` + `image_caption`: Generated via Gemini image generation and placed into dedicated image frames with aspect-ratio fitting.

### 4.2 Deterministic Document Assembly (`python-docx` & `python-pptx`)
* **Word (`.docx`):**
  * Custom corporate/editorial typography palette, title cover page (title, subtitle, author/date metadata), styled Table of Contents / Outline overview, numbered Heading 1 sections, executive summary callouts with subtle left-border shading, formatted bullet lists, styled header-shaded tables, centered captioned Gemini images (`Inches(5.6)` max width), and running header + page-number footer.
* **PowerPoint (`.pptx`):**
  * Widescreen 16:9 (`13.333" x 7.5"`), cohesive dark-accent cover slide, Agenda/Overview slide, layout-dispatched content slides (clean top accent bar, kicker + bold slide title + takeaway subtitle, structured cards/columns/bullets, embedded Gemini visual with shadow/frame and caption, consistent footer + slide number), and populated presenter speaker notes on every slide.
