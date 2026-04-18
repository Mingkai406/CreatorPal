"""Evaluate retrieval quality on YouTube-to-subreddit ground-truth pairs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Compute Recall@K for one query.

    Args:
        retrieved: Ordered list of retrieved subreddit names.
        relevant: Set of ground-truth relevant subreddits.
        k: Cutoff rank.

    Returns:
        Fraction of relevant items found in the top-k results, capped at 1.0.
    """
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return min(hits / len(relevant), 1.0)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Compute Precision@K for one query.

    Args:
        retrieved: Ordered list of retrieved subreddit names.
        relevant: Set of ground-truth relevant subreddits.
        k: Cutoff rank.

    Returns:
        Fraction of top-k retrieved items that are in the relevant set.
    """
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / k


def mean_reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """Compute reciprocal rank for one query.

    Args:
        retrieved: Ordered list of retrieved subreddit names.
        relevant: Set of ground-truth relevant subreddits.

    Returns:
        1/rank of the first relevant item, or 0.0 if none found.
    """
    for i, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / i
    return 0.0


def run_retrieval_evaluation(
    ground_truth_path: str,
    predictions_path: str,
    k_values: list[int],
) -> dict[str, float]:
    """Run retrieval evaluation and return a metric dictionary.

    Args:
        ground_truth_path: Path to CSV with columns (channel_id, subreddit).
        predictions_path: Path to CSV with columns (channel_id, subreddit, rank).
        k_values: List of k cutoffs for Recall@K.

    Returns:
        Dict with average Recall@K and Precision@K for each k, plus average MRR.
    """
    gt_df = pd.read_csv(ground_truth_path)
    pred_df = pd.read_csv(predictions_path)

    # Build ground-truth lookup: channel_id -> set of relevant subreddits
    gt_by_channel: dict[str, set[str]] = {}
    for channel_id, group in gt_df.groupby("channel_id"):
        gt_by_channel[channel_id] = set(group["subreddit"])

    # Build predictions lookup: channel_id -> ordered list of subreddits
    pred_by_channel: dict[str, list[str]] = {}
    for channel_id, group in pred_df.groupby("channel_id"):
        sorted_group = group.sort_values("rank")
        pred_by_channel[channel_id] = list(sorted_group["subreddit"])

    # Evaluate only channels present in both ground truth and predictions
    channels = set(gt_by_channel) & set(pred_by_channel)
    if not channels:
        metrics: dict[str, float] = {f"recall@{k}": 0.0 for k in k_values}
        metrics.update({f"precision@{k}": 0.0 for k in k_values})
        metrics["mrr"] = 0.0
        return metrics

    recall_scores: dict[int, list[float]] = {k: [] for k in k_values}
    precision_scores: dict[int, list[float]] = {k: [] for k in k_values}
    mrr_scores: list[float] = []

    for channel_id in channels:
        relevant = gt_by_channel[channel_id]
        retrieved = pred_by_channel[channel_id]
        for k in k_values:
            recall_scores[k].append(recall_at_k(retrieved, relevant, k))
            precision_scores[k].append(precision_at_k(retrieved, relevant, k))
        mrr_scores.append(mean_reciprocal_rank(retrieved, relevant))

    metrics = {f"recall@{k}": float(np.mean(recall_scores[k])) for k in k_values}
    metrics.update(
        {f"precision@{k}": float(np.mean(precision_scores[k])) for k in k_values}
    )
    metrics["mrr"] = float(np.mean(mrr_scores))
    return metrics


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for retrieval evaluation."""
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality.")
    parser.add_argument(
        "--ground-truth", required=True, help="Path to ground-truth CSV."
    )
    parser.add_argument(
        "--predictions", required=True, help="Path to predictions CSV."
    )
    parser.add_argument(
        "--k-values",
        nargs="+",
        type=int,
        default=[10, 50],
        help="K cutoffs for Recall@K (default: 10 50).",
    )
    return parser.parse_args()


def main() -> None:
    """Run retrieval evaluation from the command line."""
    args = parse_args()
    metrics = run_retrieval_evaluation(
        ground_truth_path=args.ground_truth,
        predictions_path=args.predictions,
        k_values=args.k_values,
    )
    print("Retrieval Evaluation Results")
    print("-" * 30)
    for name, value in metrics.items():
        print(f"  {name}: {value:.4f}")


if __name__ == "__main__":
    main()
