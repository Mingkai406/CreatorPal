# CreatorPal — UI/UX Design Specification (Streamlit)

> Version: 1.1  
> Owner: Ziqi (Person D)  
> Based on: approved SaaS dashboard mockup (2026-04-11)  
> Stack: Python 3.11 + Streamlit

---

## 1. Streamlit CSS Injection Strategy

Streamlit does not expose its DOM directly. All custom styling goes through a single
`st.markdown(..., unsafe_allow_html=True)` call at the top of `main()`, injected inside
a `<style>` block. Components are then rendered using `st.markdown(html, unsafe_allow_html=True)`
for custom HTML elements, and native Streamlit widgets for inputs/buttons.

```python
# app/streamlit_app.py — top of main()
def inject_css() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
```

`GLOBAL_CSS` is defined as a module-level string constant in `streamlit_app.py`.

---

## 2. Color Tokens

Define once as a Python dict and interpolate into the CSS string.

```python
COLORS = {
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
```

Never hardcode hex values outside `COLORS`. Always use `COLORS["key"]` when building
the CSS string or inline HTML.

---

## 3. Global CSS Block

```python
GLOBAL_CSS = f"""
<style>
/* ── Reset ─────────────────────────────────────────────── */
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
footer, #MainMenu {{ display: none; }}

/* ── Typography ─────────────────────────────────────────── */
body, .stMarkdown, .stText {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: {COLORS["text_primary"]};
}}

/* ── Card surface ────────────────────────────────────────── */
.cp-card {{
    background: {COLORS["bg_card"]};
    border-radius: 12px;
    border: 1px solid {COLORS["border_default"]};
    padding: 14px 16px;
    margin-bottom: 10px;
}}

/* ── Card header ─────────────────────────────────────────── */
.cp-card-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}}
.cp-card-title {{
    font-size: 14px;
    font-weight: 600;
    color: {COLORS["text_primary"]};
    margin: 0;
}}

/* ── Metric card ─────────────────────────────────────────── */
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
.cp-metric-sub-up      {{ font-size: 11px; color: {COLORS["green_500"]}; margin-top: 4px; }}
.cp-metric-sub-neutral {{ font-size: 11px; color: {COLORS["text_muted"]}; margin-top: 4px; }}

/* ── Subreddit row ────────────────────────────────────────── */
.cp-sub-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 0.5px solid {COLORS["border_subtle"]};
}}
.cp-sub-row:last-child {{ border-bottom: none; }}
.cp-rank       {{ font-size: 13px; font-weight: 700; color: {COLORS["text_muted"]}; width: 18px; text-align: right; flex-shrink: 0; }}
.cp-sub-info   {{ flex: 1; min-width: 0; }}
.cp-sub-name   {{ font-size: 13px; font-weight: 600; color: {COLORS["text_link"]}; text-decoration: none; }}
.cp-sub-name:hover {{ text-decoration: underline; }}
.cp-sub-reason {{ font-size: 11px; color: {COLORS["text_muted"]}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cp-score-wrap  {{ width: 56px; flex-shrink: 0; }}
.cp-score-label {{ font-size: 10px; color: {COLORS["text_muted"]}; text-align: right; margin-bottom: 2px; }}
.cp-score-track {{ height: 4px; background: {COLORS["bg_page"]}; border-radius: 2px; overflow: hidden; }}
.cp-score-fill  {{ height: 100%; background: {COLORS["blue_500"]}; border-radius: 2px; }}
.cp-open-link   {{ font-size: 11px; color: {COLORS["text_link"]}; text-decoration: none; flex-shrink: 0; padding-left: 8px; }}

/* ── Sentiment bar ────────────────────────────────────────── */
.cp-sent-row   {{ display: flex; align-items: center; gap: 8px; margin-top: 8px; }}
.cp-sent-label {{ font-size: 11px; color: {COLORS["text_secondary"]}; width: 120px; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.cp-sent-track {{ flex: 1; height: 5px; background: {COLORS["bg_page"]}; border-radius: 3px; overflow: hidden; }}
.cp-sent-fill-green {{ height: 100%; background: {COLORS["green_500"]}; border-radius: 3px; }}
.cp-sent-fill-amber {{ height: 100%; background: {COLORS["amber_400"]}; border-radius: 3px; }}
.cp-sent-fill-red   {{ height: 100%; background: {COLORS["red_400"]}; border-radius: 3px; }}
.cp-sent-val   {{ font-size: 11px; color: {COLORS["text_secondary"]}; width: 34px; text-align: right; flex-shrink: 0; }}

/* ── Badge ────────────────────────────────────────────────── */
.cp-badge       {{ display: inline-block; font-size: 10px; font-weight: 500; padding: 2px 7px; border-radius: 20px; }}
.cp-badge-blue  {{ background: {COLORS["bg_badge_blue"]};  color: {COLORS["blue_500"]}; }}
.cp-badge-green {{ background: {COLORS["bg_badge_green"]}; color: {COLORS["green_500"]}; }}

/* ── Strategy report ──────────────────────────────────────── */
.cp-report {{ font-size: 13px; color: {COLORS["text_secondary"]}; line-height: 1.7; }}
.cp-report h2 {{ font-size: 13px; font-weight: 600; color: {COLORS["text_primary"]}; margin: 10px 0 4px; }}
.cp-report h2:first-child {{ margin-top: 0; }}
.cp-report p  {{ margin: 0 0 6px; }}

/* ── Error card ───────────────────────────────────────────── */
.cp-error {{
    background: {COLORS["bg_card"]};
    border-radius: 12px;
    border: 1px solid {COLORS["border_default"]};
    border-left: 3px solid {COLORS["red_400"]};
    padding: 14px 16px;
}}
.cp-error-title {{ font-size: 14px; font-weight: 600; color: {COLORS["red_400"]}; margin-bottom: 6px; }}
.cp-error-msg   {{ font-size: 13px; color: {COLORS["text_secondary"]}; }}

/* ── Page title ───────────────────────────────────────────── */
.cp-page-title    {{ font-size: 18px; font-weight: 600; color: {COLORS["text_primary"]}; letter-spacing: -0.02em; margin: 0 0 2px; }}
.cp-page-subtitle {{ font-size: 12px; color: {COLORS["text_muted"]}; margin: 0 0 16px; }}
</style>
"""
```

