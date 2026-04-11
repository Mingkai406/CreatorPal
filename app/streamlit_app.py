"""Streamlit UI for CreatorPal subreddit matching and strategy report display."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

import streamlit as st

from app.helpers.adapter import adapt
from app.helpers.components import (
    error_card_html,
    metric_card_html,
    sentiment_bar_html,
    subreddit_row_html,
)
from app.helpers.mock_pipeline import MockPipeline
from src.pipeline import build_pipeline

COLORS: dict[str, str] = {
    "bg_page": "#EEF2F7",
    "bg_card": "#FFFFFF",
    "bg_input": "#F8FAFC",
    "bg_badge_blue": "#EFF6FF",
    "bg_badge_green": "#ECFDF5",
    "border_default": "#E2E8F0",
    "border_subtle": "#F1F5F9",
    "text_primary": "#0F172A",
    "text_secondary": "#475569",
    "text_muted": "#94A3B8",
    "text_link": "#3B82F6",
    "blue_500": "#3B82F6",
    "green_500": "#10B981",
    "amber_400": "#F59E0B",
    "red_400": "#F87171",
}

GLOBAL_CSS = f"""<style>
[data-testid="stAppViewContainer"] {{
    background: {COLORS["bg_page"]};
}}
[data-testid="stSidebar"] {{
    background: {COLORS["bg_card"]};
    border-right: 1px solid {COLORS["border_default"]};
}}
[data-testid="block-container"] {{
    padding: 1.5rem 2rem;
    max-width: 1100px;
}}
footer, #MainMenu {{
    display: none;
}}
body, .stMarkdown, .stText {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: {COLORS["text_primary"]};
}}
.cp-card {{
    background: {COLORS["bg_card"]};
    border-radius: 12px;
    border: 1px solid {COLORS["border_default"]};
    padding: 14px 16px;
    margin-bottom: 10px;
}}
.cp-card-title {{
    font-size: 14px;
    font-weight: 600;
    color: {COLORS["text_primary"]};
    margin: 0 0 12px;
}}
.cp-metric {{
    background: {COLORS["bg_card"]};
    border-radius: 12px;
    border: 1px solid {COLORS["border_default"]};
    padding: 12px 14px;
}}
.cp-metric-label {{
    font-size: 11px;
    font-weight: 500;
    color: {COLORS["text_muted"]};
    letter-spacing: 0.03em;
    text-transform: uppercase;
    margin-bottom: 6px;
}}
.cp-metric-value {{
    font-size: 22px;
    font-weight: 700;
    color: {COLORS["text_primary"]};
    letter-spacing: -0.03em;
    line-height: 1;
}}
.cp-metric-sub-up {{
    font-size: 11px;
    color: {COLORS["green_500"]};
    margin-top: 4px;
}}
.cp-metric-sub-neutral {{
    font-size: 11px;
    color: {COLORS["text_muted"]};
    margin-top: 4px;
}}
.cp-sub-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 0.5px solid {COLORS["border_subtle"]};
}}
.cp-sub-row:last-child {{
    border-bottom: none;
}}
.cp-rank {{
    font-size: 13px;
    font-weight: 700;
    color: {COLORS["text_muted"]};
    width: 18px;
    text-align: right;
    flex-shrink: 0;
}}
.cp-sub-info {{
    flex: 1;
    min-width: 0;
}}
.cp-sub-name {{
    font-size: 13px;
    font-weight: 600;
    color: {COLORS["text_link"]};
    text-decoration: none;
}}
.cp-sub-name:hover {{
    text-decoration: underline;
}}
.cp-sub-reason {{
    font-size: 11px;
    color: {COLORS["text_muted"]};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.cp-score-wrap {{
    width: 56px;
    flex-shrink: 0;
}}
.cp-score-label {{
    font-size: 10px;
    color: {COLORS["text_muted"]};
    text-align: right;
    margin-bottom: 2px;
}}
.cp-score-track {{
    height: 4px;
    background: {COLORS["bg_page"]};
    border-radius: 2px;
    overflow: hidden;
}}
.cp-score-fill {{
    height: 100%;
    background: {COLORS["blue_500"]};
    border-radius: 2px;
}}
.cp-open-link {{
    font-size: 11px;
    color: {COLORS["text_link"]};
    text-decoration: none;
    flex-shrink: 0;
    padding-left: 8px;
}}
.cp-sent-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
}}
.cp-sent-label {{
    font-size: 11px;
    color: {COLORS["text_secondary"]};
    width: 120px;
    flex-shrink: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
.cp-sent-track {{
    flex: 1;
    height: 5px;
    background: {COLORS["bg_page"]};
    border-radius: 3px;
    overflow: hidden;
}}
.cp-sent-fill-green {{
    height: 100%;
    background: {COLORS["green_500"]};
    border-radius: 3px;
}}
.cp-sent-fill-amber {{
    height: 100%;
    background: {COLORS["amber_400"]};
    border-radius: 3px;
}}
.cp-sent-fill-red {{
    height: 100%;
    background: {COLORS["red_400"]};
    border-radius: 3px;
}}
.cp-sent-val {{
    font-size: 11px;
    color: {COLORS["text_secondary"]};
    width: 34px;
    text-align: right;
    flex-shrink: 0;
}}
.cp-error {{
    background: {COLORS["bg_card"]};
    border-radius: 12px;
    border: 1px solid {COLORS["border_default"]};
    border-left: 3px solid {COLORS["red_400"]};
    padding: 14px 16px;
}}
.cp-error-title {{
    font-size: 14px;
    font-weight: 600;
    color: {COLORS["red_400"]};
    margin-bottom: 6px;
}}
.cp-error-msg {{
    font-size: 13px;
    color: {COLORS["text_secondary"]};
}}
.cp-page-title {{
    font-size: 18px;
    font-weight: 600;
    color: {COLORS["text_primary"]};
    letter-spacing: -0.02em;
    margin: 0 0 2px;
}}
.cp-page-subtitle {{
    font-size: 12px;
    color: {COLORS["text_muted"]};
    margin: 0 0 16px;
}}
.cp-empty {{
    font-size: 13px;
    color: {COLORS["text_muted"]};
    text-align: center;
    padding: 24px 0;
}}
.cp-report {{
    font-size: 13px;
    color: {COLORS["text_secondary"]};
    line-height: 1.7;
    white-space: pre-wrap;
}}
</style>"""


def _env_flag_enabled(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on", "y"}


@st.cache_resource
def get_pipeline(force_mock: bool = False) -> Any:
    """Build backend pipeline with mock fallback for offline verification."""
    if force_mock:
        return MockPipeline()

    try:
        pipeline = build_pipeline()
        if not hasattr(pipeline, "run"):
            raise TypeError("build_pipeline() returned an object without run().")
        return pipeline
    except Exception:
        return MockPipeline()


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def render_ranked_subreddits(subreddits: Sequence[Mapping[str, Any]]) -> None:
    """Render ranked subreddit results with clickable Reddit links."""
    rows = []
    for item in subreddits:
        rows.append(
            subreddit_row_html(
                rank=int(item.get("rank", 0)),
                name=str(item.get("subreddit", "")),
                url=str(item.get("url", "")),
                rerank_score=item.get("rerank_score"),
                reason=str(item.get("reason", "")),
            )
        )

    body = "".join(rows) if rows else '<p class="cp-empty">No communities found for this query.</p>'
    card_html = (
        '<div class="cp-card">'
        '<div class="cp-card-title">Recommended communities</div>'
        f"{body}"
        "</div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


def render_strategy_report(report: str) -> None:
    """Render the generated audience strategy report in the UI."""
    text = report.strip() if report.strip() else "No report available."
    report_html = (
        '<div class="cp-card">'
        '<div class="cp-card-title">Strategy report</div>'
        f'<div class="cp-report">{escape(text)}</div>'
        "</div>"
    )
    st.markdown(report_html, unsafe_allow_html=True)


def render_metrics(data: Mapping[str, Any]) -> None:
    """Render four summary metrics from adapted payload."""
    subreddits = data["ranked_subreddits"]
    sentiment_scores = data["sentiment_scores"]
    meta = data["meta"]

    top_score = _as_float(subreddits[0].get("rerank_score")) if subreddits else 0.0
    top_name = f'r/{subreddits[0]["subreddit"]}' if subreddits else "-"
    avg_sentiment = sum(sentiment_scores.values()) / len(sentiment_scores) if sentiment_scores else 0.0
    latency_s = f'{meta["latency_ms"] / 1000:.1f}s'

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            metric_card_html("Subreddits found", str(len(subreddits)), f'from {meta["retrieval_top_k"]} retrieved'),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(metric_card_html("Top rerank score", f"{top_score:.2f}", top_name), unsafe_allow_html=True)
    with c3:
        st.markdown(
            metric_card_html("Avg sentiment", f"{avg_sentiment:+.2f}", "across communities"),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(metric_card_html("Latency", latency_s, "end-to-end", sub_up=False), unsafe_allow_html=True)


def render_sentiment(sentiment_scores: Mapping[str, float]) -> None:
    """Render sentiment bars for subreddit-level scores."""
    bars = [sentiment_bar_html(name, score) for name, score in sentiment_scores.items()]
    body = "".join(bars) if bars else '<p class="cp-empty">No sentiment scores available.</p>'
    card_html = (
        '<div class="cp-card">'
        '<div class="cp-card-title">Community sentiment</div>'
        f"{body}"
        "</div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


def main() -> None:
    """Run the Streamlit application entrypoint."""
    st.set_page_config(
        page_title="CreatorPal",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    if "last_result" not in st.session_state:
        st.session_state["last_result"] = None
    if "last_error" not in st.session_state:
        st.session_state["last_error"] = None

    force_mock = _env_flag_enabled("CREATORPAL_USE_MOCK_PIPELINE")
    pipeline = get_pipeline(force_mock=force_mock)
    using_mock = isinstance(pipeline, MockPipeline)

    with st.sidebar:
        st.markdown("**CreatorPal**")
        st.caption("YouTube -> Reddit audience intelligence")

    st.markdown('<p class="cp-page-title">CreatorPal</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="cp-page-subtitle">YouTube -> Reddit audience intelligence</p>',
        unsafe_allow_html=True,
    )

    with st.form("query_form"):
        col_a, col_b = st.columns([2, 1])
        with col_a:
            channel_or_query = st.text_input(
                "Channel or topic",
                placeholder="https://youtube.com/@channel or a topic keyword",
            )
        with col_b:
            user_query = st.text_input(
                "Your goal (optional)",
                placeholder="e.g. grow subscribers in EU",
            )
        submitted = st.form_submit_button("Analyze", use_container_width=False)

    if submitted:
        query = channel_or_query.strip()
        goal = user_query.strip() or None
        if not query:
            st.warning("Please enter a YouTube channel URL or topic keyword.")
        else:
            try:
                with st.spinner("Analyzing..."):
                    raw = pipeline.run(channel_or_query=query, user_query=goal)
                st.session_state["last_result"] = adapt(raw)
                st.session_state["last_error"] = None
            except Exception as exc:
                st.session_state["last_error"] = str(exc)

    if using_mock:
        if force_mock:
            st.info("Using mock pipeline for offline verification (CREATORPAL_USE_MOCK_PIPELINE=1).")
        else:
            st.info("Backend pipeline is not ready. Falling back to mock pipeline for offline verification.")

    error_message = st.session_state.get("last_error")
    if error_message:
        st.markdown(error_card_html(error_message), unsafe_allow_html=True)

    data = st.session_state.get("last_result")
    if not data:
        return

    render_metrics(data)
    col_left, col_right = st.columns([1, 1])
    with col_left:
        render_ranked_subreddits(data["ranked_subreddits"])
    with col_right:
        render_sentiment(data["sentiment_scores"])
        render_strategy_report(data["strategy_report"])


if __name__ == "__main__":
    main()
