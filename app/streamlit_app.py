"""CreatorPal Streamlit frontend aligned to strict dashboard design."""

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
    "bg_page": "#E2E8F0",
    "bg_card": "#FFFFFF",
    "bg_input": "#F8FAFC",
    "bg_badge_blue": "#EFF6FF",
    "bg_badge_green": "#ECFDF5",
    "border_default": "#E2E8F0",
    "border_subtle": "#F1F5F9",
    "text_primary": "#1C1C1E",
    "text_secondary": "#3C3C43",
    "text_muted": "#8E8E93",
    "text_link": "#3B82F6",
    "blue_500": "#3B82F6",
    "blue_hover": "#2563EB",
    "green_500": "#10B981",
    "amber_400": "#F59E0B",
    "red_400": "#F87171",
    "rank_light": "#CBD5E1",
}

GLOBAL_CSS = f"""<style>
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="collapsedControl"] {{
    display: none !important;
}}

.stApp {{
    background-color: {COLORS["bg_page"]} !important;
}}

[data-testid="stSidebar"] {{
    background: {COLORS["bg_card"]} !important;
    border-right: 1px solid {COLORS["border_default"]} !important;
    min-width: 60px !important;
    max-width: 60px !important;
    width: 60px !important;
}}

section[data-testid="stSidebar"] {{
    width: 60px !important;
}}

[data-testid="stSidebar"] > div:first-child {{
    width: 60px !important;
    padding: 10px 6px !important;
}}

[data-testid="stSidebarNav"] {{
    display: none !important;
}}

.block-container {{
    padding: 2rem 2.5rem 2.25rem !important;
    max-width: 1200px !important;
}}

[data-testid="stForm"] {{
    background: rgba(255, 255, 255, 0.78) !important;
    border: 1px solid rgba(255, 255, 255, 0.95) !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06) !important;
    padding: 16px 18px 10px !important;
    margin-bottom: 0 !important;
}}

[data-testid="stForm"] + div {{
    margin-top: 0 !important;
}}

[data-testid="stTextInput"] input {{
    background: rgba(255, 255, 255, 0.60) !important;
    border: 1px solid rgba(255, 255, 255, 0.90) !important;
    border-radius: 8px !important;
    color: #1C1C1E !important;
    font-size: 13px !important;
    padding: 9px 14px !important;
}}

[data-testid="stTextInput"] label p {{
    font-size: 11px !important;
    font-weight: 500 !important;
    color: #6E6E73 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}}

[data-testid="stTextInput"] input::placeholder {{
    color: #C7C7CC !important;
}}

[data-testid="stTextInput"] input:focus {{
    background: rgba(255, 255, 255, 0.85) !important;
    border-color: {COLORS["blue_500"]} !important;
    box-shadow: none !important;
}}

[data-testid="stFormSubmitButton"] button {{
    background-color: #3B82F6 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 9px 0 !important;
    width: 100% !important;
}}

[data-testid="stFormSubmitButton"] button:hover {{
    background: {COLORS["blue_hover"]} !important;
    border: none !important;
}}

[data-testid="stFormSubmitButton"] button p {{
    color: #FFFFFF !important;
}}

[data-testid="stCaptionContainer"] {{
    margin: 0 !important;
    padding: 0 !important;
}}

[data-testid="stCaptionContainer"] p {{
    font-size: 11px !important;
    color: #8E8E93 !important;
    margin: 4px 0 0 !important;
    line-height: 1.2 !important;
}}

[data-testid="stCaptionContainer"] + div {{
    margin-top: 0 !important;
}}

.cp-sidebar-shell {{
    height: calc(100vh - 24px);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
}}

.cp-sidebar-icons {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}}

.cp-sidebar-btn {{
    width: 34px;
    height: 34px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.cp-page-header {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 16px;
}}

.cp-page-title {{
    font-size: 24px;
    font-weight: 700;
    color: {COLORS["text_primary"]};
    letter-spacing: -0.025em;
    margin: 0 0 2px;
}}

.cp-page-subtitle {{
    font-size: 14px;
    color: #6E6E73;
    margin: 0;
}}

.cp-badge {{
    display: inline-block;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 9px;
    border-radius: 20px;
}}

.cp-badge-blue {{
    background: {COLORS["bg_badge_blue"]};
    color: {COLORS["blue_500"]};
}}

.cp-badge-green {{
    background: {COLORS["bg_badge_green"]};
    color: {COLORS["green_500"]};
}}

.cp-field-label {{
    font-size: 11px;
    font-weight: 500;
    color: {COLORS["text_muted"]};
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
}}

.cp-btn-spacer {{
    height: 26px;
}}

.cp-card {{
    background: rgba(255, 255, 255, 0.78) !important;
    border: 1px solid rgba(255, 255, 255, 0.95) !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    padding: 16px 18px;
}}

.cp-card-fill-col {{
    height: 100%;
}}

.cp-card,
.cp-metric {{
    transition:
        transform 220ms cubic-bezier(0.34, 1.56, 0.64, 1),
        box-shadow 220ms ease;
    will-change: transform;
}}

.cp-card:hover,
.cp-metric:hover {{
    transform: scale(1.018);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08) !important;
}}

.cp-results-grid {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 24px;
    align-items: stretch;
}}

.cp-results-col {{
    min-width: 0;
}}

.cp-results-right {{
    display: flex;
    flex-direction: column;
    gap: 14px;
}}

.cp-card-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 14px;
}}

.cp-card-header-row {{
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    margin-bottom: 4px;
}}

.cp-card-title {{
    font-size: 16px;
    font-weight: 600;
    color: {COLORS["text_primary"]};
}}

.cp-card-subtitle {{
    font-size: 13px;
    color: {COLORS["text_muted"]};
}}

.cp-metric {{
    background: rgba(255, 255, 255, 0.78) !important;
    border: 1px solid rgba(255, 255, 255, 0.95) !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    padding: 14px 16px;
}}

.cp-metric-label {{
    font-size: 12px;
    font-weight: 500;
    color: #6E6E73;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}}

.cp-metric-value {{
    font-size: 32px;
    font-weight: 700;
    color: {COLORS["text_primary"]};
    letter-spacing: -0.03em;
    line-height: 1 !important;
}}

.cp-metric-sub-up {{
    font-size: 13px;
    color: {COLORS["green_500"]};
    margin-top: 5px;
}}

.cp-metric-sub-neutral {{
    font-size: 13px;
    color: {COLORS["text_muted"]};
    margin-top: 5px;
}}

.cp-sub-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    border-radius: 8px;
    margin: 0 -8px;
    padding: 10px 8px;
    transition: background 100ms ease;
}}

.cp-sub-row + .cp-sub-row {{
    border-top: 0.5px solid rgba(0, 0, 0, 0.05);
}}

.cp-sub-row:hover {{
    background: rgba(255, 255, 255, 0.60);
}}

.cp-rank {{
    width: 20px;
    flex-shrink: 0;
    text-align: right;
    font-size: 15px;
    font-weight: 700;
    color: {COLORS["rank_light"]};
}}

.cp-sub-info {{
    flex: 1;
    min-width: 0;
}}

.cp-sub-name {{
    font-size: 15px;
    font-weight: 600;
    color: {COLORS["text_link"]};
    text-decoration: none !important;
}}

.cp-sub-name:hover {{
    text-decoration: underline !important;
}}

.cp-sub-reason {{
    font-size: 13px;
    color: {COLORS["text_muted"]};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

.cp-score-wrap {{
    width: 72px;
    flex-shrink: 0;
    text-align: right;
}}

.cp-score-num {{
    font-size: 13px;
    color: #636366;
    margin-bottom: 3px;
}}

.cp-score-track {{
    height: 4px;
    background: rgba(59, 130, 246, 0.10);
    border-radius: 2px;
    overflow: hidden;
}}

.cp-score-fill {{
    height: 100%;
    background: #3B82F6;
}}

a[href*="reddit.com"]:hover {{
    background: rgba(59, 130, 246, 0.18) !important;
}}

.cp-sent-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}}

.cp-sent-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 5px 0;
}}

.cp-sent-label {{
    width: 130px;
    flex-shrink: 0;
    font-size: 13px;
    color: {COLORS["text_secondary"]};
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}

.cp-sent-track {{
    flex: 1;
    height: 5px !important;
    background: rgba(0, 0, 0, 0.07);
    border-radius: 3px;
    overflow: hidden;
}}

.cp-sent-fill-green {{
    height: 100% !important;
    background: #10B981;
}}

.cp-sent-fill-amber {{
    height: 100% !important;
    background: #F59E0B;
}}

.cp-sent-fill-red {{
    height: 100% !important;
    background: #F87171;
}}

.cp-sent-val {{
    width: 38px;
    flex-shrink: 0;
    text-align: right;
    font-size: 13px;
    font-weight: 500;
    color: {COLORS["text_secondary"]};
}}

.cp-report {{
    font-size: 14px;
    color: {COLORS["text_secondary"]};
    line-height: 1.75;
}}

.cp-report h2 {{
    font-size: 14px;
    font-weight: 600;
    color: {COLORS["text_primary"]};
    margin: 14px 0 6px;
}}

.cp-report h2:first-child {{
    margin-top: 0;
}}

.cp-report p {{
    margin: 0 0 10px;
}}

.cp-error {{
    background: {COLORS["bg_card"]};
    border: 1px solid {COLORS["border_default"]};
    border-left: 3px solid {COLORS["red_400"]};
    border-radius: 12px;
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

.cp-empty {{
    text-align: center;
    color: {COLORS["text_muted"]};
    font-size: 13px;
    padding: 24px 0;
}}

[data-testid="stTextInput"] input, [data-testid="stFormSubmitButton"] button {{
    box-shadow: none !important;
}}

[data-testid="stButton"] button {{
    background: transparent !important;
    border: 1px solid rgba(0, 0, 0, 0.12) !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    color: #6E6E73 !important;
    padding: 4px 12px !important;
    margin-bottom: 12px !important;
}}

[data-testid="stButton"] button:hover {{
    background: rgba(255, 255, 255, 0.5) !important;
}}
</style>"""


