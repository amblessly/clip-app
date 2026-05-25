#!/usr/bin/env bash
# Inject Netlify env vars into the landing page (optional).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INDEX="$ROOT/public/index.html"

if [ -n "${STREAMLIT_APP_URL:-}" ]; then
  python3 - "$INDEX" "$STREAMLIT_APP_URL" <<'PY'
import sys
path, url = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
needle = 'window.STREAMLIT_APP_URL = "";'
repl = f'window.STREAMLIT_APP_URL = "{url}";'
if needle not in text:
    sys.exit(0)
open(path, "w", encoding="utf-8").write(text.replace(needle, repl, 1))
PY
fi

if [ -n "${REPO_URL:-}" ]; then
  python3 - "$INDEX" "$REPO_URL" <<'PY'
import sys
path, url = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
needle = 'window.REPO_URL = "";'
repl = f'window.REPO_URL = "{url}";'
if needle in text:
    open(path, "w", encoding="utf-8").write(text.replace(needle, repl, 1))
PY
fi

echo "Netlify static site ready."
