"""Retrieval package with hybrid search (BM25 + FAISS), query rewriting, and reranking."""

from __future__ import annotations

from openai import OpenAI

from src.config import Settings
from src.retrieval.bm25_search import BM25Retriever
from src.retrieval.faiss_search import FaissRetriever
from src.retrieval.hybrid_search import HybridRetriever
from src.retrieval.hyde import HyDEQueryRewriter
from src.retrieval.query_rewriter import QueryRewriter
from src.retrieval.reranker import CrossEncoderReranker


def build_retrieval_stack(
    settings: Settings,
    llm_client: OpenAI,
) -> tuple[
    HyDEQueryRewriter,
    FaissRetriever,
    BM25Retriever,
    HybridRetriever,
    QueryRewriter,
    CrossEncoderReranker,
]:
    """Construct retrieval components in their pipeline execution order.

    The retrieval pipeline uses:

    1. **QueryRewriter** – LLM-based multi-query expansion.
    2. **HybridRetriever** – fused BM25 (15%) + FAISS dense (85%) scoring.
    3. **CrossEncoderReranker** – precision reranking on the fused candidate set.
    """
    hyde_rewriter = HyDEQueryRewriter(llm_client, settings.vllm_model)

    faiss_retriever = FaissRetriever(
        index_path=settings.faiss_index_path,
        metadata_path=settings.faiss_metadata_path,
        bi_encoder_model=settings.embedding_model,
    )
    bm25_retriever = BM25Retriever(metadata_path=settings.faiss_metadata_path)

    hybrid_retriever = HybridRetriever(
        faiss_retriever=faiss_retriever,
        bm25_retriever=bm25_retriever,
        alpha_keyword=settings.hybrid_alpha_keyword,
        alpha_semantic=settings.hybrid_alpha_semantic,
    )

    query_rewriter = QueryRewriter(
        client=llm_client,
        model_name=settings.vllm_model,
    )

    reranker = CrossEncoderReranker(model_name=settings.reranker_model)

    return (
        hyde_rewriter,
        faiss_retriever,
        bm25_retriever,
        hybrid_retriever,
        query_rewriter,
        reranker,
    )
