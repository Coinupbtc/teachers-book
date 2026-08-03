#!/usr/bin/env bash
# One-command local setup + run for Teachers Book
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"

echo "==> Teachers Book setup"
python3 -m venv venv
./venv/bin/pip -q install -U pip
./venv/bin/pip -q install -r requirements.txt

# Local-only defaults (never use placeholder SECRET_KEY in production — see README)
if [[ ! -f .teachers-book.env ]]; then
  cat > .teachers-book.env <<'EOF'
TEACHERS_BOOK_ENV=local
SECRET_KEY=dev-only-change-me
EOF
  echo "Wrote backend/.teachers-book.env (local defaults)"
fi

echo
echo "Starting http://127.0.0.1:8010/"
set -a
# shellcheck disable=SC1091
. ./.teachers-book.env
set +a
exec ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
