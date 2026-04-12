"""BM25 keyword retrieval over subreddit profile chunks."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphanumeric characters."""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Retriever:
    """Keyword-based retrieval using Okapi BM25 over chunk_text.

    Shares the same metadata format as :class:`FaissRetriever` so both
    retrievers can operate on an identical document collection.
    """

    def __init__(self, metadata_path: Path) -> None:
        self.metadata: pd.DataFrame = self._load_metadata(metadata_path)
        corpus_tokens = [_tokenize(text) for text in self.metadata["chunk_text"]]
        self.bm25 = BM25Okapi(corpus_tokens)
        logger.info("BM25Retriever ready – %d documents indexed", len(self.metadata))

    def retrieve(self, query: str, top_k: int = 50) -> list[dict[str, Any]]:
        """Return the *top_k* chunks ranked by BM25 score."""
        query_tokens = _tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        ranked_indices = scores.argsort()[::-1][:top_k]
        results: list[dict[str, Any]] = []
        for idx in ranked_indices:
            if scores[idx] <= 0:
                break
            row = self.metadata.iloc[idx]
            results.append({
                "bm25_id": int(idx),
                "score": float(scores[idx]),
                "subreddit": row["subreddit"],
                "chunk_text": row["chunk_text"],
                **{c: row[c] for c in row.index if c not in ("subreddit", "chunk_text")},
            })
        return results

    @staticmethod
    def _load_metadata(path: Path) -> pd.DataFrame:
        """Load metadata from CSV, JSON-lines, or Parquet."""
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix in (".json", ".jsonl", ".ndjson"):
            df = pd.read_json(path, lines=True)
        elif suffix == ".parquet":
            df = pd.read_parquet(path)
        else:
            raise ValueError(f"Unsupported metadata format: {suffix}")

        missing = {"subreddit", "chunk_text"} - set(df.columns)
        if missing:
            raise ValueError(f"Metadata is missing required columns: {missing}")
        return df.reset_index(drop=True)
