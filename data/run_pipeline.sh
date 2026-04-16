#!/usr/bin/env bash
# data/run_pipeline.sh – End-to-end CreatorPal data pipeline
#
# Runs all four pipeline stages in order.  Each step is idempotent:
# it is skipped automatically when its output already exists.
#
# Usage:
#   bash data/run_pipeline.sh
#
# Environment overrides:
#   ZST_INPUT    – path to raw .zst dump       (default: data/RS_2019-04.zst)
#   LIMIT_POSTS  – stop after N posts per step  (fast local validation)
#
# Outputs written to data/processed/:
#   reddit_slim.ndjson              filtered submissions (7 fields)
#   subreddit_profiles.json         aggregated subreddit profile documents
#   ground_truth_pairs.csv          YouTube-to-subreddit pairs for evaluation
#   subreddit_profiles.faiss        FAISS IndexFlatIP (all-mpnet-base-v2)
#   subreddit_profile_chunks.json   per-chunk metadata aligned with the index

set -euo pipefail

ZST_INPUT="${ZST_INPUT:-data/RS_2019-04.zst}"
PROCESSED_DIR="data/processed"

SLIM_NDJSON="$PROCESSED_DIR/reddit_slim.ndjson"
PROFILES_JSON="$PROCESSED_DIR/subreddit_profiles.json"
GROUND_TRUTH_CSV="$PROCESSED_DIR/ground_truth_pairs.csv"
FAISS_INDEX="$PROCESSED_DIR/subreddit_profiles.faiss"
CHUNKS_JSON="$PROCESSED_DIR/subreddit_profile_chunks.json"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
skip() { log "SKIP  $1 already exists"; }

mkdir -p "$PROCESSED_DIR"

# ---------------------------------------------------------------------------
# Step 1 – Build slim NDJSON from the raw .zst dump
# ---------------------------------------------------------------------------
if [ -f "$SLIM_NDJSON" ]; then
    skip "$SLIM_NDJSON"
else
    log "Step 1/4  building slim NDJSON from $ZST_INPUT …"
    if [ ! -f "$ZST_INPUT" ]; then
        echo "ERROR: $ZST_INPUT not found. Download it first:" >&2
        echo "  python data/download_reddit.py --output $ZST_INPUT" >&2
        exit 1
    fi
    LIMIT_ARG=""
    if [ -n "${LIMIT_POSTS:-}" ]; then
        LIMIT_ARG="--limit-posts $LIMIT_POSTS"
    fi
    # shellcheck disable=SC2086
    python data/build_reddit_slim.py \
        --input  "$ZST_INPUT" \
        --output "$SLIM_NDJSON" \
        $LIMIT_ARG
    log "Step 1/4  done → $SLIM_NDJSON"
fi

# ---------------------------------------------------------------------------
# Step 2 – Aggregate subreddit profiles
# ---------------------------------------------------------------------------
if [ -f "$PROFILES_JSON" ]; then
    skip "$PROFILES_JSON"
else
    log "Step 2/4  building subreddit profiles …"
    python data/preprocess_corpus.py \
        --input  "$SLIM_NDJSON" \
        --output "$PROFILES_JSON"
    log "Step 2/4  done → $PROFILES_JSON"
fi

# ---------------------------------------------------------------------------
# Step 3 – Extract ground-truth YouTube–subreddit pairs
# ---------------------------------------------------------------------------
if [ -f "$GROUND_TRUTH_CSV" ]; then
    skip "$GROUND_TRUTH_CSV"
else
    log "Step 3/4  building ground-truth pairs …"
    LIMIT_ARG=""
    if [ -n "${LIMIT_POSTS:-}" ]; then
        LIMIT_ARG="--limit-posts $LIMIT_POSTS"
    fi
    # shellcheck disable=SC2086
    python data/build_ground_truth.py \
        --posts  "$SLIM_NDJSON" \
        --output "$GROUND_TRUTH_CSV" \
        $LIMIT_ARG
    log "Step 3/4  done → $GROUND_TRUTH_CSV"
fi

# ---------------------------------------------------------------------------
# Step 4 – Encode profiles and build FAISS index
# ---------------------------------------------------------------------------
if [ -f "$FAISS_INDEX" ] && [ -f "$CHUNKS_JSON" ]; then
    skip "$FAISS_INDEX + $CHUNKS_JSON"
else
    log "Step 4/4  building FAISS index …"
    python data/build_faiss_index.py \
        --profiles        "$PROFILES_JSON" \
        --output-index    "$FAISS_INDEX" \
        --output-metadata "$CHUNKS_JSON"
    log "Step 4/4  done → $FAISS_INDEX"
fi

log "Pipeline complete.  All outputs in $PROCESSED_DIR/"
