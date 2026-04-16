# CreatorPal Backend Pipeline

This document describes `src/pipeline.py` — the end-to-end orchestration layer that wires together every backend component. It is the authoritative reference for how inputs are transformed into the frontend payload.

---

## 1. Responsibilities

`CreatorPalPipeline.run()` is the single callable entry point that:

- accepts a YouTube channel URL or a freeform topic query
- invokes all backend components in a defined order
- assembles and returns a dict conforming to the frontend adapter contract (see `doc/frontend/frontend-backend-interaction-guide.md`)

The pipeline is instantiated once per process by `build_pipeline()` and cached by Streamlit's `@st.cache_resource`. It is **stateless across invocations**: all intermediate data lives in local variables inside `run()`. The same instance is reused for every user request.

---

## 2. Configuration

All tunable parameters are held in `src/config.py::Settings`, a frozen dataclass loaded from environment variables via `Settings.from_env()`.

| Field | Env Var | Default | Description |
|---|---|---|---|
| `youtube_api_key` | `YOUTUBE_API_KEY` | `""` | YouTube Data API v3 key |
| `vllm_endpoint` | `VLLM_ENDPOINT` | `http://localhost:8000/v1` | OpenAI-compatible LLM endpoint |
| `vllm_model` | `VLLM_MODEL` | `meta-llama/Llama-3.1-8B-Instruct` | LLM model identifier |
| `embedding_model` | `EMBEDDING_MODEL` | `sentence-transformers/all-mpnet-base-v2` | Bi-encoder for FAISS retrieval |
| `reranker_model` | `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder for reranking |
| `sentiment_model` | `SENTIMENT_MODEL` | `cardiffnlp/twitter-roberta-base-sentiment-latest` | RoBERTa sentiment classifier |
| `faiss_index_path` | `FAISS_INDEX_PATH` | `data/processed/subreddit_profiles.faiss` | FAISS index file |
| `faiss_metadata_path` | `FAISS_METADATA_PATH` | `data/processed/subreddit_profile_chunks.json` | Chunk metadata file |
| `retrieval_top_k` | `RETRIEVAL_TOP_K` | `50` | Candidates returned from hybrid retrieval |
| `rerank_top_k` | `RERANK_TOP_K` | `10` | Final candidates after reranking |
| `hybrid_alpha_keyword` | `HYBRID_ALPHA_KEYWORD` | `0.15` | BM25 weight in hybrid score fusion |
| `hybrid_alpha_semantic` | `HYBRID_ALPHA_SEMANTIC` | `0.85` | FAISS weight in hybrid score fusion |
| `max_channel_videos` | `MAX_CHANNEL_VIDEOS` | `20` | Videos fetched per YouTube channel |
| `max_video_comments` | `MAX_VIDEO_COMMENTS` | `100` | Comments fetched per video |

`Settings.from_env()` raises `EnvironmentError` for any required variable that is missing. Always call `load_settings()` rather than `Settings.from_env()` directly — `load_settings()` first loads `.env` via `python-dotenv`, then delegates to `from_env()`.

---

## 3. Component Initialization

### 3.1 Required Components

These components are constructed unconditionally in `__init__()`. A construction failure (e.g. missing FAISS index, unreachable vLLM endpoint) propagates as an exception and prevents the pipeline from starting.

| Component | Class | Hard dependency |
|---|---|---|
| LLM client | `openai.OpenAI` | `VLLM_ENDPOINT` must be reachable |
| FAISS retriever | `FaissRetriever` | `FAISS_INDEX_PATH`, `FAISS_METADATA_PATH` on disk |
| BM25 retriever | `BM25Retriever` | `FAISS_METADATA_PATH` (shares chunk metadata with FAISS) |
| Hybrid retriever | `HybridRetriever` | Both retrievers above |
| Query rewriter | `QueryRewriter` | LLM client |
| Cross-encoder reranker | `CrossEncoderReranker` | Model weights from HuggingFace Hub |
| PAL executor | `PALExecutor` | LLM client |

### 3.2 Optional Components and `_try_init()`

Optional components are wrapped with `_try_init(label, factory)`, which calls `factory()` and returns its result on success, or logs a warning and returns `None` on `NotImplementedError`. The `None` sentinel is checked before each use in `run()`.

```python
def _try_init(label: str, factory):
    try:
        return factory()
    except NotImplementedError:
        logger.warning("Skipping %s – not yet implemented", label)
        return None
