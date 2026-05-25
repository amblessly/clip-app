# Auto Clip Studio

Upload long videos **or** paste a YouTube link (sidebar) to generate multiple short clips. Built with **Python 3.10+**, **Streamlit**, **yt-dlp**, and **FFmpeg**.

## Features

- **Large uploads** — up to **10 GB** per file (MP4, MOV, MKV, AVI, WEBM, etc.), no duration cap
- **Upload progress** — chunked save with live progress bar
- **Smart clipping** — configurable duration (5–60s) and clip count (1–50)
- **Placement modes** — random or sequential segments
- **Overlap control** — non-overlapping by default; optional overlap mode
- **Silence trim** — optional intro/outro detection via FFmpeg `silencedetect`
- **Fast clipping** — FFmpeg stream copy when possible (no re-encode); ultrafast fallback
- **Low-spec friendly** — default 1 worker, max 2; YouTube capped at 720p
- **Downloads** — per-clip download + optional preview, or all clips as ZIP
- **Dark UI** — Cursor-style Streamlit interface

## Prerequisites

1. **Python 3.10+**
2. **FFmpeg** (required for clipping)
3. **yt-dlp** (installed via `requirements.txt` for YouTube download)

### Install FFmpeg

**Ubuntu / Debian:**

```bash
sudo apt update && sudo apt install -y ffmpeg
```

**macOS:**

```bash
brew install ffmpeg
```

**Windows:**  
Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add `ffmpeg` to your PATH.

Verify:

```bash
ffmpeg -version
ffprobe -version
```

## Quick Start

### Ubuntu / Debian (recommended)

If `python3 -m venv` fails with **ensurepip is not available**, or `pip install` shows **externally-managed-environment**, use the setup script (installs `python3.12-venv`, `ffmpeg`, etc.):

```bash
cd clip-app
chmod +x setup.sh run.sh
./setup.sh
./run.sh
```

One-time system packages (what `setup.sh` installs via apt):

```bash
sudo apt update
sudo apt install -y ffmpeg python3.12-venv python3-full
```

If you already have a **broken** `.venv` folder (no `pip` inside), remove it first:

```bash
rm -rf .venv
./setup.sh
```

### Manual setup (any OS)

```bash
cd clip-app
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run main.py
```

The app opens in your browser (default: `http://localhost:8501`).

Upload limit is **10 GB per file** (set in `.streamlit/config.toml` as `maxUploadSize = 10240`). Restart the app after changing this value.

## Usage

**Option A — Upload (main screen)**  
1. Upload a video file (drag & drop).  
2. Adjust **Clip Settings** in the sidebar.  
3. Click **Generate Clips**.

**Option B — YouTube (sidebar)**  
1. Paste a YouTube URL in the sidebar and click **Fetch**.  
2. Adjust **Clip Settings**.  
3. Click **Generate Clips** (downloads first if needed).

Download clips individually or as **ZIP** from the main area.

Clips are saved to the `output/` folder as `clip_1.mp4`, `clip_2.mp4`, etc.

## Project Structure

```
clip-app/
├── main.py              # Streamlit entry point
├── video_processor.py   # FFmpeg clipping engine
├── ui.py                # UI components & dark theme
├── requirements.txt
├── README.md
├── uploads/             # Saved uploads (created at runtime)
└── output/              # Generated clips (created at runtime)
```

## Settings Reference

| Setting | Description |
|--------|-------------|
| Clip duration | Length of each clip (5–60 seconds) |
| Number of clips | How many clips to generate (1–50) |
| Random | Picks start times across the usable timeline |
| Sequential | Clips in order from trim start |
| Overlap mode | Allows time ranges to overlap between clips |
| Auto-trim intro/outro | Skips leading/trailing silence |
| Parallel workers | CPU workers for simultaneous FFmpeg jobs |

## Performance Notes

- Large files are processed **on disk** via FFmpeg (not loaded fully into RAM).
- Increase **parallel workers** on multi-core machines for faster batch exports.
- Very long videos may take several minutes; progress is shown in the UI.
- Re-encoding uses `libx264` (fast preset, CRF 23) for reliable, compatible MP4 output.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ensurepip is not available` | `sudo apt install python3.12-venv python3-full` then `rm -rf .venv && ./setup.sh` |
| `externally-managed-environment` | Do **not** use system `pip`; use `./setup.sh` to install into `.venv` |
| `streamlit: command not found` | Run `./run.sh` or `source .venv/bin/activate` first |
| `ffmpeg not found` | `sudo apt install ffmpeg` |
| Not enough video for clips | Reduce clip count/duration or enable overlap mode |
| Corrupted upload | Re-export the source video; check the processing log |
| Slow processing | Lower clip count or reduce parallel workers if disk is slow |

## Deploy (Netlify + Streamlit Cloud)

- **Netlify** — hosts the static landing page in `public/` (see `netlify.toml`).
- **Streamlit Cloud** — runs the app (`main.py`, FFmpeg via `packages.txt`).

Full steps: **[DEPLOY.md](DEPLOY.md)**

## License

MIT — use freely for personal and commercial projects.
