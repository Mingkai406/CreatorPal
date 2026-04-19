"""Encode subreddit profile chunks and build a FAISS Flat index.

Uses semantic chunking: splits text into sentences, encodes them,
and groups consecutive sentences with high cosine similarity into
coherent chunks.  Chunks that exceed the encoder's max context are
split at sentence boundaries; tiny chunks are merged with neighbours.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

TEXT_COLUMN_CANDIDATES = [
    "chunk_text",
    "profile_text",
    "text",
    "content",
    "profile",
    "description",
]


def load_json_records(path: Path) -> list[dict[str, Any]]:
    """Load records from either JSON array/object or NDJSON."""
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            if "data" in parsed and isinstance(parsed["data"], list):
                return [item for item in parsed["data"] if isinstance(item, dict)]
            return [parsed]
    except json.JSONDecodeError:
        pass

    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"Expected a JSON object on line {line_no}.")
        records.append(item)
    return records


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation boundaries."""
    raw_parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [s.strip() for s in raw_parts if s.strip()]


def _token_count(text: str, tokenizer: Any) -> int:
    """Return the number of tokens for *text* according to *tokenizer*."""
    return len(tokenizer.encode(text, add_special_tokens=False))


def sentence_chunk_text(
    text: str,
    tokenizer: Any,
    max_chunk_tokens: int = 384,
    min_chunk_tokens: int = 20,
) -> list[str]:
    """Split *text* into chunks at sentence boundaries with a token limit.

    Greedily accumulates sentences until adding the next would exceed
    *max_chunk_tokens*, then starts a new chunk.  No encoder calls are
    needed, making this orders of magnitude faster than semantic chunking
    while preserving sentence integrity.
    """
    if not text or not text.strip():
        return []

    sentences = split_sentences(text)
    if not sentences:
        return []

    buf: list[str] = []
    buf_tokens = 0
    chunks: list[str] = []

    for sent in sentences:
        sent_tokens = _token_count(sent, tokenizer)
        if buf and buf_tokens + sent_tokens > max_chunk_tokens:
            chunks.append(" ".join(buf))
            buf = [sent]
            buf_tokens = sent_tokens
        else:
            buf.append(sent)
            buf_tokens += sent_tokens

    if buf:
        chunks.append(" ".join(buf))

    # Merge trailing tiny chunks into their predecessor
    merged: list[str] = []
    for chunk in chunks:
        if merged and _token_count(merged[-1], tokenizer) < min_chunk_tokens:
            merged[-1] = merged[-1] + " " + chunk
        else:
            merged.append(chunk)
    if len(merged) > 1 and _token_count(merged[-1], tokenizer) < min_chunk_tokens:
        merged[-2] = merged[-2] + " " + merged[-1]
        merged.pop()

    return merged


def infer_text_column(frame: pd.DataFrame) -> str:
    """Find the most likely text-bearing column in a profile table."""
    for column in TEXT_COLUMN_CANDIDATES:
        if column in frame.columns:
            return column
    raise ValueError(
        "Could not infer profile text column. Expected one of: "
        + ", ".join(TEXT_COLUMN_CANDIDATES)
    )


def build_chunk_metadata(
    profile_chunks_path: Path,
    tokenizer: Any,
    max_chunk_tokens: int = 384,
    min_chunk_tokens: int = 20,
) -> pd.DataFrame:
    """Build per-chunk metadata rows from subreddit profile records."""
    records = load_json_records(profile_chunks_path)
    frame = pd.DataFrame(records)
    if frame.empty:
        return pd.DataFrame(columns=["vector_id", "subreddit", "chunk_id", "chunk_text"])

    if "subreddit" not in frame.columns:
        raise ValueError("Input profile records must include a 'subreddit' column.")

    text_column = infer_text_column(frame)
    rows: list[dict[str, Any]] = []
    vector_id = 0

    for record in frame.to_dict(orient="records"):
        subreddit = str(record.get("subreddit", "")).strip()
        if not subreddit:
            continue
        raw_text = str(record.get(text_column, "") or "")
        if text_column == "chunk_text":
            chunks = [raw_text] if raw_text.strip() else []
        else:
            chunks = sentence_chunk_text(
                raw_text,
                tokenizer=tokenizer,
                max_chunk_tokens=max_chunk_tokens,
                min_chunk_tokens=min_chunk_tokens,
            )
        for chunk_id, chunk_text in enumerate(chunks):
            rows.append(
                {
                    "vector_id": vector_id,
                    "subreddit": subreddit,
                    "chunk_id": chunk_id,
                    "chunk_text": chunk_text,
                }
            )
            vector_id += 1

    return pd.DataFrame(rows)


