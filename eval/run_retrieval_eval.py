"""End-to-end retrieval evaluation with realistic query construction.

Instead of using ground-truth subreddit names as queries (which leaks the
answer), we construct queries from the *profile text* of the GT subreddits
and evaluate whether the retrieval pipeline can surface the correct
subreddits from semantic content alone.

Two evaluation levels are supported:
  Level 1  – Hybrid only (BM25 + FAISS)
  Level 2  – Hybrid + Cross-Encoder rerank  (--with-rerank)

Usage (from project root):
    python eval/run_retrieval_eval.py \
        --ground-truth data/processed/ground_truth_pairs.csv \
        --output eval/predictions.csv \
        --output-report eval/report.json \
        --k-values 5 10 50 \
        --sample 200

    # with reranking
    python eval/run_retrieval_eval.py \
        --ground-truth data/processed/ground_truth_pairs.csv \
        --output eval/predictions.csv \
        --output-report eval/report.json \
        --with-rerank \
        --k-values 5 10 50 \
        --sample 200
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.retrieval_eval import (
    bootstrap_ci,
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from src.retrieval.bm25_search import BM25Retriever
from src.retrieval.faiss_search import FaissRetriever
from src.retrieval.hybrid_search import HybridRetriever

logger = logging.getLogger(__name__)

DEFAULT_INDEX = Path("data/processed/subreddit_profiles.faiss")
DEFAULT_META = Path("data/processed/subreddit_profile_chunks.json")
DEFAULT_MODEL = "sentence-transformers/all-mpnet-base-v2"
MAX_QUERY_WORDS = 100


# ---------------------------------------------------------------------------
# Build components
# ---------------------------------------------------------------------------

def build_retriever(
    index_path: Path,
    meta_path: Path,
    model: str,
    alpha_kw: float = 0.15,
    alpha_sem: float = 0.85,
) -> HybridRetriever:
    """Construct the hybrid (BM25 + FAISS) retriever stack."""
    logger.info("Loading FAISS retriever …")
    faiss_ret = FaissRetriever(
        index_path=index_path,
        metadata_path=meta_path,
        bi_encoder_model=model,
    )
    logger.info("Loading BM25 retriever …")
    bm25_ret = BM25Retriever(metadata_path=meta_path)
    return HybridRetriever(
        faiss_retriever=faiss_ret,
        bm25_retriever=bm25_ret,
        alpha_keyword=alpha_kw,
        alpha_semantic=alpha_sem,
    )


def build_reranker(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
    """Lazily import and construct the cross-encoder reranker."""
    from src.retrieval.reranker import CrossEncoderReranker
    return CrossEncoderReranker(model_name=model_name)


# ---------------------------------------------------------------------------
# Query construction helpers
# ---------------------------------------------------------------------------

def _build_sub_to_chunks(chunk_meta: pd.DataFrame) -> dict[str, list[str]]:
    """Map each subreddit to its list of chunk texts (ordered by chunk_id)."""
    sub_chunks: dict[str, list[str]] = {}
    for sub, grp in chunk_meta.groupby("subreddit"):
        ordered = grp.sort_values("chunk_id") if "chunk_id" in grp.columns else grp
        sub_chunks[sub] = list(ordered["chunk_text"])
    return sub_chunks


_META_PREFIX_RE = re.compile(
    r"^subreddit\s*:\s*r\s*/\s*\S+\s+subscribers\s*:\s*\d+\s+top\s+posts\s*:\s*",
    re.IGNORECASE,
)


def _strip_meta_prefix(text: str) -> str:
    """Remove the 'subreddit : r/xxx subscribers : NNN top posts :' header."""
    return _META_PREFIX_RE.sub("", text).strip()


def _strip_subreddit_names(text: str, names: set[str]) -> str:
    """Remove literal subreddit names from query text to prevent BM25 leakage."""
    for name in names:
        text = re.sub(re.escape(name), "", text, flags=re.IGNORECASE)
        text = re.sub(r"r\s*/\s*" + re.escape(name), "", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def _truncate(text: str, max_words: int = MAX_QUERY_WORDS) -> str:
    words = text.split()
    return " ".join(words[:max_words])


def build_query_for_channel(
    gt_subreddits: set[str],
    sub_to_chunks: dict[str, list[str]],
) -> str | None:
    """Build a realistic query from the profile text of a channel's GT subreddits.

    Prefers non-header chunks (chunk_id > 0) to avoid metadata.  Falls back
    to chunk 0 with metadata prefix stripped.  Subreddit names are scrubbed
    to prevent trivial BM25 matches.
    """
    parts: list[str] = []
    for sub in sorted(gt_subreddits):
        chunks = sub_to_chunks.get(sub)
        if not chunks:
            continue
        if len(chunks) > 1:
            parts.append(chunks[1])
        else:
            parts.append(_strip_meta_prefix(chunks[0]))
    if not parts:
        return None
    raw = " ".join(parts)
    raw = _strip_subreddit_names(raw, gt_subreddits)
    return _truncate(raw)


# ---------------------------------------------------------------------------
# Prediction generation
# ---------------------------------------------------------------------------

def generate_predictions(
    gt_df: pd.DataFrame,
    chunk_meta: pd.DataFrame,
    retriever: HybridRetriever,
    reranker: Any | None,
    top_k: int,
    rerank_top_k: int,
    k_values: list[int],
    sample_n: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Run retrieval for each channel, collect predictions and per-query metrics.

    Returns (predictions_df, per_query_details) where per_query_details maps
    channel_id -> {query, gt_subs, level -> {metric -> value}}.
    """
    sub_to_chunks = _build_sub_to_chunks(chunk_meta)
    indexed_subs = set(chunk_meta["subreddit"].unique())

    channel_groups: dict[str, set[str]] = {}
    for cid, grp in gt_df.groupby("channel_id"):
        subs = set(grp["subreddit"])
        if subs & indexed_subs:
            channel_groups[cid] = subs
    channel_ids = list(channel_groups.keys())

    if sample_n and sample_n < len(channel_ids):
        random.seed(42)
        channel_ids = random.sample(channel_ids, sample_n)

    logger.info(
        "Generating predictions for %d channels (rerank=%s) …",
        len(channel_ids),
        reranker is not None,
    )

    rows: list[dict] = []
    per_query: dict[str, dict] = {}
    t0 = time.time()

    for i, cid in enumerate(channel_ids):
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            logger.info("  progress: %d / %d  (%.1fs)", i + 1, len(channel_ids), elapsed)

        gt_subs = channel_groups[cid]
        query = build_query_for_channel(gt_subs, sub_to_chunks)
        if query is None:
            continue

        relevant = gt_subs & indexed_subs

        hybrid_results = retriever.retrieve(query, top_k=top_k)

        def _dedup_and_extract(results: list[dict], limit: int) -> list[str]:
            seen: set[str] = set()
            ordered: list[str] = []
            for r in results:
                sub = r["subreddit"]
                if sub not in seen:
                    seen.add(sub)
                    ordered.append(sub)
                    if len(ordered) >= limit:
                        break
            return ordered

        hybrid_retrieved = _dedup_and_extract(hybrid_results, max(k_values))

        detail: dict[str, Any] = {
            "query_preview": query[:200],
            "gt_subs": sorted(relevant),
        }

        detail["hybrid"] = _compute_query_metrics(hybrid_retrieved, relevant, k_values)

        if reranker is not None:
            reranked_results = reranker.rerank(
                query=query,
                candidates=hybrid_results,
                top_k=rerank_top_k,
            )
            rerank_retrieved = _dedup_and_extract(reranked_results, max(k_values))
            detail["hybrid+rerank"] = _compute_query_metrics(rerank_retrieved, relevant, k_values)
            final_retrieved = rerank_retrieved
            final_level = "hybrid+rerank"
        else:
            final_retrieved = hybrid_retrieved
            final_level = "hybrid"

        for rank, sub in enumerate(final_retrieved, start=1):
            rows.append({"channel_id": cid, "subreddit": sub, "rank": rank})

        per_query[cid] = detail

    elapsed = time.time() - t0
    logger.info("Prediction generation completed in %.1fs", elapsed)
    return pd.DataFrame(rows), per_query