---

## 4. Layout with `st.columns`

Streamlit columns replace CSS grid. Use these fixed ratios to match the mockup.

```python
# Metrics row — 4 equal columns
c1, c2, c3, c4 = st.columns(4)

# Content row — ranked list : sentiment + report
col_left, col_right = st.columns([1, 1])
```

The 52px icon sidebar from the mockup is simplified to `st.sidebar` with the app name
and a brief tagline. Full icon nav is not worth the Streamlit workaround cost.

---

## 5. HTML Component Templates

These are pure Python functions returning HTML strings.
Always call via `st.markdown(html, unsafe_allow_html=True)`.

### Metric card

```python
def metric_card_html(label: str, value: str, sub: str, sub_up: bool = True) -> str:
    sub_class = "cp-metric-sub-up" if sub_up else "cp-metric-sub-neutral"
    return f"""
    <div class="cp-metric">
        <div class="cp-metric-label">{label}</div>
        <div class="cp-metric-value">{value}</div>
        <div class="{sub_class}">{sub}</div>
    </div>
    """
```

### Subreddit row

```python
def subreddit_row_html(rank: int, name: str, url: str,
                       rerank_score: float, reason: str) -> str:
    score_pct = f"{rerank_score * 100:.0f}%"
    score_label = f"{rerank_score:.2f}"
    safe_reason = reason[:80] + "…" if len(reason) > 80 else reason
    return f"""
    <div class="cp-sub-row">
        <div class="cp-rank">{rank}</div>
        <div class="cp-sub-info">
            <a class="cp-sub-name" href="{url}" target="_blank">r/{name}</a>
            <div class="cp-sub-reason">{safe_reason}</div>
        </div>
        <div class="cp-score-wrap">
            <div class="cp-score-label">{score_label}</div>
            <div class="cp-score-track">
                <div class="cp-score-fill" style="width:{score_pct}"></div>
            </div>
        </div>
        <a class="cp-open-link" href="{url}" target="_blank">↗</a>
    </div>
    """
```

### Sentiment bar row

```python
def sentiment_bar_html(subreddit: str, score: float) -> str:
    pct = f"{min(abs(score), 1.0) * 100:.0f}%"
    if score >= 0.5:
        fill_class = "cp-sent-fill-green"
    elif score >= 0.2:
        fill_class = "cp-sent-fill-amber"
    else:
        fill_class = "cp-sent-fill-red"
    label = subreddit if subreddit.startswith("r/") else f"r/{subreddit}"
    return f"""
    <div class="cp-sent-row">
        <div class="cp-sent-label">{label}</div>
        <div class="cp-sent-track">
            <div class="{fill_class}" style="width:{pct}"></div>
        </div>
        <div class="cp-sent-val">{score:+.2f}</div>
    </div>
    """
```

---

## 6. States

| State | What to render |
|---|---|
| Idle | Input card only, no results section visible |
| Loading | `st.spinner("Analyzing…")` wrapping `pipeline.run()` call |
| Success | Metrics row + content row (list + sentiment + report) |
| Exception | `cp-error` card with message; app stays interactive |
| Contract violation | Same error card; message names the missing key |
| Empty `ranked_subreddits` | List card with centered muted "No communities found." text |
| Missing URL on item | Auto-fill before render: `url = f"https://www.reddit.com/r/{item['subreddit']}/"` |

---

## 7. Do / Don't

| Do | Don't |
|---|---|
| Define all hex values in `COLORS` dict | Hardcode any hex inside component functions |
| Use `cp-` prefix on every custom CSS class | Use generic names like `.card` — clash with Streamlit internals |
| Wrap HTML blocks with `<div class="cp-card">` | Use `st.container()` borders (don't match the design) |
| `target="_blank"` on every Reddit link | Use `st.link_button` (loses custom styling) |
| Pass normalized payload to render functions | Let render functions call `pipeline.run()` directly |
| Show `cp-error` for all exception types | Let Streamlit display a raw Python traceback |
