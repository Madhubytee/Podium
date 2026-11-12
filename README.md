# Podium

**Practice with Oli, then own the room.**

Podium is an AI speaking coach where you rehearse interviews, pitches, presentations, speeches, and debates with Oli, a wise little owl who talks back, watches your delivery, and tells you exactly what to fix. Feedback comes from transparent IF THEN rules written with domain experts, not from an AI's opinion.

Course project, Group 21: Jenish Patel, Madhurishitha Boddu, Anushka Garge, Monish Beegamudre, Mishka Sonavadekar.

## Modules

| Person | Owns | Files |
| --- | --- | --- |
| Jenish Patel | M1 UI shell and landing page, M2 API | `frontend/` setup, styles, landing, app shell and sidebar; `api/main.py` |
| Madhurishitha Boddu | M3 media preprocessing, recording and session capture | `preprocessing/`; `frontend/src/pages/Session.jsx`, `lib/recorder.js`, `lib/speech.js`; `api/pipeline.py`, `api/video_store.py` |
| Mishka Sonavadekar | M4 feature analyzers, live meters, login and rate limiting | `analyzers/`; `lib/eyeContact.js`, pace chart; `api/auth.py`, `api/ratelimit.py`, login page |
| Monish Beegamudre | M5 knowledge base, M6 inference engine, Oli's live conversation | `knowledge_base/`, `inference/`; `api/oli.py`, `api/live.py` |
| Anushka Garge | M7 feedback and storage, report page, rehearsal setup | `feedback/`; report, rehearsal, and setup pages; `api/documents.py` |

How it fits together: [docs/BACKEND_GUIDE.md](docs/BACKEND_GUIDE.md). How to write rules: [knowledge_base/FACTS.md](knowledge_base/FACTS.md).

```
browser records -> api -> preprocessing -> analyzers -> facts -> inference (rules.json) -> feedback report -> browser
```

## Run it

You need Python 3.12, Node 20+, and (optionally) FFmpeg on your PATH.

```bash
# backend, from the repo root
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # then add your OPENAI_API_KEY for live mode
uvicorn api.main:app --reload --port 8000

# frontend, in a second terminal
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Record mode works with no API key at all. Live mode (Oli talking back) uses OpenAI: ChatGPT plays Oli and Whisper transcribes your answers.

The first analysis downloads the Whisper model (about 480 MB for `small.en`) and the MediaPipe face, pose, and hand models (about 15 MB) into `storage/`.

## Tests

```bash
python -m pytest
```

Covers preprocessing, the inference engine (hand-written facts, no media), scoring and progress, and the full API flow including the live WebSocket.

## Privacy

Video is processed on our own server and never sent to a third party. In live mode, each spoken answer's audio is sent to OpenAI Whisper so Oli can reply. Raw video is deleted after 30 days (`PODIUM_VIDEO_RETENTION_DAYS`), and deleting a rehearsal removes its videos and everything computed from them.
