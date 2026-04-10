"""YouTube ingestion package for channel metadata and comment retrieval."""

from __future__ import annotations

from src.ingest.youtube import YouTubeIngestor


def build_ingestor(api_key: str) -> YouTubeIngestor:
    """Construct a YouTube ingestor for pipeline usage."""
    raise NotImplementedError("Implement ingestion factory helper.")
