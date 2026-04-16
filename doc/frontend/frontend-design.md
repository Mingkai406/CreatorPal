# CreatorPal Frontend Engineering Guide (Implementation-Aligned)

Last Updated: 2026-04-12  
Branch Baseline: `feature/frontend-deploy`  
Primary Files:
- `app/streamlit_app.py`
- `app/helpers/adapter.py`
- `app/helpers/components.py`
- `app/helpers/mock_pipeline.py`

## 1. Purpose

This guide defines how to extend or modify the Streamlit frontend without breaking:
- the UI state machine
- the adapter contract boundary
- light/dark rendering parity
- local demo reliability (mock fallback)

## 2. Engineering Boundaries

Hard boundaries in current code:
- `streamlit_app.py`: all `st.*` calls and page orchestration only.
- `adapter.py`: contract validation + normalization only; no UI logic.
- `components.py`: pure HTML string builders; no `st.*` calls.
- `mock_pipeline.py`: deterministic contract-compliant fallback payload.

Do not move these responsibilities across files.

## 3. Runtime Contract Between Frontend and Backend

Frontend invokes:

```python
pipeline.run(channel_or_query: str, user_query: str | None = None) -> dict[str, Any]
```

Payload must pass `adapt(raw)` before any render.

Required top-level keys:
- `input`
- `ranked_subreddits`
- `strategy_report`
- `pal_results`
- `sentiment_scores`
- `meta`

Failure policy:
- Any exception in `run()` or `adapt()` is captured and shown as `cp-error`.
- UI must stay interactive; no raw traceback.

## 4. Pipeline Bootstrap Policy

Current bootstrap behavior in `get_pipeline()`:
- forced mock when `CREATORPAL_USE_MOCK_PIPELINE` is enabled
- otherwise `build_pipeline()` from `src.pipeline`
- on construction failure or invalid object, fallback to `MockPipeline`
- object cached via `@st.cache_resource`

Implication:
- local/demo runs remain available even while backend is incomplete.

## 5. UI State and Session Rules

Required session keys:
- `dark_mode` (default `False`)
- `last_result` (default `None`)
- `last_error` (default `None`)

State transitions:
- IDLE hero when `last_result is None`
- DASHBOARD when `last_result` is present
- reset button clears `last_result` + `last_error`
- successful submit clears `last_error`

## 6. Styling and Motion Rules

Theme model:
- two CSS blocks (`LIGHT_CSS`, `DARK_CSS`)
- selected by `get_css(dark)`

Global rules:
- keep sidebar at `60px` in dashboard
- keep theme toggle at `32x32` in both themes
- maintain existing animation class names (`cp-db-*`, `cp-hero-*`)
- keep `cp-` class prefix for custom elements

If adding new components:
- implement both light and dark styles in the same change
- verify spacing parity between themes

## 7. Rendering Rules by Section

Hero:
- form id remains `query_form`
- primary input is required at submit
- hero form width remains capped for readability (`max-width: 680px`)

Dashboard header:
- includes compact logo, subtitle, Beta badge, theme toggle

Metrics:
- four cards, fixed order:
  1. subreddits found
  2. top rerank score
  3. avg sentiment
  4. latency

Main content:
- left: ranked communities (top 10)
- right: sentiment + report stack

## 8. Security and Data Hygiene

Current code guarantees:
- HTML escaping for message/text fields in `components.py`
- URL normalization/fallback in `adapter.py`

Rules for future changes:
- never inject raw user text into HTML without escaping
- keep URL scheme validation (`http/https`) or fallback
- avoid exposing secrets in backend error strings

## 9. Change Workflow (Required)

When changing UI or contract-sensitive behavior:
1. Modify code.
2. Update docs in `doc/frontend/` in the same PR.
3. Verify light and dark mode visually.
4. Verify mock and real pipeline code paths.
5. Run at least one manual submit flow and one error flow.

## 10. Manual Regression Checklist

1. Idle page shows hero, no sidebar, floating theme toggle.
2. Toggle works in idle and dashboard.
3. Empty query submit is blocked with warning.
4. Loading spinner appears during run.
5. Success renders metrics + list + sentiment + report.
6. Reset button returns to hero and clears stale data.
7. Backend/adapter exception renders error card and app remains usable.
8. Links in ranked card are clickable and open new tabs.

## 11. Non-Goals

This guide does not define:
- retrieval/model quality targets
- business logic inside backend pipeline components
- infrastructure deployment topology

Those belong to backend/system documentation.
