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
                    "reason": "Strong overlap with benchmark-focused creator content.",
                    "evidence": ["High fit on device-review intent and discussion norms."],
                    "sentiment_score": 0.72,
                },
                {
                    "rank": 2,
                    "subreddit": "r/buildapc",
                    "url": "",
                    "retrieval_score": 0.86,
                    "rerank_score": 0.89,
                    "reason": "Community often cites deep-dive review videos in discussions.",
                    "evidence": ["Frequent linking behavior aligns with long-form creator output."],
                    "sentiment_score": 0.63,
                },
                {
                    "rank": 3,
                    "subreddit": "gadgets",
                    "url": "https://www.reddit.com/r/gadgets/",
                    "retrieval_score": 0.77,
                    "rerank_score": 0.80,
                    "reason": "Broad consumer tech audience with high post engagement.",
                    "evidence": ["Strong overlap for launch news and quick highlights."],
                    "sentiment_score": 0.44,
                },
            ],
            "strategy_report": (
                "Audience fit is strongest in technical hardware communities.\n"
                "Start with r/hardware and r/buildapc, then expand to broader tech forums."
            ),
            "pal_results": {
                "summary": "Top recommendations indicate stable engagement potential.",
                "metrics": {"avg_rerank_score": 0.88, "top_subreddit": "r/hardware"},
            },
            "sentiment_scores": {
                "r/hardware": 0.72,
                "r/buildapc": 0.63,
                "r/gadgets": 0.44,
            },
            "meta": {
                "retrieval_top_k": 50,
                "rerank_top_k": 10,
                "latency_ms": int(self.runtime_delay_s * 1000),
            },
        }

