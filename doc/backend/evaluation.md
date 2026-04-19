# Evaluation Reference

This document covers how CreatorPal evaluates system quality today, including:

- retrieval evaluation (`eval/retrieval_eval.py`, `eval/run_retrieval_eval.py`)
- generation evaluation (`eval/generation_eval.py`)
- community sentiment scoring interpretation (`src/sentiment/analyzer.py`, `src/pipeline.py`)

It is the backend reference for what is currently measured, how metrics are produced, and what each score should and should not be interpreted as.

---

## 1. Scope

CreatorPal currently has two formal evaluation tracks and one runtime analytics signal:

| Track | Script(s) | Status | Output |
|---|---|---|---|
| Retrieval quality | `eval/retrieval_eval.py`, `eval/run_retrieval_eval.py` | Implemented | Recall@K, Precision@K (library function), MRR |
| Generation quality | `eval/generation_eval.py` | Implemented | Human rubric averages (1-5) |
| Community sentiment | `src/sentiment/analyzer.py` in pipeline runtime | Implemented (runtime), no dedicated eval script | Per-subreddit sentiment score in [-1, +1] |

Important: there is no standalone `eval/sentiment_eval.py` yet. Sentiment is used in inference and tested via unit tests (`tests/test_sentiment.py`), but not benchmarked by a dedicated offline evaluator.

---

## 2. Evaluation Artifacts

The retrieval evaluation depends on artifacts produced by the data pipeline:

| Artifact | Produced by | Used by |
|---|---|---|
| `data/processed/ground_truth_pairs.csv` | `data/build_ground_truth.py` | `eval/run_retrieval_eval.py` and `eval/retrieval_eval.py` |
| `data/processed/subreddit_profiles.faiss` | `data/build_faiss_index.py` | `eval/run_retrieval_eval.py` |
| `data/processed/subreddit_profile_chunks.json` | `data/build_faiss_index.py` | `eval/run_retrieval_eval.py` |

Run the data pipeline first if these files are missing:

```bash
bash data/run_pipeline.sh
```

---

## 3. Retrieval Evaluation

### 3.1 Metric Definitions

`eval/retrieval_eval.py` provides per-query metric functions and aggregate evaluation:

- `recall_at_k(retrieved, relevant, k)`  
  Fraction of relevant items found in top-k, capped at 1.0.
- `precision_at_k(retrieved, relevant, k)`  
  Fraction of top-k retrieved items that are relevant.
- `mean_reciprocal_rank(retrieved, relevant)`  
  Reciprocal rank of first relevant item.

`run_retrieval_evaluation(...)` aggregates these metrics across channels that appear in both ground truth and predictions.

### 3.2 End-to-End Runner

`eval/run_retrieval_eval.py` is the practical runner that:

1. Loads `ground_truth_pairs.csv`
2. Builds the hybrid retriever stack (FAISS + BM25)
3. Generates predictions per `channel_id`
4. Writes predictions CSV
5. Prints aggregate metrics

Run:

```bash
python eval/run_retrieval_eval.py \
  --ground-truth data/processed/ground_truth_pairs.csv \
  --output eval/predictions.csv \
  --k-values 5 10 50 \
  --top-k 50
```

### 3.3 Current Query Proxy

For each channel, the runner currently builds a proxy query by joining that channel's ground-truth subreddit names:

```python
query = " ".join(gt_subs)
```

This is explicitly documented in code as a fallback because channel descriptions are not available in the eval input.

Interpretation impact:

- useful for relative retriever regression checks
- not equivalent to full online pipeline input quality (real user query + theme extraction + rewrite + rerank flow)

### 3.4 Output Schema

Predictions file (`--output`) format:

| Column | Meaning |
|---|---|
| `channel_id` | Channel key from ground truth |
| `subreddit` | Retrieved subreddit |
| `rank` | Rank after dedupe |

Printed metrics from runner `evaluate(...)`:

- `recall@K` for each requested K
- `mrr`
- `num_channels_evaluated`

Note: the runner prints recall and MRR. Precision exists in `eval/retrieval_eval.py` but is not currently included in runner output.

---

## 4. Generation Evaluation

`eval/generation_eval.py` is an interactive human-evaluation tool.

### 4.1 Rubric

Each report is scored on three 1-5 dimensions:

| Dimension | Question |
|---|---|
| `coherence` | Is the report logically structured and easy to follow? |
| `grounding` | Are recommendations backed by retrieved subreddit data? |
| `actionability` | Can the creator act on these recommendations? |

### 4.2 Workflow

1. Put generated reports as `.txt` files in one directory
2. Run evaluator
3. Rate each dimension for each report in terminal
4. Read averaged summary

Run:

```bash
python eval/generation_eval.py --reports-dir path/to/reports
```

### 4.3 Limitations

- manual, not automatic
- no inter-rater agreement tracking
- no stored metadata for evaluator identity/session

Use it for qualitative validation and release checks, not as a high-throughput benchmark.

---

## 5. Community Sentiment Scoring

This section clarifies what the "Community sentiment" panel means in the running app.

### 5.1 Actual Runtime Logic

In `src/pipeline.py`, sentiment runs after reranking:

1. Take reranked entries (`ranked_raw`)
2. Group by `subreddit`
3. For each entry, append `chunk_text` into that subreddit's text list
4. Call `SentimentAnalyzer.score_subreddits(...)`
5. Store one average score per subreddit
6. Render in Streamlit sentiment bars

The analyzer mapping is:

- `positive` -> `+confidence`
- `negative` -> `-confidence`
- `neutral` -> `0.0`

Final subreddit score is the mean of mapped per-text scores.

### 5.2 What Text Is Scored

The scored text is retrieved Reddit profile chunks (`chunk_text`), not live comment threads fetched at runtime.

Those chunks are generated from offline Reddit submission content (title + selftext) during data preprocessing and chunking.

Therefore:

- sentiment reflects tone of retrieved corpus passages for candidate communities
- sentiment is not a full real-time moderation-risk detector for current subreddit comment behavior

### 5.3 Frontend Rendering

The sentiment bar component displays:

- bar width: `abs(score)` (clamped to 1.0)
- color:
  - green for `score >= 0.5`
  - amber for `0.2 <= score < 0.5`
  - red for `score < 0.2`

This is a visualization heuristic, not a calibrated toxicity threshold.

---

## 6. Test Coverage

Relevant automated tests:

| File | Coverage |
|---|---|
| `tests/test_eval.py` | retrieval metric functions + generation rubric summarization |
| `tests/test_sentiment.py` | label mapping, per-text inference path, subreddit aggregation |

Run:

```bash
python tests/test_eval.py
python tests/test_sentiment.py
```

---

## 7. Recommended Next Steps

To improve evaluation rigor, prioritize:

1. Add a dedicated sentiment evaluation script (`eval/sentiment_eval.py`) with labeled subreddit text samples.
2. Extend retrieval runner to include Precision@K and nDCG@K in printed output.
3. Add offline replay evaluation for the full online pipeline query path (real user query + rewrite + rerank), not only ground-truth-subreddit proxy queries.
4. Add multi-rater generation evaluation with agreement reporting.

