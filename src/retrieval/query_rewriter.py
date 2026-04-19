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
        rrf_k: int = 60,
        retrieval_base_query: str | None = None,
    ) -> list[dict]:
        """Run retrieval for all rewritten queries and fuse results with RRF.

        Uses Reciprocal Rank Fusion (RRF) to merge ranked lists from multiple
        query rewrites.  RRF only depends on rank position, so raw scores from
        different queries (which are not on a comparable scale) are never mixed.

        *user_query* is shown to the LLM for generating rewrites (may include
        the creator's goal).  *retrieval_base_query*, if provided, replaces the
        original query slot in BM25/FAISS retrieval so that meta-keywords like
        "grow subscribers" do not pollute keyword matching.

        *retriever* must expose a ``retrieve(query, top_k)`` method (works
        with :class:`HybridRetriever`, :class:`FaissRetriever`, or
        :class:`BM25Retriever`).
        """
        rewrites = self.rewrite(user_query)
        # Use content-only query as the retrieval anchor; keep LLM rewrites.
        base = retrieval_base_query if retrieval_base_query is not None else rewrites[0]
        queries = [base, *rewrites[1:]]

        # key -> best hit dict (metadata carrier)
        best_hit: dict[str, dict] = {}
        # key -> accumulated RRF score across all query lists
        rrf_scores: dict[str, float] = {}

        for q in queries:
            hits = retriever.retrieve(q, top_k=top_k)  # type: ignore[attr-defined]
            for rank, hit in enumerate(hits, start=1):
                key = f"{hit.get('subreddit', '')}|{hit.get('chunk_text', '')[:80]}"
                rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
                if key not in best_hit:
                    best_hit[key] = hit

        ranked_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)
        merged: list[dict] = []
        for key in ranked_keys[:top_k]:
            entry = dict(best_hit[key])
            entry["rrf_score"] = rrf_scores[key]
            merged.append(entry)

        logger.info(
            "RRF fusion over %d queries produced %d unique candidates",
            len(queries),
            len(merged),
        )
        return merged
