"""Mock pipeline implementation for offline Streamlit frontend verification."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any


class MockPipeline:
    """Return deterministic, contract-compliant mock data for UI development."""

    def __init__(self, runtime_delay_s: float = 0.7) -> None:
        self.runtime_delay_s = runtime_delay_s

    def run(self, channel_or_query: str, user_query: str | None = None) -> dict[str, Any]:
        time.sleep(self.runtime_delay_s)
        resolved_mode = "channel" if "youtube.com" in channel_or_query or "@" in channel_or_query else "query"
        return {
            "input": {
                "channel_or_query": channel_or_query,
                "user_query": user_query,
                "resolved_mode": resolved_mode,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "ranked_subreddits": [
                {
                    "rank": 1,
                    "subreddit": "hardware",
                    "url": "https://www.reddit.com/r/hardware/",
                    "retrieval_score": 0.91,
                    "rerank_score": 0.94,
                    "reason": "GPU/CPU benchmark overlap, shares YT reviews in weekly threads.",
                    "evidence": ["Hardware benchmark threads show strong review-link affinity."],
                    "sentiment_score": 0.72,
                },
                {
                    "rank": 2,
                    "subreddit": "androidquestions",
                    "url": "https://www.reddit.com/r/androidquestions/",
                    "retrieval_score": 0.85,
                    "rerank_score": 0.88,
                    "reason": "Phone comparisons, frequently links reviews in help threads.",
                    "evidence": ["High overlap with troubleshooting and buyer advice content."],
                    "sentiment_score": 0.61,
                },
                {
                    "rank": 3,
                    "subreddit": "buildapc",
                    "url": "",
                    "retrieval_score": 0.79,
                    "rerank_score": 0.81,
                    "reason": "High component discussion, video citations in recommendation posts.",
                    "evidence": ["Part-comparison posts frequently include review references."],
                    "sentiment_score": 0.55,
                },
                {
                    "rank": 4,
                    "subreddit": "gadgets",
                    "url": "https://www.reddit.com/r/gadgets/",
                    "retrieval_score": 0.73,
                    "rerank_score": 0.76,
                    "reason": "Broad tech news, active link sharing for launch coverage.",
                    "evidence": ["Launch and rumor threads reward concise video context."],
                    "sentiment_score": 0.38,
                },
                {
                    "rank": 5,
                    "subreddit": "apple",
                    "url": "https://www.reddit.com/r/apple/",
                    "retrieval_score": 0.70,
                    "rerank_score": 0.72,
                    "reason": "iOS/Mac product reviews with strong brand-focused audience fit.",
                    "evidence": ["Strong engagement around ecosystem comparison content."],
                    "sentiment_score": 0.44,
                },
            ],
            "strategy_report": (
                "## Audience expansion opportunity\n\n"
                "Your channel has strong fit with hardware-focused subreddits. "
                "r/hardware scores highest due to its culture of sharing benchmark videos in weekly discussion threads.\n\n"
                "## Recommended action\n\n"
                "Prioritize r/hardware and r/buildapc for initial outreach. "
                "Engage in component comparison threads where video links are contextually appropriate."
            ),
            "pal_results": {
                "summary": "Top recommendations indicate stable engagement potential.",
                "metrics": {"avg_rerank_score": 0.88, "top_subreddit": "r/hardware"},
            },
            "sentiment_scores": {
                "r/hardware": 0.72,
                "r/androidquestions": 0.61,
                "r/buildapc": 0.55,
                "r/gadgets": 0.44,
            },
            "meta": {
                "retrieval_top_k": 50,
                "rerank_top_k": 10,
                "latency_ms": int(self.runtime_delay_s * 1000),
            },
        }
