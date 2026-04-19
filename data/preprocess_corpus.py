"""Build subreddit profiles from Reddit submission dumps for FAISS indexing."""

from __future__ import annotations

import argparse
import heapq
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Subreddit quality filters
# ---------------------------------------------------------------------------

# Exact lowercase subreddit names to exclude unconditionally.
_BLOCKED_NAMES: frozenset[str] = frozenset({
    # Self-promotion / sub-for-sub
    "sub4sub", "subforsub", "subforsubreddit",
    "subscribetome", "subscribetomeyoutube",
    "promote", "promote_your_channel", "promoteyourchannel",
    "youtubelimited", "cookiecollector",
    "ytpromotion", "youtubegrowth",
    # Known NSFW
    "gfur", "yiff", "rule34", "hentai",
})

# If any of these fragments appear in the lowercase subreddit name, exclude it.
_BLOCKED_NAME_FRAGMENTS: tuple[str, ...] = (
    "sub4sub", "subforsub", "subscribetome",
    "promote_your", "promotechannel", "youtubelimited",
    "nsfw", "porn", "xxx",
)

# Phrases that indicate subscription-farming content.
_SPAM_PHRASES: tuple[str, ...] = (
    "sub 4 sub", "sub4sub", "sub for sub", "subforsub",
    "i will sub back", "sub back", "subscribe back",
    "subscribe to my channel", "i sub back",
)

# If a profile contains more than this many spam-phrase hits, drop it.
_SPAM_PHRASE_THRESHOLD = 5


def _is_blocked(subreddit: str, profile_text: str) -> bool:
    """Return True if this subreddit should be excluded from the corpus."""
    lower_name = subreddit.lower()
    if lower_name in _BLOCKED_NAMES:
        return True
    if any(frag in lower_name for frag in _BLOCKED_NAME_FRAGMENTS):
        return True
    lower_text = profile_text.lower()
    hits = sum(lower_text.count(phrase) for phrase in _SPAM_PHRASES)
    return hits > _SPAM_PHRASE_THRESHOLD


def _iter_ndjson(path: Path):
    """Yield JSON objects line-by-line from an NDJSON file."""
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if raw:
                yield json.loads(raw)


def _post_text(record: dict[str, Any]) -> str:
    """Combine title and selftext into a single string."""
    title = str(record.get("title", "") or "").strip()
    selftext = str(record.get("selftext", "") or "").strip()
    if selftext and selftext != "[removed]" and selftext != "[deleted]":
        return f"{title}. {selftext}"
    return title


def build_subreddit_profiles(
    input_path: Path,
    output_path: Path,
    min_posts: int = 10,
    top_posts: int = 50,
) -> int:
    """Aggregate Reddit submissions into per-subreddit profile documents.

    For each subreddit, keeps the *top_posts* highest-scored submissions and
    concatenates their title + selftext into a single ``profile_text``.
    Subreddits with fewer than *min_posts* submissions are discarded.

    Returns the number of profiles written.
    """
    if min_posts > top_posts:
        raise ValueError(
            f"min_posts ({min_posts}) must be <= top_posts ({top_posts}); "
            "the heap can hold at most top_posts entries so no subreddit "
            "would ever satisfy the min_posts threshold."
        )

    # Use a min-heap of size top_posts per subreddit to bound memory.
    # Heap items are (score, post_text) so the lowest score is popped first.
    heaps: dict[str, list[tuple[int, str]]] = defaultdict(list)

    logger.info("Scanning posts from %s ...", input_path)
    scanned = 0
    for record in _iter_ndjson(input_path):
        scanned += 1
        if scanned % 500_000 == 0:
            logger.info("  scanned %d posts, %d subreddits so far", scanned, len(heaps))

        subreddit = str(record.get("subreddit", "")).strip()
        if not subreddit:
            continue

        try:
            score = int(record.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        text = _post_text(record)
        if not text:
            continue

        heap = heaps[subreddit]
        item = (score, text)
        if len(heap) < top_posts:
            heapq.heappush(heap, item)
        elif score > heap[0][0]:
            heapq.heapreplace(heap, item)

    logger.info("Scanned %d posts across %d subreddits", scanned, len(heaps))

    profiles: list[dict[str, Any]] = []
    blocked_count = 0
    for subreddit, heap in sorted(heaps.items()):
        if len(heap) < min_posts:
            continue
        top = sorted(heap, key=lambda x: x[0], reverse=True)
        profile_text = "\n".join(text for _, text in top)
        if _is_blocked(subreddit, profile_text):
            blocked_count += 1
            logger.info("Filtered out r/%s", subreddit)
            continue
        profiles.append({
            "subreddit": subreddit,
            "profile_text": profile_text,
            "post_count": len(heap),
        })

    logger.info("Blocked %d subreddits by name/content filter", blocked_count)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(profiles, fh, ensure_ascii=False, indent=2)

    logger.info("Wrote %d subreddit profiles to %s", len(profiles), output_path)
    return len(profiles)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for corpus preprocessing."""
    parser = argparse.ArgumentParser(
        description="Build subreddit profiles from a Reddit NDJSON dump."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/reddit_slim.ndjson"),
        help="Path to input NDJSON file (default: data/processed/reddit_slim.ndjson).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/subreddit_profiles.json"),
        help="Path to output JSON (default: data/processed/subreddit_profiles.json).",
    )
    parser.add_argument(
        "--min-posts",
        type=int,
        default=10,
        help="Minimum posts required to keep a subreddit (default: 10).",
    )
    parser.add_argument(
        "--top-posts",
        type=int,
        default=50,
        help="Number of top-scored posts per subreddit to keep (default: 50).",
    )
    return parser.parse_args()


def main() -> None:
    """Run subreddit profile preprocessing from the command line."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    count = build_subreddit_profiles(
        input_path=args.input,
        output_path=args.output,
        min_posts=args.min_posts,
        top_posts=args.top_posts,
    )
    print(f"Wrote {count} subreddit profiles to {args.output}")


if __name__ == "__main__":
    main()
