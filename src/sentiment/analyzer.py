"""Sentiment scoring over Reddit comment threads using a pretrained RoBERTa model."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from transformers import pipeline


class SentimentAnalyzer:
    """Compute per-subreddit sentiment scores from comment text."""

    def __init__(self, model_name: str = "cardiffnlp/twitter-roberta-base-sentiment-latest") -> None:
        """Initialize sentiment inference pipeline.

        Args:
            model_name: HuggingFace model identifier for sentiment classification.
        """
        self._pipeline = pipeline("sentiment-analysis", model=model_name)

    def label_to_score(self, label: str, confidence: float) -> float:
        """Map model output labels and confidence to a signed numeric score.

        Args:
            label: One of "positive", "neutral", or "negative".
            confidence: Model confidence in [0, 1].

        Returns:
            Signed score: positive -> +confidence, neutral -> 0.0, negative -> -confidence.
        """
        label_lower = label.lower()
        if label_lower == "positive":
            return confidence * 1.0
        elif label_lower == "negative":
            return confidence * -1.0
        return 0.0

    def analyze_comments(self, comments: Sequence[str]) -> list[dict[str, Any]]:
        """Return sentiment distribution metrics for a comment set.

        Args:
            comments: List of comment strings to analyze.

        Returns:
            List of dicts with keys: text, label, confidence, score.
        """
        results: list[dict[str, Any]] = []
        if not comments:
            return results
        predictions = self._pipeline(list(comments))
        for text, pred in zip(comments, predictions):
            label = pred["label"]
            confidence = pred["score"]
            score = self.label_to_score(label, confidence)
            results.append({
                "text": text,
                "label": label,
                "confidence": confidence,
                "score": score,
            })
        return results

    def score_subreddits(self, subreddit_comments: Mapping[str, Sequence[str]]) -> dict[str, float]:
        """Aggregate sentiment into a single score per subreddit.

        Args:
            subreddit_comments: Mapping of subreddit name to list of comment strings.

        Returns:
            Dict mapping each subreddit to its average sentiment score.
        """
        scores: dict[str, float] = {}
        for subreddit, comments in subreddit_comments.items():
            if not comments:
                scores[subreddit] = 0.0
                continue
            analyzed = self.analyze_comments(comments)
            avg = float(np.mean([c["score"] for c in analyzed]))
            scores[subreddit] = avg
        return scores
