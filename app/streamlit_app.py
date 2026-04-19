"""CreatorPal Streamlit 前端主文件。

# 主页面（Dashboard）改进说明
# ============================================================
#
# 指标卡片（顶部4个数字）
#   改动前 → 改动后
#   顶部重排分数（负数无意义）  → 适配分 0–100（越高越好，min-max归一化）
#   平均情感（原始小数）        → 社区氛围（Friendly / Warm / Mixed / Cautious / Hostile）
#   找到的 Subreddit 数         → 高置信社区数（适配分 ≥ 70 的数量）
#   延迟时间                    → 已分析社区总数（延迟移至页面底部小字）
#
# 左栏：从"排名列表"变成"行动卡片"
#   每张卡片包含：
#     - 适配分徽章 + 风险标签（Low / Medium / High）
#     - 发帖角度：一句话告诉你怎么切入这个社区
#     - 匹配理由：2–3 条具体证据
#     - View rules → 链接直达版规
#   剩余社区折叠进"查看全部"展开栏
#
# 右栏：新增两个模块
#   1. Top 3 对比表：并排展示前三社区的适配分、氛围、风险
#   2. 第一帖草稿：自动生成建议标题 + 开场白 + ⚠ 避免用语清单
#
# 总体定位：
#   改版前 → 展示模型输出的数据面板
#   改版后 → 告诉你在哪里发、为什么发、第一条怎么写的行动决策界面
#
# ============================================================
"""

from __future__ import annotations

import base64
import os
import re
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import streamlit as st
from PIL import Image

# Ensure absolute imports work no matter where Streamlit is launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.helpers.adapter import adapt
from app.helpers.components import (
    error_card_html,
    metric_card_html,
    sentiment_bar_html,
    subreddit_row_html,
)
from app.helpers.mock_pipeline import MockPipeline
from src.pipeline_vllm import build_pipeline

