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
        """Score all candidates, sort descending, and return the top *top_k*."""
        if not candidates:
            return []

        scores = self.score_pairs(query, candidates)
        ranked_indices = np.argsort(scores)[::-1][:top_k]

        results: list[dict[str, Any]] = []
        for idx in ranked_indices:
            entry = dict(candidates[idx])
            entry["rerank_score"] = float(scores[idx])
            results.append(entry)
        return results
