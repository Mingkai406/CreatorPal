# CreatorPal Frontend Engineering Spec (Aligned)

Last Updated: 2026-04-11  
Owner: Ziqi (Person D)  
Branch: `feature/frontend-deploy`  
Aligned With: `structure.md` (v1.1), `UIUX.md` (v1.1)

## 1. Purpose

This document is the execution spec for frontend implementation.  
It is intentionally aligned to:
- structural boundaries in `structure.md`
- visual and interaction standards in `UIUX.md`
- strict pipeline contract policy confirmed by project owner

## 2. Scope

In scope:
- `app/streamlit_app.py`
- `app/helpers/adapter.py`
- `app/helpers/components.py`
- frontend/deploy docs update in `README.md`

Out of scope:
- retrieval quality or model internals
- PAL logic changes
- full backend pipeline implementation

## 3. Hard Demo Requirement

Karl demo gate is mandatory:
- every recommended subreddit must have a clickable full Reddit URL
- frontend must enforce fallback URL when URL is missing

Fallback rule:
- `url = f"https://www.reddit.com/r/{subreddit}/"` after subreddit normalization

## 4. Target Frontend Structure

Follow `structure.md` layout:

```text
app/
├── streamlit_app.py
└── helpers/
    ├── __init__.py
    ├── adapter.py
    └── components.py
```

Boundary rules:
- `streamlit_app.py` contains all `st.*` calls and page orchestration.
- `helpers/adapter.py` contains schema validation and normalization only.
- `helpers/components.py` contains pure HTML-returning functions, no `st.*`.

## 5. Pipeline Contract (Strict Required Keys)

`pipeline.run(channel_or_query: str, user_query: str | None = None) -> dict[str, Any]`

Default contract policy:
- all listed top-level keys are required
- missing required key is a contract violation

Required top-level keys:
- `input`
- `ranked_subreddits`
- `strategy_report`
- `pal_results`
- `sentiment_scores`
- `meta`

Required per subreddit item:
- `rank`
- `subreddit`
- `url` (can be synthesized by adapter fallback)
- `retrieval_score`
- `rerank_score`
- `reason`
- `evidence`
- `sentiment_score`

Required `meta` keys:
- `retrieval_top_k`
- `rerank_top_k`
- `latency_ms`

Rendering behavior:
- missing required key: show structured error card and stop results render
- `ranked_subreddits` empty: render empty state, keep report/other sections visible

## 6. Adapter Constraints (`app/helpers/adapter.py`)

Adapter responsibilities:
- validate raw payload type and required keys
- normalize subreddit name (strip leading `r/`, trim whitespace)
- enforce URL fallback rule
- coerce invalid numeric score fields to `None`
- return normalized payload safe for rendering

Adapter error policy:
- raise `ValueError` with explicit missing key name for contract violations
- do not silently drop required fields

## 7. UI/UX Constraints (`UIUX.md` Aligned)

### 7.1 CSS Injection Strategy
- one global CSS injection via `st.markdown(GLOBAL_CSS, unsafe_allow_html=True)` at top of `main()`
- custom component HTML rendered via `st.markdown(html, unsafe_allow_html=True)`

### 7.2 Color Token Policy
- define all color values in a single `COLORS` dict
- never hardcode hex values outside `COLORS`

### 7.3 Naming and Styling Policy
- all custom classes must use `cp-` prefix
- card surfaces use `cp-card`
- links open with `target="_blank"`

### 7.4 Layout Policy
- metrics row: `st.columns(4)`
- content row: `st.columns([1, 1])`
- keep sidebar simplified (Streamlit-native), no complex fake nav

## 8. Required Page Components

In `streamlit_app.py`, implement:
- `get_pipeline()` with `@st.cache_resource`
- `render_metrics(data)`
- `render_ranked_subreddits(subreddits)`
- `render_sentiment(sentiment_scores)`
- `render_strategy_report(report)`
- top-level `main()`

In `helpers/components.py`, implement pure HTML builders:
- `metric_card_html`
- `subreddit_row_html`
- `sentiment_bar_html`
- `error_card_html`

## 9. Runtime States (Must Be Visible and Stable)

Required states:
- Idle: input area only
- Loading: spinner around pipeline call
- Success: metrics + ranked list + sentiment + report
- Exception: error card, app still interactive
- Contract violation: error card with missing key detail
- Empty ranking: ranked card shows muted empty message
- Missing URL item: adapter auto-fills URL before render

## 10. Implementation Sequence

1. Create `app/helpers/adapter.py` and enforce strict contract + normalization.
2. Create `app/helpers/components.py` with pure HTML builders.
3. Implement `app/streamlit_app.py` orchestration, CSS tokens, rendering, and state flow.
4. Use mock pipeline for offline UI verification if backend contract is not ready.
5. Switch to real pipeline integration once callable interface is available.
6. Validate local run and docker deploy path.
7. Update `README.md` frontend runbook and hard URL requirement.

## 11. Testing Checklist

1. Empty submit blocked with warning.
2. Successful run renders all four sections.
3. Each subreddit row has clickable full Reddit URL.
4. Missing URL in payload becomes valid fallback URL.
5. Missing required key triggers explicit contract violation error.
6. Pipeline exception is handled without traceback shown to user.
7. Empty `ranked_subreddits` still shows report section.
8. Session state keeps last successful result across reruns.

## 12. Definition of Done (DoD)

All must pass:
- no `NotImplementedError` in frontend files owned by Person D
- `streamlit_app.py` fully runnable with mock or real pipeline
- every recommendation link is clickable and complete
- docs and implementation are consistent with `structure.md` and `UIUX.md`
- `docker-startup deploy` can bring up app service for demo

## 13. Integration Note (Current Repo Reality)

Current backend skeleton may expose `build_pipeline()` instead of a concrete `Pipeline` class.  
Frontend should keep a thin integration boundary in `get_pipeline()`:
- use whichever backend entrypoint is currently available
- preserve the same strict `run(...)` payload contract at adapter boundary

