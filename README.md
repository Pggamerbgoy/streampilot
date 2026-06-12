# 🚀 StreamPilot AI

A local-first command center for YouTube creators and streamers with analytics, SEO tools, trend discovery, local ML predictions, training workflows, channel safety checks, and OBS livestream control.

## Problem Statement

Creators often juggle YouTube analytics, title optimization, trend research, upload checks, livestream setup, and audience engagement across too many tools. StreamPilot AI brings those workflows into one local dashboard so creators can make faster, safer, data-backed decisions before publishing or going live.

## 🏗️ Architecture

| Component | Language | Framework / Tooling | Port |
| --- | --- | --- | --- |
| Creator Dashboard | HTML / CSS / JavaScript 🟨 | Browser UI served by backend | 8000 |
| Backend API | Python 🐍 | FastAPI | 8000 |
| ML / Training Engine | Python 🧠 | scikit-learn + joblib | Local |
| OBS Control | Python 🎥 | OBS WebSocket client | 4455 |
| YouTube / AI Integrations | Python 🔌 | Google APIs, OpenAI, Groq | External APIs |

## 🚀 Quick Start

### 1. Install Python Dependencies

```powershell
pip install -r requirements.txt
```

### 2. Configure Local Environment

```powershell
Copy-Item .env.example .env.local
```

Add only the keys you need. YouTube, OpenAI, Groq, and OBS features are optional.

### 3. Start StreamPilot AI

```powershell
python backend/server.py
```

Open:

```text
http://127.0.0.1:8000
```

### 4. Run Tests

```powershell
python -m pytest backend
```

## ✨ Features

- 📊 YouTube creator analytics dashboard
- 🔍 SEO topic and title assistance
- 🚀 AI-assisted upload workflow
- 📈 Trend discovery and realtime video prediction
- 🎯 Competitor radar and growth simulator
- 🧠 Local ML training and model promotion workflow
- 🛡️ Channel safety, policy, and content risk checks
- 🎥 OBS livestream scene and recording controls
- 💬 AI comment reply generation
- 📡 Live backend telemetry through REST, SSE, and WebSockets

## 🧠 AI & Creator Intelligence

StreamPilot AI combines local heuristics, optional trained models, and optional cloud AI providers:

| Capability | What It Does |
| --- | --- |
| CTR prediction | Estimates title/content performance with local model fallback |
| Training pipeline | Collects local or YouTube-derived rows and trains candidate models |
| Trend intelligence | Scores trending videos and predicts creator fit |
| SEO generation | Produces tags, hooks, descriptions, and metadata ideas |
| Video analysis | Uses ffmpeg plus optional transcript providers for pre-upload checks |

Generated model files and training snapshots are intentionally local-only by default.

## 🎥 OBS Livestream Control

StreamPilot can connect to OBS through the OBS WebSocket server.

| Setting | Default |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `4455` |
| Password | Optional, from `.env.local` or dashboard input |

Supported workflows include scene switching, source control, recording controls, replay buffer actions, and guided livestream setup.

## 🔐 Environment Variables

Copy `.env.example` to `.env.local` and fill only what you use.

| Variable | Purpose |
| --- | --- |
| `YOUTUBE_API_KEY` | Public YouTube trend and video data |
| `GOOGLE_API_KEY` | Alternative Google API key name |
| `OPENAI_API_KEY` | Optional transcript/AI provider |
| `GROQ_API_KEY` | Optional reply generation and transcript provider |
| `OBS_WS_HOST` | OBS WebSocket host |
| `OBS_WS_PORT` | OBS WebSocket port |
| `OBS_WS_PASSWORD` | OBS WebSocket password |

For OAuth upload and private channel analytics, place your Google OAuth client file at `backend/client_secret.json`. It is ignored by Git and must stay local.

## ✅ Testing

```powershell
python -m pytest backend
```

Some real YouTube tests are skipped unless you explicitly enable them with local environment variables. Local model tests skip automatically when generated model files are not present.

## 🛡️ Security Notes

- Never commit `.env.local`, API keys, OAuth client secrets, access tokens, or pickle token files.
- `backend/client_secret.json` and `backend/token.pickle` are local-only.
- Generated models, training data, trend snapshots, and upload temp files are ignored by Git.
- Keep OBS WebSocket passwords private.
- Review YouTube API quota usage before enabling real upload or trend scans.

## 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.
