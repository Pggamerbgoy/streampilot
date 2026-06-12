import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
import re
import shutil
import subprocess
import uuid
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import joblib
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import StreamPilotAgent
from math_engine import StreamPilotMathEngine
from obs_control import ObsManager
from training_pipeline import TrainingPipeline


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.dirname(BACKEND_DIR)
MODEL_PATH = os.path.join(BACKEND_DIR, "models", "base_intelligence_rf.pkl")
UPLOAD_TMP_DIR = os.path.join(BACKEND_DIR, ".tmp_uploads")
TREND_STORE_DIR = os.path.join(BACKEND_DIR, ".trend_data")
TREND_SNAPSHOT_PATH = os.path.join(TREND_STORE_DIR, "trend_snapshots.json")
YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
YOUTUBE_MAX_UPLOAD_BYTES = 256 * 1024 * 1024 * 1024
APP_WARN_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
VIDEO_EXTENSIONS = {
    ".mov",
    ".mpeg",
    ".mpg",
    ".mpeg4",
    ".mp4",
    ".avi",
    ".wmv",
    ".mpegps",
    ".flv",
    ".3gp",
    ".3gpp",
    ".webm",
    ".mkv",
    ".m4v",
}
THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
VIDEO_INSERT_DAILY_LIMIT = 100
DATA_API_DAILY_UNITS = 10000
THUMBNAIL_SET_UNITS = 50
MEDIA_ANALYSIS_SECONDS = 30
PROFANITY_TERMS = {
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "bastard",
    "damn",
}
SENSITIVE_TOPIC_TERMS = {
    "violence": {"kill", "murder", "blood", "weapon", "gun", "shooting", "attack", "violent"},
    "self_harm": {"suicide", "self harm", "self-harm", "harm myself"},
    "drugs": {"cocaine", "heroin", "meth", "drug cartel", "illegal drugs"},
    "sexual": {"porn", "explicit sex", "nude", "onlyfans"},
    "gambling": {"casino", "betting", "gamble", "slots"},
    "scam": {"scam", "fraud", "phishing", "hack accounts"},
}
COPYRIGHT_RISK_TERMS = {
    "full song",
    "movie clip",
    "trailer reaction",
    "copyrighted music",
    "leaked episode",
    "full match",
    "stream replay",
}
SYNTHETIC_MEDIA_TERMS = {"deepfake", "ai voice", "synthetic voice", "generated face", "realistic ai"}

env_file = os.getenv("STREAMPILOT_ENV_FILE")
if env_file:
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv(os.path.join(FRONTEND_DIR, ".env.local"))
    load_dotenv(os.path.join(FRONTEND_DIR, ".env"))
    load_dotenv()


class SEORequest(BaseModel):
    topic: str


class ReplyRequest(BaseModel):
    comment: str


class ObsConnectRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None


class ObsActionRequest(BaseModel):
    action: str
    params: Dict[str, Any] = {}
    confirm: bool = False


class ObsAutopilotRequest(BaseModel):
    topic: Optional[str] = None
    game: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None


class TrainingPromoteRequest(BaseModel):
    candidate_version: Optional[str] = None
    manual_override: bool = True


class _TestDataEngine:
    def __init__(self):
        self.knowledge_base = {
            "user": {
                "channel_name": "StreamPilot Test Channel",
                "subscribers": 45000,
                "total_views": 4200000,
                "video_count": 128,
                "videos": [
                    {"views": 10000 + i * 250 + ((i % 7) * 350), "date": f"2026-05-{(i % 28) + 1:02d}"}
                    for i in range(30)
                ],
            }
        }

    def stream_layer4_telemetry(self):
        tick = 0
        while True:
            tick += 1
            yield {
                "timestamp": f"2026-06-03T00:00:{tick:02d}",
                "concurrent_viewers": 1000 + tick,
                "chat_rate_per_min": 25,
                "sentiment_ema": 0.82,
                "super_chats": 0,
            }


class _TestAgent:
    def __init__(self):
        self.data_engine = _TestDataEngine()
        self.state = {
            "insights": ["Test-mode analytics loaded."],
            "schedule": {"Thursday_14:00": "RTX 5090 Review"},
            "metrics": {"true_growth_rate": 1.2},
        }

    def get_dashboard_payload(self):
        user = self.data_engine.knowledge_base["user"]
        return {
            "channel_name": user["channel_name"],
            "real_subscribers": user["subscribers"],
            "total_views": user["total_views"],
            "video_count": user["video_count"],
            "channel_health": 85,
            "insights": self.state["insights"],
            "optimal_schedule": self.state["schedule"],
        }


def load_ctr_model(path: str = MODEL_PATH, test_mode: bool = False):
    if test_mode:
        return None
    try:
        model = joblib.load(path)
        print("Loaded StreamPilot CTR model.")
        return model
    except Exception as exc:
        print(f"CTR model unavailable, using heuristic fallback: {exc}")
        return None


