"""Encode subreddit profile chunks and build a FAISS Flat index."""

from __future__ import annotations

import argparse
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


def encode_profiles(profile_chunks_path: Path, model_name: str = "sentence-transformers/all-mpnet-base-v2") -> np.ndarray:
    """Encode profile chunks with a bi-encoder model."""
    raise NotImplementedError("Implement profile chunk encoding.")


def build_faiss_flat_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """Build an exact nearest-neighbor FAISS Flat index from embeddings."""
    raise NotImplementedError("Implement FAISS Flat index construction.")


def save_index(index: faiss.Index, output_path: Path) -> None:
    """Persist a FAISS index to disk."""
    raise NotImplementedError("Implement FAISS index serialization.")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for index building."""
    raise NotImplementedError("Implement CLI argument parsing for build_faiss_index.py.")


def main() -> None:
    """Run embedding and FAISS index build from the command line."""
    raise NotImplementedError("Implement main entrypoint for FAISS index build.")


if __name__ == "__main__":
    main()
