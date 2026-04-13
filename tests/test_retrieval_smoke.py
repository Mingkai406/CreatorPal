"""Smoke test for the retrieval stack using a small synthetic dataset."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.bm25_search import BM25Retriever
from src.retrieval.faiss_search import FaissRetriever
from src.retrieval.hybrid_search import HybridRetriever

ENCODER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

FAKE_DOCS = [
    {"subreddit": "gaming", "chunk_text": "Video games discussion, PC gaming, console gaming reviews and esports tournaments"},
    {"subreddit": "cooking", "chunk_text": "Recipes, meal prep, cooking tips, kitchen equipment and food photography"},
    {"subreddit": "python", "chunk_text": "Python programming language, coding tutorials, debugging help and open source projects"},
    {"subreddit": "fitness", "chunk_text": "Workout routines, gym tips, weight training, cardio exercises and nutrition advice"},
    {"subreddit": "music", "chunk_text": "Music production, guitar lessons, band recommendations, vinyl collecting and concerts"},
    {"subreddit": "travel", "chunk_text": "Budget travel guides, backpacking tips, flight deals and hotel reviews worldwide"},
    {"subreddit": "science", "chunk_text": "Scientific discoveries, research papers, physics experiments and biology news"},
    {"subreddit": "movies", "chunk_text": "Film reviews, movie recommendations, cinema discussion, directors and actors"},
    {"subreddit": "learnprogramming", "chunk_text": "Beginner coding help, programming tutorials, software engineering career advice"},
    {"subreddit": "photography", "chunk_text": "Camera gear reviews, photo editing tutorials, landscape and portrait photography tips"},
]


def build_test_data(tmpdir: Path) -> tuple[Path, Path]:
    """Create a temporary FAISS index and metadata file from FAKE_DOCS."""
    metadata_path = tmpdir / "metadata.jsonl"
    index_path = tmpdir / "index.faiss"

    df = pd.DataFrame(FAKE_DOCS)
    df.to_json(metadata_path, orient="records", lines=True)

    encoder = SentenceTransformer(ENCODER_MODEL)
    embeddings = encoder.encode(
        [d["chunk_text"] for d in FAKE_DOCS], convert_to_numpy=True
    ).astype(np.float32)
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, str(index_path))

    return index_path, metadata_path


def test_bm25(metadata_path: Path) -> None:
    print("\n" + "=" * 60)
    print("TEST 1: BM25 Retriever")
    print("=" * 60)

    bm25 = BM25Retriever(metadata_path)
    query = "Python coding tutorials"
    results = bm25.retrieve(query, top_k=5)

    print(f"Query: '{query}'")
    print(f"Results ({len(results)}):")
    for i, r in enumerate(results, 1):
        print(f"  {i}. r/{r['subreddit']:20s}  score={r['score']:.4f}")

    assert results[0]["subreddit"] == "python", (
        f"Expected 'python' as top result, got '{results[0]['subreddit']}'"
    )
    print("PASS - 'python' is the top BM25 result")


def test_faiss(index_path: Path, metadata_path: Path) -> None:
    print("\n" + "=" * 60)
    print("TEST 2: FAISS Retriever")
    print("=" * 60)

    faiss_ret = FaissRetriever(index_path, metadata_path, ENCODER_MODEL)
    query = "I want to learn how to write code"
    results = faiss_ret.retrieve(query, top_k=5)

    print(f"Query: '{query}'")
    print(f"Results ({len(results)}):")
    for i, r in enumerate(results, 1):
        print(f"  {i}. r/{r['subreddit']:20s}  score={r['score']:.4f}")

    top_subs = {r["subreddit"] for r in results[:3]}
    assert "python" in top_subs or "learnprogramming" in top_subs, (
        f"Expected coding-related subreddit in top 3, got {top_subs}"
    )
    print("PASS - coding-related subreddit found in top 3")


def test_hybrid(index_path: Path, metadata_path: Path) -> None:
    print("\n" + "=" * 60)
    print("TEST 3: Hybrid Retriever (BM25 15% + FAISS 85%)")
    print("=" * 60)

    faiss_ret = FaissRetriever(index_path, metadata_path, ENCODER_MODEL)
    bm25_ret = BM25Retriever(metadata_path)
    hybrid = HybridRetriever(faiss_ret, bm25_ret, alpha_keyword=0.15, alpha_semantic=0.85)

    query = "Python programming tutorials"
    results = hybrid.retrieve(query, top_k=5)

    print(f"Query: '{query}'")
    print(f"Results ({len(results)}):")
    for i, r in enumerate(results, 1):
        print(f"  {i}. r/{r['subreddit']:20s}  hybrid={r['hybrid_score']:.4f}  "
              f"faiss={r['faiss_score']:.4f}  bm25={r['bm25_score']:.4f}")

    assert results[0]["subreddit"] in ("python", "learnprogramming"), (
        f"Expected coding subreddit as top hybrid result, got '{results[0]['subreddit']}'"
    )
    print("PASS - coding subreddit is the top hybrid result")


def test_hybrid_keyword_boost(index_path: Path, metadata_path: Path) -> None:
    print("\n" + "=" * 60)
    print("TEST 4: Hybrid vs pure FAISS — keyword boost check")
    print("=" * 60)

    faiss_ret = FaissRetriever(index_path, metadata_path, ENCODER_MODEL)
    bm25_ret = BM25Retriever(metadata_path)
    hybrid = HybridRetriever(faiss_ret, bm25_ret, alpha_keyword=0.15, alpha_semantic=0.85)

    query = "gym workout cardio fitness"
    faiss_results = faiss_ret.retrieve(query, top_k=5)
    hybrid_results = hybrid.retrieve(query, top_k=5)

    print(f"Query: '{query}'")
    print("\nFAISS-only top 3:")
    for i, r in enumerate(faiss_results[:3], 1):
        print(f"  {i}. r/{r['subreddit']:20s}  score={r['score']:.4f}")
    print("\nHybrid top 3:")
    for i, r in enumerate(hybrid_results[:3], 1):
        print(f"  {i}. r/{r['subreddit']:20s}  hybrid={r['hybrid_score']:.4f}  "
              f"faiss={r['faiss_score']:.4f}  bm25={r['bm25_score']:.4f}")

    assert hybrid_results[0]["subreddit"] == "fitness", (
        f"Expected 'fitness' as top result, got '{hybrid_results[0]['subreddit']}'"
    )
    print("PASS - 'fitness' boosted to top by keyword match")


def main() -> None:
    print("Building synthetic test data (encoding may take a moment)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        index_path, metadata_path = build_test_data(Path(tmpdir))
        print(f"Test data ready: {index_path}, {metadata_path}")

        test_bm25(metadata_path)
        test_faiss(index_path, metadata_path)
        test_hybrid(index_path, metadata_path)
        test_hybrid_keyword_boost(index_path, metadata_path)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
