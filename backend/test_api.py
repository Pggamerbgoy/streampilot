import os
import sys
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient


os.environ["STREAMPILOT_TEST_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import server as server_module  # noqa: E402
from server import _TestAgent, create_app  # noqa: E402
from training_pipeline import TrainingPipeline  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "real_youtube: read-only tests that call the real YouTube APIs")


class FakeReadOnlyYouTube:
    def get_recent_channel_videos(self, max_results=25):
        return [
            {
                "id": "realVid001",
                "title": "Real RTX 5090 Review",
                "view_count": 10000,
                "like_count": 700,
                "comment_count": 80,
                "published_at": "2026-06-01T10:00:00Z",
                "category_id": "28",
                "views_per_hour": 120.0,
            },
            {
                "id": "realVid002",
                "title": "AI Creator Tools Tested",
                "view_count": 18000,
                "like_count": 1400,
                "comment_count": 130,
                "published_at": "2026-05-30T10:00:00Z",
                "category_id": "28",
                "views_per_hour": 150.0,
            },
        ]

    def get_channel_analytics_window(self, days=28, strict=False):
        return {
            "rows": [
                {"day": "2026-06-01", "views": 1000, "watch_time_minutes": 900, "average_view_duration_seconds": 54},
                {"day": "2026-06-02", "views": 1500, "watch_time_minutes": 1600, "average_view_duration_seconds": 64},
            ],
            "totals": {"views": 2500, "watch_time_minutes": 2500, "average_view_duration_seconds": 60},
            "analytics_available": True,
        }

    def get_video_stats(self, video_id):
        return {
            "id": video_id,
            "title": "Real RTX 5090 Review",
            "view_count": 12000,
            "like_count": 900,
            "comment_count": 95,
            "published_at": "2026-06-01T10:00:00Z",
            "category_id": "28",
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }

    def get_video_analytics_window(self, video_id, days=7, strict=False):
        return {
            "rows": [{"day": "2026-06-02", "views": 1200, "watch_time_minutes": 1300, "average_view_duration_seconds": 65}],
            "timeline": [{"day": "2026-06-02", "views": 1200}],
            "totals": {"views": 1200, "watch_time_minutes": 1300, "average_view_duration_seconds": 65, "comments": 20},
            "analytics_available": True,
        }

    def get_recent_comments(self, video_id, max_results=20, strict=False):
        return [{"id": "c1", "author": "Viewer", "text": "This real data breakdown is useful."}]

    def get_trending_videos(self, region_code="US", category_id=None, max_results=12):
        return [
            {
                "id": "trendReal1",
                "title": "AI Video Editing Is Everywhere Now",
                "channel_title": "CreatorLab",
                "view_count": 500000,
                "like_count": 30000,
                "comment_count": 2500,
                "published_at": "2026-06-03T10:00:00Z",
                "category_id": "28",
                "region_code": region_code,
                "url": "https://www.youtube.com/watch?v=trendReal1",
                "thumbnail_url": "",
            }
        ][:max_results]


class RisingTrendYouTube(FakeReadOnlyYouTube):
    def get_trending_videos(self, region_code="US", category_id=None, max_results=12):
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "trendRise",
                "title": "AI Video Editing Explosion Is Happening Now",
                "channel_title": "CreatorLab",
                "view_count": 900000,
                "like_count": 45000,
                "comment_count": 4000,
                "published_at": (now - timedelta(hours=4)).isoformat(),
                "category_id": "28",
                "region_code": region_code,
                "url": "https://www.youtube.com/watch?v=trendRise",
                "thumbnail_url": "",
            },
            {
                "id": "trendOther1",
                "title": "Budget Camera Setup Tested",
                "channel_title": "GearDesk",
                "view_count": 150000,
                "like_count": 6000,
                "comment_count": 400,
                "published_at": (now - timedelta(hours=9)).isoformat(),
                "category_id": "28",
                "region_code": region_code,
                "url": "https://www.youtube.com/watch?v=trendOther1",
                "thumbnail_url": "",
            },
        ][:max_results]


class CoolingTrendYouTube(FakeReadOnlyYouTube):
    def get_trending_videos(self, region_code="US", category_id=None, max_results=12):
        now = datetime.now(timezone.utc)
        rows = [
            ("trendOtherA", "New Creator Tool Tested", 420000, 21000, 1800, 5),
            ("trendOtherB", "RTX Setup Mistakes", 340000, 12000, 900, 6),
            ("trendOtherC", "Hidden YouTube Settings", 260000, 9000, 850, 7),
            ("trendCool", "AI Editing Trend Is Slowing Down", 180000, 8500, 700, 6),
        ]
        return [
            {
                "id": video_id,
                "title": title,
                "channel_title": "TrendLab",
                "view_count": views,
                "like_count": likes,
                "comment_count": comments,
                "published_at": (now - timedelta(hours=age)).isoformat(),
                "category_id": "28",
                "region_code": region_code,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail_url": "",
            }
            for video_id, title, views, likes, comments, age in rows[:max_results]
        ]


