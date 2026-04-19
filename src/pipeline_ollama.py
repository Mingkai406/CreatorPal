"""End-to-end CreatorPal pipeline orchestration across ingest, retrieval, sentiment, and generation."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any

from openai import OpenAI

from src.config import Settings, load_settings

logger = logging.getLogger(__name__)


def _apply_runtime_stability_defaults() -> None:
    """Apply conservative runtime defaults to reduce native crashes on macOS.

    These can still be overridden by explicitly setting environment variables
    before process start.
    """
    defaults = {
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


_apply_runtime_stability_defaults()


def _try_init(label: str, factory):
    """Try to call *factory*; return None and log a warning on NotImplementedError."""
    try:
        return factory()
    except NotImplementedError:
        logger.warning("Skipping %s – not yet implemented", label)
        return None


class CreatorPalPipeline:
    """Coordinate all components required to produce subreddit recommendations and strategy text."""

    def __init__(self, settings: Settings) -> None:
        """Initialize pipeline component dependencies from settings."""
        self.settings = settings

        self._llm = OpenAI(
            base_url=settings.vllm_endpoint,
            api_key="not-needed",
        )

        # --- Components that may not be implemented yet ---
        from src.ingest.youtube import YouTubeIngestor
        self.youtube: YouTubeIngestor | None = _try_init(
            "YouTubeIngestor",
            lambda: YouTubeIngestor(
                api_key=settings.youtube_api_key,
                cache_dir=settings.youtube_cache_dir,
                cache_ttl_seconds=settings.youtube_cache_ttl_seconds,
            ),
        )

        from src.retrieval.hyde import HyDEQueryRewriter
        self.hyde: HyDEQueryRewriter | None = _try_init(
            "HyDEQueryRewriter",
            lambda: HyDEQueryRewriter(client=self._llm, model_name=settings.vllm_model),
        )

        from src.generator.augmented_gen import AugmentedGenerator
        self.generator: AugmentedGenerator | None = _try_init(
            "AugmentedGenerator",
            lambda: AugmentedGenerator(client=self._llm, model_name=settings.vllm_model),
        )

        # --- Components that are fully implemented ---
        from src.retrieval.faiss_search import FaissRetriever
        self.faiss_retriever = FaissRetriever(
            index_path=settings.faiss_index_path,
            metadata_path=settings.faiss_metadata_path,
            bi_encoder_model=settings.embedding_model,
        )

        from src.retrieval.bm25_search import BM25Retriever
        self.bm25_retriever = BM25Retriever(metadata_path=settings.faiss_metadata_path)

        from src.retrieval.hybrid_search import HybridRetriever
        self.hybrid_retriever = HybridRetriever(
            faiss_retriever=self.faiss_retriever,
            bm25_retriever=self.bm25_retriever,
            alpha_keyword=settings.hybrid_alpha_keyword,
            alpha_semantic=settings.hybrid_alpha_semantic,
        )

        from src.retrieval.query_rewriter import QueryRewriter
        self.query_rewriter = QueryRewriter(
            client=self._llm,
            model_name=settings.vllm_model,
        )

        from src.retrieval.reranker import CrossEncoderReranker
        self.reranker = CrossEncoderReranker(model_name=settings.reranker_model)

        from src.sentiment.analyzer import SentimentAnalyzer
        self.sentiment: SentimentAnalyzer | None = _try_init(
            "SentimentAnalyzer",
            lambda: SentimentAnalyzer(model_name=settings.sentiment_model),
        )

        logger.info("CreatorPalPipeline initialised")

    # ------------------------------------------------------------------
    # Query preparation
    # ------------------------------------------------------------------

    def prepare_retrieval_query(
        self,
        user_query: str | None,
        channel_context: dict[str, Any],
    ) -> tuple[str, str]:
        """Build retrieval queries from user goal and channel metadata.

        Returns (llm_query, content_query):
        - llm_query: includes the creator's goal; for LLM components.
        - content_query: channel content only; for BM25/FAISS retrieval.
        """
        content_sections: list[str] = []

        title = channel_context.get("title", "")
        if title:
            content_sections.append(f"Channel: {title}")

        description = channel_context.get("description", "")
        if description:
            content_sections.append(f"Description: {description[:300]}")

        videos = channel_context.get("videos", [])
        video_titles = [v["title"] for v in videos[:10] if v.get("title")]
        if video_titles:
            content_sections.append(f"Videos: {' | '.join(video_titles)}")

        content_query = "\n".join(content_sections) if content_sections else "general content recommendation"

        llm_sections = []
        if user_query:
            llm_sections.append(f"Goal: {user_query}")
        llm_sections.extend(content_sections)
        llm_query = "\n".join(llm_sections) if llm_sections else content_query

        return llm_query, content_query

    # ------------------------------------------------------------------
    # End-to-end execution
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_analytics(ranked_raw: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute simple analytics over ranked results (replaces PAL)."""
        if not ranked_raw:
            return {"summary": "", "metrics": {}}
        scores = [e.get("rerank_score", 0.0) for e in ranked_raw]
        subs = {e.get("subreddit", "") for e in ranked_raw}
        best = max(ranked_raw, key=lambda e: e.get("rerank_score", 0.0))
        result = {
            "avg_rerank_score": round(sum(scores) / len(scores), 2),
            "top_subreddit": best.get("subreddit", ""),
            "unique_subreddits": len(subs),
        }
        return {"summary": str(result), "metrics": {"result": result}}

    def run(self, channel_or_query: str, user_query: str | None = None) -> dict[str, Any]:
        """Execute the full CreatorPal pipeline.

        Returns a dict conforming to the frontend adapter contract (see
        ``app/helpers/adapter.py``).
        """
        import time
        from datetime import datetime, timezone

        t0 = time.monotonic()
        stages: list[str] = []

        # 1. YouTube ingestion
        channel_context: dict[str, Any] = {}
        if self.youtube is not None:
            try:
                channel_context = self.youtube.ingest_channel(
                    channel_or_query,
                    max_videos=self.settings.max_channel_videos,
                    max_comments_per_video=self.settings.max_video_comments,
                )
                stages.append("youtube_ingest")
            except Exception as exc:
                logger.warning("YouTube ingestion failed – skipping: %s", exc)

        # 2. Build retrieval queries from channel metadata
        llm_query, content_query = self.prepare_retrieval_query(
            user_query, channel_context
        )

        # 3. Query Rewriter + HyDE in parallel
        with ThreadPoolExecutor(max_workers=2) as pool:
            rewrite_future: Future[list[dict]] = pool.submit(
                self.query_rewriter.retrieve_with_rewrites,
                user_query=llm_query,
                retriever=self.hybrid_retriever,
                top_k=self.settings.retrieval_top_k,
                retrieval_base_query=content_query,
            )

            hyde_future: Future[list[dict[str, Any]]] | None = None
            if self.hyde is not None:
                hyde_future = pool.submit(
                    self.hyde.retrieve,
                    user_query=llm_query,
                    faiss_retriever=self.faiss_retriever,
                    top_k=self.settings.retrieval_top_k,
                )

        candidates = rewrite_future.result()
        stages.extend(["query_rewriting", "hybrid_retrieval"])

        if hyde_future is not None:
            try:
                hyde_hits = hyde_future.result()
                seen_keys: set[str] = {
                    f"{c.get('subreddit', '')}|{c.get('chunk_text', '')[:80]}"
                    for c in candidates
                }
                for hit in hyde_hits:
                    key = f"{hit.get('subreddit', '')}|{hit.get('chunk_text', '')[:80]}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        candidates.append(hit)
                stages.append("hyde_retrieval")
            except Exception as exc:
                logger.warning("HyDE retrieval failed – skipping: %s", exc)

        # 4. Cross-encoder reranking
        try:
            ranked_raw = self.reranker.rerank(
                query=llm_query,
                candidates=candidates,
                top_k=self.settings.rerank_top_k,
            )
            ranked_raw = [e for e in ranked_raw if e.get("rerank_score", 0.0) > -5.0]
            stages.append("reranking")
        except Exception as exc:
            logger.warning("Reranking failed – fallback to hybrid score ordering: %s", exc)
            ranked_raw = sorted(
                candidates,
                key=lambda item: float(
                    item.get("hybrid_score", item.get("score", 0.0))
                ),
                reverse=True,
            )[: self.settings.rerank_top_k]
            for entry in ranked_raw:
                entry["rerank_score"] = float(
                    entry.get("hybrid_score", entry.get("score", 0.0))
                )
            stages.append("reranking_fallback")

        # 5. Analytics (direct computation, no LLM)
        pal_results = self._compute_analytics(ranked_raw)
        stages.append("analytics")

        # 6. Sentiment + Report generation in parallel
        sentiment_scores: dict[str, float] = {}
        report = ""

        with ThreadPoolExecutor(max_workers=2) as pool:
            sentiment_future: Future[dict[str, float]] | None = None
            if self.sentiment is not None and ranked_raw:
                sub_comments: dict[str, list[str]] = {}
                for entry in ranked_raw:
                    sub = entry.get("subreddit", "unknown")
                    text = entry.get("chunk_text", "")
                    sub_comments.setdefault(sub, []).append(text)
                sentiment_future = pool.submit(
                    self.sentiment.score_subreddits, sub_comments
                )

            report_future: Future[str] | None = None
            if self.generator is not None:
                report_future = pool.submit(
                    self.generator.generate_strategy_report,
                    channel_context=channel_context,
                    ranked_subreddits=ranked_raw,
                    pal_results=pal_results,
                    sentiment_scores={},
                )

        if sentiment_future is not None:
            try:
                sentiment_scores = sentiment_future.result()
                stages.append("sentiment")
            except Exception as exc:
                logger.warning("Sentiment analysis failed: %s", exc)

        if report_future is not None:
            try:
                report = report_future.result()
                stages.append("generation")
            except Exception as exc:
                logger.warning("Report generation failed – skipping: %s", exc)

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Build frontend-compatible ranked_subreddits
        ranked_subreddits: list[dict[str, Any]] = []
        for i, entry in enumerate(ranked_raw, 1):
            sub = entry.get("subreddit", "unknown")
            ranked_subreddits.append({
                "rank": i,
                "subreddit": sub,
                "url": f"https://www.reddit.com/r/{sub}/",
                "retrieval_score": entry.get("hybrid_score") or entry.get("score", 0.0),
                "rerank_score": entry.get("rerank_score", 0.0),
                "reason": entry.get("chunk_text", "")[:120],
                "evidence": [entry.get("chunk_text", "")[:200]],
                "sentiment_score": sentiment_scores.get(sub, 0.0),
            })

        resolved_mode = "channel" if "youtube.com" in channel_or_query or "@" in channel_or_query else "query"

        logger.info("Pipeline finished in %dms – stages: %s", elapsed_ms, stages)
        return {
            "input": {
                "channel_or_query": channel_or_query,
                "user_query": user_query,
                "resolved_mode": resolved_mode,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "ranked_subreddits": ranked_subreddits,
            "strategy_report": report,
            "pal_results": pal_results,
            "sentiment_scores": {f"r/{sub}": score for sub, score in sentiment_scores.items()},
            "meta": {
                "retrieval_top_k": self.settings.retrieval_top_k,
                "rerank_top_k": self.settings.rerank_top_k,
                "latency_ms": elapsed_ms,
            },
        }


def build_pipeline(settings: Settings | None = None) -> CreatorPalPipeline:
    """Create a configured pipeline instance with optional explicit settings."""
    if settings is None:
        settings = load_settings()
    return CreatorPalPipeline(settings)
