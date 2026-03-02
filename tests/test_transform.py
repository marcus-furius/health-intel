"""Tests for src/transform.py — data transformation pipeline."""

import json

import pandas as pd
import pytest

from src.transform import (
    _load_all_json,
    _load_raw_json,
    transform_boditrax,
    transform_hevy_workouts,
    transform_mfp,
    transform_mfp_weight,
    transform_oura_activity,
    transform_oura_readiness,
    transform_oura_sleep,
    transform_oura_stress,
)


# --- Helper functions ---


def test_load_raw_json_returns_most_recent(tmp_path):
    """Two JSON files — the most recent (by name sort) should be loaded."""
    old = [{"day": "2026-01-01", "score": 70}]
    new = [{"day": "2026-02-01", "score": 85}]
    (tmp_path / "sleep_2026-01-01_2026-01-31.json").write_text(json.dumps(old))
    (tmp_path / "sleep_2026-02-01_2026-02-28.json").write_text(json.dumps(new))

    result = _load_raw_json(tmp_path, "sleep_*.json")
    assert len(result) == 1
    assert result[0]["score"] == 85


def test_load_raw_json_empty_dir(tmp_path):
    """No matching files → empty list."""
    result = _load_raw_json(tmp_path, "sleep_*.json")
    assert result == []


def test_load_all_json_combines_files(tmp_path):
    """Two files → all records combined."""
    a = [{"date": "2026-01-01"}, {"date": "2026-01-02"}]
    b = [{"date": "2026-02-01"}]
    (tmp_path / "mfp_diary_2026-01.json").write_text(json.dumps(a))
    (tmp_path / "mfp_diary_2026-02.json").write_text(json.dumps(b))

    result = _load_all_json(tmp_path, "mfp_diary_*.json")
    assert len(result) == 3


# --- Oura transforms ---


def _write_oura_json(raw_dir, endpoint, records):
    """Helper to write Oura JSON files in the expected location."""
    oura_dir = raw_dir / "oura"
    oura_dir.mkdir(parents=True, exist_ok=True)
    filepath = oura_dir / f"{endpoint}_2026-01-01_2026-01-31.json"
    filepath.write_text(json.dumps(records))


def test_transform_oura_sleep_basic(tmp_path):
    records = [
        {"day": "2026-01-01", "score": 75, "id": "a"},
        {"day": "2026-01-02", "score": 80, "id": "b"},
        {"day": "2026-01-03", "score": 70, "id": "c"},
        {"day": "2026-01-04", "score": 85, "id": "d"},
        {"day": "2026-01-05", "score": 72, "id": "e"},
    ]
    _write_oura_json(tmp_path, "daily_sleep", records)
    df = transform_oura_sleep(tmp_path)

    assert len(df) == 5
    assert pd.api.types.is_datetime64_any_dtype(df["day"])
    assert "score" in df.columns


def test_transform_oura_sleep_empty(tmp_path):
    (tmp_path / "oura").mkdir(parents=True, exist_ok=True)
    df = transform_oura_sleep(tmp_path)
    assert df.empty


def test_transform_oura_readiness_basic(tmp_path):
    records = [
        {"day": "2026-01-01", "score": 80},
        {"day": "2026-01-02", "score": 75},
        {"day": "2026-01-03", "score": 82},
    ]
    _write_oura_json(tmp_path, "daily_readiness", records)
    df = transform_oura_readiness(tmp_path)

    assert len(df) == 3
    assert pd.api.types.is_datetime64_any_dtype(df["day"])
    assert "score" in df.columns


def test_transform_oura_activity_basic(tmp_path):
    records = [
        {"day": "2026-01-01", "steps": 8000},
        {"day": "2026-01-02", "steps": 10000},
        {"day": "2026-01-03", "steps": 6500},
    ]
    _write_oura_json(tmp_path, "daily_activity", records)
    df = transform_oura_activity(tmp_path)

    assert len(df) == 3
    assert "steps" in df.columns


def test_transform_oura_stress_converts_seconds(tmp_path):
    """Values > 300 median should be divided by 60 (seconds → minutes)."""
    records = [
        {"day": f"2026-01-{i+1:02d}", "stress_high": 3600, "recovery_high": 1800}
        for i in range(5)
    ]
    _write_oura_json(tmp_path, "daily_stress", records)
    df = transform_oura_stress(tmp_path)

    assert df["stress_high"].iloc[0] == 60.0
    assert df["recovery_high"].iloc[0] == 30.0


def test_transform_oura_stress_empty(tmp_path):
    (tmp_path / "oura").mkdir(parents=True, exist_ok=True)
    df = transform_oura_stress(tmp_path)
    assert df.empty


# --- Hevy transforms ---


def _write_hevy_json(raw_dir, endpoint, records):
    hevy_dir = raw_dir / "hevy"
    hevy_dir.mkdir(parents=True, exist_ok=True)
    filepath = hevy_dir / f"{endpoint}_2026-01-01_2026-01-31.json"
    filepath.write_text(json.dumps(records))


