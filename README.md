# Teachers B00k — offline gradebook PWA

Open in Chrome, install the app, create an account with your name. Grades stay on that computer.

![Gradebook](docs/screenshots/hero.png)

## At a glance

| | |
|---|---|
| **What it is** | Offline Teachers B00k gradebook (browser PWA). |
| **What it’s for** | Enter and manage class grades on one Windows PC or Chromebook — no cloud login. |
| **How to use it** | Open https://coinupbtc.com/teachers-book/ → Install → Create account with your name. Or `./setup.sh`. |

## Try it

### One click
Open **[https://coinupbtc.com/teachers-book/](https://coinupbtc.com/teachers-book/)** in Chrome → **Install** → **Create account** with your name (e.g. Ms. Rivera).

### One command
```bash
git clone https://github.com/Coinupbtc/teachers-book.git
cd teachers-book && ./setup.sh
# → http://127.0.0.1:8010/
```

Next visit: **Sign in** and tap your name. No email, no password.

### Important

- Grades are stored in **this browser on this device** (IndexedDB). They are not uploaded to a server.
- Clearing site/browser data **deletes** your gradebooks. Sign out does **not**.
- There is no multi-device sync — use the same computer/browser to keep your grades.
- **Backup before updates:** tap **Back up data** (top-right, next to your name / Sign out) — the file lands in Downloads; copy `Teachers-B00k-backup-*.json` to a flash drive. To put grades back, tap **Restore data** → choose that file (this replaces data on that device).

## Features

| Feature | Teachers B00k |
|---------|---------------|
| Offline / installable PWA | ✅ |
| Name-only local accounts | ✅ |
| Full-device backup / restore (JSON → flash drive) | ✅ |
| Classes + weighted categories | ✅ |
| Gradebook grid (autosave, Enter → next row) | ✅ |
| Batch add students | ✅ |
| Assignments CRUD | ✅ |
| Excused / late / comments | ✅ |
| Class insights + CSV export | ✅ |
| Student Rewards | ✅ |
| IEP Goal Tracker + benchmarks | ✅ |
| Light / dark theme | ✅ |

## Optional: FastAPI + SQLite

The public product is the static PWA in `docs/` (`./setup.sh` serves that). The older Python stack still lives under `backend/` if you want a networked API.