```

Note that `_try_init` only suppresses `NotImplementedError`. Other failures (e.g. `ImportError`, network errors) propagate normally.

| Component | Class | Effect when `None` |
|---|---|---|
| YouTube ingestor | `YouTubeIngestor` | `channel_context` stays `{}`; themes and report have no channel data |
| Theme extractor | `ThemeExtractor` | `channel_themes` stays `[]`; retrieval query uses raw input only |
| HyDE retriever | `HyDEQueryRewriter` | No supplementary candidates; recall is slightly lower |
| Sentiment analyzer | `SentimentAnalyzer` | `sentiment_scores` stays `{}`; all sentiment fields default to `0.0` |
| Report generator | `AugmentedGenerator` | `strategy_report` is `""`; empty report card in the UI |

---

## 4. Execution Flow

`run(channel_or_query, user_query=None)` executes the stages below in sequence. `time.monotonic()` wraps the entire call; elapsed milliseconds are included in the returned `meta` dict.

---

### Step 1 — YouTube Ingest

```
Inputs  → channel_or_query: str
Outputs → channel_context: dict[str, Any]
```

Calls `YouTubeIngestor.ingest_channel(channel_or_query, max_videos, max_comments_per_video)`. On any exception, logs a warning and falls back to `channel_context = {}`.

`channel_context` is used downstream in Step 2 (theme extraction) and Step 8 (report generation). An empty dict means those steps have no channel-specific context to work with.

---

### Step 2 — Theme Extraction

```
Inputs  → channel_context: dict[str, Any]
Outputs → channel_themes: list[str]
```

Skipped when either `self.theme_extractor is None` or `channel_context` is empty. Calls `ThemeExtractor.extract_themes(channel_context)`, returning up to 20 short topic phrases (e.g. `"indie game development"`, `"pixel art tutorial"`).

`channel_themes` is used to condition both the retrieval query (Step 3) and the LLM-based components in Steps 4 and 4b.

---

### Step 3 — Retrieval Query Construction

```
Inputs  → user_query: str | None, channel_themes: list[str]
Outputs → retrieval_query: str
```

`prepare_retrieval_query()` composes the query string according to this logic:

1. Base: `user_query` if provided, otherwise `channel_or_query`.
2. Theme suffix: appends `"Topics: <t1>, <t2>, ..."` when `channel_themes` is non-empty.
3. Fallback: `"general content recommendation"` when both are empty.

---

### Step 4 — Query Rewriting + Hybrid Retrieval

```
Inputs  → retrieval_query: str, channel_themes: list[str]
Outputs → candidates: list[dict]
```

`QueryRewriter.retrieve_with_rewrites()` generates 3 LLM reformulations of `retrieval_query`, runs `HybridRetriever.retrieve(q, top_k=retrieval_top_k)` for each (plus the original), and deduplicates by `(subreddit, chunk_text[:80])`. Results are sorted by `hybrid_score` descending; the top `retrieval_top_k` entries are returned.

Each dict in `candidates` contains: `subreddit`, `chunk_text`, `hybrid_score`, `faiss_score`, `bm25_score`, plus all passthrough metadata columns from the index.

See `doc/backend/retrieval.md` for the detailed fusion algorithm.

---

### Step 4b — HyDE Supplementary Retrieval

```
Inputs  → retrieval_query, channel_themes, candidates (existing)
Outputs → candidates (extended in-place)
```

If `self.hyde is not None`, `HyDEQueryRewriter.retrieve()` generates a hypothetical subreddit profile document and runs FAISS retrieval on it. Results are merged into `candidates` using the same `(subreddit, chunk_text[:80])` deduplication key — only novel hits are appended; no existing candidate is replaced or modified.

Wrapped in a try-except so a HyDE LLM failure does not abort the run.

---

### Step 5 — Cross-Encoder Reranking

```
Inputs  → retrieval_query: str, candidates: list[dict]
Outputs → ranked_raw: list[dict]
```

`CrossEncoderReranker.rerank(retrieval_query, candidates, top_k=rerank_top_k)` scores every `(query, chunk_text)` pair through a late-interaction cross-encoder in a single batch, sorts descending by score, and returns the top `rerank_top_k` results.

Each entry in `ranked_raw` gains a `rerank_score` field. All upstream score fields (`hybrid_score`, `faiss_score`, `bm25_score`) are preserved.

---

### Step 6 — PAL Analytics

```
Inputs  → ranked_raw: list[dict]
Outputs → pal_results: {"summary": str, "metrics": dict}
```

The task prompt is fixed:

> *"Analyze the subreddit candidates and compute: (a) average rerank_score, (b) subreddit with max score, (c) number of unique subreddits."*

`ranked_raw` is converted to a `pandas.DataFrame`. `PALExecutor.generate_program(task, context)` asks the LLM to write Python code that assigns its answer to `result`. `PALExecutor.execute_program(code, dataframe=pal_df)` runs that code in a RestrictedPython sandbox.

On failure, `pal_results` is set to `{"summary": "PAL error: <msg>", "metrics": {}}` and execution continues.

---

### Step 7 — Sentiment Analysis

```
Inputs  → ranked_raw: list[dict]
Outputs → sentiment_scores: dict[str, float]
```

`chunk_text` entries from `ranked_raw` are grouped by `subreddit` into `sub_comments: dict[str, list[str]]`. `SentimentAnalyzer.score_subreddits()` runs the RoBERTa classifier over each group and returns one average score per subreddit.

**Design note:** sentiment is computed over retrieved Reddit post chunks, not YouTube comments. YouTube comments inform theme extraction (Step 2); community tone is inferred exclusively from the subreddit's own content. This is documented in a source comment at `src/pipeline.py:227`.

Scores are in `[−1.0, +1.0]`: positive confidence maps to `+confidence`, neutral to `0.0`, negative to `−confidence`.

---

### Step 8 — Report Generation

```
Inputs  → channel_context, ranked_raw, pal_results, sentiment_scores
Outputs → report: str
```

`AugmentedGenerator.generate_strategy_report()` builds a prompt from the top-5 subreddits (by `rerank_score`), up to 5 sentiment scores, and the PAL summary. The LLM is called with `temperature=0.5`, `max_tokens=512`. The expected output structure uses `##` headings: Overview, Top Communities, Engagement Strategy, Sentiment Insights.

