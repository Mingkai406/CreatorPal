"""Encode subreddit profile chunks and build a FAISS Flat index."""

from __future__ import annotations

import argparse
import json
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


def chunk_text_with_tokenizer(
    text: str,
    tokenizer: Any,
    window_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Chunk text according to model token ids."""
    if not text or not text.strip():
        return []
    if window_tokens <= 0:
        raise ValueError("window_tokens must be > 0")
    if overlap_tokens < 0 or overlap_tokens >= window_tokens:
        raise ValueError("overlap_tokens must be >= 0 and < window_tokens")

    token_ids = tokenizer.encode(text, add_special_tokens=False)
    if not token_ids:
        return []

    step = window_tokens - overlap_tokens
    chunks: list[str] = []
    for start in range(0, len(token_ids), step):
        chunk_ids = token_ids[start : start + window_tokens]
        if not chunk_ids:
            continue
        chunk_text = tokenizer.decode(chunk_ids, skip_special_tokens=True).strip()
        if chunk_text:
            chunks.append(" ".join(chunk_text.split()))
        if start + window_tokens >= len(token_ids):
            break
    return chunks


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
    window_tokens: int,
    overlap_tokens: int,
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
        chunks = (
            [raw_text]
            if text_column == "chunk_text"
            else chunk_text_with_tokenizer(raw_text, tokenizer, window_tokens, overlap_tokens)
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


def encode_profiles(
    profile_chunks_path: Path,
    model_name: str = "sentence-transformers/all-mpnet-base-v2",
    batch_size: int = 32,
    window_tokens: int = 64,
    overlap_tokens: int = 16,
) -> np.ndarray:
    """Encode profile chunks with a bi-encoder model."""
    model = SentenceTransformer(model_name)
    metadata = build_chunk_metadata(
        profile_chunks_path=profile_chunks_path,
        tokenizer=model.tokenizer,
        window_tokens=window_tokens,
        overlap_tokens=overlap_tokens,
    )
    if metadata.empty:
        return np.empty((0, model.get_sentence_embedding_dimension()), dtype=np.float32)

    embeddings = model.encode(
        metadata["chunk_text"].tolist(),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return np.asarray(embeddings, dtype=np.float32)


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
    parser = argparse.ArgumentParser(description="Build a FAISS Flat index over subreddit profile chunks.")
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
    parser.add_argument("--batch-size", type=int, default=32, help="Embedding batch size (default: 32).")
    parser.add_argument(
        "--window-tokens",
        type=int,
        default=64,
        help="Sliding window size in model tokens (default: 64).",
    )
    parser.add_argument(
        "--overlap-tokens",
        type=int,
        default=16,
        help="Sliding window overlap in model tokens (default: 16).",
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
        window_tokens=args.window_tokens,
        overlap_tokens=args.overlap_tokens,
    )
    if metadata.empty:
        raise ValueError("No profile chunks were produced from the provided input.")

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
