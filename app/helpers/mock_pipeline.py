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
                    "evidence": [
                        "Community actively discusses GPU benchmarks in weekly threads",
                        "High keyword overlap: 'benchmark', 'review', 'comparison'",
                        "Positive sentiment toward YouTube video citations (+0.72)",
                    ],
                    "sentiment_score": 0.72,
                    "risk_level": "Low",
                    "posting_angle": "Share a benchmark breakdown as a discussion starter, not a promotion.",
                },
                {
                    "rank": 2,
                    "subreddit": "androidquestions",
                    "url": "https://www.reddit.com/r/androidquestions/",
                    "retrieval_score": 0.85,
                    "rerank_score": 0.88,
                    "reason": "Phone comparisons, frequently links reviews in help threads.",
                    "evidence": [
                        "High overlap with troubleshooting and buyer advice content",
                        "Review links upvoted when they answer specific questions",
                        "Warm community sentiment supports external resource sharing",
                    ],
                    "sentiment_score": 0.61,
                    "risk_level": "Low",
                    "posting_angle": "Answer a common phone-buying question with your comparison video as the reference.",
                },
                {
                    "rank": 3,
                    "subreddit": "buildapc",
                    "url": "https://www.reddit.com/r/buildapc/",
                    "retrieval_score": 0.79,
                    "rerank_score": 0.81,
                    "reason": "High component discussion, video citations in recommendation posts.",
                    "evidence": [
                        "Part-comparison posts frequently include review video references",
                        "Weekly 'What should I buy?' threads welcome curated video resources",
                        "Component overlap: CPU/GPU/RAM topics match your content",
                    ],
                    "sentiment_score": 0.55,
                    "risk_level": "Medium",
                    "posting_angle": "Contribute to a build-advice thread by linking your most relevant component review.",
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
                    "risk_level": "Medium",
                    "posting_angle": "Frame a launch-day take as news commentary rather than a channel promo.",
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
                    "risk_level": "Medium",
                    "posting_angle": "Post an ecosystem comparison that invites community opinion.",
                },
                {
                    "rank": 6,
                    "subreddit": "techsupport",
                    "url": "https://www.reddit.com/r/techsupport/",
                    "retrieval_score": 0.67,
                    "rerank_score": 0.69,
                    "reason": "Troubleshooting audience actively seeks step-by-step video guides.",
                    "evidence": ["Video solution links are frequently upvoted in help threads."],
                    "sentiment_score": 0.52,
                    "risk_level": "Low",
                    "posting_angle": "Answer a common support question and offer your tutorial as a reference.",
                },
                {
                    "rank": 7,
                    "subreddit": "pcmasterrace",
                    "url": "https://www.reddit.com/r/pcmasterrace/",
                    "retrieval_score": 0.63,
                    "rerank_score": 0.66,
                    "reason": "Enthusiast community with high benchmark and build-log engagement.",
                    "evidence": ["Showcase posts reward detailed spec comparisons with video walkthroughs."],
                    "sentiment_score": 0.68,
                    "risk_level": "Medium",
                    "posting_angle": "Share a rig showcase or benchmark that fits community build standards.",
                },
                {
                    "rank": 8,
                    "subreddit": "homelab",
                    "url": "https://www.reddit.com/r/homelab/",
                    "retrieval_score": 0.59,
                    "rerank_score": 0.61,
                    "reason": "DIY server and networking audience overlaps with deep-dive tech content.",
                    "evidence": ["Setup showcase threads regularly surface video tutorials."],
                    "sentiment_score": 0.57,
                    "risk_level": "Low",
                    "posting_angle": "Share a setup walkthrough as a detailed guide for the community.",
                },
                {
                    "rank": 9,
                    "subreddit": "photography",
                    "url": "https://www.reddit.com/r/photography/",
                    "retrieval_score": 0.55,
                    "rerank_score": 0.57,
                    "reason": "Camera and lens review content aligns with gear discussion threads.",
                    "evidence": ["Gear threads frequently link external review videos."],
                    "sentiment_score": 0.41,
                    "risk_level": "Medium",
                    "posting_angle": "Join a gear recommendation thread with a focused, comparison-driven take.",
                },
                {
                    "rank": 10,
                    "subreddit": "cordcutters",
                    "url": "https://www.reddit.com/r/cordcutters/",
                    "retrieval_score": 0.51,
                    "rerank_score": 0.53,
                    "reason": "Streaming device and antenna setup audience fits consumer electronics content.",
                    "evidence": ["Setup and comparison posts often include video links for clarity."],
                    "sentiment_score": 0.33,
                    "risk_level": "Medium",
                    "posting_angle": "Help someone choose a streaming device by referencing your comparison video.",
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
                "r/apple": 0.44,
                "r/techsupport": 0.52,
                "r/pcmasterrace": 0.68,
                "r/homelab": 0.57,
                "r/photography": 0.41,
                "r/cordcutters": 0.33,
            },
            "meta": {
                "retrieval_top_k": 50,
                "rerank_top_k": 10,
                "latency_ms": int(self.runtime_delay_s * 1000),
            },
        }
