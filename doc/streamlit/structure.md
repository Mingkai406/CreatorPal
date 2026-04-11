# CreatorPal — Frontend Structure (Python / Streamlit)

> Version: 1.1  
> Owner: Ziqi (Person D)  
> Stack: Python 3.11 + Streamlit  
> Branch: `feature/frontend-deploy`

---

## Directory Layout

Only `app/` is in scope for Person D. Everything else is owned by other team members.

```
app/
├── streamlit_app.py      # single entry point — all UI logic lives here
└── helpers/
    ├── __init__.py
    ├── adapter.py        # pipeline contract validator + output normalizer
    └── components.py     # HTML-returning render functions (no st.* calls inside)
```

Run command (matches Dockerfile):
```bash
streamlit run app/streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

---

## `app/helpers/adapter.py`

Validates the raw `pipeline.run()` payload and normalizes it before any render.
Raises `ValueError` on contract violations so the UI can catch and display them cleanly.

```python
from __future__ import annotations
from typing import Any

REQUIRED_KEYS = [
    "input",
    "ranked_subreddits",
    "strategy_report",
    "pal_results",
    "sentiment_scores",
    "meta",
]


def adapt(raw: Any) -> dict:
    """
    Validate and normalize pipeline.run() output.

    Raises:
        ValueError: if a required top-level key is missing.

    Returns:
        Normalized payload dict safe to pass to render functions.
    """
    if not isinstance(raw, dict):
        raise ValueError("Pipeline returned a non-dict response.")

    for key in REQUIRED_KEYS:
        if key not in raw:
            raise ValueError(f'Contract violation: missing required key "{key}".')

    raw["ranked_subreddits"] = [
        _normalize_subreddit(item) for item in raw["ranked_subreddits"]
    ]

    return raw


def _normalize_subreddit(item: dict) -> dict:
    """Strip r/ prefix, fill missing URL, coerce invalid scores to None."""
    item = dict(item)  # shallow copy — don't mutate original

    # Normalize name
    item["subreddit"] = item.get("subreddit", "").replace("r/", "").strip()

    # URL fallback (Karl's hard requirement)
    if not item.get("url"):
        item["url"] = f"https://www.reddit.com/r/{item['subreddit']}/"

    # Coerce scores
    for field in ("retrieval_score", "rerank_score", "sentiment_score"):
        val = item.get(field)
        item[field] = val if isinstance(val, (int, float)) else None

    return item
```

---

## `app/helpers/components.py`

Pure functions: take data, return HTML strings. No `st.*` calls here.
All CSS classes reference `UIUX.md`. Import `COLORS` if needed for inline styles.

```python
from __future__ import annotations

# ── Metric card ────────────────────────────────────────────────────────────

def metric_card_html(label: str, value: str, sub: str, sub_up: bool = True) -> str:
    sub_class = "cp-metric-sub-up" if sub_up else "cp-metric-sub-neutral"
    return (
        f'<div class="cp-metric">'
        f'<div class="cp-metric-label">{label}</div>'
        f'<div class="cp-metric-value">{value}</div>'
        f'<div class="{sub_class}">{sub}</div>'
        f'</div>'
    )


# ── Subreddit row ──────────────────────────────────────────────────────────

def subreddit_row_html(
    rank: int,
    name: str,
    url: str,
    rerank_score: float | None,
    reason: str,
) -> str:
    score_pct = f"{(rerank_score or 0) * 100:.0f}%"
    score_label = f"{rerank_score:.2f}" if rerank_score is not None else "N/A"
    safe_reason = (reason[:80] + "…") if len(reason) > 80 else reason
    return (
        f'<div class="cp-sub-row">'
        f'  <div class="cp-rank">{rank}</div>'
        f'  <div class="cp-sub-info">'
        f'    <a class="cp-sub-name" href="{url}" target="_blank">r/{name}</a>'
        f'    <div class="cp-sub-reason">{safe_reason}</div>'
        f'  </div>'
        f'  <div class="cp-score-wrap">'
        f'    <div class="cp-score-label">{score_label}</div>'
        f'    <div class="cp-score-track">'
        f'      <div class="cp-score-fill" style="width:{score_pct}"></div>'
        f'    </div>'
        f'  </div>'
        f'  <a class="cp-open-link" href="{url}" target="_blank">↗</a>'
        f'</div>'
    )


# ── Sentiment bar row ──────────────────────────────────────────────────────

