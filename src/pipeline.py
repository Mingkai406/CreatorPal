"""End-to-end CreatorPal pipeline orchestration across ingest, retrieval, PAL, sentiment, and generation."""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from src.config import Settings, load_settings

logger = logging.getLogger(__name__)


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
            lambda: YouTubeIngestor(api_key=settings.youtube_api_key),
        )

        from src.retrieval.theme_extractor import ThemeExtractor
        self.theme_extractor: ThemeExtractor | None = _try_init(
            "ThemeExtractor",
            lambda: ThemeExtractor(client=self._llm, model_name=settings.vllm_model),
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

        from src.pal.executor import PALExecutor
        self.pal = PALExecutor(client=self._llm, model_name=settings.vllm_model)

        from src.sentiment.analyzer import SentimentAnalyzer
        self.sentiment: SentimentAnalyzer | None = _try_init(
            "SentimentAnalyzer",
            lambda: SentimentAnalyzer(model_name=settings.sentiment_model),
        )

        logger.info("CreatorPalPipeline initialised")

    # ------------------------------------------------------------------
    # Query preparation
    # ------------------------------------------------------------------

    def prepare_retrieval_query(self, user_query: str | None, channel_themes: list[str]) -> str:
        """Create the final retrieval query using user intent and extracted themes.

        If *user_query* is provided it is used as the base; channel themes are
        appended as keyword context to boost retrieval relevance.
        """
        parts: list[str] = []
        if user_query:
            parts.append(user_query)
        if channel_themes:
            parts.append("Topics: " + ", ".join(channel_themes))
        return " ".join(parts) if parts else "general content recommendation"

    # ------------------------------------------------------------------
    # End-to-end execution
    # ------------------------------------------------------------------

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

        # 2. Theme extraction
        channel_themes: list[str] = []
        if self.theme_extractor is not None and channel_context:
            try:
                channel_themes = self.theme_extractor.extract_themes(channel_context)
                stages.append("theme_extraction")
            except Exception as exc:
                logger.warning("Theme extraction failed – skipping: %s", exc)

        # 3. Build retrieval query
        retrieval_query = self.prepare_retrieval_query(
            user_query or channel_or_query, channel_themes
        )

        # 4. Query rewriting + hybrid retrieval
        candidates = self.query_rewriter.retrieve_with_rewrites(
            user_query=retrieval_query,
            retriever=self.hybrid_retriever,
            channel_themes=channel_themes or None,
            top_k=self.settings.retrieval_top_k,
        )
        stages.extend(["query_rewriting", "hybrid_retrieval"])

        # 4b. HyDE retrieval – merge FAISS hits from a hypothetical subreddit document
        if self.hyde is not None:
            try:
                hyde_hits = self.hyde.retrieve(
                    user_query=retrieval_query,
                    channel_themes=channel_themes,
                    faiss_retriever=self.faiss_retriever,
                    top_k=self.settings.retrieval_top_k,
                )
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
                logger.info("HyDE added %d new candidates", len(hyde_hits))
            except Exception as exc:
                logger.warning("HyDE retrieval failed – skipping: %s", exc)

        # 5. Cross-encoder reranking
        ranked_raw = self.reranker.rerank(
            query=retrieval_query,
            candidates=candidates,
            top_k=self.settings.rerank_top_k,
        )
        stages.append("reranking")

        # 6. PAL analytics
        pal_results: dict[str, Any] = {"summary": "", "metrics": {}}
        if ranked_raw:
            try:
                task = (
                    "Analyze the subreddit candidates and compute: "
                    "(a) average rerank_score, (b) subreddit with max score, "
                    "(c) number of unique subreddits."
                )
                import pandas as pd
                pal_df = pd.DataFrame(ranked_raw)
                code = self.pal.generate_program(task, {"columns": list(pal_df.columns)})
                exec_result = self.pal.execute_program(code, dataframe=pal_df)
                pal_results = {
                    "summary": str(exec_result.get("result", "")),
                    "metrics": exec_result if isinstance(exec_result, dict) else {},
                }
                stages.append("pal_analytics")
            except Exception as exc:
                logger.warning("PAL analytics failed: %s", exc)
                pal_results = {"summary": f"PAL error: {exc}", "metrics": {}}

        # 7. Sentiment analysis
        sentiment_scores: dict[str, float] = {}
        if self.sentiment is not None and ranked_raw:
            try:
                sub_comments: dict[str, list[str]] = {}
                for entry in ranked_raw:
                    sub = entry.get("subreddit", "unknown")
                    text = entry.get("chunk_text", "")
                    sub_comments.setdefault(sub, []).append(text)
                sentiment_scores = self.sentiment.score_subreddits(sub_comments)
                stages.append("sentiment")
            except Exception as exc:
                logger.warning("Sentiment analysis failed: %s", exc)

        # 8. Report generation
        report = ""
        if self.generator is not None:
            try:
                report = self.generator.generate_strategy_report(
                    channel_context=channel_context,
                    ranked_subreddits=ranked_raw,
                    pal_results=pal_results,
                    sentiment_scores=sentiment_scores,
                )
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
