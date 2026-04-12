"""Configuration model for CreatorPal services, models, and data paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the CreatorPal pipeline."""

    youtube_api_key: str
    vllm_endpoint: str
    vllm_model: str
    embedding_model: str
    reranker_model: str
    sentiment_model: str
    faiss_index_path: Path
    faiss_metadata_path: Path
    retrieval_top_k: int = 50
    rerank_top_k: int = 10
    hybrid_alpha_keyword: float = 0.15
    hybrid_alpha_semantic: float = 0.85
    max_channel_videos: int = 20
    max_video_comments: int = 100

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables and defaults."""
        raise NotImplementedError("Implement environment-backed settings loading.")


def load_settings() -> Settings:
    """Load `.env` values and construct a Settings object."""
    raise NotImplementedError("Implement settings bootstrap with python-dotenv.")
