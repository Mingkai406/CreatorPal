# Streamlit application and data pipeline

Run commands from the repository root in a dedicated Python environment. This page covers the YouTube-to-Reddit Streamlit workflow, corpus preparation and self-hosted vLLM deployment. For research tasks through the ADK agent, use the [agent quickstart](agent/README.md).

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

See [`.env.example`](../.env.example) for the full list of supported variables. The [pipeline configuration reference](backend/pipeline.md) documents each of the 14 environment variables with their types and defaults.

### Run locally with mock pipeline (no backend required)

```bash
export CREATORPAL_USE_MOCK_PIPELINE=1
streamlit run app/streamlit_app.py --server.port 8501
```

### Run locally with real pipeline

Requires a populated [FAISS index](backend/corpus.md) and a running vLLM endpoint. See [Data Pipeline](#data-pipeline) and [Deployment](#deployment).

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

For the full pipeline reference, individual script options, and GCP/large-scale setup, see [`doc/backend/corpus.md`](backend/corpus.md).

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
