"""Construct YouTube-to-subreddit ground-truth pairs for evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def extract_youtube_links(text: str) -> list[str]:
    """Extract YouTube links from post text."""
    raise NotImplementedError("Implement YouTube URL extraction from Reddit text.")


def build_ground_truth_pairs(posts_path: Path, output_path: Path, min_score: int = 10) -> pd.DataFrame:
    """Build labeled YouTube-subreddit pairs from Reddit posts with score filtering."""
    raise NotImplementedError("Implement ground-truth pair extraction.")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for ground-truth construction."""
    raise NotImplementedError("Implement CLI argument parsing for build_ground_truth.py.")


def main() -> None:
    """Run ground-truth extraction from the command line."""
    raise NotImplementedError("Implement main entrypoint for ground-truth construction.")


if __name__ == "__main__":
    main()
