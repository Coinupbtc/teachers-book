# Teachers B00k — The Gradebook That Doesn't Suck

A browser-based teacher gradebook that outperforms Teacher Aide Cloud, iDoceo, Additio, and PowerSchool.

## Competitive Differentiation

| Feature | Teacher Aide | Additio | iDoceo | PowerSchool | **Ours** |
|---------|-------------|---------|--------|------------|----------|
| Browser-based | ❌ | ✅ | ❌ iPad | ✅ Legacy | ✅ Modern |
| Auto-advance grade entry | ❌ | ❌ | ❌ | ❌ | ✅ |
| Batch score entry | ❌ | ❌ | ❌ | ❌ | ✅ |
| Voice grade entry | ❌ | ❌ | ❌ | ❌ | ✅ |
| AI comment generation | ❌ | ❌ | ❌ | ❌ | ✅ |
| Built-in rubric grading | ❌ Separate app | ✅ | ✅ | ❌ | ✅ |
| Assignment analytics/histogram | ❌ | ❌ | ❌ | ❌ | ✅ |
| Continuous scroll entry | ❌ Grid only | ❌ | ❌ | ❌ | ✅ |
| At-risk prediction | ✅ Basic | ❌ | ❌ | ❌ | ✅ AI-powered |
| Grade scanning (photo) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Multi-device sync | ✅ | ✅ | ❌ | ✅ | ✅ |
| Free tier | 30d trial | ❌ | 60d trial | N/A | ✅ Yes |

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
