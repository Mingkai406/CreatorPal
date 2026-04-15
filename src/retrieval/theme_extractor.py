"""LLM-based channel theme extraction for retrieval query conditioning."""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a content-strategy analyst. "
    "Given a YouTube channel's metadata, video titles, and audience comments, "
    "extract the most important and distinctive topics/themes that define this channel. "
    "Focus on topics that would help find relevant Reddit communities for this creator. "
    "Return ONLY a newline-separated list of short topic phrases (2-5 words each). "
    "No numbering, no bullet points, no explanations, no extra text."
)


class ThemeExtractor:
    """Extract stable creator themes and topical keywords from channel context."""

    def __init__(self, client: OpenAI, model_name: str) -> None:
        self.client = client
        self.model = model_name
        logger.info("ThemeExtractor initialised – model=%s", model_name)

    def build_prompt(self, channel_payload: dict[str, Any], max_themes: int) -> str:
        """Build the instruction prompt used for topic extraction."""
        title = channel_payload.get("title", "")
        description = channel_payload.get("description", "")[:500]
        videos = channel_payload.get("videos", [])

        video_titles = "\n".join(
            f"- {v['title']}" for v in videos[:20] if v.get("title")
        )

        comment_samples: list[str] = []
        for v in videos[:10]:
            for c in v.get("comments", [])[:5]:
                text = c.get("text", "").strip()
                if text:
                    comment_samples.append(text)

        comments_block = "\n".join(f"- {c}" for c in comment_samples[:30])

        parts = [
            f"Channel: {title}",
            f"Description: {description}" if description else "",
            f"\nRecent video titles:\n{video_titles}" if video_titles else "",
            f"\nSample audience comments:\n{comments_block}" if comments_block else "",
            f"\nExtract up to {max_themes} themes.",
        ]
        return "\n".join(p for p in parts if p)

    def extract_themes(self, channel_payload: dict[str, Any], max_themes: int = 20) -> list[str]:
        """Return a ranked list of themes inferred from channel metadata and comments."""
        prompt = self.build_prompt(channel_payload, max_themes)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=256,
        )

        raw = response.choices[0].message.content or ""
        themes = [
            line.strip().lstrip("-•*0123456789. ")
            for line in raw.splitlines()
            if line.strip()
        ]
        themes = [t for t in themes if t][:max_themes]

        logger.info(
            "ThemeExtractor extracted %d themes for '%s'",
            len(themes),
            channel_payload.get("title", ""),
        )
        return themes
