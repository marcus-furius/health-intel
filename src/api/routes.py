"""API routes — all endpoints in one file (data is small)."""

import logging
from datetime import date
from typing import Any

import pandas as pd
from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.correlate import compute_correlations
from src.report import _corr_strength, _recent_trend, compute_alerts

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic Response Models ──


class SparkPoint(BaseModel):
    date: str
    value: float | None


class MetricSummary(BaseModel):
    label: str
    value: float | None
    unit: str
    trend: float | None  # slope
    sparkline: list[SparkPoint]


class AlertOut(BaseModel):
    severity: str
    title: str
    detail: str
    intervention: str


class OverviewResponse(BaseModel):
    metrics: list[MetricSummary]
    alerts: list[AlertOut]
    alert_counts: dict[str, int]


class CorrelationItem(BaseModel):
    key: str
    x_label: str
    y_label: str
    r_value: float | None
    strength: str
    points: list[dict[str, Any]]


class CorrelationsResponse(BaseModel):
    correlations: list[CorrelationItem]


# ── Helpers ──


def _get_datasets() -> dict[str, pd.DataFrame]:
    from src.api.server import datasets
    return datasets


def _filter_dates(df: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
    if df.empty or "day" not in df.columns:
        return df
    out = df.copy()
    if start:
        out = out[out["day"] >= pd.Timestamp(start)]
    if end:
        out = out[out["day"] <= pd.Timestamp(end)]
    return out


def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert DataFrame to JSON-safe records (NaN → None)."""
    import math
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    records = out.to_dict(orient="records")
    # Replace NaN/inf with None for JSON compliance
    for row in records:
        for key, val in row.items():
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                row[key] = None
    return records


def _sparkline(df: pd.DataFrame, col: str, days: int = 30) -> list[SparkPoint]:
    if df.empty or col not in df.columns or "day" not in df.columns:
        return []
    recent = df.sort_values("day").tail(days)
    points = []
    for _, row in recent.iterrows():
        val = row[col]
        points.append(SparkPoint(
            date=row["day"].strftime("%Y-%m-%d") if hasattr(row["day"], "strftime") else str(row["day"]),
            value=float(val) if pd.notna(val) else None,
        ))
    return points


# ── Endpoints ──


@router.get("/overview", response_model=OverviewResponse)
def overview():
    ds = _get_datasets()
    correlations = compute_correlations(ds)
    raw_alerts = compute_alerts(ds, correlations)

    metrics: list[MetricSummary] = []

    # Sleep score
    sleep_df = ds.get("sleep", pd.DataFrame())
    if not sleep_df.empty and "score" in sleep_df.columns:
        recent = sleep_df.sort_values("day").tail(30)
        metrics.append(MetricSummary(
            label="Sleep Score",
            value=round(recent["score"].mean(), 1),
            unit="avg",
            trend=_recent_trend(sleep_df.sort_values("day")["score"]),
            sparkline=_sparkline(sleep_df, "score"),
        ))

    # Readiness score
    readiness_df = ds.get("readiness", pd.DataFrame())
    if not readiness_df.empty and "score" in readiness_df.columns:
        recent = readiness_df.sort_values("day").tail(30)
        metrics.append(MetricSummary(
            label="Readiness",
            value=round(recent["score"].mean(), 1),
            unit="avg",
            trend=_recent_trend(readiness_df.sort_values("day")["score"]),
            sparkline=_sparkline(readiness_df, "score"),
        ))

    # Steps
    activity_df = ds.get("activity", pd.DataFrame())
    steps_col = None
    if not activity_df.empty:
        steps_col = next((c for c in ["steps", "total_steps"] if c in activity_df.columns), None)
    if steps_col:
        recent = activity_df.sort_values("day").tail(30)
        metrics.append(MetricSummary(
            label="Daily Steps",
            value=round(recent[steps_col].mean()),
            unit="avg",
            trend=_recent_trend(activity_df.sort_values("day")[steps_col]),
            sparkline=_sparkline(activity_df, steps_col),
        ))

    # Calories
    nutrition_df = ds.get("nutrition", pd.DataFrame())
    if not nutrition_df.empty and "calories" in nutrition_df.columns:
        logged = nutrition_df[nutrition_df["calories"] > 0]
        recent = logged.sort_values("day").tail(30)
        metrics.append(MetricSummary(
            label="Avg Calories",
            value=round(recent["calories"].mean()),
            unit="kcal",
            trend=_recent_trend(logged.sort_values("day")["calories"]),
            sparkline=_sparkline(nutrition_df, "calories"),
        ))

    # Training volume per week
    workouts_df = ds.get("workouts", pd.DataFrame())
    if not workouts_df.empty and "volume" in workouts_df.columns:
        daily_vol = workouts_df.groupby("day")["volume"].sum().reset_index()
        daily_vol = daily_vol.sort_values("day")
        if not daily_vol.empty:
            recent_weeks = daily_vol.tail(28)
            total_recent = recent_weeks["volume"].sum()
            weeks = max((recent_weeks["day"].max() - recent_weeks["day"].min()).days / 7, 1)
            metrics.append(MetricSummary(
                label="Volume/Week",
                value=round(total_recent / weeks),
                unit="kg",
                trend=_recent_trend(daily_vol["volume"]),
                sparkline=_sparkline(daily_vol, "volume"),
            ))

    # Weight
    body_df = ds.get("body_composition", pd.DataFrame())
    if not body_df.empty and "weight_kg" in body_df.columns:
        latest = body_df.sort_values("day").iloc[-1]
        metrics.append(MetricSummary(
            label="Weight",
            value=round(float(latest["weight_kg"]), 1),
            unit="kg",
            trend=_recent_trend(body_df.sort_values("day")["weight_kg"], window=len(body_df)),
            sparkline=_sparkline(body_df, "weight_kg", days=100),
        ))

    alerts_out = [AlertOut(**a) for a in raw_alerts]
    counts: dict[str, int] = {}
    for a in raw_alerts:
        counts[a["severity"]] = counts.get(a["severity"], 0) + 1

    return OverviewResponse(metrics=metrics, alerts=alerts_out, alert_counts=counts)


@router.get("/sleep")
def sleep_data(start: date | None = Query(None), end: date | None = Query(None)):
    ds = _get_datasets()
    df = _filter_dates(ds.get("sleep", pd.DataFrame()), start, end)
    return {"data": _df_to_records(df)}


@router.get("/readiness")
def readiness_data(start: date | None = Query(None), end: date | None = Query(None)):
    ds = _get_datasets()
    df = _filter_dates(ds.get("readiness", pd.DataFrame()), start, end)
    return {"data": _df_to_records(df)}


@router.get("/activity")
def activity_data(start: date | None = Query(None), end: date | None = Query(None)):
    ds = _get_datasets()
    df = _filter_dates(ds.get("activity", pd.DataFrame()), start, end)
    # Select useful columns only (activity has huge met.items)
    keep = ["day", "score", "steps", "active_calories", "total_calories",
            "high_activity_time", "medium_activity_time", "low_activity_time",
            "sedentary_time", "resting_time", "equivalent_walking_distance",
            "meters_to_target", "target_calories"]
    available = [c for c in keep if c in df.columns]
    return {"data": _df_to_records(df[available])}


@router.get("/stress")
def stress_data(start: date | None = Query(None), end: date | None = Query(None)):
    ds = _get_datasets()
    df = _filter_dates(ds.get("stress", pd.DataFrame()), start, end)
    return {"data": _df_to_records(df)}


@router.get("/spo2")
def spo2_data(start: date | None = Query(None), end: date | None = Query(None)):
    ds = _get_datasets()
    df = _filter_dates(ds.get("spo2", pd.DataFrame()), start, end)
    return {"data": _df_to_records(df)}


@router.get("/heartrate")
def heartrate_data(start: date | None = Query(None), end: date | None = Query(None)):
    ds = _get_datasets()
    df = ds.get("heartrate", pd.DataFrame())
    if not df.empty and "day" in df.columns:
        df = _filter_dates(df, start, end)
    return {"data": _df_to_records(df)}


@router.get("/training")
def training_data(start: date | None = Query(None), end: date | None = Query(None)):
    ds = _get_datasets()
    df = _filter_dates(ds.get("workouts", pd.DataFrame()), start, end)
    if df.empty:
        return {"data": [], "daily": []}

    # Daily summaries
    daily = df.groupby("day").agg(
        sessions=("workout_title", "nunique"),
        total_volume=("volume", "sum"),
        total_sets=("volume", "count"),
        exercises=("exercise", "nunique"),
    ).reset_index()
    daily = daily.sort_values("day")

    return {
        "data": _df_to_records(df),
        "daily": _df_to_records(daily),
    }


@router.get("/training/exercises")
def training_exercises():
    ds = _get_datasets()
    df = ds.get("workouts", pd.DataFrame())
    if df.empty:
        return {"data": []}

    exercise_history = df.groupby(["day", "exercise"]).agg(
        volume=("volume", "sum"),
        sets=("volume", "count"),
        max_weight=("weight_kg", "max"),
        total_reps=("reps", "sum"),
    ).reset_index().sort_values(["exercise", "day"])

    return {"data": _df_to_records(exercise_history)}


@router.get("/training/muscle-groups")
def training_muscle_groups():
    ds = _get_datasets()
    df = ds.get("workouts", pd.DataFrame())
    if df.empty:
        return {"data": []}

    groups = df.groupby("muscle_group").agg(
        total_volume=("volume", "sum"),
        total_sets=("volume", "count"),
    ).reset_index().sort_values("total_volume", ascending=False)

    return {"data": _df_to_records(groups)}


@router.get("/nutrition")
def nutrition_data(start: date | None = Query(None), end: date | None = Query(None)):
    ds = _get_datasets()
    df = _filter_dates(ds.get("nutrition", pd.DataFrame()), start, end)
    if df.empty:
        return {"data": []}

    # Select core columns (skip raw totals/meals dicts for cleaner JSON)
    keep = ["day", "calories", "protein", "carbohydrates", "fat", "fiber", "sugar",
            "sodium", "saturated_fat", "cholesterol", "potassium",
            "vitamin_a", "vitamin_c", "calcium", "iron"]
    available = [c for c in keep if c in df.columns]
    return {"data": _df_to_records(df[available])}


@router.get("/body-composition")
def body_composition_data():
    ds = _get_datasets()
    df = ds.get("body_composition", pd.DataFrame())
    if df.empty:
        return {"data": []}

    keep = ["day", "weight_kg", "body_fat_pct", "muscle_mass_kg", "fat_mass_kg",
            "water_mass_kg", "bone_mass_kg", "visceral_fat", "metabolic_age",
            "bmr", "bmi", "phase_angle_left_arm", "phase_angle_right_arm"]
    available = [c for c in keep if c in df.columns]
    return {"data": _df_to_records(df[available].sort_values("day"))}


@router.get("/weight")
def weight_data():
    ds = _get_datasets()
    frames = []

    body_df = ds.get("body_composition", pd.DataFrame())
    if not body_df.empty and "weight_kg" in body_df.columns:
        bt = body_df[["day", "weight_kg"]].copy()
        bt["source"] = "boditrax"
        frames.append(bt)

    mfp_df = ds.get("mfp_weight", pd.DataFrame())
    if not mfp_df.empty and "weight_kg" in mfp_df.columns:
        mw = mfp_df[["day", "weight_kg"]].copy()
        mw["source"] = "mfp"
        frames.append(mw)

    if not frames:
        return {"data": []}

    combined = pd.concat(frames).sort_values("day")
    return {"data": _df_to_records(combined)}


@router.get("/correlations", response_model=CorrelationsResponse)
def correlations_data():
    ds = _get_datasets()
    raw = compute_correlations(ds)
    items: list[CorrelationItem] = []

    for key, val in raw.items():
        if "correlation" in val and "data" in val:
            corr = val["correlation"]
            data_df = val["data"]
            items.append(CorrelationItem(
                key=key,
                x_label=val.get("x_label", ""),
                y_label=val.get("y_label", ""),
                r_value=round(corr, 3) if corr is not None else None,
                strength=_corr_strength(corr),
                points=_df_to_records(data_df),
            ))

    items.sort(key=lambda i: abs(i.r_value) if i.r_value is not None else 0, reverse=True)
    return CorrelationsResponse(correlations=items)


@router.get("/alerts")
def alerts_data():
    ds = _get_datasets()
    correlations = compute_correlations(ds)
    raw_alerts = compute_alerts(ds, correlations)
    return {"alerts": raw_alerts}


@router.post("/reload")
def reload_data():
    from src.api.server import load_datasets
    import src.api.server as server_mod
    server_mod.datasets = load_datasets()
    return {"status": "ok", "datasets": list(server_mod.datasets.keys())}
