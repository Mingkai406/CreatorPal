"""Configuration model for CreatorPal services, models, and data paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_DEFAULTS = {
    "vllm_endpoint": "http://localhost:8000/v1",
    "vllm_model": "meta-llama/Llama-3.1-8B-Instruct",
    "embedding_model": "sentence-transformers/all-mpnet-base-v2",
    "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "sentiment_model": "cardiffnlp/twitter-roberta-base-sentiment-latest",
    "faiss_index_path": "data/processed/subreddit_profiles.faiss",
    "faiss_metadata_path": "data/processed/subreddit_profile_chunks.json",
}


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
    hybrid_alpha_keyword: float = 0.05
    hybrid_alpha_semantic: float = 0.95
    max_channel_videos: int = 20
    max_video_comments: int = 100
    youtube_cache_ttl_seconds: int = 0
    youtube_cache_dir: Path = Path("data/cache/youtube")

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables and defaults.

        Environment variable names are the uppercased field names, e.g.
        ``YOUTUBE_API_KEY``, ``VLLM_ENDPOINT``, etc.
        """
        def _get(key: str, default: str | None = None) -> str:
            val = os.environ.get(key.upper(), default)
            if val is None:
                raise EnvironmentError(f"Required environment variable {key.upper()} is not set")
            return val

        return cls(
            youtube_api_key=_get("youtube_api_key", ""),
            vllm_endpoint=_get("vllm_endpoint", _DEFAULTS["vllm_endpoint"]),
            vllm_model=_get("vllm_model", _DEFAULTS["vllm_model"]),
            embedding_model=_get("embedding_model", _DEFAULTS["embedding_model"]),
            reranker_model=_get("reranker_model", _DEFAULTS["reranker_model"]),
            sentiment_model=_get("sentiment_model", _DEFAULTS["sentiment_model"]),
            faiss_index_path=Path(_get("faiss_index_path", _DEFAULTS["faiss_index_path"])),
            faiss_metadata_path=Path(_get("faiss_metadata_path", _DEFAULTS["faiss_metadata_path"])),
            retrieval_top_k=int(_get("retrieval_top_k", "50")),
            rerank_top_k=int(_get("rerank_top_k", "10")),
            hybrid_alpha_keyword=float(_get("hybrid_alpha_keyword", "0.05")),
            hybrid_alpha_semantic=float(_get("hybrid_alpha_semantic", "0.95")),
            max_channel_videos=int(_get("max_channel_videos", "20")),
            max_video_comments=int(_get("max_video_comments", "100")),
            youtube_cache_ttl_seconds=int(_get("youtube_cache_ttl_seconds", "0")),
            youtube_cache_dir=Path(_get("youtube_cache_dir", "data/cache/youtube")),
        )


def load_settings() -> Settings:
    """Load ``.env`` values into the process environment, then build Settings."""
    load_dotenv(override=False)
    return Settings.from_env()
