# CreatorPal Frontend-Backend Interaction Guide (Streamlit x Pipeline)

Last Updated: 2026-04-12  
Owner: Frontend + Pipeline Integration  
Applies To:
- `app/streamlit_app.py`
- `app/helpers/adapter.py`
- `app/helpers/components.py`
- `src/pipeline.py` (`build_pipeline()` + `run()`)

## 1. Purpose and Scope

This document defines the production-facing integration contract between the Streamlit frontend and the pipeline backend.

Primary goals:
- Keep rendering stable even when backend implementation changes.
- Enforce a strict payload contract at the integration boundary.
- Ensure all failures are user-safe (no raw Python traceback in UI).

Layer responsibilities:
- Orchestration/UI state: `app/streamlit_app.py`
- Contract validation/normalization: `app/helpers/adapter.py`
- Pure HTML builders (no `st.*`): `app/helpers/components.py`
- Business execution and data generation: `pipeline.run(...)`

## 2. Runtime State Machine

```text
FRESH LOAD / NEW QUERY
        -> IDLE (last_result is None)
        -> SUBMIT
        -> LOADING (spinner + pipeline.run)
        -> adapt(raw) success
        -> st.session_state["last_result"] = data
        -> st.rerun()
        -> DASHBOARD
        -> NEW QUERY
        -> clear session + st.rerun()
        -> IDLE
```

Session keys used by frontend:
- `last_result`: last successful adapted payload
- `last_error`: last error message string
- `dark_mode`: UI theme state only (no backend semantics)

## 3. Backend Interface Contract

The backend must expose:

```python
pipeline.run(channel_or_query: str, user_query: str | None = None) -> dict[str, Any]
```

Frontend acquisition rule:
- Frontend calls `build_pipeline()`.
- Returned object must implement `.run(...)`.

## 4. Required Payload Schema

### 4.1 Top-level keys (all required)

| Key | Type | Required | Notes |
|---|---|---|---|
| `input` | object | yes | request metadata |
| `ranked_subreddits` | array | yes | ranked recommendation list |
| `strategy_report` | string/null | yes | null normalized to empty string |
| `pal_results` | object | yes | PAL summary + metrics |
| `sentiment_scores` | object | yes | subreddit -> score |
| `meta` | object | yes | retrieval/rerank/runtime metadata |

### 4.2 `input` object (all required)

| Key | Type | Constraint |
|---|---|---|
| `channel_or_query` | string | non-empty |
| `user_query` | string/null | optional user intent |
| `resolved_mode` | enum | `"channel"` or `"query"` |
| `timestamp_utc` | string | non-empty UTC timestamp string |

### 4.3 `ranked_subreddits[i]` fields

| Key | Type | Constraint |
|---|---|---|
| `rank` | int | integer only (bool rejected) |
| `subreddit` | string | `r/` prefix allowed; normalized in adapter |
| `retrieval_score` | number | invalid -> normalized to `None` |
| `rerank_score` | number | invalid -> normalized to `None` |
| `reason` | string | empty string allowed |
| `evidence` | list[string] | null -> `[]`; invalid type is a contract error |
| `sentiment_score` | number | invalid -> normalized to `None` |
| `url` | string | optional; adapter synthesizes fallback if missing |

Required URL fallback behavior:

```text
https://www.reddit.com/r/{normalized_subreddit}/
```

### 4.4 `pal_results` and `meta`

`pal_results` required keys:
- `summary` (string)
- `metrics` (object)

`meta` required integer keys:
- `retrieval_top_k`
- `rerank_top_k`
- `latency_ms`

## 5. Adapter Boundary Rules (`adapter.py`)

Adapter is the single contract gate before rendering.

Required behaviors:
- Raise `ValueError` when required keys are missing.
- Include precise key path in error message.
- Normalize subreddit names (`r/` stripping, slash trimming).
- Enforce Reddit URL fallback when URL is missing/invalid.
- Normalize sentiment keys to `r/{name}` format.
- Reject malformed data early; do not silently drop required fields.

## 6. Error Handling and Recovery

Current frontend flow:
- `pipeline.run(...)` exception -> store `last_error` -> rerun -> show error card.
- `adapt(raw)` contract error -> same flow.
- User can retry without page reload.

Engineering constraints:
- Backend error messages must be actionable and non-empty.
- Never include secrets, internal endpoints, or credential material in messages.
- UI must never expose raw traceback to end users.

## 7. Performance and Reliability Constraints

Minimum requirements:
- `meta.latency_ms` must be real end-to-end runtime in integer milliseconds.
- `run()` must always return a dict on success.
- Schema must remain stable for same contract version.

Suggested service targets:
- P50 latency < 3s
- P95 latency < 8s (demo environments may be looser)

Instance lifecycle:
- Frontend caches pipeline with `@st.cache_resource`.
- Backend pipeline object should be reusable and re-entrant.

## 8. Security and Data Hygiene

Mandatory:
- Escape all user/backend text before HTML injection (`components.py` already does this).
- Accept only valid `http/https` URLs or fallback to canonical Reddit URL.
- Do not return secrets in payload fields.

Recommended:
- Add domain allowlist checks for outbound links.
- Limit user input length to reduce injection and failure amplification risk.

## 9. Observability Requirements

Backend should emit:
- Sanitized input summary
- Stage-level timings (ingest/retrieval/rerank/generation)
- Candidate and final result counts
- Error category and code

Cross-layer tracing recommendation:
- Add `meta.request_id`
- Surface `request_id` in debug/error UI for triage

## 10. Versioning and Compatibility

Recommended metadata:
- `meta.contract_version` (for example `1.0.0`)

Compatibility rules:
- Adding new optional fields is allowed.
- Removing required fields is not allowed.
- Type changes on required fields require a version bump and coordinated rollout.
- Frontend release must include contract regression tests against real backend.

## 11. Test and Acceptance Checklist

Backend acceptance:
- All required top-level keys returned.
- Every `ranked_subreddits` item includes required keys.
- Missing URL still renders clickable link via fallback.
- `meta` values are integers.

Frontend acceptance:
- Empty input is blocked.
- Loading state is visible during execution.
- Success state renders all sections.
- Contract violations are displayed via structured error card.
- `last_result` persists across reruns.

## 12. Current Repository Reality

At time of writing, `src/pipeline.py` still contains `NotImplementedError`.  
Frontend currently falls back to `MockPipeline` when real pipeline construction fails.

Operational recommendation:
- Allow fallback in local development.
- Disable silent fallback in staging/production so real integration failures are visible.

---

Change management rule:
1. Update this guide first.
2. Update `adapter.py` contract logic.
3. Update `streamlit_app.py` rendering assumptions.
4. Attach contract test evidence in PR.