def test_transform_hevy_basic(tmp_path):
    workouts = [{
        "start_time": "2026-01-15T10:00:00",
        "title": "Push Day",
        "duration_seconds": 3600,
        "exercises": [
            {
                "title": "Bench Press",
                "exercise_template_id": "tmpl_1",
                "sets": [
                    {"weight_kg": 80, "reps": 8, "type": "normal"},
                    {"weight_kg": 80, "reps": 6, "type": "normal"},
                ],
            },
            {
                "title": "OHP",
                "exercise_template_id": "tmpl_2",
                "sets": [
                    {"weight_kg": 40, "reps": 10, "type": "normal"},
                ],
            },
        ],
    }]
    templates = [
        {"id": "tmpl_1", "primary_muscle_group": "chest"},
        {"id": "tmpl_2", "primary_muscle_group": "shoulders"},
    ]
    _write_hevy_json(tmp_path, "workouts", workouts)
    _write_hevy_json(tmp_path, "exercise_templates", templates)

    df = transform_hevy_workouts(tmp_path)

    assert len(df) == 3  # 2 sets bench + 1 set OHP
    assert df["volume"].iloc[0] == 80 * 8
    assert df["muscle_group"].iloc[0] == "chest"


def test_transform_hevy_missing_template(tmp_path):
    """Unknown template_id → muscle_group defaults to 'other'."""
    workouts = [{
        "start_time": "2026-01-15T10:00:00",
        "title": "Test",
        "exercises": [{
            "title": "Mystery Lift",
            "exercise_template_id": "unknown_id",
            "sets": [{"weight_kg": 50, "reps": 10, "type": "normal"}],
        }],
    }]
    _write_hevy_json(tmp_path, "workouts", workouts)
    # No exercise_templates file at all

    df = transform_hevy_workouts(tmp_path)
    assert df["muscle_group"].iloc[0] == "other"


def test_transform_hevy_zero_weight(tmp_path):
    """Zero weight should produce volume=0 without crashing."""
    workouts = [{
        "start_time": "2026-01-15T10:00:00",
        "title": "Test",
        "exercises": [{
            "title": "Bodyweight Dips",
            "exercise_template_id": "",
            "sets": [{"weight_kg": 0, "reps": 15, "type": "normal"}],
        }],
    }]
    _write_hevy_json(tmp_path, "workouts", workouts)

    df = transform_hevy_workouts(tmp_path)
    assert len(df) == 1
    assert df["volume"].iloc[0] == 0


def test_transform_hevy_empty(tmp_path):
    (tmp_path / "hevy").mkdir(parents=True, exist_ok=True)
    df = transform_hevy_workouts(tmp_path)
    assert df.empty


# --- Boditrax transforms ---


def test_transform_boditrax_prefers_native_csv(tmp_path):
    """When native CSV exists alongside stale JSON, CSV is preferred."""
    bt_dir = tmp_path / "boditrax"
    bt_dir.mkdir(parents=True, exist_ok=True)

    # Write a stale JSON with different weight
    stale_json = [{"date": "2026-01-01", "weight_kg": 90.0}]
    (bt_dir / "scans_2026-01-01_2026-01-31.json").write_text(json.dumps(stale_json))

    # Write a simple wide-format CSV (will be picked up as fallback)
    csv_content = "date,weight_kg,body_fat_pct\n2026-01-15,84.5,17.5\n"
    (bt_dir / "boditrax_scan_2026-01.csv").write_text(csv_content)

    # The function tries native BoditraxAccount_* CSV first, then simple CSV, then JSON.
    # With only a simple CSV and a JSON, the simple CSV should win.
    df = transform_boditrax(tmp_path)
    assert len(df) == 1
    assert df["weight_kg"].iloc[0] == pytest.approx(84.5)


def test_transform_boditrax_empty(tmp_path):
    (tmp_path / "boditrax").mkdir(parents=True, exist_ok=True)
    df = transform_boditrax(tmp_path)
    assert df.empty


# --- MFP transforms ---


def test_transform_mfp_basic(tmp_path):
    mfp_dir = tmp_path / "mfp"
    mfp_dir.mkdir(parents=True, exist_ok=True)

    diary = [
        {"date": "2026-01-15", "calories": 2100, "protein": 150, "carbohydrates": 250, "fat": 70},
        {"date": "2026-01-16", "calories": 2300, "protein": 160, "carbohydrates": 260, "fat": 75},
    ]
    (mfp_dir / "mfp_diary_2026-01.json").write_text(json.dumps(diary))

    df = transform_mfp(tmp_path)
    assert len(df) == 2
    assert pd.api.types.is_datetime64_any_dtype(df["day"])
    assert df["calories"].dtype.kind in ("i", "f")  # numeric


def test_transform_mfp_zero_calorie_days_preserved(tmp_path):
    """Zero-calorie days must not be dropped."""
    mfp_dir = tmp_path / "mfp"
    mfp_dir.mkdir(parents=True, exist_ok=True)

    diary = [
        {"date": "2026-01-15", "calories": 0, "protein": 0, "fat": 0, "carbohydrates": 0},
        {"date": "2026-01-16", "calories": 2100, "protein": 150, "fat": 70, "carbohydrates": 250},
    ]
    (mfp_dir / "mfp_diary_2026-01.json").write_text(json.dumps(diary))

    df = transform_mfp(tmp_path)
    assert len(df) == 2  # both days preserved


def test_transform_mfp_weight_basic(tmp_path):
    mfp_dir = tmp_path / "mfp"
    mfp_dir.mkdir(parents=True, exist_ok=True)

    measurements = [
        {"date": "2026-01-10", "weight_kg": 84.5},
        {"date": "2026-01-17", "weight_kg": 84.2},
    ]
    (mfp_dir / "mfp_measurements_2026-01-01_2026-01-31.json").write_text(json.dumps(measurements))

    df = transform_mfp_weight(tmp_path)
    assert len(df) == 2
    assert df["weight_kg"].dtype == float


def test_transform_mfp_empty(tmp_path):
    (tmp_path / "mfp").mkdir(parents=True, exist_ok=True)
    df = transform_mfp(tmp_path)
    assert df.empty
