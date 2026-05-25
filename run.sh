#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/streamlit ]]; then
  echo "Streamlit not installed. Run ./setup.sh first."
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate
exec streamlit run main.py "$@"
