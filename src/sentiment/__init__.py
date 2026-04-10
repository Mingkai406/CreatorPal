"""Sentiment analysis package for subreddit-level polarity scoring."""

from __future__ import annotations

from src.sentiment.analyzer import SentimentAnalyzer


def build_sentiment_analyzer() -> SentimentAnalyzer:
    """Construct the sentiment analyzer used by the pipeline."""
    raise NotImplementedError("Implement sentiment analyzer factory.")
