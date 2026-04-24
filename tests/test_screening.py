"""Tests for the health screening engine."""

import json

import pandas as pd
import pytest

from src.screening import (
    add_vo2max_entry,
    classify_vo2max,
    compute_health_screening,
    load_vo2max,
    save_vo2max,
    _score_cardiovascular,
    _score_body_composition,
    _score_sleep_recovery,
    _score_training,
    _score_nutrition,
    _score_metabolic,
    _score_hormonal,
    _trend_direction,
    _clamp,
    VO2MAX_PATH,
)


# ── VO2 Max classification ──


class TestClassifyVo2Max:
    def test_superior(self):
        result = classify_vo2max(46)
        assert result["category"] == "Superior"
        assert result["score"] >= 90

    def test_excellent(self):
        result = classify_vo2max(41)
        assert result["category"] == "Excellent"
        assert 70 <= result["score"] < 90

    def test_good(self):
        result = classify_vo2max(37)
        assert result["category"] == "Good"
        assert 50 <= result["score"] < 70

    def test_fair(self):
        result = classify_vo2max(33)
        assert result["category"] == "Fair"
        assert 30 <= result["score"] < 50

    def test_poor(self):
        result = classify_vo2max(28)
        assert result["category"] == "Poor"
        assert result["score"] < 30

    def test_boundary_excellent_superior(self):
        result = classify_vo2max(43.3)
        assert result["category"] == "Excellent"
        result2 = classify_vo2max(43.4)
        assert result2["category"] == "Superior"

    def test_score_capped_at_100(self):
        result = classify_vo2max(80)
        assert result["score"] <= 100


# ── VO2 Max persistence ──


class TestVo2MaxPersistence:
    def test_save_and_load(self, tmp_path, monkeypatch):
        test_path = tmp_path / "vo2max.json"
        monkeypatch.setattr("src.screening.VO2MAX_PATH", test_path)

        entries = [{"date": "2026-01-06", "value": 46, "method": "manual"}]
        save_vo2max(entries)
        loaded = load_vo2max()
        assert len(loaded) == 1
        assert loaded[0]["value"] == 46

    def test_add_entry_sorts_by_date(self, tmp_path, monkeypatch):
        test_path = tmp_path / "vo2max.json"
        monkeypatch.setattr("src.screening.VO2MAX_PATH", test_path)

        # Seed
        save_vo2max([{"date": "2026-03-01", "value": 44, "method": "manual"}])
        # Add earlier date
        entries = add_vo2max_entry("2026-01-06", 46, "manual")
        assert entries[0]["date"] == "2026-01-06"
        assert entries[1]["date"] == "2026-03-01"

    def test_load_seeds_when_file_missing(self, tmp_path, monkeypatch):
        test_path = tmp_path / "vo2max.json"
        monkeypatch.setattr("src.screening.VO2MAX_PATH", test_path)

        entries = load_vo2max()
        assert len(entries) == 1
        assert entries[0]["value"] == 46
        assert test_path.exists()


# ── Helpers ──


class TestHelpers:
    def test_trend_direction_improving(self):
        assert _trend_direction(0.5) == "improving"

    def test_trend_direction_declining(self):
        assert _trend_direction(-0.5) == "declining"

    def test_trend_direction_stable(self):
        assert _trend_direction(0.001) == "stable"

    def test_trend_direction_none(self):
        assert _trend_direction(None) == "stable"

    def test_clamp_low(self):
        assert _clamp(-5) == 0.0

    def test_clamp_high(self):
        assert _clamp(150) == 100.0

    def test_clamp_normal(self):
        assert _clamp(55.5) == 55.5


# ── Domain scorers ──


def _date_range(n: int, start: str = "2026-01-01") -> list[pd.Timestamp]:
    return pd.date_range(start, periods=n, freq="D").tolist()