def sentiment_bar_html(subreddit: str, score: float) -> str:
    pct = f"{min(abs(score), 1.0) * 100:.0f}%"
    if score >= 0.5:
        fill_class = "cp-sent-fill-green"
    elif score >= 0.2:
        fill_class = "cp-sent-fill-amber"
    else:
        fill_class = "cp-sent-fill-red"
    label = subreddit if subreddit.startswith("r/") else f"r/{subreddit}"
    return (
        f'<div class="cp-sent-row">'
        f'  <div class="cp-sent-label">{label}</div>'
        f'  <div class="cp-sent-track">'
        f'    <div class="{fill_class}" style="width:{pct}"></div>'
        f'  </div>'
        f'  <div class="cp-sent-val">{score:+.2f}</div>'
        f'</div>'
    )


# ── Error card ─────────────────────────────────────────────────────────────

def error_card_html(message: str) -> str:
    return (
        f'<div class="cp-error">'
        f'  <div class="cp-error-title">Pipeline error</div>'
        f'  <div class="cp-error-msg">{message}</div>'
        f'</div>'
    )
```

---

## `app/streamlit_app.py`

Single entry point. All `st.*` calls live here. Render functions are imported from
`helpers/components.py`; pipeline is imported from `src/pipeline.py`.

```python
from __future__ import annotations

import streamlit as st
from src.pipeline import Pipeline   # swap for mock during offline dev
from app.helpers.adapter import adapt
from app.helpers.components import (
    metric_card_html,
    subreddit_row_html,
    sentiment_bar_html,
    error_card_html,
)

# ── Color tokens (source of truth — matches UIUX.md) ──────────────────────

COLORS: dict[str, str] = {
    "bg_page":        "#EEF2F7",
    "bg_card":        "#FFFFFF",
    "bg_input":       "#F8FAFC",
    "bg_badge_blue":  "#EFF6FF",
    "bg_badge_green": "#ECFDF5",
    "border_default": "#E2E8F0",
    "border_subtle":  "#F1F5F9",
    "text_primary":   "#0F172A",
    "text_secondary": "#475569",
    "text_muted":     "#94A3B8",
    "text_link":      "#3B82F6",
    "blue_500":       "#3B82F6",
    "green_500":      "#10B981",
    "amber_400":      "#F59E0B",
    "red_400":        "#F87171",
}

GLOBAL_CSS: str = f"""<style>
[data-testid="stAppViewContainer"] {{ background: {COLORS["bg_page"]}; }}
[data-testid="stSidebar"] {{ background: {COLORS["bg_card"]}; border-right: 1px solid {COLORS["border_default"]}; }}
[data-testid="block-container"] {{ padding: 1.5rem 2rem; max-width: 1100px; }}
footer, #MainMenu {{ display: none; }}
body, .stMarkdown {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.cp-card {{ background:{COLORS["bg_card"]}; border-radius:12px; border:1px solid {COLORS["border_default"]}; padding:14px 16px; margin-bottom:10px; }}
.cp-card-title {{ font-size:14px; font-weight:600; color:{COLORS["text_primary"]}; margin:0 0 12px; }}
.cp-metric {{ background:{COLORS["bg_card"]}; border-radius:12px; border:1px solid {COLORS["border_default"]}; padding:12px 14px; }}
.cp-metric-label {{ font-size:11px; font-weight:500; color:{COLORS["text_muted"]}; letter-spacing:.03em; text-transform:uppercase; margin-bottom:6px; }}
.cp-metric-value {{ font-size:22px; font-weight:700; color:{COLORS["text_primary"]}; letter-spacing:-.03em; line-height:1; }}
.cp-metric-sub-up {{ font-size:11px; color:{COLORS["green_500"]}; margin-top:4px; }}
.cp-metric-sub-neutral {{ font-size:11px; color:{COLORS["text_muted"]}; margin-top:4px; }}
.cp-sub-row {{ display:flex; align-items:center; gap:10px; padding:8px 0; border-bottom:.5px solid {COLORS["border_subtle"]}; }}
.cp-sub-row:last-child {{ border-bottom:none; }}
.cp-rank {{ font-size:13px; font-weight:700; color:{COLORS["text_muted"]}; width:18px; text-align:right; flex-shrink:0; }}
.cp-sub-info {{ flex:1; min-width:0; }}
.cp-sub-name {{ font-size:13px; font-weight:600; color:{COLORS["text_link"]}; text-decoration:none; }}
.cp-sub-name:hover {{ text-decoration:underline; }}
.cp-sub-reason {{ font-size:11px; color:{COLORS["text_muted"]}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.cp-score-wrap {{ width:56px; flex-shrink:0; }}
.cp-score-label {{ font-size:10px; color:{COLORS["text_muted"]}; text-align:right; margin-bottom:2px; }}
.cp-score-track {{ height:4px; background:{COLORS["bg_page"]}; border-radius:2px; overflow:hidden; }}
.cp-score-fill {{ height:100%; background:{COLORS["blue_500"]}; border-radius:2px; }}
.cp-open-link {{ font-size:11px; color:{COLORS["text_link"]}; text-decoration:none; flex-shrink:0; padding-left:8px; }}
.cp-sent-row {{ display:flex; align-items:center; gap:8px; margin-top:8px; }}
.cp-sent-label {{ font-size:11px; color:{COLORS["text_secondary"]}; width:120px; flex-shrink:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.cp-sent-track {{ flex:1; height:5px; background:{COLORS["bg_page"]}; border-radius:3px; overflow:hidden; }}
.cp-sent-fill-green {{ height:100%; background:{COLORS["green_500"]}; border-radius:3px; }}
.cp-sent-fill-amber {{ height:100%; background:{COLORS["amber_400"]}; border-radius:3px; }}
.cp-sent-fill-red {{ height:100%; background:{COLORS["red_400"]}; border-radius:3px; }}
.cp-sent-val {{ font-size:11px; color:{COLORS["text_secondary"]}; width:34px; text-align:right; flex-shrink:0; }}
.cp-error {{ background:{COLORS["bg_card"]}; border-radius:12px; border:1px solid {COLORS["border_default"]}; border-left:3px solid {COLORS["red_400"]}; padding:14px 16px; }}
.cp-error-title {{ font-size:14px; font-weight:600; color:{COLORS["red_400"]}; margin-bottom:6px; }}
.cp-error-msg {{ font-size:13px; color:{COLORS["text_secondary"]}; }}
</style>"""