COLORS: dict[str, str] = {
    "bg_page": "#F5F5F7",
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

LOGO_72 = (
    '<svg width="72" height="72" viewBox="0 0 72 72" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<rect width="72" height="72" rx="18" fill="#0F172A"/>'
    '<line x1="22" y1="50" x2="50" y2="22" '
    'stroke="white" stroke-width="5.5" stroke-linecap="round"/>'
    '<polyline points="32,22 50,22 50,40" '
    'fill="none" stroke="white" stroke-width="5.5" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    "</svg>"
)

LOGO_32 = (
    '<svg width="32" height="32" viewBox="0 0 72 72" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<rect width="72" height="72" rx="18" fill="#0F172A"/>'
    '<line x1="22" y1="50" x2="50" y2="22" '
    'stroke="white" stroke-width="5.5" stroke-linecap="round"/>'
    '<polyline points="32,22 50,22 50,40" '
    'fill="none" stroke="white" stroke-width="5.5" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    "</svg>"
)

LOGO_72_SMALL = LOGO_32

MAX_BG_WIDTH = 1920
MAX_BG_BYTES = 700_000
RESAMPLE_LANCZOS = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
LOADING_STEPS = [
    "Fetching channel metadata",
    "Extracting themes with HyDE",
    "Running FAISS retrieval · top 50",
    "Cross-encoder reranking · top 10",
]

RISK_COLORS: dict[str, str] = {"Low": "#10B981", "Medium": "#F59E0B", "High": "#F87171"}
RISK_BG:     dict[str, str] = {"Low": "#ECFDF5", "Medium": "#FFFBEB", "High": "#FEF2F2"}

KEYFRAMES = """<style>
@keyframes cp-spin {
    to { transform: rotate(360deg); }
}
@keyframes cp-bar {
    0%   { transform: scaleX(0); }
    15%  { transform: scaleX(0.25); }
    40%  { transform: scaleX(0.55); }
    70%  { transform: scaleX(0.78); }
    90%  { transform: scaleX(0.92); }
    100% { transform: scaleX(0.97); }
}
@keyframes cp-fade-up {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
</style>"""

FAVICON_DATA_URI = "data:image/svg+xml;utf8," + quote(
    '<svg width="64" height="64" viewBox="0 0 72 72" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<rect width="72" height="72" rx="18" fill="#0F172A"/>'
    '<line x1="22" y1="50" x2="50" y2="22" '
    'stroke="white" stroke-width="5.5" stroke-linecap="round"/>'
    '<polyline points="32,22 50,22 50,40" '
    'fill="none" stroke="white" stroke-width="5.5" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    "</svg>"
)

LIGHT_CSS = f"""<style>
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="collapsedControl"] {{
    display: none !important;
}}

/* Hide default Streamlit spinner/status widgets */
[data-testid="stSpinner"] {{ display: none !important; }}
[data-testid="stStatusWidget"] {{ display: none !important; }}
.stAlert[kind="info"] {{ display: none !important; }}

.stApp {{
    position: relative !important;
    min-height: 100vh !important;
    overflow: visible !important;
    background-image:
        linear-gradient(
            110deg,
            rgba(245,245,247,0.91) 0%,
            rgba(245,245,247,0.75) 40%,
            rgba(245,245,247,0.15) 100%
        ),
        __BG__ !important;
    background-size: cover !important;
    background-position: center center !important;
    background-repeat: no-repeat !important;
    background-attachment: scroll !important;
    background-color: #F5F5F7 !important;
}}

[data-testid="stAppViewContainer"] {{
    position: relative !important;
    min-height: 100vh !important;
    height: auto !important;
    overflow: visible !important;
    background: transparent !important;
}}

@keyframes fadeInDown {{
    from {{
        opacity: 0;
        transform: translateY(-14px);
    }}
    to {{
        opacity: 1;
        transform: translateY(0);
    }}
}}

@keyframes fadeInUp {{
    from {{
        opacity: 0;
        transform: translateY(18px);
    }}
    to {{
        opacity: 1;
        transform: translateY(0);
    }}
}}

@keyframes scaleIn {{
    from {{
        opacity: 0;
        transform: scale(0.97);
    }}
    to {{
        opacity: 1;
        transform: scale(1);
    }}
}}

@keyframes shimmer {{
    0% {{
        background-position: -500px 0;
    }}
    100% {{
        background-position: 500px 0;
    }}
}}

[data-testid="stSidebar"] {{
    display: none !important;
}}

section[data-testid="stSidebar"] {{
    display: none !important;
}}

[data-testid="stSidebar"] > div:first-child {{
    display: none !important;
}}

[data-testid="stSidebarNav"] {{
    display: none !important;
}}

.block-container {{
    background: transparent !important;
    padding: 0 2.5rem 2.25rem !important;
    max-width: 1200px !important;
}}

[data-testid="stMainBlockContainer"] {{
    background: transparent !important;
}}

/* Strip form card */
[data-testid="stForm"] {{
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}}
[data-testid="stForm"] > div {{
    border: none !important;
    padding: 0 !important;
}}
[data-testid="stForm"] + div {{
    margin-top: 0 !important;
}}

/* Input area — no card */
.cp-input-labels {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    max-width: 600px;
    margin-bottom: 5px;
}}
.cp-input-label {{
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #A0A0A8;
    padding: 0 2px;
}}
.cp-input-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1px;
    background: rgba(0, 0, 0, 0.09);
    border-radius: 12px;
    overflow: hidden;
    max-width: 600px;
    margin-bottom: 16px;
}}
.cp-input-cell {{
    background: rgba(255, 255, 255, 0.78);
    padding: 12px 16px;
}}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:first-of-type {{
    gap: 1px !important;
    background: rgba(0, 0, 0, 0.09);
    border-radius: 12px;
    overflow: hidden;
    max-width: 600px;
    margin-bottom: 16px;
}}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="stColumn"] {{
    background: rgba(255, 255, 255, 0.78);
    padding: 12px 16px;
}}
[data-testid="stTextInput"] > div {{
    background: transparent !important;
}}
[data-testid="stTextInput"] div[data-baseweb="base-input"],
[data-testid="stTextInput"] div[data-baseweb="input"] {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}
[data-testid="stTextInput"] input {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    font-size: 14px !important;
    color: #1C1C1E !important;
    -webkit-text-fill-color: #1C1C1E !important;
    caret-color: #1C1C1E !important;
    padding: 0 !important;
}}
[data-testid="stTextInput"] input::placeholder {{
    color: #C0C0C8 !important;
}}
[data-testid="stTextInput"] label {{
    display: none !important;
}}

/* Button row */
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:nth-of-type(2) {{
    align-items: center !important;
    max-width: 600px;
}}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="stColumn"] {{
    display: flex;
    align-items: center;
}}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="stColumn"]:last-of-type {{
    padding-left: 10px;
}}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="stMarkdown"] {{
    margin: 0 !important;
}}
.cp-btn-row {{
    display: flex;
    align-items: center;
    gap: 16px;
    max-width: 600px;
}}
[data-testid="stFormSubmitButton"] {{
    width: fit-content !important;
}}
[data-testid="stFormSubmitButton"] button {{
    background: #1C1C1E !important;
    color: #FAFAFA !important;
    border: none !important;
    border-radius: 30px !important;
    padding: 11px 34px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    width: auto !important;
}}
[data-testid="stFormSubmitButton"] button:hover {{
    background: #2A2A2D !important;
    border: none !important;
}}
[data-testid="stFormSubmitButton"] button p {{
    color: #FAFAFA !important;
}}
.cp-btn-hint {{
    font-size: 12px;
    color: #A0A0A8;
    line-height: 1.4;
}}

/* Loading — no card */
.cp-loading-wrap {{
    max-width: 600px;
    animation: cp-fade-up 280ms ease both;
}}
.cp-loading-top {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 6px;
}}
.cp-loading-ring {{
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 2px solid rgba(0, 0, 0, 0.10);
    border-top-color: #1C1C1E;
    animation: cp-spin 0.85s linear infinite;
    flex-shrink: 0;
}}
.cp-loading-label {{
    font-size: 15px;
    font-weight: 500;
    color: #1C1C1E;
}}
.cp-loading-sub {{
    font-size: 13px;
    color: #8E8E93;
    margin-left: 34px;
    margin-bottom: 20px;
}}
.cp-bar-track {{
    height: 1.5px;
    background: rgba(0, 0, 0, 0.10);
    border-radius: 1px;
    overflow: hidden;
    max-width: 600px;
}}
.cp-bar-fill {{
    height: 100%;
    background: #1C1C1E;
    border-radius: 1px;
    transform: scaleX(0);
    transform-origin: left;
    animation: cp-bar 8s cubic-bezier(0.4, 0, 0.2, 1) forwards;
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

.cp-hero-logo-block {{
    animation: fadeInDown 360ms ease both;
}}

.cp-hero-hint {{
    animation: fadeInUp 300ms 300ms ease both;
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
    background: rgba(255, 255, 255, 0.88) !important;
    border: 1px solid rgba(255, 255, 255, 0.95) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
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

.cp-db-header {{
    animation: fadeInDown 300ms ease both;
}}

.cp-db-m1 {{
    animation: fadeInUp 380ms 80ms cubic-bezier(0.34, 1.1, 0.64, 1) both;
}}

.cp-db-m2 {{
    animation: fadeInUp 380ms 140ms cubic-bezier(0.34, 1.1, 0.64, 1) both;
}}

.cp-db-m3 {{
    animation: fadeInUp 380ms 200ms cubic-bezier(0.34, 1.1, 0.64, 1) both;
}}

.cp-db-m4 {{
    animation: fadeInUp 380ms 260ms cubic-bezier(0.34, 1.1, 0.64, 1) both;
}}

.cp-db-left {{
    animation: fadeInUp 420ms 300ms cubic-bezier(0.34, 1.1, 0.64, 1) both;
}}

.cp-db-right-top {{
    animation: fadeInUp 420ms 360ms cubic-bezier(0.34, 1.1, 0.64, 1) both;
}}

.cp-db-right-bot {{
    animation: fadeInUp 420ms 420ms cubic-bezier(0.34, 1.1, 0.64, 1) both;
}}

.cp-db-error {{
    animation: fadeInUp 350ms ease both;
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
    background: rgba(255, 255, 255, 0.88) !important;
    border: 1px solid rgba(255, 255, 255, 0.95) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
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

[data-testid="stButton"][data-key="theme_toggle"] button,
.st-key-theme_toggle [data-testid="stButton"] button,
.st-key-theme_toggle button {{
    width: 32px !important;
    min-width: 32px !important;
    max-width: 32px !important;
    height: 32px !important;
    min-height: 32px !important;
    max-height: 32px !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 8px !important;
    background: rgba(0, 0, 0, 0.06) !important;
    border: 1px solid rgba(0, 0, 0, 0.08) !important;
    color: #6E6E73 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0 !important;
}}

[data-testid="stButton"][data-key="theme_toggle"] button:hover,
.st-key-theme_toggle [data-testid="stButton"] button:hover,
.st-key-theme_toggle button:hover {{
    background: rgba(0, 0, 0, 0.10) !important;
}}

[data-testid="stButton"][data-key="theme_toggle"] button > div,
.st-key-theme_toggle [data-testid="stButton"] button > div,
.st-key-theme_toggle button > div {{
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0 !important;
    width: 100% !important;
}}

[data-testid="stButton"][data-key="theme_toggle"] button p,
.st-key-theme_toggle [data-testid="stButton"] button p,
.st-key-theme_toggle button p {{
    display: none !important;
    margin: 0 !important;
}}

[data-testid="stButton"][data-key="theme_toggle"] [data-testid="stIconMaterial"],
.st-key-theme_toggle [data-testid="stButton"] [data-testid="stIconMaterial"],
.st-key-theme_toggle [data-testid="stIconMaterial"] {{
    margin: 0 !important;
    line-height: 1 !important;
}}

[data-testid="stButton"][data-key="theme_toggle"] [data-testid="stIconMaterial"] span,
.st-key-theme_toggle [data-testid="stButton"] [data-testid="stIconMaterial"] span,
.st-key-theme_toggle [data-testid="stIconMaterial"] span {{
    font-size: 17px !important;
}}
</style>"""


DARK_CSS = """<style>
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="collapsedControl"] { display: none !important; }

/* Hide default Streamlit spinner/status widgets */
[data-testid="stSpinner"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
.stAlert[kind="info"] { display: none !important; }

@keyframes fadeInDown {
    from { opacity: 0; transform: translateY(-14px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(18px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes scaleIn {
    from { opacity: 0; transform: scale(0.97); }
    to   { opacity: 1; transform: scale(1); }
}
@keyframes shimmer {
    0%   { background-position: -500px 0; }
    100% { background-position:  500px 0; }
}

.stApp {
    position: relative !important;
    min-height: 100vh !important;
    overflow: visible !important;
    background-image:
        linear-gradient(
            110deg,
            rgba(8,8,8,0.90) 0%,
            rgba(8,8,8,0.65) 40%,
            rgba(8,8,8,0.10) 100%
        ),
        __BG__ !important;
    background-size: cover !important;
    background-position: center center !important;
    background-repeat: no-repeat !important;
    background-attachment: scroll !important;
    background-color: #080808 !important;
}

[data-testid="stAppViewContainer"] {
    position: relative !important;
    min-height: 100vh !important;
    height: auto !important;
    overflow: visible !important;
    background: transparent !important;
}

[data-testid="stSidebar"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebar"] > div:first-child { display: none !important; }
[data-testid="stSidebarNav"] { display: none !important; }

.block-container {
    background: transparent !important;
    padding: 0 2.5rem 2.25rem !important;
    max-width: 1200px !important;
}

[data-testid="stMainBlockContainer"] {
    background: transparent !important;
}

[data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
[data-testid="stForm"] > div {
    border: none !important;
    padding: 0 !important;
}
[data-testid="stForm"] + div { margin-top: 0 !important; }

.cp-input-labels {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    max-width: 600px;
    margin-bottom: 5px;
}
.cp-input-label {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #52525B;
    padding: 0 2px;
}
.cp-input-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
    max-width: 600px;
    margin-bottom: 16px;
}
.cp-input-cell {
    background: rgba(255, 255, 255, 0.05);
    padding: 12px 16px;
}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:first-of-type {
    gap: 1px !important;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
    max-width: 600px;
    margin-bottom: 16px;
}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="stColumn"] {
    background: rgba(255, 255, 255, 0.05);
    padding: 12px 16px;
}
[data-testid="stTextInput"] > div {
    background: transparent !important;
}
[data-testid="stTextInput"] div[data-baseweb="base-input"],
[data-testid="stTextInput"] div[data-baseweb="input"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
[data-testid="stTextInput"] input {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    font-size: 14px !important;
    color: #F5F5F7 !important;
    -webkit-text-fill-color: #F5F5F7 !important;
    caret-color: #F5F5F7 !important;
    padding: 0 !important;
}
[data-testid="stTextInput"] input::placeholder { color: #3F3F46 !important; }
[data-testid="stTextInput"] label { display: none !important; }

[data-testid="stForm"] [data-testid="stHorizontalBlock"]:nth-of-type(2) {
    align-items: center !important;
    max-width: 600px;
}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="stColumn"] {
    display: flex;
    align-items: center;
}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="stColumn"]:last-of-type {
    padding-left: 10px;
}
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="stMarkdown"] {
    margin: 0 !important;
}
.cp-btn-row {
    display: flex;
    align-items: center;
    gap: 16px;
    max-width: 600px;
}
[data-testid="stFormSubmitButton"] {
    width: fit-content !important;
}
[data-testid="stFormSubmitButton"] button {
    background: #FAFAFA !important;
    color: #0A0A0A !important;
    border: none !important;
    border-radius: 30px !important;
    padding: 11px 34px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    width: auto !important;
}
[data-testid="stFormSubmitButton"] button:hover {
    background: #EFEFF1 !important;
    border: none !important;
}
[data-testid="stFormSubmitButton"] button p {
    color: #0A0A0A !important;
}
.cp-btn-hint {
    font-size: 12px;
    color: #52525B;
    line-height: 1.4;
}

.cp-loading-wrap {
    max-width: 600px;
    animation: cp-fade-up 280ms ease both;
}
.cp-loading-top {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 6px;
}
.cp-loading-ring {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.12);
    border-top-color: #F5F5F7;
    animation: cp-spin 0.85s linear infinite;
    flex-shrink: 0;
}
.cp-loading-label {
    font-size: 15px;
    font-weight: 500;
    color: #F5F5F7;
}
.cp-loading-sub {
    font-size: 13px;
    color: #52525B;
    margin-left: 34px;
    margin-bottom: 20px;
}
.cp-bar-track {
    height: 1.5px;
    background: rgba(255, 255, 255, 0.10);
    border-radius: 1px;
    overflow: hidden;
    max-width: 600px;
}
.cp-bar-fill {
    height: 100%;
    background: #F5F5F7;
    border-radius: 1px;
    transform: scaleX(0);
    transform-origin: left;
    animation: cp-bar 8s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

.cp-sidebar-shell {
    height: calc(100vh - 24px);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
}
.cp-sidebar-icons {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}
.cp-sidebar-btn {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.cp-card-fill-col { height: 100%; }
.cp-results-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 24px;
    align-items: stretch;
}
.cp-results-col { min-width: 0; }
.cp-results-right { display: flex; flex-direction: column; gap: 14px; }

.cp-card {
    background: rgba(12, 12, 14, 0.82) !important;
    border: 1px solid rgba(255, 255, 255, 0.09) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.4) !important;
    padding: 16px 18px;
    transition: transform 220ms cubic-bezier(0.34,1.56,0.64,1), box-shadow 220ms ease;
    will-change: transform;
}
.cp-card:hover {
    transform: scale(1.018);
    box-shadow: 0 8px 24px rgba(0,0,0,0.5) !important;
}

.cp-metric {
    background: rgba(12, 12, 14, 0.82) !important;
    border: 1px solid rgba(255, 255, 255, 0.09) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.4) !important;
    padding: 14px 16px;
    transition: transform 220ms cubic-bezier(0.34,1.56,0.64,1), box-shadow 220ms ease;
    will-change: transform;
}
.cp-metric:hover {
    transform: scale(1.018);
    box-shadow: 0 8px 24px rgba(0,0,0,0.5) !important;
}
.cp-metric-label {
    font-size: 12px;
    font-weight: 500;
    color: #52525B;
    letter-spacing: .05em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.cp-metric-value {
    font-size: 32px;
    font-weight: 700;
    color: #F5F5F7;
    letter-spacing: -.03em;
    line-height: 1 !important;
}
.cp-metric-sub-up { font-size: 13px; color: #34D399; margin-top: 5px; }
.cp-metric-sub-neutral { font-size: 13px; color: #52525B; margin-top: 5px; }

.cp-card-title { font-size: 16px; font-weight: 600; color: #F5F5F7; }
.cp-card-subtitle { font-size: 13px; color: #52525B; }

.cp-sub-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 8px;
    border-radius: 8px;
    margin: 0 -8px;
    transition: background 100ms ease;
}
.cp-sub-row + .cp-sub-row { border-top: .5px solid rgba(255,255,255,0.06); }
.cp-sub-row:hover { background: rgba(255,255,255,0.05); }
.cp-rank {
    font-size: 15px;
    font-weight: 700;
    color: #3F3F46;
    width: 20px;
    text-align: right;
    flex-shrink: 0;
}
.cp-sub-info { flex: 1; min-width: 0; }
.cp-sub-name {
    font-size: 15px;
    font-weight: 600;
    color: #60A5FA;
    text-decoration: none !important;
    display: block;
}
.cp-sub-name:hover { text-decoration: underline !important; }
.cp-sub-reason {
    font-size: 13px;
    color: #52525B;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.cp-score-wrap { width: 72px; flex-shrink: 0; text-align: right; }
.cp-score-num { font-size: 13px; color: #71717A; margin-bottom: 3px; }
.cp-score-track {
    height: 4px;
    background: rgba(96,165,250,0.15);
    border-radius: 2px;
    overflow: hidden;
}
.cp-score-fill { height: 100%; background: #60A5FA; border-radius: 2px; }

a[href*="reddit.com"]:hover { background: rgba(96,165,250,0.18) !important; }

.cp-sent-row { display: flex; align-items: center; gap: 10px; padding: 5px 0; }
.cp-sent-label {
    font-size: 13px;
    color: #A1A1AA;
    width: 130px;
    flex-shrink: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.cp-sent-track {
    flex: 1;
    height: 5px !important;
    background: rgba(255,255,255,0.08);
    border-radius: 3px;
    overflow: hidden;
}
.cp-sent-fill-green { height: 100% !important; background: #34D399; border-radius: 3px; }
.cp-sent-fill-amber { height: 100% !important; background: #FBBF24; border-radius: 3px; }
.cp-sent-fill-red { height: 100% !important; background: #F87171; border-radius: 3px; }
.cp-sent-val {
    font-size: 13px;
    color: #A1A1AA;
    width: 38px;
    text-align: right;
    flex-shrink: 0;
    font-weight: 500;
}

.cp-badge { display: inline-block; font-size: 11px; font-weight: 500; padding: 2px 9px; border-radius: 20px; }
.cp-badge-blue { background: rgba(96,165,250,0.15); color: #60A5FA; }
.cp-badge-green { background: rgba(52,211,153,0.15); color: #34D399; }

.cp-report { font-size: 14px; color: #A1A1AA; line-height: 1.75; }
.cp-report h2 { font-size: 14px; font-weight: 600; color: #F5F5F7; margin: 14px 0 6px; }
.cp-report h2:first-child { margin-top: 0; }
.cp-report p { margin: 0 0 10px; }

.cp-error {
    background: rgba(255,255,255,0.05);
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.09);
    border-left: 3px solid #F87171;
    padding: 14px 18px;
}
.cp-error-title { font-size: 14px; font-weight: 600; color: #F87171; margin-bottom: 6px; }
.cp-error-msg { font-size: 13px; color: #A1A1AA; }
.cp-empty { text-align: center; color: #52525B; font-size: 13px; padding: 24px 0; }

.cp-page-title {
    font-size: 24px;
    font-weight: 700;
    color: #F5F5F7;
    letter-spacing: -.02em;
    margin: 0 0 2px;
}
.cp-page-subtitle { font-size: 14px; color: #52525B; margin: 0; }

.cp-hero-logo-block { animation: scaleIn 400ms cubic-bezier(0.34,1.1,0.64,1) both; }
.cp-hero-hint { animation: fadeInUp 300ms 300ms ease both; }

.cp-db-header { animation: fadeInDown 300ms ease both; }
.cp-db-m1 { animation: fadeInUp 380ms  80ms cubic-bezier(0.34,1.1,0.64,1) both; }
.cp-db-m2 { animation: fadeInUp 380ms 140ms cubic-bezier(0.34,1.1,0.64,1) both; }
.cp-db-m3 { animation: fadeInUp 380ms 200ms cubic-bezier(0.34,1.1,0.64,1) both; }
.cp-db-m4 { animation: fadeInUp 380ms 260ms cubic-bezier(0.34,1.1,0.64,1) both; }
.cp-db-left { animation: fadeInUp 420ms 300ms cubic-bezier(0.34,1.1,0.64,1) both; }
.cp-db-right-top { animation: fadeInUp 420ms 360ms cubic-bezier(0.34,1.1,0.64,1) both; }
.cp-db-right-bot { animation: fadeInUp 420ms 420ms cubic-bezier(0.34,1.1,0.64,1) both; }
.cp-db-error { animation: fadeInUp 350ms ease both; }

[data-testid="stButton"] button {
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    color: #71717A !important;
    padding: 4px 12px !important;
    margin-bottom: 12px !important;
}
[data-testid="stButton"] button:hover {
    background: rgba(255,255,255,0.06) !important;
    color: #A1A1AA !important;
}

[data-testid="stButton"][data-key="theme_toggle"] button,
.st-key-theme_toggle [data-testid="stButton"] button,
.st-key-theme_toggle button {
    width: 32px !important;
    min-width: 32px !important;
    max-width: 32px !important;
    height: 32px !important;
    min-height: 32px !important;
    max-height: 32px !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 8px !important;
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    color: #71717A !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0 !important;
}
[data-testid="stButton"][data-key="theme_toggle"] button:hover,
.st-key-theme_toggle [data-testid="stButton"] button:hover,
.st-key-theme_toggle button:hover {
    background: rgba(255,255,255,0.12) !important;
}

[data-testid="stButton"][data-key="theme_toggle"] button > div,
.st-key-theme_toggle [data-testid="stButton"] button > div,
.st-key-theme_toggle button > div {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0 !important;
    width: 100% !important;
}

[data-testid="stButton"][data-key="theme_toggle"] button p,
.st-key-theme_toggle [data-testid="stButton"] button p,
.st-key-theme_toggle button p {
    display: none !important;
    margin: 0 !important;
}

[data-testid="stButton"][data-key="theme_toggle"] [data-testid="stIconMaterial"],
.st-key-theme_toggle [data-testid="stButton"] [data-testid="stIconMaterial"],
.st-key-theme_toggle [data-testid="stIconMaterial"] {
    margin: 0 !important;
    line-height: 1 !important;
}

[data-testid="stButton"][data-key="theme_toggle"] [data-testid="stIconMaterial"] span,
.st-key-theme_toggle [data-testid="stButton"] [data-testid="stIconMaterial"] span,
.st-key-theme_toggle [data-testid="stIconMaterial"] span {
    font-size: 17px !important;
}
</style>"""


@st.cache_data(show_spinner=False)
def load_bg(path: str) -> str:
    """Read local image, compress it, and return a CSS-safe base64 url()."""
    img_path = Path(path)
    try:
        with Image.open(img_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            if img.width > MAX_BG_WIDTH:
                ratio = MAX_BG_WIDTH / float(img.width)
                new_height = int(img.height * ratio)
                img = img.resize((MAX_BG_WIDTH, new_height), RESAMPLE_LANCZOS)

            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=74, optimize=True)
            payload = buffer.getvalue()

            if len(payload) > MAX_BG_BYTES:
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=64, optimize=True)
                payload = buffer.getvalue()

            if len(payload) > MAX_BG_BYTES:
                return "none"

            b64 = base64.b64encode(payload).decode()
            return f"url('data:image/jpeg;base64,{b64}')"
    except FileNotFoundError:
        return "none"
    except Exception:
        return "none"


