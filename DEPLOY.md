# Deploy Auto Clip Studio

This project has **two parts**:

| Host | What it serves |
|------|----------------|
| **Netlify** | Static landing page (`public/`) |
| **Streamlit Community Cloud** | The real app (upload, FFmpeg, clips) |

Netlify cannot run Streamlit or FFmpeg. The app must live on Streamlit Cloud (free tier).

---

## 1. Deploy the app (Streamlit Cloud)

1. Push this repo to **GitHub** (public or private).
2. Open [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Pick the repo, branch, and main file: **`main.py`**.
4. Streamlit installs `requirements.txt` and system packages from **`packages.txt`** (`ffmpeg`).
5. After deploy, copy your app URL, e.g. `https://auto-clip-studio-xxxx.streamlit.app`.

Optional: in `.streamlit/config.toml`, upload limit is already 10 GB (`maxUploadSize`).

---

## 2. Deploy the landing page (Netlify)

### Option A — Netlify UI

1. [app.netlify.com](https://app.netlify.com) → **Add new site** → **Import from Git**.
2. Select this repository.
3. Build settings (auto-read from `netlify.toml`):
   - **Publish directory:** `public`
   - **Build command:** (leave empty)
4. **Site settings → Environment variables:**
   - `STREAMLIT_APP_URL` = your Streamlit app URL from step 1
5. Deploy.

Edit `public/index.html` or add a small build step if you want the primary button to use the env var automatically (see Option B).

### Option B — Redirect `/app` to Streamlit

Edit `public/_redirects` and uncomment/replace:

```
/app  https://YOUR-APP.streamlit.app  302
```

Redeploy Netlify. Visitors can open `https://your-site.netlify.app/app`.

### Option C — Netlify CLI

```bash
npm install -g netlify-cli
netlify login
netlify init
netlify deploy --prod
```

---

## 3. Connect landing → app

1. Set **`STREAMLIT_APP_URL`** in Netlify to your Streamlit URL.
2. Or link manually in `public/index.html` (`id="open-app"` href).
3. Optional: add your GitHub repo URL to `REPO_URL` / `repo` query param.

---

## Local run (development)

```bash
./setup.sh
./run.sh
```

Open `http://localhost:8501`.

---

## Checklist before go-live

- [ ] `ffmpeg` works on Streamlit Cloud (test **Generate clips** once)
- [ ] GitHub repo does not commit `uploads/`, `output/`, `.venv/` (see `.gitignore`)
- [ ] Netlify publish path is `public`
- [ ] Streamlit app URL set in Netlify env or `_redirects`
