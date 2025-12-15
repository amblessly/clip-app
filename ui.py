"""Streamlit UI — Cursor-inspired dark theme, white primary buttons, Material icons."""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

from video_processor import (
    ClipSegment,
    MAX_CLIPS_UI,
    max_non_overlap_clips,
    suggest_clip_settings,
)

APP_NAME = "Auto Clip Studio"
APP_LEAD = "Upload a video or add a YouTube link in the sidebar, then generate clips."

ICON = {
    "app": "content_cut",
    "settings": "tune",
    "upload": "cloud_upload",
    "preview": "movie",
    "generate": "auto_awesome",
    "log": "terminal",
    "download": "download",
    "zip": "folder_zip",
    "clip": "movie_filter",
    "link": "link",
    "clear": "close",
    "youtube": "smart_display",
    "caption": "subtitles",
    "tag": "tag",
    "copy": "content_copy",
}


def ic(name: str) -> str:
    return f":material/{ICON[name]}:"


CURSOR_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --bg: #1c1c1c;
        --bg-panel: #252526;
        --bg-elevated: #2d2d2d;
        --border: #3c3c3c;
        --border-subtle: #2a2a2a;
        --text: #e4e4e4;
        --text-muted: #9d9d9d;
        --text-dim: #6e6e6e;
        --accent: #3794ff;
        --btn-white: #ffffff;
        --btn-white-hover: #f0f0f0;
        --radius: 8px;
    }

    .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--bg) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }

    .block-container {
        padding: 1.5rem 2rem 2rem !important;
        max-width: 1320px;
    }

    /* Sidebar — Cursor-like */
    [data-testid="stSidebar"] {
        background-color: #181818 !important;
        border-right: 1px solid var(--border-subtle) !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding: 1rem 1rem 1.5rem !important;
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: var(--text-dim) !important;
        margin: 1.25rem 0 0.5rem !important;
    }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown p {
        color: var(--text-muted) !important;
        font-size: 0.875rem !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: var(--border-subtle) !important;
        margin: 1rem 0 !important;
    }

    /* Typography */
    h1, h2, h3, h4 {
        color: var(--text) !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em;
    }
    p, .stMarkdown { color: var(--text-muted); }
    .stCaption { color: var(--text-dim) !important; }

    /* White primary buttons */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: var(--btn-white) !important;
        color: #1a1a1a !important;
        border: 1px solid #d4d4d4 !important;
        border-radius: var(--radius) !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        padding: 0.5rem 1rem !important;
        transition: background 0.15s ease, box-shadow 0.15s ease !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: var(--btn-white-hover) !important;
        border-color: #c0c0c0 !important;
        color: #000 !important;
    }

    /* Secondary / default buttons */
    .stButton > button[kind="secondary"],
    .stButton > button:not([kind="primary"]) {
        background-color: var(--bg-elevated) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button:not([kind="primary"]):hover {
        background-color: #353535 !important;
        border-color: #4a4a4a !important;
    }

    /* Download buttons — light outline style */
    [data-testid="stDownloadButton"] > button {
        background-color: transparent !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
    }
    [data-testid="stDownloadButton"] > button:hover {
        background-color: var(--bg-elevated) !important;
    }

    /* Inputs */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        background-color: var(--bg-panel) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        color: var(--text) !important;
    }
    [data-testid="stTextInput"] input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 1px var(--accent) !important;
    }

    div[data-testid="stFileUploader"] {
        background: var(--bg-panel) !important;
        border: 1px dashed var(--border) !important;
        border-radius: var(--radius) !important;
    }
    div[data-testid="stFileUploader"]:hover {
        border-color: #5a5a5a !important;
    }

    /* Sliders */
    .stSlider [data-baseweb="slider"] [role="slider"] {
        background: var(--btn-white) !important;
    }
    .stSlider [data-baseweb="slider"] [data-testid="stThumbValue"] {
        color: var(--text) !important;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        color: var(--text) !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--text-dim) !important;
        font-size: 0.75rem !important;
    }

    /* Alerts */
    [data-testid="stAlert"] {
        background-color: var(--bg-panel) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
    }

    /* Expander */
    [data-testid="stExpander"] {
        background: var(--bg-panel) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius) !important;
    }

    /* Custom panels */
    .brand-block {
        padding: 0.25rem 0 1rem;
        border-bottom: 1px solid var(--border-subtle);
        margin-bottom: 0.5rem;
    }
    .brand-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--text);
        margin: 0;
    }
    .brand-sub {
        font-size: 0.75rem;
        color: var(--text-dim);
        margin: 2px 0 0;
    }
    .suggest-card {
        background: var(--bg-panel);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 12px 14px;
        margin-bottom: 12px;
    }
    .suggest-label {
        font-size: 0.65rem;
        font-weight: 600;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: var(--text-dim);
    }
    .suggest-value {
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--text);
        margin-top: 6px;
    }
    .suggest-hint {
        font-size: 0.78rem;
        color: var(--text-muted);
        margin-top: 4px;
        line-height: 1.4;
    }
    .app-hero {
        margin-bottom: 1.25rem;
    }
    .app-title {
        margin: 0;
        font-size: 1.45rem;
        font-weight: 600;
        color: var(--text);
        letter-spacing: -0.02em;
    }
    .app-lead {
        margin: 6px 0 0;
        font-size: 0.875rem;
        color: var(--text-dim);
        line-height: 1.45;
        max-width: 42rem;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--bg-panel) !important;
        border-color: var(--border-subtle) !important;
        border-radius: var(--radius) !important;
    }
    /* YouTube-style clips grid */
    .yt-clips-section {
        animation: ytFadeIn 0.35s ease;
        margin-top: 0.5rem;
    }
    @keyframes ytFadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes ytCardIn {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .yt-col {
        position: relative;
        margin-bottom: 1.5rem;
        animation: ytCardIn 0.4s ease backwards;
    }
    .yt-col [data-testid="stVideo"] {
        border-radius: 12px;
        overflow: hidden;
        background: #0f0f0f;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        will-change: transform;
    }
    .yt-col:hover [data-testid="stVideo"] {
        transform: scale(1.02);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
    }
    .yt-col video {
        border-radius: 12px;
        width: 100%;
        aspect-ratio: 16 / 9;
        object-fit: cover;
        background: #0f0f0f;
    }
    .yt-duration-pill {
        display: block;
        width: fit-content;
        margin-left: auto;
        margin-top: -32px;
        margin-right: 8px;
        margin-bottom: 0;
        position: relative;
        z-index: 2;
        background: rgba(0, 0, 0, 0.82);
        color: #fff;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 3px 6px;
        border-radius: 4px;
        line-height: 1.2;
        pointer-events: none;
        letter-spacing: 0.02em;
    }
    .yt-card-title {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--text);
        margin: 10px 0 4px;
        line-height: 1.35;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .yt-card-meta {
        font-size: 0.78rem;
        color: var(--text-dim);
        margin: 0 0 10px;
        line-height: 1.3;
    }
    .yt-col [data-testid="stDownloadButton"] {
        margin-top: 2px;
    }
    .yt-col [data-testid="stDownloadButton"] > button {
        width: 100% !important;
        background: var(--bg-elevated) !important;
        border-radius: 999px !important;
        font-size: 0.8rem !important;
        padding: 0.4rem 0.75rem !important;
        transition: background 0.15s ease, transform 0.15s ease !important;
    }
    .yt-col [data-testid="stDownloadButton"] > button:hover {
        background: #3a3a3a !important;
        transform: translateY(-1px);
    }
    .yt-toolbar-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: var(--text);
        margin: 0;
        line-height: 1.3;
    }
    .yt-toolbar-sub {
        font-size: 0.8rem;
        color: var(--text-dim);
        margin: 4px 0 0;
    }
    @media (prefers-reduced-motion: reduce) {
        .yt-clips-section, .yt-col {
            animation: none !important;
        }
        .yt-col [data-testid="stVideo"],
        .yt-col [data-testid="stDownloadButton"] > button {
            transition: none !important;
        }
        .yt-col:hover [data-testid="stVideo"] {
            transform: none;
        }
    }
    .log-box {
        background: #1a1a1a;
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius);
        padding: 12px 14px;
        font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
        font-size: 0.78rem;
        color: var(--text-muted);
        max-height: 220px;
        overflow-y: auto;
    }
    .log-line {
        display: flex;
        gap: 8px;
        margin-bottom: 4px;
        line-height: 1.45;
    }
    .log-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        margin-top: 6px;
        flex-shrink: 0;
    }
    .log-line.ok .log-dot { background: #4ec9b0; }
    .log-line.fail .log-dot { background: #f48771; }
    .log-line.info .log-dot { background: #6e6e6e; }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
</style>
"""


def apply_theme() -> None:
    st.markdown(CURSOR_CSS, unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        f"""
        <div class="brand-block">
            <p class="brand-title">{APP_NAME}</p>
            <p class="brand-sub">Clip settings</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, icon_name: str) -> None:
    st.markdown(f"#### {ic(icon_name)} {title}")


def render_header() -> None:
    st.markdown(
        f"""
        <div class="app-hero">
            <h1 class="app-title">{APP_NAME}</h1>
            <p class="app-lead">{APP_LEAD}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _slider_max_clips(duration_sec: float | None, clip_dur: float, overlap: bool) -> int:
    if overlap or not duration_sec:
        return MAX_CLIPS_UI
    return max(1, min(MAX_CLIPS_UI, max_non_overlap_clips(duration_sec, clip_dur)))


def prepare_slider_state(duration_sec: float | None = None) -> None:
    overlap = st.session_state.get("overlap_mode_cb", False)
    clip_dur = float(st.session_state.get("clip_duration_slider", 15))
    clip_dur = max(5.0, min(60.0, clip_dur))
    st.session_state.clip_duration_slider = int(clip_dur)
    max_cap = _slider_max_clips(duration_sec, clip_dur, overlap)
    num = int(st.session_state.get("num_clips_slider", 5))
    st.session_state.num_clips_slider = max(1, min(max_cap, num))


def queue_suggested_settings(duration_sec: float) -> dict:
    s = suggest_clip_settings(duration_sec)
    st.session_state.pending_clip_duration = s["clip_duration"]
    st.session_state.pending_num_clips = s["num_clips"]
    st.session_state.clip_suggest_meta = s
    st.session_state.last_suggested_duration = duration_sec
    return s


def apply_suggested_settings(duration_sec: float) -> dict:
    s = queue_suggested_settings(duration_sec)
    st.session_state.clip_duration_slider = s["clip_duration"]
    st.session_state.num_clips_slider = s["num_clips"]
    st.session_state.pop("pending_clip_duration", None)
    st.session_state.pop("pending_num_clips", None)
    return s


def apply_pending_suggestions(duration_sec: float | None = None) -> bool:
    if "pending_clip_duration" not in st.session_state:
        return False
    st.session_state.clip_duration_slider = st.session_state.pending_clip_duration
    st.session_state.num_clips_slider = st.session_state.pending_num_clips
    del st.session_state.pending_clip_duration
    del st.session_state.pending_num_clips
    return True


def render_auto_suggest_box(duration_sec: float | None) -> None:
    if not duration_sec or duration_sec <= 0:
        return

    s = suggest_clip_settings(duration_sec)
    cur_d = st.session_state.get("clip_duration_slider", 0)
    cur_n = st.session_state.get("num_clips_slider", 0)
    matches = cur_d == s["clip_duration"] and cur_n == s["num_clips"]

    cap = ""
    if s.get("capped_to_ui_max"):
        cap = f"<div class='suggest-hint'>Max {MAX_CLIPS_UI} clips in UI · video fits {s['max_clips']}</div>"

    st.sidebar.markdown(
        f"""
        <div class="suggest-card">
            <div class="suggest-label">Suggested</div>
            <div class="suggest-value">{s['num_clips']} × {s['clip_duration']}s clips</div>
            <div class="suggest-hint">{s['label']}</div>
            {cap}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not matches:
        if st.sidebar.button(
            "Apply",
            key="apply_suggest_btn",
            icon=":material/auto_fix_high:",
            width="stretch",
            type="primary",
        ):
            queue_suggested_settings(duration_sec)
            st.rerun()


def render_sidebar_settings(duration_sec: float | None = None) -> dict:
    render_sidebar_brand()
    st.sidebar.markdown("### Clip settings")

    render_auto_suggest_box(duration_sec)

    overlap_mode = st.sidebar.checkbox("Allow overlap", value=False, key="overlap_mode_cb")

    clip_duration = st.sidebar.slider(
        "Duration (sec)",
        min_value=5,
        max_value=60,
        step=1,
        key="clip_duration_slider",
    )

    fit_max = _slider_max_clips(duration_sec, float(clip_duration), overlap_mode)

    num_clips = st.sidebar.slider(
        "Clip count",
        min_value=1,
        max_value=MAX_CLIPS_UI,
        step=1,
        key="num_clips_slider",
    )

    if duration_sec and not overlap_mode:
        st.sidebar.caption(f"Fits up to {fit_max} clips at {int(clip_duration)}s each.")

    st.sidebar.divider()
    st.sidebar.markdown("### Processing")

    mode_label = st.sidebar.radio("Placement", ["Random", "Sequential"], horizontal=True)
    trim_silence = st.sidebar.checkbox("Trim silence (intro/outro)", value=False)
    max_workers = st.sidebar.select_slider(
        "Parallel clips",
        options=[1, 2],
        value=1,
        help="1 = best for 8GB RAM (i5). 2 = slightly faster, more load.",
    )
    st.sidebar.caption("Fast mode: stream copy, no AI captions.")

    return {
        "clip_duration": float(clip_duration),
        "num_clips": int(num_clips),
        "mode": "random" if mode_label == "Random" else "sequential",
        "overlap_mode": overlap_mode,
        "trim_silence": trim_silence,
        "max_workers": int(max_workers),
    }


def render_sidebar_youtube() -> tuple[str, bool, bool]:
    st.sidebar.divider()
    st.sidebar.markdown("### YouTube")

    url = st.sidebar.text_input(
        "URL",
        placeholder="https://youtu.be/...",
        key="sidebar_yt_url",
        label_visibility="collapsed",
    )

    c1, c2 = st.sidebar.columns(2)
    with c1:
        fetch = st.sidebar.button(
            "Fetch",
            key="yt_fetch",
            icon=":material/link:",
            width="stretch",
            type="primary",
        )
    with c2:
        clear = st.sidebar.button(
            "Clear",
            key="yt_clear",
            icon=":material/close:",
            width="stretch",
        )

    meta = st.session_state.get("video_meta")
    if meta and st.session_state.get("source") == "youtube":
        from youtube_loader import duration_display

        st.sidebar.markdown(
            f'<div class="suggest-card" style="margin-top:10px;">'
            f'<div class="suggest-label">Loaded</div>'
            f'<div class="suggest-value" style="font-size:0.85rem;">'
            f'{meta.title[:48]}{"…" if len(meta.title) > 48 else ""}</div>'
            f'<div class="suggest-hint">{meta.uploader} · {duration_display(meta.duration)}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if meta.thumbnail:
            st.sidebar.image(meta.thumbnail, width="stretch")

    return url.strip(), fetch, clear


def _format_log_line(line: str) -> str:
    escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if line.startswith("[OK]"):
        body = escaped[4:].lstrip()
        return f'<div class="log-line ok"><span class="log-dot"></span><span>{body}</span></div>'
    if line.startswith("[FAIL]"):
        body = escaped[6:].lstrip()
        return f'<div class="log-line fail"><span class="log-dot"></span><span>{body}</span></div>'
    if re.match(r"(?i)^(error|validation failed)", line):
        return f'<div class="log-line fail"><span class="log-dot"></span><span>{escaped}</span></div>'
    return f'<div class="log-line info"><span class="log-dot"></span><span>{escaped}</span></div>'


def render_logs(logs: list[str]) -> None:
    if not logs:
        return
    section_title("Log", "log")
    html = "".join(_format_log_line(ln) for ln in logs[-50:])
    st.markdown(f'<div class="log-box">{html}</div>', unsafe_allow_html=True)


def _format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _clip_index(clip: Path, fallback: int) -> int:
    m = re.match(r"clip_(\d+)", clip.stem, re.I)
    return int(m.group(1)) if m else fallback


def _segment_map(segments: list[ClipSegment] | None) -> dict[int, ClipSegment]:
    return {s.index: s for s in (segments or [])}


def _render_yt_clip_card(
    clip: Path,
    seg_map: dict[int, ClipSegment],
    card_index: int,
) -> None:
    idx = _clip_index(clip, card_index + 1)
    seg = seg_map.get(idx)
    duration_sec = seg.duration if seg else 0.0
    dur_label = _format_duration(duration_sec) if duration_sec > 0 else "—"
    size_mb = clip.stat().st_size / (1024 * 1024)
    title = f"Clip {idx}"

    delay = min(card_index * 0.05, 0.35)
    st.markdown(
        f'<div class="yt-col" style="animation-delay:{delay}s">',
        unsafe_allow_html=True,
    )
    st.video(str(clip))
    st.markdown(f'<p class="yt-duration-pill">{dur_label}</p>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="yt-card-title">{title}</p>'
        f'<p class="yt-card-meta">{size_mb:.1f} MB · {dur_label}</p>',
        unsafe_allow_html=True,
    )
    with open(clip, "rb") as f:
        st.download_button(
            "Download",
            f.read(),
            clip.name,
            "video/mp4",
            icon=":material/download:",
            key=f"yt_dl_{clip.name}_{card_index}",
            use_container_width=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_clip_downloads(
    clips: list[Path],
    zip_path: Path | None,
    segments: list[ClipSegment] | None = None,
) -> None:
    """YouTube-style grid: toolbar + 3-column cards with preview and download."""
    seg_map = _segment_map(segments)
    cols_per_row = 3

    st.markdown('<div class="yt-clips-section">', unsafe_allow_html=True)

    head_left, head_right = st.columns([2.2, 1])
    with head_left:
        st.markdown("#### :material/movie_filter: Clips")
        st.markdown(
            f'<p class="yt-toolbar-sub">{len(clips)} clip(s) ready to export</p>',
            unsafe_allow_html=True,
        )
    with head_right:
        if zip_path and zip_path.exists():
            with open(zip_path, "rb") as f:
                st.download_button(
                    "Download all clips",
                    f.read(),
                    zip_path.name,
                    "application/zip",
                    type="primary",
                    icon=":material/folder_zip:",
                    use_container_width=True,
                    key="yt_dl_all_zip",
                )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    for row_start in range(0, len(clips), cols_per_row):
        row = clips[row_start : row_start + cols_per_row]
        columns = st.columns(cols_per_row, gap="medium")
        for col_idx, clip in enumerate(row):
            with columns[col_idx]:
                _render_yt_clip_card(clip, seg_map, row_start + col_idx)

    st.markdown("</div>", unsafe_allow_html=True)