def create_app(
    test_mode: Optional[bool] = None,
    agent_override: Optional[Any] = None,
    math_engine: Optional[StreamPilotMathEngine] = None,
) -> FastAPI:
    test_mode = (
        os.getenv("STREAMPILOT_TEST_MODE", "").strip().lower() in {"1", "true", "yes"}
        if test_mode is None
        else bool(test_mode)
    )
    ctr_model = load_ctr_model(test_mode=test_mode)
    engine = math_engine or StreamPilotMathEngine(ctr_model=ctr_model)
    agent = agent_override or (_TestAgent() if test_mode else StreamPilotAgent())
    if not test_mode and hasattr(agent, "run_training_pipeline"):
        agent.run_training_pipeline()

    app = FastAPI(title="StreamPilot AI Backend")
    app.state.math_engine = engine
    app.state.agent = agent
    app.state.test_mode = test_mode
    app.state.youtube_connection_factory = None
    app.state.upload_progress = {}
    app.state.quota_usage = {"day": _quota_day_key(), "videos_insert": 0, "data_units": 0}
    app.state.video_analyses = {}
    app.state.uploaded_videos = {}
    app.state.ai_training_state = _train_ai_state(agent, app, engine, test_mode)
    app.state.trending_cache = {}
    app.state.trend_store_path = os.getenv("STREAMPILOT_TREND_STORE_PATH") or TREND_SNAPSHOT_PATH
    app.state.obs_client_factory = None
    app.state.obs_manager = ObsManager()
    app.state.training_pipeline = TrainingPipeline(
        BACKEND_DIR,
        data_dir=os.getenv("STREAMPILOT_TRAINING_DATA_DIR"),
        registry_dir=os.getenv("STREAMPILOT_MODEL_REGISTRY_DIR"),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def read_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/api/dashboard")
    async def get_dashboard_data():
        return agent.get_dashboard_payload()

    @app.get("/api/upload-progress/{upload_id}")
    async def get_upload_progress(upload_id: str):
        if upload_id not in app.state.upload_progress:
            _set_upload_progress(app, upload_id, "waiting", 0, "Waiting for upload to start.")

        async def event_stream():
            last_payload = None
            for _ in range(60 * 60 * 2):
                payload = app.state.upload_progress.get(upload_id) or {
                    "upload_id": upload_id,
                    "stage": "waiting",
                    "progress": 0,
                    "message": "Waiting for upload to start.",
                    "terminal": False,
                }
                serialized = json.dumps(payload)
                if serialized != last_payload:
                    yield f"data: {serialized}\n\n"
                    last_payload = serialized
                if payload.get("terminal"):
                    break
                await asyncio.sleep(0.5)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/simulate")
    async def simulate_growth(
        uploads: float,
        ctr_boost: float,
        promo: float,
        collabs: float,
        seed: Optional[int] = 42,
    ):
        base_subs = agent.data_engine.knowledge_base.get("user", {}).get("subscribers", 45000)
        return engine.simulate_growth(
            base_subscribers=base_subs,
            uploads=uploads,
            ctr_boost=ctr_boost,
            promo=promo,
            collabs=collabs,
            seed=seed,
        )

    @app.post("/api/generate-seo")
    async def generate_seo(req: SEORequest):
        if not req.topic.strip():
            raise HTTPException(status_code=400, detail="topic is required")

        package = _build_ai_upload_package(req.topic.strip(), engine, test_mode)
        titles = package["titles"]
        scored = package["ctr_scores"]
        return {
            "titles": titles,
            "predicted_ctrs": [f"{item['predicted_ctr']:.1f}%" for item in scored],
            "ctr_scores": scored,
            "final_title": package["final_title"],
            "description": package["description"],
            "tags": package["tags"],
            "category_id": package["category_id"],
            "hashtags": package["hashtags"],
            "pinned_comment": package["pinned_comment"],
            "thumbnail_brief": package["thumbnail_brief"],
            "upload_checklist": package["upload_checklist"],
            "best_time": package["best_time"],
            "next_actions": package["next_actions"],
            "package": package,
        }

    @app.post("/api/analyze-video")
    async def analyze_video(
        video: UploadFile = File(...),
        thumbnail: Optional[UploadFile] = File(None),
        topic: str = Form(""),
    ):
        if not video.filename:
            raise HTTPException(status_code=400, detail="video file is required")

        topic_for_analysis = topic.strip() or _topic_from_filename(video.filename)
        temp_dir = _make_upload_temp_dir()
        try:
            video_info = await _save_upload_file(video, temp_dir, allowed_kinds={"video"})
            thumbnail_info = None
            if thumbnail and thumbnail.filename:
                thumbnail_info = await _save_upload_file(thumbnail, temp_dir, allowed_kinds={"image"})
            validation = _build_validation_payload(video_info, thumbnail_info)
            package = _build_ai_upload_package(topic_for_analysis, engine, test_mode)
            analysis = _build_media_analysis(
                video_info=video_info,
                thumbnail_info=thumbnail_info,
                topic=topic_for_analysis,
                package=package,
                app=app,
                engine=engine,
                temp_dir=temp_dir,
                require_media_tools=True,
            )
            analysis["validation"] = validation
            analysis["package"] = package
            app.state.video_analyses[analysis["analysis_id"]] = analysis
            status_code = 424 if analysis.get("setup_required") or analysis.get("provider_error") else 200
            return JSONResponse(status_code=status_code, content=analysis)
        except HTTPException:
            raise
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "analysis_id": uuid.uuid4().hex,
                    "topic": topic_for_analysis,
                    "error": str(exc),
                    "requires_confirmation": True,
                    "risk_report": {
                        "level": "unknown",
                        "publish_allowed": False,
                        "reasons": ["Pre-upload analysis failed before completion."],
                    },
                },
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @app.post("/api/ai-upload")
    async def ai_upload(
        video: UploadFile = File(...),
        thumbnail: Optional[UploadFile] = File(None),
        topic: str = Form(""),
        made_for_kids: bool = Form(False),
        contains_synthetic_media: bool = Form(False),
        upload_id: Optional[str] = Form(None),
        analysis_id: Optional[str] = Form(None),
        confirm_risk: bool = Form(False),
        apply_fix_draft: bool = Form(False),
    ):
        if not video.filename:
            raise HTTPException(status_code=400, detail="video file is required")

        upload_id = _safe_upload_id(upload_id)
        _set_upload_progress(app, upload_id, "validating", 2, "Validating files and preparing upload.")
        topic_for_package = topic.strip() or _topic_from_filename(video.filename)

        temp_dir = _make_upload_temp_dir()
        try:
            video_info = await _save_upload_file(video, temp_dir, allowed_kinds={"video"})
            thumbnail_info = None
            if thumbnail and thumbnail.filename:
                thumbnail_info = await _save_upload_file(thumbnail, temp_dir, allowed_kinds={"image"})
            validation = _build_validation_payload(video_info, thumbnail_info)

            _set_upload_progress(app, upload_id, "analysis", 10, "Running pre-upload intelligence and brand-safety checks.")
            package = _build_ai_upload_package(topic_for_package, engine, test_mode)
            analysis = _resolve_upload_analysis(
                app=app,
                analysis_id=analysis_id,
                video_info=video_info,
                thumbnail_info=thumbnail_info,
                topic=topic_for_package,
                package=package,
                engine=engine,
                temp_dir=temp_dir,
                require_media_tools=False,
            )
            if contains_synthetic_media:
                brand_report = analysis.setdefault("brand_safety_report", {})
                reminders = brand_report.setdefault("synthetic_media_reminders", [])
                if "user_disclosed_realistic_synthetic_media" not in reminders:
                    reminders.append("user_disclosed_realistic_synthetic_media")
                recommendations = brand_report.setdefault("recommendations", [])
                if "Keep YouTube synthetic-media disclosure enabled for this upload." not in recommendations:
                    recommendations.append("Keep YouTube synthetic-media disclosure enabled for this upload.")
                analysis["risk_report"] = _build_analysis_risk_report(
                    analysis.get("hook_report", {}),
                    brand_report,
                )
            if analysis.get("setup_required") or analysis.get("provider_error"):
                _set_upload_progress(app, upload_id, "analysis_required", 100, "Pre-upload analysis setup is required.", terminal=True)
                return JSONResponse(
                    status_code=424,
                    content={
                        "ok": False,
                        "test_mode": test_mode,
                        "upload_id": upload_id,
                        "requires_confirmation": False,
                        "package": package,
                        "analysis": analysis,
                        "risk_report": analysis.get("risk_report"),
                        "fix_draft": analysis.get("fix_draft"),
                        "validation": validation,
                        "quota": _quota_payload(app),
                        "upload": {"status": "analysis_required", "privacy_status": "public"},
                    },
                )

            if apply_fix_draft:
                package = _apply_fix_draft_to_package(package, analysis.get("fix_draft") or {})
                analysis["fix_draft_applied"] = True

            risk_gate = _build_risk_gate(analysis)
            if risk_gate["requires_confirmation"] and not (confirm_risk or apply_fix_draft):
                _set_upload_progress(
                    app,
                    upload_id,
                    "needs_confirmation",
                    100,
                    "AI paused public publish until risk is confirmed or fixed.",
                    terminal=True,
                )
                return {
                    "ok": False,
                    "test_mode": test_mode,
                    "upload_id": upload_id,
                    "requires_confirmation": True,
                    "package": package,
                    "analysis": analysis,
                    "risk_report": risk_gate["risk_report"],
                    "fix_draft": analysis.get("fix_draft"),
                    "validation": validation,
                    "quota": _quota_payload(app),
                    "upload": {
                        "status": "blocked",
                        "privacy_status": "public",
                        "note": "Public upload paused by StreamPilot risk gate.",
                    },
                }

            if confirm_risk and risk_gate["requires_confirmation"]:
                package.setdefault("warnings", []).append("Risk override confirmed by user before public publish.")
                analysis["risk_override_confirmed"] = True

            _set_upload_progress(app, upload_id, "packaging", 18, "Finalizing title, SEO package, and launch checklist.")

            if test_mode:
                _set_upload_progress(app, upload_id, "publishing", 85, "Test mode publish simulation in progress.")
                quota = _record_quota_usage(app, videos_insert=1, data_units=THUMBNAIL_SET_UNITS if thumbnail_info else 0)
                video_id = _fake_video_id()
                upload_payload = {
                    "status": "published",
                    "privacy_status": "public",
                    "video_id": video_id,
                    "watch_url": YOUTUBE_WATCH_URL.format(video_id=video_id),
                    "thumbnail_applied": bool(thumbnail_info),
                    "note": "Test mode: no real YouTube upload was performed.",
                    "risk_override": bool(confirm_risk and risk_gate["requires_confirmation"]),
                    "fix_draft_applied": bool(apply_fix_draft),
                }
                war_room = _record_uploaded_video(app, video_id, package, analysis, upload_payload, test_mode=True)
                _set_upload_progress(app, upload_id, "published", 100, "Test mode public upload complete.", terminal=True)
                return {
                    "ok": True,
                    "test_mode": True,
                    "upload_id": upload_id,
                    "package": package,
                    "analysis": analysis,
                    "risk_report": risk_gate["risk_report"],
                    "validation": validation,
                    "quota": quota,
                    "upload": upload_payload,
                    "war_room": war_room,
                }

            _set_upload_progress(app, upload_id, "uploading", 25, "Uploading video to YouTube using resumable chunks.")
            youtube_factory = getattr(app.state, "youtube_connection_factory", None)
            if youtube_factory is None:
                from youtube_api import YouTubeConnection

                youtube_factory = YouTubeConnection

            def on_youtube_progress(progress: Dict[str, Any]):
                raw = float(progress.get("progress", 0.0))
                scaled = min(92, 25 + int(raw * 0.67))
                total = progress.get("total_bytes") or video_info.get("size")
                uploaded = progress.get("bytes_uploaded")
                message = "Uploading to YouTube"
                if uploaded is not None and total:
                    message = f"Uploading to YouTube: {_format_bytes(int(uploaded))} / {_format_bytes(int(total))}"
                _set_upload_progress(
                    app,
                    upload_id,
                    "uploading",
                    scaled,
                    message,
                    extra={
                        "youtube_progress": raw,
                        "bytes_uploaded": uploaded,
                        "total_bytes": total,
                    },
                )

            yt = youtube_factory()
            upload_response = yt.upload_video(
                file_path=video_info["path"],
                title=package["final_title"],
                description=package["description"],
                tags=package["tags"],
                category_id=package["category_id"],
                privacy_status="public",
                made_for_kids=made_for_kids,
                contains_synthetic_media=contains_synthetic_media,
                progress_callback=on_youtube_progress,
            )
            video_id = upload_response.get("id")
            if not video_id:
                raise RuntimeError("YouTube upload completed without returning a video id")

            thumbnail_applied = False
            thumbnail_error = None
            if thumbnail_info:
                _set_upload_progress(app, upload_id, "thumbnail", 94, "Applying custom thumbnail.")
                try:
                    yt.set_thumbnail(video_id, thumbnail_info["path"])
                    thumbnail_applied = True
                except Exception as exc:
                    thumbnail_error = str(exc)

            quota = _record_quota_usage(app, videos_insert=1, data_units=THUMBNAIL_SET_UNITS if thumbnail_info else 0)
            upload_payload = {
                "status": "published",
                "privacy_status": upload_response.get("status", {}).get("privacyStatus", "public"),
                "video_id": video_id,
                "watch_url": YOUTUBE_WATCH_URL.format(video_id=video_id),
                "thumbnail_applied": thumbnail_applied,
                "risk_override": bool(confirm_risk and risk_gate["requires_confirmation"]),
                "fix_draft_applied": bool(apply_fix_draft),
                "note": (
                    "YouTube may force uploads from unaudited API projects to private. "
                    "Check the returned privacy status in YouTube Studio."
                ),
            }
            if thumbnail_error:
                upload_payload["thumbnail_error"] = thumbnail_error

            war_room = _record_uploaded_video(app, video_id, package, analysis, upload_payload, test_mode=False)
            _set_upload_progress(app, upload_id, "published", 100, "Public upload complete.", terminal=True)
            return {
                "ok": True,
                "test_mode": False,
                "upload_id": upload_id,
                "package": package,
                "analysis": analysis,
                "risk_report": risk_gate["risk_report"],
                "validation": validation,
                "quota": quota,
                "upload": upload_payload,
                "war_room": war_room,
            }
        except HTTPException:
            _set_upload_progress(app, upload_id, "failed", 100, "Upload validation failed.", terminal=True)
            raise
        except Exception as exc:
            package = locals().get("package") or _build_ai_upload_package(topic_for_package, engine, test_mode)
            validation = locals().get("validation") or {"warnings": [], "errors": []}
            _set_upload_progress(app, upload_id, "failed", 100, str(exc), terminal=True)
            return JSONResponse(
                status_code=502,
                content={
                    "ok": False,
                    "test_mode": False,
                    "upload_id": upload_id,
                    "package": package,
                    "validation": validation,
                    "quota": _quota_payload(app),
                    "error": str(exc),
                    "upload": {
                        "status": "failed",
                        "privacy_status": "public",
                    },
                },
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @app.post("/api/predict-ctr")
    async def predict_ctr(req: SEORequest):
        title = req.topic.strip()
        if not title:
            raise HTTPException(status_code=400, detail="topic is required")
        fallback = engine.predict_ctr(title)
        return _training_pipeline_for_app(app).predict_ctr(title, fallback)

    @app.post("/api/generate-reply")
    async def generate_reply(req: ReplyRequest):
        if test_mode:
            return {"reply": "Thanks for the thoughtful comment. I appreciate you watching!"}
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return {"error": "GROQ_API_KEY not found"}

        import groq

        client = groq.Groq(api_key=api_key)
        prompt = f"""
        You are the owner of a gaming/tech YouTube channel. A viewer just left this comment: "{req.comment}"
        Write a short, engaging, authentic reply (1-3 sentences max). Use an emoji if appropriate.
        Do NOT include any quotation marks around the reply. Just return the raw text.
        """
        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
            )
            return {"reply": response.choices[0].message.content.strip()}
        except Exception as exc:
            return {"error": str(exc)}

    @app.get("/api/competitors")
    async def get_competitors():
        if test_mode:
            return {
                "competitors": [
                    {"name": "TestTech", "subs": 100000, "views": 5000000},
                    {"name": "BuildLab", "subs": 80000, "views": 3100000},
                ]
            }
        try:
            from youtube_api import YouTubeConnection

            yt = YouTubeConnection()
            if not yt.youtube:
                yt.authenticate()
            request = yt.youtube.search().list(
                part="snippet",
                q="gaming channel",
                type="channel",
                maxResults=5,
                order="viewCount",
            )
            response = request.execute()

            competitors = []
            for item in response.get("items", []):
                channel_id = item["snippet"]["channelId"]
                stats_req = yt.youtube.channels().list(part="statistics,snippet", id=channel_id)
                stats_res = stats_req.execute()
                if stats_res["items"]:
                    channel = stats_res["items"][0]
                    competitors.append(
                        {
                            "name": channel["snippet"]["title"][:15],
                            "subs": int(channel["statistics"].get("subscriberCount", 0)),
                            "views": int(channel["statistics"].get("viewCount", 0)),
                        }
                    )
            return {"competitors": competitors}
        except Exception as exc:
            return {"error": str(exc), "competitors": []}

    @app.get("/api/war-room/{video_id}")
    async def get_war_room(video_id: str):
        clean_video_id = re.sub(r"[^A-Za-z0-9_-]", "", video_id or "")[:32]
        if not clean_video_id:
            raise HTTPException(status_code=400, detail="video_id is required")
        uploaded = app.state.uploaded_videos.get(clean_video_id, {})
        return _build_war_room_payload(clean_video_id, app, uploaded=uploaded, test_mode=test_mode)

    @app.post("/api/train-ai")
    async def train_ai(source: str = "local"):
        if _is_real_source(source):
            state = _train_ai_state_real(app, engine)
        else:
            state = _train_ai_state(agent, app, engine, test_mode)
        training_status = _training_pipeline_for_app(app).status()
        state["training_registry"] = {
            "champion": training_status.get("champion"),
            "badges": training_status.get("badges", []),
            "dataset": training_status.get("dataset", {}),
        }
        state["champion_model_active"] = bool(training_status.get("champion"))
        app.state.ai_training_state = state
        return state

    @app.post("/api/training/collect")
    async def training_collect(
        source: str = "local",
        scope: str = "channel",
        region_code: str = "US",
        category_id: Optional[str] = None,
    ):
        pipeline = _training_pipeline_for_app(app)
        clean_scope = (scope or "channel").strip().lower()
        if clean_scope not in {"channel", "platform", "mixed"}:
            clean_scope = "channel"
        clean_region = re.sub(r"[^A-Za-z]", "", region_code or "US").upper()[:2] or "US"
        clean_category = re.sub(r"[^0-9]", "", category_id or "") or None
        if _is_real_source(source):
            rows_result = _training_rows_for_collect(
                app,
                engine,
                source="real_youtube",
                scope=clean_scope,
                test_mode=test_mode,
                region_code=clean_region,
                category_id=clean_category,
            )
            if not rows_result.get("ok"):
                return rows_result
            result = pipeline.collect_rows(rows_result.get("rows", []), source="real_youtube")
            return {**result, "scope": clean_scope, "fetched_counts": rows_result.get("fetched_counts", {})}
        rows_result = _training_rows_for_collect(
            app,
            engine,
            source="local",
            scope=clean_scope,
            test_mode=test_mode,
            region_code=clean_region,
            category_id=clean_category,
        )
        result = pipeline.collect_rows(rows_result.get("rows", []), source="local")
        return {**result, "scope": clean_scope, "fetched_counts": rows_result.get("fetched_counts", {})}

    @app.post("/api/training/retrain")
    async def training_retrain():
        return _training_pipeline_for_app(app).start_retrain()

    @app.get("/api/training/jobs/{job_id}")
    async def training_job(job_id: str):
        clean_job_id = re.sub(r"[^A-Za-z0-9_-]", "", job_id or "")
        return _training_pipeline_for_app(app).get_job(clean_job_id)

    @app.get("/api/training/status")
    async def training_status():
        return _training_pipeline_for_app(app).status()

    @app.get("/api/training/evaluation")
    async def training_evaluation():
        return _training_pipeline_for_app(app).evaluation()

    @app.post("/api/training/promote")
    async def training_promote(request: TrainingPromoteRequest):
        return _training_pipeline_for_app(app).promote(request.candidate_version, manual_override=request.manual_override)

    @app.get("/api/realtime-predict/{video_id}")
    async def realtime_predict(video_id: str, source: str = "local", refresh: bool = False):
        clean_video_id = re.sub(r"[^A-Za-z0-9_-]", "", video_id or "")[:32]
        if not clean_video_id:
            raise HTTPException(status_code=400, detail="video_id is required")
        if _is_real_source(source):
            return _build_realtime_prediction_real(clean_video_id, app, refresh=refresh)
        return _build_realtime_prediction(clean_video_id, app, test_mode=test_mode)

    @app.get("/api/trending-videos")
    async def trending_videos(
        region_code: str = "US",
        category_id: Optional[str] = None,
        max_results: int = 12,
        source: str = "local",
    ):
        clean_region = re.sub(r"[^A-Za-z]", "", region_code or "US").upper()[:2] or "US"
        clean_category = re.sub(r"[^0-9]", "", category_id or "") or None
        limit = max(1, min(int(max_results or 12), 25))
        return _build_trending_scan(
            app,
            engine,
            clean_region,
            clean_category,
            limit,
            test_mode=test_mode,
            real_source=_is_real_source(source),
        )

    @app.post("/api/obs/connect")
    async def obs_connect(request: ObsConnectRequest):
        return await _obs_manager_for_app(app).connect(_model_payload(request))

    @app.post("/api/obs/disconnect")
    async def obs_disconnect():
        return await _obs_manager_for_app(app).disconnect()

    @app.get("/api/obs/status")
    async def obs_status():
        return await _obs_manager_for_app(app).status()

    @app.get("/api/obs/scenes")
    async def obs_scenes():
        return await _obs_manager_for_app(app).scenes()

    @app.get("/api/obs/events")
    async def obs_events():
        manager = _obs_manager_for_app(app)

        async def event_stream():
            async for event in manager.event_stream():
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.post("/api/obs/action")
    async def obs_action(request: ObsActionRequest):
        payload = _model_payload(request)
        return await _obs_manager_for_app(app).action(payload)

    @app.post("/api/obs/autopilot-setup")
    async def obs_autopilot_setup(request: ObsAutopilotRequest):
        payload = _model_payload(request)
        manager = _obs_manager_for_app(app)
        if not manager._connected() and any(payload.get(key) for key in ("host", "port", "password")):
            connect_result = await manager.connect(payload)
            if not connect_result.get("ok"):
                return {**connect_result, "planned_actions": []}
        return await manager.autopilot_setup(payload)

    @app.websocket("/ws/telemetry")
    async def websocket_telemetry(websocket: WebSocket):
        await websocket.accept()
        stream = agent.data_engine.stream_layer4_telemetry()
        try:
            while True:
                await websocket.send_json(next(stream))
                await asyncio.sleep(2)
        except WebSocketDisconnect:
            return

    app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="static")
    return app


def _model_payload(model: BaseModel) -> Dict[str, Any]:
    try:
        return model.model_dump(exclude_none=True)
    except AttributeError:
        return model.dict(exclude_none=True)


def _obs_manager_for_app(app: FastAPI) -> ObsManager:
    factory = getattr(app.state, "obs_client_factory", None)
    manager = getattr(app.state, "obs_manager", None)
    if manager is None or getattr(manager, "_factory_ref", None) is not factory:
        manager = ObsManager(client_factory=factory)
        manager._factory_ref = factory
        app.state.obs_manager = manager
    return manager


def _training_pipeline_for_app(app: FastAPI) -> TrainingPipeline:
    pipeline = getattr(app.state, "training_pipeline", None)
    if pipeline is None:
        pipeline = TrainingPipeline(BACKEND_DIR)
        app.state.training_pipeline = pipeline
    return pipeline


