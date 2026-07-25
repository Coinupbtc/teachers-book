#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
set -a
. ./.teachers-book.env
set +a
exec ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010
