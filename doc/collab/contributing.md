# Contributing to CreatorPal

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys and paths
```

For local UI development without a live backend:

```bash
export CREATORPAL_USE_MOCK_PIPELINE=1
streamlit run app/streamlit_app.py --server.port 8501
```

---

## Branch Strategy

| Branch | Scope |
|---|---|
| `feature/data-pipeline` | Dataset download, slim build, ground-truth extraction |
| `feature/data-pipeline-config` | Corpus preprocessing, config management, pipeline orchestration |
| `feature/retrieval` | Hybrid search, BM25, query rewriting, HyDE, reranking |
| `feature/pal-sentiment` | PAL executor, sentiment analyzer, evaluation scripts |
| `feature/frontend-deploy` | Streamlit UI, Docker, deployment |

All branches integrate into `main` via pull request.

---

## Pull Request Guidelines

- Keep PRs focused on a single concern.
- **Frontend changes** (`app/` or `app/helpers/`): update the relevant doc under `doc/frontend/` in the same PR.
- **Payload shape changes** (`src/pipeline.py` → `adapt()`): update `app/helpers/adapter.py` and `doc/frontend/frontend-backend-interaction-guide.md` in the same PR.
- Verify both light and dark themes visually before merging frontend changes.
- Run the relevant tests before opening a PR (see [Testing](#testing)).

---

## Module Ownership

| Area | Modules |
|---|---|
| Data & Configuration | `data/`, `src/config.py`, `src/pipeline.py` |
| Retrieval | `src/ingest/`, `src/retrieval/` |
| Analytics & Evaluation | `src/pal/`, `src/sentiment/`, `eval/` |
| Frontend & Deployment | `app/`, `Dockerfile`, `docker-compose.yml`, `docker-startup` |

---

## Testing

Run the test suite before opening a PR:

```bash
python tests/test_retrieval_smoke.py   # BM25 + FAISS + hybrid fusion
python tests/test_pal.py               # PAL code generation + sandbox
python tests/test_sentiment.py         # RoBERTa sentiment scoring
python tests/test_eval.py              # retrieval evaluation metrics
```

Tests run as standalone scripts and require no test runner. Tests that depend on a live FAISS index or vLLM endpoint are skipped automatically when those services are unavailable.

---

## Quality Gates

Before a PR is merged, verify the relevant areas:

| Area | Gate |
|---|---|
| Data | Artifact paths and formats are correct |
| Retrieval | Stable top-10 subreddit output for sample queries |
| Frontend | Every recommended subreddit renders with a clickable Reddit URL |
| Evaluation | `eval/` scripts produce Recall@K and generation quality metrics |
| Integration | `src/pipeline.py` runs end-to-end from input to strategy report |

---

## Documentation Rules

- Code is the source of truth. If a doc conflicts with code, update the doc.
- Do not include internal planning content (task assignments, deadlines) in committed docs.
- Keep all documentation in English for consistency.
