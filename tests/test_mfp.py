"""Tests for src/sources/mfp.py — MyFitnessPal CSV export parsing."""

import json

import pytest

from src.sources.mfp import MfpSource


@pytest.fixture
def mfp():
    return MfpSource()


# --- Directory / file finding ---


def test_find_export_dir_most_recent(tmp_path, mfp):
    """Two export dirs — picks the newest by sorted name."""
    (tmp_path / "File-Export-2024-01-01-to-2024-06-30").mkdir()
    (tmp_path / "File-Export-2025-01-01-to-2025-06-30").mkdir()

    result = mfp._find_export_dir(tmp_path)
    assert result is not None
    assert "2025" in result.name


def test_find_export_dir_none(tmp_path, mfp):
    """No export dirs → None."""
    result = mfp._find_export_dir(tmp_path)
    assert result is None


def test_find_csv_match(tmp_path, mfp):
    (tmp_path / "Nutrition-Summary-2026-01.csv").write_text("header\n")
    result = mfp._find_csv(tmp_path, "Nutrition-Summary")
    assert result is not None
    assert result.name.startswith("Nutrition-Summary")


def test_find_csv_no_match(tmp_path, mfp):
    result = mfp._find_csv(tmp_path, "Nonexistent-File")
    assert result is None


# --- Nutrition parsing ---


def test_parse_nutrition_aggregates_meals(mfp, mfp_nutrition_csv):
    """4 meal rows for 2026-01-15 should aggregate to 1 daily entry."""
    entries = mfp._parse_nutrition(mfp_nutrition_csv, "2026-01-01", "2026-12-31")
    day_15 = [e for e in entries if e["date"] == "2026-01-15"]
    assert len(day_15) == 1
    assert day_15[0]["calories"] == 450 + 700 + 600 + 200


def test_parse_nutrition_date_filtering(mfp, mfp_nutrition_csv):
    """Out-of-range dates should be excluded."""
    entries = mfp._parse_nutrition(mfp_nutrition_csv, "2026-01-16", "2026-01-16")
    assert len(entries) == 1
    assert entries[0]["date"] == "2026-01-16"


def test_parse_nutrition_preserves_meal_breakdown(mfp, mfp_nutrition_csv):
    """Each daily entry should have a 'meals' list with correct meal names."""
    entries = mfp._parse_nutrition(mfp_nutrition_csv, "2026-01-01", "2026-12-31")
    day_15 = [e for e in entries if e["date"] == "2026-01-15"][0]
    meal_names = [m["name"] for m in day_15["meals"]]
    assert "Breakfast" in meal_names
    assert "Lunch" in meal_names
    assert "Dinner" in meal_names
    assert "Snacks" in meal_names


def test_parse_nutrition_missing_columns(mfp, tmp_path):
    """CSV with only a subset of columns should still parse."""
    csv = "Date,Meal,Calories,Protein (g)\n2026-01-15,Lunch,800,40\n"
    path = tmp_path / "Nutrition-Partial.csv"
    path.write_text(csv)
    entries = mfp._parse_nutrition(path, "2026-01-01", "2026-12-31")
    assert len(entries) == 1
    assert entries[0]["calories"] == 800
    assert entries[0]["protein"] == 40


def test_parse_nutrition_empty_csv(mfp, tmp_path):
    """CSV with only headers → empty list."""
    csv = "Date,Meal,Calories,Fat (g),Protein (g)\n"
    path = tmp_path / "Nutrition-Empty.csv"
    path.write_text(csv)
    entries = mfp._parse_nutrition(path, "2026-01-01", "2026-12-31")
    assert entries == []


# --- Measurement parsing ---


def test_parse_measurements_basic(mfp, mfp_measurement_csv):
    entries = mfp._parse_measurements(mfp_measurement_csv, "2026-01-01", "2026-12-31")
    assert len(entries) == 3
    assert entries[0]["weight_kg"] == 84.5


def test_parse_measurements_date_filtering(mfp, mfp_measurement_csv):
    entries = mfp._parse_measurements(mfp_measurement_csv, "2026-01-15", "2026-01-20")
    assert len(entries) == 1
    assert entries[0]["date"] == "2026-01-17"


# --- Exercise parsing ---


def test_parse_exercise_basic(mfp, mfp_exercise_csv):
    entries = mfp._parse_exercise(mfp_exercise_csv, "2026-01-01", "2026-12-31")
    assert len(entries) == 2
    assert entries[0]["exercise"] == "Walking"
    assert isinstance(entries[0]["exercise_calories"], (int, float))


def test_parse_exercise_nan_excluded(mfp, mfp_exercise_csv):
    """NaN values (e.g. missing Sets for cardio) should not appear in output dicts."""
    entries = mfp._parse_exercise(mfp_exercise_csv, "2026-01-01", "2026-12-31")
    walking = entries[0]
    # Walking row has no Sets, Reps Per Set, Kilograms — these should be absent
    assert "sets" not in walking
    assert "reps_per_set" not in walking
    assert "kilograms" not in walking


# --- save_raw ---


def test_save_raw_monthly_batching(mfp, tmp_path):
    """60 days of diary spanning 2 months → 2 monthly JSON files."""
    diary = [{"date": f"2026-01-{d+1:02d}", "calories": 2000} for d in range(31)]
    diary += [{"date": f"2026-02-{d+1:02d}", "calories": 2100} for d in range(28)]
    data = {"diary": diary, "measurements": [], "exercise": []}

    counts = mfp.save_raw(data, tmp_path, "2026-01-01", "2026-02-28")

    assert (tmp_path / "mfp_diary_2026-01.json").exists()
    assert (tmp_path / "mfp_diary_2026-02.json").exists()
    assert counts["diary"] == 59


def test_save_raw_metadata(mfp, tmp_path):
    data = {"diary": [{"date": "2026-01-01", "calories": 2000}], "measurements": [], "exercise": []}
    mfp.save_raw(data, tmp_path, "2026-01-01", "2026-01-31")

    meta_path = tmp_path / "_metadata.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert "source" in meta
    assert meta["source"] == "mfp"
    assert "record_counts" in meta
    assert "last_sync" in meta
