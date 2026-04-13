"""Validate and normalize pipeline payloads before Streamlit rendering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from numbers import Integral, Number
from typing import Any
from urllib.parse import urlparse

REQUIRED_TOP_LEVEL_KEYS = (
    "input",
    "ranked_subreddits",
    "strategy_report",
    "pal_results",
    "sentiment_scores",
    "meta",
)

REQUIRED_INPUT_KEYS = (
    "channel_or_query",
    "user_query",
    "resolved_mode",
    "timestamp_utc",
)

REQUIRED_SUBREDDIT_KEYS = (
    "rank",
    "subreddit",
    "retrieval_score",
    "rerank_score",
    "reason",
    "evidence",
    "sentiment_score",
)

REQUIRED_PAL_KEYS = (
    "summary",
    "metrics",
)

REQUIRED_META_KEYS = (
    "retrieval_top_k",
    "rerank_top_k",
    "latency_ms",
)


def adapt(raw: Any) -> dict[str, Any]:
    """Validate the pipeline contract and return a normalized payload."""
    if not isinstance(raw, Mapping):
        raise ValueError("Pipeline returned a non-dict response.")

    payload = dict(raw)
    _validate_required_keys(payload, REQUIRED_TOP_LEVEL_KEYS)

    payload["input"] = _normalize_input(payload["input"])
    payload["ranked_subreddits"] = _normalize_ranked_subreddits(payload["ranked_subreddits"])
    payload["strategy_report"] = _normalize_strategy_report(payload["strategy_report"])
    payload["pal_results"] = _normalize_pal_results(payload["pal_results"])
    payload["sentiment_scores"] = _normalize_sentiment_scores(payload["sentiment_scores"])
    payload["meta"] = _normalize_meta(payload["meta"])
    return payload


def _normalize_input(raw_input: Any) -> dict[str, Any]:
    if not isinstance(raw_input, Mapping):
        raise ValueError('Contract violation: "input" must be a dict.')

    data = dict(raw_input)
    _validate_required_keys(data, REQUIRED_INPUT_KEYS, path="input")

    channel_or_query = data["channel_or_query"]
    if not isinstance(channel_or_query, str) or not channel_or_query.strip():
        raise ValueError('Contract violation: "input.channel_or_query" must be a non-empty string.')

    user_query = data["user_query"]
    if user_query is not None and not isinstance(user_query, str):
        raise ValueError('Contract violation: "input.user_query" must be a string or null.')

    resolved_mode = data["resolved_mode"]
    if resolved_mode not in {"channel", "query"}:
        raise ValueError('Contract violation: "input.resolved_mode" must be "channel" or "query".')

    timestamp_utc = data["timestamp_utc"]
    if not isinstance(timestamp_utc, str) or not timestamp_utc.strip():
        raise ValueError('Contract violation: "input.timestamp_utc" must be a non-empty string.')

    data["channel_or_query"] = channel_or_query.strip()
    data["user_query"] = user_query.strip() if isinstance(user_query, str) else None
    data["resolved_mode"] = resolved_mode
    data["timestamp_utc"] = timestamp_utc.strip()
    return data


def _normalize_ranked_subreddits(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        raise ValueError('Contract violation: "ranked_subreddits" must be a list.')
    return [_normalize_subreddit_item(item, idx) for idx, item in enumerate(raw_items)]


def _normalize_subreddit_item(raw_item: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw_item, Mapping):
        raise ValueError(f'Contract violation: "ranked_subreddits[{index}]" must be a dict.')

    item = dict(raw_item)
    _validate_required_keys(item, REQUIRED_SUBREDDIT_KEYS, path=f"ranked_subreddits[{index}]")

    rank = item["rank"]
    if not _is_int_like(rank):
        raise ValueError(f'Contract violation: "ranked_subreddits[{index}].rank" must be an integer.')

    subreddit = _normalize_subreddit_name(item["subreddit"])
    if not subreddit:
        raise ValueError(f'Contract violation: "ranked_subreddits[{index}].subreddit" is invalid.')

    reason = item["reason"]
    evidence = item["evidence"]

    item["rank"] = int(rank)
    item["subreddit"] = subreddit
    item["url"] = _normalize_reddit_url(item.get("url"), subreddit)
    item["retrieval_score"] = _coerce_float_or_none(item["retrieval_score"])
    item["rerank_score"] = _coerce_float_or_none(item["rerank_score"])
    item["sentiment_score"] = _coerce_float_or_none(item["sentiment_score"])
    item["reason"] = str(reason).strip() if reason is not None else ""
    item["evidence"] = _normalize_evidence(evidence, index)
    return item


def _normalize_strategy_report(report: Any) -> str:
    if report is None:
        return ""
    return str(report)


def _normalize_pal_results(raw_pal: Any) -> dict[str, Any]:
    if not isinstance(raw_pal, Mapping):
        raise ValueError('Contract violation: "pal_results" must be a dict.')

    pal = dict(raw_pal)
    _validate_required_keys(pal, REQUIRED_PAL_KEYS, path="pal_results")

    pal["summary"] = str(pal["summary"]).strip()
    metrics = pal["metrics"]
    if not isinstance(metrics, Mapping):
        raise ValueError('Contract violation: "pal_results.metrics" must be a dict.')
    pal["metrics"] = dict(metrics)
    return pal


def _normalize_sentiment_scores(raw_scores: Any) -> dict[str, float]:
    if not isinstance(raw_scores, Mapping):
        raise ValueError('Contract violation: "sentiment_scores" must be a dict.')

    normalized: dict[str, float] = {}
    for raw_name, raw_score in raw_scores.items():
        name = _normalize_sentiment_key(raw_name)
        score = _coerce_float_or_none(raw_score)
        if score is None:
            raise ValueError(f'Contract violation: "sentiment_scores.{name}" must be numeric.')
        normalized[name] = score
    return normalized


def _normalize_meta(raw_meta: Any) -> dict[str, int]:
    if not isinstance(raw_meta, Mapping):
        raise ValueError('Contract violation: "meta" must be a dict.')

    meta = dict(raw_meta)
    _validate_required_keys(meta, REQUIRED_META_KEYS, path="meta")

    for key in REQUIRED_META_KEYS:
        value = meta[key]
        if not _is_int_like(value):
            raise ValueError(f'Contract violation: "meta.{key}" must be an integer.')
        meta[key] = int(value)
    return meta


def _validate_required_keys(data: Mapping[str, Any], keys: Sequence[str], path: str | None = None) -> None:
    for key in keys:
        if key in data:
            continue
        if path:
            raise ValueError(f'Contract violation: missing required key "{path}.{key}".')
        raise ValueError(f'Contract violation: missing required key "{key}".')


def _normalize_subreddit_name(raw_value: Any) -> str:
    if not isinstance(raw_value, str):
        return ""
    name = raw_value.strip()
    if name.lower().startswith("r/"):
        name = name[2:]
    return name.strip("/")


def _normalize_reddit_url(raw_url: Any, subreddit: str) -> str:
    fallback = f"https://www.reddit.com/r/{subreddit}/"
    if not isinstance(raw_url, str) or not raw_url.strip():
        return fallback

    url = raw_url.strip()
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return url
    return fallback


def _normalize_evidence(raw_evidence: Any, index: int) -> list[str]:
    if raw_evidence is None:
        return []

    if not isinstance(raw_evidence, Sequence) or isinstance(raw_evidence, (str, bytes)):
        raise ValueError(
            f'Contract violation: "ranked_subreddits[{index}].evidence" must be a list of strings.'
        )

    evidence: list[str] = []
    for value in raw_evidence:
        if value is None:
            continue
        evidence.append(str(value))
    return evidence


def _normalize_sentiment_key(raw_name: Any) -> str:
    name = str(raw_name).strip()
    if not name:
        raise ValueError('Contract violation: "sentiment_scores" contains an empty subreddit key.')
    if not name.startswith("r/"):
        return f"r/{name.lstrip('/')}"
    return name


def _coerce_float_or_none(raw_value: Any) -> float | None:
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, Number):
        return float(raw_value)
    return None


def _is_int_like(raw_value: Any) -> bool:
    return isinstance(raw_value, Integral) and not isinstance(raw_value, bool)

