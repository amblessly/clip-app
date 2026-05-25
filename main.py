"""Auto Clip Studio — upload videos or YouTube (sidebar) → auto clip."""

from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

from ui import (
    ICON,
    apply_pending_suggestions,
    apply_theme,
    apply_suggested_settings,
    queue_suggested_settings,
    render_clip_downloads,
    render_header,
    render_logs,
    prepare_slider_state,
    render_upload_hint,
    render_sidebar_settings,
    render_sidebar_youtube,
    render_youtube_hint_in_main,
    section_title,
)
from video_processor import (
    UPLOAD_DIR,
    create_zip_archive,
    ensure_directories,
    get_video_info,
    process_video,
    validate_clip_settings,
    validate_video,
)
from youtube_loader import (
    download_video,
    fetch_metadata,
    get_cached_video_path,
    is_valid_youtube_url,
    normalize_youtube_url,
)

st.set_page_config(
    page_title="Auto Clip Studio",
    page_icon=f":material/{ICON['app']}:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def save_upload_with_progress(uploaded_file, dest: Path) -> list[str]:
    logs: list[str] = []
    chunk_size = 4 * 1024 * 1024
    total = uploaded_file.size or 0
    written = 0

    progress = st.progress(0.0, text="Uploading video...")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "wb") as out:
        uploaded_file.seek(0)
        while True:
            chunk = uploaded_file.read(chunk_size)
            if not chunk:
                break
            out.write(chunk)
            written += len(chunk)
            if total > 0:
                pct = min(written / total, 1.0)
                progress.progress(pct, text=f"Uploading… {pct * 100:.0f}%")
            else:
                progress.progress(0.5, text="Uploading…")

    progress.progress(1.0, text="Upload complete")
    time.sleep(0.3)
    progress.empty()

    size_mb = dest.stat().st_size / (1024 * 1024)
    logs.append(f"Saved upload: {dest.name} ({size_mb:.1f} MB)")
    return logs