class ModerateTrendYouTube(FakeReadOnlyYouTube):
    def get_trending_videos(self, region_code="US", category_id=None, max_results=12):
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "trendSingle",
                "title": "Creator Desk Setup Update",
                "channel_title": "SmallLab",
                "view_count": 72000,
                "like_count": 1800,
                "comment_count": 90,
                "published_at": (now - timedelta(hours=14)).isoformat(),
                "category_id": "28",
                "region_code": region_code,
                "url": "https://www.youtube.com/watch?v=trendSingle",
                "thumbnail_url": "",
            }
        ][:max_results]


def _set_tmp_trend_store(app, tmp_path):
    app.state.trend_store_path = str(tmp_path / "trend_snapshots.json")
    return app.state.trend_store_path


def _set_tmp_training_pipeline(app, tmp_path):
    app.state.training_pipeline = TrainingPipeline(
        server_module.BACKEND_DIR,
        data_dir=str(tmp_path / "training_data"),
        registry_dir=str(tmp_path / "training_registry"),
    )
    return app.state.training_pipeline


def _write_previous_trend_snapshot(path, video_id, title, rank, views_per_hour):
    previous_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "version": 1,
                "videos": {
                    video_id: {
                        "id": video_id,
                        "title": title,
                        "channel_title": "Fixture",
                        "region_code": "US",
                        "category_id": "28",
                        "last_seen_at": previous_time,
                        "snapshots": [
                            {
                                "fetched_at": previous_time,
                                "rank": rank,
                                "views": int(views_per_hour * 8),
                                "likes": 4000,
                                "comments": 300,
                                "age_hours": 8,
                                "views_per_hour": views_per_hour,
                                "engagement_rate": 4.5,
                                "topic_cluster": "AI creator tools",
                                "category_id": "28",
                                "region_code": "US",
                                "source": "real_youtube",
                            }
                        ],
                    }
                },
            },
            handle,
        )


class FakeObsClient:
    def __init__(self, config=None, platform="windows", fail_on=None):
        self.config = config
        self.connected = False
        self.platform = platform
        self.fail_on = set(fail_on or [])
        self.calls = []
        self.closed = False
        self.version = {
            "obsVersion": "30.0.0",
            "obsWebSocketVersion": "5.3.1",
            "rpcVersion": 1,
            "platform": platform,
            "platformDescription": platform,
            "availableRequests": [
                "GetVersion",
                "GetStreamStatus",
                "GetRecordStatus",
                "GetReplayBufferStatus",
                "GetVirtualCamStatus",
                "GetCurrentProgramScene",
                "GetStudioModeEnabled",
                "GetSceneList",
                "GetSceneItemList",
                "GetCurrentPreviewScene",
                "SetCurrentProgramScene",
                "SetCurrentPreviewScene",
                "TriggerStudioModeTransition",
                "SetSceneItemEnabled",
                "SetSceneItemTransform",
                "SetSceneItemIndex",
                "CreateScene",
                "CreateInput",
                "SetInputSettings",
                "SetInputMute",
                "SetInputVolume",
                "SetInputAudioMonitorType",
                "StartStream",
                "StopStream",
                "StartRecord",
                "StopRecord",
                "PauseRecord",
                "ResumeRecord",
                "StartVirtualCam",
                "StopVirtualCam",
                "StartReplayBuffer",
                "StopReplayBuffer",
                "SaveReplayBuffer",
                "SetStreamServiceSettings",
                "GetInputKindList",
            ],
        }
        self.available_requests = set(self.version["availableRequests"])

    async def connect(self):
        if "connect" in self.fail_on:
            raise RuntimeError("auth failed")
        self.connected = True
        return self.version

    async def disconnect(self):
        self.connected = False
        self.closed = True
        return {"connected": False}

    async def request(self, request_type, request_data=None):
        self.calls.append((request_type, request_data or {}))
        if request_type in self.fail_on:
            raise RuntimeError(f"{request_type} failed")
        if request_type == "GetVersion":
            return self.version
        if request_type == "GetStreamStatus":
            return {"outputActive": False}
        if request_type == "GetRecordStatus":
            return {"outputActive": False, "outputPaused": False}
        if request_type == "GetReplayBufferStatus":
            return {"outputActive": False}
        if request_type == "GetVirtualCamStatus":
            return {"outputActive": False}
        if request_type == "GetCurrentProgramScene":
            return {"currentProgramSceneName": "Gameplay"}
        if request_type == "GetCurrentPreviewScene":
            return {"currentPreviewSceneName": "Starting Soon"}
        if request_type == "GetStudioModeEnabled":
            return {"studioModeEnabled": False}
        if request_type == "GetSceneList":
            return {"currentProgramSceneName": "Gameplay", "scenes": [{"sceneName": "Gameplay"}, {"sceneName": "Starting Soon"}]}
        if request_type == "GetSceneItemList":
            return {
                "sceneItems": [
                    {"sceneItemId": 1, "sourceName": "Camera", "sceneItemEnabled": True},
                    {"sceneItemId": 2, "sourceName": "Game Capture", "sceneItemEnabled": True},
                ]
            }
        if request_type == "GetInputKindList":
            kinds = ["browser_source"]
            if self.platform == "windows":
                kinds.append("text_gdiplus_v3")
            else:
                kinds.append("text_ft2_source")
            return {"inputKinds": kinds}
        return {"accepted": True}

    async def event_stream(self):
        yield {"eventType": "CurrentProgramSceneChanged", "eventData": {"sceneName": "Gameplay"}}
        yield {"eventType": "InputVolumeMeters", "eventData": {"inputs": [{"inputName": "Mic", "inputLevelsMul": [[0.2, 0.3]]}]}}


