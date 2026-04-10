"""Build subreddit profiles and chunk text for FAISS indexing."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_subreddit_profiles(
    raw_posts_path: Path,
    raw_metadata_path: Path,
    output_path: Path,
    min_subscribers: int = 1000,
    top_posts: int = 50,
) -> pd.DataFrame:
    """Create profile records from sidebar, rules, and top posts per subreddit."""
    raise NotImplementedError("Implement subreddit profile construction.")


def chunk_profile_text(
    profile_text: str,
    window_tokens: int = 64,
    overlap_tokens: int = 16,
) -> list[str]:
    """Chunk profile text into overlapping token windows for dense encoding."""
    raise NotImplementedError("Implement profile chunking with overlap.")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for corpus preprocessing."""
    raise NotImplementedError("Implement CLI argument parsing for preprocess_corpus.py.")


def main() -> None:
    """Run subreddit profile preprocessing from the command line."""
    raise NotImplementedError("Implement main entrypoint for corpus preprocessing.")


if __name__ == "__main__":
    main()
