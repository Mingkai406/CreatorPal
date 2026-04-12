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
3. FAISS retrieval (top-50) + cross-encoder reranking (top-10)
4. PAL analytics + subreddit sentiment scoring
5. Final strategy report generation and Streamlit rendering

---

## Architecture

```
Input (YouTube URL / Query)
  -> YouTube Ingest
  -> Theme Extractor
  -> HyDE Rewriter
  -> FAISS Retriever (top-50)
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
│   ├── preprocess_corpus.py
│   ├── build_faiss_index.py
│   ├── build_ground_truth.py
│   ├── read_zst.py
│   └── read_zst_commands.md
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
│   ├── config.py
│   ├── pipeline.py
│   ├── ingest/
│   ├── retrieval/
│   ├── pal/
│   ├── sentiment/
│   └── generator/
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
- Person 2 (`preprocess_corpus.py`): build subreddit profiles (sidebar + rules + top-50 posts), filter subscriber count < 1000.
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

`.env`:

```env
YOUTUBE_API_KEY=your_youtube_api_key
VLLM_ENDPOINT=http://localhost:8000/v1
```

---

## Deployment

```bash
./docker-startup deploy
```

Services:

- `vllm`: Llama 3.1 8B OpenAI-compatible inference endpoint
- `app`: Streamlit frontend

---

## Current Implementation Status

The project is still in scaffold-to-implementation transition:

- Interfaces and module boundaries are defined.
- A large portion of core functions still use `NotImplementedError`.
- Team is implementing by module ownership and integrating through `src/pipeline.py`.

---

## Development Workflow

- Branches:
  - `feature/data-pipeline`
  - `feature/retrieval`
  - `feature/pal-sentiment`
  - `feature/frontend-deploy`
- Integration via PR to `main`.
- Final end-to-end assembly in `src/pipeline.py`.

---

## License

MIT. See [LICENSE](LICENSE).
