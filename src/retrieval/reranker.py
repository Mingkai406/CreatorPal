"""Cross-encoder reranking for subreddit retrieval candidates."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Rerank dense-retrieval candidates with a cross-encoder model.

    Each candidate dict must contain a ``chunk_text`` key whose value is
    the text passage to compare against the query.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model = CrossEncoder(model_name)
        logger.info("CrossEncoderReranker ready – model=%s", model_name)

    def score_pairs(self, query: str, candidates: Sequence[Mapping[str, Any]]) -> np.ndarray:
        """Return an array of relevance scores, one per candidate."""
        if not candidates:
            return np.array([], dtype=np.float32)
        pairs = [(query, c["chunk_text"]) for c in candidates]
        scores = self.model.predict(pairs, convert_to_numpy=True)
        return np.asarray(scores, dtype=np.float32)

    def rerank(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Score all candidates, deduplicate by subreddit, return top *top_k*.

        All (query, chunk) pairs are scored first.  For each subreddit only the
        highest-scoring chunk is kept, so the final list contains at most one
        entry per subreddit.  This prevents a single highly-indexed subreddit
        from occupying multiple slots in the output.
        """
        if not candidates:
            return []

        scores = self.score_pairs(query, candidates)

        # Per-subreddit: keep only the best-scoring chunk index
        best: dict[str, tuple[int, float]] = {}
        for idx, score in enumerate(scores.tolist()):
            sub = candidates[idx].get("subreddit", "")
            if sub not in best or score > best[sub][1]:
                best[sub] = (idx, score)

        sorted_best = sorted(best.values(), key=lambda x: x[1], reverse=True)[:top_k]

        results: list[dict[str, Any]] = []
        for idx, score in sorted_best:
            entry = dict(candidates[idx])
            entry["rerank_score"] = score
            results.append(entry)

        logger.info(
            "Reranker: %d candidates → %d unique subreddits → top %d",
            len(candidates),
            len(best),
            len(results),
        )
        return results
