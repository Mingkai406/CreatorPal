"""Hybrid retrieval combining BM25 keyword search with FAISS dense similarity."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.retrieval.bm25_search import BM25Retriever
from src.retrieval.faiss_search import FaissRetriever

logger = logging.getLogger(__name__)

DEFAULT_ALPHA_KEYWORD = 0.15
DEFAULT_ALPHA_SEMANTIC = 0.85


def _min_max_normalize(scores: dict[int, float]) -> dict[int, float]:
    """Normalize score values to [0, 1] using min-max scaling."""
    if not scores:
        return {}
    vals = np.array(list(scores.values()), dtype=np.float32)
    lo, hi = vals.min(), vals.max()
    if hi - lo < 1e-9:
        return {k: 1.0 for k in scores}
    return {k: float((v - lo) / (hi - lo)) for k, v in scores.items()}


class HybridRetriever:
    """Fuse BM25 and FAISS results via weighted linear combination.

    Parameters
    ----------
    faiss_retriever:
        Dense similarity retriever (cosine via FAISS IndexFlatIP).
    bm25_retriever:
        Sparse keyword retriever (Okapi BM25).
    alpha_keyword:
        Weight for the BM25 component (default 0.15).
    alpha_semantic:
        Weight for the FAISS component (default 0.85).
    """

    def __init__(
        self,
        faiss_retriever: FaissRetriever,
        bm25_retriever: BM25Retriever,
        alpha_keyword: float = DEFAULT_ALPHA_KEYWORD,
        alpha_semantic: float = DEFAULT_ALPHA_SEMANTIC,
    ) -> None:
        if abs((alpha_keyword + alpha_semantic) - 1.0) > 1e-6:
            raise ValueError("alpha_keyword + alpha_semantic must equal 1.0")
        self.faiss = faiss_retriever
        self.bm25 = bm25_retriever
        self.alpha_kw = alpha_keyword
        self.alpha_sem = alpha_semantic
        logger.info(
            "HybridRetriever ready – alpha_keyword=%.2f, alpha_semantic=%.2f",
            self.alpha_kw, self.alpha_sem,
        )

    def retrieve(self, query: str, top_k: int = 50) -> list[dict[str, Any]]:
        """Run both retrievers, fuse scores, and return the top *top_k* results.

        Each retriever first fetches ``top_k * 2`` candidates to give the
        fusion step a wider pool.  Scores from each source are min-max
        normalised before the weighted combination.
        """
        pool_size = top_k * 2

        faiss_results = self.faiss.retrieve(query, top_k=pool_size)
        bm25_results = self.bm25.retrieve(query, top_k=pool_size)

        faiss_scores: dict[int, float] = {}
        faiss_docs: dict[int, dict[str, Any]] = {}
        for doc in faiss_results:
            fid = doc["faiss_id"]
            faiss_scores[fid] = doc["score"]
            faiss_docs[fid] = doc

        bm25_scores: dict[int, float] = {}
        bm25_docs: dict[int, dict[str, Any]] = {}
        for doc in bm25_results:
            bid = doc["bm25_id"]
            bm25_scores[bid] = doc["score"]
            bm25_docs[bid] = doc

        norm_faiss = _min_max_normalize(faiss_scores)
        norm_bm25 = _min_max_normalize(bm25_scores)

        all_ids = set(norm_faiss.keys()) | set(norm_bm25.keys())
        fused: list[tuple[int, float]] = []
        for doc_id in all_ids:
            sem = norm_faiss.get(doc_id, 0.0)
            kw = norm_bm25.get(doc_id, 0.0)
            fused.append((doc_id, self.alpha_sem * sem + self.alpha_kw * kw))

        fused.sort(key=lambda x: x[1], reverse=True)

        results: list[dict[str, Any]] = []
        for doc_id, score in fused[:top_k]:
            doc = faiss_docs.get(doc_id) or bm25_docs[doc_id]
            entry = {k: v for k, v in doc.items() if k not in ("score", "faiss_id", "bm25_id")}
            entry["hybrid_score"] = score
            entry["faiss_score"] = norm_faiss.get(doc_id, 0.0)
            entry["bm25_score"] = norm_bm25.get(doc_id, 0.0)
            results.append(entry)

        return results
