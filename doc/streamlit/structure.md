# CreatorPal Frontend Structure (Streamlit)

Last Updated: 2026-04-12  
Owner: Frontend / Integration

This document describes the current frontend code layout and runtime boundaries exactly as implemented in this repository.

## 1. Scope and Source of Truth

Frontend scope for Streamlit:
- `app/streamlit_app.py`
- `app/helpers/adapter.py`
- `app/helpers/components.py`
- `app/helpers/mock_pipeline.py` (development/runtime fallback)

If this document conflicts with code, code is the source of truth and this file must be updated.

## 2. Directory Layout

```text
app/
├── streamlit_app.py
└── helpers/
    ├── __init__.py
    ├── adapter.py
    ├── components.py
    └── mock_pipeline.py
```

## 3. Runtime Entrypoint and Page Lifecycle

Entrypoint:
- `main()` in `app/streamlit_app.py`

State machine:

```text
fresh load
  -> initialize session keys: dark_mode, last_result, last_error
  -> IDLE hero (when last_result is None)
  -> submit form
  -> LOADING spinner + pipeline.run(...)
  -> adapt(raw) success -> store last_result -> rerun -> DASHBOARD
  -> "New query" clears last_result/last_error -> rerun -> IDLE
```

Session keys:
- `dark_mode: bool`
- `last_result: dict | None`
- `last_error: str | None`

## 4. `streamlit_app.py` Responsibilities

`streamlit_app.py` is the only module that calls `st.*`.

Primary groups:
- Theme and assets:
  - `COLORS`
  - `LOGO_72`, `LOGO_32`
  - `FAVICON_DATA_URI`
  - `LIGHT_CSS`, `DARK_CSS`, `get_css(dark)`
- Pipeline acquisition:
  - `_env_flag_enabled(name)`
  - `get_pipeline(force_mock=False)` (`@st.cache_resource`)
- Render helpers:
  - `render_theme_toggle()`
  - `render_sidebar(dark)`
  - `render_page_header(dark)`
  - `render_idle_hero(dark, error_message)`
  - `render_metrics(data)`
  - `render_results_grid(data)`
  - card/html helper wrappers for ranked list, sentiment, report

## 5. Pipeline Acquisition Strategy

Current behavior:
1. Read `CREATORPAL_USE_MOCK_PIPELINE` (truthy: `1/true/yes/on/y`).
2. `get_pipeline(force_mock=...)`:
   - if forced: return `MockPipeline`
   - else: call `build_pipeline()`
   - if build fails or object has no `.run`: fallback to `MockPipeline`
3. Cache the pipeline object with `@st.cache_resource`.

Operational implication:
- Frontend is resilient for local/demo mode even when `src/pipeline.py` is incomplete.

## 6. Rendering Structure

### 6.1 Idle / Hero (`last_result is None`)

- Sidebar hidden via injected CSS.
- Theme toggle rendered as fixed top-right floating button.
- Hero includes:
  - large logo mark (`LOGO_72`)
  - title/tagline
  - centered form (`query_form`)
  - hint line
- Form fields:
  - `channel_or_query` (required at submit time)
  - `user_query` (optional; normalized to `None` when empty)
- Error card shown in hero when `last_error` exists.

### 6.2 Dashboard (`last_result` exists)

- Render left icon sidebar.
- Render compact header with:
  - `LOGO_32`
  - beta badge
  - theme toggle button
- Render `← New query` reset button.
- Render metric row (4 cards) + 2-column content grid:
  - left: ranked subreddit card (top 10)
  - right-top: sentiment card
  - right-bottom: strategy report card

## 7. Styling Architecture

Theme model:
- `get_css(dark: bool) -> DARK_CSS | LIGHT_CSS`
- CSS injected once at top of `main()`
- Both themes define:
  - page background
  - sidebar chrome
  - form and input styles
  - cards/metrics/rows/labels
  - animation keyframes and stagger classes
  - button styles including theme toggle

Animation model:
- Streamlit rerun remounts DOM, so entrance animations are mount-based (`@keyframes`).
- No explicit transition-out.

## 8. Adapter Boundary (`helpers/adapter.py`)

`adapt(raw)` is mandatory before rendering backend output.

Enforced contract:
- required top-level keys:
  - `input`
  - `ranked_subreddits`
  - `strategy_report`
  - `pal_results`
  - `sentiment_scores`
  - `meta`
- strict type checks with explicit key-path `ValueError` messages
- normalization rules:
  - subreddit name cleanup
  - reddit URL fallback synthesis
  - numeric coercion for score fields (`invalid -> None`)
  - sentiment key normalization to `r/<name>`
  - `meta` integer enforcement

## 9. HTML Components (`helpers/components.py`)

Pure string builders, no Streamlit calls:
- `metric_card_html(...)`
- `subreddit_row_html(...)`
- `sentiment_bar_html(...)`
- `error_card_html(...)`

Safety rules implemented:
- HTML escaping for labels/text/URLs
- reason truncation in subreddit rows
- robust numeric coercion for display

## 10. Error Handling and Recovery

Submit path:
- Empty query -> warning message, no backend call
- Backend/adapter exception -> store `last_error`, rerun, show structured error card
- On successful submit -> clear `last_error`, store adapted result

Reset path:
- `← New query` clears both `last_result` and `last_error`

## 11. Change Checklist

When changing frontend behavior:
1. Update code in `streamlit_app.py` / helpers.
2. Re-verify both light and dark themes.
3. Validate adapter contract assumptions.
4. Update `doc/streamlit/*.md` in same PR (this file + UIUX + interaction guide).

## 12. Local Run

```bash
streamlit run app/streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

Optional forced mock mode:

```bash
export CREATORPAL_USE_MOCK_PIPELINE=1
streamlit run app/streamlit_app.py
```
