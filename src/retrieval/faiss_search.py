"""FAISS Flat retrieval over subreddit profile embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


class FaissRetriever:
    """Run exact nearest-neighbor search on precomputed subreddit embeddings."""

    def __init__(self, index_path: Path, metadata_path: Path, bi_encoder_model: str) -> None:
        """Initialize embedding model and load FAISS index resources."""
        raise NotImplementedError("Implement FAISS retriever initialization.")

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a query string into embedding space."""
        raise NotImplementedError("Implement query encoding.")

    def retrieve(self, query: str, top_k: int = 50) -> list[dict[str, Any]]:
        """Retrieve top-K candidate subreddit profiles using FAISS Flat search."""
        raise NotImplementedError("Implement FAISS retrieval with metadata join.")

    def load_metadata(self) -> pd.DataFrame:
        """Load index metadata mapping vector ids to subreddit profiles."""
        raise NotImplementedError("Implement retrieval metadata loading.")