def _training_rows_for_collect(
    app: FastAPI,
    engine: StreamPilotMathEngine,
    source: str,
    scope: str,
    test_mode: bool,
    region_code: str,
    category_id: Optional[str],
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    counts = {"channel_videos": 0, "platform_trends": 0}
    if scope in {"channel", "mixed"}:
        if source == "real_youtube":
            channel_result = _training_rows_real(app)
            if not channel_result.get("ok"):
                return {**channel_result, "scope": scope}
            channel_rows = channel_result.get("rows", [])
        else:
            channel_rows = _training_rows_local(app, test_mode=test_mode)
        rows.extend(channel_rows)
        counts["channel_videos"] = len(channel_rows)

    if scope in {"platform", "mixed"}:
        platform_result = _training_rows_platform(
            app,
            engine,
            real_source=source == "real_youtube",
            test_mode=test_mode,
            region_code=region_code,
            category_id=category_id,
        )
        if source == "real_youtube" and not platform_result.get("ok"):
            return {**platform_result, "scope": scope}
        platform_rows = platform_result.get("rows", [])
        rows.extend(platform_rows)
        counts["platform_trends"] = len(platform_rows)

    return {
        "ok": True,
        "source": source,
        "scope": scope,
        "fake_fallback_used": False if source == "real_youtube" else None,
        "rows": rows,
        "fetched_counts": {**counts, "total": len(rows)},
    }


def _training_rows_local(app: FastAPI, test_mode: bool) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    user = getattr(getattr(app.state.agent, "data_engine", None), "knowledge_base", {}).get("user", {})
    now = datetime.now(timezone.utc)
    for index, item in enumerate(user.get("videos") or []):
        if not isinstance(item, dict):
            continue
        published = now - timedelta(days=max(2, len(user.get("videos") or []) - index))
        views = int(item.get("views") or 0)
        rows.append(
            {
                "video_id": f"local-{index:04d}",
                "title": item.get("title") or f"Local Training Video {index + 1}",
                "published_at": item.get("published_at") or published.isoformat(),
                "category_id": item.get("category_id") or "28",
                "views": views,
                "likes": int(max(views * 0.05, 1)),
                "comments": int(max(views * 0.005, 0)),
                "analytics": {
                    "rows": [
                        {"day": (published + timedelta(days=offset)).date().isoformat(), "views": int(views * ratio)}
                        for offset, ratio in enumerate((0.32, 0.18, 0.12, 0.1, 0.09, 0.07, 0.05))
                    ],
                    "totals": {
                        "views": views,
                        "impressions": max(int(views / 0.055), 100),
                        "ctr": 4.0 + (index % 6) * 0.45,
                        "average_view_duration_seconds": 46 + (index % 9) * 4,
                        "watch_time_minutes": int(views * 0.85),
                    },
                    "analytics_available": True,
                },
                "trend": {"opportunity_score": 50 + (index % 8) * 5, "topic_cluster": "tech and gear"},
            }
        )
    for video_id, record in (getattr(app.state, "uploaded_videos", {}) or {}).items():
        package = record.get("package") or {}
        analysis = record.get("analysis") or {}
        war = record.get("war_room") or {}
        metrics = war.get("metrics") or {}
        rows.append(
            {
                "video_id": video_id,
                "title": package.get("final_title") or package.get("topic") or "Published upload",
                "description": package.get("description") or "",
                "tags": package.get("tags") or [],
                "published_at": record.get("published_at") or now.isoformat(),
                "category_id": package.get("category_id") or "28",
                "views": int(metrics.get("views") or 0),
                "likes": int(metrics.get("likes") or 0),
                "comments": int(metrics.get("comments") or 0),
                "analytics": {
                    "rows": [{"day": now.date().isoformat(), "views": int(metrics.get("views") or 0)}],
                    "totals": {
                        "views": int(metrics.get("views") or 0),
                        "impressions": metrics.get("impressions"),
                        "ctr": metrics.get("ctr"),
                        "average_view_duration_seconds": metrics.get("average_view_duration_seconds"),
                        "watch_time_minutes": metrics.get("watch_time_minutes"),
                    },
                    "analytics_available": True,
                },
                "package": package,
                "analysis": analysis,
            }
        )
    if not rows and test_mode:
        rows.append({"video_id": "local-empty", "title": "Local baseline", "published_at": (now - timedelta(days=3)).isoformat(), "views": 1000})
    return rows


def _training_rows_real(app: FastAPI) -> Dict[str, Any]:
    try:
        yt = _youtube_factory_for_app(app)()
        videos = yt.get_recent_channel_videos(max_results=50)
        rows = []
        for video in videos:
            video_id = video.get("id")
            analytics = {"rows": [], "totals": {}, "analytics_available": False}
            try:
                if hasattr(yt, "get_video_analytics_window") and video_id:
                    analytics = yt.get_video_analytics_window(video_id, days=7, strict=False)
            except Exception as exc:
                analytics = {"rows": [], "totals": {}, "analytics_available": False, "error": str(exc)}
            rows.append(
                {
                    "video_id": video_id,
                    "title": video.get("title", ""),
                    "description": video.get("description", ""),
                    "published_at": video.get("published_at"),
                    "category_id": video.get("category_id"),
                    "views": int(video.get("view_count") or 0),
                    "likes": int(video.get("like_count") or 0),
                    "comments": int(video.get("comment_count") or 0),
                    "analytics": analytics,
                }
            )
        return {"ok": True, "source": "real_youtube", "fake_fallback_used": False, "rows": rows, "fetched_counts": {"videos": len(rows)}}
    except Exception as exc:
        return {**_real_youtube_error("training_collect", exc), "rows": [], "fetched_counts": {"videos": 0}}


def _training_rows_platform(
    app: FastAPI,
    engine: StreamPilotMathEngine,
    real_source: bool,
    test_mode: bool,
    region_code: str,
    category_id: Optional[str],
) -> Dict[str, Any]:
    scan = _build_trending_scan(
        app,
        engine,
        region_code=region_code,
        category_id=category_id,
        max_results=25,
        test_mode=test_mode,
        real_source=real_source,
    )
    if real_source and not scan.get("ok"):
        return {
            **scan,
            "operation": "training_collect_platform",
            "rows": [],
            "fetched_counts": {"platform_trends": 0},
        }
    captured_at = datetime.now(timezone.utc).isoformat()
    rows = [_training_row_from_trend(video, captured_at) for video in scan.get("videos", [])]
    return {
        "ok": True,
        "source": "real_youtube" if real_source else "local",
        "rows": rows,
        "fetched_counts": {"platform_trends": len(rows)},
        "trend_summary": scan.get("trend_summary", {}),
    }


def _training_row_from_trend(video: Dict[str, Any], captured_at: str) -> Dict[str, Any]:
    views = int(video.get("view_count") or 0)
    likes = int(video.get("like_count") or 0)
    comments = int(video.get("comment_count") or 0)
    age_hours = max(float(video.get("age_hours") or _hours_since(video.get("published_at"))), 0.5)
    first_24h_estimate = int(min(views, float(video.get("views_per_hour") or views / age_hours) * min(age_hours, 24.0)))
    return {
        "video_id": str(video.get("id") or uuid.uuid4().hex),
        "snapshot_kind": "platform_trend",
        "captured_at": captured_at,
        "title": video.get("title", ""),
        "description": video.get("description", ""),
        "published_at": video.get("published_at"),
        "category_id": video.get("category_id") or "28",
        "views": views,
        "likes": likes,
        "comments": comments,
        "analytics": {
            "rows": [{"day": datetime.now(timezone.utc).date().isoformat(), "views": first_24h_estimate}],
            "totals": {
                "views": views,
                "watch_time_minutes": None,
                "average_view_duration_seconds": None,
            },
            "analytics_available": False,
            "label_note": "Public platform trend snapshot; private CTR/retention analytics unavailable.",
        },
        "trend": {
            "topic_cluster": video.get("topic_cluster"),
            "opportunity_score": video.get("creator_opportunity_score") or video.get("opportunity_score"),
            "trend_prediction": video.get("trend_prediction") or {},
        },
        "feature_overrides": {
            "source_rank": video.get("source_rank"),
            "region_code": video.get("region_code"),
            "platform_views_per_hour": video.get("views_per_hour"),
            "engagement_rate": video.get("engagement_rate"),
        },
    }


def _strip_json_markdown(content: str) -> str:
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def _set_upload_progress(
    app: FastAPI,
    upload_id: str,
    stage: str,
    progress: int,
    message: str,
    terminal: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "upload_id": upload_id,
        "stage": stage,
        "progress": max(0, min(100, int(progress))),
        "message": message,
        "terminal": terminal,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    app.state.upload_progress[upload_id] = payload
    return payload


def _safe_upload_id(upload_id: Optional[str]) -> str:
    candidate = (upload_id or "").strip()
    if candidate and re.fullmatch(r"[A-Za-z0-9_-]{6,80}", candidate):
        return candidate
    return uuid.uuid4().hex


def _fake_video_id() -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    return "".join(alphabet[int(uuid.uuid4().hex[i : i + 2], 16) % len(alphabet)] for i in range(0, 22, 2))


def _quota_day_key() -> str:
    try:
        now = datetime.now(ZoneInfo("America/Los_Angeles"))
    except ZoneInfoNotFoundError:
        now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d")


def _ensure_quota_day(app: FastAPI) -> Dict[str, Any]:
    day = _quota_day_key()
    usage = getattr(app.state, "quota_usage", None) or {}
    if usage.get("day") != day:
        usage = {"day": day, "videos_insert": 0, "data_units": 0}
        app.state.quota_usage = usage
    return usage


def _record_quota_usage(app: FastAPI, videos_insert: int = 0, data_units: int = 0) -> Dict[str, Any]:
    usage = _ensure_quota_day(app)
    usage["videos_insert"] = int(usage.get("videos_insert", 0)) + int(videos_insert)
    usage["data_units"] = int(usage.get("data_units", 0)) + int(data_units)
    return _quota_payload(app)


def _quota_payload(app: FastAPI) -> Dict[str, Any]:
    usage = _ensure_quota_day(app)
    videos_used = int(usage.get("videos_insert", 0))
    data_units = int(usage.get("data_units", 0))
    remaining = max(VIDEO_INSERT_DAILY_LIMIT - videos_used, 0)
    warnings = []
    if remaining <= 5:
        warnings.append("YouTube videos.insert daily upload bucket is nearly exhausted.")
    if data_units >= DATA_API_DAILY_UNITS * 0.8:
        warnings.append("Estimated Data API unit usage is high for this local session.")
    return {
        "day": usage["day"],
        "reset_timezone": "America/Los_Angeles",
        "videos_insert": {
            "daily_limit": VIDEO_INSERT_DAILY_LIMIT,
            "used_estimate": videos_used,
            "remaining_estimate": remaining,
            "used_by_this_upload": 1,
        },
        "data_api_units": {
            "daily_limit": DATA_API_DAILY_UNITS,
            "used_estimate": data_units,
            "thumbnail_set_units": THUMBNAIL_SET_UNITS,
        },
        "warnings": warnings,
        "note": "Local estimate only. Confirm exact quota in Google Cloud Console.",
    }


def _build_validation_payload(video_info: Dict[str, Any], thumbnail_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    warnings = list(video_info.get("warnings", []))
    if thumbnail_info:
        warnings.extend(thumbnail_info.get("warnings", []))
    return {
        "errors": [],
        "warnings": warnings,
        "video": _public_file_info(video_info),
        "thumbnail": _public_file_info(thumbnail_info) if thumbnail_info else None,
    }


def _public_file_info(file_info: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "filename": file_info.get("filename"),
        "extension": file_info.get("extension"),
        "content_type": file_info.get("content_type"),
        "size": file_info.get("size"),
        "size_label": _format_bytes(int(file_info.get("size") or 0)),
    }


def _validate_upload_metadata(filename: str, content_type: str, allowed_kinds: set[str]) -> tuple[str, List[str]]:
    ext = os.path.splitext(filename or "")[1].lower()
    warnings: List[str] = []
    if "video" in allowed_kinds:
        if ext not in VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported video format '{ext or 'unknown'}'. Use MP4, MOV, AVI, WMV, FLV, WebM, MKV, or another YouTube-supported video file.",
            )
    elif "image" in allowed_kinds:
        if ext not in THUMBNAIL_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported thumbnail format '{ext or 'unknown'}'. Use JPG, PNG, GIF, BMP, or WebP.",
            )

    kind = content_type.split("/", 1)[0] if "/" in content_type else ""
    if content_type and kind and kind not in allowed_kinds and content_type != "application/octet-stream":
        raise HTTPException(status_code=400, detail=f"{filename} is not a valid {', '.join(allowed_kinds)} file")
    if not content_type:
        warnings.append("Browser did not provide a MIME type; validation used the file extension.")
    return ext, warnings


def _format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def _build_ai_upload_package(topic: str, engine: StreamPilotMathEngine, test_mode: bool = False) -> Dict[str, Any]:
    clean_topic = topic.strip() or "Untitled Video"
    raw: Dict[str, Any] = {}
    source = "heuristic"
    warnings: List[str] = []

    if test_mode:
        raw = _fallback_upload_package(clean_topic)
        source = "test"
    else:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raw = _fallback_upload_package(clean_topic)
            warnings.append("GROQ_API_KEY not found; used local metadata fallback.")
        else:
            try:
                import groq

                client = groq.Groq(api_key=api_key)
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": _ai_upload_prompt(clean_topic)}],
                    model="llama-3.3-70b-versatile",
                    temperature=0.82,
                )
                content = _strip_json_markdown(response.choices[0].message.content.strip())
                parsed = json.loads(content)
                raw = parsed if isinstance(parsed, dict) else _fallback_upload_package(clean_topic)
                source = "groq:llama-3.3-70b-versatile"
            except Exception as exc:
                raw = _fallback_upload_package(clean_topic)
                warnings.append(f"AI metadata fallback used: {exc}")

    return _normalize_upload_package(clean_topic, raw, engine, source, warnings)


def _fallback_upload_package(topic: str) -> Dict[str, Any]:
    clean_topic = topic.strip() or "Untitled Video"
    compact_hashtag = "#" + re.sub(r"[^A-Za-z0-9]", "", clean_topic.title())[:40]
    return {
        "titles": [
            f"I Tested {clean_topic} So You Don't Have To",
            f"Do NOT Upload Your {clean_topic} Video Before Watching This",
            f"{clean_topic}: The Full Breakdown You Need",
        ],
        "description": (
            f"In this video, we break down {clean_topic} with practical context, key takeaways, "
            "and the details viewers need before they decide what to do next.\n\n"
            "Watch till the end for the final verdict, useful next steps, and the biggest mistake to avoid."
        ),
        "tags": [clean_topic.lower(), "review", "guide", "youtube", "2026", "tips", "breakdown"],
        "category_id": "28",
        "hashtags": [compact_hashtag, "#Review", "#Tech"],
        "pinned_comment": f"What should I test next after {clean_topic}? Drop your best idea below.",
        "thumbnail_brief": f"Use a high-contrast thumbnail showing the main {clean_topic} result and one bold promise.",
        "upload_checklist": [
            "Public visibility selected",
            "Title chosen by CTR score",
            "Description includes primary keyword naturally",
            "Tags and hashtags attached",
            "Pinned comment drafted",
            "First 24h analytics watchlist ready",
        ],
        "best_time": "Thursday 8:00 PM IST",
        "next_actions": [
            "Monitor CTR and retention after the first hour",
            "Reply to early comments with AI draft replies",
            "Clip 2-3 Shorts from the strongest moments",
        ],
    }


def _normalize_upload_package(
    topic: str,
    raw: Dict[str, Any],
    engine: StreamPilotMathEngine,
    source: str,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    fallback = _fallback_upload_package(topic)
    titles = _clean_list(raw.get("titles") or fallback["titles"], fallback["titles"])
    titles = [_limit_text(title, 100) for title in titles][:3]
    scored_pairs = [(title, engine.predict_ctr(title)) for title in titles]
    scored_pairs.sort(key=lambda item: item[1].get("predicted_ctr", 0), reverse=True)
    ranked_titles = [title for title, _ in scored_pairs]
    ranked_scores = [score for _, score in scored_pairs]

    final_title = _limit_text(str(raw.get("final_title") or ranked_titles[0]), 100)
    if final_title not in ranked_titles:
        final_title = ranked_titles[0]

    tags = _clean_list(raw.get("tags") or fallback["tags"], fallback["tags"])
    tags = _dedupe([_limit_text(tag.strip().lower(), 40) for tag in tags if tag.strip()])[:15]
    hashtags = _clean_list(raw.get("hashtags") or fallback["hashtags"], fallback["hashtags"])
    hashtags = _dedupe([tag if tag.startswith("#") else f"#{tag}" for tag in hashtags])[:5]
    checklist = _clean_list(raw.get("upload_checklist") or fallback["upload_checklist"], fallback["upload_checklist"])
    next_actions = _clean_list(raw.get("next_actions") or fallback["next_actions"], fallback["next_actions"])

    return {
        "topic": topic,
        "source": source,
        "warnings": warnings or [],
        "titles": ranked_titles,
        "final_title": final_title,
        "description": _limit_text(str(raw.get("description") or fallback["description"]), 5000),
        "tags": tags,
        "category_id": str(raw.get("category_id") or fallback["category_id"] or "28"),
        "hashtags": hashtags,
        "pinned_comment": _limit_text(str(raw.get("pinned_comment") or fallback["pinned_comment"]), 500),
        "thumbnail_brief": _limit_text(str(raw.get("thumbnail_brief") or fallback["thumbnail_brief"]), 500),
        "upload_checklist": checklist[:10],
        "best_time": str(raw.get("best_time") or fallback["best_time"]),
        "next_actions": next_actions[:8],
        "ctr_scores": ranked_scores,
        "predicted_ctrs": [f"{item['predicted_ctr']:.1f}%" for item in ranked_scores],
        "publish_mode": "public",
    }


def _clean_list(value: Any, fallback: List[str]) -> List[str]:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or fallback
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()] or fallback
    return fallback


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    results = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
    return results


def _limit_text(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3].rstrip() + "..."


