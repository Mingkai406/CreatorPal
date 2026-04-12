"""Tests for the sentiment analysis module."""

from __future__ import annotations

import pytest

from src.sentiment.analyzer import SentimentAnalyzer
from src.sentiment import build_sentiment_analyzer


@pytest.fixture(scope="module")
def analyzer() -> SentimentAnalyzer:
    """Load the sentiment analyzer once for all tests in this module."""
    return SentimentAnalyzer()


class TestLabelToScore:
    """Tests for label_to_score mapping."""

    def test_positive_label(self, analyzer: SentimentAnalyzer) -> None:
        score = analyzer.label_to_score("positive", 0.95)
        assert score == pytest.approx(0.95)

    def test_negative_label(self, analyzer: SentimentAnalyzer) -> None:
        score = analyzer.label_to_score("negative", 0.88)
        assert score == pytest.approx(-0.88)

    def test_neutral_label(self, analyzer: SentimentAnalyzer) -> None:
        score = analyzer.label_to_score("neutral", 0.72)
        assert score == 0.0

    def test_case_insensitive(self, analyzer: SentimentAnalyzer) -> None:
        assert analyzer.label_to_score("Positive", 0.9) == pytest.approx(0.9)
        assert analyzer.label_to_score("NEGATIVE", 0.8) == pytest.approx(-0.8)


class TestAnalyzeComments:
    """Tests for analyze_comments."""

    def test_positive_comment(self, analyzer: SentimentAnalyzer) -> None:
        results = analyzer.analyze_comments(["This community is amazing and very helpful"])
        assert len(results) == 1
        r = results[0]
        assert r["text"] == "This community is amazing and very helpful"
        assert r["label"] in ("positive", "neutral", "negative")
        assert 0.0 <= r["confidence"] <= 1.0
        assert "score" in r
        # Expect positive sentiment for this text
        assert r["score"] > 0

    def test_negative_comment(self, analyzer: SentimentAnalyzer) -> None:
        results = analyzer.analyze_comments(["Terrible place, full of spam"])
        assert len(results) == 1
        r = results[0]
        assert r["text"] == "Terrible place, full of spam"
        assert r["score"] < 0

    def test_multiple_comments(self, analyzer: SentimentAnalyzer) -> None:
        comments = [
            "This community is amazing and very helpful",
            "Terrible place, full of spam",
            "Just a normal post about the weather",
        ]
        results = analyzer.analyze_comments(comments)
        assert len(results) == 3
        for r in results:
            assert set(r.keys()) == {"text", "label", "confidence", "score"}

    def test_empty_list(self, analyzer: SentimentAnalyzer) -> None:
        results = analyzer.analyze_comments([])
        assert results == []


class TestScoreSubreddits:
    """Tests for score_subreddits."""

    def test_single_subreddit(self, analyzer: SentimentAnalyzer) -> None:
        data = {
            "r/python": [
                "This community is amazing and very helpful",
                "Great answers and friendly people",
            ],
        }
        scores = analyzer.score_subreddits(data)
        assert "r/python" in scores
        assert scores["r/python"] > 0

    def test_multiple_subreddits(self, analyzer: SentimentAnalyzer) -> None:
        data = {
            "r/happy": ["This community is amazing and very helpful"],
            "r/angry": ["Terrible place, full of spam"],
        }
        scores = analyzer.score_subreddits(data)
        assert len(scores) == 2
        assert scores["r/happy"] > scores["r/angry"]

    def test_empty_comments(self, analyzer: SentimentAnalyzer) -> None:
        scores = analyzer.score_subreddits({"r/empty": []})
        assert scores["r/empty"] == 0.0


class TestBuildFactory:
    """Test the factory function."""

    def test_build_returns_analyzer(self) -> None:
        a = build_sentiment_analyzer()
        assert isinstance(a, SentimentAnalyzer)
