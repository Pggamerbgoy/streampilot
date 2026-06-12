import json
import math
import os
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import f1_score, mean_absolute_error, roc_auc_score


LABEL_VERSION = 1
MAX_SNAPSHOT_ROWS = 10000
RETENTION_DAYS = 180
MIN_PROMOTION_SAMPLES = 20
MIN_EVAL_SAMPLES = 8

TASK_WEIGHTS = {
    "ctr": 0.20,
    "views_24h": 0.25,
    "views_7d": 0.15,
    "breakout": 0.20,
    "retention_risk": 0.10,
    "trend_opportunity": 0.10,
}

PRE_UPLOAD_FEATURES = [
    "title_length",
    "caps_ratio",
    "has_power_word",
    "has_negative_hook",
    "topic_cluster_id",
    "category_id_num",
    "publish_hour",
    "description_length",
    "tag_count",
    "contains_synthetic_media",
    "hook_score",
    "brand_risk_score",
    "trend_fit",
]

POST_PUBLISH_FEATURES = PRE_UPLOAD_FEATURES + [
    "elapsed_hours",
    "views_per_hour",
    "likes_per_view",
    "comments_per_view",
    "ctr",
    "impressions",
    "average_view_duration_seconds",
    "watch_time_minutes",
    "trend_rank_movement",
]

TASK_CONFIG = {
    "ctr": {"kind": "regressor", "target": "ctr_label", "features": PRE_UPLOAD_FEATURES},
    "views_24h": {"kind": "regressor", "target": "views_24h_label", "features": POST_PUBLISH_FEATURES},
    "views_7d": {"kind": "regressor", "target": "views_7d_label", "features": POST_PUBLISH_FEATURES},
    "breakout": {"kind": "classifier", "target": "breakout_label", "features": POST_PUBLISH_FEATURES},
    "retention_risk": {"kind": "classifier", "target": "retention_risk_label", "features": POST_PUBLISH_FEATURES},
    "trend_opportunity": {"kind": "regressor", "target": "trend_opportunity_label", "features": POST_PUBLISH_FEATURES},
}

POWER_WORDS = {"ultimate", "destroy", "secret", "truth", "insane", "best", "worst", "cheap", "budget", "hidden", "new"}
NEGATIVE_HOOKS = {"don't", "dont", "stop", "regret", "never", "hate", "scam", "mistake", "avoid", "wrong"}
CLUSTER_IDS = {
    "AI creator tools": 1,
    "tech and gear": 2,
    "creator growth": 3,
    "gaming": 4,
    "general trend": 5,
}


