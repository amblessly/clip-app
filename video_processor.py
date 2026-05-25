"""Video clipping engine using FFmpeg for large-file performance."""

from __future__ import annotations

import json
import logging
import random
import subprocess
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed

from tqdm import tqdm
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

logger = logging.getLogger(__name__)

ClipMode = Literal["random", "sequential"]
ProgressCallback = Callable[[float, str], None]

OUTPUT_DIR = Path("output")
UPLOAD_DIR = Path("uploads")
MAX_CLIPS_UI = 50  # Streamlit slider cap; longer videos use max fit up to this


@dataclass
class VideoInfo:
    path: Path
    duration: float
    width: int
    height: int
    codec: str
    fps: float


@dataclass
class ClipSegment:
    index: int
    start: float
    duration: float


@dataclass
class ProcessingResult:
    success: bool
    clips: list[Path]
    logs: list[str]
    segments: list[ClipSegment] = field(default_factory=list)
    error: str | None = None


def _run_cmd(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def ensure_directories() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def validate_video(path: Path) -> tuple[bool, str]:
    """Verify the file is a readable video via ffprobe."""
    if not path.exists():
        return False, "File does not exist."
    if path.stat().st_size == 0:
        return False, "File is empty."

    result = _run_cmd(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        timeout=120,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "Unknown ffprobe error").strip()
        return False, f"Invalid or corrupted video: {err}"

    try:
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return False, "Could not parse video metadata."

    if duration <= 0:
        return False, "Video has no readable duration."

    return True, ""


def get_video_info(path: Path) -> VideoInfo:
    """Extract duration, resolution, codec, and fps."""
    result = _run_cmd(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    duration = float(data["format"]["duration"])

    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if not video_stream:
        raise RuntimeError("No video stream found.")

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    codec = video_stream.get("codec_name", "unknown")

    fps_raw = video_stream.get("r_frame_rate", "30/1")
    if "/" in fps_raw:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den) if float(den) else 30.0
    else:
        fps = float(fps_raw)

    return VideoInfo(
        path=path,
        duration=duration,
        width=width,
        height=height,
        codec=codec,
        fps=fps,
    )


def detect_silence_boundaries(
    path: Path,
    noise_db: int = -35,
    min_silence: float = 0.5,
) -> tuple[float, float]:
    """
    Detect intro/outro silence using ffmpeg silencedetect.
    Returns (trim_start, trim_end) in seconds within the video.
    """
    result = _run_cmd(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ],
        timeout=600,
    )
    stderr = result.stderr or ""
    silence_starts: list[float] = []
    silence_ends: list[float] = []

    for line in stderr.splitlines():
        if "silence_start:" in line:
            try:
                silence_starts.append(float(line.split("silence_start:")[-1].strip()))
            except ValueError:
                pass
        elif "silence_end:" in line:
            try:
                part = line.split("silence_end:")[-1].split("|")[0].strip()
                silence_ends.append(float(part))
            except ValueError:
                pass

    info = get_video_info(path)
    duration = info.duration

    trim_start = 0.0
    trim_end = duration

    # Leading silence: first silence block starting near 0
    if silence_starts and silence_starts[0] < 1.0:
        if silence_ends:
            trim_start = min(silence_ends[0], duration * 0.15)

    # Trailing silence: last silence block ending near duration
    if silence_starts:
        last_start = silence_starts[-1]
        if last_start > duration * 0.85:
            trim_end = max(last_start, duration * 0.85)

    trim_start = max(0.0, min(trim_start, duration - 1))
    trim_end = max(trim_start + 1, min(trim_end, duration))
    return trim_start, trim_end


