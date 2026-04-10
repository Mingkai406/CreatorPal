"""Retrieval package with theme extraction, HyDE, FAISS search, and reranking."""

from __future__ import annotations

from src.retrieval.faiss_search import FaissRetriever
from src.retrieval.hyde import HyDEQueryRewriter
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.theme_extractor import ThemeExtractor


def build_retrieval_stack() -> tuple[ThemeExtractor, HyDEQueryRewriter, FaissRetriever, CrossEncoderReranker]:
    """Construct retrieval components in their pipeline execution order."""
    raise NotImplementedError("Implement retrieval stack factory.")