def _topic_from_filename(filename: str) -> str:
    base = os.path.splitext(os.path.basename(filename or ""))[0]
    base = re.sub(r"[_\-]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base.title() or "Untitled Video"


def _make_upload_temp_dir() -> str:
    os.makedirs(UPLOAD_TMP_DIR, exist_ok=True)
    return os.path.join(UPLOAD_TMP_DIR, uuid.uuid4().hex)


async def _save_upload_file(upload: UploadFile, temp_dir: str, allowed_kinds: set[str]) -> Dict[str, Any]:
    os.makedirs(temp_dir, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(upload.filename or "upload.bin"))
    path = os.path.join(temp_dir, safe_name or "upload.bin")
    content_type = (upload.content_type or "").lower()
    ext, warnings = _validate_upload_metadata(upload.filename or safe_name, content_type, allowed_kinds)

    total = 0
    with open(path, "wb") as out_file:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if "video" in allowed_kinds and total > YOUTUBE_MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=400, detail="Video is larger than YouTube's 256 GB upload limit.")
            out_file.write(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail=f"{upload.filename} is empty")
    if "video" in allowed_kinds and total > APP_WARN_UPLOAD_BYTES:
        warnings.append(
            "This video is very large. Upload can take a long time; keep this app open until the progress reaches 100%."
        )
    return {
        "path": path,
        "filename": upload.filename or safe_name,
        "extension": ext,
        "content_type": content_type or "unknown",
        "size": total,
        "warnings": warnings,
    }


def _resolve_upload_analysis(
    app: FastAPI,
    analysis_id: Optional[str],
    video_info: Dict[str, Any],
    thumbnail_info: Optional[Dict[str, Any]],
    topic: str,
    package: Dict[str, Any],
    engine: StreamPilotMathEngine,
    temp_dir: str,
    require_media_tools: bool,
) -> Dict[str, Any]:
    existing = None
    clean_id = (analysis_id or "").strip()
    if clean_id:
        existing = getattr(app.state, "video_analyses", {}).get(clean_id)
    if existing:
        return existing

    analysis = _build_media_analysis(
        video_info=video_info,
        thumbnail_info=thumbnail_info,
        topic=topic,
        package=package,
        app=app,
        engine=engine,
        temp_dir=temp_dir,
        require_media_tools=require_media_tools,
    )
    app.state.video_analyses[analysis["analysis_id"]] = analysis
    return analysis


def _build_media_analysis(
    video_info: Dict[str, Any],
    thumbnail_info: Optional[Dict[str, Any]],
    topic: str,
    package: Dict[str, Any],
    app: FastAPI,
    engine: StreamPilotMathEngine,
    temp_dir: str,
    require_media_tools: bool,
) -> Dict[str, Any]:
    analysis_id = uuid.uuid4().hex
    test_mode = bool(getattr(app.state, "test_mode", False))
    clean_topic = topic.strip() or _topic_from_filename(video_info.get("filename", ""))
    media_metadata = _lightweight_media_metadata(video_info, thumbnail_info)

    if require_media_tools and not test_mode:
        missing_tools = _missing_media_tools()
        if missing_tools:
            return _setup_required_analysis(analysis_id, clean_topic, missing_tools, media_metadata, package)
        media_metadata = _probe_media_metadata(video_info["path"], media_metadata)

    if test_mode:
        transcript_payload = _test_transcript_payload(clean_topic, video_info.get("filename", ""))
    elif require_media_tools:
        audio_path = _extract_first_30s_audio(video_info["path"], temp_dir)
        transcript_payload = _transcribe_audio_segment(audio_path)
    else:
        transcript_payload = _topic_only_transcript_payload(clean_topic, video_info.get("filename", ""))

    transcript_text = transcript_payload.get("text", "")
    hook_report = _build_hook_report(transcript_text, clean_topic, package, media_metadata)
    brand_safety_report = _build_brand_safety_report(transcript_text, clean_topic)
    revenue_estimate = _build_revenue_estimate(clean_topic, package.get("category_id"), brand_safety_report)
    fix_draft = _build_fix_draft(clean_topic, package, hook_report, brand_safety_report)
    shorts_candidates = _build_shorts_candidates(transcript_text, clean_topic, hook_report)
    risk_report = _build_analysis_risk_report(hook_report, brand_safety_report)
    requires_confirmation = bool(risk_report["requires_confirmation"])

    return {
        "ok": not transcript_payload.get("provider_error"),
        "analysis_id": analysis_id,
        "topic": clean_topic,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider_error": transcript_payload.get("provider_error"),
        "requires_confirmation": requires_confirmation,
        "transcript_summary": {
            "provider": transcript_payload.get("provider", "topic-only"),
            "summary": _summarize_transcript(transcript_text, clean_topic),
            "text_excerpt": _limit_text(transcript_text, 420),
            "segments": transcript_payload.get("segments", []),
            "warnings": transcript_payload.get("warnings", []),
            "provider_error": transcript_payload.get("provider_error"),
        },
        "hook_report": hook_report,
        "brand_safety_report": brand_safety_report,
        "revenue_estimate": revenue_estimate,
        "fix_draft": fix_draft,
        "risk_report": risk_report,
        "media": media_metadata,
        "shorts_candidates": shorts_candidates,
        "auto_shorts_foundation": {
            "segments_stored": bool(shorts_candidates),
            "next_step": "Queue trim/crop/upload automation in V1.2.",
        },
    }


def _setup_required_analysis(
    analysis_id: str,
    topic: str,
    missing_tools: List[str],
    media_metadata: Dict[str, Any],
    package: Dict[str, Any],
) -> Dict[str, Any]:
    fix_draft = _build_fix_draft(
        topic,
        package,
        {"weak_hook": False, "suggested_recut_start_seconds": 0},
        {"risk_level": "unknown", "risk_reasons": []},
    )
    return {
        "ok": False,
        "analysis_id": analysis_id,
        "topic": topic,
        "setup_required": True,
        "missing_tools": missing_tools,
        "message": "Install ffmpeg and ffprobe, then retry pre-upload intelligence.",
        "requires_confirmation": False,
        "transcript_summary": {
            "provider": "none",
            "summary": "Media analysis could not run because required binaries are missing.",
            "warnings": ["ffmpeg/ffprobe setup required for real video analysis."],
        },
        "hook_report": {
            "hook_strength": None,
            "drop_off_risk": "unknown",
            "weak_hook": False,
            "suggested_recut_start_seconds": 0,
            "title_package_fit": None,
            "signals": [],
        },
        "brand_safety_report": {
            "risk_level": "unknown",
            "risk_score": None,
            "risk_reasons": ["Setup required before brand-safety scan can read the media."],
        },
        "revenue_estimate": _build_revenue_estimate(topic, package.get("category_id"), {"risk_level": "unknown"}),
        "fix_draft": fix_draft,
        "risk_report": {
            "level": "setup_required",
            "requires_confirmation": False,
            "publish_allowed": False,
            "reasons": ["Pre-upload intelligence setup is incomplete."],
        },
        "media": media_metadata,
    }


def _missing_media_tools() -> List[str]:
    return [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]


def _lightweight_media_metadata(
    video_info: Dict[str, Any],
    thumbnail_info: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "filename": video_info.get("filename"),
        "size": video_info.get("size"),
        "size_label": _format_bytes(int(video_info.get("size") or 0)),
        "extension": video_info.get("extension"),
        "duration_seconds": None,
        "has_audio": None,
        "has_video": True,
        "thumbnail_provided": bool(thumbnail_info),
        "analysis_window_seconds": MEDIA_ANALYSIS_SECONDS,
    }


def _probe_media_metadata(path: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(fallback)
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        parsed = json.loads(result.stdout or "{}")
        streams = parsed.get("streams", [])
        duration = parsed.get("format", {}).get("duration")
        metadata.update(
            {
                "duration_seconds": round(float(duration), 2) if duration else None,
                "has_audio": any(stream.get("codec_type") == "audio" for stream in streams),
                "has_video": any(stream.get("codec_type") == "video" for stream in streams),
                "video_codec": next((stream.get("codec_name") for stream in streams if stream.get("codec_type") == "video"), None),
                "audio_codec": next((stream.get("codec_name") for stream in streams if stream.get("codec_type") == "audio"), None),
            }
        )
    except Exception as exc:
        metadata.setdefault("warnings", []).append(f"ffprobe metadata read failed: {exc}")
    return metadata


def _extract_first_30s_audio(video_path: str, temp_dir: str) -> str:
    audio_path = os.path.join(temp_dir, "first_30s.wav")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-t",
            str(MEDIA_ANALYSIS_SECONDS),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            audio_path,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return audio_path


def _transcribe_audio_segment(audio_path: str) -> Dict[str, Any]:
    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    warnings: List[str] = []

    if openai_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=openai_key)
            with open(audio_path, "rb") as audio_file:
                result = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
            return _transcript_payload_from_text(getattr(result, "text", str(result)), "openai:whisper-1", warnings)
        except Exception as exc:
            warnings.append(f"OpenAI transcript failed, trying Groq fallback: {exc}")

    if groq_key:
        try:
            import groq

            client = groq.Groq(api_key=groq_key)
            with open(audio_path, "rb") as audio_file:
                result = client.audio.transcriptions.create(
                    file=(os.path.basename(audio_path), audio_file.read()),
                    model="whisper-large-v3",
                    response_format="json",
                )
            text = result.get("text") if isinstance(result, dict) else getattr(result, "text", str(result))
            return _transcript_payload_from_text(text or "", "groq:whisper-large-v3", warnings)
        except Exception as exc:
            warnings.append(f"Groq transcript failed: {exc}")

    return {
        "provider": "none",
        "text": "",
        "segments": [],
        "warnings": warnings + ["No transcript provider configured. Add OPENAI_API_KEY or GROQ_API_KEY."],
        "provider_error": "No transcript provider configured. Add OPENAI_API_KEY or GROQ_API_KEY.",
    }


def _transcript_payload_from_text(text: str, provider: str, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    clean_text = " ".join(str(text or "").split())
    return {
        "provider": provider,
        "text": clean_text,
        "segments": _segment_transcript(clean_text),
        "warnings": warnings or [],
    }


def _test_transcript_payload(topic: str, filename: str) -> Dict[str, Any]:
    lower = f"{topic} {filename}".lower()
    if "weak hook" in lower:
        text = (
            "Welcome back guys, before we start please like and subscribe. "
            "Today we are going to slowly talk about the background and then maybe get to the point later."
        )
    elif any(term in lower for terms in SENSITIVE_TOPIC_TERMS.values() for term in terms) or any(
        term in lower for term in PROFANITY_TERMS
    ):
        text = (
            f"This video covers {topic}. It includes sensitive claims, strong language, and examples that need careful framing "
            "before public publishing."
        )
    else:
        text = (
            f"In the first ten seconds I show the final result for {topic}, the biggest surprise, and why it matters. "
            "Then I compare the practical tradeoffs so viewers know exactly what to do next."
        )
    return _transcript_payload_from_text(text, "test-mode")


def _topic_only_transcript_payload(topic: str, filename: str) -> Dict[str, Any]:
    text = (
        f"Topic-only preflight for {topic or filename}. "
        "A full first-30-second transcript is available from /api/analyze-video when ffmpeg and a transcript provider are configured."
    )
    return _transcript_payload_from_text(text, "topic-only", ["Used topic-only risk scan during upload."])


def _segment_transcript(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    words = text.split()
    segments = []
    for idx in range(0, min(len(words), 90), 18):
        start = int((idx / 90) * MEDIA_ANALYSIS_SECONDS)
        end = min(MEDIA_ANALYSIS_SECONDS, start + 6)
        segments.append({"start": start, "end": end, "text": " ".join(words[idx : idx + 18])})
    return segments


def _summarize_transcript(text: str, topic: str) -> str:
    if not text:
        return f"No transcript text available yet for {topic}."
    first_sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    return _limit_text(first_sentence or f"First 30 seconds discuss {topic}.", 220)


def _build_hook_report(
    transcript_text: str,
    topic: str,
    package: Dict[str, Any],
    media_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    text = f"{transcript_text} {topic}".strip()
    lower = text.lower()
    first_words = lower.split()[:80]
    score = 52
    signals: List[str] = []

    if any(word in lower for word in ("result", "secret", "mistake", "tested", "before", "truth", "surprise")):
        score += 18
        signals.append("Clear curiosity or outcome promise in the opening.")
    if re.search(r"\b\d+\b", lower):
        score += 8
        signals.append("Specific number detected in hook.")
    if "?" in transcript_text:
        score += 6
        signals.append("Question-style opener can invite retention.")
    if len(first_words) >= 22:
        score += 5
        signals.append("Opening has enough substance for analysis.")

    weak_patterns = (
        "welcome back",
        "before we start",
        "like and subscribe",
        "today we are going to",
        "today we're going to",
        "in this video we will",
        "weak hook",
    )
    weak_hits = [pattern for pattern in weak_patterns if pattern in lower]
    if weak_hits:
        score -= 30
        signals.append("Slow intro pattern detected: " + ", ".join(weak_hits[:3]))
    if len(first_words) < 12:
        score -= 12
        signals.append("Opening text is too thin to prove a strong hook.")

    title_text = package.get("final_title") or topic
    title_fit = _token_overlap_score(title_text, text)
    if title_fit < 35:
        score -= 8
        signals.append("Opening does not strongly match the title/package promise.")
    else:
        signals.append("Opening aligns with the title/package promise.")

    duration = media_metadata.get("duration_seconds")
    if duration and duration > 0 and duration < 45:
        score += 4
        signals.append("Short total runtime lowers first-30s drop-off risk.")

    score = max(0, min(100, int(score)))
    weak_hook = score < 50
    if score >= 70:
        drop_off_risk = "low"
        suggested_recut = 0
        verdict = "strong"
    elif score >= 50:
        drop_off_risk = "medium"
        suggested_recut = 5 if weak_hits else 0
        verdict = "usable"
    else:
        drop_off_risk = "high"
        suggested_recut = 12 if weak_hits else 6
        verdict = "weak"

    return {
        "hook_strength": score,
        "verdict": verdict,
        "drop_off_risk": drop_off_risk,
        "weak_hook": weak_hook,
        "suggested_recut_start_seconds": suggested_recut,
        "title_package_fit": title_fit,
        "signals": signals,
    }


def _token_overlap_score(left: str, right: str) -> int:
    left_tokens = {token for token in re.findall(r"[a-z0-9]+", left.lower()) if len(token) > 2}
    right_tokens = {token for token in re.findall(r"[a-z0-9]+", right.lower()) if len(token) > 2}
    if not left_tokens or not right_tokens:
        return 0
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens), 1)
    return max(0, min(100, int(overlap * 100)))


def _build_brand_safety_report(transcript_text: str, topic: str) -> Dict[str, Any]:
    text = f"{topic} {transcript_text}".lower()
    words = re.findall(r"[a-z']+", text)
    word_count = max(len(words), 1)
    profanity_hits = [term for term in PROFANITY_TERMS if re.search(rf"\b{re.escape(term)}\b", text)]
    profanity_density = round((len(profanity_hits) / word_count) * 100, 2)

    sensitive_topics = []
    for category, terms in SENSITIVE_TOPIC_TERMS.items():
        matches = sorted(term for term in terms if term in text)
        if matches:
            sensitive_topics.append({"category": category, "matches": matches[:4]})

    copyright_signals = sorted(term for term in COPYRIGHT_RISK_TERMS if term in text)
    synthetic_reminders = sorted(term for term in SYNTHETIC_MEDIA_TERMS if term in text)

    risk_score = 8
    risk_reasons: List[str] = []
    if profanity_hits:
        risk_score += min(30, 10 * len(profanity_hits))
        risk_reasons.append("Profanity detected in first-30s/topic context.")
    for item in sensitive_topics:
        bump = 32 if item["category"] in {"self_harm", "sexual", "scam"} else 18
        risk_score += bump
        risk_reasons.append(f"Sensitive topic signal: {item['category']}.")
    if copyright_signals:
        risk_score += min(25, 8 * len(copyright_signals))
        risk_reasons.append("Possible copyright-risk wording detected.")
    if synthetic_reminders:
        risk_score += 10
        risk_reasons.append("Synthetic-media disclosure reminder detected.")

    risk_score = max(0, min(100, int(risk_score)))
    if any(item["category"] in {"self_harm", "sexual", "scam"} for item in sensitive_topics) or risk_score >= 65:
        risk_level = "high"
    elif risk_score >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"

    recommendations = []
    if profanity_hits:
        recommendations.append("Bleep or mute strong language in the opening where possible.")
    if sensitive_topics:
        recommendations.append("Use neutral wording and avoid sensational claims in title/description.")
    if copyright_signals:
        recommendations.append("Verify rights for music/clips and avoid implying full copyrighted material.")
    if synthetic_reminders:
        recommendations.append("Keep realistic synthetic media disclosure enabled before upload.")
    if not recommendations:
        recommendations.append("No major advertiser-safety issue detected in available context.")

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "profanity_density": profanity_density,
        "profanity_hits": len(profanity_hits),
        "sensitive_topics": sensitive_topics,
        "copyright_risk_signals": copyright_signals,
        "synthetic_media_reminders": synthetic_reminders,
        "risk_reasons": risk_reasons,
        "recommendations": recommendations,
    }