def resolve_bg_path(dark: bool) -> Path:
    """Pick the first existing hero background file for the active theme."""
    name = "dark" if dark else "white"
    candidates = [
        PROJECT_ROOT / "app" / "background" / f"{name}.jpg",
        PROJECT_ROOT / "app" / "background" / f"{name}.jpeg",
        PROJECT_ROOT / "app" / "background" / f"{name}.png",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def get_css(dark: bool, bg: str = "none") -> str:
    base = DARK_CSS if dark else LIGHT_CSS
    return base.replace("__BG__", bg)


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


def _loading_card_html(step: int = 2) -> str:
    current = max(1, min(step, len(LOADING_STEPS)))
    step_label = escape(LOADING_STEPS[current - 1])
    return (
        '<div class="cp-loading-wrap">'
        '<div class="cp-loading-top">'
        '<div class="cp-loading-ring"></div>'
        '<span class="cp-loading-label">Analyzing your channel</span>'
        "</div>"
        f'<div class="cp-loading-sub">{step_label} · step {current} of {len(LOADING_STEPS)}</div>'
        '<div class="cp-bar-track">'
        '<div class="cp-bar-fill"></div>'
        "</div>"
        "</div>"
    )


def render_loading_card(dark: bool, step: int = 2) -> None:
    """Render the custom loading indicator."""
    _ = dark  # Theme colors are controlled by LIGHT_CSS / DARK_CSS.
    st.markdown(_loading_card_html(step=step), unsafe_allow_html=True)


def run_with_loading(
    channel_or_query: str,
    user_query: str | None,
    dark: bool,
    force_mock: bool,
    loading_placeholder: Any,
) -> tuple[dict[str, Any], bool]:
    """Run pipeline work in a worker thread while animating estimated loading steps."""
    st.session_state["loading_step"] = 1

    result_box: dict[str, Any] = {}
    error_box: dict[str, Exception] = {}

    current_step = 1
    with loading_placeholder:
        render_loading_card(dark=dark, step=current_step)

    pipeline = get_pipeline(force_mock=force_mock)
    pipeline_is_mock = isinstance(pipeline, MockPipeline)

    def _run_pipeline() -> None:
        try:
            result_box["raw"] = pipeline.run(
                channel_or_query=channel_or_query,
                user_query=user_query,
            )
        except Exception as exc:  # pragma: no cover - runtime fallback path
            error_box["exc"] = exc

    worker = threading.Thread(target=_run_pipeline, daemon=True)
    worker.start()

    last_step_tick = time.monotonic()
    while worker.is_alive():
        time.sleep(0.12)
        now = time.monotonic()
        if now - last_step_tick < 1.8:
            continue
        last_step_tick = now
        if current_step < len(LOADING_STEPS):
            current_step += 1
            st.session_state["loading_step"] = current_step
            with loading_placeholder:
                render_loading_card(dark=dark, step=current_step)

    worker.join()

    if "exc" in error_box:
        raise error_box["exc"]

    raw = result_box.get("raw")
    if not isinstance(raw, Mapping):
        raise RuntimeError("Pipeline returned an invalid response.")
    return dict(raw), pipeline_is_mock


def _svg_icon(path: str, stroke: str, bg: str) -> str:
    return (
        f'<div class="cp-sidebar-btn" style="background:{bg}">'
        f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" '
        f'stroke="{stroke}" stroke-width="1.8">{path}</svg>'
        f"</div>"
    )


def render_theme_toggle() -> None:
    """Render dark mode toggle button and flip session state on click."""
    is_dark = st.session_state.get("dark_mode", False)
    icon = ":material/dark_mode:" if not is_dark else ":material/light_mode:"
    if st.button("", key="theme_toggle", icon=icon, help="Toggle theme", width="content"):
        st.session_state["dark_mode"] = not is_dark
        st.rerun()


def render_sidebar(dark: bool) -> None:
    """Render fixed-width visual icon sidebar."""
    inactive_stroke = "#3F3F46" if dark else "#94A3B8"
    active_stroke = "#60A5FA" if dark else "#3B82F6"
    active_bg = "rgba(96,165,250,0.12)" if dark else "#EEF2F7"

    top_icons = "".join(
        [
            _svg_icon(
                '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>'
                '<polyline points="9 22 9 12 15 12 15 22"/>',
                stroke=active_stroke,
                bg=active_bg,
            ),
            _svg_icon(
                '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
                stroke=inactive_stroke,
                bg="transparent",
            ),
            _svg_icon(
                '<line x1="18" y1="20" x2="18" y2="10"/>'
                '<line x1="12" y1="20" x2="12" y2="4"/>'
                '<line x1="6" y1="20" x2="6" y2="14"/>',
                stroke=inactive_stroke,
                bg="transparent",
            ),
            _svg_icon(
                '<circle cx="12" cy="12" r="3"/>'
                '<path d="M19.07 4.93a10 10 0 010 14.14"/>'
                '<path d="M4.93 4.93a10 10 0 000 14.14"/>',
                stroke=inactive_stroke,
                bg="transparent",
            ),
        ]
    )
    user_icon = _svg_icon(
        '<circle cx="12" cy="8" r="4"/>'
        '<path d="M6 20v-2a4 4 0 014-4h4a4 4 0 014 4v2"/>',
        stroke=inactive_stroke,
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


def render_page_header(dark: bool) -> None:
    """Render compact dashboard header after results are available."""
    title_color = "#F5F5F7" if dark else "#1C1C1E"
    subtitle_color = "#A1A1AA" if dark else "#6E6E73"

    col_hdr, col_badge, col_toggle = st.columns([10, 1, 0.6], gap="small")
    with col_hdr:
        st.markdown(
            '<div class="cp-db-header" style="display:flex;align-items:center;gap:10px;margin-bottom:16px">'
            f"{LOGO_32}"
            "<div>"
            f'<div style="font-size:18px;font-weight:700;color:{title_color};letter-spacing:-.02em;line-height:1">'
            "CreatorPal"
            "</div>"
            f'<div style="font-size:12px;color:{subtitle_color};margin-top:1px">'
            "YouTube → Reddit audience intelligence"
            "</div>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with col_badge:
        st.markdown(
            '<div class="cp-db-header" style="padding-top:8px;text-align:right">'
            '<span class="cp-badge cp-badge-blue">Beta</span></div>',
            unsafe_allow_html=True,
        )
    with col_toggle:
        st.markdown('<div class="cp-db-header" style="padding-top:2px"></div>', unsafe_allow_html=True)
        render_theme_toggle()


def _hero_intro_html(dark: bool) -> str:
    title_color = "#FAFAFA" if dark else "#1C1C1E"
    tagline_color = "rgba(255,255,255,0.52)" if dark else "#6E6E73"
    return (
        '<div style="margin-bottom:44px">'
        '<div style="display:flex;align-items:center;gap:9px;margin-bottom:52px">'
        '<div style="width:30px;height:30px;border-radius:8px;background:#0F172A;display:flex;'
        'align-items:center;justify-content:center;flex-shrink:0">'
        '<svg width="15" height="15" viewBox="0 0 72 72" fill="none">'
        '<rect width="72" height="72" rx="16" fill="#0F172A"/>'
        '<line x1="22" y1="50" x2="50" y2="22" stroke="white" stroke-width="6" stroke-linecap="round"/>'
        '<polyline points="32,22 50,22 50,40" fill="none" stroke="white" stroke-width="6" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
        "</div>"
        f'<span style="font-size:14px;font-weight:600;color:{title_color};letter-spacing:-.01em">CreatorPal</span>'
        "</div>"
        f'<div style="font-size:60px;font-weight:800;color:{title_color};letter-spacing:-.05em;'
        'line-height:1.01;margin-bottom:16px">Find your<br>audience.<br>Own your niche.</div>'
        f'<div style="font-size:16px;color:{tagline_color};line-height:1.6;max-width:420px">'
        "Match your YouTube channel to the Reddit communities that will actually engage."
        "</div>"
        "</div>"
    )


def render_idle_hero(dark: bool, error_message: str | None = None) -> tuple[str, str | None, bool]:
    """Render hero + form in the idle state and return submitted query payload."""
    label_color = "rgba(255,255,255,0.35)" if dark else "#A0A0A8"
    hint_color = "rgba(255,255,255,0.28)" if dark else "#A0A0A8"

    st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([0.4, 3, 0.4])
    with col:
        st.markdown(_hero_intro_html(dark=dark), unsafe_allow_html=True)
        st.markdown(
            f'<div class="cp-input-labels">'
            f'<span class="cp-input-label" style="color:{label_color}">Channel or topic</span>'
            f'<span class="cp-input-label" style="color:{label_color}">Your goal (optional)</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        with st.form("query_form", clear_on_submit=False):
            col_a, col_b = st.columns([1, 1], gap="small")
            with col_a:
                channel_or_query = st.text_input(
                    "channel",
                    placeholder="youtube.com/@yourchannel",
                    label_visibility="collapsed",
                )
            with col_b:
                user_query = st.text_input(
                    "goal",
                    placeholder="e.g. grow EU subscribers",
                    label_visibility="collapsed",
                )

            btn_col, hint_col = st.columns([0.36, 0.64], gap="small")
            with btn_col:
                submitted = st.form_submit_button("Analyze →", use_container_width=False)
            with hint_col:
                st.markdown(
                    f'<div class="cp-btn-hint" style="color:{hint_color}">'
                    "Powered by FAISS · cross-encoder reranking"
                    "</div>",
                    unsafe_allow_html=True,
                )

        if error_message:
            st.markdown(
                f'<div class="cp-db-error">{error_card_html(error_message)}</div>',
                unsafe_allow_html=True,
            )

    normalized_goal = user_query.strip() or None
    return channel_or_query, normalized_goal, submitted


def render_loading_hero(dark: bool, step: int = 1) -> Any:
    """Render hero + loading indicator in the same position as the idle form."""
    st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([0.4, 3, 0.4])
    with col:
        st.markdown(_hero_intro_html(dark=dark), unsafe_allow_html=True)
        loading_placeholder = st.empty()
        with loading_placeholder:
            render_loading_card(dark=dark, step=step)
    return loading_placeholder


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float safely, returning default on invalid input."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_fit_score(rerank_score: float, all_scores: list[float]) -> int:
    if not all_scores or len(all_scores) == 1:
        return 85
    min_s = min(all_scores)
    max_s = max(all_scores)
    if max_s == min_s:
        return 85
    normalized = (rerank_score - min_s) / (max_s - min_s)
    return round(normalized * 100)


def sentiment_label(score: float) -> tuple[str, str]:
    if score >= 0.4:
        return "Friendly",  "#10B981"
    elif score >= 0.1:
        return "Warm",      "#34D399"
    elif score >= -0.1:
        return "Mixed",     "#F59E0B"
    elif score >= -0.3:
        return "Cautious",  "#F97316"
    else:
        return "Hostile",   "#F87171"


def derive_risk_level(sentiment_score: float, self_promo: bool | None = None) -> str:
    if self_promo is False:
        return "High"
    if sentiment_score < -0.2:
        return "High"
    if sentiment_score < 0.1:
        return "Medium"
    return "Low"


def action_card_html(s: dict[str, Any], dark: bool) -> str:
    fit      = s.get("fit_score", 0)
    risk     = s.get("risk_level") or derive_risk_level(s.get("sentiment_score") or 0)
    angle    = s.get("posting_angle", "")
    evidence = s.get("evidence", [])
    url      = s.get("url") or f"https://www.reddit.com/r/{s['subreddit']}/"
    tone_lbl, tone_col = sentiment_label(s.get("sentiment_score") or 0)

    risk_col = RISK_COLORS.get(risk, "#F59E0B")
    risk_bg  = RISK_BG.get(risk, "#FFFBEB")

    ev_items = "".join(
        f'<li style="font-size:12px;color:#6E6E73;margin-bottom:4px">{escape(e)}</li>'
        for e in evidence[:3]
    )

    card_bg   = "rgba(255,255,255,0.06)" if dark else "rgba(255,255,255,0.82)"
    border    = "rgba(255,255,255,0.10)" if dark else "rgba(0,0,0,0.08)"
    name_col  = "#60A5FA" if dark else "#3B82F6"
    title_col = "#F5F5F7" if dark else "#1C1C1E"
    safe_url  = escape(url, quote=True)
    safe_name = escape(s["subreddit"])

    return (
        f'<div style="background:{card_bg};border:1px solid {border};border-radius:14px;'
        f'padding:18px 20px;margin-bottom:10px">'
        f'<div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px">'
        f'<a href="{safe_url}" target="_blank" style="font-size:16px;font-weight:700;'
        f'color:{name_col};text-decoration:none">r/{safe_name}</a>'
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<span style="font-size:11px;font-weight:600;background:#EFF6FF;color:#3B82F6;'
        f'padding:3px 8px;border-radius:6px">{fit}/100 fit</span>'
        f'<span style="font-size:11px;font-weight:600;background:{risk_bg};color:{risk_col};'
        f'padding:3px 8px;border-radius:6px">{escape(risk)} risk</span>'
        f'</div></div>'
        f'<p style="font-size:13px;color:{title_col};font-style:italic;margin-bottom:14px;'
        f'line-height:1.5">"{escape(angle)}"</p>'
        f'<div style="border-top:1px solid rgba(0,0,0,0.06);padding-top:12px;margin-bottom:12px">'
        f'<p style="font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;'
        f'color:#A0A0A8;margin-bottom:8px">Why this matches</p>'
        f'<ul style="list-style:none;padding:0;margin:0">{ev_items}</ul>'
        f'</div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between">'
        f'<span style="font-size:12px;color:{tone_col};font-weight:500">● {escape(tone_lbl)} community</span>'
        f'<a href="{safe_url}about/rules" target="_blank" style="font-size:12px;'
        f'color:#A0A0A8;text-decoration:none">View rules →</a>'
        f'</div></div>'
    )


def render_metrics(data: Mapping[str, Any]) -> None:
    """Render the four metric cards."""
    subreddits = data["ranked_subreddits"]
    sentiment_scores = data["sentiment_scores"]
    meta = data["meta"]

    top_score = _safe_float(subreddits[0].get("rerank_score")) if subreddits else 0.0
    top_name = f'r/{subreddits[0]["subreddit"]}' if subreddits else "-"
    avg_sentiment = sum(sentiment_scores.values()) / len(sentiment_scores) if sentiment_scores else 0.0
    latency_s = f'{meta["latency_ms"] / 1000:.1f}s'
    sentiment_sub = "Positive community" if avg_sentiment >= 0.2 else "Mixed community"

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        st.markdown(
            '<div class="cp-db-m1">'
            + metric_card_html(
                "SUBREDDITS FOUND",
                str(len(subreddits)),
                f"↑ from {meta['retrieval_top_k']} retrieved",
                sub_up=True,
                container_style="border-top:3px solid #3B82F6 !important;",
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="cp-db-m2">'
            + metric_card_html(
                "TOP RERANK SCORE",
                f"{top_score:.2f}",
                top_name,
                sub_up=True,
                container_style="border-top:3px solid #10B981 !important;",
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div class="cp-db-m3">'
            + metric_card_html(
                "AVG SENTIMENT",
                f"{avg_sentiment:+.2f}",
                sentiment_sub,
                sub_up=True,
                container_style="border-top:3px solid #10B981 !important;",
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            '<div class="cp-db-m4">'
            + metric_card_html(
                "LATENCY",
                latency_s,
                "end-to-end",
                sub_up=False,
                container_style="border-top:3px solid #C7C7CC !important;",
            )
            + "</div>",
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


def render_sentiment(sentiment_scores: Mapping[str, float], dark: bool = False) -> None:
    """Render community sentiment card."""
    _ = dark
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


def render_report(report: str, dark: bool = False) -> None:
    _ = dark
    st.markdown(_strategy_report_card_html(report), unsafe_allow_html=True)


def render_results_grid(data: Mapping[str, Any]) -> None:
    """Render equal-height two-column results area with right-side stacked cards."""
    left = _ranked_subreddits_card_html(data["ranked_subreddits"])
    right_top = _sentiment_card_html(data["sentiment_scores"])
    right_bottom = _strategy_report_card_html(str(data["strategy_report"]))
    st.markdown(
        '<div class="cp-results-grid">'
        f'<div class="cp-results-col cp-db-left">{left}</div>'
        '<div class="cp-results-col cp-results-right">'
        f'<div class="cp-db-right-top">{right_top}</div>'
        f'<div class="cp-db-right-bot">{right_bottom}</div>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_action_cards(data: Mapping[str, Any], dark: bool) -> None:
    st.markdown(
        '<p style="font-size:11px;font-weight:600;letter-spacing:.07em;'
        'text-transform:uppercase;color:#A0A0A8;margin-bottom:12px">'
        'Top communities to post in</p>',
        unsafe_allow_html=True,
    )
    top3 = list(data["ranked_subreddits"])[:3]
    for s in top3:
        st.markdown(action_card_html(s, dark), unsafe_allow_html=True)

    remaining = list(data["ranked_subreddits"])[3:]
    if remaining:
        with st.expander(f"See all {len(data['ranked_subreddits'])} communities"):
            for s in remaining:
                st.markdown(
                    subreddit_row_html(
                        s["rank"], s["subreddit"], s["url"],
                        s["rerank_score"], s.get("reason", ""),
                    ),
                    unsafe_allow_html=True,
                )


def render_compare(data: Mapping[str, Any], dark: bool) -> None:
    top3 = list(data["ranked_subreddits"])[:3]
    if len(top3) < 2:
        return

    card_bg  = "rgba(255,255,255,0.06)" if dark else "rgba(255,255,255,0.82)"
    border   = "rgba(255,255,255,0.10)" if dark else "rgba(0,0,0,0.08)"
    text_col = "#F5F5F7" if dark else "#1C1C1E"
    muted    = "#71717A"  if dark else "#A0A0A8"

    metrics: list[tuple[str, Any]] = [
        ("Fit score", lambda s: f'{s.get("fit_score", 0)}/100'),
        ("Tone",      lambda s: sentiment_label(s.get("sentiment_score") or 0)[0]),
        ("Risk",      lambda s: s.get("risk_level", "—")),
    ]

    cols_html = "".join(
        f'<th style="text-align:center;font-size:13px;font-weight:600;'
        f'color:{text_col};padding:8px 12px">'
        f'<a href="{escape(s["url"], quote=True)}" target="_blank" '
        f'style="color:#3B82F6;text-decoration:none">r/{escape(s["subreddit"])}</a></th>'
        for s in top3
    )
    header = (
        f'<tr><th style="text-align:left;color:{muted};font-size:11px;padding:8px 12px"></th>'
        f'{cols_html}</tr>'
    )

    rows = []
    for label, fn in metrics:
        cells = "".join(
            f'<td style="text-align:center;font-size:13px;color:{text_col};'
            f'padding:8px 12px">{escape(str(fn(s)))}</td>'
            for s in top3
        )
        rows.append(
            f'<tr style="border-top:1px solid rgba(0,0,0,0.05)">'
            f'<td style="font-size:11px;font-weight:500;letter-spacing:.05em;'
            f'text-transform:uppercase;color:{muted};padding:8px 12px">{label}</td>'
            f'{cells}</tr>'
        )

    table = (
        f'<div style="background:{card_bg};border:1px solid {border};'
        f'border-radius:14px;padding:4px 0;margin-bottom:14px;overflow:hidden">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead>{header}</thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table></div>'
    )

    st.markdown(
        '<p style="font-size:11px;font-weight:600;letter-spacing:.07em;'
        'text-transform:uppercase;color:#A0A0A8;margin-bottom:10px">'
        'Compare top 3</p>',
        unsafe_allow_html=True,
    )
    st.markdown(table, unsafe_allow_html=True)


def extract_first_post_draft(strategy_report: str, top_subreddit: str) -> dict[str, Any]:
    title_match = re.search(
        r'(?:title|headline|post title)[:\s]+(.+?)(?:\n|$)',
        strategy_report, re.IGNORECASE,
    )
    draft_title = title_match.group(1).strip() if title_match else (
        f"[Question] What's your experience with [your topic] on r/{top_subreddit}?"
    )

    action_match = re.search(
        r'(?:recommended action|first post|how to post)[:\s\n]+(.+?)(?:\n\n|##|$)',
        strategy_report, re.IGNORECASE | re.DOTALL,
    )
    draft_body = action_match.group(1).strip()[:300] if action_match else (
        "Hi r/{sub}! I've been creating content about [topic] and wanted to get "
        "your community's perspective on [specific question]. What do you think about..."
    ).format(sub=top_subreddit)

    return {
        "title": draft_title,
        "body":  draft_body,
        "avoid_words": [
            "subscribe", "check out my channel", "I made a video",
            "follow me", "watch my", "link in bio",
        ],
    }


def render_first_post_draft(data: Mapping[str, Any], dark: bool) -> None:
    top_sub  = data["ranked_subreddits"][0]["subreddit"] if data["ranked_subreddits"] else ""
    draft    = extract_first_post_draft(str(data["strategy_report"]), top_sub)

    card_bg  = "rgba(255,255,255,0.06)" if dark else "rgba(255,255,255,0.82)"
    border   = "rgba(255,255,255,0.10)" if dark else "rgba(0,0,0,0.08)"
    text_col = "#F5F5F7" if dark else "#1C1C1E"
    sub_col  = "#A1A1AA"  if dark else "#6E6E73"
    tag_bg   = "#FEF2F2"
    tag_col  = "#F87171"

    avoid_tags = "".join(
        f'<span style="background:{tag_bg};color:{tag_col};font-size:11px;'
        f'padding:2px 8px;border-radius:4px;margin-right:6px;margin-bottom:4px;'
        f'display:inline-block">{escape(w)}</span>'
        for w in draft["avoid_words"]
    )

    html = (
        f'<div style="background:{card_bg};border:1px solid {border};'
        f'border-radius:14px;padding:18px 20px">'
        f'<p style="font-size:11px;font-weight:600;letter-spacing:.06em;'
        f'text-transform:uppercase;color:#A0A0A8;margin-bottom:14px">'
        f'First post draft · r/{escape(top_sub)}</p>'
        f'<p style="font-size:10px;font-weight:500;letter-spacing:.05em;'
        f'text-transform:uppercase;color:#A0A0A8;margin-bottom:4px">Title</p>'
        f'<p style="font-size:14px;font-weight:600;color:{text_col};'
        f'margin-bottom:16px;line-height:1.4">{escape(draft["title"])}</p>'
        f'<p style="font-size:10px;font-weight:500;letter-spacing:.05em;'
        f'text-transform:uppercase;color:#A0A0A8;margin-bottom:4px">Opening</p>'
        f'<p style="font-size:13px;color:{sub_col};line-height:1.65;'
        f'margin-bottom:16px">{escape(draft["body"])}</p>'
        f'<p style="font-size:10px;font-weight:500;letter-spacing:.05em;'
        f'text-transform:uppercase;color:#F87171;margin-bottom:8px">⚠ Avoid these phrases</p>'
        f'<div>{avoid_tags}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_dashboard(data: Mapping[str, Any], dark: bool) -> None:
    subs       = data["ranked_subreddits"]
    scores     = data["sentiment_scores"]
    meta       = data["meta"]
    all_rerank = [s["rerank_score"] for s in subs if s["rerank_score"] is not None]

    for s in subs:
        s["fit_score"] = normalize_fit_score(s["rerank_score"] or 0, all_rerank)

    hc_count   = len([s for s in subs if s.get("fit_score", 0) >= 70])
    top_fit    = subs[0]["fit_score"] if subs else 0
    top_name   = f'r/{subs[0]["subreddit"]}' if subs else "—"
    avg_sent   = sum(scores.values()) / len(scores) if scores else 0
    tone_lbl, tone_col = sentiment_label(avg_sent)

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        st.markdown(
            '<div class="cp-db-m1">'
            + metric_card_html(
                "HIGH-CONFIDENCE COMMUNITIES",
                str(hc_count),
                "fit score ≥ 70",
                sub_up=True,
                container_style="border-top:3px solid #3B82F6 !important;",
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="cp-db-m2">'
            + metric_card_html(
                "TOP FIT SCORE",
                f"{top_fit}/100",
                top_name,
                sub_up=True,
                container_style="border-top:3px solid #10B981 !important;",
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div class="cp-db-m3">'
            + metric_card_html(
                "COMMUNITY TONE",
                tone_lbl,
                f"avg {avg_sent:+.2f}",
                sub_up=avg_sent >= 0,
                container_style=f"border-top:3px solid {tone_col} !important;",
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            '<div class="cp-db-m4">'
            + metric_card_html(
                "COMMUNITIES ANALYZED",
                str(len(subs)),
                f"from {meta['retrieval_top_k']} retrieved",
                sub_up=False,
                container_style="border-top:3px solid #C7C7CC !important;",
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1], gap="medium")
    with col_left:
        render_action_cards(data, dark)
    with col_right:
        render_compare(data, dark)
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        render_sentiment(data["sentiment_scores"])
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        render_report(str(data["strategy_report"]))
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        render_first_post_draft(data, dark)

    st.markdown(
        f'<p style="font-size:11px;color:#A0A0A8;text-align:right;margin-top:4px">'
        f'Analysis in {meta["latency_ms"] / 1000:.1f}s</p>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="CreatorPal",
        page_icon=FAVICON_DATA_URI,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False

    dark = st.session_state["dark_mode"]
    bg = load_bg(str(resolve_bg_path(dark)))
    st.markdown(KEYFRAMES, unsafe_allow_html=True)
    st.markdown(get_css(dark=dark, bg=bg), unsafe_allow_html=True)

    if "last_result" not in st.session_state:
        st.session_state["last_result"] = None
    if "last_error" not in st.session_state:
        st.session_state["last_error"] = None
    if "is_loading" not in st.session_state:
        st.session_state["is_loading"] = False

    force_mock = _env_flag_enabled("CREATORPAL_USE_MOCK_PIPELINE")
    if "pipeline_is_mock" not in st.session_state:
        st.session_state["pipeline_is_mock"] = force_mock
    using_mock = bool(st.session_state.get("pipeline_is_mock", False))

    data: Mapping[str, Any] | None = st.session_state.get("last_result")
    error_message = st.session_state.get("last_error")
    is_loading = bool(st.session_state.get("is_loading", False))

    if data is None:
        st.markdown('<style>[data-testid="stSidebar"]{display:none !important;}</style>', unsafe_allow_html=True)
        st.markdown(
            """
<style>
[data-testid="stButton"][data-key="theme_toggle"],
.st-key-theme_toggle {
    position: fixed;
    top: 18px;
    right: 24px;
    z-index: 1001;
    width: auto !important;
}
[data-testid="stButton"][data-key="theme_toggle"] button,
.st-key-theme_toggle [data-testid="stButton"] {
    margin: 0 !important;
}
</style>
""",
            unsafe_allow_html=True,
        )
        render_theme_toggle()

        if is_loading:
            query = str(st.session_state.get("pending_query", "")).strip()
            goal = st.session_state.get("pending_goal")
            if not query:
                st.session_state["is_loading"] = False
                st.session_state["last_error"] = "Missing query payload."
                st.rerun()

            loading_placeholder = render_loading_hero(
                dark=dark,
                step=int(st.session_state.get("loading_step", 1)),
            )
            try:
                raw, pipeline_is_mock = run_with_loading(
                    channel_or_query=query,
                    user_query=goal,
                    dark=dark,
                    force_mock=force_mock,
                    loading_placeholder=loading_placeholder,
                )
                st.session_state["last_result"] = adapt(raw)
                st.session_state["pipeline_is_mock"] = pipeline_is_mock
                st.session_state["last_error"] = None
            except Exception as exc:
                st.session_state["last_result"] = None
                st.session_state["last_error"] = str(exc)
            finally:
                st.session_state["is_loading"] = False
                st.session_state.pop("loading_step", None)
                st.session_state.pop("pending_query", None)
                st.session_state.pop("pending_goal", None)
                st.rerun()

        channel_or_query, user_query, submitted = render_idle_hero(
            dark=dark,
            error_message=error_message,
        )
        if submitted:
            query = channel_or_query.strip()
            if not query:
                st.warning("Please enter a YouTube channel URL or topic keyword.")
                return
            st.session_state["is_loading"] = True
            st.session_state["pending_query"] = query
            st.session_state["pending_goal"] = user_query
            st.session_state["loading_step"] = 1
            st.session_state["last_error"] = None
            st.rerun()

        if using_mock:
            st.caption("Mock pipeline active — CREATORPAL_USE_MOCK_PIPELINE=1")
        return

    render_page_header(dark=dark)
    if st.button("← New query", key="reset"):
        st.session_state["last_result"] = None
        st.session_state["last_error"] = None
        st.session_state["is_loading"] = False
        st.session_state.pop("loading_step", None)
        st.session_state.pop("pending_query", None)
        st.session_state.pop("pending_goal", None)
        st.rerun()
    if using_mock:
        st.caption("Mock pipeline active — CREATORPAL_USE_MOCK_PIPELINE=1")
    if error_message:
        st.markdown(f'<div class="cp-db-error">{error_card_html(error_message)}</div>', unsafe_allow_html=True)

    render_dashboard(data, dark=dark)


if __name__ == "__main__":
    main()
