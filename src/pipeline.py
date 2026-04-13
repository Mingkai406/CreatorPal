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
        """Execute the full CreatorPal pipeline and return ranked subreddits plus report.

        Steps (each stage is skipped gracefully if its component is ``None``):
        1. **Ingest** – fetch YouTube channel info (if *channel_or_query* is a URL/ID).
        2. **Theme extraction** – derive channel themes from ingested context.
        3. **Query preparation** – build retrieval query from user intent + themes.
        4. **Query rewriting** – expand into multiple diverse queries.
        5. **Hybrid retrieval** – BM25 + FAISS fusion.
        6. **Reranking** – cross-encoder precision pass.
        7. **PAL analytics** – programmatic analysis of top candidates.
        8. **Sentiment** – community-sentiment scoring for top subreddits.
        9. **Generation** – LLM report summarising recommendations.
        """
        result: dict[str, Any] = {"stages_run": []}

        # 1. YouTube ingestion
        channel_context: dict[str, Any] = {}
        if self.youtube is not None:
            try:
                channel_context = self.youtube.ingest_channel(
                    channel_or_query,
                    max_videos=self.settings.max_channel_videos,
                    max_comments_per_video=self.settings.max_video_comments,
                )
                result["stages_run"].append("youtube_ingest")
            except NotImplementedError:
                logger.warning("YouTubeIngestor.ingest_channel not implemented – skipping")
        result["channel_context"] = channel_context

        # 2. Theme extraction
        channel_themes: list[str] = []
        if self.theme_extractor is not None and channel_context:
            try:
                channel_themes = self.theme_extractor.extract_themes(channel_context)
                result["stages_run"].append("theme_extraction")
            except NotImplementedError:
                logger.warning("ThemeExtractor.extract_themes not implemented – skipping")
        result["channel_themes"] = channel_themes

        # 3. Build retrieval query
        retrieval_query = self.prepare_retrieval_query(
            user_query or channel_or_query, channel_themes
        )
        result["retrieval_query"] = retrieval_query

        # 4. Query rewriting + hybrid retrieval (combined via retrieve_with_rewrites)
        candidates = self.query_rewriter.retrieve_with_rewrites(
            user_query=retrieval_query,
            retriever=self.hybrid_retriever,
            channel_themes=channel_themes or None,
            top_k=self.settings.retrieval_top_k,
        )
        result["stages_run"].append("query_rewriting")
        result["stages_run"].append("hybrid_retrieval")
        result["retrieval_candidates"] = len(candidates)

        # 5. Cross-encoder reranking
        ranked = self.reranker.rerank(
            query=retrieval_query,
            candidates=candidates,
            top_k=self.settings.rerank_top_k,
        )
        result["stages_run"].append("reranking")
        result["ranked_subreddits"] = ranked

        # 6. PAL analytics
        pal_results: dict[str, Any] = {}
        if ranked:
            try:
                task = (
                    "Analyze the subreddit candidates and compute: "
                    "(a) average rerank_score, (b) subreddit with max score, "
                    "(c) number of unique subreddits."
                )
                import pandas as pd
                pal_df = pd.DataFrame(ranked)
                code = self.pal.generate_program(task, {"columns": list(pal_df.columns)})
                pal_results = self.pal.execute_program(code, dataframe=pal_df)
                result["stages_run"].append("pal_analytics")
            except Exception as exc:
                logger.warning("PAL analytics failed: %s", exc)
                pal_results = {"error": str(exc)}
        result["pal_results"] = pal_results

        # 7. Sentiment analysis (on chunk_text of top subreddits as proxy)
        sentiment_scores: dict[str, float] = {}
        if self.sentiment is not None and ranked:
            try:
                sub_comments: dict[str, list[str]] = {}
                for entry in ranked:
                    sub = entry.get("subreddit", "unknown")
                    text = entry.get("chunk_text", "")
                    sub_comments.setdefault(sub, []).append(text)
                sentiment_scores = self.sentiment.score_subreddits(sub_comments)
                result["stages_run"].append("sentiment")
            except Exception as exc:
                logger.warning("Sentiment analysis failed: %s", exc)
        result["sentiment_scores"] = sentiment_scores

        # 8. Report generation
        report = ""
        if self.generator is not None:
            try:
                report = self.generator.generate_strategy_report(
                    channel_context=channel_context,
                    ranked_subreddits=ranked,
                    pal_results=pal_results,
                    sentiment_scores=sentiment_scores,
                )
                result["stages_run"].append("generation")
            except NotImplementedError:
                logger.warning("AugmentedGenerator not implemented – skipping report")
        result["report"] = report

        logger.info("Pipeline finished – stages: %s", result["stages_run"])
        return result


def build_pipeline(settings: Settings | None = None) -> CreatorPalPipeline:
    """Create a configured pipeline instance with optional explicit settings."""
    if settings is None:
        settings = load_settings()
    return CreatorPalPipeline(settings)
