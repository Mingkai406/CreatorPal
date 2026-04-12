# CreatorPal UI/UX Specification (Streamlit, Current Implementation)

Last Updated: 2026-04-12  
Applies To: `app/streamlit_app.py`, `app/helpers/components.py`

This spec reflects what the app renders today. It is not a future design draft.

## 1. UI States

The page is fully rerendered by Streamlit on each submit/reset/theme toggle.

```text
IDLE (hero) -> submit -> LOADING (spinner) -> DASHBOARD
DASHBOARD -> "← New query" -> IDLE
Any pipeline/adapter exception -> store last_error -> rerun -> show error card
```

State ownership:
- `st.session_state["last_result"]`
- `st.session_state["last_error"]`
- `st.session_state["dark_mode"]`

## 2. Theme System

Implementation model:
- `LIGHT_CSS` + `DARK_CSS` constants
- `get_css(dark)` selects one block
- injected at top of `main()` via `st.markdown(..., unsafe_allow_html=True)`

### 2.1 Core Theme Tokens

| Role | Light | Dark |
|---|---|---|
| Page background | `#F5F5F7` | `#0F0F10` |
| Card/form surface | `rgba(255,255,255,0.78)` / `0.78` glass | `rgba(255,255,255,0.05~0.06)` |
| Card border | `rgba(255,255,255,0.95)` | `rgba(255,255,255,0.09)` |
| Primary text | `#1C1C1E` | `#F5F5F7` |
| Secondary text | `#3C3C43` / `#6E6E73` context-dependent | `#A1A1AA` |
| Muted text | `#8E8E93` | `#52525B` |
| Link blue | `#3B82F6` | `#60A5FA` |
| Positive | `#10B981` | `#34D399` |
| Warning | `#F59E0B` | `#FBBF24` |
| Error | `#F87171` | `#F87171` |

Notes:
- Some inline styles in `components.py` remain light-blue values (`#3B82F6`) for the outbound link pill.
- This is current behavior and should be treated as intentional until changed in code.

## 3. Brand Mark and Favicon

Current mark (all places):
- Rounded square `#0F172A`
- White diagonal arrow motif
- No gradient

Used as:
- `LOGO_72` in hero
- `LOGO_32` in dashboard header
- `FAVICON_DATA_URI` in `st.set_page_config(page_icon=...)`

## 4. Layout Specification

### 4.1 Global Frame

- Layout mode: `st.set_page_config(layout="wide")`
- Sidebar width: fixed `60px` (dashboard only)
- Main container: `max-width: 1200px`, padding `2rem 2.5rem 2.25rem`

### 4.2 Idle / Hero Layout

- Sidebar hidden with CSS
- Top-right floating theme toggle (`position: fixed; top: 18px; right: 24px`)
- Vertical spacer: `14vh`
- Center column ratio: `[0.6, 2.8, 0.6]`
- Form max width: `680px`
- Input row ratio inside form: `[5, 4, 2]`

### 4.3 Dashboard Layout

- Header row columns: `[10, 1, 0.6]`
  - left: compact brand block
  - middle: `Beta` badge
  - right: theme toggle
- Reset button (`← New query`) below header
- Metrics row: `st.columns(4, gap="small")`
- Content area: CSS grid, two equal columns, `gap: 24px`
  - left: recommended subreddits card
  - right: stacked sentiment card + report card (`gap: 14px`)

## 5. Component Behavior

### 5.1 Hero Form

Fields:
- `Channel or topic` (required on submit)
- `Your goal (optional)` (empty normalized to `None`)
- submit label: `Analyze →`

Submit handling:
- empty primary input -> warning and no pipeline call
- valid input -> spinner + `pipeline.run(...)` + `adapt(raw)` + rerun

### 5.2 Theme Toggle

Implementation:
- `render_theme_toggle()` uses Streamlit Material icons:
  - light mode icon: `:material/dark_mode:`
  - dark mode icon: `:material/light_mode:`
- Key: `theme_toggle`
- Visual size: `32x32` in both themes

### 5.3 Metrics Row

Cards:
1. `SUBREDDITS FOUND`
2. `TOP RERANK SCORE`
3. `AVG SENTIMENT`
4. `LATENCY`

Computed rules:
- `AVG SENTIMENT` subtitle uses threshold `>= 0.2` => `"Positive community"`, else `"Mixed community"`
- Latency displayed as seconds with one decimal from `meta.latency_ms`

### 5.4 Ranked Communities Card

- Renders top 10 items from `ranked_subreddits`
- Row fields: rank, subreddit link, reason, score number + bar, outbound link pill
- Empty state text: `No communities found for this query.`

### 5.5 Sentiment Card

- Badge threshold: average score `>= 0.5` => `Positive`, else `Mixed`
- Per-row color thresholds (from `sentiment_bar_html`):
  - `>= 0.5` green
  - `>= 0.2` amber
  - `< 0.2` red

### 5.6 Strategy Report Card

- Supports lightweight markdown-like parsing:
  - lines starting with `## ` rendered as `<h2>`
  - paragraphs split by blank lines

### 5.7 Error Card

- Title: `Pipeline error`
- Shows escaped message from `last_error`
- Appears in hero or dashboard when error is present

## 6. Motion and Animation

Keyframes:
- `fadeInDown`
- `fadeInUp`
- `scaleIn`
- `shimmer`

Entrance classes (dashboard):
- `cp-db-header`, `cp-db-m1..m4`, `cp-db-left`, `cp-db-right-top`, `cp-db-right-bot`, `cp-db-error`

Theme-specific hero motion:
- Light: `.cp-hero-logo-block` uses `fadeInDown 360ms`
- Dark: `.cp-hero-logo-block` uses `scaleIn 400ms`

Form loading motion:
- Disabled submit button uses `shimmer 1.4s linear infinite`

## 7. Interaction Constraints

Mandatory constraints:
- No raw traceback shown to user
- All reddit links open in new tab (`target="_blank"`)
- Theme toggle must preserve size/alignment parity between light/dark
- Reset action must clear both result and error state

## 8. Verification Checklist

1. Light mode idle: hero centered, toggle fixed top-right, form width capped.
2. Dark mode idle: same geometry as light, only colors/hero animation differ.
3. Submit flow shows spinner; success rerenders dashboard.
4. Dashboard toggle and Beta badge align in header.
5. `← New query` returns to idle and clears prior result/error.
6. Error path renders styled `cp-error` card, app remains interactive.