class FailingObsClient(FakeObsClient):
    async def connect(self):
        raise RuntimeError("bad password")


def _obs_app_with_fake(fake):
    app = create_app(test_mode=True)
    app.state.obs_client_factory = lambda config: fake
    return app


def test_simulate_endpoint_preserves_compatibility_fields():
    client = TestClient(create_app(test_mode=True))
    response = client.get(
        "/api/simulate",
        params={"uploads": 3, "ctr_boost": 1, "promo": 50, "collabs": 1, "seed": 9},
    )

    assert response.status_code == 200
    data = response.json()
    for key in ("current", "optimized", "lower", "upper", "final_subs"):
        assert key in data
    for key in ("current_lower", "current_upper", "baseline_final_subs", "gain", "pct_gain", "weeks", "seed"):
        assert key in data
    assert data["seed"] == 9
    assert len(data["current"]) == 24
    assert len(data["optimized"]) == 24


def test_predict_ctr_endpoint_uses_heuristic_fallback_in_test_mode():
    client = TestClient(create_app(test_mode=True))
    response = client.post("/api/predict-ctr", json={"topic": "Do NOT Buy This GPU Before Watching"})

    assert response.status_code == 200
    data = response.json()
    assert data["predicted_ctr"] > 0
    assert data["model_source"] == "heuristic"
    assert data["calibrated"] is True
    assert data["analysis"]["has_negative_hook"] is True


def test_predict_ctr_rejects_empty_title():
    client = TestClient(create_app(test_mode=True))
    response = client.post("/api/predict-ctr", json={"topic": "   "})

    assert response.status_code == 400


def test_ai_upload_requires_video_file():
    client = TestClient(create_app(test_mode=True))
    response = client.post("/api/ai-upload", data={"topic": "RTX 5090 review"})

    assert response.status_code == 422


