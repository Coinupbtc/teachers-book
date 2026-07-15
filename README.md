# Teachers B00k — The Gradebook That Doesn't Suck

A browser-based teacher gradebook that makes entering and managing grades effortless.

## Key Features

| Feature | **Teachers B00k** |
|---------|------------------|
| Browser-based | ✅ Modern web app |
| Auto-advance grade entry | ✅ |
| Batch score entry | ✅ |
| Voice grade entry | ✅ |
| AI comment generation | ✅ |
| Built-in rubric grading | ✅ |
| Assignment analytics/histogram | ✅ |
| Continuous scroll entry | ✅ |
| At-risk prediction | ✅ AI-powered |
| Grade scanning (photo) | ✅ |
| Multi-device sync | ✅ |
| Free tier | ✅ Yes |

## Stack
- **Backend:** Python FastAPI + SQLite (swappable to Postgres)
- **Frontend:** Vanilla JS + HTMX + Tailwind CSS + Chart.js
- **Auth:** Session-based (email + magic link / password)
- **AI:** Ollama local LLM (qwen3.6:35b) for comment gen & analysis
- **Deploy:** Single binary via uvicorn + sqlite — deploy anywhere

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
