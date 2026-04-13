"""Stream a raw Reddit `.zst` dump into a smaller NDJSON subset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from read_zst import iter_zst_jsonl
except ImportError:
    from data.read_zst import iter_zst_jsonl

DEFAULT_FIELDS = [
    "id",
    "subreddit",
    "subreddit_subscribers",
    "created_utc",
    "score",
    "title",
    "url",
    "selftext",
]


def project_record(record: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Keep only the requested fields from a Reddit record."""
    return {field: record.get(field) for field in fields}


def build_reddit_slim(
    input_path: Path,
    output_path: Path,
    fields: list[str],
    min_score: int | None = None,
    limit_posts: int | None = None,
) -> int:
    """Write a filtered NDJSON subset and return the number of kept posts."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    scanned = 0

    with output_path.open("w", encoding="utf-8") as handle:
        for record in iter_zst_jsonl(input_path):
            scanned += 1
            if limit_posts is not None and scanned > limit_posts:
                break

            if min_score is not None:
                try:
                    score = int(record.get("score", 0))
                except (TypeError, ValueError):
                    continue
                if score < min_score:
                    continue

            payload = project_record(record, fields)
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            kept += 1

    return kept


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for slim-file generation."""
    parser = argparse.ArgumentParser(description="Build a slim NDJSON subset from a Reddit Pushshift .zst dump.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/RS_2019-04.zst"),
        help="Path to the raw .zst file (default: data/RS_2019-04.zst).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/reddit_slim.ndjson"),
        help="Path to the output NDJSON file (default: data/processed/reddit_slim.ndjson).",
    )
    parser.add_argument(
        "--fields",
        type=str,
        default=",".join(DEFAULT_FIELDS),
        help=f"Comma-separated fields to keep (default: {','.join(DEFAULT_FIELDS)}).",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=None,
        help="Optional minimum Reddit score filter.",
    )
    parser.add_argument(
        "--limit-posts",
        type=int,
        default=None,
        help="Optional cap on scanned input posts for quick validation.",
    )
    return parser.parse_args()


def main() -> None:
    """Run slim-file generation from the command line."""
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    fields = [field.strip() for field in args.fields.split(",") if field.strip()]
    if not fields:
        raise ValueError("At least one field must be provided.")

    kept = build_reddit_slim(
        input_path=args.input,
        output_path=args.output,
        fields=fields,
        min_score=args.min_score,
        limit_posts=args.limit_posts,
    )
    print(f"Wrote {kept} slim Reddit posts to {args.output}")


if __name__ == "__main__":
    main()