def test_ai_upload_test_mode_returns_fake_public_upload():
    client = TestClient(create_app(test_mode=True))
    response = client.post(
        "/api/ai-upload",
        data={"topic": "RTX 5090 review", "made_for_kids": "false", "contains_synthetic_media": "false"},
        files={"video": ("review.mp4", BytesIO(b"fake video bytes"), "video/mp4")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["test_mode"] is True
    assert data["upload_id"]
    assert data["upload"]["status"] == "published"
    assert data["upload"]["privacy_status"] == "public"
    assert data["upload"]["watch_url"].startswith("https://www.youtube.com/watch?v=")
    assert len(data["upload"]["video_id"]) == 11
    assert data["validation"]["video"]["extension"] == ".mp4"
    assert data["quota"]["videos_insert"]["used_by_this_upload"] == 1
    assert data["quota"]["videos_insert"]["remaining_estimate"] == 99

    package = data["package"]
    for key in ("final_title", "description", "tags", "category_id", "upload_checklist"):
        assert package[key]
    assert len(package["titles"]) == 3
    assert package["publish_mode"] == "public"


def test_ai_upload_empty_topic_falls_back_to_filename():
    client = TestClient(create_app(test_mode=True))
    response = client.post(
        "/api/ai-upload",
        data={"topic": "   "},
        files={"video": ("budget-laptop-guide.mp4", BytesIO(b"video"), "video/mp4")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["package"]["topic"] == "Budget Laptop Guide"
    assert "Budget Laptop Guide" in data["package"]["final_title"]


def test_ai_upload_rejects_invalid_video_extension():
    client = TestClient(create_app(test_mode=True))
    response = client.post(
        "/api/ai-upload",
        data={"topic": "bad file"},
        files={"video": ("notes.txt", BytesIO(b"not a video"), "text/plain")},
    )

    assert response.status_code == 400
    assert "Unsupported video format" in response.json()["detail"]


def test_ai_upload_records_progress_for_upload_id():
    app = create_app(test_mode=True)
    client = TestClient(app)
    response = client.post(
        "/api/ai-upload",
        data={"topic": "progress test", "upload_id": "uploadProgress1"},
        files={"video": ("progress.mp4", BytesIO(b"video"), "video/mp4")},
    )

    assert response.status_code == 200
    progress = app.state.upload_progress["uploadProgress1"]
    assert progress["stage"] == "published"
    assert progress["progress"] == 100
    assert progress["terminal"] is True


def test_ai_upload_returns_structured_error_when_youtube_upload_fails(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = create_app(test_mode=False, agent_override=_TestAgent())

    class FailingYouTube:
        def upload_video(self, **kwargs):
            raise RuntimeError("quota exhausted")

    app.state.youtube_connection_factory = FailingYouTube
    client = TestClient(app)
    response = client.post(
        "/api/ai-upload",
        data={"topic": "GPU launch analysis"},
        files={"video": ("gpu.mp4", BytesIO(b"video"), "video/mp4")},
    )

    assert response.status_code == 502
    data = response.json()
    assert data["ok"] is False
    assert data["upload"]["status"] == "failed"
    assert "quota exhausted" in data["error"]
    assert data["package"]["final_title"]


def test_analyze_video_missing_ffmpeg_returns_setup_required(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(server_module.shutil, "which", lambda _: None)
    client = TestClient(create_app(test_mode=False, agent_override=_TestAgent()))
    response = client.post(
        "/api/analyze-video",
        data={"topic": "RTX 5090 review"},
        files={"video": ("review.mp4", BytesIO(b"video"), "video/mp4")},
    )

    assert response.status_code == 424
    data = response.json()
    assert data["ok"] is False
    assert data["setup_required"] is True
    assert "ffmpeg" in data["missing_tools"]


def test_analyze_video_missing_transcript_provider_returns_clear_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(server_module.shutil, "which", lambda name: name)
    monkeypatch.setattr(server_module, "_probe_media_metadata", lambda path, fallback: {**fallback, "duration_seconds": 30, "has_audio": True})
    monkeypatch.setattr(
        server_module,
        "_extract_first_30s_audio",
        lambda video_path, temp_dir: os.path.join(temp_dir, "first_30s.wav"),
    )
    client = TestClient(create_app(test_mode=False, agent_override=_TestAgent()))
    response = client.post(
        "/api/analyze-video",
        data={"topic": "RTX 5090 review"},
        files={"video": ("review.mp4", BytesIO(b"video"), "video/mp4")},
    )

    assert response.status_code == 424
    data = response.json()
    assert data["ok"] is False
    assert "OPENAI_API_KEY or GROQ_API_KEY" in data["provider_error"]


def test_analyze_video_weak_hook_requires_confirmation():
    client = TestClient(create_app(test_mode=True))
    response = client.post(
        "/api/analyze-video",
        data={"topic": "weak hook laptop review"},
        files={"video": ("weak-hook.mp4", BytesIO(b"video"), "video/mp4")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requires_confirmation"] is True
    assert data["hook_report"]["weak_hook"] is True
    assert data["fix_draft"]["safer_title"]


def test_ai_upload_high_risk_without_confirmation_does_not_publish():
    client = TestClient(create_app(test_mode=True))
    response = client.post(
        "/api/ai-upload",
        data={"topic": "casino scam violence fuck"},
        files={"video": ("risk.mp4", BytesIO(b"video"), "video/mp4")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["requires_confirmation"] is True
    assert data["upload"]["status"] == "blocked"
    assert data["risk_report"]["level"] == "high"


def test_ai_upload_high_risk_confirmed_publishes_and_records_override():
    client = TestClient(create_app(test_mode=True))
    response = client.post(
        "/api/ai-upload",
        data={"topic": "casino scam violence fuck", "confirm_risk": "true"},
        files={"video": ("risk.mp4", BytesIO(b"video"), "video/mp4")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["upload"]["status"] == "published"
    assert data["upload"]["risk_override"] is True
    assert data["analysis"]["risk_override_confirmed"] is True


def test_ai_upload_apply_fix_draft_uses_safer_metadata():
    client = TestClient(create_app(test_mode=True))
    response = client.post(
        "/api/ai-upload",
        data={"topic": "casino scam violence fuck", "apply_fix_draft": "true"},
        files={"video": ("risk.mp4", BytesIO(b"video"), "video/mp4")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["upload"]["fix_draft_applied"] is True
    assert "sensitive topic" in data["package"]["final_title"].lower()
    assert "Auto Fix Draft applied" in data["package"]["warnings"][0]


def test_war_room_test_mode_returns_metrics_alerts_and_reply_drafts():
    client = TestClient(create_app(test_mode=True))
    response = client.get("/api/war-room/fakeVideo123")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["metrics"]["views"] > 0
    assert data["alert_cards"]
    assert any(alert["type"] == "low_ctr" for alert in data["alert_cards"])
    assert data["ai_reply_drafts"]
    assert data["recommended_intervention"]


def test_train_ai_returns_local_training_state():
    client = TestClient(create_app(test_mode=True))
    response = client.post("/api/train-ai")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["trained_samples"] >= 1
    assert data["channel_baselines"]["baseline_24h_views"] > 0
    assert data["prediction_weights"]["early_velocity"] > 0


def test_training_collect_local_writes_dataset_and_status(tmp_path):
    app = create_app(test_mode=True)
    _set_tmp_training_pipeline(app, tmp_path)
    client = TestClient(app)

    response = client.post("/api/training/collect")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "local"
    assert data["snapshot_rows"] >= 1
    assert data["labels_ready"] >= 1

    status = client.get("/api/training/status").json()
    assert status["dataset"]["snapshot_rows"] == data["snapshot_rows"]
    assert "Temporal Backtest" in status["badges"]


def test_training_collect_mixed_adds_platform_trend_rows(tmp_path):
    app = create_app(test_mode=True)
    _set_tmp_training_pipeline(app, tmp_path)
    _set_tmp_trend_store(app, tmp_path)
    client = TestClient(app)

    response = client.post("/api/training/collect", params={"scope": "mixed", "region_code": "US"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["scope"] == "mixed"
    assert data["fetched_counts"]["channel_videos"] >= 1
    assert data["fetched_counts"]["platform_trends"] >= 1
    assert data["snapshot_rows"] == data["fetched_counts"]["total"]


def test_training_collect_real_uses_read_only_youtube_without_fake_fallback(tmp_path):
    app = create_app(test_mode=True)
    app.state.youtube_connection_factory = FakeReadOnlyYouTube
    _set_tmp_training_pipeline(app, tmp_path)
    client = TestClient(app)

    response = client.post("/api/training/collect", params={"source": "real"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "real_youtube"
    assert data["fake_fallback_used"] is False
    assert data["input_rows"] == 2
    assert data["snapshot_rows"] == 2


def test_training_collect_real_failure_returns_structured_error(tmp_path):
    class FailingYouTube:
        def get_recent_channel_videos(self, max_results=50):
            raise RuntimeError("quota exhausted")

    app = create_app(test_mode=True)
    app.state.youtube_connection_factory = FailingYouTube
    _set_tmp_training_pipeline(app, tmp_path)
    client = TestClient(app)

    response = client.post("/api/training/collect", params={"source": "real"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["source"] == "real_youtube"
    assert data["fake_fallback_used"] is False
    assert data["rows"] == []
    assert data["error_category"]


def test_training_retrain_api_returns_job_id_immediately(tmp_path):
    app = create_app(test_mode=True)
    _set_tmp_training_pipeline(app, tmp_path)
    client = TestClient(app)
    client.post("/api/training/collect")

    response = client.post("/api/training/retrain")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["status"] == "queued"
    assert data["job_id"]

    job = client.get(f"/api/training/jobs/{data['job_id']}").json()
    assert job["ok"] is True
    assert job["status"] in {"queued", "running", "completed", "failed"}


def test_realtime_predict_returns_forecast_from_war_room_metrics():
    client = TestClient(create_app(test_mode=True))
    response = client.get("/api/realtime-predict/fakeVideo123")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["forecast"]["next_24h_views"] >= data["current_metrics"]["views"]
    assert 0 <= data["forecast"]["virality_probability"] <= 1
    assert data["signals"]["early_velocity_views_per_hour"] > 0
    assert data["trend_prediction"]["status"] in {"will_trend_soon", "watchlist", "cooling", "low_probability"}
    assert "recommended_action" in data["trend_prediction"]


def test_trending_videos_test_mode_returns_analyzed_opportunities(tmp_path):
    app = create_app(test_mode=True)
    _set_tmp_trend_store(app, tmp_path)
    client = TestClient(app)
    response = client.get("/api/trending-videos", params={"region_code": "US", "max_results": 5})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["mode"] == "test"
    assert len(data["videos"]) == 5
    assert data["videos"][0]["opportunity_score"] >= data["videos"][-1]["opportunity_score"]
    assert data["trend_summary"]["top_cluster"]
    assert data["next_actions"]
    first = data["videos"][0]
    assert first["trend_prediction"]["status"] in {"will_trend_soon", "watchlist", "cooling", "low_probability"}
    assert first["youtube_trend_score"] == first["trend_prediction"]["signals"]["youtube_trend_score"]
    assert first["creator_opportunity_score"] == first["trend_prediction"]["signals"]["creator_opportunity_score"]
    assert first["history_available"] is False


def test_trending_prediction_rising_history_returns_will_trend_soon(tmp_path):
    app = create_app(test_mode=True)
    app.state.youtube_connection_factory = RisingTrendYouTube
    trend_path = _set_tmp_trend_store(app, tmp_path)
    _write_previous_trend_snapshot(
        trend_path,
        "trendRise",
        "AI Video Editing Explosion Is Happening Now",
        rank=3,
        views_per_hour=60000,
    )
    client = TestClient(app)
    response = client.get("/api/trending-videos", params={"source": "real", "region_code": "US", "max_results": 2})

    assert response.status_code == 200
    data = response.json()
    target = next(video for video in data["videos"] if video["id"] == "trendRise")
    prediction = target["trend_prediction"]
    assert prediction["will_trend_soon"] is True
    assert prediction["status"] == "will_trend_soon"
    assert prediction["score"] >= 78
    assert prediction["signals"]["history_available"] is True
    assert prediction["signals"]["acceleration_pct"] > 0


def test_trending_prediction_cooling_history_does_not_mark_will_trend_soon(tmp_path):
    app = create_app(test_mode=True)
    app.state.youtube_connection_factory = CoolingTrendYouTube
    trend_path = _set_tmp_trend_store(app, tmp_path)
    _write_previous_trend_snapshot(
        trend_path,
        "trendCool",
        "AI Editing Trend Is Slowing Down",
        rank=1,
        views_per_hour=90000,
    )
    client = TestClient(app)
    response = client.get("/api/trending-videos", params={"source": "real", "region_code": "US", "max_results": 4})

    assert response.status_code == 200
    data = response.json()
    target = next(video for video in data["videos"] if video["id"] == "trendCool")
    prediction = target["trend_prediction"]
    assert prediction["will_trend_soon"] is False
    assert prediction["status"] in {"cooling", "watchlist"}
    assert prediction["signals"]["history_available"] is True
    assert prediction["signals"]["acceleration_pct"] < 0


def test_trending_prediction_single_scan_has_low_confidence(tmp_path):
    app = create_app(test_mode=True)
    app.state.youtube_connection_factory = ModerateTrendYouTube
    _set_tmp_trend_store(app, tmp_path)
    client = TestClient(app)
    response = client.get("/api/trending-videos", params={"source": "real", "region_code": "US", "max_results": 1})

    assert response.status_code == 200
    data = response.json()
    prediction = data["videos"][0]["trend_prediction"]
    assert prediction["signals"]["history_available"] is False
    assert prediction["signals"]["snapshots_seen"] == 1
    assert prediction["confidence"] == "low"
    assert prediction["will_trend_soon"] is False


def test_train_ai_real_source_uses_read_only_youtube_data():
    app = create_app(test_mode=True)
    app.state.youtube_connection_factory = FakeReadOnlyYouTube
    client = TestClient(app)
    response = client.post("/api/train-ai", params={"source": "real"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "real_youtube"
    assert data["fake_fallback_used"] is False
    assert data["trained_samples"] == 2
    assert data["fetched_counts"]["videos"] == 2
    assert data["analytics_available"] is True


def test_realtime_predict_real_source_combines_stats_analytics_and_comments():
    app = create_app(test_mode=True)
    app.state.youtube_connection_factory = FakeReadOnlyYouTube
    client = TestClient(app)
    response = client.get("/api/realtime-predict/realVid001", params={"source": "real", "refresh": "true"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "real_youtube"
    assert data["fake_fallback_used"] is False
    assert data["current_metrics"]["views"] == 12000
    assert data["data_freshness"]["analytics_available"] is True
    assert data["data_freshness"]["comments_available"] is True
    assert data["war_room"]["first_comments"]
    assert data["trend_prediction"]["status"] in {"will_trend_soon", "watchlist", "cooling", "low_probability"}
    assert data["trend_prediction"]["signals"]["analytics_available"] is True


def test_trending_videos_real_source_does_not_use_fake_fallback(tmp_path):
    app = create_app(test_mode=True)
    app.state.youtube_connection_factory = FakeReadOnlyYouTube
    _set_tmp_trend_store(app, tmp_path)
    client = TestClient(app)
    response = client.get("/api/trending-videos", params={"source": "real", "region_code": "US", "max_results": 1})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "real_youtube"
    assert data["fake_fallback_used"] is False
    assert data["videos"][0]["id"] == "trendReal1"
    assert data["videos"][0]["trend_prediction"]["signals"]["history_available"] is False


def test_trending_videos_real_source_returns_structured_error_without_fallback():
    class FailingRealYouTube:
        def get_trending_videos(self, **kwargs):
            raise RuntimeError("quota exhausted")

    app = create_app(test_mode=True)
    app.state.youtube_connection_factory = FailingRealYouTube
    client = TestClient(app)
    response = client.get("/api/trending-videos", params={"source": "real", "region_code": "US"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["source"] == "real_youtube"
    assert data["error_category"] == "quota_error"
    assert data["fake_fallback_used"] is False
    assert data["videos"] == []
    assert data["trend_predictions"] == []


def test_real_youtube_auth_errors_include_setup_action():
    data = server_module._real_youtube_error("trending_videos", RuntimeError("invalid_grant"))

    assert data["ok"] is False
    assert data["error_category"] == "auth_error"
    assert "YOUTUBE_API_KEY" in data["auth_action"]
    assert "backend/token.pickle" in data["auth_action"]


def test_obs_status_returns_disconnected_without_obs():
    client = TestClient(create_app(test_mode=True))
    response = client.get("/api/obs/status")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["connected"] is False


def test_obs_connect_success_and_disconnect_closes_client():
    fake = FakeObsClient()
    app = _obs_app_with_fake(fake)
    client = TestClient(app)

    response = client.post("/api/obs/connect", json={"host": "127.0.0.1", "port": 4455})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["connected"] is True
    assert data["version"]["obs_websocket_version"] == "5.3.1"

    response = client.post("/api/obs/disconnect")
    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert fake.closed is True


def test_obs_connect_auth_failure_returns_json_error():
    app = _obs_app_with_fake(FailingObsClient())
    client = TestClient(app)
    response = client.post("/api/obs/connect", json={"password": "wrong"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["context"] == "connect"
    assert "bad password" in data["error"]


def test_obs_scenes_returns_scene_items():
    app = _obs_app_with_fake(FakeObsClient())
    client = TestClient(app)
    client.post("/api/obs/connect", json={})

    response = client.get("/api/obs/scenes")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["current_program_scene"] == "Gameplay"
    assert data["scenes"][0]["items"][0]["sourceName"] == "Camera"


def test_obs_events_sse_emits_scene_and_audio_meter_events():
    app = _obs_app_with_fake(FakeObsClient())
    client = TestClient(app)
    client.post("/api/obs/connect", json={})

    response = client.get("/api/obs/events")
    assert response.status_code == 200
    text = response.text
    assert "CurrentProgramSceneChanged" in text
    assert "InputVolumeMeters" in text


def test_obs_safe_action_executes_without_confirmation():
    fake = FakeObsClient()
    app = _obs_app_with_fake(fake)
    client = TestClient(app)
    client.post("/api/obs/connect", json={})

    response = client.post(
        "/api/obs/action",
        json={"action": "set_scene_item_index", "params": {"sceneName": "Gameplay", "sceneItemId": 2, "sceneItemIndex": 0}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["request_type"] == "SetSceneItemIndex"
    assert fake.calls[-1][0] == "SetSceneItemIndex"


def test_obs_dangerous_action_requires_confirmation_and_then_executes():
    fake = FakeObsClient()
    app = _obs_app_with_fake(fake)
    client = TestClient(app)
    client.post("/api/obs/connect", json={})

    response = client.post("/api/obs/action", json={"action": "start_stream", "params": {}})
    data = response.json()
    assert data["ok"] is False
    assert data["requires_confirmation"] is True
    assert all(call[0] != "StartStream" for call in fake.calls)

    response = client.post("/api/obs/action", json={"action": "start_stream", "params": {}, "confirm": True})
    assert response.json()["request_type"] == "StartStream"


def test_obs_stream_settings_maps_to_set_stream_service_settings():
    fake = FakeObsClient()
    app = _obs_app_with_fake(fake)
    client = TestClient(app)
    client.post("/api/obs/connect", json={})

    response = client.post(
        "/api/obs/action",
        json={
            "action": "set_stream_service_settings",
            "confirm": True,
            "params": {"streamServiceSettings": {"server": "rtmp://example", "key": "secret"}},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["request_type"] == "SetStreamServiceSettings"


def test_obs_set_bitrate_is_not_supported_action():
    app = _obs_app_with_fake(FakeObsClient())
    client = TestClient(app)
    client.post("/api/obs/connect", json={})

    response = client.post("/api/obs/action", json={"action": "set_bitrate", "params": {"bitrate": 8000}, "confirm": True})
    data = response.json()
    assert data["ok"] is False
    assert data["error_category"] == "unsupported_action"


def test_obs_autopilot_uses_platform_text_kind_and_reports_partial_failure():
    fake = FakeObsClient(platform="windows", fail_on={"CreateInput"})
    app = _obs_app_with_fake(fake)
    client = TestClient(app)
    client.post("/api/obs/connect", json={})

    response = client.post("/api/obs/autopilot-setup", json={"topic": "God of War"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["partial_success"] is True
    assert data["applied_actions"]
    assert data["failed_actions"]
    assert any(action["params"].get("inputKind") == "text_gdiplus_v3" for action in data["planned_actions"] if action["action"] == "create_input")
    assert data["manual_cleanup_notes"]


def test_obs_autopilot_uses_linux_text_source_kind():
    fake = FakeObsClient(platform="linux")
    app = _obs_app_with_fake(fake)
    client = TestClient(app)
    client.post("/api/obs/connect", json={})

    response = client.post("/api/obs/autopilot-setup", json={"topic": "Just Chatting"})
    data = response.json()
    assert data["ok"] is True
    assert any(action["params"].get("inputKind") == "text_ft2_source" for action in data["planned_actions"] if action["action"] == "create_input")


real_youtube_enabled = os.getenv("STREAMPILOT_REAL_YOUTUBE_TESTS") == "1"
real_video_id = os.getenv("STREAMPILOT_REAL_TEST_VIDEO_ID", "").strip()


@pytest.mark.real_youtube
@pytest.mark.skipif(not real_youtube_enabled, reason="Set STREAMPILOT_REAL_YOUTUBE_TESTS=1 to call real YouTube APIs.")
def test_real_youtube_training_fetches_channel_history():
    client = TestClient(create_app(test_mode=False, agent_override=_TestAgent()))
    response = client.post("/api/train-ai", params={"source": "real"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "real_youtube"
    assert data["fake_fallback_used"] is False
    assert data["fetched_counts"]["videos"] >= 1


@pytest.mark.real_youtube
@pytest.mark.skipif(
    not real_youtube_enabled or not real_video_id,
    reason="Set STREAMPILOT_REAL_YOUTUBE_TESTS=1 and STREAMPILOT_REAL_TEST_VIDEO_ID.",
)
def test_real_youtube_realtime_prediction_reads_real_video_data():
    client = TestClient(create_app(test_mode=False, agent_override=_TestAgent()))
    response = client.get(
        f"/api/realtime-predict/{real_video_id}",
        params={"source": "real", "refresh": "true"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "real_youtube"
    assert data["fake_fallback_used"] is False
    assert data["current_metrics"]["views"] >= 0
    assert "analytics_available" in data["data_freshness"]
    assert "comments_available" in data["data_freshness"]


@pytest.mark.real_youtube
@pytest.mark.skipif(not real_youtube_enabled, reason="Set STREAMPILOT_REAL_YOUTUBE_TESTS=1 to call real YouTube APIs.")
def test_real_youtube_trending_scan_returns_real_most_popular_videos(tmp_path):
    app = create_app(test_mode=False, agent_override=_TestAgent())
    _set_tmp_trend_store(app, tmp_path)
    client = TestClient(app)
    response = client.get("/api/trending-videos", params={"source": "real", "region_code": "US", "max_results": 5})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "real_youtube"
    assert data["fake_fallback_used"] is False
    assert len(data["videos"]) >= 1
    assert "trend_prediction" in data["videos"][0]
