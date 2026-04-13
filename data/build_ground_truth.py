"""Construct YouTube-to-subreddit ground-truth pairs for evaluation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

try:
    from read_zst import iter_zst_jsonl
except ImportError:
    from data.read_zst import iter_zst_jsonl

YOUTUBE_URL_RE = re.compile(r"https?://[^\s<>\"]*(?:youtube\.com|youtu\.be)[^\s<>\"]*", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,!?;:)]}\"'*"


def normalize_youtube_url(url: str) -> str:
    """Trim common punctuation artifacts from URLs embedded in text."""
    normalized = url.strip().replace("\\_", "_")
    for delimiter in ("](", ")(", ">("):
        if delimiter in normalized:
            normalized = normalized.split(delimiter, maxsplit=1)[0]
    return normalized.rstrip(TRAILING_PUNCTUATION)


def infer_channel_id(url: str) -> tuple[str | None, str]:
    """Infer a stable retrieval key from a YouTube URL.

    Preference order:
    - channel URL -> `channel:<id>`
    - handle URL -> `handle:@name`
    - legacy user/custom channel URL
    - video URL -> `video:<id>` as a fallback when no channel identifier exists
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")
    path_parts = [part for part in parsed.path.split("/") if part]

    if host == "youtu.be" and path_parts:
        return f"video:{path_parts[0]}", "video"

    if "youtube.com" not in host:
        return None, "unknown"

    if path_parts:
        first = path_parts[0]
        if first == "channel" and len(path_parts) >= 2:
            return f"channel:{path_parts[1]}", "channel"
        if first.startswith("@"):
            return f"handle:{first}", "handle"
        if first == "user" and len(path_parts) >= 2:
            return f"user:{path_parts[1]}", "user"
        if first == "c" and len(path_parts) >= 2:
            return f"custom:{path_parts[1]}", "custom"
        if first in {"shorts", "embed", "live", "v"} and len(path_parts) >= 2:
            return f"video:{path_parts[1]}", "video"

    query = parse_qs(parsed.query)
    if "v" in query and query["v"]:
        return f"video:{query['v'][0]}", "video"

    return None, "unknown"


def iter_ndjson(path: Path) -> dict:
    """Yield JSON objects from an NDJSON file."""
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_no}: {exc}") from exc


def iter_input_records(path: Path) -> dict:
    """Yield records from either NDJSON or a raw Pushshift `.zst` dump."""
    if path.suffix == ".zst":
        yield from iter_zst_jsonl(path)
        return
    yield from iter_ndjson(path)


def extract_youtube_links(text: str) -> list[str]:
    """Extract YouTube links from post text."""
    if not text:
        return []

    seen: set[str] = set()
    links: list[str] = []
    for match in YOUTUBE_URL_RE.findall(text):
        normalized = normalize_youtube_url(match)
        if normalized and normalized not in seen:
            seen.add(normalized)
            links.append(normalized)
    return links


def build_ground_truth_pairs(
    posts_path: Path,
    output_path: Path,
    min_score: int = 2,
    limit_posts: int | None = None,
) -> pd.DataFrame:
    """Build labeled YouTube-subreddit pairs from Reddit posts with score filtering."""
    rows: list[dict[str, object]] = []
    scanned = 0

    for record in iter_input_records(posts_path):
        scanned += 1
        if limit_posts is not None and scanned > limit_posts:
            break
        subreddit = str(record.get("subreddit", "")).strip()
        if not subreddit:
            continue

        try:
            score = int(record.get("score", 0))
        except (TypeError, ValueError):
            continue

        if score < min_score:
            continue

        text_parts = [
            str(record.get("title", "") or ""),
            str(record.get("selftext", "") or ""),
            str(record.get("url", "") or ""),
        ]
        links = extract_youtube_links("\n".join(text_parts))
        if not links:
            continue

        seen_channel_ids: set[str] = set()
        for link in links:
            channel_id, url_type = infer_channel_id(link)
            if not channel_id or channel_id in seen_channel_ids:
                continue
            seen_channel_ids.add(channel_id)
            rows.append(
                {
                    "channel_id": channel_id,
                    "subreddit": subreddit,
                    "url_type": url_type,
                    "source_url": link,
                    "post_id": record.get("id"),
                    "score": score,
                    "created_utc": record.get("created_utc"),
                }
            )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["channel_id", "subreddit", "score"], ascending=[True, True, False])
        frame = frame.drop_duplicates(subset=["channel_id", "subreddit"], keep="first").reset_index(drop=True)
    else:
        frame = pd.DataFrame(columns=["channel_id", "subreddit", "url_type", "source_url", "post_id", "score", "created_utc"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return frame


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for ground-truth construction."""
    parser = argparse.ArgumentParser(description="Build YouTube-to-subreddit ground-truth pairs from Reddit posts.")
    parser.add_argument(
        "--posts",
        type=Path,
        default=Path("data/processed/reddit_slim.ndjson"),
        help="Path to input NDJSON or .zst posts file (default: data/processed/reddit_slim.ndjson).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/ground_truth_pairs.csv"),
        help="Path to output CSV (default: data/processed/ground_truth_pairs.csv).",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=2,
        help="Minimum Reddit score required to keep a post (default: 2).",
    )
    parser.add_argument(
        "--limit-posts",
        type=int,
        default=None,
        help="Optional cap on scanned input posts for quick validation.",
    )
    return parser.parse_args()


def main() -> None:
    """Run ground-truth extraction from the command line."""
    args = parse_args()
    if not args.posts.exists():
        raise FileNotFoundError(f"Input posts file not found: {args.posts}")

    frame = build_ground_truth_pairs(
        posts_path=args.posts,
        output_path=args.output,
        min_score=args.min_score,
        limit_posts=args.limit_posts,
    )
    print(f"Wrote {len(frame)} ground-truth pairs to {args.output}")


if __name__ == "__main__":
    main()