def suggest_clip_settings(duration_sec: float) -> dict:
    """
    Auto-suggest clip duration and count from video length (non-overlap friendly).
    Returns clip_duration, num_clips, max_clips, label (human-readable duration).
    """
    if duration_sec < 5:
        d = max(5, int(duration_sec))
        return {
            "clip_duration": d,
            "num_clips": 1,
            "max_clips": 1,
            "label": f"{duration_sec:.0f}s video",
        }

    # Short-form default: 15s clips; longer videos: 30s
    if duration_sec <= 90:
        clip_duration = 15
    elif duration_sec <= 600:
        clip_duration = 20
    else:
        clip_duration = 30

    max_clips = max_non_overlap_clips(duration_sec, clip_duration)
    num_clips = min(max_clips, MAX_CLIPS_UI)
    capped = max_clips > MAX_CLIPS_UI

    return {
        "clip_duration": int(clip_duration),
        "num_clips": int(num_clips),
        "max_clips": int(max_clips),
        "capped_to_ui_max": capped,
        "label": f"{duration_sec:.0f}s ({_format_duration_short(duration_sec)})",
    }


def _format_duration_short(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def max_non_overlap_clips(effective_duration: float, clip_duration: float) -> int:
    """How many back-to-back clips fit without overlap."""
    if effective_duration < clip_duration:
        return 0
    return max(1, int(effective_duration // clip_duration))


def adjust_clip_count(
    effective_duration: float,
    clip_duration: float,
    num_clips: int,
    mode: ClipMode,
    overlap_mode: bool,
) -> tuple[int, str | None]:
    """
    Fit clip count to video length. Returns (clips_to_use, warning_or_none).
    Raises ValueError if even one clip cannot fit.
    """
    if effective_duration < clip_duration:
        raise ValueError(
            f"Video is only {effective_duration:.1f}s but each clip is {clip_duration:.0f}s. "
            "Lower clip duration in the sidebar."
        )

    if overlap_mode:
        return num_clips, None

    cap = max_non_overlap_clips(effective_duration, clip_duration)
    if num_clips > cap:
        return cap, (
            f"Adjusted clip count {num_clips} → {cap} "
            f"({effective_duration:.0f}s video, {clip_duration:.0f}s per clip, no overlap)."
        )
    return num_clips, None


def validate_clip_settings(
    duration_sec: float,
    clip_duration: float,
    num_clips: int,
    overlap_mode: bool,
) -> tuple[bool, str, int]:
    """
    Check settings against video length before processing.
    Returns (ok, message, max_recommended_clips).
    """
    if duration_sec < clip_duration:
        return (
            False,
            f"Clip duration ({clip_duration:.0f}s) is longer than the video ({duration_sec:.0f}s).",
            0,
        )
    cap = max_non_overlap_clips(duration_sec, clip_duration)
    if not overlap_mode and num_clips > cap:
        need = num_clips * clip_duration
        return (
            False,
            f"Need {need:.0f}s for {num_clips} clips × {clip_duration:.0f}s, but video is only "
            f"{duration_sec:.0f}s. Use at most **{cap}** clips, enable **Overlap mode**, or shorten clip duration.",
            cap,
        )
    return True, "", cap


def calculate_segments(
    effective_duration: float,
    effective_start: float,
    clip_duration: float,
    num_clips: int,
    mode: ClipMode,
    overlap_mode: bool,
) -> list[ClipSegment]:
    """Compute non-overlapping or overlapping clip start times."""
    if effective_duration < clip_duration:
        raise ValueError(
            f"Usable video length ({effective_duration:.1f}s) is shorter than clip duration ({clip_duration}s)."
        )

    max_start = effective_start + effective_duration - clip_duration
    if max_start < effective_start:
        raise ValueError("Not enough video content for even one clip.")

    segments: list[ClipSegment] = []

    if mode == "sequential":
        if overlap_mode:
            if num_clips <= 1:
                starts = [effective_start]
            else:
                step = (effective_duration - clip_duration) / (num_clips - 1)
                starts = [effective_start + i * step for i in range(num_clips)]
        else:
            total_span = num_clips * clip_duration
            if total_span > effective_duration:
                raise ValueError(
                    f"Sequential non-overlap needs {total_span:.1f}s but only {effective_duration:.1f}s available. "
                    "Enable overlap mode or reduce clips/duration."
                )
            starts = [effective_start + i * clip_duration for i in range(num_clips)]
    else:
        # Random placement
        if overlap_mode:
            starts = [
                effective_start + random.uniform(0, effective_duration - clip_duration)
                for _ in range(num_clips)
            ]
        else:
            available = effective_duration - num_clips * clip_duration
            if available < 0:
                raise ValueError(
                    f"Random non-overlap needs {num_clips * clip_duration:.1f}s but only "
                    f"{effective_duration:.1f}s available. Enable overlap or reduce settings."
                )
            # Partition timeline into slots and pick random offset within each
            slot_size = available / num_clips
            starts = []
            for i in range(num_clips):
                slot_start = effective_start + i * (clip_duration + slot_size)
                offset = random.uniform(0, slot_size) if slot_size > 0 else 0
                starts.append(slot_start + offset)

    for idx, start in enumerate(starts, start=1):
        start = max(effective_start, min(start, max_start))
        segments.append(ClipSegment(index=idx, start=start, duration=clip_duration))

    return segments


def recommended_max_workers() -> int:
    """Conservative default for low-RAM PCs (e.g. 8GB)."""
    return 1


def _extract_clip_fast(input_path: str, output_path: str, start: float, duration: float) -> tuple[bool, str]:
    """
    Fast clip cut: stream copy first (no re-encode), then ultrafast x264 fallback.
    -ss before -i = faster seek on long files.
    """
    copy_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(start),
        "-i",
        input_path,
        "-t",
        str(duration),
        "-map",
        "0:v:0?",
        "-map",
        "0:a:0?",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "1",
        "-movflags",
        "+faststart",
        output_path,
    ]
    result = _run_cmd(copy_cmd, timeout=3600)
    if result.returncode == 0 and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
        return True, ""

    encode_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(start),
        "-i",
        input_path,
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-threads",
        "1",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        output_path,
    ]
    result = _run_cmd(encode_cmd, timeout=3600)
    if result.returncode != 0:
        return False, result.stderr or "ffmpeg extraction failed"
    return True, ""


def _extract_clip_worker(args: tuple[str, str, float, float]) -> tuple[bool, str, str]:
    """Worker for multiprocessing: extract one clip."""
    input_path, output_path, start, duration = args
    ok, err = _extract_clip_fast(input_path, output_path, start, duration)
    if not ok:
        return False, output_path, err
    return True, output_path, ""


def extract_clips_parallel(
    input_path: Path,
    segments: list[ClipSegment],
    output_dir: Path,
    max_workers: int = 1,
    on_progress: ProgressCallback | None = None,
) -> tuple[list[Path], list[str]]:
    """Extract clips — sequential when workers=1 (low RAM), else small pool."""
    output_dir.mkdir(parents=True, exist_ok=True)
    max_workers = max(1, min(2, int(max_workers)))

    logs: list[str] = []
    successful: list[Path] = []
    total = len(segments)
    inp = str(input_path)

    if max_workers <= 1:
        for i, seg in enumerate(segments, start=1):
            out = output_dir / f"clip_{seg.index}.mp4"
            ok, err = _extract_clip_fast(inp, str(out), seg.start, seg.duration)
            if on_progress:
                on_progress(i / total, f"Clip {i}/{total}")
            if ok:
                successful.append(out)
                logs.append(f"[OK] Created {out.name} (start={seg.start:.2f}s)")
            else:
                logs.append(f"[FAIL] Failed {out.name}: {err}")
    else:
        tasks = [
            (inp, str(output_dir / f"clip_{seg.index}.mp4"), seg.start, seg.duration)
            for seg in segments
        ]
        completed = 0
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_extract_clip_worker, t): t for t in tasks}
            for future in as_completed(futures):
                ok, out_path, err = future.result()
                completed += 1
                if on_progress:
                    on_progress(completed / total, f"Clip {completed}/{total}")
                if ok:
                    successful.append(Path(out_path))
                    t = futures[future]
                    logs.append(f"[OK] Created {Path(out_path).name} (start={t[2]:.2f}s)")
                else:
                    logs.append(f"[FAIL] Failed {Path(out_path).name}: {err}")

    successful.sort(key=lambda p: p.name)
    return successful, logs


