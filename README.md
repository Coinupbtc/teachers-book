# Teachers Book

Browser-based teacher gradebook: fast entry, batch scores, voice, rubrics, and analytics.

## At a glance

| | |
|---|---|
| **What it is** | **Teachers Book** — a browser-based teacher gradebook (FastAPI + SQLite) with fast entry, batch/voice, rubrics, and analytics. |
| **What it’s for** | Enter and manage grades quickly on a single machine (or your own deploy) without a heavyweight SIS — local-first by default. |
| **How to use it** | `./setup.sh` → **http://127.0.0.1:8010/**. For any shared/production host, set `SECRET_KEY` + `TEACHERS_BOOK_ENV=production` (see Security below). |

## Try it (pick one)

### One command
```bash
git clone https://github.com/Coinupbtc/teachers-book.git
cd teachers-book && ./setup.sh
# open http://127.0.0.1:8010/
```

### Copy-paste
```bash
git clone https://github.com/Coinupbtc/teachers-book.git && cd teachers-book/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

## Key features

| Feature | |
|---------|--|
| Browser-based | Modern web app |
| Auto-advance / batch / voice grade entry | Yes |
| Rubrics, analytics, at-risk hints | Yes |
| Local-first (SQLite) | Yes |

## Stack

- **Backend:** Python FastAPI + SQLite
- **Frontend:** Vanilla JS + HTMX + Tailwind + Chart.js
- **Auth:** Session-based
- **AI (optional):** local OpenAI-compatible LLM for comments

## Security (required for any non-local deploy)

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | JWT signing — **set a long random value** |
| `TEACHERS_BOOK_ENV` | `production` refuses placeholder secret + open CORS |
| `CORS_ORIGINS` | Comma-separated origins (not `*` in production) |
| `TEACHERS_BOOK_INVITE_CODE` | Optional registration gate |

```bash
export TEACHERS_BOOK_ENV=production
export SECRET_KEY="$(openssl rand -hex 32)"
export CORS_ORIGINS="https://your-domain.example"
```

## License

MIT
