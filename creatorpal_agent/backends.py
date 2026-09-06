import hashlib
import json
import re
from pathlib import Path

from .contracts import Evidence
from .state import digest


class CorpusBackend:
    """Small file-backed reference backend. Lexical matching is explicitly not hybrid RAG."""

    kind = "reference-lexical"

    def __init__(self, path=None):
        path = Path(path) if path else Path(__file__).parent / "fixtures" / "corpus.json"
        self.documents = [Evidence.model_validate(d) for d in json.loads(path.read_text())]
        if len({d.id for d in self.documents}) != len(self.documents):
            raise ValueError("Duplicate evidence IDs")
        self.fingerprint = digest([d.model_dump() for d in self.documents])

    def search(self, query, limit=3):
        terms = set(re.findall(r"[a-z]+", query.lower()))
        scored = []
        for doc in self.documents:
            if doc.kind != "profile":
                continue
            words = set(re.findall(r"[a-z]+", doc.text.lower()))
            score = len(terms & words)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [d.model_dump() for _, d in scored[:limit]]

    def rules(self, community):
        return [
            d.model_dump() for d in self.documents if d.community == community and d.kind == "rules"
        ]


class LegacyHybridBackend:
    """Adapter to the existing team's BM25 / FAISS / cross-encoder implementations."""

    kind = "legacy-hybrid-reranked"

    def __init__(self, settings, rules_path=None):
        from src.retrieval.bm25_search import BM25Retriever
        from src.retrieval.faiss_search import FaissRetriever
        from src.retrieval.hybrid_search import HybridRetriever
        from src.retrieval.reranker import CrossEncoderReranker

        self.retriever = HybridRetriever(
            faiss_retriever=FaissRetriever(
                index_path=settings.faiss_index_path,
                metadata_path=settings.faiss_metadata_path,
                bi_encoder_model=settings.embedding_model,
            ),
            bm25_retriever=BM25Retriever(metadata_path=settings.faiss_metadata_path),
            alpha_keyword=settings.hybrid_alpha_keyword,
            alpha_semantic=settings.hybrid_alpha_semantic,
        )
        self.reranker = CrossEncoderReranker(model_name=settings.reranker_model)
        self.rules_backend = CorpusBackend(rules_path) if rules_path else None
        self.fingerprint = digest(
            {
                "index": hashlib.sha256(Path(settings.faiss_index_path).read_bytes()).hexdigest(),
                "metadata": hashlib.sha256(
                    Path(settings.faiss_metadata_path).read_bytes()
                ).hexdigest(),
                "embedding": settings.embedding_model,
                "reranker": settings.reranker_model,
                "alpha": [settings.hybrid_alpha_keyword, settings.hybrid_alpha_semantic],
                "rules": self.rules_backend.fingerprint if self.rules_backend else None,
            }
        )

    def search(self, query, limit=3):
        candidates = self.retriever.retrieve(query, top_k=50)
        ranked = self.reranker.rerank(query=query, candidates=candidates, top_k=50)
        results, seen = [], set()
        for row in ranked:
            community = row["subreddit"]
            if community in seen:
                continue
            seen.add(community)
            results.append(
                Evidence(
                    id="profile-" + digest([community, row["chunk_text"]])[:16],
                    community=community,
                    text=row["chunk_text"][:6000],
                    source_url=f"https://www.reddit.com/r/{community}/",
                    collected_at="unknown; legacy corpus snapshot",
                    metrics={"rerank_score": float(row["rerank_score"])},
                ).model_dump()
            )
            if len(results) == limit:
                break
        return results

    def rules(self, community):
        return self.rules_backend.rules(community) if self.rules_backend else []
