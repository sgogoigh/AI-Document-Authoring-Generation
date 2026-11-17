# Scenario Testing & Database Performance Optimization Report

**Test Suite Location:** `backend/tests/scenarios/`  
**Total Scenario Cases:** **57 automated scenarios** (23 Word `.docx` builder scenarios, 20 PowerPoint `.pptx` builder scenarios, 8 multi-step situational AI & workflow scenarios, and 6 DB performance & observability benchmark scenarios).  
**Total Backend Tests Passing:** **77 unit, integration & scenario tests** (`pytest -m "not live_ai"`) + 2 live Gemini E2E suites.

---

## 1. Scenario Coverage Summary (`backend/tests/scenarios/`)

### 1.1 Word Builder Scenarios (`test_docx_builder_scenarios.py` — 23 cases)
- **Palettes & Fallbacks (6 cases):** `executive_navy`, `emerald_slate`, `obsidian_gold`, `warm_editorial`, unknown palette fallback, `None` theme config.
- **Editorial Tones & Metadata (4 cases):** `executive`, `analytical`, `persuasive`, `technical` rendered accurately into the cover metadata table.
- **Document Scaling (3 cases):** 1-section concise brief, 6-section standard report, 12-section enterprise monograph.
- **Adversarial & Formatting Edge Cases (6 cases):**
  - Unicode, emoji, CJK, and XML-special characters (`& < > " ' — € 東京 🚀`)
  - Fallback to `content_text` when `content_json` is `None`
  - Empty section payload (`{}`)
  - String-only bullet lists vs `{label, detail}` bullet dicts
  - Jagged & oversized `data_table` (5 columns x 7 rows cleanly clamped & padded to 4x6 max)
  - Missing image file on disk gracefully skipped without crashing export
- **Multi-Aspect Image Sizing (4 cases):** Panoramic (`1200x300`), tall portrait (`300x1000`), square (`512x512`), and small (`64x64`) PNGs.

### 1.2 PowerPoint Builder Scenarios (`test_pptx_builder_scenarios.py` — 20 cases)
- **Palettes & Fallbacks (6 cases):** All 4 curated palettes + invalid/missing fallbacks across 16:9 widescreen slides.
- **Agenda Scaling (4 cases):** 2-slide & 5-slide single-column Agenda vs 6-slide & 12-slide two-column Agenda grid.
- **Layout Fallbacks & Overflow Guards (6 cases):**
  - `two_column` with empty `secondary_bullets` falls back cleanly
  - `metrics_cards` with empty `metric_cards` falls back cleanly
  - `bullets_with_visual` with missing image file falls back cleanly
  - Extreme text clamping (200-char title, 300-char subtitle, 8 long bullets clamped to 5) with programmatic assertion that **zero shapes exceed slide bounds (`13.333" x 7.5"`)**
  - Multi-currency & Unicode metrics (`$`, `€`, `¥`, `🚀`)
  - `content_json=None` fallback to `content_text` bullet parsing
- **Multi-Aspect Visual Fitting (4 cases):** Center-fitted aspect-ratio preservation for `1400x400`, `400x1200`, `600x600`, and `80x80` PNGs.

### 1.3 Situational AI & Workflow Scenarios (`test_situational_ai_and_workflow_scenarios.py` — 8 multi-step cases)
- **`only_missing=True` Incremental Generation After Outline Edits:** Preserves previously refined sections (`REFINED_A_KEEP`), removes deleted sections, reorders remaining sections, generates only newly added sections, and exports in the exact new order.
- **5-Round Iterative Refinement Chain + Reconstruction:** Verifies revision chain `r1..r6`, `previous_content_json` / `new_content_json` audit links, and historical `v3` reconstruction.
- **Mid-Generation Upstream Failure:** Simulates Gemini failure on Section 2, confirming `LLMCallMetric(status="error")` persistence and clean HTTP `502` handling.
- **JSON Text Fallback & Malformed JSON Resilience:** Exercises `response.text` JSON parsing fallback and malformed JSON error metric logging.
- **Empty Image Response & Missing Disk Asset at Export:** Ensures empty image candidates do not fail section text generation, missing PNG files on disk skip gracefully on export, and special characters in titles sanitize cleanly in `Content-Disposition` filenames.
- **Image Toggle Guards (2 cases):** Verifies `theme_config.include_images=False` and `ENABLE_IMAGE_GENERATION=false` skip image model calls.
- **Feedback Cycle, Comment Soft-Delete, `event_seq_id` / `at_timestamp` Reconstruction & Cross-User 403 Isolation:** Verifies full `FeedbackEvent` history, comment soft-delete filtering, seq-ID and timestamp reconstruction, and `403 Forbidden` isolation across 9 protected project/section/monitoring endpoints.

