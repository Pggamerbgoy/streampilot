import os
import sys
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


os.environ["STREAMPILOT_TEST_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import create_app  # noqa: E402
from training_pipeline import TrainingPipeline, derive_labels  # noqa: E402


def _row(index, views=1000, ctr=5.0, avd=60, days_old=10, trend_score=65):
    now = datetime.now(timezone.utc)
    published = now - timedelta(days=days_old + index)
    day_views = max(int(views * 0.35), 1)
    rows = [
        {"day": (published + timedelta(days=offset)).date().isoformat(), "views": max(day_views - offset * 10, 1)}
        for offset in range(7)
    ]
    return {
        "video_id": f"vid-{index:03d}",
        "title": f"AI Creator Tool Test {index}",
        "published_at": published.isoformat(),
        "category_id": "28",
        "views": views,
        "likes": int(views * 0.06),
        "comments": int(views * 0.01),
        "analytics": {
            "rows": rows,
            "totals": {
                "views": views,
                "impressions": max(int(views / max(ctr / 100.0, 0.01)), 100),
                "ctr": ctr,
                "average_view_duration_seconds": avd,
                "watch_time_minutes": int(views * avd / 60),
            },
            "analytics_available": True,
        },
        "trend": {
            "trend_prediction": {
                "score": trend_score,
                "signals": {"channel_fit_score": 80, "rank_movement": index % 4},
            }
        },
    }


def _training_app(tmp_path):
    app = create_app(test_mode=True)
    app.state.training_pipeline = TrainingPipeline(
        os.path.dirname(os.path.abspath(__file__)),
        data_dir=str(tmp_path / "training_data"),
        registry_dir=str(tmp_path / "registry"),
    )
    return app


def _wait_job(client, job_id, timeout=10):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/training/jobs/{job_id}").json()
        if last.get("status") in {"completed", "failed"}:
            return last
        time.sleep(0.15)
    return last


def test_training_labels_keep_ctr_pending_without_impressions():
    row = _row(1)
    row["analytics"]["totals"].pop("impressions")
    row["analytics"]["totals"].pop("ctr")

    label = derive_labels([row])[0]

    assert label["labels"]["ctr_label"]["status"] == "pending"


def test_training_breakout_label_uses_channel_threshold():
    rows = [_row(i, views=1000 + i * 20, days_old=12) for i in range(12)]
    rows.append(_row(99, views=20000, days_old=12))

    labels = derive_labels(rows)
    breakout = next(label for label in labels if label["video_id"] == "vid-099")

    assert breakout["labels"]["breakout_label"]["status"] == "ready"
    assert breakout["labels"]["breakout_label"]["value"] == 1


def test_training_retention_ambiguous_band_is_not_training_ready():
    rows = [_row(i, avd=100, days_old=12) for i in range(8)]
    target = _row(90, avd=78, days_old=12)
    rows.append(target)

    label = next(item for item in derive_labels(rows) if item["video_id"] == "vid-090")

    assert label["labels"]["retention_risk_label"]["status"] == "ambiguous"
    assert label["training_eligible"]["retention_risk"] is False


def test_training_24h_and_7d_labels_wait_for_video_age():
    fresh = _row(0, days_old=0)

    label = derive_labels([fresh])[0]

    assert label["labels"]["views_24h_label"]["status"] == "pending"
    assert label["labels"]["views_7d_label"]["status"] == "pending"


def test_training_collect_dedups_rows(tmp_path):
    pipeline = TrainingPipeline(os.path.dirname(os.path.abspath(__file__)), data_dir=str(tmp_path / "data"), registry_dir=str(tmp_path / "registry"))
    row = _row(1)
    row["captured_at"] = datetime.now(timezone.utc).replace(minute=3, second=0, microsecond=0).isoformat()

    first = pipeline.collect_rows([row], source="local")
    second = pipeline.collect_rows([{**row, "views": 9999}], source="local")

    assert first["snapshot_rows"] == 1
    assert second["snapshot_rows"] == 1
    assert second["updated_rows"] == 1


def test_training_retrain_returns_job_id_immediately_and_shadow_under_min_samples(tmp_path):
    app = _training_app(tmp_path)
    client = TestClient(app)
    app.state.training_pipeline.collect_rows([_row(i) for i in range(6)], source="local")

    response = client.post("/api/training/retrain")
    data = response.json()
    assert data["status"] == "queued"

    job = _wait_job(client, data["job_id"])
    assert job["status"] == "completed"
    assert job["promotion_decision"]["shadow_mode"] is True
    assert "Needs at least 20 labeled samples" in " ".join(job["promotion_decision"]["reasons"])


def test_training_temporal_candidate_promotes_over_weak_champion(tmp_path):
    app = _training_app(tmp_path)
    client = TestClient(app)
    rows = [
        _row(i, views=1500 + i * 120, ctr=4.0 + (i % 5), avd=42 if i % 6 == 0 else 80, trend_score=45 + (i % 10) * 5)
        for i in range(50)
    ]
    app.state.training_pipeline.collect_rows(rows, source="local")
    app.state.training_pipeline._write_manifest(
        {
            "version": 1,
            "champion": {"version": "weak", "metrics": {"composite_score": 0.1, "task_scores": {"ctr": 0.1}}},
            "candidates": [],
        }
    )

    data = client.post("/api/training/retrain").json()
    job = _wait_job(client, data["job_id"], timeout=15)

    assert job["status"] == "completed"
    assert job["promotion_decision"]["auto_promoted"] is True
    status = client.get("/api/training/status").json()
    assert status["champion"]["version"] == job["candidate_version"]


def test_training_predict_ctr_uses_pre_upload_champion_schema(tmp_path):
    app = _training_app(tmp_path)
    client = TestClient(app)
    rows = [_row(i, views=2000 + i * 80, ctr=3.5 + (i % 8), avd=80, trend_score=70) for i in range(50)]
    app.state.training_pipeline.collect_rows(rows, source="local")
    job_id = client.post("/api/training/retrain").json()["job_id"]
    job = _wait_job(client, job_id, timeout=15)
    assert job["status"] == "completed"

    response = client.post("/api/predict-ctr", json={"topic": "Do NOT Buy This AI Camera Yet"})
    data = response.json()

    assert data["training_champion_active"] is True
    assert data["feature_schema"] == "pre_upload_features"
    assert data["model_source"] == "champion_ctr_model"
