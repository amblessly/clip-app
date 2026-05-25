#!/usr/bin/env bash
# One-time setup for Ubuntu/Debian (fixes missing venv + PEP 668 issues).
set -euo pipefail

cd "$(dirname "$0")"
PY="${PY:-python3}"

echo "==> Auto Clip Studio setup"

py_minor="$("$PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
venv_pkg="python${py_minor}-venv"

venv_usable() {
  [[ -x .venv/bin/pip ]] && .venv/bin/python -c "import pip" &>/dev/null
}

ensurepip_available() {
  "$PY" -c "import ensurepip" &>/dev/null 2>&1
}

# --- System packages (Ubuntu/Debian) ---
need_apt=()

if ! command -v ffmpeg &>/dev/null; then
  need_apt+=(ffmpeg)
fi

if command -v dpkg &>/dev/null; then
  if ! dpkg -s "$venv_pkg" &>/dev/null 2>&1; then
    need_apt+=("$venv_pkg")
  fi
elif ! ensurepip_available; then
  echo "WARN: ensurepip missing; on Debian/Ubuntu install: sudo apt install $venv_pkg"
fi

if ((${#need_apt[@]})); then
  echo "==> Installing system packages (sudo required): ${need_apt[*]}"
  if ! command -v apt-get &>/dev/null; then
    echo "ERROR: apt-get not found. Install manually: ${need_apt[*]}"
    exit 1
  fi
  sudo apt-get update -qq
  sudo apt-get install -y "${need_apt[@]}"
fi

# Still broken after apt? (non-Debian)
if ! ensurepip_available; then
  echo "ERROR: Python ensurepip is not available."
  echo "  Ubuntu/Debian: sudo apt install $venv_pkg python3-full"
  exit 1
fi

# --- Remove broken venv (created without ensurepip / pip) ---
if [[ -d .venv ]] && ! venv_usable; then
  echo "==> Removing incomplete .venv (missing pip)"
  rm -rf .venv
fi

# --- Create virtual environment ---
if [[ ! -d .venv ]]; then
  echo "==> Creating virtual environment"
  if ! "$PY" -m venv .venv; then
    echo "ERROR: Could not create venv. Try:"
    echo "  sudo apt install $venv_pkg python3-full"
    echo "  rm -rf .venv && ./setup.sh"
    exit 1
  fi
fi

if ! venv_usable; then
  echo "ERROR: .venv has no working pip. Run:"
  echo "  sudo apt install $venv_pkg"
  echo "  rm -rf .venv && ./setup.sh"
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

echo "==> Upgrading pip"
python -m pip install --upgrade pip wheel

echo "==> Installing Python dependencies"
pip install -r requirements.txt

mkdir -p uploads output

echo ""
echo "Setup complete. Start the app with:"
echo "  ./run.sh"
echo "or:"
echo "  source .venv/bin/activate && streamlit run main.py"