class TestSleepRecoveryScorer:
    def test_returns_available_with_data(self):
        datasets = {
            "sleep": pd.DataFrame({
                "day": _date_range(30),
                "score": [75] * 30,
                "deep_sleep_duration": [6000] * 30,
                "total_sleep_duration": [28800] * 30,
            }),
            "readiness": pd.DataFrame({
                "day": _date_range(30),
                "score": [80] * 30,
            }),
            "stress": pd.DataFrame({
                "day": _date_range(30),
                "stress_high": [40] * 30,
                "recovery_high": [60] * 30,
            }),
        }
        result = _score_sleep_recovery(datasets)
        assert result["available"] is True
        assert 0 <= result["score"] <= 100
        assert len(result["components"]) > 0

    def test_returns_unavailable_without_data(self):
        result = _score_sleep_recovery({})
        assert result["available"] is False
        assert result["score"] == 0


class TestBodyCompositionScorer:
    def test_scores_with_body_data(self):
        datasets = {
            "body_composition": pd.DataFrame({
                "day": pd.date_range("2026-01-01", periods=5, freq="14D"),
                "weight_kg": [85, 84.5, 84, 83.5, 83],
                "body_fat_pct": [18, 17.5, 17, 16.5, 16],
                "muscle_mass_kg": [38, 38.2, 38.4, 38.6, 38.8],
                "visceral_fat": [6, 6, 5, 5, 5],
                "bmi": [25.5, 25.3, 25.1, 24.9, 24.7],
                "metabolic_age": [48, 47, 46, 45, 44],
            }),
        }
        result = _score_body_composition(datasets)
        assert result["available"] is True
        assert result["score"] > 0

    def test_unavailable_without_data(self):
        result = _score_body_composition({})
        assert result["available"] is False


class TestTrainingScorer:
    def test_scores_with_workout_data(self):
        dates = _date_range(30)
        rows = []
        for i in range(30):
            rows.append({
                "day": dates[i],
                "exercise": ["Bench Press", "Squat", "Deadlift"][i % 3],
                "muscle_group": ["chest", "quadriceps", "hamstrings"][i % 3],
                "weight_kg": 60 + i,
                "reps": 8,
                "volume": (60 + i) * 8,
            })
        datasets = {"workouts": pd.DataFrame(rows)}
        result = _score_training(datasets)
        assert result["available"] is True
        assert result["score"] > 0

    def test_unavailable_without_data(self):
        result = _score_training({})
        assert result["available"] is False


class TestNutritionScorer:
    def test_scores_with_nutrition_data(self):
        datasets = {
            "nutrition": pd.DataFrame({
                "day": _date_range(30),
                "calories": [2200] * 30,
                "protein": [160] * 30,
                "calcium": [900] * 30,
                "vitamin_c": [80] * 30,
                "iron": [10] * 30,
                "fiber": [28] * 30,
            }),
            "body_composition": pd.DataFrame({
                "day": [pd.Timestamp("2026-01-01")],
                "weight_kg": [85],
                "bmr": [1850],
            }),
            "activity": pd.DataFrame({
                "day": _date_range(30),
                "active_calories": [500] * 30,
            }),
        }
        result = _score_nutrition(datasets)
        assert result["available"] is True
        assert result["score"] > 0

    def test_unavailable_without_data(self):
        result = _score_nutrition({})
        assert result["available"] is False


