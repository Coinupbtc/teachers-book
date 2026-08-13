#!/usr/bin/env bash
# Teachers B00k — serve the public product (offline PWA in docs/).
# The FastAPI + SQLite stack under backend/ is optional / legacy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/docs"
PORT="${PORT:-8010}"
echo "Teachers B00k PWA → http://127.0.0.1:${PORT}/"
echo "Create an account with your name (no email, no password)."
echo "Ctrl+C to stop."
echo "Optional FastAPI stack: see backend/"
exec python3 -m http.server "$PORT" --bind 127.0.0.1