def _build_revenue_estimate(topic: str, category_id: Optional[str], brand_safety_report: Dict[str, Any]) -> Dict[str, Any]:
    lower = topic.lower()
    cpm_low, cpm_high, band = 3.0, 8.0, "general creator"
    if any(term in lower for term in ("gpu", "laptop", "software", "ai", "pc", "camera", "tech")):
        cpm_low, cpm_high, band = 6.0, 16.0, "tech/high-intent"
    if any(term in lower for term in ("finance", "invest", "credit", "business", "saas")):
        cpm_low, cpm_high, band = 12.0, 28.0, "premium finance/business"
    if any(term in lower for term in ("gaming", "gameplay", "minecraft", "gta", "fortnite")):
        cpm_low, cpm_high, band = 2.0, 7.0, "gaming/entertainment"
    if brand_safety_report.get("risk_level") == "medium":
        cpm_low *= 0.75
        cpm_high *= 0.8
    elif brand_safety_report.get("risk_level") == "high":
        cpm_low *= 0.35
        cpm_high *= 0.45

    midpoint = (cpm_low + cpm_high) / 2
    projected_views_24h = 2500 if band.startswith("tech") else 1600
    projected_revenue = (projected_views_24h / 1000.0) * midpoint
    return {
        "topic_band": band,
        "category_id": str(category_id or "28"),
        "estimated_cpm_usd": round(midpoint, 2),
        "cpm_range_usd": [round(cpm_low, 2), round(cpm_high, 2)],
        "first_24h_projection_usd": round(projected_revenue, 2),
        "assumed_24h_views": projected_views_24h,
        "notes": [
            "Estimate is pre-upload and heuristic until real RPM data is available.",
            f"Brand-safety risk level: {brand_safety_report.get('risk_level', 'unknown')}.",
        ],
    }


def _build_fix_draft(
    topic: str,
    package: Dict[str, Any],
    hook_report: Dict[str, Any],
    brand_safety_report: Dict[str, Any],
) -> Dict[str, Any]:
    safe_topic = _sanitize_risky_topic(topic)
    recut_start = int(hook_report.get("suggested_recut_start_seconds") or 0)
    bleep_suggestions = []
    if brand_safety_report.get("profanity_hits", 0):
        bleep_suggestions.append("Review 0:00-0:30 and bleep/mute strong language before public release.")
    for item in brand_safety_report.get("sensitive_topics", []) or []:
        bleep_suggestions.append(f"Reframe {item['category']} wording with neutral, factual language.")
    if brand_safety_report.get("copyright_risk_signals"):
        bleep_suggestions.append("Replace or remove any unlicensed music/clip segments before upload.")

    return {
        "safer_title": _limit_text(f"{safe_topic}: The Practical Breakdown", 100),
        "safer_description": _limit_text(
            (
                f"This video breaks down {safe_topic} with practical context, clear caveats, and viewer-first takeaways.\n\n"
                "All claims are framed carefully. If the topic includes sensitive or synthetic material, disclosure and context stay visible."
            ),
            5000,
        ),
        "pinned_comment": _limit_text(
            f"Quick note: I kept this {safe_topic} breakdown focused on context and practical takeaways. What should I clarify next?",
            500,
        ),
        "thumbnail_brief": _limit_text(
            f"Use a clean thumbnail for {safe_topic}: one clear result, no shocking or graphic framing, high contrast text.",
            500,
        ),
        "bleep_mute_suggestions": bleep_suggestions or ["No bleep/mute edit required from available context."],
        "recut_timestamps": [
            {
                "start": recut_start,
                "end": MEDIA_ANALYSIS_SECONDS,
                "reason": "Start closer to the result/promise to improve first-30s retention.",
            }
        ]
        if recut_start
        else [],
        "disclosure_note": "Keep synthetic-media disclosure enabled if the video includes realistic AI-generated visuals or audio.",
        "applied_changes": ["safer title", "safer description", "pinned comment", "thumbnail brief"],
    }