class TestHormonalScorer:
    def test_scores_with_bloodwork(self):
        datasets = {
            "bloodwork": pd.DataFrame({
                "day": [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-03-01")],
                "testosterone_nmol": [25, 28],
                "free_testosterone_nmol": [0.6, 0.7],
                "oestradiol_pmol": [120, 130],
            }),
        }
        result = _score_hormonal(datasets)
        assert result["available"] is True
        assert result["score"] > 0

    def test_unavailable_without_bloodwork(self):
        result = _score_hormonal({})
        assert result["available"] is False


class TestMetabolicScorer:
    def test_scores_with_mixed_data(self):
        datasets = {
            "bloodwork": pd.DataFrame({
                "day": [pd.Timestamp("2026-01-01")],
                "hba1c_mmol": [35],
                "cholesterol_hdl_ratio": [3.2],
            }),
            "body_composition": pd.DataFrame({
                "day": pd.date_range("2026-01-01", periods=5, freq="14D"),
                "body_fat_pct": [18, 17.5, 17, 16.5, 16],
                "bmr_score": [7.5, 7.6, 7.7, 7.8, 7.9],
            }),
        }
        result = _score_metabolic(datasets)
        assert result["available"] is True
        assert result["score"] > 0


# ── Composite scoring ──


class TestComputeHealthScreening:
    def test_returns_complete_structure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.screening.VO2MAX_PATH", tmp_path / "vo2max.json")

        datasets = {
            "sleep": pd.DataFrame({
                "day": _date_range(30),
                "score": [75] * 30,
                "deep_sleep_duration": [6000] * 30,
                "total_sleep_duration": [28800] * 30,
            }),
            "readiness": pd.DataFrame({
                "day": _date_range(30),
                "score": [80] * 30,
                "contributors.hrv_balance": [65] * 30,
                "contributors.resting_heart_rate": [70] * 30,
            }),
            "stress": pd.DataFrame({
                "day": _date_range(30),
                "stress_high": [40] * 30,
                "recovery_high": [60] * 30,
            }),
            "spo2": pd.DataFrame({
                "day": _date_range(30),
                "spo2_percentage.average": [97.5] * 30,
            }),
        }
        result = compute_health_screening(datasets)

        assert "overall_score" in result
        assert 0 <= result["overall_score"] <= 100
        assert result["overall_trend"] in ("improving", "stable", "declining")
        assert 0 <= result["data_completeness"] <= 1
        assert len(result["domains"]) == 7
        assert isinstance(result["risk_factors"], list)
        assert isinstance(result["interventions"], list)
        assert isinstance(result["vo2max_history"], list)

    def test_handles_empty_datasets(self, tmp_path, monkeypatch):
        # Use an empty vo2max file so cardiovascular has no data either
        test_path = tmp_path / "vo2max.json"
        test_path.write_text("[]")
        monkeypatch.setattr("src.screening.VO2MAX_PATH", test_path)
        result = compute_health_screening({})

        assert result["overall_score"] == 0
        assert result["data_completeness"] == 0
        assert all(not d["available"] for d in result["domains"])

    def test_weight_redistribution(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.screening.VO2MAX_PATH", tmp_path / "vo2max.json")

        # Only sleep data available
        datasets = {
            "sleep": pd.DataFrame({
                "day": _date_range(30),
                "score": [80] * 30,
                "deep_sleep_duration": [6000] * 30,
                "total_sleep_duration": [28800] * 30,
            }),
            "readiness": pd.DataFrame({
                "day": _date_range(30),
                "score": [80] * 30,
            }),
            "stress": pd.DataFrame({
                "day": _date_range(30),
                "stress_high": [40] * 30,
                "recovery_high": [60] * 30,
            }),
        }
        result = compute_health_screening(datasets)

        # Sleep/recovery should be available, others not
        available = [d for d in result["domains"] if d["available"]]
        assert len(available) >= 1
        # Overall score should reflect only available domains
        assert result["overall_score"] > 0

    def test_vo2max_included_when_present(self, tmp_path, monkeypatch):
        test_path = tmp_path / "vo2max.json"
        monkeypatch.setattr("src.screening.VO2MAX_PATH", test_path)

        save_vo2max([{"date": "2026-01-06", "value": 46, "method": "manual"}])

        datasets = {
            "readiness": pd.DataFrame({
                "day": _date_range(30),
                "score": [80] * 30,
                "contributors.hrv_balance": [65] * 30,
                "contributors.resting_heart_rate": [70] * 30,
            }),
            "spo2": pd.DataFrame({
                "day": _date_range(30),
                "spo2_percentage.average": [97.5] * 30,
            }),
        }
        result = compute_health_screening(datasets)

        assert result["vo2max"] is not None
        assert result["vo2max"]["value"] == 46
        assert result["vo2max"]["category"] == "Superior"

        # Cardiovascular should be available since we have VO2 Max + readiness + spo2
        cardio = next(d for d in result["domains"] if d["name"] == "cardiovascular")
        assert cardio["available"] is True
