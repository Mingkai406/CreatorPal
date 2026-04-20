"""LLM report generation conditioned on retrieval, PAL analytics, and sentiment."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a YouTube creator growth strategist specializing in Reddit community engagement. "
    "Given a channel profile, ranked Reddit communities, analytics, and sentiment data, "
    "write a concise, actionable strategy report for the creator. "
    "Structure the report with short sections using ## headings: "
    "## Overview, ## Top Communities, ## Engagement Strategy, ## Sentiment Insights. "
    "Be specific, practical, and grounded in the provided data. 250 words max."
)


class AugmentedGenerator:
    """Generate final audience strategy reports with retrieved evidence."""

    def __init__(self, client: OpenAI, model_name: str) -> None:
        self.client = client
        self.model = model_name
        logger.info("AugmentedGenerator initialised – model=%s", model_name)

    def build_prompt(
        self,
        channel_context: Mapping[str, Any],
        ranked_subreddits: Sequence[Mapping[str, Any]],
        pal_results: Mapping[str, Any],
        sentiment_scores: Mapping[str, float],
    ) -> str:
        """Build the prompt template for augmented report generation."""
        channel_name = channel_context.get("title", "Unknown Channel")
        channel_desc = channel_context.get("description", "")[:300]
        subscriber_count = channel_context.get("subscriber_count", 0)

        top_subs = "\n".join(
            f"{i + 1}. r/{s.get('subreddit', '')} "
            f"(score: {s.get('rerank_score', 0.0):.2f}) – "
            f"{str(s.get('chunk_text', ''))[:100]}"
            for i, s in enumerate(list(ranked_subreddits)[:5])
        )

        sentiment_lines = "\n".join(
            f"  {sub}: {score:+.2f}"
            for sub, score in list(sentiment_scores.items())[:5]
        )

        pal_summary = pal_results.get("summary", "")

        parts = [
            f"Channel: {channel_name}"
            + (f" ({subscriber_count:,} subscribers)" if subscriber_count else ""),
            f"Description: {channel_desc}" if channel_desc else "",
            f"\nTop ranked subreddits:\n{top_subs}" if top_subs else "",
            f"\nSentiment scores:\n{sentiment_lines}" if sentiment_lines else "",
            f"\nAnalytics: {pal_summary}" if pal_summary else "",
        ]
        return "\n".join(p for p in parts if p)

    def generate_strategy_report(
        self,
        channel_context: Mapping[str, Any],
        ranked_subreddits: Sequence[Mapping[str, Any]],
        pal_results: Mapping[str, Any],
        sentiment_scores: Mapping[str, float],
    ) -> str:
        """Generate the final CreatorPal strategy report."""
        prompt = self.build_prompt(
            channel_context, ranked_subreddits, pal_results, sentiment_scores
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=512,
        )

        report = response.choices[0].message.content or ""
        logger.info("AugmentedGenerator produced report (%d chars)", len(report))
        return report
