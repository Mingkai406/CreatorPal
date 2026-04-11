"""Pure HTML builders for Streamlit-rendered frontend components."""

from __future__ import annotations

from html import escape


def metric_card_html(label: str, value: str, sub: str, sub_up: bool = True) -> str:
    """Build a metric card HTML block."""
    sub_class = "cp-metric-sub-up" if sub_up else "cp-metric-sub-neutral"
    return (
        f'<div class="cp-metric">'
        f'<div class="cp-metric-label">{escape(label)}</div>'
        f'<div class="cp-metric-value">{escape(value)}</div>'
        f'<div class="{sub_class}">{escape(sub)}</div>'
        f"</div>"
    )


def subreddit_row_html(
    rank: int,
    name: str,
    url: str,
    rerank_score: float | None,
    reason: str,
) -> str:
    """Build one subreddit row with score bar and link."""
    safe_score = _coerce_float(rerank_score)
    clamped_score = max(0.0, min(safe_score, 1.0))
    score_pct = f"{clamped_score * 100:.0f}%"
    score_label = f"{safe_score:.2f}" if rerank_score is not None else "N/A"
    safe_reason = reason if len(reason) <= 80 else f"{reason[:80]}..."
    safe_url = escape(url, quote=True)
    safe_name = escape(name)

    return (
        f'<div class="cp-sub-row">'
        f'<div class="cp-rank">{int(rank)}</div>'
        f'<div class="cp-sub-info">'
        f'<a class="cp-sub-name" href="{safe_url}" target="_blank">r/{safe_name}</a>'
        f'<div class="cp-sub-reason">{escape(safe_reason)}</div>'
        f"</div>"
        f'<div class="cp-score-wrap">'
        f'<div class="cp-score-label">{escape(score_label)}</div>'
        f'<div class="cp-score-track">'
        f'<div class="cp-score-fill" style="width:{score_pct}"></div>'
        f"</div>"
        f"</div>"
        f'<a class="cp-open-link" href="{safe_url}" target="_blank">Open</a>'
        f"</div>"
    )


def sentiment_bar_html(subreddit: str, score: float) -> str:
    """Build one sentiment bar row."""
    safe_score = _coerce_float(score)
    pct = f"{min(abs(safe_score), 1.0) * 100:.0f}%"
    if safe_score >= 0.5:
        fill_class = "cp-sent-fill-green"
    elif safe_score >= 0.2:
        fill_class = "cp-sent-fill-amber"
    else:
        fill_class = "cp-sent-fill-red"

    label = subreddit if subreddit.startswith("r/") else f"r/{subreddit}"
    return (
        f'<div class="cp-sent-row">'
        f'<div class="cp-sent-label">{escape(label)}</div>'
        f'<div class="cp-sent-track">'
        f'<div class="{fill_class}" style="width:{pct}"></div>'
        f"</div>"
        f'<div class="cp-sent-val">{safe_score:+.2f}</div>'
        f"</div>"
    )


def error_card_html(message: str) -> str:
    """Build the error card HTML."""
    return (
        f'<div class="cp-error">'
        f'<div class="cp-error-title">Pipeline error</div>'
        f'<div class="cp-error-msg">{escape(message)}</div>'
        f"</div>"
    )


def _coerce_float(value: float | None) -> float:
    """Coerce potentially missing numeric input to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