# ── Pipeline (cached singleton) ────────────────────────────────────────────

@st.cache_resource
def get_pipeline() -> Pipeline:
    return Pipeline()


# ── Render helpers ─────────────────────────────────────────────────────────

def render_metrics(data: dict) -> None:
    """Four-column metric row derived from pipeline payload."""
    subreddits = data["ranked_subreddits"]
    sentiment_scores = data["sentiment_scores"]
    meta = data["meta"]

    top_score = subreddits[0]["rerank_score"] if subreddits else 0.0
    top_name = f'r/{subreddits[0]["subreddit"]}' if subreddits else "—"

    avg_sentiment = (
        sum(sentiment_scores.values()) / len(sentiment_scores)
        if sentiment_scores else 0.0
    )
    latency_s = f'{meta["latency_ms"] / 1000:.1f}s'

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card_html("Subreddits found", str(len(subreddits)), f"from {meta['retrieval_top_k']} retrieved"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card_html("Top rerank score", f"{top_score:.2f}", top_name), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card_html("Avg sentiment", f"{avg_sentiment:+.2f}", "across communities"), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card_html("Latency", latency_s, "end-to-end", sub_up=False), unsafe_allow_html=True)


def render_ranked_subreddits(subreddits: list[dict]) -> None:
    """Left column: ranked list card."""
    st.markdown('<div class="cp-card"><div class="cp-card-title">Recommended communities</div>', unsafe_allow_html=True)
    if not subreddits:
        st.markdown('<p style="font-size:13px;color:#94A3B8;text-align:center;padding:24px 0">No communities found for this query.</p>', unsafe_allow_html=True)
    else:
        for item in subreddits:
            st.markdown(
                subreddit_row_html(
                    rank=item["rank"],
                    name=item["subreddit"],
                    url=item["url"],
                    rerank_score=item["rerank_score"],
                    reason=item.get("reason", ""),
                ),
                unsafe_allow_html=True,
            )
    st.markdown('</div>', unsafe_allow_html=True)