On failure, `report` defaults to `""`.

---

### Output Assembly

The `run()` method assembles the final dict after all stages complete:

```python
{
    "input": {
        "channel_or_query": str,
        "user_query":        str | None,
        "resolved_mode":     "channel" | "query",   # heuristic: youtube.com or @ in input
        "timestamp_utc":     str,                    # ISO-8601
    },
    "ranked_subreddits": [                           # len == rerank_top_k
        {
            "rank":             int,                 # 1-based
            "subreddit":        str,                 # no r/ prefix
            "url":              str,                 # https://www.reddit.com/r/{subreddit}/
            "retrieval_score":  float,               # hybrid_score (falls back to "score")
            "rerank_score":     float,
            "reason":           str,                 # chunk_text[:120]
            "evidence":         list[str],           # [chunk_text[:200]]
            "sentiment_score":  float,               # from sentiment_scores; 0.0 if absent
        },
        ...
    ],
    "strategy_report":  str,
    "pal_results":      {"summary": str, "metrics": dict},
    "sentiment_scores": {"r/<subreddit>": float, ...},
    "meta": {
        "retrieval_top_k":  int,
        "rerank_top_k":     int,
        "latency_ms":       int,
    },
}
```

This payload is passed to `adapt()` in `app/helpers/adapter.py` before any rendering. `adapt()` performs strict type validation and normalization; see the interaction guide for full contract details.

---

## 5. Graceful Degradation

The pipeline always produces a structurally valid payload, even when most optional components are unavailable. The table below summarizes the effective output in each degraded scenario.

| Unavailable component | Affected field | Runtime behavior |
|---|---|---|
| YouTube ingestor | `channel_context = {}` | Themes empty; report has no channel context |
| Theme extractor | `channel_themes = []` | Retrieval query is the raw user input |
| HyDE retriever | No extra candidates | Slightly lower recall; reranker still runs on hybrid results |
| Sentiment analyzer | `sentiment_scores = {}` | All `sentiment_score` fields set to `0.0` |
| Report generator | `strategy_report = ""` | Empty report card rendered in UI |

**Hard failure points** — if any of these are broken, `build_pipeline()` itself raises and the UI falls back to `MockPipeline`:

- FAISS index missing or corrupt
- Chunk metadata missing or column-mismatched
- vLLM endpoint unreachable at startup

---

## 6. Adding a New Pipeline Stage

1. Implement the component class in the appropriate `src/<module>/` directory with a clear public interface.
2. Instantiate it in `CreatorPalPipeline.__init__()`. Use `_try_init()` if the component is optional.
3. Insert the call at the correct position in `run()`. Store output in a local variable; append a label to `stages` on success.
4. If the output contributes a new top-level key to the return payload, update `app/helpers/adapter.py` to validate and normalize it, and update `doc/frontend/frontend-backend-interaction-guide.md` in the same PR.