def _compute_query_metrics(
    retrieved: list[str],
    relevant: set[str],
    k_values: list[int],
) -> dict[str, float]:
    """Compute all per-query metrics for a single retrieval list."""
    m: dict[str, float] = {}
    for k in k_values:
        m[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)
        m[f"precision@{k}"] = precision_at_k(retrieved, relevant, k)
        m[f"ndcg@{k}"] = ndcg_at_k(retrieved, relevant, k)
        m[f"hit_rate@{k}"] = hit_rate_at_k(retrieved, relevant, k)
    m["mrr"] = mean_reciprocal_rank(retrieved, relevant)
    return m


# ---------------------------------------------------------------------------
# Aggregation & reporting
# ---------------------------------------------------------------------------

def aggregate_metrics(
    per_query: dict[str, dict],
    k_values: list[int],
    levels: list[str],
) -> dict[str, dict[str, Any]]:
    """Aggregate per-query metrics into means with bootstrap CIs.

    Returns {level: {metric_name: {mean, ci_lower, ci_upper}}}.
    """
    metric_names = []
    for k in k_values:
        metric_names.extend([f"recall@{k}", f"precision@{k}", f"ndcg@{k}", f"hit_rate@{k}"])
    metric_names.append("mrr")

    report: dict[str, dict[str, Any]] = {}
    for level in levels:
        level_report: dict[str, Any] = {}
        for mname in metric_names:
            scores = [
                detail[level][mname]
                for detail in per_query.values()
                if level in detail
            ]
            if not scores:
                level_report[mname] = {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
                continue
            mean, lo, hi = bootstrap_ci(scores)
            level_report[mname] = {"mean": mean, "ci_lower": lo, "ci_upper": hi}
        level_report["num_channels"] = sum(1 for d in per_query.values() if level in d)
        report[level] = level_report
    return report


def print_report(report: dict[str, dict[str, Any]]) -> None:
    """Pretty-print the evaluation report to stdout."""
    for level, metrics in report.items():
        n = metrics.get("num_channels", "?")
        print(f"\n{'=' * 55}")
        print(f"  Level: {level}    ({n} channels)")
        print(f"{'=' * 55}")
        for mname, val in metrics.items():
            if mname == "num_channels":
                continue
            m = val["mean"]
            lo = val["ci_lower"]
            hi = val["ci_upper"]
            print(f"  {mname:>18s}: {m:.4f}  (95% CI: {lo:.4f} – {hi:.4f})")
        print(f"{'=' * 55}")


def save_per_query_csv(per_query: dict[str, dict], path: Path, level: str) -> None:
    """Write per-channel metric detail to CSV for deeper analysis."""
    rows: list[dict] = []
    for cid, detail in per_query.items():
        if level not in detail:
            continue
        row: dict[str, Any] = {"channel_id": cid, "gt_subs": "|".join(detail["gt_subs"])}
        row.update(detail[level])
        rows.append(row)
    if rows:
        pd.DataFrame(rows).to_csv(path, index=False)
        logger.info("Per-query detail CSV written to %s (%d rows)", path, len(rows))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run end-to-end retrieval evaluation.")
    p.add_argument("--ground-truth", type=Path, default=Path("data/processed/ground_truth_pairs.csv"))
    p.add_argument("--output", type=Path, default=Path("eval/predictions.csv"))
    p.add_argument("--output-report", type=Path, default=None, help="JSON report path")
    p.add_argument("--output-detail", type=Path, default=None, help="Per-query CSV path")
    p.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    p.add_argument("--meta", type=Path, default=DEFAULT_META)
    p.add_argument("--model", type=str, default=DEFAULT_MODEL)
    p.add_argument("--k-values", nargs="+", type=int, default=[5, 10, 50])
    p.add_argument("--top-k", type=int, default=50, help="Candidates from hybrid retrieval")
    p.add_argument("--rerank-top-k", type=int, default=10, help="Top-k after reranking")
    p.add_argument("--with-rerank", action="store_true", help="Enable cross-encoder reranking (Level 2)")
    p.add_argument("--rerank-model", type=str, default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    p.add_argument("--sample", type=int, default=None, help="Sample N channels for faster evaluation")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = parse_args()

    gt_df = pd.read_csv(args.ground_truth)
    logger.info(
        "Loaded %d ground-truth pairs across %d channels",
        len(gt_df),
        gt_df["channel_id"].nunique(),
    )

    chunk_meta = pd.read_json(args.meta) if args.meta.suffix == ".json" else pd.read_json(args.meta, lines=True)
    logger.info("Loaded %d chunk metadata rows", len(chunk_meta))

    retriever = build_retriever(args.index, args.meta, args.model)

    reranker = build_reranker(args.rerank_model) if args.with_rerank else None

    pred_df, per_query = generate_predictions(
        gt_df=gt_df,
        chunk_meta=chunk_meta,
        retriever=retriever,
        reranker=reranker,
        top_k=args.top_k,
        rerank_top_k=args.rerank_top_k,
        k_values=args.k_values,
        sample_n=args.sample,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pred_df.to_csv(args.output, index=False)
    logger.info("Wrote %d prediction rows to %s", len(pred_df), args.output)

    levels = ["hybrid"]
    if args.with_rerank:
        levels.append("hybrid+rerank")

    report = aggregate_metrics(per_query, args.k_values, levels)
    print_report(report)

    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("JSON report written to %s", args.output_report)

    if args.output_detail:
        primary_level = levels[-1]
        args.output_detail.parent.mkdir(parents=True, exist_ok=True)
        save_per_query_csv(per_query, args.output_detail, primary_level)


if __name__ == "__main__":
    main()