---

## 2. Database Performance & Observability Benchmarks

Measured via SQLAlchemy `before_cursor_execute` instrumentation on a seeded multi-project workspace (up to 25 projects, 150 sections, 300 revisions, 500 `audit_event_logs` with JSON payloads, and 500 `llm_call_metrics`).

### Bottlenecks Identified & Fixes Applied
1. **`ProjectService.list_projects` (`backend/app/services/project_service.py`):**
   - *Before:* N+1 loop executing 2 queries per project (`DocumentSection` scan + `ExportRecord` count).
   - *Optimization:* Replaced per-project queries with 2 batched SQL `GROUP BY project_id` queries (`CASE WHEN` aggregation for likes/dislikes + export counts).
2. **`ProjectService.build_project_detail` (`backend/app/services/project_service.py`):**
   - *Before:* N+1 loop executing 3 queries per section (`SectionComment`, `DocumentAsset`, `SectionRevision` count).
   - *Optimization:* Replaced with 3 batched `WHERE section_id IN (...)` / `GROUP BY section_id` queries.
3. **`AuditService.compute_analytics` (`backend/app/services/audit_service.py`):**
   - *Before:* Loaded every `LLMCallMetric` and `AuditEventLog` ORM row (including large `before_state_json` / `after_state_json` blobs) into Python memory.
   - *Optimization:* Pushed aggregation to SQL (`COUNT`, `SUM`, `GROUP BY operation, status`, `GROUP BY event_type`, `GROUP BY like_status`) and fetched only sorted scalar `latency_ms` values for percentile calculation.
4. **`ReconstructionService` (`backend/app/services/reconstruction_service.py`):**
   - *Before:* Queried comments, assets, revisions, and feedback events inside per-section loops.
   - *Optimization:* Batched project-scoped queries mapped by `section_id` in Python.

### Measured Results (Before vs. After)

| Operation | Seeded Scale | Before | After | Improvement |
|---|---|---|---|---|
| `ProjectService.list_projects` | 25 projects, 150 sections | 51 queries / 17.62 ms | **3 queries / 8.51 ms** | **-94.1% queries (O(1))**, 2.1× faster |
| `ProjectService.build_project_detail` | 12 sections + comments/assets/revs | 37 queries / 13.49 ms | **4 queries / 7.84 ms** | **-89.2% queries (O(1))**, 1.7× faster |
| `AuditService.compute_analytics` | 500 LLM + 500 Audit rows | 5 full ORM scans / 35.06 ms | **5 SQL aggregations / 8.98 ms** | **3.9× faster**, zero JSON blob hydration |
| `ReconstructionService` (snapshot) | 10 sections + comments/assets | 22 queries / 7.41 ms | **4 queries / 4.71 ms** | **-81.8% queries**, 1.6× faster |
| `ReconstructionService` (replay) | 10 sections + revs/fb/comments | 52 queries / 21.74 ms | **7 queries / 9.06 ms** | **-86.5% queries**, 2.4× faster |
| `AuditService.query_logs` (3 filters) | 500 Audit rows w/ JSON | 6 queries / 9.32 ms | **6 queries / 8.88 ms** | Indexed `< 10 ms` across 3 faceted lookups |