def build_faiss_flat_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """Build an exact nearest-neighbor FAISS Flat index from embeddings."""
    if embeddings.ndim != 2:
        raise ValueError("Embeddings must be a 2D array.")
    if embeddings.shape[0] == 0:
        raise ValueError("Cannot build a FAISS index from zero embeddings.")

    normalized = np.asarray(embeddings, dtype=np.float32)
    faiss.normalize_L2(normalized)
    index = faiss.IndexFlatIP(normalized.shape[1])
    index.add(normalized)
    return index


def save_index(index: faiss.Index, output_path: Path) -> None:
    """Persist a FAISS index to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_path))


def save_metadata(metadata: pd.DataFrame, output_path: Path) -> None:
    """Persist vector-to-subreddit metadata alongside the FAISS index."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata.to_json(output_path, orient="records", indent=2, force_ascii=False)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for index building."""
    parser = argparse.ArgumentParser(
        description="Build a FAISS Flat index over semantically chunked subreddit profiles."
    )
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path("data/processed/subreddit_profiles.json"),
        help="Path to subreddit profile JSON/NDJSON (default: data/processed/subreddit_profiles.json).",
    )
    parser.add_argument(
        "--output-index",
        type=Path,
        default=Path("data/processed/subreddit_profiles.faiss"),
        help="Path to output FAISS index (default: data/processed/subreddit_profiles.faiss).",
    )
    parser.add_argument(
        "--output-metadata",
        type=Path,
        default=Path("data/processed/subreddit_profile_chunks.json"),
        help="Path to output chunk metadata JSON (default: data/processed/subreddit_profile_chunks.json).",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="sentence-transformers/all-mpnet-base-v2",
        help="SentenceTransformer model name (default: sentence-transformers/all-mpnet-base-v2).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Embedding batch size (default: 32).",
    )
    parser.add_argument(
        "--max-chunk-tokens",
        type=int,
        default=384,
        help="Maximum tokens per chunk (default: 384).",
    )
    parser.add_argument(
        "--min-chunk-tokens",
        type=int,
        default=20,
        help="Minimum tokens per chunk; smaller chunks are merged (default: 20).",
    )
    return parser.parse_args()


def main() -> None:
    """Run embedding and FAISS index build from the command line."""
    args = parse_args()
    if not args.profiles.exists():
        raise FileNotFoundError(f"Input profiles file not found: {args.profiles}")

    model = SentenceTransformer(args.model_name)
    metadata = build_chunk_metadata(
        profile_chunks_path=args.profiles,
        tokenizer=model.tokenizer,
        max_chunk_tokens=args.max_chunk_tokens,
        min_chunk_tokens=args.min_chunk_tokens,
    )
    if metadata.empty:
        raise ValueError("No profile chunks were produced from the provided input.")

    print(f"Sentence chunking produced {len(metadata)} chunks")

    embeddings = model.encode(
        metadata["chunk_text"].tolist(),
        batch_size=args.batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    index = build_faiss_flat_index(np.asarray(embeddings, dtype=np.float32))
    save_index(index, args.output_index)
    save_metadata(metadata, args.output_metadata)
    print(
        f"Wrote {index.ntotal} vectors to {args.output_index} "
        f"and metadata to {args.output_metadata}"
    )


if __name__ == "__main__":
    main()
