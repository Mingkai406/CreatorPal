"""Streamlit UI for CreatorPal subreddit matching and strategy report display."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

from src.pipeline import build_pipeline


def render_ranked_subreddits(subreddits: Sequence[Mapping[str, Any]]) -> None:
    """Render ranked subreddit results with clickable Reddit links."""
    raise NotImplementedError("Implement subreddit ranking UI renderer.")


def render_strategy_report(report: str) -> None:
    """Render the generated audience strategy report in the UI."""
    raise NotImplementedError("Implement strategy report UI renderer.")


def main() -> None:
    """Run the Streamlit application entrypoint."""
    raise NotImplementedError("Implement Streamlit app workflow.")


if __name__ == "__main__":
    main()
