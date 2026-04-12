"""Retrieval package with theme extraction, HyDE, FAISS search, and reranking."""

from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from src.config import Settings
from src.retrieval.faiss_search import FaissRetriever
from src.retrieval.hyde import HyDEQueryRewriter
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.theme_extractor import ThemeExtractor


def build_retrieval_stack(
    settings: Settings,
    llm_client: OpenAI,
) -> tuple[ThemeExtractor, HyDEQueryRewriter, FaissRetriever, CrossEncoderReranker]:
    """Construct retrieval components in their pipeline execution order.

    *ThemeExtractor* and *HyDEQueryRewriter* depend on an LLM and are
    still skeleton — they will raise ``NotImplementedError`` until
    implemented.  *FaissRetriever* and *CrossEncoderReranker* are fully
    functional once the FAISS index and metadata files exist on disk.
    """
    theme_extractor = ThemeExtractor(llm_client, settings.vllm_model)
    hyde_rewriter = HyDEQueryRewriter(llm_client, settings.vllm_model)
    faiss_retriever = FaissRetriever(
        index_path=settings.faiss_index_path,
        metadata_path=settings.faiss_metadata_path,
        bi_encoder_model=settings.embedding_model,
    )
    reranker = CrossEncoderReranker(model_name=settings.reranker_model)
    return theme_extractor, hyde_rewriter, faiss_retriever, reranker