def _sanitize_risky_topic(topic: str) -> str:
    cleaned = topic
    risky_terms = set(PROFANITY_TERMS) | {term for terms in SENSITIVE_TOPIC_TERMS.values() for term in terms}
    for term in sorted(risky_terms, key=len, reverse=True):
        cleaned = re.sub(re.escape(term), "sensitive topic", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "This Video"


def _build_shorts_candidates(transcript_text: str, topic: str, hook_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not transcript_text:
        return []
    recut = int(hook_report.get("suggested_recut_start_seconds") or 0)
    return [
        {
            "start": recut,
            "end": min(MEDIA_ANALYSIS_SECONDS, recut + 18),
            "idea": f"Shorts hook: strongest reveal from {topic}",
            "caption": _limit_text(_summarize_transcript(transcript_text, topic), 90),
        }
    ]


def _build_analysis_risk_report(
    hook_report: Dict[str, Any],
    brand_safety_report: Dict[str, Any],
) -> Dict[str, Any]:
    reasons = list(brand_safety_report.get("risk_reasons") or [])
    if hook_report.get("weak_hook"):
        reasons.append("Weak first-30s hook may cause early drop-off.")
    level = brand_safety_report.get("risk_level", "unknown")
    requires_confirmation = bool(level == "high" or hook_report.get("weak_hook"))
    return {
        "level": level,
        "requires_confirmation": requires_confirmation,
        "publish_allowed": not requires_confirmation,
        "reasons": reasons or ["No major pre-upload risk detected."],
        "warnings": brand_safety_report.get("recommendations", []),
    }


def _build_risk_gate(analysis: Dict[str, Any]) -> Dict[str, Any]:
    risk_report = analysis.get("risk_report") or {}
    requires_confirmation = bool(analysis.get("requires_confirmation") or risk_report.get("requires_confirmation"))
    return {
        "requires_confirmation": requires_confirmation,
        "risk_report": {
            **risk_report,
            "requires_confirmation": requires_confirmation,
            "publish_allowed": not requires_confirmation,
        },
    }


def _apply_fix_draft_to_package(package: Dict[str, Any], fix_draft: Dict[str, Any]) -> Dict[str, Any]:
    fixed = dict(package)
    if fix_draft.get("safer_title"):
        title = _limit_text(str(fix_draft["safer_title"]), 100)
        fixed["final_title"] = title
        fixed["titles"] = _dedupe([title] + list(fixed.get("titles") or []))[:3]
    if fix_draft.get("safer_description"):
        fixed["description"] = _limit_text(str(fix_draft["safer_description"]), 5000)
    if fix_draft.get("pinned_comment"):
        fixed["pinned_comment"] = _limit_text(str(fix_draft["pinned_comment"]), 500)
    if fix_draft.get("thumbnail_brief"):
        fixed["thumbnail_brief"] = _limit_text(str(fix_draft["thumbnail_brief"]), 500)
    checklist = list(fixed.get("upload_checklist") or [])
    checklist.extend(["Risk fix draft applied", "Sensitive wording reviewed before public publish"])
    fixed["upload_checklist"] = _dedupe(checklist)[:10]
    fixed.setdefault("warnings", []).append("Auto Fix Draft applied before public upload.")
    return fixed


def _record_uploaded_video(
    app: FastAPI,
    video_id: str,
    package: Dict[str, Any],
    analysis: Dict[str, Any],
    upload_payload: Dict[str, Any],
    test_mode: bool,
) -> Dict[str, Any]:
    record = {
        "video_id": video_id,
        "package": package,
        "analysis": analysis,
        "upload": upload_payload,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    app.state.uploaded_videos[video_id] = record
    return _build_war_room_payload(video_id, app, uploaded=record, test_mode=test_mode)


def _is_real_source(source: Optional[str]) -> bool:
    return str(source or "").strip().lower() in {"real", "real_youtube", "youtube"}


def _youtube_factory_for_app(app: FastAPI):
    youtube_factory = getattr(app.state, "youtube_connection_factory", None)
    if youtube_factory is None:
        from youtube_api import YouTubeConnection

        youtube_factory = YouTubeConnection
    return youtube_factory


def _real_youtube_error(operation: str, exc: Exception) -> Dict[str, Any]:
    message = str(exc)
    lower = message.lower()
    if any(token in lower for token in ("invalid_grant", "credentials", "oauth", "unauthorized", "access_denied")):
        category = "auth_error"
    elif any(token in lower for token in ("quota", "daily limit", "rate limit", "rate_limit")):
        category = "quota_error"
    elif any(token in lower for token in ("notfound", "not found", "videonotfound", "404")):
        category = "not_found"
    elif any(token in lower for token in ("commentsdisabled", "comments disabled")):
        category = "comments_disabled"
    elif any(token in lower for token in ("analytics", "insufficient", "forbidden", "403")):
        category = "analytics_or_permission_error"
    else:
        category = "api_error"
    payload = {
        "ok": False,
        "source": "real_youtube",
        "mode": "real",
        "operation": operation,
        "error_category": category,
        "error": message,
        "fake_fallback_used": False,
    }
    if category == "auth_error":
        payload["auth_action"] = (
            "Set YOUTUBE_API_KEY or GOOGLE_API_KEY in .env.local for public trend data, "
            "or refresh the OAuth token by deleting backend/token.pickle and reconnecting YouTube."
        )
    return payload


def _build_war_room_payload(
    video_id: str,
    app: FastAPI,
    uploaded: Optional[Dict[str, Any]] = None,
    test_mode: bool = False,
) -> Dict[str, Any]:
    if test_mode:
        return _fake_war_room_payload(video_id, uploaded or {})

    try:
        youtube_factory = getattr(app.state, "youtube_connection_factory", None)
        if youtube_factory is None:
            from youtube_api import YouTubeConnection

            youtube_factory = YouTubeConnection
        yt = youtube_factory()
        analytics = yt.get_video_analytics_24h(video_id) if hasattr(yt, "get_video_analytics_24h") else {}
        comments = yt.get_recent_comments(video_id) if hasattr(yt, "get_recent_comments") else []
        summary = _summarize_real_war_room_metrics(analytics)
        alerts = _build_war_room_alerts(summary, comments, uploaded or {})
        reply_drafts = _draft_reply_batch(comments, uploaded or {})
        return {
            "ok": True,
            "video_id": video_id,
            "mode": "real",
            "metrics": summary,
            "timeline": analytics.get("timeline", []),
            "alert_cards": alerts,
            "first_comments": comments[:8],
            "ai_reply_drafts": reply_drafts,
            "recommended_intervention": _recommended_intervention(alerts),
            "next_actions": _war_room_next_actions(alerts),
        }
    except Exception as exc:
        fallback = _fake_war_room_payload(video_id, uploaded or {})
        fallback["ok"] = False
        fallback["mode"] = "fallback"
        fallback["error"] = str(exc)
        fallback["recommended_intervention"] = "Connect YouTube Analytics permissions, then refresh this War Room."
        return fallback


def _fake_war_room_payload(video_id: str, uploaded: Dict[str, Any]) -> Dict[str, Any]:
    package = uploaded.get("package") or {}
    topic = package.get("topic") or "latest upload"
    timeline = []
    views = 0
    for hour in range(1, 25):
        views += 38 + hour * 9
        timeline.append(
            {
                "hour": hour,
                "views": views,
                "impressions": 950 + hour * 280,
                "ctr": round(2.6 + min(hour, 8) * 0.05, 2),
                "average_view_duration_seconds": 38 + hour // 3,
                "watch_time_minutes": round(views * 0.72, 1),
                "comments": max(0, hour // 3 - 1),
            }
        )
    summary = {
        "elapsed_hours": 6,
        "views": timeline[5]["views"],
        "impressions": timeline[5]["impressions"],
        "ctr": timeline[5]["ctr"],
        "average_view_duration_seconds": timeline[5]["average_view_duration_seconds"],
        "watch_time_minutes": timeline[5]["watch_time_minutes"],
        "comments": timeline[5]["comments"],
    }
    comments = [
        {"id": "c1", "author": "EarlyViewer", "text": "The intro was useful, but the title made me expect benchmarks faster."},
        {"id": "c2", "author": "BuildBuddy", "text": "Can you make a Shorts version with just the final result?"},
        {"id": "c3", "author": "TechFan", "text": "Thumbnail idea is good, maybe make the result bigger."},
    ]
    alerts = _build_war_room_alerts(summary, comments, uploaded)
    return {
        "ok": True,
        "video_id": video_id,
        "mode": "test",
        "metrics": summary,
        "timeline": timeline,
        "alert_cards": alerts,
        "first_comments": comments,
        "ai_reply_drafts": _draft_reply_batch(comments, uploaded),
        "recommended_intervention": _recommended_intervention(alerts),
        "next_actions": _war_room_next_actions(alerts)
        + [
            f"Create 2 Shorts ideas from the strongest {topic} moment.",
            "Refresh this War Room after the first hour and again at 24h.",
        ],
    }


def _summarize_real_war_room_metrics(analytics: Dict[str, Any]) -> Dict[str, Any]:
    rows = analytics.get("rows") or []
    totals = analytics.get("totals") or {}
    if totals:
        return totals
    if not rows:
        return {
            "elapsed_hours": None,
            "views": 0,
            "impressions": None,
            "ctr": None,
            "average_view_duration_seconds": 0,
            "watch_time_minutes": 0,
            "comments": 0,
        }
    latest = rows[-1]
    return {
        "elapsed_hours": None,
        "views": latest.get("views", 0),
        "impressions": latest.get("impressions"),
        "ctr": latest.get("ctr"),
        "average_view_duration_seconds": latest.get("average_view_duration_seconds", 0),
        "watch_time_minutes": latest.get("watch_time_minutes", 0),
        "comments": latest.get("comments", 0),
    }


def _build_war_room_alerts(
    metrics: Dict[str, Any],
    comments: List[Dict[str, Any]],
    uploaded: Dict[str, Any],
) -> List[Dict[str, Any]]:
    alerts = []
    ctr = metrics.get("ctr")
    avd = metrics.get("average_view_duration_seconds") or 0
    if ctr is not None and float(ctr) < 3.5:
        alerts.append(
            {
                "type": "low_ctr",
                "severity": "high",
                "title": "Low CTR",
                "message": "Thumbnail/title package is under the early browse benchmark.",
                "suggestion": "Try a clearer result-led thumbnail and swap title candidate #2.",
            }
        )
    if avd and float(avd) < 45:
        alerts.append(
            {
                "type": "weak_avd",
                "severity": "medium",
                "title": "Weak Average View Duration",
                "message": "Early viewers are not staying long enough for strong recommendation signals.",
                "suggestion": "Pin a comment pointing to the payoff and cut a Shorts teaser from the strongest moment.",
            }
        )
    if len(comments) >= 5:
        alerts.append(
            {
                "type": "comment_spike",
                "severity": "medium",
                "title": "Comment Spike",
                "message": "Early comments are accelerating.",
                "suggestion": "Reply to high-intent questions now to boost conversation velocity.",
            }
        )
    if uploaded.get("analysis", {}).get("hook_report", {}).get("weak_hook"):
        alerts.append(
            {
                "type": "hook_followup",
                "severity": "high",
                "title": "Hook Needs Support",
                "message": "Pre-upload detector marked the opening weak.",
                "suggestion": "Pin a payoff comment and prepare a tighter intro recut for Shorts.",
            }
        )
    if not alerts:
        alerts.append(
            {
                "type": "healthy_start",
                "severity": "low",
                "title": "Healthy Start",
                "message": "No urgent first-24h intervention detected.",
                "suggestion": "Keep replying to early comments and monitor CTR after more impressions.",
            }
        )
    return alerts


def _draft_reply_batch(comments: List[Dict[str, Any]], uploaded: Dict[str, Any]) -> List[Dict[str, Any]]:
    topic = (uploaded.get("package") or {}).get("topic") or "the video"
    drafts = []
    for comment in comments[:6]:
        text = comment.get("text", "")
        if "short" in text.lower():
            reply = f"Good call. I am cutting a Shorts version of the strongest {topic} moment now."
        elif "thumbnail" in text.lower() or "title" in text.lower():
            reply = "Appreciate that. I am watching early CTR and may test a cleaner title/thumbnail combo today."
        else:
            reply = "Thanks for watching early. I am tracking the first 24h data and your feedback helps shape the next cut."
        drafts.append({"comment_id": comment.get("id"), "author": comment.get("author"), "draft": reply})
    return drafts


def _recommended_intervention(alerts: List[Dict[str, Any]]) -> str:
    alert_types = {alert.get("type") for alert in alerts}
    if "low_ctr" in alert_types:
        return "Change thumbnail/title first; CTR is the biggest first-24h constraint."
    if "weak_avd" in alert_types:
        return "Support retention with a pinned payoff comment and Shorts teaser."
    if "comment_spike" in alert_types:
        return "Reply to early comments now; conversation velocity is the opportunity."
    return "No urgent intervention. Keep monitoring until more impressions arrive."


def _war_room_next_actions(alerts: List[Dict[str, Any]]) -> List[str]:
    actions = []
    for alert in alerts:
        suggestion = alert.get("suggestion")
        if suggestion:
            actions.append(suggestion)
    actions.extend(["Draft replies for early comments", "Monitor CTR and AVD until the 24h mark"])
    return _dedupe(actions)[:8]


def _train_ai_state(
    agent: Any,
    app: Optional[FastAPI],
    engine: StreamPilotMathEngine,
    test_mode: bool,
) -> Dict[str, Any]:
    user = getattr(getattr(agent, "data_engine", None), "knowledge_base", {}).get("user", {})
    historical_videos = user.get("videos") or []
    view_values = [int(item.get("views", 0)) for item in historical_videos if isinstance(item, dict)]
    uploaded_count = len(getattr(getattr(app, "state", None), "uploaded_videos", {}) or {}) if app else 0
    samples = max(len(view_values) + uploaded_count, 1)
    avg_views = sum(view_values) / max(len(view_values), 1) if view_values else 10000.0
    sorted_views = sorted(view_values) or [int(avg_views)]
    median_views = sorted_views[len(sorted_views) // 2]
    recent = view_values[-7:] if len(view_values) >= 7 else view_values
    previous = view_values[-14:-7] if len(view_values) >= 14 else view_values[:7]
    recent_avg = sum(recent) / max(len(recent), 1) if recent else avg_views
    previous_avg = sum(previous) / max(len(previous), 1) if previous else avg_views
    growth_rate = ((recent_avg - previous_avg) / max(previous_avg, 1)) * 100.0
    trained_topics = list(getattr(engine, "trending_terms", []) or [])
    state = {
        "ok": True,
        "test_mode": test_mode,
        "model_version": f"streampilot-local-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "trained_samples": samples,
        "data_sources": [
            "local channel history",
            "published upload memory",
            "CTR heuristic/model signals",
            "war-room early metrics",
        ],
        "channel_baselines": {
            "average_views": int(avg_views),
            "median_views": int(median_views),
            "recent_growth_rate_pct": round(growth_rate, 2),
            "baseline_ctr": 4.8,
            "baseline_avd_seconds": 58,
            "baseline_24h_views": max(int(avg_views * 0.18), 300),
        },
        "prediction_weights": {
            "early_velocity": 0.38,
            "ctr_signal": 0.24,
            "average_view_duration": 0.18,
            "hook_quality": 0.12,
            "trend_alignment": 0.08,
        },
        "topic_priors": trained_topics,
        "learned_rules": [
            "High early CTR with average view duration above baseline raises breakout probability.",
            "Weak hook or low AVD suppresses 24h forecast even when early views look healthy.",
            "Trending-topic alignment boosts recommendations only when package fit is strong.",
        ],
        "note": "Local online training state. It updates the predictor without adding external dependencies.",
    }
    return state


def _train_ai_state_real(app: FastAPI, engine: StreamPilotMathEngine) -> Dict[str, Any]:
    try:
        yt = _youtube_factory_for_app(app)()
        videos = yt.get_recent_channel_videos(max_results=25)
        if not videos:
            raise RuntimeError("No real channel videos returned from YouTube.")
    except Exception as exc:
        return _real_youtube_error("train_ai", exc)

    views = [int(video.get("view_count") or 0) for video in videos]
    likes = [int(video.get("like_count") or 0) for video in videos]
    comments = [int(video.get("comment_count") or 0) for video in videos]
    velocities = [float(video.get("views_per_hour") or 0.0) for video in videos]
    avg_views = sum(views) / max(len(views), 1)
    median_views = sorted(views)[len(views) // 2] if views else 0
    recent_videos = sorted(videos, key=lambda item: item.get("published_at") or "", reverse=True)[:7]
    previous_videos = sorted(videos, key=lambda item: item.get("published_at") or "", reverse=True)[7:14]
    recent_avg = sum(int(item.get("view_count") or 0) for item in recent_videos) / max(len(recent_videos), 1)
    previous_avg = sum(int(item.get("view_count") or 0) for item in previous_videos) / max(len(previous_videos), 1)
    growth_rate = ((recent_avg - previous_avg) / max(previous_avg, 1)) * 100 if previous_videos else 0.0

    analytics_available = False
    analytics_rows = 0
    analytics_error = None
    try:
        if hasattr(yt, "get_channel_analytics_window"):
            analytics = yt.get_channel_analytics_window(days=28, strict=True)
        elif hasattr(yt, "get_analytics_data"):
            rows = yt.get_analytics_data()
            analytics = {"rows": rows, "analytics_available": bool(rows)}
        else:
            analytics = {"rows": [], "analytics_available": False}
        analytics_available = bool(analytics.get("analytics_available") or analytics.get("rows"))
        analytics_rows = len(analytics.get("rows") or [])
    except Exception as exc:
        analytics_error = str(exc)

    title_terms = _extract_title_terms([video.get("title", "") for video in videos])
    baseline_ctr = 4.8
    baseline_avd = 58
    if analytics_available and hasattr(yt, "get_channel_analytics_window"):
        totals = analytics.get("totals") or {}
        baseline_avd = int(totals.get("average_view_duration_seconds") or baseline_avd)

    state = {
        "ok": True,
        "source": "real_youtube",
        "mode": "real",
        "test_mode": bool(getattr(app.state, "test_mode", False)),
        "fake_fallback_used": False,
        "model_version": f"streampilot-real-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "trained_samples": len(videos),
        "fetched_counts": {
            "videos": len(videos),
            "analytics_rows": analytics_rows,
            "likes_total": sum(likes),
            "comments_total": sum(comments),
        },
        "data_sources": [
            "YouTube Data API videos/list",
            "YouTube channel upload history",
            "YouTube Analytics reports/query" if analytics_available else "YouTube Analytics unavailable/delayed",
        ],
        "channel_baselines": {
            "average_views": int(avg_views),
            "median_views": int(median_views),
            "recent_growth_rate_pct": round(growth_rate, 2),
            "baseline_ctr": baseline_ctr,
            "baseline_avd_seconds": baseline_avd,
            "baseline_24h_views": max(int(avg_views * 0.18), 300),
            "average_views_per_hour": round(sum(velocities) / max(len(velocities), 1), 2),
            "average_engagement_rate": round(((sum(likes) + sum(comments)) / max(sum(views), 1)) * 100, 2),
        },
        "prediction_weights": {
            "early_velocity": 0.4,
            "public_stats": 0.22,
            "analytics_signal": 0.18,
            "comment_velocity": 0.1,
            "trend_alignment": 0.1,
        },
        "topic_priors": title_terms,
        "learned_rules": [
            "Real velocity is compared against this channel's recent upload baseline.",
            "Analytics AVD strengthens confidence when YouTube has exposed rows.",
            "Comment velocity and engagement rate increase intervention urgency.",
        ],
        "recent_video_ids": [video.get("id") for video in videos[:10] if video.get("id")],
        "analytics_available": analytics_available,
        "analytics_error": analytics_error,
        "confidence": "high" if len(videos) >= 10 and analytics_available else "medium",
        "data_freshness": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "analytics_available": analytics_available,
            "analytics_delayed": not analytics_available,
        },
    }
    return state


def _build_realtime_prediction(video_id: str, app: FastAPI, test_mode: bool) -> Dict[str, Any]:
    uploaded = app.state.uploaded_videos.get(video_id, {})
    training_state = getattr(app.state, "ai_training_state", None) or _train_ai_state(app.state.agent, app, app.state.math_engine, test_mode)
    war_room = _build_war_room_payload(video_id, app, uploaded=uploaded, test_mode=test_mode)
    metrics = war_room.get("metrics") or {}
    package = uploaded.get("package") or {}
    analysis = uploaded.get("analysis") or {}
    baseline = training_state.get("channel_baselines", {})

    elapsed_hours = float(metrics.get("elapsed_hours") or 6)
    current_views = max(float(metrics.get("views") or 0), 1.0)
    ctr = metrics.get("ctr")
    avd = float(metrics.get("average_view_duration_seconds") or 0)
    baseline_ctr = float(baseline.get("baseline_ctr") or 4.8)
    baseline_avd = float(baseline.get("baseline_avd_seconds") or 58)
    baseline_24h = float(baseline.get("baseline_24h_views") or 1200)

    hourly_velocity = current_views / max(elapsed_hours, 1)
    ctr_factor = _clamp((float(ctr) / baseline_ctr) if ctr is not None else 1.0, 0.45, 2.0)
    avd_factor = _clamp((avd / baseline_avd) if avd else 0.85, 0.45, 1.7)
    hook_strength = float(analysis.get("hook_report", {}).get("hook_strength") or 62)
    hook_factor = _clamp(hook_strength / 65.0, 0.55, 1.35)
    trend_factor = _topic_trend_alignment(package.get("topic", ""), training_state.get("topic_priors", []))
    momentum = hourly_velocity * (0.72 + (ctr_factor * 0.16) + (avd_factor * 0.08) + (hook_factor * 0.04))

    next_1h = int(current_views + momentum)
    next_6h = int(current_views + momentum * 6 * _clamp(avd_factor, 0.65, 1.35))
    next_24h = int(max(current_views, baseline_24h * 0.35) + momentum * max(24 - elapsed_hours, 1) * trend_factor)
    expected_watch_minutes_24h = int((next_24h * max(avd, baseline_avd * 0.75)) / 60)
    virality_probability = _clamp(
        0.08 + (ctr_factor - 1) * 0.18 + (avd_factor - 1) * 0.15 + (hook_factor - 1) * 0.12 + (trend_factor - 1) * 0.1,
        0.03,
        0.72,
    )

    if virality_probability >= 0.35 and next_24h > baseline_24h:
        outcome = "breakout candidate"
    elif ctr is not None and float(ctr) < 3.5:
        outcome = "needs packaging intervention"
    elif avd and avd < baseline_avd * 0.75:
        outcome = "retention risk"
    else:
        outcome = "stable growth"

    title_for_prediction = (
        package.get("final_title")
        or package.get("topic")
        or uploaded.get("title")
        or video_id
    )
    trend_prediction = _build_realtime_trend_prediction(
        title=title_for_prediction,
        metrics=metrics,
        forecast_probability=virality_probability,
        baseline_24h=baseline_24h,
        hourly_velocity=hourly_velocity,
        velocity_factor=_clamp(hourly_velocity / max(baseline_24h / 24.0, 1.0), 0.35, 2.4),
        avd_factor=avd_factor,
        comment_factor=_clamp((float(metrics.get("comments") or 0) / max(current_views, 1.0)) / 0.01, 0.4, 1.8),
        trend_factor=trend_factor,
        topic_priors=training_state.get("topic_priors", []),
        analytics_available=True,
    )

    return {
        "ok": True,
        "video_id": video_id,
        "model_version": training_state.get("model_version"),
        "trained_samples": training_state.get("trained_samples"),
        "current_metrics": metrics,
        "forecast": {
            "next_1h_views": next_1h,
            "next_6h_views": next_6h,
            "next_24h_views": next_24h,
            "expected_24h_watch_time_minutes": expected_watch_minutes_24h,
            "virality_probability": round(virality_probability, 3),
            "outcome": outcome,
        },
        "signals": {
            "early_velocity_views_per_hour": round(hourly_velocity, 2),
            "ctr_factor": round(ctr_factor, 2),
            "avd_factor": round(avd_factor, 2),
            "hook_factor": round(hook_factor, 2),
            "trend_factor": round(trend_factor, 2),
        },
        "trend_prediction": trend_prediction,
        "youtube_trend_score": trend_prediction["signals"]["youtube_trend_score"],
        "creator_opportunity_score": trend_prediction["signals"]["creator_opportunity_score"],
        "recommended_intervention": war_room.get("recommended_intervention"),
        "next_actions": war_room.get("next_actions", [])[:6],
        "confidence": "medium" if metrics.get("views", 0) >= 100 else "low until more early data arrives",
        "war_room": war_room,
    }


def _build_realtime_prediction_real(video_id: str, app: FastAPI, refresh: bool = False) -> Dict[str, Any]:
    try:
        yt = _youtube_factory_for_app(app)()
        stats = yt.get_video_stats(video_id)
        if not stats:
            raise RuntimeError(f"Video not found or inaccessible: {video_id}")
    except Exception as exc:
        return _real_youtube_error("realtime_predict.video_stats", exc)

    analytics = {"rows": [], "totals": {}, "analytics_available": False}
    analytics_error = None
    try:
        if hasattr(yt, "get_video_analytics_window"):
            analytics = yt.get_video_analytics_window(video_id, days=7, strict=True)
        elif hasattr(yt, "get_video_analytics_24h"):
            analytics = yt.get_video_analytics_24h(video_id, strict=True)
        analytics["analytics_available"] = bool(analytics.get("analytics_available") or analytics.get("rows"))
    except Exception as exc:
        analytics_error = str(exc)
        analytics = {"rows": [], "totals": {}, "timeline": [], "analytics_available": False}

    comments = []
    comments_error = None
    try:
        comments = yt.get_recent_comments(video_id, max_results=20, strict=True)
    except Exception as exc:
        comments_error = str(exc)

    training_state = getattr(app.state, "ai_training_state", None)
    if not training_state or training_state.get("source") != "real_youtube" or refresh:
        training_state = _train_ai_state_real(app, app.state.math_engine)
        if training_state.get("ok"):
            app.state.ai_training_state = training_state
    if not training_state.get("ok"):
        fallback_baseline = _train_ai_state(app.state.agent, app, app.state.math_engine, bool(getattr(app.state, "test_mode", False)))
        baseline = fallback_baseline.get("channel_baselines", {})
    else:
        baseline = training_state.get("channel_baselines", {})

    public_views = int(stats.get("view_count") or 0)
    public_comments = int(stats.get("comment_count") or 0)
    published_at = stats.get("published_at")
    elapsed_hours = max(_hours_since(published_at), 0.5)
    analytics_totals = analytics.get("totals") or {}
    avd = float(
        analytics_totals.get("average_view_duration_seconds")
        or analytics_totals.get("averageViewDuration")
        or baseline.get("baseline_avd_seconds")
        or 58
    )
    watch_minutes = float(
        analytics_totals.get("watch_time_minutes")
        or analytics_totals.get("estimatedMinutesWatched")
        or (public_views * avd / 60.0)
    )
    metrics = {
        "elapsed_hours": round(elapsed_hours, 2),
        "views": public_views,
        "impressions": analytics_totals.get("impressions"),
        "ctr": analytics_totals.get("ctr"),
        "average_view_duration_seconds": round(avd, 2),
        "watch_time_minutes": round(watch_minutes, 2),
        "comments": public_comments,
        "likes": int(stats.get("like_count") or 0),
        "views_per_hour": round(public_views / elapsed_hours, 2),
    }
    alerts = _build_war_room_alerts(metrics, comments, {"package": {"topic": stats.get("title", "")}})
    war_room = {
        "ok": True,
        "video_id": video_id,
        "mode": "real",
        "source": "real_youtube",
        "metrics": metrics,
        "timeline": analytics.get("timeline") or analytics.get("rows") or [],
        "alert_cards": alerts,
        "first_comments": comments[:8],
        "ai_reply_drafts": _draft_reply_batch(comments, {"package": {"topic": stats.get("title", "")}}),
        "recommended_intervention": _recommended_intervention(alerts),
        "next_actions": _war_room_next_actions(alerts),
        "analytics_available": bool(analytics.get("analytics_available")),
        "comments_available": comments_error is None,
        "analytics_error": analytics_error,
        "comments_error": comments_error,
    }

    baseline_24h = float(baseline.get("baseline_24h_views") or max(public_views, 1200))
    baseline_avd = float(baseline.get("baseline_avd_seconds") or 58)
    baseline_velocity = float(baseline.get("average_views_per_hour") or max(baseline_24h / 24.0, 1.0))
    hourly_velocity = public_views / elapsed_hours
    avd_factor = _clamp(avd / max(baseline_avd, 1), 0.45, 1.7)
    velocity_factor = _clamp(hourly_velocity / max(baseline_velocity, 1), 0.35, 2.4)
    comment_factor = _clamp((public_comments / max(public_views, 1)) / 0.01, 0.4, 1.8)
    trend_factor = _topic_trend_alignment(stats.get("title", ""), training_state.get("topic_priors", [])) if training_state.get("ok") else 1.0
    momentum = hourly_velocity * (0.62 + velocity_factor * 0.18 + avd_factor * 0.12 + comment_factor * 0.05 + trend_factor * 0.03)
    remaining_hours = max(24 - elapsed_hours, 1)
    next_24h = int(max(public_views, baseline_24h * 0.25) + momentum * remaining_hours)
    virality_probability = _clamp(
        0.08 + (velocity_factor - 1) * 0.2 + (avd_factor - 1) * 0.15 + (comment_factor - 1) * 0.08 + (trend_factor - 1) * 0.08,
        0.03,
        0.82,
    )
    outcome = "stable growth"
    if virality_probability >= 0.38 and next_24h >= baseline_24h:
        outcome = "breakout candidate"
    elif analytics_error:
        outcome = "public-stats forecast; analytics delayed"
    elif avd_factor < 0.75:
        outcome = "retention risk"

    trend_prediction = _build_realtime_trend_prediction(
        title=stats.get("title") or video_id,
        metrics=metrics,
        forecast_probability=virality_probability,
        baseline_24h=baseline_24h,
        hourly_velocity=hourly_velocity,
        velocity_factor=velocity_factor,
        avd_factor=avd_factor,
        comment_factor=comment_factor,
        trend_factor=trend_factor,
        topic_priors=training_state.get("topic_priors", []) if training_state.get("ok") else [],
        analytics_available=bool(analytics.get("analytics_available")),
    )

    return {
        "ok": True,
        "source": "real_youtube",
        "mode": "real",
        "fake_fallback_used": False,
        "video_id": video_id,
        "video": stats,
        "model_version": training_state.get("model_version"),
        "trained_samples": training_state.get("trained_samples"),
        "current_metrics": metrics,
        "forecast": {
            "next_1h_views": int(public_views + momentum),
            "next_6h_views": int(public_views + momentum * 6),
            "next_24h_views": next_24h,
            "expected_24h_watch_time_minutes": int((next_24h * avd) / 60),
            "virality_probability": round(virality_probability, 3),
            "outcome": outcome,
        },
        "signals": {
            "early_velocity_views_per_hour": round(hourly_velocity, 2),
            "velocity_factor": round(velocity_factor, 2),
            "avd_factor": round(avd_factor, 2),
            "comment_factor": round(comment_factor, 2),
            "trend_factor": round(trend_factor, 2),
        },
        "trend_prediction": trend_prediction,
        "youtube_trend_score": trend_prediction["signals"]["youtube_trend_score"],
        "creator_opportunity_score": trend_prediction["signals"]["creator_opportunity_score"],
        "recommended_intervention": war_room.get("recommended_intervention"),
        "next_actions": war_room.get("next_actions", [])[:6],
        "confidence": "high" if analytics.get("analytics_available") else "medium with public stats; analytics delayed",
        "data_freshness": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "public_stats_available": True,
            "analytics_available": bool(analytics.get("analytics_available")),
            "analytics_delayed": not bool(analytics.get("analytics_available")),
            "comments_available": comments_error is None,
            "analytics_error": analytics_error,
            "comments_error": comments_error,
        },
        "war_room": war_room,
    }


def _build_realtime_trend_prediction(
    title: str,
    metrics: Dict[str, Any],
    forecast_probability: float,
    baseline_24h: float,
    hourly_velocity: float,
    velocity_factor: float,
    avd_factor: float,
    comment_factor: float,
    trend_factor: float,
    topic_priors: List[str],
    analytics_available: bool,
) -> Dict[str, Any]:
    views = float(metrics.get("views") or 0)
    comments = float(metrics.get("comments") or 0)
    likes = float(metrics.get("likes") or 0)
    engagement_rate = ((likes + comments) / max(views, 1.0)) * 100.0
    velocity_score = _clamp((velocity_factor / 2.4) * 100.0, 1, 100)
    avd_score = _clamp((avd_factor / 1.7) * 100.0, 1, 100)
    comment_score = _clamp((comment_factor / 1.8) * 100.0, 1, 100)
    forecast_score = _clamp(forecast_probability * 100.0, 1, 100)
    trend_fit_score = _channel_fit_score(title, topic_priors)
    youtube_score = int(round(velocity_score * 0.38 + avd_score * 0.22 + comment_score * 0.16 + forecast_score * 0.24))
    creator_score = int(round(youtube_score * 0.68 + trend_fit_score * 0.22 + _clamp((trend_factor / 1.12) * 100.0, 1, 100) * 0.10))
    positive_momentum = velocity_factor >= 1.05 or forecast_probability >= 0.38
    weak_retention = avd_factor < 0.75

    if creator_score >= 78 and positive_momentum and not weak_retention:
        status = "will_trend_soon"
    elif weak_retention and creator_score < 82:
        status = "cooling"
    elif creator_score >= 58:
        status = "watchlist"
    else:
        status = "low_probability"

    probability = _clamp(
        creator_score / 100.0
        + (0.05 if positive_momentum else 0.0)
        - (0.1 if weak_retention else 0.0)
        - (0.04 if not analytics_available else 0.0),
        0.03,
        0.94,
    )
    reasons: List[str] = []
    if velocity_factor >= 1.05:
        reasons.append("Early velocity is above the channel baseline.")
    if forecast_probability >= 0.38:
        reasons.append("The 24h forecast is inside the breakout band.")
    if avd_factor >= 1.0:
        reasons.append("Average view duration is supporting distribution.")
    elif weak_retention:
        reasons.append("Retention is pulling the forecast down.")
    if comment_factor >= 1.0:
        reasons.append("Comment velocity is helping momentum.")
    if not analytics_available:
        reasons.append("Analytics are delayed, so confidence uses public stats.")
    if not reasons:
        reasons.append("Signals need more early data before a strong call.")

    return {
        "status": status,
        "will_trend_soon": status == "will_trend_soon",
        "score": creator_score,
        "probability": round(probability, 3),
        "confidence": "medium" if analytics_available else "medium with analytics delayed",
        "signals": {
            "youtube_trend_score": youtube_score,
            "creator_opportunity_score": creator_score,
            "velocity_factor": round(velocity_factor, 2),
            "views_per_hour": int(round(hourly_velocity)),
            "baseline_24h_views": int(round(baseline_24h)),
            "avd_factor": round(avd_factor, 2),
            "comment_factor": round(comment_factor, 2),
            "trend_factor": round(trend_factor, 2),
            "engagement_rate": round(engagement_rate, 2),
            "forecast_probability": round(forecast_probability, 3),
            "history_available": False,
            "snapshots_seen": 0,
            "analytics_available": analytics_available,
        },
        "reasons": _dedupe(reasons)[:5],
        "recommended_action": _trend_prediction_action(title, status, "your upload"),
    }


def _build_trending_scan(
    app: FastAPI,
    engine: StreamPilotMathEngine,
    region_code: str,
    category_id: Optional[str],
    max_results: int,
    test_mode: bool,
    real_source: bool = False,
) -> Dict[str, Any]:
    cache_key = f"{region_code}:{category_id or 'all'}:{max_results}"
    if real_source:
        try:
            yt = _youtube_factory_for_app(app)()
            raw_videos = yt.get_trending_videos(region_code=region_code, category_id=category_id, max_results=max_results)
        except Exception as exc:
            return {
                **_real_youtube_error("trending_videos", exc),
                "region_code": region_code,
                "category_id": category_id,
                "videos": [],
                "trend_predictions": [],
                "trend_summary": {},
                "next_actions": [],
            }
    elif test_mode:
        raw_videos = _fake_trending_video_rows(region_code, category_id, max_results)
    else:
        try:
            yt = _youtube_factory_for_app(app)()
            raw_videos = yt.get_trending_videos(region_code=region_code, category_id=category_id, max_results=max_results)
        except Exception as exc:
            fallback = _fake_trending_video_rows(region_code, category_id, max_results)
            analyzed_fallback = [
                _analyze_trending_video({**row, "source_rank": rank}, engine)
                for rank, row in enumerate(fallback, start=1)
            ]
            return {
                "ok": False,
                "mode": "fallback",
                "region_code": region_code,
                "category_id": category_id,
                "error": str(exc),
                "videos": analyzed_fallback,
                "trend_summary": _summarize_trends(analyzed_fallback),
            }

    analyzed = [
        _analyze_trending_video({**row, "source_rank": rank}, engine)
        for rank, row in enumerate(raw_videos[:max_results], start=1)
    ]
    store_status = _attach_trend_predictions(
        app,
        analyzed,
        region_code=region_code,
        category_id=category_id,
        source="real_youtube" if real_source else ("test" if test_mode else "youtube_or_fallback"),
    )
    analyzed.sort(key=lambda item: item.get("creator_opportunity_score", item["opportunity_score"]), reverse=True)
    payload = {
        "ok": True,
        "source": "real_youtube" if real_source else ("test" if test_mode else "youtube_or_fallback"),
        "mode": "real" if real_source else ("test" if test_mode else "real"),
        "fake_fallback_used": False,
        "region_code": region_code,
        "category_id": category_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "videos": analyzed,
        "trend_predictions": [video.get("trend_prediction") for video in analyzed if video.get("trend_prediction")],
        "trend_summary": _summarize_trends(analyzed),
        "next_actions": _trend_next_actions(analyzed),
        "trend_store": store_status,
        "source_note": "Uses YouTube videos.list chart=mostPopular in real mode.",
    }
    app.state.trending_cache[cache_key] = payload
    return payload


def _trend_store_path(app: FastAPI) -> str:
    return getattr(app.state, "trend_store_path", None) or os.getenv("STREAMPILOT_TREND_STORE_PATH") or TREND_SNAPSHOT_PATH


def _empty_trend_store() -> Dict[str, Any]:
    return {"version": 1, "videos": {}, "created_at": datetime.now(timezone.utc).isoformat()}


def _load_trend_store(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return _empty_trend_store()
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return _empty_trend_store()
    videos = data.get("videos")
    if not isinstance(videos, dict):
        data["videos"] = {}
    data.setdefault("version", 1)
    return data


def _save_trend_store(path: str, store: Dict[str, Any]) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(store, handle, ensure_ascii=True, indent=2)


def _attach_trend_predictions(
    app: FastAPI,
    videos: List[Dict[str, Any]],
    region_code: str,
    category_id: Optional[str],
    source: str,
) -> Dict[str, Any]:
    path = _trend_store_path(app)
    fetched_at = datetime.now(timezone.utc).isoformat()
    store_error = None
    store_ok = True
    store = _empty_trend_store()
    histories: Dict[str, List[Dict[str, Any]]] = {}

    try:
        store = _load_trend_store(path)
        store.setdefault("videos", {})
        for rank, video in enumerate(videos, start=1):
            video["source_rank"] = int(video.get("source_rank") or rank)
            video_id = str(video.get("id") or "").strip()
            if not video_id:
                continue
            entry = store["videos"].setdefault(
                video_id,
                {
                    "id": video_id,
                    "title": video.get("title", ""),
                    "channel_title": video.get("channel_title", ""),
                    "region_code": region_code,
                    "category_id": video.get("category_id") or category_id,
                    "snapshots": [],
                },
            )
            entry.update(
                {
                    "title": video.get("title", entry.get("title", "")),
                    "channel_title": video.get("channel_title", entry.get("channel_title", "")),
                    "region_code": region_code,
                    "category_id": video.get("category_id") or category_id or entry.get("category_id"),
                    "last_seen_at": fetched_at,
                }
            )
            entry["snapshots"].append(_trend_snapshot(video, region_code, category_id, fetched_at, source))
            entry["snapshots"] = entry["snapshots"][-12:]
            histories[video_id] = list(entry["snapshots"])

        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        store["videos"] = {
            video_id: entry
            for video_id, entry in store.get("videos", {}).items()
            if _parse_trend_timestamp(entry.get("last_seen_at") or _last_snapshot_time(entry)) >= cutoff
        }
        store["updated_at"] = fetched_at
        _save_trend_store(path, store)
    except Exception as exc:
        store_ok = False
        store_error = str(exc)
        histories = {}

    priors = []
    training_state = getattr(app.state, "ai_training_state", {}) or {}
    if isinstance(training_state, dict):
        priors = training_state.get("topic_priors") or []

    for rank, video in enumerate(videos, start=1):
        video["source_rank"] = int(video.get("source_rank") or rank)
    velocities = [float(video.get("views_per_hour") or 0) for video in videos]
    for video in videos:
        history = histories.get(str(video.get("id") or ""), []) if store_ok else []
        prediction = _build_trend_prediction(video, videos, velocities, history, priors, store_ok=store_ok)
        video["trend_prediction"] = prediction
        video["youtube_trend_score"] = prediction["signals"]["youtube_trend_score"]
        video["creator_opportunity_score"] = prediction["signals"]["creator_opportunity_score"]
        video["history_available"] = bool(prediction["signals"]["history_available"])

    return {
        "ok": store_ok,
        "path": path,
        "history_available": any(video.get("history_available") for video in videos),
        "stored_videos": len(store.get("videos", {})) if store_ok else 0,
        "error": store_error,
    }


def _trend_snapshot(
    video: Dict[str, Any],
    region_code: str,
    category_id: Optional[str],
    fetched_at: str,
    source: str,
) -> Dict[str, Any]:
    return {
        "fetched_at": fetched_at,
        "rank": int(video.get("source_rank") or 0),
        "views": int(video.get("view_count") or 0),
        "likes": int(video.get("like_count") or 0),
        "comments": int(video.get("comment_count") or 0),
        "age_hours": float(video.get("age_hours") or 0),
        "views_per_hour": float(video.get("views_per_hour") or 0),
        "engagement_rate": float(video.get("engagement_rate") or 0),
        "topic_cluster": video.get("topic_cluster"),
        "category_id": video.get("category_id") or category_id,
        "region_code": region_code,
        "source": source,
    }


def _last_snapshot_time(entry: Dict[str, Any]) -> Optional[str]:
    snapshots = entry.get("snapshots") or []
    if not snapshots:
        return None
    return snapshots[-1].get("fetched_at")


def _parse_trend_timestamp(value: Optional[str]) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return datetime.fromtimestamp(0, timezone.utc)


def _build_trend_prediction(
    video: Dict[str, Any],
    batch: List[Dict[str, Any]],
    velocities: List[float],
    history: List[Dict[str, Any]],
    topic_priors: List[str],
    store_ok: bool = True,
) -> Dict[str, Any]:
    title = video.get("title", "")
    rank = int(video.get("source_rank") or len(batch) or 1)
    velocity = float(video.get("views_per_hour") or 0)
    engagement_rate = float(video.get("engagement_rate") or 0)
    age_hours = float(video.get("age_hours") or 24)
    predicted_ctr = float(video.get("predicted_ctr") or 0)
    previous = history[-2] if len(history) >= 2 else None
    history_available = bool(previous and store_ok)

    velocity_percentile = _percentile_rank(velocity, velocities)
    velocity_intensity = _clamp((velocity / 50000.0) * 100.0, 1, 100)
    velocity_score = _clamp(velocity_percentile * 0.58 + velocity_intensity * 0.42, 1, 100)
    engagement_score = _clamp((engagement_rate / 6.0) * 100.0, 1, 100)
    freshness_score = _clamp(((48.0 - age_hours) / 48.0) * 100.0, 0, 100)
    rank_score = _clamp(((max(len(batch), 1) - rank + 1) / max(len(batch), 1)) * 100.0, 1, 100)

    previous_velocity = float(previous.get("views_per_hour") or 0) if previous else 0.0
    acceleration_pct = ((velocity - previous_velocity) / max(previous_velocity, 1.0)) * 100.0 if previous else 0.0
    previous_rank = int(previous.get("rank") or rank) if previous else rank
    rank_movement = previous_rank - rank if previous else 0
    acceleration_score = 50.0
    if previous:
        acceleration_score = _clamp(50.0 + acceleration_pct * 0.8 + rank_movement * 8.0, 0, 100)

    youtube_score = int(
        round(
            velocity_score * 0.30
            + acceleration_score * 0.24
            + engagement_score * 0.18
            + freshness_score * 0.14
            + rank_score * 0.14
        )
    )
    channel_fit = _channel_fit_score(title, topic_priors)
    title_hook_score = _clamp((predicted_ctr / 12.0) * 100.0, 1, 100)
    creator_score = int(round(youtube_score * 0.58 + channel_fit * 0.24 + title_hook_score * 0.18))

    positive_acceleration = history_available and (acceleration_pct >= 8.0 or rank_movement > 0)
    cooling_signal = history_available and (acceleration_pct <= -15.0 or rank_movement <= -2)
    exceptional_single_scan = (
        not history_available
        and youtube_score >= 90
        and creator_score >= 82
        and velocity >= 25000
        and engagement_rate >= 3.0
    )

    if cooling_signal and not positive_acceleration:
        status = "cooling"
    elif (creator_score >= 78 and positive_acceleration) or exceptional_single_scan:
        status = "will_trend_soon"
    elif creator_score >= 58:
        status = "watchlist"
    else:
        status = "low_probability"

    probability = _clamp(
        creator_score / 100.0
        + (0.08 if positive_acceleration else 0.0)
        + (0.04 if exceptional_single_scan else 0.0)
        - (0.12 if cooling_signal else 0.0)
        - (0.08 if not history_available and not exceptional_single_scan else 0.0),
        0.03,
        0.94,
    )
    confidence = _trend_confidence(len(history), history_available, exceptional_single_scan, store_ok)
    return {
        "status": status,
        "will_trend_soon": status == "will_trend_soon",
        "score": creator_score,
        "probability": round(probability, 3),
        "confidence": confidence,
        "signals": {
            "youtube_trend_score": youtube_score,
            "creator_opportunity_score": creator_score,
            "velocity_percentile": round(velocity_percentile, 2),
            "views_per_hour": int(round(velocity)),
            "acceleration_pct": round(acceleration_pct, 2),
            "rank_movement": rank_movement,
            "engagement_rate": round(engagement_rate, 2),
            "freshness_score": round(freshness_score, 2),
            "rank_score": round(rank_score, 2),
            "channel_fit_score": round(channel_fit, 2),
            "title_hook_score": round(title_hook_score, 2),
            "history_available": history_available,
            "snapshots_seen": len(history) if store_ok else 0,
            "storage_ok": store_ok,
        },
        "reasons": _trend_prediction_reasons(
            status,
            velocity,
            velocity_percentile,
            acceleration_pct,
            rank_movement,
            engagement_rate,
            history_available,
            exceptional_single_scan,
        ),
        "recommended_action": _trend_prediction_action(title, status, video.get("topic_cluster", "trend")),
    }


def _percentile_rank(value: float, values: List[float]) -> float:
    clean_values = [float(item) for item in values if item is not None]
    if not clean_values:
        return 50.0
    lower_or_equal = sum(1 for item in clean_values if item <= value)
    return _clamp((lower_or_equal / len(clean_values)) * 100.0, 1, 100)


def _channel_fit_score(title: str, priors: List[str]) -> float:
    alignment = _topic_trend_alignment(title, priors)
    if alignment >= 1.11:
        return 100.0
    if alignment >= 1.07:
        return 88.0
    if alignment >= 1.0:
        return 70.0
    return 52.0


def _trend_confidence(history_len: int, history_available: bool, exceptional_single_scan: bool, store_ok: bool) -> str:
    if not store_ok:
        return "low"
    if history_len >= 3:
        return "high"
    if history_available:
        return "medium"
    if exceptional_single_scan:
        return "medium"
    return "low"


def _trend_prediction_reasons(
    status: str,
    velocity: float,
    velocity_percentile: float,
    acceleration_pct: float,
    rank_movement: int,
    engagement_rate: float,
    history_available: bool,
    exceptional_single_scan: bool,
) -> List[str]:
    reasons: List[str] = []
    if velocity_percentile >= 80:
        reasons.append("Velocity is near the top of the current scan.")
    if velocity >= 25000:
        reasons.append("View speed is already strong for the publish age.")
    if history_available and acceleration_pct > 0:
        reasons.append(f"Velocity is accelerating by {round(acceleration_pct, 1)}%.")
    if history_available and rank_movement > 0:
        reasons.append(f"Rank improved by {rank_movement} place(s).")
    if engagement_rate >= 4.5:
        reasons.append("Like/comment engagement is above the strong-signal band.")
    if exceptional_single_scan:
        reasons.append("Single-scan signals are strong enough to flag early.")
    if status == "cooling":
        reasons.append("Recent velocity or rank movement is cooling.")
    if not history_available and not exceptional_single_scan:
        reasons.append("Needs another scan for acceleration confidence.")
    return _dedupe(reasons)[:5]


def _trend_prediction_action(title: str, status: str, cluster: str) -> str:
    clean_title = _limit_text(re.sub(r"\s+", " ", title or "").strip(), 80)
    if status == "will_trend_soon":
        return f"Create a fast response package now around {clean_title or cluster}."
    if status == "watchlist":
        return f"Draft a Shorts hook and rescan soon before committing to a full {cluster} video."
    if status == "cooling":
        return "Use only if you have a sharply different angle; momentum is fading."
    return "Do not prioritize this trend yet."


def _fake_trending_video_rows(region_code: str, category_id: Optional[str], max_results: int) -> List[Dict[str, Any]]:
    base_topics = [
        ("RTX 5090 Benchmarks Are Finally Real", "TechPulse", 1800000, 84000, 9400, "28"),
        ("I Tried the New AI Video Editor for 7 Days", "CreatorLab", 920000, 51000, 5200, "28"),
        ("Budget Gaming PC Build That Beat My Console", "BuildArena", 740000, 36000, 4100, "20"),
        ("The Hidden Settings Every YouTuber Should Change", "ChannelOps", 610000, 29000, 3300, "27"),
        ("This Tiny Camera Changed My Whole Setup", "GearDesk", 530000, 25000, 2600, "28"),
        ("I Let AI Run My Channel for 24 Hours", "AutomationStudio", 1200000, 64000, 8700, "28"),
    ]
    now = datetime.now(timezone.utc)
    rows = []
    for idx, (title, channel, views, likes, comments, cat) in enumerate(base_topics[:max_results]):
        published = now - timedelta(hours=4 + idx * 3)
        rows.append(
            {
                "id": f"trend{idx:08d}",
                "title": title,
                "channel_title": channel,
                "view_count": views,
                "like_count": likes,
                "comment_count": comments,
                "published_at": published.isoformat(),
                "category_id": category_id or cat,
                "region_code": region_code,
                "url": YOUTUBE_WATCH_URL.format(video_id=f"trend{idx:08d}"),
                "thumbnail_url": "",
            }
        )
    return rows


def _analyze_trending_video(row: Dict[str, Any], engine: StreamPilotMathEngine) -> Dict[str, Any]:
    title = row.get("title", "")
    published_at = row.get("published_at")
    age_hours = _hours_since(published_at)
    views = int(row.get("view_count") or 0)
    likes = int(row.get("like_count") or 0)
    comments = int(row.get("comment_count") or 0)
    velocity = views / max(age_hours, 1.0)
    engagement_rate = ((likes + comments) / max(views, 1)) * 100
    ctr_prediction = engine.predict_ctr(title)
    hook_score = float(ctr_prediction.get("predicted_ctr") or 0)
    cluster = _trend_cluster(title)
    opportunity_score = int(
        _clamp((velocity / 35000) * 42 + (engagement_rate / 7) * 20 + (hook_score / 12) * 25 + _cluster_bonus(cluster), 1, 100)
    )
    return {
        **row,
        "age_hours": round(age_hours, 1),
        "views_per_hour": int(velocity),
        "engagement_rate": round(engagement_rate, 2),
        "predicted_ctr": round(hook_score, 2),
        "topic_cluster": cluster,
        "opportunity_score": opportunity_score,
        "why_trending": _why_trending(title, velocity, engagement_rate, cluster),
        "creator_action": _trend_creator_action(title, cluster, opportunity_score),
        "package_angle": _trend_package_angle(title, cluster),
    }


def _hours_since(iso_value: Optional[str]) -> float:
    if not iso_value:
        return 24.0
    try:
        normalized = iso_value.replace("Z", "+00:00")
        published = datetime.fromisoformat(normalized)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        return max((datetime.now(timezone.utc) - published).total_seconds() / 3600.0, 0.5)
    except Exception:
        return 24.0


def _trend_cluster(title: str) -> str:
    lower = title.lower()
    if any(term in lower for term in ("ai", "automation", "editor")):
        return "AI creator tools"
    if any(term in lower for term in ("gpu", "pc", "rtx", "laptop", "camera", "setup")):
        return "tech and gear"
    if any(term in lower for term in ("gaming", "console", "game")):
        return "gaming"
    if any(term in lower for term in ("youtube", "channel", "creator")):
        return "creator growth"
    return "general trend"


def _cluster_bonus(cluster: str) -> int:
    return {
        "AI creator tools": 16,
        "tech and gear": 13,
        "creator growth": 12,
        "gaming": 8,
    }.get(cluster, 5)


def _why_trending(title: str, velocity: float, engagement_rate: float, cluster: str) -> List[str]:
    reasons = []
    if velocity > 50000:
        reasons.append("High view velocity for its publish age.")
    if engagement_rate > 4.5:
        reasons.append("Strong like/comment ratio suggests active viewer interest.")
    if re.search(r"\b(new|finally|hidden|changed|24 hours|7 days|beat)\b", title.lower()):
        reasons.append("Title uses a concrete novelty or curiosity hook.")
    reasons.append(f"Cluster momentum: {cluster}.")
    return reasons[:4]


def _trend_creator_action(title: str, cluster: str, opportunity_score: int) -> str:
    if opportunity_score >= 75:
        return f"Make a fast response video today using a contrarian or practical angle on {cluster}."
    if opportunity_score >= 50:
        return f"Create a Shorts test first, then expand if comments validate the {cluster} angle."
    return f"Save this as a research signal; wait for stronger proof before making a full {cluster} video."


def _trend_package_angle(title: str, cluster: str) -> Dict[str, Any]:
    cleaned = re.sub(r"\s+", " ", title).strip()
    return {
        "title_seed": _limit_text(f"I Tested This Trend So You Know What Actually Matters", 100),
        "description_seed": _limit_text(
            f"A fast creator-first breakdown of the trend behind '{cleaned}' and what it means for {cluster}.",
            260,
        ),
        "shorts_hook": _limit_text(f"{cleaned}: the 15-second takeaway creators need", 90),
    }


def _summarize_trends(videos: List[Dict[str, Any]]) -> Dict[str, Any]:
    clusters: Dict[str, int] = {}
    for video in videos:
        clusters[video["topic_cluster"]] = clusters.get(video["topic_cluster"], 0) + 1
    top_cluster = max(clusters, key=clusters.get) if clusters else "none"
    best = videos[0] if videos else {}
    return {
        "top_cluster": top_cluster,
        "cluster_counts": clusters,
        "best_opportunity": best.get("title"),
        "best_opportunity_score": best.get("opportunity_score"),
        "average_opportunity_score": round(sum(v.get("opportunity_score", 0) for v in videos) / max(len(videos), 1), 1),
    }


def _trend_next_actions(videos: List[Dict[str, Any]]) -> List[str]:
    top = videos[:3]
    actions = [video.get("creator_action", "") for video in top if video.get("creator_action")]
    actions.append("Turn the best trend into one long-form outline and two Shorts hooks.")
    actions.append("Compare trend fit against your current channel baseline before publishing.")
    return _dedupe(actions)[:6]


def _extract_title_terms(titles: List[str], limit: int = 16) -> List[str]:
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "your",
        "you",
        "are",
        "was",
        "from",
        "into",
        "video",
        "review",
    }
    counts: Dict[str, int] = {}
    for title in titles:
        for token in re.findall(r"[a-z0-9]+", title.lower()):
            if len(token) < 3 or token in stop_words:
                continue
            counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ranked[:limit]]


def _topic_trend_alignment(topic: str, priors: List[str]) -> float:
    lower = (topic or "").lower()
    if not lower:
        return 1.0
    if any(prior.lower() in lower or any(token in lower for token in prior.lower().split()) for prior in priors):
        return 1.12
    if any(term in lower for term in ("ai", "rtx", "gpu", "gaming", "youtube", "creator")):
        return 1.08
    return 0.96


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _seo_prompt(topic: str) -> str:
    return f"""
    You are a world-class YouTube strategist and viral packaging expert.
    A creator wants to make a video about: "{topic}"

    Generate a complete YouTube SEO package.
    Return ONLY a raw JSON object. Do not include markdown fences.

    Example output format:
    {{
      "titles": [
        "I built a $500 PC to destroy the PS5",
        "The dark truth about gaming monitors...",
        "Do NOT buy a prebuilt PC in 2026."
      ],
      "description": "A 2-3 sentence highly engaging description using relevant keywords.",
      "tags": ["gaming pc", "pc build", "budget pc"],
      "best_time": "Friday 4:00 PM EST"
    }}
    """


def _ai_upload_prompt(topic: str) -> str:
    return f"""
    You are StreamPilot AI, a fully managed YouTube channel operator.
    A creator is uploading a video about: "{topic}"

    Generate a complete public-upload package for YouTube.
    Return ONLY a raw JSON object. Do not include markdown fences.

    Required shape:
    {{
      "titles": ["3 high-CTR titles, each under 100 chars"],
      "final_title": "best title under 100 chars",
      "description": "SEO-rich YouTube description with natural keywords and viewer promise",
      "tags": ["10 to 15 concise tags"],
      "category_id": "28",
      "hashtags": ["#tag1", "#tag2", "#tag3"],
      "pinned_comment": "short comment to pin after publishing",
      "thumbnail_brief": "specific visual direction for the thumbnail",
      "upload_checklist": ["public visibility", "title", "description", "tags", "thumbnail", "first 24h monitoring"],
      "best_time": "best publish window",
      "next_actions": ["reply to early comments", "make shorts", "monitor CTR"]
    }}
    """


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