def init_session_state() -> None:
    defaults = {
        "source": None,  # "file" | "youtube"
        "youtube_url": "",
        "video_meta": None,
        "upload_path": None,
        "video_valid": False,
        "clips": [],
        "zip_path": None,
        "clip_segments": [],
        "process_logs": [],
        "last_upload_name": None,
        "clip_duration_slider": 15,
        "num_clips_slider": 5,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def clear_youtube_state() -> None:
    st.session_state.youtube_url = ""
    st.session_state.video_meta = None
    st.session_state.last_suggested_duration = None
    if st.session_state.get("source") == "youtube":
        st.session_state.source = None
        st.session_state.upload_path = None
        st.session_state.video_valid = False


def handle_youtube_fetch(url: str) -> None:
    if not url:
        st.sidebar.warning("Paste a YouTube link first.")
        return
    if not is_valid_youtube_url(url):
        st.sidebar.error("Invalid YouTube URL.")
        return

    url = normalize_youtube_url(url)
    with st.spinner("Fetching video info…"):
        try:
            meta = fetch_metadata(url)
        except Exception as exc:
            st.sidebar.error(f"Fetch failed: {exc}")
            return

    st.session_state.source = "youtube"
    st.session_state.youtube_url = url
    st.session_state.video_meta = meta
    st.session_state.last_upload_name = None
    st.session_state.clips = []
    st.session_state.zip_path = None
    st.session_state.process_logs = [f"Fetched: {meta.title}"]

    cached = get_cached_video_path(meta.video_id)
    if cached:
        st.session_state.upload_path = cached
        st.session_state.video_valid = True
        st.session_state.process_logs.append(f"[OK] Cached: {cached.name}")
    else:
        st.session_state.upload_path = None
        st.session_state.video_valid = False
        st.session_state.process_logs.append("Click Generate Clips to download and process.")

    if meta.duration:
        queue_suggested_settings(float(meta.duration))
    st.rerun()


def maybe_auto_suggest_settings() -> None:
    """Apply suggestions when a new video duration is detected (before sliders)."""
    dur = known_duration_sec()
    if not dur:
        return
    last = st.session_state.get("last_suggested_duration")
    if last is None or abs(last - dur) > 0.5:
        apply_suggested_settings(dur)


def known_duration_sec() -> float | None:
    """Video length from file or YouTube metadata."""
    if st.session_state.get("upload_path") and st.session_state.get("video_valid"):
        try:
            return get_video_info(Path(st.session_state.upload_path)).duration
        except Exception:
            pass
    meta = st.session_state.get("video_meta")
    if meta and st.session_state.get("source") == "youtube":
        return float(meta.duration)
    return None


def can_generate() -> bool:
    if st.session_state.get("source") == "file":
        path = st.session_state.get("upload_path")
        return bool(path and Path(path).exists() and st.session_state.get("video_valid"))
    if st.session_state.get("source") == "youtube":
        return bool(st.session_state.get("video_meta") and st.session_state.get("youtube_url"))
    return False


def resolve_video_path(
    on_progress,
) -> tuple[Path, list[str]]:
    """Return path to video file; download YouTube if needed."""
    logs: list[str] = []
    source = st.session_state.get("source")

    if source == "file":
        path = Path(st.session_state.upload_path)
        if not path.exists():
            raise FileNotFoundError("Uploaded file not found.")
        return path, logs

    if source == "youtube":
        meta = st.session_state.video_meta
        if not meta:
            raise ValueError("No YouTube video loaded. Fetch a link in the sidebar.")

        path = st.session_state.get("upload_path")
        if path and Path(path).exists() and st.session_state.get("video_valid"):
            logs.append("Using cached YouTube download.")
            on_progress(0.4, "Using cached download…")
            return Path(path), logs

        logs.append("Downloading from YouTube…")
        downloaded = download_video(
            st.session_state.youtube_url,
            meta.video_id,
            on_progress=lambda p, m: on_progress(p * 0.4, m),
        )
        st.session_state.upload_path = downloaded
        st.session_state.video_valid = True
        logs.append(f"[OK] Downloaded {downloaded.name}")
        return downloaded, logs

    raise ValueError("Upload a video or fetch a YouTube link in the sidebar.")


def main() -> None:
    ensure_directories()
    init_session_state()
    apply_theme()
    render_header()

    dur = known_duration_sec()
    apply_pending_suggestions(dur)
    maybe_auto_suggest_settings()
    prepare_slider_state(dur)
    settings = render_sidebar_settings(dur)
    yt_url, yt_fetch, yt_clear = render_sidebar_youtube()

    if yt_clear:
        clear_youtube_state()
        st.session_state.process_logs = []
        st.rerun()

    if yt_fetch:
        handle_youtube_fetch(yt_url)

    col_upload, col_preview = st.columns([1, 1], gap="large")

    with col_upload:
        st.markdown("**Upload**")
        render_upload_hint()
        uploaded = st.file_uploader(
            "Video file",
            type=["mp4", "mov", "mkv", "avi", "webm", "flv", "wmv", "m4v", "mpeg", "mpg"],
            label_visibility="collapsed",
        )

        if uploaded is not None:
            safe_name = Path(uploaded.name).name
            dest = UPLOAD_DIR / safe_name

            if st.session_state.get("last_upload_name") != safe_name:
                with st.spinner("Saving upload..."):
                    upload_logs = save_upload_with_progress(uploaded, dest)
                st.session_state.last_upload_name = safe_name
                st.session_state.source = "file"
                st.session_state.upload_path = dest
                st.session_state.process_logs = upload_logs
                st.session_state.clips = []
                st.session_state.zip_path = None
                st.session_state.video_meta = None
                st.session_state.youtube_url = ""

                ok, err = validate_video(dest)
                st.session_state.video_valid = ok
                if ok:
                    info = get_video_info(dest)
                    s = queue_suggested_settings(info.duration)
                    st.session_state.process_logs.append(
                        f"Validated: {info.duration:.1f}s, {info.width}×{info.height}"
                    )
                    st.session_state.process_logs.append(
                        f"Suggested: {s.get('num_clips')} clips × {s.get('clip_duration')}s"
                    )
                    st.rerun()
                else:
                    st.session_state.process_logs.append(f"Validation failed: {err}")
                    st.error(err, icon=":material/error:")

    with col_preview:
        st.markdown("**Preview**")
        path = st.session_state.get("upload_path")
        if path and Path(path).exists() and st.session_state.get("video_valid"):
            try:
                info = get_video_info(Path(path))
                m1, m2, m3 = st.columns(3)
                m1.metric("Duration", f"{info.duration:.0f}s")
                m2.metric("Resolution", f"{info.width}×{info.height}")
                m3.metric("FPS", f"{info.fps:.1f}")
                st.video(str(path))
            except Exception as exc:
                st.warning(f"Preview unavailable: {exc}")
        elif st.session_state.get("source") == "youtube" and st.session_state.get("video_meta"):
            render_youtube_hint_in_main()
            meta = st.session_state.video_meta
            if meta.thumbnail:
                st.image(meta.thumbnail, width="stretch")
            st.markdown(f"**{meta.title}**")
            st.caption(meta.uploader)
        else:
            st.caption("Upload a file or fetch YouTube from the sidebar.")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    ready = can_generate()
    generate = st.button(
        "Generate clips",
        type="primary",
        icon=":material/auto_awesome:",
        disabled=not ready,
        use_container_width=True,
    )
    if not ready:
        st.caption("Add a video first (upload or YouTube in sidebar).")

    if generate and ready:
        dur = known_duration_sec()
        if dur:
            ok_settings, msg, cap = validate_clip_settings(
                dur,
                settings["clip_duration"],
                settings["num_clips"],
                settings["overlap_mode"],
            )
            if not ok_settings:
                if settings["clip_duration"] > dur:
                    st.error(msg)
                    st.stop()
                if not settings["overlap_mode"]:
                    st.warning(f"{msg} Will use **{cap}** clips automatically.")

        all_logs: list[str] = list(st.session_state.get("process_logs", []))
        progress_bar = st.progress(0.0, text="Starting…")
        status = st.empty()

        def on_progress(pct: float, msg: str) -> None:
            progress_bar.progress(min(max(pct, 0.0), 1.0), text=msg)
            status.caption(msg)

        try:

            def prep_progress(pct: float, msg: str) -> None:
                on_progress(pct * 0.45, msg)

            video_path, prep_logs = resolve_video_path(prep_progress)
            all_logs.extend(prep_logs)

            info = get_video_info(video_path)
            all_logs.append(
                f"Source: {info.duration:.0f}s, {info.width}×{info.height}, {info.fps:.0f} fps"
            )

            def clip_progress(pct: float, msg: str) -> None:
                on_progress(0.45 + pct * 0.55, msg)

            result = process_video(
                input_path=video_path,
                clip_duration=settings["clip_duration"],
                num_clips=settings["num_clips"],
                mode=settings["mode"],
                overlap_mode=settings["overlap_mode"],
                trim_silence=settings["trim_silence"],
                max_workers=settings["max_workers"],
                on_progress=clip_progress,
            )

            all_logs.extend(result.logs)
            progress_bar.progress(1.0, text="Complete")
            status.empty()

            if result.success:
                st.session_state.clips = result.clips
                st.session_state.clip_segments = result.segments
                st.session_state.zip_path = create_zip_archive(result.clips)
                st.success(
                    f"Generated {len(result.clips)} clip(s) in output/",
                    icon=":material/check_circle:",
                )
            else:
                st.session_state.clips = []
                st.session_state.clip_segments = []
                st.session_state.zip_path = None
                st.error(result.error or "Processing failed.")

        except Exception as exc:
            progress_bar.empty()
            status.empty()
            all_logs.append(f"Error: {exc}")
            st.error(str(exc))

        st.session_state.process_logs = all_logs

    render_logs(st.session_state.get("process_logs", []))

    clips = st.session_state.get("clips") or []
    if clips:
        render_clip_downloads(
            clips,
            st.session_state.get("zip_path"),
            st.session_state.get("clip_segments"),
        )


if __name__ == "__main__":
    main()
