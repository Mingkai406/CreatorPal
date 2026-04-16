# CreatorPal Frontend-Backend Interaction Guide (Code-Aligned)

Last Updated: 2026-04-12  
Applies To:
- `app/streamlit_app.py`
- `app/helpers/adapter.py`
- `app/helpers/components.py`
- `app/helpers/mock_pipeline.py`
- `src/pipeline.py`

## 1. Integration Objective

Provide a stable integration boundary so the Streamlit UI can render safely whether the backend is:
- fully implemented (`build_pipeline()` works), or
- unavailable/incomplete (frontend falls back to `MockPipeline`)

The strict boundary is `adapt(raw)` in `app/helpers/adapter.py`.

## 2. Runtime Flow

```text
IDLE (last_result is None)
  -> user submits form
  -> pipeline.run(...)
  -> adapt(raw)
  -> save last_result, clear last_error
  -> rerun
  -> DASHBOARD

Error in run/adapt
  -> save last_error
  -> rerun
  -> show error card
```

Session keys:
- `last_result`
- `last_error`
- `dark_mode` (UI-only; not part of backend payload)

## 3. Backend Bootstrap Contract

Frontend pipeline acquisition (`get_pipeline(force_mock=False)`):
1. if `force_mock` is true, return `MockPipeline`.
2. else call `build_pipeline()`.
3. if build fails or returned object has no `run`, return `MockPipeline`.
4. cache result with `@st.cache_resource`.

Environment switch:
- `CREATORPAL_USE_MOCK_PIPELINE=1|true|yes|on|y` forces mock mode.

## 4. Required `run()` Interface

Backend object must expose:

```python
run(channel_or_query: str, user_query: str | None = None) -> dict[str, Any]
```

## 5. Payload Contract Enforced by `adapt(raw)`

### 5.1 Top-Level Required Keys

- `input`
- `ranked_subreddits`
- `strategy_report`
- `pal_results`
- `sentiment_scores`
- `meta`

Missing required keys raise `ValueError`.

### 5.2 `input` Required Keys

- `channel_or_query` (non-empty string)
- `user_query` (string or `null`)
- `resolved_mode` (`"channel"` or `"query"`)
- `timestamp_utc` (non-empty string)

### 5.3 `ranked_subreddits[i]` Required Keys

- `rank` (integer, bool rejected)
- `subreddit`
- `retrieval_score`
- `rerank_score`
- `reason`
- `evidence`
- `sentiment_score`

Notes:
- `url` is optional in incoming payload.
- adapter synthesizes fallback URL when missing/invalid:
  - `https://www.reddit.com/r/{subreddit}/`

Normalization behavior:
- `subreddit`: strips leading `r/` and trims slashes.
- score fields: invalid numeric values normalize to `None`.
- `reason`: normalized to string.
- `evidence`: `null -> []`; non-sequence raises contract error.

### 5.4 `pal_results` Required Keys

- `summary` (string after normalization)
- `metrics` (dict)

### 5.5 `sentiment_scores`

- Must be a dict.
- Keys normalized to `r/<name>` format.
- Values must be numeric; non-numeric raises contract error.

### 5.6 `meta` Required Keys

- `retrieval_top_k` (int)
- `rerank_top_k` (int)
- `latency_ms` (int)

## 6. Frontend Consumption Rules

After adapter success, UI uses payload as follows:
- `ranked_subreddits`: top 10 rendered in recommended card.
- `sentiment_scores`: rendered as bars + average badge.
- `strategy_report`: parsed into headings/paragraphs by `_render_report_html`.
- `meta.latency_ms`: shown in metric card as seconds.

Display thresholds (implemented):
- Metric subtitle for avg sentiment: `>= 0.2` => "Positive community", else "Mixed community".
- Sentiment card badge: average `>= 0.5` => "Positive", else "Mixed".
- Sentiment bar color:
  - `>= 0.5` green
  - `>= 0.2` amber
  - `< 0.2` red

## 7. Error Handling Contract

Error sources handled uniformly:
- pipeline runtime exceptions
- adapter contract violations

Frontend behavior:
- store `str(exc)` in `last_error`
- rerun page
- render structured error card (`Pipeline error`) without traceback UI

## 8. Security and Safety Guarantees in Current Code

- HTML escaping is applied in `components.py` for user/backend text.
- URLs are validated in adapter (`http/https` with netloc) or replaced with fallback.
- Empty query is blocked before backend call.

## 9. Known Repository Status

`src/pipeline.py` is fully implemented end-to-end. All pipeline stages
(YouTube ingest, theme extraction, hybrid retrieval, HyDE, reranking,
PAL, sentiment, report generation) are wired and guarded with
`_try_init` / try-except so that unavailable components are skipped
gracefully rather than aborting the run.

`get_pipeline()` falls back to `MockPipeline` in two cases:
1. `CREATORPAL_USE_MOCK_PIPELINE=1|true|yes|on|y` is set in the environment.
2. `build_pipeline()` raises any exception (e.g. missing FAISS index, no
   vLLM endpoint) or returns an object without a `run` method.

## 10. Change Rules for Integration Work

When backend payload shape changes:
1. Update `adapter.py` first.
2. Update `streamlit_app.py` rendering assumptions second.
3. Update this guide in the same PR.
4. Validate both real and mock pipeline paths.