def _env_flag_enabled(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on", "y"}


@st.cache_resource
def get_pipeline(force_mock: bool = False) -> Any:
    """Return real pipeline if available, otherwise a mock pipeline."""
    if force_mock:
        return MockPipeline(runtime_delay_s=1.2)
    try:
        pipeline = build_pipeline()
        if not hasattr(pipeline, "run"):
            raise TypeError("build_pipeline() returned an object without run().")
        return pipeline
    except Exception:
        return MockPipeline(runtime_delay_s=1.2)


def _svg_icon(path: str, stroke: str, bg: str) -> str:
    return (
        f'<div class="cp-sidebar-btn" style="background:{bg}">'
        f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" '
        f'stroke="{stroke}" stroke-width="1.8">{path}</svg>'
        f"</div>"
    )


def render_sidebar() -> None:
    """Render fixed-width visual icon sidebar."""
    top_icons = "".join(
        [
            _svg_icon(
                '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>'
                '<polyline points="9 22 9 12 15 12 15 22"/>',
                stroke=COLORS["blue_500"],
                bg=COLORS["bg_page"],
            ),
            _svg_icon(
                '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
                stroke=COLORS["text_muted"],
                bg="transparent",
            ),
            _svg_icon(
                '<line x1="18" y1="20" x2="18" y2="10"/>'
                '<line x1="12" y1="20" x2="12" y2="4"/>'
                '<line x1="6" y1="20" x2="6" y2="14"/>',
                stroke=COLORS["text_muted"],
                bg="transparent",
            ),
            _svg_icon(
                '<circle cx="12" cy="12" r="3"/>'
                '<path d="M19.07 4.93a10 10 0 010 14.14"/>'
                '<path d="M4.93 4.93a10 10 0 000 14.14"/>',
                stroke=COLORS["text_muted"],
                bg="transparent",
            ),
        ]
    )
    user_icon = _svg_icon(
        '<circle cx="12" cy="8" r="4"/>'
        '<path d="M6 20v-2a4 4 0 014-4h4a4 4 0 014 4v2"/>',
        stroke=COLORS["text_muted"],
        bg="transparent",
    )

    with st.sidebar:
        st.markdown(
            '<div class="cp-sidebar-shell">'
            f'<div class="cp-sidebar-icons">{top_icons}</div>'
            f"<div>{user_icon}</div>"
            "</div>",
            unsafe_allow_html=True,
        )


def render_page_header() -> None:
    """Render compact dashboard header after results are available."""
    col_hdr, col_badge = st.columns([10, 1])
    with col_hdr:
        st.markdown(
            """
<div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
    <div style="width:32px;height:32px;border-radius:8px;background:#3B82F6;
                display:flex;align-items:center;justify-content:center;flex-shrink:0">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
             stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="23 7 16 12 23 17 23 7"/>
            <rect x="1" y="5" width="15" height="14" rx="2"/>
        </svg>
    </div>
    <div>
        <div style="font-size:18px;font-weight:700;color:#1C1C1E;letter-spacing:-.02em;line-height:1">
            CreatorPal
        </div>
        <div style="font-size:12px;color:#6E6E73;margin-top:1px">
            YouTube → Reddit audience intelligence
        </div>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )
    with col_badge:
        st.markdown(
            '<div style="padding-top:8px;text-align:right">'
            '<span class="cp-badge cp-badge-blue">Beta</span></div>',
            unsafe_allow_html=True,
        )


def render_idle_hero() -> tuple[str, str | None, bool]:
    """Render centered idle hero and return submitted query payload."""
    st.markdown("<div style='height:16vh'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([0.6, 2.8, 0.6])
    st.markdown(
        """
<style>
[data-testid="stForm"] {
    max-width: 680px !important;
    margin: 0 auto !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    with col:
        st.markdown(
            """
<div style="display:flex;flex-direction:column;align-items:center;margin-bottom:32px">
    <div style="
        width:72px;height:72px;border-radius:20px;
        background:#3B82F6;
        display:flex;align-items:center;justify-content:center;
        margin-bottom:18px;
    ">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none"
             stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="23 7 16 12 23 17 23 7"/>
            <rect x="1" y="5" width="15" height="14" rx="2"/>
        </svg>
    </div>
    <div style="font-size:36px;font-weight:700;color:#1C1C1E;letter-spacing:-.03em;margin-bottom:10px">
        CreatorPal
    </div>
    <div style="font-size:16px;color:#6E6E73;text-align:center;line-height:1.6;max-width:420px">
        Find the right Reddit communities for your YouTube channel
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

        with st.form("query_form", clear_on_submit=False):
            col_a, col_b, col_btn = st.columns([5, 4, 2], gap="small")
            with col_a:
                channel_or_query = st.text_input(
                    "Channel or topic",
                    placeholder="https://youtube.com/@channel",
                )
            with col_b:
                user_query = st.text_input(
                    "Your goal (optional)",
                    placeholder="e.g. grow subscribers in EU",
                )
            with col_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                submitted = st.form_submit_button("Analyze →", use_container_width=True)

        st.markdown(
            """
<div style="text-align:center;margin-top:14px;font-size:12px;color:#8E8E93">
    Powered by RAG · <span style="color:#3B82F6">FAISS</span> retrieval · cross-encoder reranking
</div>
""",
            unsafe_allow_html=True,
        )

    normalized_goal = user_query.strip() or None
    return channel_or_query, normalized_goal, submitted


def render_metrics(data: Mapping[str, Any]) -> None:
    """Render the four metric cards."""
    subreddits = data["ranked_subreddits"]
    sentiment_scores = data["sentiment_scores"]
    meta = data["meta"]

    top_score = float(subreddits[0]["rerank_score"]) if subreddits else 0.0
    top_name = f'r/{subreddits[0]["subreddit"]}' if subreddits else "-"
    avg_sentiment = sum(sentiment_scores.values()) / len(sentiment_scores) if sentiment_scores else 0.0
    latency_s = f'{meta["latency_ms"] / 1000:.1f}s'
    sentiment_sub = "Positive community" if avg_sentiment >= 0.2 else "Mixed community"

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        st.markdown(
            metric_card_html(
                "SUBREDDITS FOUND",
                str(len(subreddits)),
                f"↑ from {meta['retrieval_top_k']} retrieved",
                sub_up=True,
                container_style="border-top:3px solid #3B82F6 !important;",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            metric_card_html(
                "TOP RERANK SCORE",
                f"{top_score:.2f}",
                top_name,
                sub_up=True,
                container_style="border-top:3px solid #10B981 !important;",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            metric_card_html(
                "AVG SENTIMENT",
                f"{avg_sentiment:+.2f}",
                sentiment_sub,
                sub_up=True,
                container_style="border-top:3px solid #10B981 !important;",
            ),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            metric_card_html(
                "LATENCY",
                latency_s,
                "end-to-end",
                sub_up=False,
                container_style="border-top:3px solid #C7C7CC !important;",
            ),
            unsafe_allow_html=True,
        )


def _ranked_subreddits_card_html(subreddits: Sequence[Mapping[str, Any]]) -> str:
    """Build recommended communities card HTML."""
    top_items = list(subreddits)[:10]
    rows = "".join(
        subreddit_row_html(
            rank=int(item["rank"]),
            name=str(item["subreddit"]),
            url=str(item["url"]),
            rerank_score=item.get("rerank_score"),
            reason=str(item.get("reason", "")),
        )
        for item in top_items
    )
    if not rows:
        rows = '<p class="cp-empty">No communities found for this query.</p>'

    return (
        '<div class="cp-card cp-card-fill-col">'
        '<div style="display:flex;align-items:baseline;justify-content:space-between;'
        'padding-bottom:12px;border-bottom:1px solid rgba(0,0,0,0.06);margin-bottom:4px">'
        '<span class="cp-card-title">Recommended communities</span>'
        '<span class="cp-card-subtitle">top 10 by rerank</span>'
        "</div>"
        f"{rows}"
        "</div>"
    )


def render_ranked_subreddits(subreddits: Sequence[Mapping[str, Any]]) -> None:
    """Render recommended communities card."""
    st.markdown(_ranked_subreddits_card_html(subreddits), unsafe_allow_html=True)


def _sentiment_card_html(sentiment_scores: Mapping[str, float]) -> str:
    """Build community sentiment card HTML."""
    avg = sum(sentiment_scores.values()) / len(sentiment_scores) if sentiment_scores else 0.0
    badge = (
        '<span class="cp-badge cp-badge-green">Positive</span>'
        if avg >= 0.5
        else '<span class="cp-badge cp-badge-blue">Mixed</span>'
    )
    rows = "".join(sentiment_bar_html(name, score) for name, score in sentiment_scores.items())
    if not rows:
        rows = '<p class="cp-empty">No sentiment data available.</p>'

    return (
        '<div class="cp-card">'
        '<div style="display:flex;align-items:center;justify-content:space-between;'
        'padding-bottom:12px;border-bottom:1px solid rgba(0,0,0,0.06);margin-bottom:8px">'
        '<span class="cp-card-title">Community sentiment</span>'
        f"{badge}"
        "</div>"
        f"{rows}"
        "</div>"
    )


def _render_report_html(report: str) -> str:
    """Convert simple markdown-like report text into styled HTML."""
    if not report.strip():
        return '<p class="cp-empty">No report available.</p>'

    lines = report.splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{escape(' '.join(paragraph))}</p>")
            paragraph = []

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_paragraph()
            continue
        if line.startswith("## "):
            flush_paragraph()
            blocks.append(f"<h2>{escape(line[3:])}</h2>")
            continue
        paragraph.append(line)
    flush_paragraph()
    return "".join(blocks)


def render_sentiment(sentiment_scores: Mapping[str, float]) -> None:
    """Render community sentiment card."""
    st.markdown(_sentiment_card_html(sentiment_scores), unsafe_allow_html=True)


def _strategy_report_card_html(report: str) -> str:
    """Build strategy report card HTML."""
    return (
        '<div class="cp-card">'
        '<div style="padding-bottom:12px;border-bottom:1px solid rgba(0,0,0,0.06);margin-bottom:12px">'
        '<span class="cp-card-title">Strategy report</span>'
        "</div>"
        f'<div class="cp-report">{_render_report_html(report)}</div>'
        "</div>"
    )


def render_strategy_report(report: str) -> None:
    """Render strategy report card."""
    st.markdown(_strategy_report_card_html(report), unsafe_allow_html=True)


def render_results_grid(data: Mapping[str, Any]) -> None:
    """Render equal-height two-column results area with right-side stacked cards."""
    left = _ranked_subreddits_card_html(data["ranked_subreddits"])
    right_top = _sentiment_card_html(data["sentiment_scores"])
    right_bottom = _strategy_report_card_html(str(data["strategy_report"]))
    st.markdown(
        '<div class="cp-results-grid">'
        f'<div class="cp-results-col">{left}</div>'
        '<div class="cp-results-col cp-results-right">'
        f"{right_top}"
        f"{right_bottom}"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="CreatorPal", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    if "last_result" not in st.session_state:
        st.session_state["last_result"] = None
    if "last_error" not in st.session_state:
        st.session_state["last_error"] = None

    force_mock = _env_flag_enabled("CREATORPAL_USE_MOCK_PIPELINE")
    pipeline = get_pipeline(force_mock=force_mock)
    using_mock = isinstance(pipeline, MockPipeline)

    data: Mapping[str, Any] | None = st.session_state.get("last_result")
    error_message = st.session_state.get("last_error")

    if data is None:
        st.markdown('<style>[data-testid="stSidebar"]{display:none !important;}</style>', unsafe_allow_html=True)
        if error_message:
            st.markdown(error_card_html(error_message), unsafe_allow_html=True)

        channel_or_query, user_query, submitted = render_idle_hero()
        if submitted:
            query = channel_or_query.strip()
            if not query:
                st.warning("Please enter a YouTube channel URL or topic keyword.")
                return
            try:
                with st.spinner("Analyzing..."):
                    raw = pipeline.run(channel_or_query=query, user_query=user_query)
                st.session_state["last_result"] = adapt(raw)
                st.session_state["last_error"] = None
                st.rerun()
            except Exception as exc:
                st.session_state["last_error"] = str(exc)
                st.rerun()
        if using_mock:
            st.caption("Mock pipeline active — CREATORPAL_USE_MOCK_PIPELINE=1")
        return

    render_sidebar()
    render_page_header()
    if st.button("← New query", key="reset"):
        st.session_state["last_result"] = None
        st.session_state["last_error"] = None
        st.rerun()
    if using_mock:
        st.caption("Mock pipeline active — CREATORPAL_USE_MOCK_PIPELINE=1")
    if error_message:
        st.markdown(error_card_html(error_message), unsafe_allow_html=True)

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    render_metrics(data)
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    render_results_grid(data)


if __name__ == "__main__":
    main()
