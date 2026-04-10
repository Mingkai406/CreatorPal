"""HyDE query rewriting for subreddit-profile retrieval."""

from __future__ import annotations

from collections.abc import Sequence

from openai import OpenAI


class HyDEQueryRewriter:
    """Generate hypothetical ideal subreddit descriptions for dense retrieval."""

    def __init__(self, client: OpenAI, model_name: str) -> None:
        """Initialize the LLM client and model reference."""
        raise NotImplementedError("Implement HyDE rewriter initialization.")

    def generate_hypothetical_subreddit_description(
        self,
        user_query: str,
        channel_themes: Sequence[str],
    ) -> str:
        """Rewrite user/channel intent into a retrieval-optimized pseudo-document."""
        raise NotImplementedError("Implement HyDE generation workflow.")

    def build_prompt(self, user_query: str, channel_themes: Sequence[str]) -> str:
        """Build the HyDE instruction prompt sent to the LLM."""
        raise NotImplementedError("Implement HyDE prompt builder.")
