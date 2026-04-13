"""Build subreddit profiles and chunk text for FAISS indexing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from read_zst import iter_zst_jsonl
except ImportError:
    from data.read_zst import iter_zst_jsonl

IGNORED_TEXT_VALUES = {"", "[deleted]", "[removed]", "nan", "none"}


def iter_ndjson(path: Path) -> dict[str, Any]:
    """Yield JSON objects from an NDJSON file."""
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_no}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Expected JSON object at line {line_no}.")
            yield item


def iter_input_records(path: Path) -> dict[str, Any]:
    """Yield records from either NDJSON or a raw Pushshift `.zst` dump."""
    if path.suffix == ".zst":
        yield from iter_zst_jsonl(path)
        return
    yield from iter_ndjson(path)


def load_metadata_map(raw_metadata_path: Path | None) -> dict[str, dict[str, Any]]:
    """Load optional subreddit metadata keyed by subreddit name."""
    if raw_metadata_path is None or not raw_metadata_path.exists():
        return {}

    raw = raw_metadata_path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            if all(isinstance(value, dict) for value in parsed.values()):
                return {str(key): value for key, value in parsed.items()}
            return {}
        if isinstance(parsed, list):
            records = [item for item in parsed if isinstance(item, dict)]
        else:
            return {}
    except json.JSONDecodeError:
        records = []
        for line in raw.splitlines():
            item = json.loads(line)
            if isinstance(item, dict):
                records.append(item)

    metadata: dict[str, dict[str, Any]] = {}
    for record in records:
        subreddit = str(record.get("subreddit", "")).strip()
        if subreddit:
            metadata[subreddit] = record
    return metadata


def normalize_text(text: Any) -> str:
    """Normalize free-form text fields and drop deleted/removed placeholders."""
    value = str(text or "").strip()
    if value.lower() in IGNORED_TEXT_VALUES:
        return ""
    return " ".join(value.split())


def first_non_empty(*values: Any) -> str:
    """Return the first non-empty normalized text value."""
    for value in values:
        normalized = normalize_text(value)
        if normalized:
            return normalized
    return ""


def build_subreddit_profiles(
    raw_posts_path: Path,
    raw_metadata_path: Path | None,
    output_path: Path,
    min_subscribers: int = 1000,
    top_posts: int = 50,
) -> pd.DataFrame:
    """Create profile records from sidebar, rules, and top posts per subreddit."""
    metadata_map = load_metadata_map(raw_metadata_path)
    grouped: dict[str, dict[str, Any]] = {}

    for record in iter_input_records(raw_posts_path):
        subreddit = str(record.get("subreddit", "")).strip()
        if not subreddit:
            continue

        bucket = grouped.setdefault(
            subreddit,
            {
                "subreddit": subreddit,
                "subreddit_subscribers": None,
                "top_posts": [],
            },
        )

        subscribers = record.get("subreddit_subscribers")
        if subscribers is not None:
            try:
                bucket["subreddit_subscribers"] = max(
                    int(subscribers),
                    int(bucket["subreddit_subscribers"] or 0),
                )
            except (TypeError, ValueError):
                pass

        try:
            score = int(record.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        title = normalize_text(record.get("title"))
        selftext = normalize_text(record.get("selftext"))
        permalink = first_non_empty(
            record.get("permalink"),
            record.get("url"),
        )
        combined_post = " ".join(part for part in [title, selftext] if part).strip()
        if combined_post:
            bucket["top_posts"].append(
                {
                    "score": score,
                    "title": title,
                    "selftext": selftext,
                    "permalink": permalink,
                    "combined_text": combined_post,
                }
            )

    rows: list[dict[str, Any]] = []
    for subreddit, bucket in grouped.items():
        subscribers = bucket.get("subreddit_subscribers")
        if subscribers is not None and subscribers < min_subscribers:
            continue

        metadata = metadata_map.get(subreddit, {})
        sidebar = first_non_empty(
            metadata.get("sidebar"),
            metadata.get("public_description"),
            metadata.get("description"),
        )
        rules = metadata.get("rules")
        if isinstance(rules, list):
            rules_text = " | ".join(normalize_text(rule) for rule in rules if normalize_text(rule))
        else:
            rules_text = normalize_text(rules)

        top_post_limit = top_posts
        selected_posts = sorted(bucket["top_posts"], key=lambda item: item["score"], reverse=True)[:top_post_limit]
        top_post_texts = []
        for idx, post in enumerate(selected_posts, start=1):
            segments = [f"{idx}. {post['title']}"]
            if post["selftext"]:
                segments.append(post["selftext"])
            top_post_texts.append(" ".join(segments).strip())

        profile_sections = [f"Subreddit: r/{subreddit}"]
        if subscribers is not None:
            profile_sections.append(f"Subscribers: {subscribers}")
        if sidebar:
            profile_sections.append(f"Sidebar: {sidebar}")
        if rules_text:
            profile_sections.append(f"Rules: {rules_text}")
        if top_post_texts:
            profile_sections.append("Top posts: " + " || ".join(top_post_texts))

        rows.append(
            {
                "subreddit": subreddit,
                "subreddit_subscribers": subscribers,
                "sidebar": sidebar,
                "rules_text": rules_text,
                "top_posts": [
                    {
                        "score": post["score"],
                        "title": post["title"],
                        "selftext": post["selftext"],
                        "permalink": post["permalink"],
                    }
                    for post in selected_posts
                ],
                "profile_text": "\n".join(profile_sections),
            }
        )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(
            by=["subreddit_subscribers", "subreddit"],
            ascending=[False, True],
            na_position="last",
        ).reset_index(drop=True)
    else:
        frame = pd.DataFrame(
            columns=["subreddit", "subreddit_subscribers", "sidebar", "rules_text", "top_posts", "profile_text"]
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(frame.to_json(orient="records", indent=2, force_ascii=False), encoding="utf-8")
    return frame


def chunk_profile_text(
    profile_text: str,
    window_tokens: int = 64,
    overlap_tokens: int = 16,
) -> list[str]:
    """Chunk profile text into overlapping token windows for dense encoding."""
    text = normalize_text(profile_text)
    if not text:
        return []
    if window_tokens <= 0:
        raise ValueError("window_tokens must be > 0")
    if overlap_tokens < 0 or overlap_tokens >= window_tokens:
        raise ValueError("overlap_tokens must be >= 0 and < window_tokens")

    tokens = text.split()
    if not tokens:
        return []

    step = window_tokens - overlap_tokens
    chunks: list[str] = []
    for start in range(0, len(tokens), step):
        chunk_tokens = tokens[start : start + window_tokens]
        if not chunk_tokens:
            continue
        chunks.append(" ".join(chunk_tokens))
        if start + window_tokens >= len(tokens):
            break
    return chunks


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for corpus preprocessing."""
    parser = argparse.ArgumentParser(description="Build subreddit profile JSON from Reddit post data.")
    parser.add_argument(
        "--posts",
        type=Path,
        default=Path("data/processed/reddit_slim.ndjson"),
        help="Path to input NDJSON or .zst posts file (default: data/processed/reddit_slim.ndjson).",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=None,
        help="Optional path to subreddit metadata JSON/NDJSON containing sidebar/rules.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/subreddit_profiles.json"),
        help="Path to output subreddit profiles JSON (default: data/processed/subreddit_profiles.json).",
    )
    parser.add_argument(
        "--min-subscribers",
        type=int,
        default=1000,
        help="Minimum subreddit subscriber count when that field is available (default: 1000).",
    )
    parser.add_argument(
        "--top-posts",
        type=int,
        default=50,
        help="Number of top-scoring posts to include per subreddit (default: 50).",
    )
    return parser.parse_args()


def main() -> None:
    """Run subreddit profile preprocessing from the command line."""
    args = parse_args()
    if not args.posts.exists():
        raise FileNotFoundError(f"Input posts file not found: {args.posts}")

    frame = build_subreddit_profiles(
        raw_posts_path=args.posts,
        raw_metadata_path=args.metadata,
        output_path=args.output,
        min_subscribers=args.min_subscribers,
        top_posts=args.top_posts,
    )
    print(f"Wrote {len(frame)} subreddit profiles to {args.output}")


if __name__ == "__main__":
    main()