def clear_output_dir(output_dir: Path | None = None) -> None:
    target = output_dir or OUTPUT_DIR
    if target.exists():
        for f in target.glob("clip_*.mp4"):
            f.unlink(missing_ok=True)


def create_zip_archive(clips: list[Path], zip_path: Path | None = None) -> Path:
    """Bundle all clips into a single ZIP."""
    zip_path = zip_path or OUTPUT_DIR / "all_clips.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for clip in clips:
            zf.write(clip, arcname=clip.name)
    return zip_path


def process_video(
    input_path: Path,
    clip_duration: float,
    num_clips: int,
    mode: ClipMode = "random",
    overlap_mode: bool = False,
    trim_silence: bool = False,
    max_workers: int = 1,
    on_progress: ProgressCallback | None = None,
) -> ProcessingResult:
    """Full pipeline: validate → optional silence trim → segment → extract."""
    logs: list[str] = []

    def report(pct: float, msg: str) -> None:
        logs.append(msg)
        if on_progress:
            on_progress(pct, msg)

    try:
        report(0.05, "Validating video...")
        ok, err = validate_video(input_path)
        if not ok:
            return ProcessingResult(False, [], logs, segments=[], error=err)

        report(0.1, "Reading video metadata...")
        info = get_video_info(input_path)
        logs.append(
            f"Source: {info.duration:.1f}s, {info.width}x{info.height}, "
            f"{info.codec} @ {info.fps:.1f}fps"
        )

        trim_start, trim_end = 0.0, info.duration
        if trim_silence:
            report(0.15, "Detecting intro/outro silence...")
            try:
                trim_start, trim_end = detect_silence_boundaries(input_path)
                logs.append(f"Trim range: {trim_start:.1f}s – {trim_end:.1f}s")
            except Exception as exc:
                logs.append(f"Silence detection skipped: {exc}")

        effective_start = trim_start
        effective_duration = trim_end - trim_start

        report(0.2, "Calculating clip segments...")
        try:
            num_clips, adjust_msg = adjust_clip_count(
                effective_duration,
                clip_duration,
                num_clips,
                mode,
                overlap_mode,
            )
        except ValueError as exc:
            return ProcessingResult(False, [], logs, segments=[], error=str(exc))
        if adjust_msg:
            logs.append(adjust_msg)

        segments = calculate_segments(
            effective_duration=effective_duration,
            effective_start=effective_start,
            clip_duration=clip_duration,
            num_clips=num_clips,
            mode=mode,
            overlap_mode=overlap_mode,
        )
        for seg in segments:
            logs.append(f"Segment {seg.index}: start={seg.start:.2f}s, duration={seg.duration}s")

        clear_output_dir()

        def clip_progress(done_ratio: float, msg: str) -> None:
            # Map extraction 0–1 into overall 0.25–0.95
            overall = 0.25 + done_ratio * 0.7
            report(overall, msg)

        report(0.25, f"Extracting {num_clips} clips (parallel workers={max_workers})...")
        clips, extract_logs = extract_clips_parallel(
            input_path,
            segments,
            OUTPUT_DIR,
            max_workers=max_workers,
            on_progress=clip_progress,
        )
        logs.extend(extract_logs)

        if not clips:
            return ProcessingResult(
                False, [], logs, segments=segments, error="No clips were generated."
            )

        report(1.0, f"Done — {len(clips)} clip(s) ready.")
        return ProcessingResult(True, clips, logs, segments=segments)

    except Exception as exc:
        logger.exception("Processing failed")
        logs.append(f"Error: {exc}")
        return ProcessingResult(False, [], logs, segments=[], error=str(exc))