def render_sentiment(sentiment_scores: dict[str, float]) -> None:
    """Right column top: sentiment bars card."""
    st.markdown('<div class="cp-card"><div class="cp-card-title">Community sentiment</div>', unsafe_allow_html=True)
    for subreddit, score in sentiment_scores.items():
        st.markdown(sentiment_bar_html(subreddit, score), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_strategy_report(report: str) -> None:
    """Right column bottom: strategy report card."""
    st.markdown('<div class="cp-card"><div class="cp-card-title">Strategy report</div>', unsafe_allow_html=True)
    if report:
        st.markdown(f'<div class="cp-report">{report}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="font-size:13px;color:#94A3B8">No report available.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="CreatorPal",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("**CreatorPal**")
        st.caption("YouTube → Reddit audience intelligence")

    # Page header
    st.markdown('<p class="cp-page-title">CreatorPal</p>', unsafe_allow_html=True)
    st.markdown('<p class="cp-page-subtitle">YouTube → Reddit audience intelligence</p>', unsafe_allow_html=True)

    # Input card
    with st.form("query_form"):
        col_a, col_b = st.columns([2, 1])
        with col_a:
            channel_or_query = st.text_input(
                "Channel or topic",
                placeholder="https://youtube.com/@mkbhd or a topic keyword",
            )
        with col_b:
            user_query = st.text_input(
                "Your goal (optional)",
                placeholder="e.g. grow subscribers in EU",
            )
        submitted = st.form_submit_button("Analyze →", use_container_width=False)

    if submitted and not channel_or_query.strip():
        st.warning("Please enter a YouTube channel URL or topic keyword.")
        return

    # Run pipeline
    if submitted and channel_or_query.strip():
        pipeline = get_pipeline()
        try:
            with st.spinner("Analyzing…"):
                raw = pipeline.run(
                    channel_or_query=channel_or_query.strip(),
                    user_query=user_query.strip() or None,
                )
            data = adapt(raw)
            st.session_state["last_result"] = data
        except Exception as exc:
            st.markdown(error_card_html(str(exc)), unsafe_allow_html=True)
            return

    # Render results from session state (persists across reruns)
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
```

---

## Mock Pipeline (offline dev)

Use this during development before `src/pipeline.py` is ready.
Drop it in `app/helpers/mock_pipeline.py` and swap the import in `streamlit_app.py`.

```python
# app/helpers/mock_pipeline.py
import time
from datetime import datetime, timezone

class Pipeline:
    def run(self, channel_or_query: str, user_query: str | None = None) -> dict:
        time.sleep(1.2)  # simulate latency
        return {
            "input": {
                "channel_or_query": channel_or_query,
                "user_query": user_query,
                "resolved_mode": "channel",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "ranked_subreddits": [
                {"rank": 1, "subreddit": "hardware",        "url": "https://www.reddit.com/r/hardware/",        "retrieval_score": 0.91, "rerank_score": 0.94, "reason": "GPU/CPU benchmark overlap, shares YT reviews in weekly threads.", "evidence": [], "sentiment_score": 0.72},
                {"rank": 2, "subreddit": "androidquestions","url": "https://www.reddit.com/r/androidquestions/","retrieval_score": 0.85, "rerank_score": 0.88, "reason": "Phone comparisons, frequently links reviews when helping users.", "evidence": [], "sentiment_score": 0.61},
                {"rank": 3, "subreddit": "buildapc",         "url": "https://www.reddit.com/r/buildapc/",         "retrieval_score": 0.79, "rerank_score": 0.81, "reason": "High component discussion, frequent video citations.",           "evidence": [], "sentiment_score": 0.55},
                {"rank": 4, "subreddit": "gadgets",          "url": "https://www.reddit.com/r/gadgets/",          "retrieval_score": 0.73, "rerank_score": 0.76, "reason": "Broad tech news feed, active YouTube link sharing.",            "evidence": [], "sentiment_score": 0.38},
                {"rank": 5, "subreddit": "apple",            "url": "https://www.reddit.com/r/apple/",            "retrieval_score": 0.70, "rerank_score": 0.72, "reason": "iOS/Mac product reviews, strong brand overlap.",                 "evidence": [], "sentiment_score": 0.44},
            ],
            "strategy_report": "## Audience Expansion Opportunity\n\nYour channel has strong fit with hardware-focused subreddits. r/hardware scores highest due to its culture of sharing benchmark videos in weekly threads.\n\n## Recommended Action\n\nPrioritize r/hardware and r/buildapc for initial outreach.",
            "pal_results": {
                "summary": "Top communities show consistent positive sentiment.",
                "metrics": {"avg_rerank_score": 0.82, "top_subreddit": "r/hardware"},
            },
            "sentiment_scores": {
                "r/hardware": 0.72, "r/androidquestions": 0.61,
                "r/buildapc": 0.55, "r/gadgets": 0.38, "r/apple": 0.44,
            },
            "meta": {"retrieval_top_k": 50, "rerank_top_k": 10, "latency_ms": 1200},
        }
```

---

## Implementation Order

1. `helpers/adapter.py` — contract validation + URL fallback
2. `helpers/components.py` — all HTML-returning functions
3. `streamlit_app.py` — wire up with mock pipeline, verify all render paths
4. Swap mock for real `src.pipeline.Pipeline` once Person A confirms interface
5. Docker path validation (`docker-startup deploy`)
