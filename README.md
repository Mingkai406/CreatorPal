# CreatorPal: Audience Research Agent

> Audience research with Google ADK, on-demand Agent Skills, community retrieval, programmatic analytics and evidence-linked reports.

[![Agent CI](https://github.com/Mingkai406/CreatorPal/actions/workflows/agent-ci.yml/badge.svg?branch=main)](https://github.com/Mingkai406/CreatorPal/actions/workflows/agent-ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit)](https://streamlit.io/)
[![FAISS](https://img.shields.io/badge/FAISS-Vector%20Search-0467DF)](https://github.com/facebookresearch/faiss)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Research workflow

CreatorPal selects relevant skills and tools, retrieves community evidence, runs restricted Python analytics, and validates report citations before committing a result. The `creatorpal-agent` CLI provides three model and skill-loading policies, persistent task state, and a reproducible evaluation runner.

**[Agent quickstart, architecture and evaluation boundaries](doc/agent/README.md)** · **[Testing guide: offline, live models and acceptance criteria](doc/agent/testing.md)** · **[Example task](examples/agent/task.json)** · **[Agent tests](tests_agent/)**

Run an offline demo using `uv sync --locked --extra adk --extra dev`, then `uv run creatorpal-agent run --adapter offline-adk --task examples/agent/task.json --output runs`. The demo uses a deterministic model double and synthetic data. Configure a supported model and evidence corpus to run live research tasks; see the testing guide for model setup and evaluation criteria.

## Table of Contents

- [Research workflow](#research-workflow)
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

CreatorPal helps creators investigate relevant Reddit communities using retrieved profiles, analytics and source-linked recommendations. The agent CLI accepts a research task, chooses tools and Skills, and persists a validated report. The Streamlit interface provides a YouTube-to-Reddit strategy workflow. Latency and recommendation quality depend on the configured models and corpus; see the [testing guide](doc/agent/testing.md) for how to measure them and the [Product Overview](doc/product/overview.md) for the user workflow.

The YouTube-to-Reddit workflow uses `src/pipeline_vllm.py`:

1. YouTube channel ingest (metadata, videos, comments)
2. LLM theme extraction
3. **[Query rewriting](doc/algorithm/query-expansion.md)** – LLM generates diverse reformulations for broader recall
4. **[Hybrid retrieval](doc/algorithm/retrieval.md)** (top-50) – [Okapi BM25](doc/algorithm/retrieval.md) keyword search (5% default) + [FAISS dense similarity](doc/algorithm/retrieval.md) (95% default)
5. **[HyDE](doc/algorithm/query-expansion.md)** – supplementary retrieval from a hypothetical subreddit document; merged into candidates
6. [Cross-encoder reranking](doc/algorithm/analytics.md) (top-10)
7. Pipeline analytics + [subreddit sentiment scoring](doc/algorithm/analytics.md); the agent exposes generated Python analysis as a separate tool
8. Strategy report generation and [Streamlit rendering](doc/frontend/structure.md)

---

## Architecture

The agent coordinates research through explicit tools and persistent task state. See the [agent design](doc/agent/README.md#architecture) for tool contracts, model policies and execution boundaries.

```text
Research task
  → Task-based model policy
  → ADK tool loop + on-demand Agent Skills
       → Community search and rules lookup
       → Restricted Python analytics
       → Evidence and analysis state
  → Citation validation
  → Atomic report and receipt commit
  → Evaluation results + OpenTelemetry traces
```

The Streamlit interface uses the YouTube retrieval workflow described above.

See the [pipeline orchestration reference](doc/backend/pipeline.md) for component initialization order, graceful-skip behavior, and the full return payload schema.

---

## Repository Structure

```text
creatorpal/
├── creatorpal_agent/               # ADK loop, Skills, tools, state and evaluation
├── tests_agent/                    # agent and execution-boundary tests
├── examples/agent/                 # tasks and labeled offline results
├── pyproject.toml                  # lightweight agent package and optional extras
├── uv.lock                         # reproducible dependencies
├── Dockerfile.analytics            # isolated restricted analytics worker
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
│   ├── product/
│   │   └── overview.md             # product narrative, user journey, and vision
│   ├── collab/
│   │   └── contributing.md         # development workflow and PR process
│   ├── backend/
│   │   ├── pipeline.md             # runtime inference pipeline reference
│   │   ├── retrieval.md            # retrieval stack deep dive
│   │   └── corpus.md               # offline corpus and FAISS index build
│   ├── frontend/
│   │   ├── structure.md
│   │   ├── UIUX.md
│   │   ├── frontend-design.md
│   │   └── frontend-backend-interaction-guide.md
│   └── algorithm/
│       ├── retrieval.md            # BM25, FAISS, chunking, hybrid fusion
│       ├── query-expansion.md      # multi-query expansion and HyDE
│       └── analytics.md            # cross-encoder reranking, sentiment, PAL
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

See [`.env.example`](.env.example) for the full list of supported variables. The [pipeline configuration reference](doc/backend/pipeline.md) documents each of the 14 environment variables with their types and defaults.

### Run locally with mock pipeline (no backend required)

```bash
export CREATORPAL_USE_MOCK_PIPELINE=1
streamlit run app/streamlit_app.py --server.port 8501
```

### Run locally with real pipeline

Requires a populated [FAISS index](doc/backend/corpus.md) and a running vLLM endpoint. See [Data Pipeline](#data-pipeline) and [Deployment](#deployment).

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

```sh
uv sync --locked --extra adk --extra dev
uv run pytest -q tests_agent
uv run creatorpal-agent compare --adapter offline-adk --output runs/offline
```

Expected offline control: 39 tests pass, with the Docker test run separately in CI, and 12/12 task-policy runs complete. These are implementation checks with deterministic model doubles. Follow the **[testing guide](doc/agent/testing.md)** for Docker checks, one-task model setup, frozen-data comparisons, human review and acceptance criteria.

For the Streamlit pipeline, install its `requirements.txt` and use `python -m pytest -q tests/`. Dataset/model-dependent tests need their fixtures; the lightweight agent environment does not supply the original corpus or all pipeline dependencies. To run just the PAL/sentiment regression checks, use `python -m pytest -q tests/test_pal.py tests/test_sentiment.py` in that environment.

---

## Retrieval Pipeline Details

### Hybrid Search

The retrieval stage fuses two complementary signals:

| Component | Weight (α) | Description |
|---|---|---|
| BM25 (keyword) | 0.05 default | Okapi BM25 over tokenized `chunk_text` — captures exact keyword matches |
| FAISS (semantic) | 0.95 default | Cosine similarity via `all-mpnet-base-v2` embeddings — captures meaning |

Scores from each source are [min-max normalized](doc/algorithm/retrieval.md) before the weighted linear combination. The fused ranking is then passed to the [cross-encoder reranker](doc/algorithm/analytics.md) for precision refinement. For the full scoring formulas, weight selection rationale, and tuning guide, see the [retrieval stack reference](doc/backend/retrieval.md).

### Query Rewriting

The user query is expanded into multiple [diverse reformulations](doc/algorithm/query-expansion.md) via an LLM. All reformulations are run through the hybrid retriever; results are deduplicated and merged by score. This improves recall by surfacing documents that a single query phrasing might miss.

### HyDE (Hypothetical Document Embedding)

A [hypothetical subreddit profile document](doc/algorithm/query-expansion.md) is synthesized by an LLM and encoded to retrieve additional FAISS candidates. These are deduplicated and merged into the hybrid retrieval pool before reranking. HyDE results are append-only — they cannot displace candidates that already scored well on real signals.

---

## Documentation

| Document | Description |
|---|---|
| [`doc/agent/README.md`](doc/agent/README.md) | Agent architecture, setup, models, state and execution boundaries |
| [`doc/agent/testing.md`](doc/agent/testing.md) | Offline checks, live-model protocol, metrics and human review |
| [`doc/product/overview.md`](doc/product/overview.md) | Product narrative: problem, user journey, value proposition, and vision |
| [`doc/backend/pipeline.md`](doc/backend/pipeline.md) | Backend pipeline: component init, 9-step execution flow, graceful degradation, return payload |
| [`doc/backend/retrieval.md`](doc/backend/retrieval.md) | Retrieval stack: BM25, FAISS, hybrid fusion, query rewriting, HyDE, reranking, tuning guide |
| [`doc/backend/corpus.md`](doc/backend/corpus.md) | Offline corpus build: dataset download, build stages, per-script options, GCP setup |
| [`doc/frontend/structure.md`](doc/frontend/structure.md) | Frontend code boundaries and runtime lifecycle |
| [`doc/frontend/UIUX.md`](doc/frontend/UIUX.md) | Visual system, UI states, theme tokens, animations |
| [`doc/frontend/frontend-design.md`](doc/frontend/frontend-design.md) | Implementation constraints and regression checklist |
| [`doc/frontend/frontend-backend-interaction-guide.md`](doc/frontend/frontend-backend-interaction-guide.md) | Payload contract, adapter rules, error handling |
| [`doc/collab/contributing.md`](doc/collab/contributing.md) | Development workflow, branch strategy, PR process |
| [`doc/algorithm/retrieval.md`](doc/algorithm/retrieval.md) | BM25 scoring, bi-encoder FAISS retrieval, sliding-window chunking, hybrid fusion |
| [`doc/algorithm/query-expansion.md`](doc/algorithm/query-expansion.md) | Multi-query LLM expansion and HyDE hypothetical document retrieval |
| [`doc/algorithm/analytics.md`](doc/algorithm/analytics.md) | Cross-encoder reranking, RoBERTa sentiment scoring, legacy PAL execution |

---

## Implementation Status

| Module | Status | Notes |
|---|---|---|
| `creatorpal_agent/` | Implemented | ADK loop, four Skills, validated tools, atomic state and evaluation |
| `tests_agent/` + Agent CI | Passing offline | Includes crash recovery, model doubles, wheel and Docker execution |
| Live model comparison | Pending configuration | No measured model quality, latency or cost improvement claimed |
| Agent integration in Streamlit UI | Not implemented | Use the CLI for agent tasks |
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
| `src/pal/executor.py` | Done | Legacy in-process RestrictedPython executor |
| `src/sentiment/analyzer.py` | Done | RoBERTa sentiment scoring |
| `src/ingest/youtube.py` | Done | YouTube Data API v3 ingestion (requires `YOUTUBE_API_KEY`) |
| `src/generator/augmented_gen.py` | Done | LLM strategy report generation |

---

## License

MIT. See [LICENSE](LICENSE).

## Report
[CreatorPal Final Report (PDF)](./CreatorPal_Final_Report.pdf)
