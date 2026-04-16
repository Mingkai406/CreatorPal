# Data Pipeline Reference

This document covers the full CreatorPal data pipeline: from raw Reddit dump to FAISS index.

## Overview

The pipeline converts a Reddit Pushshift submission dump (`.zst`) into a FAISS vector index and supporting files consumed by the retrieval stack at runtime.

```
RS_2019-04.zst
  │
  ▼  build_reddit_slim.py
reddit_slim.ndjson           (7-field subset, ~hundreds MB)
  │
  ├── ▼  preprocess_corpus.py
  │   subreddit_profiles.json      (aggregated per-subreddit documents)
  │       │
  │       ▼  build_faiss_index.py
  │       subreddit_profiles.faiss         (IndexFlatIP, all-mpnet-base-v2)
  │       subreddit_profile_chunks.json    (chunk ↔ index row metadata)
  │
  └── ▼  build_ground_truth.py
      ground_truth_pairs.csv       (YouTube-to-subreddit pairs for eval)
```

All outputs are written to `data/processed/`.

---

## Quick Start

```bash
# Full pipeline (requires data/RS_2019-04.zst)
bash data/run_pipeline.sh

# Quick local validation (first 10 000 posts only)
LIMIT_POSTS=10000 bash data/run_pipeline.sh
```

`run_pipeline.sh` is **idempotent**: each stage is skipped when its output already exists. Re-running after a partial failure picks up where it left off.

---

## Dataset Download

| Field | Value |
|---|---|
| **Source** | Reddit Pushshift April 2019 submissions |
| **File** | `RS_2019-04.zst` |
| **Size** | ~15.5 GB compressed |
| **URL** | https://zenodo.org/records/3608135 |

Download with the helper script:

```bash
python data/download_reddit.py --output data/RS_2019-04.zst
```

Or download manually and place the file at `data/RS_2019-04.zst` (or set `ZST_INPUT` to a different path).

> **Tip**: For local development, use `LIMIT_POSTS=10000` to work with a small slice without downloading the full file.

---

## Pipeline Stages

### Stage 1 – Build Slim NDJSON (`build_reddit_slim.py`)

Streams the raw `.zst` dump and writes a 7-field NDJSON subset. This keeps only the fields needed downstream, reducing disk usage from 15+ GB to a few hundred MB.

```bash
python data/build_reddit_slim.py \
    --input  data/RS_2019-04.zst \
    --output data/processed/reddit_slim.ndjson
```

| Option | Default | Description |
|---|---|---|
| `--input` | `data/RS_2019-04.zst` | Path to raw `.zst` dump |
| `--output` | `data/processed/reddit_slim.ndjson` | Output NDJSON path |
| `--fields` | `id,subreddit,created_utc,score,title,url,selftext` | Comma-separated fields to retain |
| `--min-score` | _(none)_ | Only keep posts with `score ≥ N` |
| `--limit-posts` | _(none)_ | Stop after N scanned posts (fast validation) |

---

### Stage 2 – Build Subreddit Profiles (`preprocess_corpus.py`)

Aggregates slim submissions into per-subreddit profile documents, keeping the top-50 posts by score per subreddit and filtering out subreddits with fewer than 10 posts.

```bash
python data/preprocess_corpus.py \
    --input  data/processed/reddit_slim.ndjson \
    --output data/processed/subreddit_profiles.json
```

| Option | Default | Description |
|---|---|---|
| `--input` | `data/processed/reddit_slim.ndjson` | Slim NDJSON input |
| `--output` | `data/processed/subreddit_profiles.json` | Profile JSON output |
| `--min-posts` | `10` | Minimum posts required to include a subreddit |
| `--top-posts` | `50` | Top-scored posts kept per subreddit |

---

### Stage 3 – Build Ground Truth (`build_ground_truth.py`)

Extracts `(YouTube channel, subreddit)` pairs from Reddit posts that contain YouTube links. Used by `eval/retrieval_eval.py` to compute Recall@K and MRR.

```bash
python data/build_ground_truth.py \
    --posts  data/processed/reddit_slim.ndjson \
    --output data/processed/ground_truth_pairs.csv
```

| Option | Default | Description |
|---|---|---|
| `--posts` | `data/processed/reddit_slim.ndjson` | NDJSON or `.zst` input |
| `--output` | `data/processed/ground_truth_pairs.csv` | Output CSV |
| `--min-score` | `2` | Minimum Reddit score required to keep a post |
| `--limit-posts` | _(none)_ | Stop after N scanned posts |

Stages 3 and 4 are independent and can be run in parallel once Stage 2 is complete.

---

### Stage 4 – Build FAISS Index (`build_faiss_index.py`)

Splits subreddit profile documents into 64-token sliding windows, encodes them with `all-mpnet-base-v2`, and writes a FAISS `IndexFlatIP` (cosine similarity via normalized vectors).

```bash
python data/build_faiss_index.py \
    --profiles        data/processed/subreddit_profiles.json \
    --output-index    data/processed/subreddit_profiles.faiss \
    --output-metadata data/processed/subreddit_profile_chunks.json
```

| Option | Default | Description |
|---|---|---|
| `--profiles` | `data/processed/subreddit_profiles.json` | Profile JSON input |
| `--output-index` | `data/processed/subreddit_profiles.faiss` | FAISS index output |
| `--output-metadata` | `data/processed/subreddit_profile_chunks.json` | Chunk metadata output |
| `--model-name` | `sentence-transformers/all-mpnet-base-v2` | Embedding model |
| `--window-tokens` | `64` | Sliding window size (in model tokens) |
| `--overlap-tokens` | `16` | Sliding window overlap (in model tokens) |
| `--batch-size` | `32` | Encoding batch size |

> **Resources**: On the full April 2019 dataset the index is expected to reach ~1 M vectors. Budget approximately 8 GB RAM for the embedding step.

---

## Inspecting Raw Data

`data/read_zst.py` lets you inspect the `.zst` file without running the full pipeline:

```bash
# Print the first 5 records (default fields)
python data/read_zst.py RS_2019-04.zst --limit 5

# Print full raw JSON for 2 records
python data/read_zst.py RS_2019-04.zst --raw --limit 2

# Filter by subreddit and minimum score
python data/read_zst.py RS_2019-04.zst --subreddit AskReddit --min-score 10 --limit 10

# Count matching records (scans the full file)
python data/read_zst.py RS_2019-04.zst --subreddit AskReddit --count
```

---

## GCP / Large-Scale Setup

For full-scale processing on GCP:

1. Upload `RS_2019-04.zst` to a Cloud Storage bucket.
2. Run the pipeline on a VM with sufficient resources (recommended: 16 vCPU, 64 GB RAM, 500 GB SSD).
3. Commit only derived artifacts — not the raw or slim dumps:
   - `data/processed/subreddit_profiles.json`
   - `data/processed/subreddit_profile_chunks.json`
   - `data/processed/ground_truth_pairs.csv`
4. Store `reddit_slim.ndjson` and `subreddit_profiles.faiss` on GCP or use Git LFS, since they typically exceed GitHub's 100 MB file limit.

---

## Environment Configuration

After the pipeline completes, verify `.env` points to the generated artifacts:

```bash
FAISS_INDEX_PATH=data/processed/subreddit_profiles.faiss
FAISS_METADATA_PATH=data/processed/subreddit_profile_chunks.json
```

These match the defaults in both `src/config.py` and `.env.example`, so no edits are needed if you used the default output paths.