class TrainingPipeline:
    def __init__(self, backend_dir: str, data_dir: Optional[str] = None, registry_dir: Optional[str] = None):
        self.backend_dir = backend_dir
        self.data_dir = data_dir or os.path.join(backend_dir, ".training_data")
        self.snapshots_path = os.path.join(self.data_dir, "video_snapshots.jsonl")
        self.labels_path = os.path.join(self.data_dir, "video_labels.jsonl")
        self.jobs_path = os.path.join(self.data_dir, "training_jobs.json")
        self.registry_dir = registry_dir or os.path.join(backend_dir, "models", "registry")
        self.manifest_path = os.path.join(self.registry_dir, "manifest.json")
        self._lock = threading.RLock()
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.registry_dir, exist_ok=True)

    def collect_rows(self, rows: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
        now = _utc_now()
        normalized = [_normalize_snapshot(row, source, now) for row in rows]
        existing = _read_jsonl(self.snapshots_path)
        by_key = {_snapshot_key(row): row for row in existing}
        written = 0
        updated = 0
        for row in normalized:
            key = _snapshot_key(row)
            if key in by_key:
                updated += 1
            else:
                written += 1
            by_key[key] = row
        retained = _apply_snapshot_retention(list(by_key.values()))
        _write_jsonl(self.snapshots_path, retained)
        labels = derive_labels(retained)
        _write_jsonl(self.labels_path, labels)
        return {
            "ok": True,
            "source": source,
            "fake_fallback_used": False if source == "real_youtube" else None,
            "collected_at": now,
            "input_rows": len(rows),
            "written_rows": written,
            "updated_rows": updated,
            "snapshot_rows": len(retained),
            "labels_ready": _count_ready_labels(labels),
            "labels_pending": _count_pending_labels(labels),
            "label_version": LABEL_VERSION,
        }

    def status(self) -> Dict[str, Any]:
        snapshots = _read_jsonl(self.snapshots_path)
        labels = _read_jsonl(self.labels_path)
        jobs = self._read_jobs()
        manifest = self._read_manifest()
        champion = manifest.get("champion")
        latest_candidate = (manifest.get("candidates") or [])[-1] if manifest.get("candidates") else None
        return {
            "ok": True,
            "dataset": {
                "snapshot_rows": len(snapshots),
                "video_count": len({row.get("video_id") for row in snapshots if row.get("video_id")}),
                "labels_ready": _count_ready_labels(labels),
                "labels_pending": _count_pending_labels(labels),
                "latest_collection_time": max([row.get("captured_at", "") for row in snapshots] or [""]),
            },
            "champion": champion,
            "latest_candidate": latest_candidate,
            "jobs": sorted(jobs.values(), key=lambda item: item.get("created_at", ""), reverse=True)[:8],
            "badges": _training_badges(champion, labels, latest_candidate),
            "feature_schema": {"pre_upload_features": PRE_UPLOAD_FEATURES, "post_publish_features": POST_PUBLISH_FEATURES},
        }

    def start_retrain(self) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "status": "queued",
            "phase": "queued",
            "progress": 0,
            "created_at": _utc_now(),
        }
        self._save_job(job)
        thread = threading.Thread(target=self._run_retrain_job, args=(job_id,), daemon=True)
        thread.start()
        return {"ok": True, "job_id": job_id, "status": "queued"}

    def get_job(self, job_id: str) -> Dict[str, Any]:
        job = self._read_jobs().get(job_id)
        if not job:
            return {"ok": False, "error": "training job not found", "job_id": job_id}
        return {"ok": True, **job}

    def evaluation(self) -> Dict[str, Any]:
        manifest = self._read_manifest()
        candidate = (manifest.get("candidates") or [])[-1] if manifest.get("candidates") else None
        return {
            "ok": True,
            "champion": manifest.get("champion"),
            "latest_candidate": candidate,
            "promotion_decision": candidate.get("promotion_decision") if candidate else None,
        }

    def promote(self, candidate_version: Optional[str] = None, manual_override: bool = True) -> Dict[str, Any]:
        manifest = self._read_manifest()
        candidates = manifest.get("candidates") or []
        candidate = None
        for item in candidates:
            if candidate_version is None or item.get("version") == candidate_version:
                candidate = item
        if not candidate:
            return {"ok": False, "error": "candidate model not found"}
        candidate = {**candidate, "manual_override": manual_override, "promoted_at": _utc_now()}
        manifest["champion"] = candidate
        self._write_manifest(manifest)
        return {"ok": True, "champion": candidate}

    def predict_ctr(self, title: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        manifest = self._read_manifest()
        champion = manifest.get("champion") or {}
        model_paths = champion.get("model_paths") or {}
        ctr_path = model_paths.get("ctr")
        if not ctr_path or not os.path.exists(ctr_path):
            return {**fallback, "training_champion_active": False}
        try:
            model = joblib.load(ctr_path)
            features = _feature_vector(_feature_row({"title": title}), PRE_UPLOAD_FEATURES).reshape(1, -1)
            prediction = float(model.predict(features)[0])
            return {
                **fallback,
                "predicted_ctr": round(float(np.clip(prediction, 0.1, 25.0)), 2),
                "model_source": "champion_ctr_model",
                "training_champion_active": True,
                "champion_version": champion.get("version"),
                "feature_schema": "pre_upload_features",
            }
        except Exception as exc:
            return {**fallback, "training_champion_active": False, "champion_error": str(exc)}

    def _run_retrain_job(self, job_id: str) -> None:
        try:
            self._save_job({"job_id": job_id, "status": "running", "phase": "loading data", "progress": 10})
            snapshots = _read_jsonl(self.snapshots_path)
            labels = _read_jsonl(self.labels_path)
            manifest = self._read_manifest()
            self._save_job({"job_id": job_id, "status": "running", "phase": "building temporal split", "progress": 25})
            result = train_candidate_models(snapshots, labels, self.registry_dir, manifest)
            self._save_job({"job_id": job_id, "status": "running", "phase": "evaluating candidate", "progress": 80})
            manifest = self._record_candidate(result)
            completed = {
                "job_id": job_id,
                "status": "completed",
                "phase": "completed",
                "progress": 100,
                "completed_at": _utc_now(),
                "candidate_version": result.get("version"),
                "candidate_model_path": result.get("candidate_dir"),
                "evaluation_summary": result.get("evaluation"),
                "promotion_decision": result.get("promotion_decision"),
            }
            if result.get("promotion_decision", {}).get("auto_promoted"):
                completed["champion"] = manifest.get("champion")
            self._save_job(completed)
        except Exception as exc:
            self._save_job({"job_id": job_id, "status": "failed", "phase": "failed", "progress": 100, "error": str(exc), "completed_at": _utc_now()})

    def _record_candidate(self, result: Dict[str, Any]) -> Dict[str, Any]:
        manifest = self._read_manifest()
        candidates = manifest.get("candidates") or []
        candidate = {
            "version": result.get("version"),
            "created_at": result.get("created_at"),
            "candidate_dir": result.get("candidate_dir"),
            "model_paths": result.get("model_paths", {}),
            "metrics": result.get("evaluation", {}),
            "promotion_decision": result.get("promotion_decision", {}),
            "feature_schema": {"pre_upload_features": PRE_UPLOAD_FEATURES, "post_publish_features": POST_PUBLISH_FEATURES},
            "sample_counts": result.get("sample_counts", {}),
        }
        candidates.append(candidate)
        manifest["candidates"] = candidates[-5:]
        if result.get("promotion_decision", {}).get("auto_promoted"):
            manifest["champion"] = {**candidate, "promoted_at": _utc_now(), "manual_override": False}
        self._write_manifest(manifest)
        _prune_candidate_dirs(self.registry_dir, manifest)
        return manifest

    def _read_jobs(self) -> Dict[str, Any]:
        if not os.path.exists(self.jobs_path):
            return {}
        with open(self.jobs_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}

    def _save_job(self, update: Dict[str, Any]) -> None:
        with self._lock:
            jobs = self._read_jobs()
            job_id = update["job_id"]
            existing = jobs.get(job_id, {})
            jobs[job_id] = {**existing, **update, "updated_at": _utc_now()}
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.jobs_path, "w", encoding="utf-8") as handle:
                json.dump(jobs, handle, indent=2)

    def _read_manifest(self) -> Dict[str, Any]:
        if not os.path.exists(self.manifest_path):
            return {"version": 1, "champion": None, "candidates": []}
        with open(self.manifest_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            data.setdefault("version", 1)
            data.setdefault("candidates", [])
            return data

    def _write_manifest(self, manifest: Dict[str, Any]) -> None:
        os.makedirs(self.registry_dir, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)


def derive_labels(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    partials = [_initial_label(row) for row in rows]
    views_24h = [_label_value(item, "views_24h_label") for item in partials if _label_ready(item, "views_24h_label")]
    avds = [_analytics_total(row, "average_view_duration_seconds") for row in rows if _analytics_total(row, "average_view_duration_seconds")]
    ctrs = [_label_value(item, "ctr_label") for item in partials if _label_ready(item, "ctr_label")]
    median_24h = _percentile(views_24h, 50) or 1000.0
    p75_24h = _percentile(views_24h, 75) or median_24h * 1.4
    p80_velocity = _percentile([value / 24.0 for value in views_24h], 80) or median_24h / 24.0
    baseline_avd = _percentile(avds, 50) or 58.0

    final = []
    by_video: Dict[str, Dict[str, Any]] = {}
    for row, label in zip(rows, partials):
        labels = label["labels"]
        if _label_ready(label, "ctr_label"):
            labels["ctr_label"]["ctr_percentile_channel"] = _percentile_rank(float(labels["ctr_label"]["value"]), ctrs)
        if _label_ready(label, "views_24h_label"):
            views = float(labels["views_24h_label"]["value"])
            velocity = views / 24.0
            threshold = max(median_24h * 2.0, p75_24h)
            labels["breakout_label"] = {"status": "ready", "value": int(views >= threshold or velocity >= p80_velocity), "threshold": round(threshold, 2)}
        else:
            labels["breakout_label"] = {"status": "pending", "reason": "24h label missing"}

        avd = _analytics_total(row, "average_view_duration_seconds")
        avg_pct = _analytics_total(row, "average_percentage_viewed")
        if avd is None and avg_pct is None:
            labels["retention_risk_label"] = {"status": "pending", "reason": "retention analytics unavailable"}
        elif (avd is not None and avd < baseline_avd * 0.70) or (avg_pct is not None and avg_pct < 35):
            labels["retention_risk_label"] = {"status": "ready", "value": 1, "baseline_avd_seconds": round(baseline_avd, 2)}
        elif avd is not None and avd >= baseline_avd * 0.85:
            labels["retention_risk_label"] = {"status": "ready", "value": 0, "baseline_avd_seconds": round(baseline_avd, 2)}
        else:
            labels["retention_risk_label"] = {"status": "ambiguous", "reason": "retention inside uncertain 70-85 percent band", "baseline_avd_seconds": round(baseline_avd, 2)}

        trend_score = _trend_opportunity(row)
        labels["trend_opportunity_label"] = {"status": "ready", "value": trend_score} if trend_score is not None else {"status": "pending", "reason": "trend context unavailable"}
        label["training_eligible"] = {
            task: labels.get(config["target"], {}).get("status") == "ready"
            for task, config in TASK_CONFIG.items()
        }
        by_video[label["video_id"]] = label
    final = list(by_video.values())
    final.sort(key=lambda item: item.get("published_at") or "")
    return final


def train_candidate_models(snapshots: List[Dict[str, Any]], labels: List[Dict[str, Any]], registry_dir: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    version = f"candidate-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    candidate_dir = os.path.join(registry_dir, version)
    os.makedirs(candidate_dir, exist_ok=True)
    rows_by_video = _latest_rows_by_video(snapshots)
    label_rows = [label for label in labels if label.get("video_id") in rows_by_video]
    label_rows.sort(key=lambda item: item.get("published_at") or "")
    split_index = max(1, int(len(label_rows) * 0.8))
    train_labels = label_rows[:split_index]
    eval_labels = label_rows[split_index:] or label_rows[-1:]
    model_paths: Dict[str, str] = {}
    task_metrics: Dict[str, Any] = {}
    task_scores: Dict[str, float] = {}
    shadow_tasks: List[str] = []

    for task, config in TASK_CONFIG.items():
        train_x, train_y = _examples_for_task(train_labels, rows_by_video, task)
        eval_x, eval_y = _examples_for_task(eval_labels, rows_by_video, task)
        if len(train_y) < 3 or len(eval_y) < 1:
            shadow_tasks.append(task)
            task_metrics[task] = {"status": "shadow", "reason": "not enough task labels", "train_samples": len(train_y), "eval_samples": len(eval_y)}
            continue
        if config["kind"] == "classifier" and len(set(train_y)) < 2:
            shadow_tasks.append(task)
            task_metrics[task] = {"status": "shadow", "reason": "classifier has one class in train", "train_samples": len(train_y), "eval_samples": len(eval_y)}
            continue
        model = RandomForestClassifier(n_estimators=80, max_depth=8, random_state=42) if config["kind"] == "classifier" else RandomForestRegressor(n_estimators=80, max_depth=8, random_state=42)
        model.fit(np.array(train_x), np.array(train_y))
        path = os.path.join(candidate_dir, f"{task}.joblib")
        joblib.dump(model, path)
        model_paths[task] = path
        predictions = model.predict(np.array(eval_x))
        metrics, score = _task_metric(task, config["kind"], np.array(eval_y), predictions, model, np.array(eval_x))
        task_metrics[task] = {**metrics, "status": "trained", "train_samples": len(train_y), "eval_samples": len(eval_y)}
        task_scores[task] = score

    total_labeled = len([item for item in label_rows if any(item.get("training_eligible", {}).values())])
    eval_samples = len(eval_labels)
    composite = _composite_score(task_scores)
    champion = manifest.get("champion") or {}
    champion_metrics = champion.get("metrics") or {}
    champion_score = float(champion_metrics.get("composite_score") or 0.0)
    critical_regressions = _critical_regressions(task_scores, champion_metrics.get("task_scores") or {})
    can_promote = (
        total_labeled >= MIN_PROMOTION_SAMPLES
        and eval_samples >= MIN_EVAL_SAMPLES
        and bool(task_scores)
        and not critical_regressions
        and (not champion or composite >= champion_score * 1.05 or champion_score == 0.0)
    )
    decision = {
        "auto_promoted": bool(can_promote),
        "shadow_mode": not bool(can_promote),
        "reasons": _promotion_reasons(total_labeled, eval_samples, composite, champion_score, critical_regressions, task_scores),
        "critical_regressions": critical_regressions,
    }
    metadata = {
        "version": version,
        "created_at": _utc_now(),
        "candidate_dir": candidate_dir,
        "model_paths": model_paths,
        "sample_counts": {"total_labeled": total_labeled, "eval_samples": eval_samples, "train_videos": len(train_labels), "eval_videos": len(eval_labels)},
        "evaluation": {
            "temporal_split": {"train_count": len(train_labels), "eval_count": len(eval_labels), "split": "oldest_80_train_newest_20_eval"},
            "task_metrics": task_metrics,
            "task_scores": task_scores,
            "composite_score": composite,
            "champion_composite_score": champion_score,
            "shadow_tasks": shadow_tasks,
        },
        "promotion_decision": decision,
    }
    with open(os.path.join(candidate_dir, "metadata.json"), "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    return metadata


def _initial_label(row: Dict[str, Any]) -> Dict[str, Any]:
    age_hours = _hours_since(row.get("published_at"), now=row.get("captured_at"))
    analytics = row.get("analytics") or {}
    totals = analytics.get("totals") or {}
    rows = analytics.get("rows") or analytics.get("timeline") or []
    labels: Dict[str, Any] = {}

    ctr = _analytics_ctr(totals)
    impressions = _to_float(totals.get("impressions"))
    if ctr is not None and impressions:
        labels["ctr_label"] = {"status": "ready", "value": float(np.clip(ctr, 0.1, 25.0)), "impressions": impressions}
    else:
        labels["ctr_label"] = {"status": "pending", "reason": "analytics impressions/ctr unavailable"}

    first_day_views = _sum_row_metric(rows[:1], "views")
    if age_hours >= 24 and first_day_views is not None:
        labels["views_24h_label"] = {"status": "ready", "value": first_day_views, "label_quality": "analytics_24h"}
    elif age_hours >= 24:
        labels["views_24h_label"] = {"status": "ready", "value": int(row.get("views") or 0), "label_quality": "public_cumulative"}
    else:
        labels["views_24h_label"] = {"status": "pending", "reason": "video younger than 24h"}

    seven_day_views = _sum_row_metric(rows[:7], "views")
    if age_hours >= 168 and seven_day_views is not None:
        labels["views_7d_label"] = {"status": "ready", "value": seven_day_views, "label_quality": "analytics_7d"}
    elif age_hours >= 168:
        labels["views_7d_label"] = {"status": "ready", "value": int(row.get("views") or 0), "label_quality": "public_cumulative"}
    else:
        labels["views_7d_label"] = {"status": "pending", "reason": "video younger than 7d"}

    return {
        "video_id": row.get("video_id"),
        "label_version": LABEL_VERSION,
        "updated_at": _utc_now(),
        "source": row.get("source"),
        "published_at": row.get("published_at"),
        "labels": labels,
    }


def _normalize_snapshot(row: Dict[str, Any], source: str, captured_at: str) -> Dict[str, Any]:
    video_id = str(row.get("video_id") or row.get("id") or "").strip()
    return {
        "video_id": video_id,
        "snapshot_kind": row.get("snapshot_kind") or "channel_video",
        "captured_at": row.get("captured_at") or captured_at,
        "source": source,
        "fake_fallback_used": False if source == "real_youtube" else None,
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "tags": row.get("tags") or [],
        "published_at": row.get("published_at"),
        "category_id": row.get("category_id") or "28",
        "views": int(row.get("views") if row.get("views") is not None else row.get("view_count") or 0),
        "likes": int(row.get("likes") if row.get("likes") is not None else row.get("like_count") or 0),
        "comments": int(row.get("comments") if row.get("comments") is not None else row.get("comment_count") or 0),
        "analytics": row.get("analytics") or {},
        "package": row.get("package") or {},
        "analysis": row.get("analysis") or {},
        "trend": row.get("trend") or {},
        "feature_overrides": row.get("feature_overrides") or {},
    }


def _feature_row(row: Dict[str, Any]) -> Dict[str, float]:
    title = row.get("title") or (row.get("package") or {}).get("final_title") or ""
    lower = title.lower()
    title_alpha = [char for char in title if char.isalpha()]
    analytics = row.get("analytics") or {}
    totals = analytics.get("totals") or {}
    views = float(row.get("views") or 0)
    likes = float(row.get("likes") or 0)
    comments = float(row.get("comments") or 0)
    published = _parse_dt(row.get("published_at"))
    publish_hour = published.hour if published else 12
    package = row.get("package") or {}
    analysis = row.get("analysis") or {}
    hook_score = _nested_number(analysis, ["hook_report", "hook_strength"], default=62.0)
    brand_risk = _nested_number(analysis, ["brand_safety_report", "risk_score"], default=0.0)
    trend = row.get("trend") or {}
    trend_prediction = trend.get("trend_prediction") or {}
    return {
        "title_length": float(len(title)),
        "caps_ratio": float(sum(1 for char in title_alpha if char.isupper()) / max(len(title_alpha), 1)),
        "has_power_word": float(any(word in lower for word in POWER_WORDS)),
        "has_negative_hook": float(any(word in lower for word in NEGATIVE_HOOKS)),
        "topic_cluster_id": float(CLUSTER_IDS.get(trend.get("topic_cluster") or package.get("topic_cluster") or "general trend", 5)),
        "category_id_num": float(_safe_int(row.get("category_id"), 28)),
        "publish_hour": float(publish_hour),
        "description_length": float(len(row.get("description") or package.get("description") or "")),
        "tag_count": float(len(row.get("tags") or package.get("tags") or [])),
        "contains_synthetic_media": float(bool(row.get("contains_synthetic_media") or package.get("contains_synthetic_media"))),
        "hook_score": float(hook_score),
        "brand_risk_score": float(brand_risk),
        "trend_fit": float(_nested_number(trend_prediction, ["signals", "channel_fit_score"], default=70.0)),
        "elapsed_hours": float(_hours_since(row.get("published_at"), now=row.get("captured_at"))),
        "views_per_hour": float(views / max(_hours_since(row.get("published_at"), now=row.get("captured_at")), 1.0)),
        "likes_per_view": float(likes / max(views, 1.0)),
        "comments_per_view": float(comments / max(views, 1.0)),
        "ctr": float(_analytics_ctr(totals) or 0.0),
        "impressions": float(totals.get("impressions") or 0.0),
        "average_view_duration_seconds": float(totals.get("average_view_duration_seconds") or totals.get("averageViewDuration") or 0.0),
        "watch_time_minutes": float(totals.get("watch_time_minutes") or totals.get("estimatedMinutesWatched") or 0.0),
        "trend_rank_movement": float(_nested_number(trend_prediction, ["signals", "rank_movement"], default=0.0)),
    }


def _feature_vector(features: Dict[str, float], schema: List[str]) -> np.ndarray:
    return np.array([float(features.get(name, 0.0)) for name in schema], dtype=float)


def _examples_for_task(labels: List[Dict[str, Any]], rows_by_video: Dict[str, Dict[str, Any]], task: str) -> Tuple[List[np.ndarray], List[float]]:
    config = TASK_CONFIG[task]
    xs: List[np.ndarray] = []
    ys: List[float] = []
    for label in labels:
        target = label.get("labels", {}).get(config["target"], {})
        if target.get("status") != "ready":
            continue
        row = rows_by_video.get(label.get("video_id"))
        if not row:
            continue
        xs.append(_feature_vector(_feature_row(row), config["features"]))
        ys.append(float(target.get("value")))
    return xs, ys


def _task_metric(task: str, kind: str, y_true: np.ndarray, y_pred: np.ndarray, model: Any, eval_x: np.ndarray) -> Tuple[Dict[str, Any], float]:
    if kind == "classifier":
        y_true_int = y_true.astype(int)
        y_pred_int = y_pred.astype(int)
        f1 = float(f1_score(y_true_int, y_pred_int, zero_division=0))
        metric = {"f1": round(f1, 4)}
        score = f1
        if len(set(y_true_int.tolist())) > 1 and hasattr(model, "predict_proba"):
            try:
                auc = float(roc_auc_score(y_true_int, model.predict_proba(eval_x)[:, 1]))
                metric["roc_auc"] = round(auc, 4)
                score = auc
            except Exception:
                pass
        return metric, float(np.clip(score, 0.0, 1.0))
    if task in {"views_24h", "views_7d"}:
        floor = np.maximum(np.abs(y_true), 100.0)
        mape = float(np.mean(np.abs((y_true - y_pred) / floor)))
        return {"mape": round(mape, 4)}, float(1.0 / (1.0 + mape))
    mae = float(mean_absolute_error(y_true, y_pred))
    denom = 25.0 if task == "ctr" else 100.0
    return {"mae": round(mae, 4)}, float(1.0 / (1.0 + mae / denom))


def _composite_score(task_scores: Dict[str, float]) -> float:
    if not task_scores:
        return 0.0
    weight_sum = sum(TASK_WEIGHTS[task] for task in task_scores if task in TASK_WEIGHTS)
    if weight_sum <= 0:
        return 0.0
    return round(sum(task_scores[task] * TASK_WEIGHTS[task] for task in task_scores if task in TASK_WEIGHTS) / weight_sum, 6)


def _critical_regressions(candidate_scores: Dict[str, float], champion_scores: Dict[str, float]) -> List[Dict[str, Any]]:
    regressions = []
    for task, champion_score in champion_scores.items():
        if task not in candidate_scores or not champion_score:
            continue
        candidate_score = candidate_scores[task]
        if candidate_score < float(champion_score) * 0.90:
            regressions.append({"task": task, "candidate_score": round(candidate_score, 4), "champion_score": round(float(champion_score), 4)})
    return regressions


def _promotion_reasons(total_labeled: int, eval_samples: int, composite: float, champion_score: float, regressions: List[Dict[str, Any]], task_scores: Dict[str, float]) -> List[str]:
    reasons = []
    if total_labeled < MIN_PROMOTION_SAMPLES:
        reasons.append("Needs at least 20 labeled samples before auto-promotion.")
    if eval_samples < MIN_EVAL_SAMPLES:
        reasons.append("Needs at least 8 temporal eval samples before auto-promotion.")
    if not task_scores:
        reasons.append("No task had enough labels to train.")
    if champion_score and composite < champion_score * 1.05:
        reasons.append("Candidate did not beat champion composite by 5%.")
    if regressions:
        reasons.append("At least one critical task regressed by more than 10%.")
    if not reasons:
        reasons.append("Candidate passed temporal backtest and promotion gates.")
    return reasons


def _latest_rows_by_video(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in sorted(rows, key=lambda item: item.get("captured_at") or ""):
        if row.get("video_id"):
            latest[row["video_id"]] = row
    return latest


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _snapshot_key(row: Dict[str, Any]) -> str:
    captured = _parse_dt(row.get("captured_at")) or datetime.now(timezone.utc)
    hour_key = captured.strftime("%Y-%m-%dT%H")
    return f"{row.get('video_id')}::{row.get('snapshot_kind')}::{hour_key}"


def _apply_snapshot_retention(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    retained = [row for row in rows if (_parse_dt(row.get("captured_at")) or cutoff) >= cutoff]
    retained.sort(key=lambda item: item.get("captured_at") or "")
    return retained[-MAX_SNAPSHOT_ROWS:]


def _count_ready_labels(labels: List[Dict[str, Any]]) -> int:
    return sum(1 for label in labels for item in label.get("labels", {}).values() if item.get("status") == "ready")


def _count_pending_labels(labels: List[Dict[str, Any]]) -> int:
    return sum(1 for label in labels for item in label.get("labels", {}).values() if item.get("status") in {"pending", "ambiguous"})


def _training_badges(champion: Optional[Dict[str, Any]], labels: List[Dict[str, Any]], candidate: Optional[Dict[str, Any]]) -> List[str]:
    badges = ["Temporal Backtest"]
    if champion:
        badges.append("Champion Active")
    else:
        badges.append("Shadow Mode")
    if _count_ready_labels(labels) < MIN_PROMOTION_SAMPLES:
        badges.append("Needs More Labels")
    if candidate and candidate.get("promotion_decision", {}).get("shadow_mode"):
        badges.append("Shadow Mode")
    return list(dict.fromkeys(badges))


def _prune_candidate_dirs(registry_dir: str, manifest: Dict[str, Any]) -> None:
    keep = {os.path.basename(item.get("candidate_dir", "")) for item in manifest.get("candidates", [])}
    champion = manifest.get("champion") or {}
    if champion.get("candidate_dir"):
        keep.add(os.path.basename(champion["candidate_dir"]))
    if not os.path.exists(registry_dir):
        return
    for name in os.listdir(registry_dir):
        path = os.path.join(registry_dir, name)
        if os.path.isdir(path) and name.startswith("candidate-") and name not in keep:
            shutil.rmtree(path, ignore_errors=True)


def _label_ready(label: Dict[str, Any], name: str) -> bool:
    return label.get("labels", {}).get(name, {}).get("status") == "ready"


def _label_value(label: Dict[str, Any], name: str) -> float:
    return float(label.get("labels", {}).get(name, {}).get("value"))


def _analytics_total(row: Dict[str, Any], key: str) -> Optional[float]:
    totals = (row.get("analytics") or {}).get("totals") or {}
    value = totals.get(key)
    if value is None and key == "average_view_duration_seconds":
        value = totals.get("averageViewDuration")
    if value is None:
        return None
    return _to_float(value)


def _analytics_ctr(totals: Dict[str, Any]) -> Optional[float]:
    value = totals.get("ctr") if totals else None
    if value is None:
        value = totals.get("impressionClickThroughRate") if totals else None
    number = _to_float(value)
    if number is None:
        return None
    return number * 100.0 if number <= 1.0 else number


def _sum_row_metric(rows: List[Dict[str, Any]], key: str) -> Optional[float]:
    if not rows:
        return None
    values = [_to_float(row.get(key)) for row in rows if _to_float(row.get(key)) is not None]
    if not values:
        return None
    return float(sum(values))


def _trend_opportunity(row: Dict[str, Any]) -> Optional[float]:
    trend = row.get("trend") or {}
    prediction = trend.get("trend_prediction") or {}
    signals = prediction.get("signals") or {}
    if prediction.get("score") is not None:
        return float(np.clip(prediction.get("score"), 0, 100))
    values = [
        _to_float(signals.get("youtube_trend_score")),
        _to_float(signals.get("creator_opportunity_score")),
        _to_float(trend.get("opportunity_score")),
    ]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return float(np.clip(sum(values) / len(values), 0, 100))


def _percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    return float(np.percentile(np.array(values, dtype=float), pct))


def _percentile_rank(value: float, values: List[float]) -> float:
    if not values:
        return 50.0
    return float(sum(1 for item in values if item <= value) / len(values) * 100.0)


def _hours_since(iso_value: Optional[str], now: Optional[str] = None) -> float:
    published = _parse_dt(iso_value)
    current = _parse_dt(now) or datetime.now(timezone.utc)
    if not published:
        return 24.0
    return max((current - published).total_seconds() / 3600.0, 0.0)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str) and not value.strip():
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except Exception:
        return None


def _nested_number(data: Dict[str, Any], path: List[str], default: float) -> float:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return _to_float(current) if _to_float(current) is not None else default


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
