import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import curve_fit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.isotonic import IsotonicRegression


EPSILON = 1e-9


@dataclass
class CTRPrediction:
    title: str
    predicted_ctr: float
    analysis: Dict[str, Any]
    model_source: str
    calibrated: bool


class StreamPilotMathEngine:
    """
    Practical creator analytics models for StreamPilot.

    Public wrappers keep the old API names alive while the implementation uses
    honest model names and deterministic random number generation where needed.
    """

    POWER_WORDS = (
        "ultimate",
        "destroy",
        "banned",
        "secret",
        "truth",
        "insane",
        "best",
        "worst",
        "cheap",
        "budget",
        "mistake",
        "worth",
    )
    NEGATIVE_HOOKS = ("don't", "do not", "stop", "regret", "never", "hate", "scam", "avoid")
    CLICKBAIT_PATTERNS = (
        r"you won'?t believe",
        r"\b\d+\s+(?:best|worst|mistakes|secrets|reasons)\b",
        r"\b(?:shocking|insane|crazy|secret|truth)\b",
        r"\b(?:before you buy|do not buy|don'?t buy)\b",
        r"\b(?:i tested|i tried|i built)\b",
    )
    TRAINING_FEATURE_ORDER = (
        "title_length",
        "caps_ratio",
        "has_power_word",
        "has_negative_hook",
        "thumbnail_contrast",
        "face_prominence",
    )

    def __init__(
        self,
        ctr_model: Any = None,
        trending_terms: Optional[Sequence[str]] = None,
        calibration_data: Optional[Sequence[Tuple[float, float]]] = None,
    ):
        self.ctr_model = ctr_model
        self.trending_terms = list(
            trending_terms
            or (
                "gaming pc build",
                "budget gaming pc",
                "graphics card review",
                "pc build guide",
                "best gpu",
                "tech review",
                "laptop review",
                "monitor buying guide",
            )
        )
        self.calibrator = self._build_calibrator(calibration_data)

    # ------------------------------------------------------------------
    # Growth simulation
    # ------------------------------------------------------------------
    def simulate_growth(
        self,
        base_subscribers: float,
        uploads: float,
        ctr_boost: float,
        promo: float,
        collabs: float,
        weeks: int = 24,
        seed: Optional[int] = 42,
        paths: int = 1000,
        baseline_weekly_growth: float = 0.02,
        jump_intensity: float = 0.05,
        shock_df: int = 5,
    ) -> Dict[str, Any]:
        """Monte Carlo subscriber simulation with OU mean reversion and viral jumps."""
        if weeks <= 0:
            raise ValueError("weeks must be positive")
        if paths < 50:
            raise ValueError("paths must be at least 50 for stable confidence bands")

        base_subscribers = max(float(base_subscribers or 0), 1.0)
        uploads = self._clip(float(uploads), 0.0, 14.0)
        ctr_boost = self._clip(float(ctr_boost), 0.0, 20.0)
        promo = self._clip(float(promo), 0.0, 10000.0)
        collabs = self._clip(float(collabs), 0.0, 20.0)

        boost = (uploads * 0.003) + (ctr_boost * 0.004) + (promo * 0.00005) + (collabs * 0.008)
        boost = self._clip(boost, 0.0, 0.12)

        rng = np.random.default_rng(seed)
        current_paths = self._simulate_growth_paths(
            base_subscribers,
            baseline_weekly_growth,
            weeks,
            paths,
            rng,
            jump_intensity,
            shock_df,
        )

        # Use a second generator advanced from the same seed so optimized and
        # baseline are deterministic but not identical paths.
        optimized_paths = self._simulate_growth_paths(
            base_subscribers,
            baseline_weekly_growth + boost,
            weeks,
            paths,
            rng,
            jump_intensity,
            shock_df,
        )

        current_median, current_lower, current_upper = self._summarize_paths(current_paths)
        optimized_median, lower, upper = self._summarize_paths(optimized_paths)
        final_subs = int(optimized_median[-1])
        baseline_final = int(current_median[-1])
        gain = final_subs - baseline_final
        pct_gain = (gain / max(baseline_final, 1)) * 100.0

        return {
            "current": current_median,
            "optimized": optimized_median,
            "lower": lower,
            "upper": upper,
            "current_lower": current_lower,
            "current_upper": current_upper,
            "final_subs": final_subs,
            "baseline_final_subs": baseline_final,
            "gain": int(gain),
            "pct_gain": round(pct_gain, 2),
            "weeks": weeks,
            "seed": seed,
            "assumptions": {
                "shock_distribution": f"student_t_df_{shock_df}",
                "mean_reversion": "ornstein_uhlenbeck",
                "jump_intensity_per_week": jump_intensity,
                "jump_size": "lognormal",
                "optimized_growth_boost": round(boost, 4),
            },
        }

    def _simulate_growth_paths(
        self,
        base_subscribers: float,
        target_weekly_growth: float,
        weeks: int,
        paths: int,
        rng: np.random.Generator,
        jump_intensity: float,
        shock_df: int,
    ) -> np.ndarray:
        theta = 0.35
        volatility = 0.025
        growth = np.full(paths, target_weekly_growth, dtype=float)
        subscribers = np.full(paths, base_subscribers, dtype=float)
        out = np.zeros((paths, weeks), dtype=float)

        for week in range(weeks):
            shocks = rng.standard_t(df=shock_df, size=paths) * volatility
            growth += theta * (target_weekly_growth - growth) + shocks
            growth = np.clip(growth, -0.18, 0.22)

            jump_mask = rng.poisson(jump_intensity, size=paths) > 0
            jumps = np.zeros(paths, dtype=float)
            if jump_mask.any():
                jumps[jump_mask] = rng.lognormal(mean=0.10, sigma=0.35, size=int(jump_mask.sum()))

            log_step = np.clip(growth + jumps, -0.35, 0.75)
            subscribers *= np.exp(log_step)
            subscribers = np.clip(subscribers, 1.0, base_subscribers * 100.0)
            out[:, week] = subscribers

        return out

    @staticmethod
    def _summarize_paths(paths: np.ndarray) -> Tuple[List[int], List[int], List[int]]:
        lower = np.percentile(paths, 2.5, axis=0)
        median = np.percentile(paths, 50, axis=0)
        upper = np.percentile(paths, 97.5, axis=0)
        return (
            [int(round(v)) for v in median],
            [int(round(v)) for v in lower],
            [int(round(v)) for v in upper],
        )

    # ------------------------------------------------------------------
    # Kalman + RTS smoothing
    # ------------------------------------------------------------------
    def kalman_filter_growth(
        self,
        historical_views: Sequence[Any],
        dates: Optional[Sequence[Any]] = None,
    ) -> Tuple[List[int], float]:
        """Local-linear Kalman filter in log space with weekly seasonality and RTS smoothing."""
        values, inferred_dates = self._extract_views_and_dates(historical_views)
        if dates is None:
            dates = inferred_dates

        if len(values) == 0:
            return [], 0.0
        if len(values) == 1:
            return [int(round(max(values[0], 0)))], 0.0

        y = np.log1p(np.maximum(np.asarray(values, dtype=float), 0.0))
        season_keys = self._season_keys(len(y), dates)
        seasonal = self._weekly_seasonality(y, season_keys)
        deseasoned = np.asarray([y[i] - seasonal[season_keys[i]] for i in range(len(y))])

        level, trend = self._rts_local_linear(deseasoned)
        smoothed_log = np.asarray([level[i] + seasonal[season_keys[i]] for i in range(len(level))])
        smoothed_views = np.maximum(np.expm1(smoothed_log), 0.0)
        result = [int(round(v)) for v in smoothed_views]

        level_last = max(abs(float(level[-1])), EPSILON)
        growth_rate = 100.0 * float(trend[-1]) / level_last
        return result, round(growth_rate, 2)

    def _rts_local_linear(self, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        n = len(y)
        f = np.array([[1.0, 1.0], [0.0, 1.0]])
        h = np.array([[1.0, 0.0]])
        i2 = np.eye(2)

        initial_trend = float(np.median(np.diff(y[: min(n, 8)]))) if n > 2 else 0.0
        x = np.array([float(y[0]), initial_trend])
        p = np.diag([0.25, 0.05])
        q = np.diag([0.01, 0.001])
        r = max(float(np.var(np.diff(y))) if n > 2 else 0.05, 0.01)

        xf = np.zeros((n, 2))
        xp = np.zeros((n, 2))
        pf = np.zeros((n, 2, 2))
        pp = np.zeros((n, 2, 2))
        innovation_var = r

        for k, obs in enumerate(y):
            if k == 0:
                x_pred = x
                p_pred = p
            else:
                x_pred = f @ x
                p_pred = f @ p @ f.T + q

            innovation = float(obs - (h @ x_pred)[0])
            innovation_var = 0.90 * innovation_var + 0.10 * (innovation * innovation)
            r = self._clip(innovation_var, 0.005, 1.5)
            q_scale = self._clip(abs(innovation) * 0.01, 0.0005, 0.05)
            q = np.diag([q_scale, q_scale * 0.1])

            s = float((h @ p_pred @ h.T)[0, 0] + r)
            k_gain = (p_pred @ h.T) / max(s, EPSILON)
            x = x_pred + (k_gain[:, 0] * innovation)
            p = (i2 - k_gain @ h) @ p_pred

            xp[k] = x_pred
            pp[k] = p_pred
            xf[k] = x
            pf[k] = p

        xs = xf.copy()
        ps = pf.copy()
        for k in range(n - 2, -1, -1):
            try:
                c = pf[k] @ f.T @ np.linalg.pinv(pp[k + 1])
            except np.linalg.LinAlgError:
                c = np.zeros((2, 2))
            xs[k] = xf[k] + c @ (xs[k + 1] - xp[k + 1])
            ps[k] = pf[k] + c @ (ps[k + 1] - pp[k + 1]) @ c.T

        return xs[:, 0], xs[:, 1]

    @staticmethod
    def _weekly_seasonality(y: np.ndarray, keys: Sequence[int]) -> Dict[int, float]:
        global_mean = float(np.mean(y))
        seasonal: Dict[int, float] = {}
        for key in range(7):
            vals = [float(y[i]) for i, item_key in enumerate(keys) if item_key == key]
            seasonal[key] = (float(np.mean(vals)) - global_mean) if vals else 0.0
        return seasonal

    @staticmethod
    def _season_keys(length: int, dates: Optional[Sequence[Any]]) -> List[int]:
        if dates and len(dates) == length:
            keys: List[int] = []
            for item in dates:
                if hasattr(item, "weekday"):
                    keys.append(int(item.weekday()))
                else:
                    try:
                        from datetime import datetime

                        keys.append(datetime.fromisoformat(str(item)).weekday())
                    except Exception:
                        keys.append(len(keys) % 7)
            return keys
        return [i % 7 for i in range(length)]

    @staticmethod
    def _extract_views_and_dates(historical_views: Sequence[Any]) -> Tuple[List[float], Optional[List[Any]]]:
        values: List[float] = []
        dates: List[Any] = []
        has_dates = False
        for item in historical_views or []:
            if isinstance(item, dict):
                values.append(float(item.get("views", 0) or 0))
                dates.append(item.get("date"))
                has_dates = has_dates or bool(item.get("date"))
            else:
                values.append(float(item or 0))
        return values, dates if has_dates else None

    # ------------------------------------------------------------------
    # Bayesian A/B testing
    # ------------------------------------------------------------------
    def bayesian_ab_test(
        self,
        impressions_a: int,
        clicks_a: int,
        impressions_b: int,
        clicks_b: int,
        historical_ctr: Optional[Any] = None,
        prior_strength: float = 200.0,
        rope: float = 0.005,
        samples: int = 20000,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._validate_ab_counts(impressions_a, clicks_a, "A")
        self._validate_ab_counts(impressions_b, clicks_b, "B")
        alpha0, beta0 = self._ctr_prior(historical_ctr, prior_strength)

        post_a = (alpha0 + clicks_a, beta0 + impressions_a - clicks_a)
        post_b = (alpha0 + clicks_b, beta0 + impressions_b - clicks_b)
        rng = np.random.default_rng(seed)
        a_samples = rng.beta(post_a[0], post_a[1], samples)
        b_samples = rng.beta(post_b[0], post_b[1], samples)
        diff = b_samples - a_samples

        prob_b = float(np.mean(diff > rope))
        prob_a = float(np.mean(diff < -rope))
        rope_probability = float(np.mean(np.abs(diff) <= rope))
        expected_loss_a = float(np.mean(np.maximum(diff, 0.0)) * 100.0)
        expected_loss_b = float(np.mean(np.maximum(-diff, 0.0)) * 100.0)

        ctr_a = clicks_a / max(impressions_a, 1)
        ctr_b = clicks_b / max(impressions_b, 1)
        if rope_probability >= 0.60:
            recommendation = "Equivalent"
            winner = "Inconclusive"
            confidence = rope_probability
        elif prob_a >= 0.95 and expected_loss_a < expected_loss_b:
            recommendation = "A"
            winner = "A"
            confidence = prob_a
        elif prob_b >= 0.95 and expected_loss_b < expected_loss_a:
            recommendation = "B"
            winner = "B"
            confidence = prob_b
        else:
            recommendation = "Keep testing"
            winner = "Inconclusive"
            confidence = max(prob_a, prob_b, rope_probability)

        return {
            "winner": winner,
            "confidence": round(confidence * 100.0, 1),
            "ctr_a": round(ctr_a * 100.0, 2),
            "ctr_b": round(ctr_b * 100.0, 2),
            "probability_a_better": round(prob_a, 4),
            "probability_b_better": round(prob_b, 4),
            "expected_loss_a": round(expected_loss_a, 4),
            "expected_loss_b": round(expected_loss_b, 4),
            "rope_probability": round(rope_probability, 4),
            "recommendation": recommendation,
            "prior": {
                "alpha": round(alpha0, 3),
                "beta": round(beta0, 3),
                "source": "historical_ctr" if historical_ctr is not None else "uniform",
            },
        }

    def quantum_bayesian_ab_test(self, impressions_a, clicks_a, impressions_b, clicks_b):
        """Compatibility wrapper for older agent code."""
        return self.bayesian_ab_test(impressions_a, clicks_a, impressions_b, clicks_b, seed=42)

    @staticmethod
    def _validate_ab_counts(impressions: int, clicks: int, label: str) -> None:
        if impressions < 0 or clicks < 0:
            raise ValueError(f"{label} impressions and clicks must be non-negative")
        if clicks > impressions:
            raise ValueError(f"{label} clicks cannot exceed impressions")

    @staticmethod
    def _ctr_prior(historical_ctr: Optional[Any], prior_strength: float) -> Tuple[float, float]:
        if historical_ctr is None:
            return 1.0, 1.0
        if isinstance(historical_ctr, (list, tuple, np.ndarray)):
            vals = np.asarray(historical_ctr, dtype=float)
            vals = vals[np.isfinite(vals)]
            ctr = float(np.mean(vals)) if len(vals) else 0.05
        else:
            ctr = float(historical_ctr)
        if ctr > 1.0:
            ctr /= 100.0
        ctr = float(np.clip(ctr, 0.001, 0.5))
        strength = max(float(prior_strength), 2.0)
        return max(1.0, ctr * strength), max(1.0, (1.0 - ctr) * strength)

    # ------------------------------------------------------------------
    # CTR prediction
    # ------------------------------------------------------------------
    def extract_title_features(
        self,
        title: str,
        query_terms: Optional[Sequence[str]] = None,
        thumbnail_contrast: float = 60.0,
        face_prominence: float = 50.0,
    ) -> Dict[str, Any]:
        title = title or ""
        lower = title.lower()
        title_length = len(title)
        alpha_chars = [c for c in title if c.isalpha()]
        caps_ratio = (
            sum(1 for c in alpha_chars if c.isupper()) / max(len(alpha_chars), 1)
            if alpha_chars
            else 0.0
        )
        punctuation_ratio = sum(1 for c in title if not c.isalnum() and not c.isspace()) / max(title_length, 1)
        has_power = int(any(word in lower for word in self.POWER_WORDS))
        has_neg = int(any(word in lower for word in self.NEGATIVE_HOOKS))
        clickbait_flags = [pattern for pattern in self.CLICKBAIT_PATTERNS if re.search(pattern, lower)]
        entropy = self._character_entropy(title)
        similarity = self._title_query_similarity(title, query_terms or self.trending_terms)

        model_features = np.array(
            [[title_length, caps_ratio, has_power, has_neg, thumbnail_contrast, face_prominence]],
            dtype=float,
        )
        return {
            "model_features": model_features,
            "feature_order": list(self.TRAINING_FEATURE_ORDER),
            "analysis": {
                "length": title_length,
                "caps_ratio": round(caps_ratio, 4),
                "punctuation_ratio": round(punctuation_ratio, 4),
                "has_power_word": bool(has_power),
                "has_negative_hook": bool(has_neg),
                "clickbait_pattern_count": len(clickbait_flags),
                "clickbait_patterns": clickbait_flags,
                "character_entropy": round(entropy, 4),
                "title_query_similarity": round(similarity, 4),
                "thumbnail_contrast": thumbnail_contrast,
                "face_prominence": face_prominence,
            },
        }

    def predict_ctr(
        self,
        title: str,
        model: Any = None,
        query_terms: Optional[Sequence[str]] = None,
        thumbnail_contrast: float = 60.0,
        face_prominence: float = 50.0,
    ) -> Dict[str, Any]:
        features = self.extract_title_features(title, query_terms, thumbnail_contrast, face_prominence)
        active_model = model if model is not None else self.ctr_model
        raw_ctr: float
        model_source: str

        if active_model is not None:
            try:
                raw_ctr = float(active_model.predict(features["model_features"])[0])
                model_source = "random_forest"
            except Exception:
                raw_ctr = self._heuristic_ctr(features["analysis"])
                model_source = "heuristic"
        else:
            raw_ctr = self._heuristic_ctr(features["analysis"])
            model_source = "heuristic"

        calibrated_ctr, calibrated = self._calibrate_ctr(raw_ctr)
        prediction = CTRPrediction(
            title=title or "",
            predicted_ctr=round(float(np.clip(calibrated_ctr, 0.1, 25.0)), 2),
            analysis=features["analysis"],
            model_source=model_source,
            calibrated=calibrated,
        )
        return {
            "title": prediction.title,
            "predicted_ctr": prediction.predicted_ctr,
            "analysis": prediction.analysis,
            "model_source": prediction.model_source,
            "calibrated": prediction.calibrated,
            "feature_order": features["feature_order"],
        }

    def _heuristic_ctr(self, analysis: Dict[str, Any]) -> float:
        length = analysis["length"]
        length_score = max(0.0, 2.0 - abs(length - 48) * 0.045)
        caps_score = 0.8 if 0.08 <= analysis["caps_ratio"] <= 0.35 else -1.0 * analysis["caps_ratio"]
        psychology = (1.3 if analysis["has_power_word"] else 0.0) + (
            1.8 if analysis["has_negative_hook"] else 0.0
        )
        clickbait = min(analysis["clickbait_pattern_count"], 2) * 0.7
        similarity = analysis["title_query_similarity"] * 2.0
        entropy_penalty = max(0.0, analysis["character_entropy"] - 4.2) * 0.7
        punctuation_penalty = max(0.0, analysis["punctuation_ratio"] - 0.12) * 5.0
        ctr = 4.5 + length_score + caps_score + psychology + clickbait + similarity
        ctr -= entropy_penalty + punctuation_penalty
        return float(np.clip(ctr, 0.1, 18.0))

    def _calibrate_ctr(self, raw_ctr: float) -> Tuple[float, bool]:
        raw_ctr = float(raw_ctr)
        if self.calibrator is not None:
            return float(self.calibrator.predict([raw_ctr])[0]), True

        # Platt-style fallback: compress extreme values toward a realistic CTR
        # range without requiring calibration data.
        centered = (raw_ctr - 5.0) / 4.0
        calibrated = 0.5 + 19.5 / (1.0 + math.exp(-centered))
        return float(0.65 * raw_ctr + 0.35 * calibrated), True

    @staticmethod
    def _build_calibrator(calibration_data: Optional[Sequence[Tuple[float, float]]]):
        if not calibration_data:
            return None
        raw = np.asarray([x for x, _ in calibration_data], dtype=float)
        actual = np.asarray([y for _, y in calibration_data], dtype=float)
        if len(raw) < 3:
            return None
        model = IsotonicRegression(out_of_bounds="clip")
        model.fit(raw, actual)
        return model

    @staticmethod
    def _character_entropy(title: str) -> float:
        if not title:
            return 0.0
        counts = np.asarray(list({char: title.count(char) for char in set(title)}.values()), dtype=float)
        probs = counts / counts.sum()
        return float(-np.sum(probs * np.log2(probs)))

    @staticmethod
    def _title_query_similarity(title: str, terms: Sequence[str]) -> float:
        if not title.strip() or not terms:
            return 0.0
        corpus = [title] + [term for term in terms if term]
        if len(corpus) <= 1:
            return 0.0
        try:
            matrix = TfidfVectorizer(ngram_range=(1, 2), lowercase=True).fit_transform(corpus)
            title_vec = matrix[0]
            term_matrix = matrix[1:]
            sims = (term_matrix @ title_vec.T).toarray().ravel()
            return float(np.max(sims)) if len(sims) else 0.0
        except ValueError:
            return 0.0

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------
    def slot_thompson_optimizer(
        self,
        videos: Sequence[Dict[str, Any]],
        slots: Sequence[str],
        slot_history: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = 42,
        diversity_penalty: float = 0.15,
    ) -> Dict[str, str]:
        if not videos or not slots:
            return {}

        rng = np.random.default_rng(seed)
        slot_history = slot_history or {}
        available_slots = list(slots)
        assigned: Dict[str, str] = {}
        assigned_types: Dict[str, str] = {}
        sorted_videos = sorted(videos, key=lambda v: float(v.get("priority", 0) or 0), reverse=True)

        for video in sorted_videos[: len(available_slots)]:
            best_slot = None
            best_score = -float("inf")
            content_type = str(video.get("type") or video.get("content_type") or "general")
            priority_boost = 1.0 + (float(video.get("priority", 0) or 0) / 100.0)

            for slot in available_slots:
                alpha, beta = self._slot_posterior(slot_history.get(slot))
                sampled_quality = rng.beta(alpha, beta)
                score = sampled_quality * priority_boost
                score -= self._adjacent_diversity_penalty(slot, content_type, slots, assigned_types, diversity_penalty)
                if score > best_score:
                    best_score = score
                    best_slot = slot

            if best_slot is None:
                continue
            assigned[best_slot] = str(video.get("id") or video.get("title") or f"video_{len(assigned) + 1}")
            assigned_types[best_slot] = content_type
            available_slots.remove(best_slot)

        return assigned

    def qaoa_schedule_optimizer(self, videos: list, slots: list) -> dict:
        """Compatibility wrapper for older agent code."""
        return self.slot_thompson_optimizer(videos, slots, seed=42)

    @staticmethod
    def _slot_posterior(history: Any) -> Tuple[float, float]:
        if isinstance(history, dict):
            if "alpha" in history and "beta" in history:
                return max(float(history["alpha"]), 1.0), max(float(history["beta"]), 1.0)
            successes = float(history.get("successes", 1.0))
            trials = max(float(history.get("trials", successes + 1.0)), successes)
            return 1.0 + successes, 1.0 + max(trials - successes, 0.0)
        if isinstance(history, (list, tuple)) and len(history) >= 2:
            successes = float(history[0])
            trials = max(float(history[1]), successes)
            return 1.0 + successes, 1.0 + max(trials - successes, 0.0)
        return 2.0, 2.0

    @staticmethod
    def _adjacent_diversity_penalty(
        slot: str,
        content_type: str,
        all_slots: Sequence[str],
        assigned_types: Dict[str, str],
        penalty: float,
    ) -> float:
        try:
            idx = list(all_slots).index(slot)
        except ValueError:
            return 0.0
        total = 0.0
        for neighbor_idx in (idx - 1, idx + 1):
            if 0 <= neighbor_idx < len(all_slots):
                neighbor = all_slots[neighbor_idx]
                if assigned_types.get(neighbor) == content_type:
                    total += penalty
        return total

    # ------------------------------------------------------------------
    # Hawkes viral detection + retention fitting
    # ------------------------------------------------------------------
    def hawkes_viral_detection(
        self,
        event_times: Optional[Sequence[float]] = None,
        view_series: Optional[Sequence[float]] = None,
        decay: float = 0.15,
    ) -> Dict[str, Any]:
        events = self._events_from_inputs(event_times, view_series)
        if len(events) < 2:
            return {"alpha": 0.0, "event_count": len(events), "status": "insufficient_data"}

        events = np.sort(np.asarray(events, dtype=float))
        window = max(float(events[-1] - events[0]), 1.0)
        excitation = 0.0
        pairs = 0
        for idx in range(1, len(events)):
            deltas = events[idx] - events[:idx]
            excitation += float(np.sum(np.exp(-decay * np.maximum(deltas, 0.0))))
            pairs += idx

        average_excitation = excitation / max(pairs, 1)
        alpha = float(np.clip(average_excitation * len(events) / max(window * decay, 1.0), 0.0, 1.5))
        return {
            "alpha": round(alpha, 3),
            "event_count": int(len(events)),
            "base_intensity": round(len(events) / window, 5),
            "status": "viral_risk" if alpha >= 1.0 else "stable",
        }

    def hawkes_virality_score(self, base_intensity: float, time_decay: float, recent_shares: list) -> float:
        """Compatibility wrapper returning only the branching ratio."""
        result = self.hawkes_viral_detection(event_times=recent_shares, decay=max(float(time_decay), EPSILON))
        if result["alpha"] == 0.0 and recent_shares:
            fallback = min(1.5, max(float(base_intensity), 0.0) + len(recent_shares) * 0.05)
            return round(fallback, 2)
        return round(float(result["alpha"]), 2)

    def fit_retention_curve(
        self,
        retention: Sequence[float],
        timestamps: Optional[Sequence[float]] = None,
    ) -> Dict[str, Any]:
        y = np.asarray(retention or [], dtype=float)
        if len(y) < 3:
            return {"model": "insufficient_data", "params": {}, "fitted": y.tolist(), "hazard_hotspots": []}
        y = np.clip(y, 0.001, 1.0 if np.nanmax(y) <= 1.0 else 100.0)
        if np.nanmax(y) > 1.0:
            y = y / 100.0
        x = (
            np.asarray(timestamps, dtype=float)
            if timestamps is not None and len(timestamps) == len(y)
            else np.linspace(0.0, 1.0, len(y))
        )
        x = np.asarray(x, dtype=float)
        x_norm = (x - np.min(x)) / max(float(np.max(x) - np.min(x)), EPSILON)
        x_fit = np.clip(x_norm, 0.001, 1.0)

        try:
            params, _ = curve_fit(self._weibull_survival, x_fit, y, p0=(1.0, 0.7), bounds=([0.05, 0.05], [10.0, 5.0]))
            fitted = self._weibull_survival(x_fit, *params)
            model = "weibull"
            param_dict = {"lambda": round(float(params[0]), 4), "shape": round(float(params[1]), 4)}
        except Exception:
            params, _ = curve_fit(self._power_law_retention, x_fit, y, p0=(1.0, 0.5), bounds=([0.01, 0.01], [2.0, 3.0]))
            fitted = self._power_law_retention(x_fit, *params)
            model = "power_law"
            param_dict = {"scale": round(float(params[0]), 4), "decay": round(float(params[1]), 4)}

        hazards = self._hazard_hotspots(fitted)
        return {
            "model": model,
            "params": param_dict,
            "fitted": [round(float(v), 4) for v in fitted],
            "hazard_hotspots": hazards,
        }

    @staticmethod
    def _events_from_inputs(
        event_times: Optional[Sequence[float]],
        view_series: Optional[Sequence[float]],
    ) -> List[float]:
        if event_times:
            return [float(x) for x in event_times]
        if not view_series or len(view_series) < 2:
            return []
        views = np.asarray(view_series, dtype=float)
        increments = np.maximum(np.diff(views), 0.0)
        if not np.any(increments):
            return []
        threshold = float(np.median(increments) + np.std(increments))
        return [float(i + 1) for i, inc in enumerate(increments) if inc >= threshold and inc > 0]

    @staticmethod
    def _weibull_survival(x: np.ndarray, lam: float, shape: float) -> np.ndarray:
        return np.exp(-np.power(x / max(lam, EPSILON), shape))

    @staticmethod
    def _power_law_retention(x: np.ndarray, scale: float, decay: float) -> np.ndarray:
        return np.clip(scale * np.power(x + 0.05, -decay), 0.0, 1.0)

    @staticmethod
    def _hazard_hotspots(fitted: np.ndarray) -> List[Dict[str, Any]]:
        safe = np.clip(np.asarray(fitted, dtype=float), 0.001, 1.0)
        hazard = -np.diff(np.log(safe))
        if len(hazard) == 0:
            return []
        top_indices = np.argsort(hazard)[-3:][::-1]
        return [
            {"index": int(idx + 1), "hazard": round(float(hazard[idx]), 4)}
            for idx in top_indices
            if hazard[idx] > 0
        ]

    @staticmethod
    def _clip(value: float, low: float, high: float) -> float:
        return float(min(max(value, low), high))


if __name__ == "__main__":
    engine = StreamPilotMathEngine()
    print(engine.hawkes_viral_detection(view_series=[100, 120, 180, 220, 500, 540]))
    print(engine.kalman_filter_growth([12000, 15000, 8000, 18000, 14000, 22000]))
    print(engine.slot_thompson_optimizer([{"id": "v1", "priority": 90}], ["Mon", "Tue"]))
    print(engine.bayesian_ab_test(3000, 114, 3050, 164, seed=42))
