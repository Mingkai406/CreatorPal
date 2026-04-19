"""LLM-based query rewriting for improved retrieval recall."""

from __future__ import annotations

import logging

from openai import OpenAI

logger = logging.getLogger(__name__)

REWRITE_SYSTEM_PROMPT = (
    "You are a search-query optimizer for a Reddit community discovery system. "
    "Given a user's original query, generate {n} diverse reformulations that "
    "will improve retrieval coverage. Each reformulation should emphasize "
    "different aspects: synonyms, related topics, or more specific sub-topics. "
    "Return one query per line, no numbering."
)


class QueryRewriter:
    """Rewrite user queries into multiple retrieval-optimized variants.

    Uses an LLM to produce diverse reformulations so that downstream
    retrievers (BM25 + FAISS) can capture a broader set of relevant
    documents before reranking narrows the list.
    """

    def __init__(self, client: OpenAI, model_name: str, num_rewrites: int = 3) -> None:
        self.client = client
        self.model = model_name
        self.num_rewrites = num_rewrites
        logger.info("QueryRewriter ready – model=%s, num_rewrites=%d", model_name, num_rewrites)

    def rewrite(self, user_query: str) -> list[str]:
        """Return a list of rewritten queries including the original.

        The original query is always the first element so that callers
        can treat ``rewrites[0]`` as the unchanged baseline.
        """
        user_message = (
            f"Original query: {user_query}\n\n"
            f"Generate {self.num_rewrites} diverse search query reformulations."
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": REWRITE_SYSTEM_PROMPT.format(n=self.num_rewrites),
                },
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=256,
        )

        raw = response.choices[0].message.content or ""
        rewrites = [line.strip() for line in raw.splitlines() if line.strip()]
        rewrites = rewrites[: self.num_rewrites]

        logger.info("QueryRewriter produced %d rewrites for: %s", len(rewrites), user_query)
        return [user_query, *rewrites]

    def retrieve_with_rewrites(
        self,
        user_query: str,
        retriever: object,
        top_k: int = 50,
    ) -> list[dict]:
        """Run retrieval for all rewritten queries and deduplicate results.

        *retriever* must expose a ``retrieve(query, top_k)`` method (works
        with :class:`HybridRetriever`, :class:`FaissRetriever`, or
        :class:`BM25Retriever`).
        """
        queries = self.rewrite(user_query)
        seen_keys: set[str] = set()
        merged: list[dict] = []

        for q in queries:
            hits = retriever.retrieve(q, top_k=top_k)  # type: ignore[attr-defined]
            for hit in hits:
                key = f"{hit.get('subreddit', '')}|{hit.get('chunk_text', '')[:80]}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    merged.append(hit)

        score_key = next(
            (k for k in ("hybrid_score", "score", "rerank_score") if merged and k in merged[0]),
            "score",
        )
        merged.sort(key=lambda d: d.get(score_key, 0.0), reverse=True)
        return merged[:top_k]
