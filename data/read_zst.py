"""Stream-read Reddit Pushshift JSONL files compressed with Zstandard."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any

import zstandard as zstd


DEFAULT_FIELDS = ["id", "subreddit", "created_utc", "score", "title", "url"]


def iter_zst_jsonl(path: Path) -> Any:
    """Yield JSON objects line-by-line from a .zst JSONL file."""
    with path.open("rb") as compressed:
        dctx = zstd.ZstdDecompressor(max_window_size=2**31)
        with dctx.stream_reader(compressed) as reader:
            text_reader = io.TextIOWrapper(reader, encoding="utf-8")
            for line_no, line in enumerate(text_reader, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at line {line_no}: {exc}") from exc


def record_matches(record: dict[str, Any], subreddit: str | None, min_score: int | None) -> bool:
    """Apply optional subreddit and minimum score filters."""
    if subreddit:
        if str(record.get("subreddit", "")).lower() != subreddit.lower():
            return False

    if min_score is not None:
        try:
            score = float(record.get("score", float("-inf")))
        except (TypeError, ValueError):
            return False
        if score < min_score:
            return False

    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read JSON records from a .zst Reddit dump.")
    parser.add_argument(
        "path",
        nargs="?",
        default="RS_2019-04.zst",
        type=Path,
        help="Path to .zst file (default: RS_2019-04.zst).",
    )
    parser.add_argument("--limit", type=int, default=5, help="Maximum records to print (default: 5).")
    parser.add_argument("--raw", action="store_true", help="Print full JSON objects instead of selected fields.")
    parser.add_argument(
        "--fields",
        type=str,
        default=",".join(DEFAULT_FIELDS),
        help=f"Comma-separated fields to output (default: {','.join(DEFAULT_FIELDS)}).",
    )
    parser.add_argument("--subreddit", type=str, default=None, help="Only keep records from this subreddit.")
    parser.add_argument("--min-score", type=int, default=None, help="Only keep records with score >= this value.")
    parser.add_argument("--count", action="store_true", help="Only count matched records; print no samples.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.path.exists():
        raise FileNotFoundError(f"File not found: {args.path}")

    if args.limit < 0:
        raise ValueError("--limit must be >= 0")

    fields = [field.strip() for field in args.fields.split(",") if field.strip()]
    matched = 0
    printed = 0

    for record in iter_zst_jsonl(args.path):
        if not record_matches(record, args.subreddit, args.min_score):
            continue

        matched += 1
        if args.count:
            continue

        payload = record if args.raw else {field: record.get(field) for field in fields}
        print(json.dumps(payload, ensure_ascii=False))
        printed += 1

        if printed >= args.limit:
            break

    if args.count:
        print(matched)


if __name__ == "__main__":
    main()
