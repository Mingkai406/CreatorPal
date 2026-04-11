# CreatorPal: YouTube-to-Reddit Audience Intelligence

> A retrieval-augmented system for matching YouTube creators to relevant Reddit communities and generating actionable audience strategy reports.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit)](https://streamlit.io/)
[![FAISS](https://img.shields.io/badge/FAISS-Vector%20Search-0467DF)](https://github.com/facebookresearch/faiss)
[![SentenceTransformers](https://img.shields.io/badge/SentenceTransformers-Embeddings-FF9900)](https://www.sbert.net/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Pipeline Design](#pipeline-design)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Data and Evaluation](#data-and-evaluation)
- [Deployment](#deployment)
- [Current Implementation Status](#current-implementation-status)
- [Development Workflow](#development-workflow)
- [License](#license)

---

## Overview

CreatorPal helps creators answer one practical question: **which Reddit communities best match my channel and how should I engage them?**

The system combines retrieval, reranking, analysis, and generation:

- Ingest creator/channel context from YouTube.
- Retrieve and rerank subreddit candidates from a FAISS index.
- Run PAL-style analytics and sentiment scoring for evidence grounding.
- Generate a final strategy report with ranked subreddit links.

### What it handles

| Concern | Mechanism |
|---|---|
| Channel understanding | YouTube metadata + comments ingestion |
| Theme extraction | LLM-based topic keyword extraction |
| Retrieval quality | HyDE query rewriting + FAISS dense retrieval |
| Candidate precision | Cross-encoder reranking |
| Quantitative analysis | PAL execution in RestrictedPython sandbox |
| Community sentiment | RoBERTa sentiment model on comment text |
| User-facing output | Streamlit app with ranked links + strategy report |

---

## Architecture

```
┌─────────────────────────────┐
│ Input: YouTube URL / Query  │
└──────────────┬──────────────┘
               │
       ┌───────▼────────┐
       │ YouTube Ingest │
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │ Theme Extract  │
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │ HyDE Rewriter  │
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │ FAISS Retrieve │  top-50
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │ Cross Reranker │  top-10
       └───────┬────────┘
               │
   ┌───────────▼───────────┐
   │ PAL + Sentiment Layer │
   └───────────┬───────────┘
               │
       ┌───────▼────────┐
       │ Report Gen LLM │
       └───────┬────────┘
               │
     ┌─────────▼─────────┐
     │ Streamlit Frontend │
     └────────────────────┘
```

---

## Repository Structure

```text
creatorpal/
├── app/
│   └── streamlit_app.py
├── data/
│   ├── download_reddit.py
│   ├── preprocess_corpus.py
│   ├── build_faiss_index.py
│   └── build_ground_truth.py
├── eval/
│   ├── retrieval_eval.py
│   └── generation_eval.py
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
├── requirements.txt
└── .env.example
```

---

## Pipeline Design

1. **Ingest**: collect channel metadata, video descriptions, and comments.
2. **Extract**: infer creator themes from channel context.
3. **Rewrite**: generate HyDE pseudo-document for retrieval.
4. **Retrieve**: dense search against subreddit profile index (top-50).
5. **Rerank**: cross-encoder scoring to top-10 candidates.
6. **Analyze**: PAL analytics + subreddit sentiment scoring.
7. **Generate**: synthesize final audience strategy report.
8. **Render**: display ranked subreddit links and report in Streamlit.

---

## Getting Started

### Prerequisites

- Python 3.11+
- pip
- Docker and Docker Compose (for containerized deployment)
- YouTube Data API v3 key
- vLLM-compatible OpenAI endpoint

### Local Setup

```bash
git clone <your-repo-url>
cd CreatorPal
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env` with your credentials:

```env
YOUTUBE_API_KEY=your_key
VLLM_ENDPOINT=http://localhost:8000/v1
```

### Run Locally

```bash
streamlit run app/streamlit_app.py
```

---

## Configuration

Environment variables currently used:

| Variable | Description |
|---|---|
| `YOUTUBE_API_KEY` | API key for YouTube Data API v3 |
| `VLLM_ENDPOINT` | OpenAI-compatible vLLM endpoint |

The configuration model and defaults are centralized in `src/config.py`.

---

## Data and Evaluation

### Data Pipeline Scripts

- `data/download_reddit.py`: download Reddit corpus (Pushshift mirror).
- `data/preprocess_corpus.py`: build subreddit profiles and text chunks.
- `data/build_faiss_index.py`: encode chunks and build FAISS index.
- `data/build_ground_truth.py`: create YouTube-channel-to-subreddit pairs.

### Evaluation Scripts

- `eval/retrieval_eval.py`: retrieval metrics such as Recall@K and MRR.
- `eval/generation_eval.py`: human-rating based generation evaluation scaffold.

---

## Deployment

### Docker Deployment

```bash
./docker-startup deploy
```

This starts:

- `vllm`: Llama 3.1 8B OpenAI-compatible inference server.
- `app`: Streamlit frontend service.

---

## Current Implementation Status

This repository is currently in **scaffold phase**:

- Project structure, interfaces, and dependency wiring are defined.
- Most core functions intentionally raise `NotImplementedError`.
- The current branch is suitable for parallel development by module owners.

For execution readiness, complete implementation is required in `src/`, `data/`, and `eval/`.

---

## Development Workflow

- Use feature branches per module domain (`data`, `retrieval`, `pal-sentiment`, `frontend-deploy`).
- Open PRs to `main` after module-level tests pass.
- Integrate through `src/pipeline.py` and run end-to-end verification.

---

## License

MIT. See [LICENSE](LICENSE).
