"""Shared fixtures for the health-intel test suite."""

import pandas as pd
import pytest


def _date_range(n: int, start: str = "2026-01-01") -> list[pd.Timestamp]:
    return pd.date_range(start, periods=n, freq="D").tolist()


@pytest.fixture
def sample_sleep_df() -> pd.DataFrame:
    dates = _date_range(30)
    return pd.DataFrame({
        "day": dates,
        "score": [70 + (i % 15) for i in range(30)],
    })


@pytest.fixture
def sample_readiness_df() -> pd.DataFrame:
    dates = _date_range(30)
    return pd.DataFrame({
        "day": dates,
        "score": [65 + (i % 20) for i in range(30)],
    })


@pytest.fixture
def sample_activity_df() -> pd.DataFrame:
    dates = _date_range(30)
    return pd.DataFrame({
        "day": dates,
        "steps": [5000 + i * 100 for i in range(30)],
    })


@pytest.fixture
def sample_workouts_df() -> pd.DataFrame:
    dates = _date_range(30)
    rows = []
    exercises = ["Bench Press", "Squat", "Deadlift"]
    muscle_groups = ["chest", "quadriceps", "hamstrings"]
    for i in range(30):
        idx = i % 3
        rows.append({
            "day": dates[i],
            "exercise": exercises[idx],
            "muscle_group": muscle_groups[idx],
            "weight_kg": 60 + i,
            "reps": 8,
            "volume": (60 + i) * 8,
            "set_type": "normal",
        })
    return pd.DataFrame(rows)


@pytest.fixture
def sample_nutrition_df() -> pd.DataFrame:
    dates = _date_range(30)
    return pd.DataFrame({
        "day": dates,
        "calories": [2200 + (i * 10) for i in range(30)],
        "protein": [150 + (i % 10) for i in range(30)],
        "carbohydrates": [250 + (i % 15) for i in range(30)],
        "fat": [70 + (i % 8) for i in range(30)],
        "sodium": [2000 + i * 20 for i in range(30)],
        "sugar": [30 + (i % 5) for i in range(30)],
        "fiber": [25 + (i % 4) for i in range(30)],
        "meals": [[{"name": "Lunch", "calories": 800}]] * 30,
    })


@pytest.fixture
def sample_body_comp_df() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=5, freq="14D").tolist()
    return pd.DataFrame({
        "day": dates,
        "weight_kg": [85.0, 84.5, 84.2, 83.8, 83.5],
        "body_fat_pct": [18.0, 17.8, 17.5, 17.3, 17.0],
        "muscle_mass_kg": [38.0, 38.2, 38.3, 38.5, 38.6],
        "bmr": [1850, 1845, 1840, 1838, 1835],
    })


@pytest.fixture
def sample_stress_df() -> pd.DataFrame:
    dates = _date_range(30)
    return pd.DataFrame({
        "day": dates,
        "stress_high": [45.0 + (i % 10) for i in range(30)],
        "recovery_high": [60.0 + (i % 12) for i in range(30)],
        "day_summary": ["restored" if i % 3 == 0 else "normal" for i in range(30)],
    })


@pytest.fixture
def sample_datasets(
    sample_sleep_df,
    sample_readiness_df,
    sample_activity_df,
    sample_workouts_df,
    sample_nutrition_df,
    sample_body_comp_df,
    sample_stress_df,
) -> dict[str, pd.DataFrame]:
    return {
        "sleep": sample_sleep_df,
        "readiness": sample_readiness_df,
        "activity": sample_activity_df,
        "workouts": sample_workouts_df,
        "nutrition": sample_nutrition_df,
        "body_composition": sample_body_comp_df,
        "stress": sample_stress_df,
    }


# --- MFP CSV fixtures ---

_NUTRITION_CSV = """\
Date,Meal,Calories,Fat (g),Saturated Fat,Polyunsaturated Fat,Monounsaturated Fat,Trans Fat,Cholesterol,Sodium (mg),Potassium,Carbohydrates (g),Fiber,Sugar,Protein (g),Vitamin A,Vitamin C,Calcium,Iron,Note
2026-01-15,Breakfast,450,15,5,3,4,0,120,600,400,55,4,10,25,10,15,20,3,
2026-01-15,Lunch,700,25,8,5,8,0,80,900,500,65,6,8,40,5,20,15,4,
2026-01-15,Dinner,600,20,6,4,7,0,90,700,450,50,5,6,35,8,10,18,5,
2026-01-15,Snacks,200,8,3,1,2,0,30,200,150,20,2,12,10,2,5,8,1,
2026-01-16,Breakfast,400,12,4,2,3,0,100,500,350,50,3,8,22,8,12,16,2,
2026-01-16,Lunch,650,22,7,4,7,0,75,850,480,60,5,7,38,4,18,14,3,
"""

_MEASUREMENT_CSV = """\
Date,Weight
2026-01-10,84.5
2026-01-17,84.2
2026-01-24,83.9
"""

_EXERCISE_CSV = """\
Date,Exercise,Type,Exercise Calories,Exercise Minutes,Sets,Reps Per Set,Kilograms,Steps,Note
2026-01-15,Walking,Cardiovascular,150,30,,,,5000,Morning walk
2026-01-16,Bench Press,Strength,200,45,3,10,80,,
"""


@pytest.fixture
def mfp_nutrition_csv(tmp_path):
    path = tmp_path / "Nutrition-Summary.csv"
    path.write_text(_NUTRITION_CSV)
    return path


@pytest.fixture
def mfp_measurement_csv(tmp_path):
    path = tmp_path / "Measurement-Summary.csv"
    path.write_text(_MEASUREMENT_CSV)
    return path


@pytest.fixture
def mfp_exercise_csv(tmp_path):
    path = tmp_path / "Exercise-Summary.csv"
    path.write_text(_EXERCISE_CSV)
    return path
