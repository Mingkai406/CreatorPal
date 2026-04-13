"""FAISS Flat retrieval over subreddit profile embeddings."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class FaissRetriever:
    """Run exact nearest-neighbor search on precomputed subreddit embeddings.

    Expects a FAISS IndexFlatIP (inner-product) built from L2-normalised
    embeddings so that IP == cosine similarity.  The accompanying metadata
    file (CSV or JSON-lines) must have one row per vector, where the
    DataFrame row index matches the FAISS vector id.

    Required metadata columns: ``subreddit``, ``chunk_text``.
    Optional columns (passed through): ``subscribers``, ``profile_text``, etc.
    """

    def __init__(self, index_path: Path, metadata_path: Path, bi_encoder_model: str) -> None:
        self.encoder = SentenceTransformer(bi_encoder_model)
        self.index: faiss.IndexFlatIP = faiss.read_index(str(index_path))
        self.metadata: pd.DataFrame = self._load_metadata(metadata_path)

        if len(self.metadata) != self.index.ntotal:
            raise ValueError(
                f"Metadata rows ({len(self.metadata)}) != FAISS vectors ({self.index.ntotal})"
            )
        logger.info(
            "FaissRetriever ready – %d vectors, dim=%d", self.index.ntotal, self.index.d
        )

    def encode_query(self, query: str) -> np.ndarray:
        """Encode *query* and L2-normalise for cosine-similarity search."""
        vec = self.encoder.encode(query, convert_to_numpy=True).astype(np.float32)
        faiss.normalize_L2(vec.reshape(1, -1))
        return vec

    def retrieve(self, query: str, top_k: int = 50) -> list[dict[str, Any]]:
        """Return the *top_k* most similar subreddit chunks with scores."""
        vec = self.encode_query(query).reshape(1, -1)
        scores, ids = self.index.search(vec, top_k)

        results: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            row = self.metadata.iloc[idx]
            results.append({
                "faiss_id": int(idx),
                "score": float(score),
                "subreddit": row["subreddit"],
                "chunk_text": row["chunk_text"],
                **{c: row[c] for c in row.index if c not in ("subreddit", "chunk_text")},
            })
        return results

    # ------------------------------------------------------------------
    # Metadata loading helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_metadata(path: Path) -> pd.DataFrame:
        """Load metadata from CSV, JSON-lines, or Parquet."""
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix in (".json", ".jsonl", ".ndjson"):
            try:
                df = pd.read_json(path, lines=True)
            except ValueError:
                df = pd.read_json(path)
        elif suffix == ".parquet":
            df = pd.read_parquet(path)
        else:
            raise ValueError(f"Unsupported metadata format: {suffix}")

        missing = {"subreddit", "chunk_text"} - set(df.columns)
        if missing:
            raise ValueError(f"Metadata is missing required columns: {missing}")

        return df.reset_index(drop=True)

    def load_metadata(self) -> pd.DataFrame:
        """Return a copy of the loaded metadata DataFrame."""
        return self.metadata.copy()
