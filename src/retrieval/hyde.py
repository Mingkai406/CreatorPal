"""HyDE query rewriting for subreddit-profile retrieval."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert on Reddit communities and content strategy. "
    "Given a YouTube creator's goal and channel themes, write a hypothetical subreddit profile "
    "description that would be a PERFECT match for this creator's target audience. "
    "Write it as if it were an actual subreddit's self-description: describe the community's "
    "focus, typical content topics, audience interests, and engagement style. "
    "Be specific and concrete. 80-120 words. No subreddit name, just the profile text."
)


class HyDEQueryRewriter:
    """Generate hypothetical ideal subreddit descriptions for dense retrieval.

    HyDE (Hypothetical Document Embeddings) encodes a LLM-generated pseudo-document
    rather than the raw query. Because the generated text lives in the same semantic
    space as real subreddit profiles stored in the FAISS index, the nearest-neighbour
    search is more accurate than encoding a short keyword query directly.
    """

    def __init__(self, client: OpenAI, model_name: str) -> None:
        self.client = client
        self.model = model_name
        logger.info("HyDEQueryRewriter initialised – model=%s", model_name)

    def build_prompt(self, user_query: str, channel_themes: Sequence[str]) -> str:
        """Build the HyDE instruction prompt sent to the LLM."""
        themes_block = ""
        if channel_themes:
            themes_block = f"\nChannel themes: {', '.join(channel_themes)}"
        return (
            f"Creator's goal: {user_query}"
            f"{themes_block}\n\n"
            "Write a hypothetical subreddit profile description that would be "
            "the ideal community for this creator's audience."
        )

    def generate_hypothetical_subreddit_description(
        self,
        user_query: str,
        channel_themes: Sequence[str],
    ) -> str:
        """Rewrite user/channel intent into a retrieval-optimized pseudo-document."""
        prompt = self.build_prompt(user_query, channel_themes)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=200,
        )

        doc = (response.choices[0].message.content or "").strip()
        logger.info(
            "HyDE generated hypothetical document (%d chars) for: %s",
            len(doc),
            user_query,
        )
        return doc

    def retrieve(
        self,
        user_query: str,
        channel_themes: Sequence[str],
        faiss_retriever: Any,
        top_k: int = 50,
    ) -> list[dict[str, Any]]:
        """Generate a hypothetical document and run FAISS retrieval with it.

        *faiss_retriever* must expose an ``encode_query`` and a ``retrieve`` method,
        matching the :class:`FaissRetriever` interface.  Results are tagged with
        ``hyde_score`` (same value as ``score``) so callers can distinguish them.
        """
        hypo_doc = self.generate_hypothetical_subreddit_description(
            user_query, channel_themes
        )
        hits = faiss_retriever.retrieve(hypo_doc, top_k=top_k)
        for hit in hits:
            hit["hyde_score"] = hit.get("score", 0.0)
        return hits
