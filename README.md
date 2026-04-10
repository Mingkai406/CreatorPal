# CreatorPal

CreatorPal is a RAG-centric system for matching YouTube creators with the most relevant Reddit communities and generating actionable audience strategy reports.

## Architecture

CreatorPal orchestrates an end-to-end retrieval-augmented workflow:

1. Channel Ingest: YouTube Data API v3 collects channel metadata, video descriptions, and top comments.
2. Theme Extractor: Llama 3.1 (8B) extracts channel themes and keywords.
3. Query Rewriting (HyDE): Llama 3.1 writes a hypothetical ideal subreddit description for retrieval.
4. RAG Retriever: `all-mpnet-base-v2` retrieves top-50 profiles from a FAISS Flat index.
5. Reranker: `ms-marco-MiniLM-L-6-v2` reranks to top-10 candidates.
6. PAL Executor: Llama-generated Python is executed in a RestrictedPython sandbox for dynamic analytics.
7. Sentiment Analyzer: `cardiffnlp/twitter-roberta-base-sentiment-latest` computes subreddit sentiment from comments.
8. Augmented Generator: Llama 3.1 produces the final strategy report from retrieved context + PAL + sentiment outputs.
9. Streamlit UI: users enter a YouTube channel URL or free-text query and receive ranked subreddit links and report text.

## Project Layout

```
creatorpal/
├── docker-compose.yml
├── Dockerfile
├── docker-startup
├── README.md
├── requirements.txt
├── .env.example
├── data/
├── src/
├── app/
└── eval/
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure environment:
   ```bash
   cp .env.example .env
   ```
3. Add your `YOUTUBE_API_KEY` and `VLLM_ENDPOINT` to `.env`.

## Local Run

```bash
streamlit run app/streamlit_app.py
```

## Docker Deploy

```bash
./docker-startup deploy
```

This starts:
- `vllm` service for Llama 3.1 (OpenAI-compatible endpoint)
- `app` service for the Streamlit frontend

## Data and Evaluation

- `data/`: corpus download, preprocessing, FAISS index build, and ground-truth construction.
- `eval/`: retrieval metrics (Recall@K, MRR) and generation evaluation scaffolding.

