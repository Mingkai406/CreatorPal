"""YouTube Data API v3 ingestion for channels, videos, and top comments."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class YouTubeIngestor:
    """Fetch channel metadata, video descriptions, and top comments.

    Optional on-disk cache (TTL) avoids repeated API calls for the same
    channel when ``cache_ttl_seconds`` > 0.  Cache files are keyed by
    resolved channel id and ``max_videos`` / ``max_comments_per_video``.
    """

    def __init__(
        self,
        api_key: str,
        *,
        cache_dir: Path | None = None,
        cache_ttl_seconds: int = 0,
    ) -> None:
        if not api_key:
            raise NotImplementedError("YOUTUBE_API_KEY is not set; skipping YouTubeIngestor.")
        self._client = build("youtube", "v3", developerKey=api_key)
        self._cache_dir = cache_dir
        self._cache_ttl = max(0, int(cache_ttl_seconds))
        if self._cache_ttl > 0 and self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(
                "YouTubeIngestor cache enabled – dir=%s ttl=%ds",
                self._cache_dir,
                self._cache_ttl,
            )
        else:
            logger.info("YouTubeIngestor initialised (cache disabled)")

    def _cache_path(
        self,
        channel_id: str,
        max_videos: int,
        max_comments_per_video: int,
    ) -> Path:
        assert self._cache_dir is not None
        safe = re.sub(r"[^\w.-]", "_", channel_id)
        name = f"{safe}_v{max_videos}_c{max_comments_per_video}.json"
        return self._cache_dir / name

    def _try_read_cache(
        self,
        channel_id: str,
        max_videos: int,
        max_comments_per_video: int,
    ) -> dict[str, Any] | None:
        if self._cache_ttl <= 0 or self._cache_dir is None:
            return None
        path = self._cache_path(channel_id, max_videos, max_comments_per_video)
        if not path.is_file():
            return None
        age = time.time() - path.stat().st_mtime
        if age >= self._cache_ttl:
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("channel_id") == channel_id:
                logger.info("YouTube cache HIT (%s, age %.0fs)", channel_id, age)
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("YouTube cache read failed: %s", exc)
        return None

    def _write_cache(
        self,
        channel_id: str,
        max_videos: int,
        max_comments_per_video: int,
        payload: dict[str, Any],
    ) -> None:
        if self._cache_ttl <= 0 or self._cache_dir is None:
            return
        path = self._cache_path(channel_id, max_videos, max_comments_per_video)
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("YouTube cache WRITE %s", path.name)
        except OSError as exc:
            logger.warning("YouTube cache write failed: %s", exc)

    def _resolve_channel_id(self, channel_url_or_id: str) -> str:
        """Resolve a URL, @handle, or raw channel ID to a YouTube channel ID."""
        text = channel_url_or_id.strip()

        # Already a bare channel ID (UC + 22 base64 chars)
        if re.match(r"^UC[\w-]{22}$", text):
            return text

        parsed = urlparse(text)
        path = parsed.path.strip("/")

        if path.startswith("@"):
            handle = path[1:]
        elif path.startswith("channel/"):
            return path.split("/", 1)[1]
        elif path.startswith(("c/", "user/")):
            username = path.split("/", 1)[1]
            resp = self._client.channels().list(
                part="id", forUsername=username
            ).execute()
            items = resp.get("items", [])
            if items:
                return items[0]["id"]
            raise ValueError(f"Cannot resolve YouTube username: {username}")
        else:
            # Treat the whole string as a handle (strip leading @)
            handle = text.lstrip("@")

        resp = self._client.channels().list(
            part="id", forHandle=handle
        ).execute()
        items = resp.get("items", [])
        if not items:
            raise ValueError(f"Cannot resolve YouTube handle: @{handle}")
        return items[0]["id"]

    def _fetch_channel_core(self, channel_id: str, max_videos: int) -> dict[str, Any]:
        """Fetch channel profile and recent videos (no comment threads)."""
        ch_resp = self._client.channels().list(
            part="snippet,statistics,contentDetails",
            id=channel_id,
        ).execute()
        ch_items = ch_resp.get("items", [])
        if not ch_items:
            raise ValueError(f"Channel not found: {channel_id}")

        ch = ch_items[0]
        snippet = ch.get("snippet", {})
        stats = ch.get("statistics", {})
        uploads_playlist = (
            ch.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads", "")
        )

        videos: list[dict[str, Any]] = []
        page_token: str | None = None

        while len(videos) < max_videos and uploads_playlist:
            pl_resp = self._client.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist,
                maxResults=min(50, max_videos - len(videos)),
                pageToken=page_token,
            ).execute()

            for item in pl_resp.get("items", []):
                vid_snippet = item.get("snippet", {})
                videos.append({
                    "video_id": item.get("contentDetails", {}).get("videoId", ""),
                    "title": vid_snippet.get("title", ""),
                    "description": vid_snippet.get("description", "")[:500],
                    "published_at": vid_snippet.get("publishedAt", ""),
                    "comments": [],
                })

            page_token = pl_resp.get("nextPageToken")
            if not page_token:
                break

        return {
            "channel_id": channel_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:1000],
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "country": snippet.get("country", ""),
            "videos": videos,
        }

    def get_channel_info(self, channel_url_or_id: str, max_videos: int = 20) -> dict[str, Any]:
        """Fetch channel profile and a bounded list of recent videos."""
        channel_id = self._resolve_channel_id(channel_url_or_id)
        return self._fetch_channel_core(channel_id, max_videos)

    def get_video_comments(self, video_id: str, max_comments: int = 100) -> list[dict[str, Any]]:
        """Fetch top comment threads for a single video."""
        comments: list[dict[str, Any]] = []
        try:
            resp = self._client.commentThreads().list(
                part="snippet",
                videoId=video_id,
                order="relevance",
                maxResults=min(100, max_comments),
                textFormat="plainText",
            ).execute()
            for item in resp.get("items", []):
                top = (
                    item.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet", {})
                )
                text = top.get("textDisplay", "").strip()
                if text:
                    comments.append({
                        "text": text[:300],
                        "like_count": int(top.get("likeCount", 0)),
                        "author": top.get("authorDisplayName", ""),
                    })
        except HttpError as exc:
            # Comments may be disabled for some videos; log and continue
            logger.warning("Could not fetch comments for video %s: %s", video_id, exc)
        return comments

    def ingest_channel(
        self,
        channel_url_or_id: str,
        max_videos: int = 20,
        max_comments_per_video: int = 100,
    ) -> dict[str, Any]:
        """Collect complete channel context needed by downstream retrieval."""
        logger.info("Ingesting YouTube channel: %s", channel_url_or_id)
        channel_id = self._resolve_channel_id(channel_url_or_id)

        cached = self._try_read_cache(channel_id, max_videos, max_comments_per_video)
        if cached is not None:
            return cached

        channel_info = self._fetch_channel_core(channel_id, max_videos)

        for video in channel_info["videos"]:
            video["comments"] = self.get_video_comments(
                video["video_id"],
                max_comments=max_comments_per_video,
            )
            logger.debug(
                "Fetched %d comments for video %s",
                len(video["comments"]),
                video["video_id"],
            )

        logger.info(
            "Channel ingestion complete: '%s' (%d videos)",
            channel_info["title"],
            len(channel_info["videos"]),
        )
        self._write_cache(channel_id, max_videos, max_comments_per_video, channel_info)
        return channel_info
