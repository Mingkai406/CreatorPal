"""Generate retrieval predictions from ground truth and evaluate Recall@K / MRR.

Usage (from project root):
    python eval/run_retrieval_eval.py \
        --ground-truth data/processed/ground_truth_pairs.csv \
        --output eval/predictions.csv \
        --k-values 5 10 50 \
        --sample 200
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.retrieval.bm25_search import BM25Retriever
from src.retrieval.faiss_search import FaissRetriever
from src.retrieval.hybrid_search import HybridRetriever
from eval.retrieval_eval import recall_at_k, mean_reciprocal_rank

logger = logging.getLogger(__name__)

DEFAULT_INDEX = Path("data/processed/subreddit_profiles.faiss")
DEFAULT_META = Path("data/processed/subreddit_profile_chunks.json")
DEFAULT_MODEL = "sentence-transformers/all-mpnet-base-v2"


def build_retriever(
    index_path: Path, meta_path: Path, model: str,
    alpha_kw: float = 0.15, alpha_sem: float = 0.85,
) -> HybridRetriever:
    """Build the hybrid retriever stack."""
    logger.info("Loading FAISS retriever ...")
    faiss_ret = FaissRetriever(
        index_path=index_path,
        metadata_path=meta_path,
        bi_encoder_model=model,
    )
    logger.info("Loading BM25 retriever ...")
    bm25_ret = BM25Retriever(metadata_path=meta_path)
    hybrid = HybridRetriever(
        faiss_retriever=faiss_ret,
        bm25_retriever=bm25_ret,
        alpha_keyword=alpha_kw,
        alpha_semantic=alpha_sem,
    )
    return hybrid


def generate_predictions(
    gt_df: pd.DataFrame,
    retriever: HybridRetriever,
    top_k: int = 50,
    sample_n: int | None = None,
) -> pd.DataFrame:
    """For each unique channel_id, run retrieval and produce a predictions dataframe.

    Since we don't have actual channel descriptions, we use the ground-truth
    subreddit names associated with each channel as a proxy query.  This tests
    whether the retriever can find *related* communities given a topic signal.
    """
    channel_groups = gt_df.groupby("channel_id")["subreddit"].apply(set).to_dict()
    channel_ids = list(channel_groups.keys())

    if sample_n and sample_n < len(channel_ids):
        import random
        random.seed(42)
        channel_ids = random.sample(channel_ids, sample_n)

    logger.info("Generating predictions for %d channels ...", len(channel_ids))
    rows: list[dict] = []

    for i, channel_id in enumerate(channel_ids):
        if (i + 1) % 50 == 0:
            logger.info("  progress: %d / %d", i + 1, len(channel_ids))

        gt_subs = channel_groups[channel_id]
        query = " ".join(gt_subs)

        results = retriever.retrieve(query, top_k=top_k)
        seen: set[str] = set()
        rank = 1
        for r in results:
            sub = r["subreddit"]
            if sub in seen:
                continue
            seen.add(sub)
            rows.append({
                "channel_id": channel_id,
                "subreddit": sub,
                "rank": rank,
            })
            rank += 1

    return pd.DataFrame(rows)


def evaluate(
    gt_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    k_values: list[int],
) -> dict[str, float]:
    """Compute Recall@K and MRR."""
    gt_by_channel: dict[str, set[str]] = {}
    for cid, group in gt_df.groupby("channel_id"):
        gt_by_channel[cid] = set(group["subreddit"])

    pred_by_channel: dict[str, list[str]] = {}
    for cid, group in pred_df.groupby("channel_id"):
        sorted_group = group.sort_values("rank")
        pred_by_channel[cid] = list(sorted_group["subreddit"])

    channels = set(gt_by_channel) & set(pred_by_channel)
    if not channels:
        return {f"recall@{k}": 0.0 for k in k_values} | {"mrr": 0.0}

    recall_scores: dict[int, list[float]] = {k: [] for k in k_values}
    mrr_scores: list[float] = []

    for cid in channels:
        relevant = gt_by_channel[cid]
        retrieved = pred_by_channel[cid]
        for k in k_values:
            recall_scores[k].append(recall_at_k(retrieved, relevant, k))
        mrr_scores.append(mean_reciprocal_rank(retrieved, relevant))

    import numpy as np
    metrics = {f"recall@{k}": float(np.mean(recall_scores[k])) for k in k_values}
    metrics["mrr"] = float(np.mean(mrr_scores))
    metrics["num_channels_evaluated"] = len(channels)
    return metrics


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Run end-to-end retrieval evaluation.")
    parser.add_argument("--ground-truth", type=Path, default=Path("data/processed/ground_truth_pairs.csv"))
    parser.add_argument("--output", type=Path, default=Path("eval/predictions.csv"))
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--meta", type=Path, default=DEFAULT_META)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--k-values", nargs="+", type=int, default=[5, 10, 50])
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--sample", type=int, default=None, help="Sample N channels for faster evaluation")
    args = parser.parse_args()

    gt_df = pd.read_csv(args.ground_truth)
    logger.info("Loaded %d ground-truth pairs across %d channels",
                len(gt_df), gt_df["channel_id"].nunique())

    retriever = build_retriever(args.index, args.meta, args.model)

    pred_df = generate_predictions(gt_df, retriever, top_k=args.top_k, sample_n=args.sample)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pred_df.to_csv(args.output, index=False)
    logger.info("Wrote %d predictions to %s", len(pred_df), args.output)

    metrics = evaluate(gt_df, pred_df, args.k_values)
    print("\n" + "=" * 40)
    print("Retrieval Evaluation Results")
    print("=" * 40)
    for name, value in metrics.items():
        if isinstance(value, float):
            print(f"  {name:>20s}: {value:.4f}")
        else:
            print(f"  {name:>20s}: {value}")
    print("=" * 40)


if __name__ == "__main__":
    main()
