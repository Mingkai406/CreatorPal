# Team Contributions

**Project:** CreatorPal — YouTube-to-Reddit Audience Intelligence  
**Repository:** [Mingkai406/CreatorPal](https://github.com/Mingkai406/CreatorPal)

Each section lists the modules that person owned, the specific files they committed, and the key technical decisions they made.

## Table of Contents

- [Runxin Shao — Retrieval Pipeline + Backend Integration](#runxin-shao)
- [Ziqi Yang — Frontend + Deployment + Project Documentation](#ziqi-yang)
- [Gaoyuan Shi — Data Pipeline](#gaoyuan-shi)
- [Mingkai Gao — Analytics + Evaluation + Project Initialization](#mingkai-gao)
- [Summary](#summary)

---

## Runxin Shao
**Role:** Retrieval Pipeline + Backend Integration

### Modules Owned
- `src/retrieval/` (all six modules)
- `src/ingest/youtube.py`
- `src/generator/augmented_gen.py`
- `src/config.py`
- `src/pipeline.py` (primary author)

### Implemented
| File | Description |
|---|---|
| `src/retrieval/faiss_search.py` | `FaissRetriever` — FAISS IndexFlatIP with L2-normalized cosine similarity |
| `src/retrieval/bm25_search.py` | `BM25Retriever` — Okapi BM25 over tokenized `chunk_text` |
| `src/retrieval/hybrid_search.py` | `HybridRetriever` — min-max normalization + weighted linear fusion (α=0.15/0.85) |
| `src/retrieval/query_rewriter.py` | `QueryRewriter` — LLM multi-query expansion with deduplication |
| `src/retrieval/reranker.py` | `CrossEncoderReranker` — cross-encoder reranking over top-50 candidates |
| `src/retrieval/hyde.py` | `HyDEQueryRewriter` — hypothetical document embedding for supplementary FAISS recall |
| `src/retrieval/theme_extractor.py` | `ThemeExtractor` — LLM extraction of creator themes from channel metadata |
| `src/ingest/youtube.py` | `YouTubeIngestor` — YouTube Data API v3 channel/video/comment ingestion |
| `src/generator/augmented_gen.py` | `AugmentedGenerator` — RAG-conditioned strategy report generation |
| `src/config.py` | `Settings` frozen dataclass — 14 env vars with typed defaults |
| `src/pipeline.py` | `CreatorPalPipeline` — 9-step end-to-end orchestration with graceful skip |
| `tests/test_retrieval_smoke.py` | Integration smoke tests for BM25, FAISS, and hybrid fusion |

### Key Technical Decisions
- Designed the `_try_init()` guard that allows the pipeline to run end-to-end even when optional components (YouTube, HyDE, sentiment, report generator) are unavailable.
- Chose 85/15 FAISS/BM25 weight split and min-max score normalization to enable cross-retriever fusion.
- Implemented HyDE as a supplementary append-only pass (not a replacement) so hybrid recall is never degraded.
- Fixed metadata loading to support both JSON array and NDJSON formats across BM25 and FAISS retrievers.

---

## Ziqi Yang
**Role:** Frontend + Deployment + Project Documentation

### Modules Owned
- `app/streamlit_app.py`
- `app/helpers/` (all four files)
- `Dockerfile`, `docker-startup`
- `doc/` (all documentation)
- `data/read_zst.py`

### Implemented
| File | Description |
|---|---|
| `app/streamlit_app.py` | Full Streamlit UI — idle hero, dashboard, light/dark CSS themes, entrance animations |
| `app/helpers/adapter.py` | Strict payload adapter — type validation, URL normalization, sentinel-safe coercion |
| `app/helpers/components.py` | Pure HTML component builders — metric cards, subreddit rows, sentiment bars |
| `app/helpers/mock_pipeline.py` | Deterministic contract-compliant mock for offline development and demo |
| `data/read_zst.py` | Streaming CLI reader for Reddit `.zst` JSONL dumps |
| `Dockerfile` | Application container image (python:3.11-slim) |
| `docker-startup` | Single-command deploy script (`./docker-startup deploy`) |
| `doc/backend/pipeline.md` | End-to-end pipeline orchestration reference |
| `doc/backend/retrieval.md` | Retrieval stack deep dive — fusion algorithm, HyDE, reranking, tuning guide |
| `doc/backend/corpus.md` | Offline corpus build reference |
| `doc/frontend/*.md` | All four frontend specification documents |
| `doc/collab/contributing.md`, `doc/collab/team.md`, `README.md` | Project-level documentation |

### Key Technical Decisions
- Implemented a strict adapter boundary (`adapt()`) between the backend and UI so that the frontend never renders unvalidated data and pipeline failures surface as structured error cards rather than crashes.
- Built a mock pipeline fallback so the UI is always demo-able regardless of backend availability.
- Applied CSS injection (`st.markdown(..., unsafe_allow_html=True)`) for full theme control without forking Streamlit internals.
- Designed the two-state page machine (IDLE hero → DASHBOARD) with `st.session_state` to provide clean navigation without page reloads.

---

## Gaoyuan Shi
**Role:** Data Pipeline

### Modules Owned
- `data/build_reddit_slim.py`
- `data/build_ground_truth.py`
- `data/build_faiss_index.py`
- `data/preprocess_corpus.py` (co-implemented with Runxin Shao)

### Implemented
| File | Description |
|---|---|
| `data/build_reddit_slim.py` | Streaming `.zst` → NDJSON reducer — keeps 7 fields, supports score filter and post limit |
| `data/build_ground_truth.py` | YouTube-to-subreddit pair extractor — regex URL detection, channel ID inference, CSV output |
| `data/build_faiss_index.py` | Profile chunker and encoder — 64-token sliding window, `all-mpnet-base-v2`, FAISS IndexFlatIP |
| `data/preprocess_corpus.py` | Subreddit profile aggregator — heapq top-50 posts by score, `min_posts` filter |

### Key Technical Decisions
- Used streaming `.zst` decompression throughout the data pipeline to avoid loading the full 15 GB dump into memory.
- Used `heapq.nlargest` for O(n log k) top-50 aggregation per subreddit instead of full sort.
- Applied 64-token / 16-token-overlap sliding windows to balance chunk granularity against FAISS index size.
- Implemented idempotent output checks so each build script can be safely re-run without duplicate work.

---

## Mingkai Gao
**Role:** Analytics + Evaluation + Project Initialization

### Modules Owned
- `src/pal/executor.py`
- `src/sentiment/analyzer.py`
- `eval/retrieval_eval.py`
- `eval/generation_eval.py`
- `tests/test_pal.py`, `tests/test_sentiment.py`, `tests/test_eval.py`
- Initial repository structure

### Implemented
| File | Description |
|---|---|
| `src/pal/executor.py` | `PALExecutor` — LLM code generation + RestrictedPython sandboxed execution |
| `src/sentiment/analyzer.py` | `SentimentAnalyzer` — RoBERTa classifier with signed score aggregation per subreddit |
| `eval/retrieval_eval.py` | Recall@K and MRR metrics over ground-truth YouTube–subreddit pairs |
| `eval/generation_eval.py` | Generation quality assessment framework (coherence, grounding, actionability) |
| `tests/test_pal.py` | PAL code generation and sandbox execution tests |
| `tests/test_sentiment.py` | Sentiment label-to-score mapping and aggregation tests |
| `tests/test_eval.py` | Retrieval evaluation metric tests |

### Key Technical Decisions
- Used `RestrictedPython.compile_restricted()` with a curated `safe_builtins` allowlist (pandas, numpy, and standard math functions) to prevent arbitrary code execution while preserving analytics expressiveness.
- Mapped RoBERTa output labels to a signed `[−1, +1]` scale so sentiment scores can be averaged and thresholded meaningfully.
- Initialized the repository and executed the structural migration from the original ReAct/Gemini architecture to the current RAG-centric pipeline, establishing the module boundaries that the rest of the team built on.

---

## Summary

| Member | Primary Area | Core Deliverable |
|---|---|---|
| Runxin Shao | Retrieval + Backend | `src/retrieval/`, `src/pipeline.py`, `src/config.py`, YouTube ingest, report generation |
| Ziqi Yang | Frontend + Docs | `app/`, `doc/`, `Dockerfile`, `data/read_zst.py` |
| Gaoyuan Shi | Data Pipeline | `data/build_*.py`, `data/preprocess_corpus.py` |
| Mingkai Gao | Analytics + Eval | `src/pal/`, `src/sentiment/`, `eval/`, `tests/`, project init |
