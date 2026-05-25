"""YouTube URL validation, metadata, and download via yt-dlp."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yt_dlp

from video_processor import UPLOAD_DIR, validate_video

ProgressCallback = Callable[[float, str], None]

YOUTUBE_URL_RE = re.compile(
    r"^(https?://)?(www\.)?"
    r"(youtube\.com/(watch\?v=|embed/|shorts/|live/)|youtu\.be/)"
    r"[\w-]{6,}",
    re.IGNORECASE,
)


@dataclass
class YouTubeMetadata:
    video_id: str
    title: str
    uploader: str
    duration: float
    description: str
    thumbnail: str
    webpage_url: str
    filesize_approx: int | None = None
    resolution: str | None = None


def normalize_youtube_url(url: str) -> str:
    return url.strip()


def is_valid_youtube_url(url: str) -> bool:
    return bool(url and YOUTUBE_URL_RE.match(normalize_youtube_url(url)))


def _format_duration(seconds: float | None) -> str:
    if not seconds:
        return "—"
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def duration_display(seconds: float | None) -> str:
    return _format_duration(seconds)


def fetch_metadata(url: str) -> YouTubeMetadata:
    """Fetch video info without downloading."""
    url = normalize_youtube_url(url)
    if not is_valid_youtube_url(url):
        raise ValueError("Invalid YouTube URL. Use a link like https://youtu.be/VIDEO_ID")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise RuntimeError("Could not read video information.")

    height = info.get("height")
    width = info.get("width")
    resolution = f"{width}x{height}" if width and height else None

    desc = info.get("description") or ""
    if len(desc) > 600:
        desc = desc[:600] + "…"

    return YouTubeMetadata(
        video_id=info.get("id") or "video",
        title=info.get("title") or "Untitled",
        uploader=info.get("uploader") or info.get("channel") or "Unknown",
        duration=float(info.get("duration") or 0),
        description=desc,
        thumbnail=info.get("thumbnail") or "",
        webpage_url=info.get("webpage_url") or url,
        filesize_approx=info.get("filesize") or info.get("filesize_approx"),
        resolution=resolution,
    )


def _expected_output_path(video_id: str) -> Path:
    return UPLOAD_DIR / f"{video_id}.mp4"


def get_cached_video_path(video_id: str) -> Path | None:
    path = _expected_output_path(video_id)
    if path.exists():
        ok, _ = validate_video(path)
        if ok:
            return path
    return None


def download_video(
    url: str,
    video_id: str,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Download YouTube video as MP4 (max 720p for faster/low-RAM systems)."""
    url = normalize_youtube_url(url)
    out_path = _expected_output_path(video_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cached = get_cached_video_path(video_id)
    if cached:
        if on_progress:
            on_progress(1.0, "Using cached download")
        return cached

    last_pct = [0.0]

    def hook(status: dict) -> None:
        if not on_progress:
            return
        if status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            done = status.get("downloaded_bytes", 0)
            if total:
                pct = min(done / total, 0.92)
                if pct - last_pct[0] >= 0.02:
                    last_pct[0] = pct
                    mb_done = done / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    on_progress(pct, f"Downloading… {mb_done:.0f}/{mb_total:.0f} MB")
            else:
                on_progress(0.3, "Downloading video…")
        elif status.get("status") == "finished":
            on_progress(0.95, "Merging audio/video…")

    opts = {
        # 720p max — faster download & less RAM on modest PCs
        "format": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/best[height<=720]",
        "merge_output_format": "mp4",
        "outtmpl": str(UPLOAD_DIR / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not out_path.exists():
        # yt-dlp may use different extension before merge
        candidates = list(UPLOAD_DIR.glob(f"{video_id}.*"))
        mp4s = [p for p in candidates if p.suffix.lower() == ".mp4"]
        if mp4s:
            out_path = mp4s[0]
        elif candidates:
            out_path = candidates[0]
        else:
            raise RuntimeError("Download finished but output file was not found.")

    ok, err = validate_video(out_path)
    if not ok:
        raise RuntimeError(f"Downloaded file is invalid: {err}")

    if on_progress:
        on_progress(1.0, "Download complete")
    return out_path
