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
- [Frontend Documentation Reference](#frontend-documentation-reference)
- [Latest Execution Plan (2026-04-10)](#latest-execution-plan-2026-04-10)
- [Team Ownership](#team-ownership)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Current Implementation Status](#current-implementation-status)
- [Development Workflow](#development-workflow)
- [License](#license)

---

## Overview

CreatorPal solves one practical question for creators: **Which Reddit communities should I target, and what engagement strategy should I use?**

Core workflow:

1. YouTube channel ingest (metadata, videos, comments)
2. LLM theme extraction + HyDE query rewriting
3. **Query rewriting** – LLM generates diverse reformulations for broader recall
4. **Hybrid retrieval** (top-50) – BM25 keyword search (15%) + FAISS dense similarity (85%)
5. Cross-encoder reranking (top-10)
6. PAL analytics + subreddit sentiment scoring
7. Final strategy report generation and Streamlit rendering

---

## Architecture

```
Input (YouTube URL / Query)
  -> YouTube Ingest
  -> Theme Extractor
  -> Query Rewriter (multi-query expansion)
  -> Hybrid Retriever (BM25 α=0.15 + FAISS α=0.85, top-50)
       ↳ HyDE Retriever (supplementary; merges FAISS hits from a
         hypothetical subreddit document, deduplicates into candidates)
  -> CrossEncoder Reranker (top-10)
  -> PAL + Sentiment
  -> Augmented Generator
  -> Streamlit UI (ranked subreddit links + report)
```

---

## Repository Structure

```text
creatorpal/
├── app/
│   ├── streamlit_app.py
│   └── helpers/
│       ├── __init__.py
│       ├── adapter.py
│       ├── components.py
│       └── mock_pipeline.py
├── data/
│   ├── download_reddit.py
│   ├── build_reddit_slim.py        # .zst → slim NDJSON
│   ├── preprocess_corpus.py        # slim NDJSON → subreddit_profiles.json
│   ├── build_faiss_index.py        # profiles → FAISS index + metadata
│   ├── build_ground_truth.py       # extract YouTube–subreddit pairs
│   ├── read_zst.py
│   ├── read_zst_commands.md
│   └── run_pipeline.sh             # one-click data pipeline script
├── eval/
│   ├── retrieval_eval.py
│   └── generation_eval.py
├── doc/
│   └── streamlit/
│       ├── structure.md
│       ├── UIUX.md
│       ├── frontend-design.md
│       └── frontend-backend-interaction-guide.md
├── src/
│   ├── config.py                   # Settings.from_env() + load_settings()
│   ├── pipeline.py                 # CreatorPalPipeline end-to-end orchestration
│   ├── ingest/
│   │   └── youtube.py
│   ├── retrieval/
│   │   ├── faiss_search.py         # FAISS dense retriever
│   │   ├── bm25_search.py          # BM25 keyword retriever
│   │   ├── hybrid_search.py        # weighted BM25 + FAISS fusion
│   │   ├── query_rewriter.py       # LLM multi-query expansion
│   │   ├── reranker.py             # cross-encoder reranker
│   │   ├── hyde.py                 # HyDE supplementary retriever
│   │   └── theme_extractor.py      # channel theme extraction
│   ├── pal/
│   │   └── executor.py             # RestrictedPython PAL sandbox
│   ├── sentiment/
│   │   └── analyzer.py             # RoBERTa sentiment scoring
│   └── generator/
│       └── augmented_gen.py        # LLM report generation
├── tests/
│   └── test_retrieval_smoke.py
├── Dockerfile
├── docker-compose.yml
├── docker-startup
├── project-plan.md
└── requirements.txt
```

---

## Frontend Documentation Reference

For Streamlit frontend implementation and integration details, use the docs under `doc/streamlit/`:

- [Frontend Structure](doc/streamlit/structure.md): code boundaries, module responsibilities, and runtime flow.
- [UI/UX Specification](doc/streamlit/UIUX.md): visual system, states, theme behavior, and animation rules.
- [Frontend Engineering Guide](doc/streamlit/frontend-design.md): implementation constraints and regression checklist.
- [Frontend-Backend Interaction Guide](doc/streamlit/frontend-backend-interaction-guide.md): payload contract, adapter rules, and error handling.

Use these docs as the reference baseline when modifying `app/streamlit_app.py` or `app/helpers/*`.

---

## Latest Execution Plan (2026-04-10)

### Step 1: Rebuild repository skeleton

- Replace previous ReAct/Gemini structure with the new RAG architecture.
- Team syncs to latest `main` and verifies skeleton signatures.

### Step 2: Data pipeline execution (parallel)

- Dataset source:
  - File: `RS_2019-04.zst`
  - URL: https://zenodo.org/records/3608135
- Person 1 (`download_reddit.py`): download Pushshift dataset (15.53GB) to GCP.
- Current local strategy: first run with a small sample (first 1000 lines) for fast validation.
- Person 2 (`preprocess_corpus.py`): build subreddit profiles (top-50 posts per subreddit by score), filter subreddits with fewer than 10 posts (`min_posts=10`).
- Person 3 (`build_faiss_index.py`): 64-token window / 16-token overlap chunking, encode with `all-mpnet-base-v2`, build FAISS Flat index.
- Person 4 (`build_ground_truth.py`): extract `(YouTube channel, subreddit)` from posts containing `youtube.com` or `youtu.be`, filter `score >= 2`.

### Latest local data strategy

1. Build `reddit_slim.ndjson` locally by streaming `RS_2019-04.zst` and keeping only selected fields.
2. Run preprocessing and ground-truth generation from `reddit_slim.ndjson` in parallel.
3. Store outputs in `data/processed/`:
   - `data/processed/reddit_slim.ndjson`
   - `data/processed/subreddit_profiles.json`
   - `data/processed/ground_truth_pairs.csv`

If `reddit_slim.ndjson` is too large for GitHub (>100MB), use Git LFS or store it on GCP/Google Drive and commit only derived outputs.

### Step 3: Validation targets

- FAISS index generated (target scale: about 1M vectors)
- `subreddit_profiles.json` generated
- `ground_truth_pairs.csv` generated

---

## Team Ownership

| Owner | Scope | Responsibilities | Deliverable |
|---|---|---|---|
| Person A (Gaoyuan) | `data/`, `src/config.py`, `src/pipeline.py` | Data pipeline maintenance, config centralization, end-to-end integration | Full call chain from input to final report |
| Person B (Runxin) | `src/ingest/`, `src/retrieval/` | YouTube ingest, theme extraction, HyDE, FAISS retrieval, reranking | Top-10 subreddit ranking with metadata |
| Person C (Mingkai) | `src/pal/`, `src/sentiment/`, `eval/` | PAL executor, sentiment scoring, retrieval and generation evaluation | Independent PAL/Sentiment runs + metric scripts |
| Person D (Ziqi) | `app/`, Docker files, docs | Streamlit UI, deploy scripts, env template, README maintenance | Demo-ready UI with clickable Reddit links |

Karl's demo requirement is mandatory: every recommended subreddit in UI/report must include a clickable full Reddit URL.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- YouTube Data API key
- vLLM OpenAI-compatible endpoint

### Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your keys and paths — see [`.env.example`](.env.example) for the full list of supported variables (API keys, model names, FAISS paths, retrieval weights, etc.).

---

## Deployment

```bash
./docker-startup deploy
```

Services:

- `vllm`: Llama 3.1 8B OpenAI-compatible inference endpoint
- `app`: Streamlit frontend

---

## Retrieval Pipeline Details

### Hybrid Search

The retrieval stage fuses two complementary signals:

| Component | Weight (α) | Description |
|---|---|---|
| BM25 (keyword) | 0.15 | Okapi BM25 over tokenized `chunk_text` — captures exact keyword matches |
| FAISS (semantic) | 0.85 | Cosine similarity via `all-mpnet-base-v2` embeddings — captures meaning |

Scores from each source are min-max normalised before the weighted linear combination. The fused ranking is then passed to the cross-encoder reranker for precision refinement.

### Query Rewriting

Before retrieval, the user query is expanded into multiple diverse reformulations via an LLM. All reformulated queries are run through the hybrid retriever; results are deduplicated and merged by score. This improves recall by surfacing documents that a single query phrasing might miss.

Modules:

- `src/retrieval/bm25_search.py` – BM25 keyword retriever (`rank-bm25`)
- `src/retrieval/hybrid_search.py` – weighted fusion of BM25 + FAISS
- `src/retrieval/query_rewriter.py` – LLM multi-query expansion

---

## Current Implementation Status

| Module | Status | Notes |
|---|---|---|
| `data/build_reddit_slim.py` | Done | Stream `.zst` → slim NDJSON |
| `data/preprocess_corpus.py` | Done | Aggregate top-50 posts per subreddit, filter `min_posts=10` |
| `data/build_faiss_index.py` | Done | 64-token chunking + `all-mpnet-base-v2` encoding |
| `data/build_ground_truth.py` | Done | YouTube–subreddit pair extraction |
| `data/run_pipeline.sh` | Done | One-click script for full data flow |
| `src/config.py` | Done | `Settings.from_env()` + `load_settings()` |
| `src/pipeline.py` | Done | End-to-end orchestration with graceful skip |
| `src/retrieval/faiss_search.py` | Done | FAISS IndexFlatIP cosine retrieval |
| `src/retrieval/bm25_search.py` | Done | BM25 keyword retrieval |
| `src/retrieval/hybrid_search.py` | Done | Weighted BM25 + FAISS fusion |
| `src/retrieval/query_rewriter.py` | Done | LLM multi-query expansion |
| `src/retrieval/reranker.py` | Done | Cross-encoder reranking |
| `src/pal/executor.py` | Done | RestrictedPython PAL sandbox |
| `src/sentiment/analyzer.py` | Done | RoBERTa sentiment scoring |
| `src/ingest/youtube.py` | Done | YouTube Data API v3 ingestion (requires `YOUTUBE_API_KEY`) |
| `src/retrieval/hyde.py` | Done | Supplementary HyDE retrieval; merges into candidates after hybrid search |
| `src/retrieval/theme_extractor.py` | Done | LLM-based channel theme extraction |
| `src/generator/augmented_gen.py` | Done | LLM strategy report generation |

---

## Development Workflow

- Branches:
  - `feature/data-pipeline` — data download, slim build, ground truth
  - `feature/data-pipeline-config` — preprocess, config, pipeline orchestration
  - `feature/retrieval` — hybrid search, BM25, query rewriting, reranking
  - `feature/pal-sentiment` — PAL executor, sentiment analyzer, evaluation
  - `feature/frontend-deploy` — Streamlit UI, Docker, deployment
- Integration via PR to `main`.
- Final end-to-end assembly in `src/pipeline.py`.

---

## License

MIT. See [LICENSE](LICENSE).
