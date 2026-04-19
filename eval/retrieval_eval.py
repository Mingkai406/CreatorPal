"""Retrieval quality metrics for YouTube-to-subreddit ground-truth evaluation.

Provides per-query metric functions (recall, precision, NDCG, MRR, hit rate)
and a bootstrap confidence interval utility for aggregate reporting.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Per-query metrics
# ---------------------------------------------------------------------------

def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant items found in the top-k results, capped at 1.0."""
    if not relevant:
        return 0.0
    hits = sum(1 for item in retrieved[:k] if item in relevant)
    return min(hits / len(relevant), 1.0)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of top-k retrieved items that are relevant."""
    if k <= 0:
        return 0.0
    hits = sum(1 for item in retrieved[:k] if item in relevant)
    return hits / k


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at rank k.

    Relevance is binary (1 if in relevant set, 0 otherwise).
    """
    if not relevant or k <= 0:
        return 0.0

    dcg = 0.0
    for i, item in enumerate(retrieved[:k]):
        if item in relevant:
            dcg += 1.0 / math.log2(i + 2)

    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    return dcg / idcg if idcg > 0 else 0.0


def mean_reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """1/rank of the first relevant item, or 0.0 if none found."""
    for i, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / i
    return 0.0


def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """1.0 if at least one relevant item appears in top-k, else 0.0."""
    return 1.0 if any(item in relevant for item in retrieved[:k]) else 0.0


# ---------------------------------------------------------------------------
# Bootstrap confidence interval
# ---------------------------------------------------------------------------

def bootstrap_ci(
    scores: list[float],
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Compute mean and bootstrap confidence interval.

    Returns:
        (mean, ci_lower, ci_upper)
    """
    arr = np.array(scores, dtype=np.float64)
    if len(arr) == 0:
        return 0.0, 0.0, 0.0

    rng = np.random.default_rng(seed)
    means = np.empty(n_bootstrap, dtype=np.float64)
    for i in range(n_bootstrap):
        sample = rng.choice(arr, size=len(arr), replace=True)
        means[i] = sample.mean()

    alpha = 1 - confidence
    ci_lower = float(np.percentile(means, 100 * alpha / 2))
    ci_upper = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return float(arr.mean()), ci_lower, ci_upper


# ---------------------------------------------------------------------------
# Batch evaluation (from pre-computed prediction CSV)
# ---------------------------------------------------------------------------

def run_retrieval_evaluation(
    ground_truth_path: str,
    predictions_path: str,
    k_values: list[int],
) -> dict[str, float]:
    """Run retrieval evaluation from CSV files and return a metric dictionary.

    Kept for backward compatibility with existing callers.
    """
    gt_df = pd.read_csv(ground_truth_path)
    pred_df = pd.read_csv(predictions_path)

    gt_by_channel: dict[str, set[str]] = {}
    for channel_id, group in gt_df.groupby("channel_id"):
        gt_by_channel[channel_id] = set(group["subreddit"])

    pred_by_channel: dict[str, list[str]] = {}
    for channel_id, group in pred_df.groupby("channel_id"):
        sorted_group = group.sort_values("rank")
        pred_by_channel[channel_id] = list(sorted_group["subreddit"])

    channels = set(gt_by_channel) & set(pred_by_channel)
    if not channels:
        metrics: dict[str, float] = {}
        for k in k_values:
            metrics[f"recall@{k}"] = 0.0
            metrics[f"precision@{k}"] = 0.0
            metrics[f"ndcg@{k}"] = 0.0
            metrics[f"hit_rate@{k}"] = 0.0
        metrics["mrr"] = 0.0
        return metrics

    recall_scores: dict[int, list[float]] = {k: [] for k in k_values}
    precision_scores: dict[int, list[float]] = {k: [] for k in k_values}
    ndcg_scores: dict[int, list[float]] = {k: [] for k in k_values}
    hitrate_scores: dict[int, list[float]] = {k: [] for k in k_values}
    mrr_scores: list[float] = []

    for channel_id in channels:
        relevant = gt_by_channel[channel_id]
        retrieved = pred_by_channel[channel_id]
        for k in k_values:
            recall_scores[k].append(recall_at_k(retrieved, relevant, k))
            precision_scores[k].append(precision_at_k(retrieved, relevant, k))
            ndcg_scores[k].append(ndcg_at_k(retrieved, relevant, k))
            hitrate_scores[k].append(hit_rate_at_k(retrieved, relevant, k))
        mrr_scores.append(mean_reciprocal_rank(retrieved, relevant))

    metrics = {}
    for k in k_values:
        metrics[f"recall@{k}"] = float(np.mean(recall_scores[k]))
        metrics[f"precision@{k}"] = float(np.mean(precision_scores[k]))
        metrics[f"ndcg@{k}"] = float(np.mean(ndcg_scores[k]))
        metrics[f"hit_rate@{k}"] = float(np.mean(hitrate_scores[k]))
    metrics["mrr"] = float(np.mean(mrr_scores))
    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality from prediction CSV.")
    parser.add_argument("--ground-truth", required=True, help="Path to ground-truth CSV.")
    parser.add_argument("--predictions", required=True, help="Path to predictions CSV.")
    parser.add_argument("--k-values", nargs="+", type=int, default=[5, 10, 50])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics = run_retrieval_evaluation(
        ground_truth_path=args.ground_truth,
        predictions_path=args.predictions,
        k_values=args.k_values,
    )
    print("Retrieval Evaluation Results")
    print("-" * 40)
    for name, value in metrics.items():
        print(f"  {name:>20s}: {value:.4f}")


if __name__ == "__main__":
    main()
