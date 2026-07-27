#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/backend"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python, then run this file again."
  read -r -p "Press Enter to close..." _
  exit 1
fi
if [ ! -x ".venv/bin/python" ]; then
  echo "Creating local Teachers B00k environment..."
  python3 -m venv .venv
fi

echo "Checking local app requirements..."
./.venv/bin/python -m pip install -q -r requirements-runtime.txt
open http://127.0.0.1:8010
printf '\nTeachers B00k is running locally. Keep this Terminal window open while using it.\n'
printf 'Your data is stored only on this Mac in backend/gradebook.db.\n\n'
exec ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
