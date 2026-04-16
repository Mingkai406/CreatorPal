# CreatorPal: YouTube-to-Reddit Audience Intelligence

> A RAG-centric system that matches YouTube creators with high-fit Reddit communities and generates actionable audience strategy reports.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit)](https://streamlit.io/)
[![FAISS](https://img.shields.io/badge/FAISS-Vector%20Search-0467DF)](https://github.com/facebookresearch/faiss)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Data Pipeline](#data-pipeline)
- [Deployment](#deployment)
- [Testing](#testing)
- [Retrieval Pipeline Details](#retrieval-pipeline-details)
- [Documentation](#documentation)
- [Implementation Status](#implementation-status)
- [License](#license)

---

## Overview

CreatorPal answers one practical question for creators: **Which Reddit communities should I target, and what engagement strategy should I use?**

Core workflow:

1. YouTube channel ingest (metadata, videos, comments)
2. LLM theme extraction
3. **Query rewriting** – LLM generates diverse reformulations for broader recall
4. **Hybrid retrieval** (top-50) – BM25 keyword search (15%) + FAISS dense similarity (85%)
5. **HyDE** – supplementary retrieval from a hypothetical subreddit document; merged into candidates
6. Cross-encoder reranking (top-10)
7. PAL analytics + subreddit sentiment scoring
8. Strategy report generation and Streamlit rendering

---

## Architecture

```
Input (YouTube URL or topic query)
  → YouTube Ingest
  → Theme Extractor
  → Query Rewriter (multi-query expansion)
  → Hybrid Retriever (BM25 α=0.15 + FAISS α=0.85, top-50)
       ↳ HyDE Retriever (supplementary; merges FAISS hits from a
         hypothetical subreddit document, deduplicates into candidates)
  → CrossEncoder Reranker (top-10)
  → PAL Analytics + Sentiment Analyzer
  → Augmented Generator (strategy report)
  → Streamlit UI (ranked subreddit links + strategy report)
```

---

## Repository Structure

```text
creatorpal/
├── app/
│   ├── streamlit_app.py
│   └── helpers/
│       ├── __init__.py
│       ├── adapter.py              # payload validation + normalization
│       ├── components.py           # pure HTML component builders
│       └── mock_pipeline.py        # deterministic fallback for local/demo
├── data/
│   ├── download_reddit.py          # Pushshift dataset download helper
│   ├── build_reddit_slim.py        # .zst → slim NDJSON
│   ├── preprocess_corpus.py        # slim NDJSON → subreddit_profiles.json
│   ├── build_faiss_index.py        # profiles → FAISS index + metadata
│   ├── build_ground_truth.py       # YouTube–subreddit pair extraction
│   ├── read_zst.py                 # CLI inspection tool for .zst files
│   ├── read_zst_commands.md        # usage examples for read_zst.py
│   └── run_pipeline.sh             # one-click idempotent data pipeline
├── doc/
│   ├── backend/
│   │   ├── pipeline.md             # runtime inference pipeline reference
│   │   ├── retrieval.md            # retrieval stack deep dive
│   │   └── corpus.md               # offline corpus and FAISS index build
│   └── frontend/
│       ├── structure.md
│       ├── UIUX.md
│       ├── frontend-design.md
│       └── frontend-backend-interaction-guide.md
├── eval/
│   ├── retrieval_eval.py           # Recall@K, MRR metrics
│   ├── generation_eval.py          # generation quality assessment
│   └── run_retrieval_eval.py       # evaluation runner
├── src/
│   ├── config.py                   # Settings.from_env() + load_settings()
│   ├── pipeline.py                 # CreatorPalPipeline end-to-end orchestration
│   ├── ingest/
│   │   └── youtube.py
│   ├── retrieval/
│   │   ├── faiss_search.py
│   │   ├── bm25_search.py
│   │   ├── hybrid_search.py
│   │   ├── query_rewriter.py
│   │   ├── reranker.py
│   │   ├── hyde.py
│   │   └── theme_extractor.py
│   ├── pal/
│   │   └── executor.py
│   ├── sentiment/
│   │   └── analyzer.py
│   └── generator/
│       └── augmented_gen.py
├── tests/
│   ├── test_retrieval_smoke.py
│   ├── test_pal.py
│   ├── test_eval.py
│   └── test_sentiment.py
├── .env.example
├── CONTRIBUTING.md
├── Dockerfile
├── docker-compose.yml
├── docker-startup
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker + Docker Compose (for full deployment)
- YouTube Data API key
- vLLM OpenAI-compatible endpoint (for LLM-backed features)

### Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys and model/path settings
```

See [`.env.example`](.env.example) for the full list of supported variables.

### Run locally with mock pipeline (no backend required)

```bash
export CREATORPAL_USE_MOCK_PIPELINE=1
streamlit run app/streamlit_app.py --server.port 8501
```

### Run locally with real pipeline

Requires a populated FAISS index and a running vLLM endpoint. See [Data Pipeline](#data-pipeline) and [Deployment](#deployment).

```bash
streamlit run app/streamlit_app.py --server.port 8501
```

---

## Data Pipeline

Build the FAISS index from a Reddit Pushshift dump before running the real pipeline.

```bash
# Full pipeline (requires data/RS_2019-04.zst)
bash data/run_pipeline.sh

# Quick local validation (first 10 000 posts only)
LIMIT_POSTS=10000 bash data/run_pipeline.sh
```

`run_pipeline.sh` executes four stages and skips any stage whose output already exists:

| Stage | Script | Output |
|---|---|---|
| 1. Slim | `build_reddit_slim.py` | `data/processed/reddit_slim.ndjson` |
| 2. Profiles | `preprocess_corpus.py` | `data/processed/subreddit_profiles.json` |
| 3. Ground truth | `build_ground_truth.py` | `data/processed/ground_truth_pairs.csv` |
| 4. FAISS index | `build_faiss_index.py` | `data/processed/subreddit_profiles.faiss` + `.json` |

For the full pipeline reference, individual script options, and GCP/large-scale setup, see [`doc/backend/corpus.md`](doc/backend/corpus.md).

---

## Deployment

```bash
./docker-startup deploy
```

Services started by Docker Compose:

| Service | Description | Port |
|---|---|---|
| `vllm` | Llama 3.1 8B OpenAI-compatible inference endpoint (requires GPU) | 8000 |
| `app` | Streamlit frontend | 8501 |

The `app` service reads `.env` and overrides `VLLM_ENDPOINT` to point at the `vllm` container. Set `HF_TOKEN` in your environment for model download from Hugging Face Hub.

---

## Testing

```bash
python tests/test_retrieval_smoke.py   # BM25 + FAISS + hybrid fusion
python tests/test_pal.py               # PAL code generation + sandbox
python tests/test_sentiment.py         # RoBERTa sentiment scoring
python tests/test_eval.py              # retrieval evaluation metrics
```

Tests run as standalone scripts. Tests that require a live FAISS index or vLLM endpoint are automatically skipped when those services are unavailable.

---

## Retrieval Pipeline Details

### Hybrid Search

The retrieval stage fuses two complementary signals:

| Component | Weight (α) | Description |
|---|---|---|
| BM25 (keyword) | 0.15 | Okapi BM25 over tokenized `chunk_text` — captures exact keyword matches |
| FAISS (semantic) | 0.85 | Cosine similarity via `all-mpnet-base-v2` embeddings — captures meaning |

Scores from each source are min-max normalized before the weighted linear combination. The fused ranking is then passed to the cross-encoder reranker for precision refinement.

### Query Rewriting

The user query is expanded into multiple diverse reformulations via an LLM. All reformulations are run through the hybrid retriever; results are deduplicated and merged by score. This improves recall by surfacing documents that a single query phrasing might miss.

### HyDE (Hypothetical Document Embedding)

A hypothetical subreddit profile document is synthesized by an LLM and encoded to retrieve additional FAISS candidates. These are deduplicated and merged into the hybrid retrieval pool before reranking.

---

## Documentation

| Document | Description |
|---|---|
| [`doc/backend/pipeline.md`](doc/backend/pipeline.md) | Backend pipeline: component init, 9-step execution flow, graceful degradation, return payload |
| [`doc/backend/retrieval.md`](doc/backend/retrieval.md) | Retrieval stack: BM25, FAISS, hybrid fusion, query rewriting, HyDE, reranking, tuning guide |
| [`doc/backend/corpus.md`](doc/backend/corpus.md) | Offline corpus build: dataset download, build stages, per-script options, GCP setup |
| [`doc/frontend/structure.md`](doc/frontend/structure.md) | Frontend code boundaries and runtime lifecycle |
| [`doc/frontend/UIUX.md`](doc/frontend/UIUX.md) | Visual system, UI states, theme tokens, animations |
| [`doc/frontend/frontend-design.md`](doc/frontend/frontend-design.md) | Implementation constraints and regression checklist |
| [`doc/frontend/frontend-backend-interaction-guide.md`](doc/frontend/frontend-backend-interaction-guide.md) | Payload contract, adapter rules, error handling |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Development workflow, branch strategy, PR process |

---

## Implementation Status

| Module | Status | Notes |
|---|---|---|
| `data/build_reddit_slim.py` | Done | Stream `.zst` → slim NDJSON |
| `data/preprocess_corpus.py` | Done | Aggregate top-50 posts per subreddit, filter `min_posts=10` |
| `data/build_faiss_index.py` | Done | 64-token chunking + `all-mpnet-base-v2` encoding |
| `data/build_ground_truth.py` | Done | YouTube–subreddit pair extraction |
| `data/run_pipeline.sh` | Done | One-click idempotent data pipeline |
| `src/config.py` | Done | `Settings.from_env()` + `load_settings()`, 14 env vars |
| `src/pipeline.py` | Done | End-to-end orchestration with graceful skip |
| `src/retrieval/faiss_search.py` | Done | FAISS IndexFlatIP cosine retrieval |
| `src/retrieval/bm25_search.py` | Done | BM25 keyword retrieval |
| `src/retrieval/hybrid_search.py` | Done | Weighted BM25 + FAISS fusion |
| `src/retrieval/query_rewriter.py` | Done | LLM multi-query expansion |
| `src/retrieval/reranker.py` | Done | Cross-encoder reranking |
| `src/retrieval/hyde.py` | Done | Supplementary HyDE retrieval |
| `src/retrieval/theme_extractor.py` | Done | LLM-based channel theme extraction |
| `src/pal/executor.py` | Done | RestrictedPython PAL sandbox |
| `src/sentiment/analyzer.py` | Done | RoBERTa sentiment scoring |
| `src/ingest/youtube.py` | Done | YouTube Data API v3 ingestion (requires `YOUTUBE_API_KEY`) |
| `src/generator/augmented_gen.py` | Done | LLM strategy report generation |

---

## License

MIT. See [LICENSE](LICENSE).
