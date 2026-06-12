import pytest

from math_engine import StreamPilotMathEngine


def test_growth_simulation_is_seeded_and_has_valid_bands():
    engine = StreamPilotMathEngine()
    first = engine.simulate_growth(45000, uploads=3, ctr_boost=1, promo=50, collabs=1, seed=7)
    second = engine.simulate_growth(45000, uploads=3, ctr_boost=1, promo=50, collabs=1, seed=7)

    assert first == second
    assert len(first["current"]) == 24
    assert len(first["optimized"]) == 24
    for lo, mid, hi in zip(first["current_lower"], first["current"], first["current_upper"]):
        assert lo <= mid <= hi
    for lo, mid, hi in zip(first["lower"], first["optimized"], first["upper"]):
        assert lo <= mid <= hi
    assert first["assumptions"]["shock_distribution"] == "student_t_df_5"
    assert first["assumptions"]["jump_intensity_per_week"] == 0.05


def test_kalman_handles_edge_cases_and_positive_trend():
    engine = StreamPilotMathEngine()

    assert engine.kalman_filter_growth([]) == ([], 0.0)
    assert engine.kalman_filter_growth([0]) == ([0], 0.0)
    zero_smoothed, zero_growth = engine.kalman_filter_growth([0, 0, 0, 0])
    assert zero_smoothed == [0, 0, 0, 0]
    assert zero_growth == 0.0

    seasonal_growth = [1000 + i * 80 + (i % 7) * 120 for i in range(35)]
    smoothed, growth = engine.kalman_filter_growth(seasonal_growth)
    assert len(smoothed) == len(seasonal_growth)
    assert all(value >= 0 for value in smoothed)
    assert growth > 0


def test_bayesian_ab_test_seed_rope_and_validation():
    engine = StreamPilotMathEngine()

    with pytest.raises(ValueError):
        engine.bayesian_ab_test(10, 11, 10, 1)

    first = engine.bayesian_ab_test(3000, 114, 3050, 164, historical_ctr=0.05, seed=11)
    second = engine.bayesian_ab_test(3000, 114, 3050, 164, historical_ctr=0.05, seed=11)
    assert first == second
    assert first["winner"] == "B"
    assert first["probability_b_better"] > first["probability_a_better"]
    assert first["expected_loss_b"] < first["expected_loss_a"]

    close = engine.bayesian_ab_test(10000, 500, 10000, 503, historical_ctr=0.05, seed=4)
    assert close["recommendation"] in {"Equivalent", "Keep testing"}
    assert close["rope_probability"] > 0.3


def test_ctr_features_and_heuristic_prediction_are_deterministic():
    engine = StreamPilotMathEngine()
    title = "Do NOT Buy This Budget Gaming PC in 2026"
    features = engine.extract_title_features(title)

    assert features["feature_order"] == list(engine.TRAINING_FEATURE_ORDER)
    assert features["model_features"].shape == (1, 6)
    assert features["analysis"]["has_negative_hook"] is True
    assert features["analysis"]["title_query_similarity"] > 0

    low_entropy = engine.extract_title_features("aaaaaaaaaa")["analysis"]["character_entropy"]
    high_entropy = engine.extract_title_features("RTX 5090 vs $500 PC?!")["analysis"]["character_entropy"]
    assert high_entropy > low_entropy

    first = engine.predict_ctr(title)
    second = engine.predict_ctr(title)
    assert first == second
    assert first["model_source"] == "heuristic"
    assert first["calibrated"] is True


def test_slot_optimizer_skips_unused_slots_and_preserves_diversity():
    engine = StreamPilotMathEngine()
    schedule = engine.slot_thompson_optimizer(
        videos=[
            {"id": "review", "priority": 90, "type": "review"},
            {"id": "build", "priority": 80, "type": "build"},
        ],
        slots=["Mon", "Tue", "Wed", "Thu"],
        seed=3,
    )

    assert len(schedule) == 2
    assert None not in schedule.values()
    assert set(schedule.values()) == {"review", "build"}


def test_hawkes_and_retention_models_return_actionable_metadata():
    engine = StreamPilotMathEngine()
    hawkes = engine.hawkes_viral_detection(view_series=[100, 120, 150, 500, 540, 900, 920])
    assert hawkes["event_count"] >= 2
    assert hawkes["alpha"] >= 0

    retention = engine.fit_retention_curve([100, 82, 70, 55, 44, 38, 30])
    assert retention["model"] in {"weibull", "power_law"}
    assert len(retention["fitted"]) == 7
    assert retention["hazard_hotspots"]
