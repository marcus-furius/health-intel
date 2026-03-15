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


class TargetZone(BaseModel):
    min: float | None = None
    max: float | None = None
    label: str | None = None


class MetricSummary(BaseModel):
    label: str
    value: float | None
    unit: str
    trend: float | None  # slope
    sparkline: list[SparkPoint]
    invert_trend: bool = False  # True when "up is bad" (e.g. stress, body fat)
    target: TargetZone | None = None


class AlertOut(BaseModel):
    severity: str
    title: str
    detail: str
    intervention: str
    category: str = ""


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
    lag_days: int = 0
    ci_low: float | None = None
    ci_high: float | None = None
    n_samples: int = 0


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


def _forward_fill_daily(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Expand sparse data to daily frequency with forward-fill."""
    if df.empty or col not in df.columns or "day" not in df.columns:
        return df
    out = df[["day", col]].copy().sort_values("day").drop_duplicates("day")
    idx = pd.date_range(out["day"].min(), out["day"].max(), freq="D")
    out = out.set_index("day").reindex(idx).ffill().reset_index()
    out.columns = ["day", col]
    return out


def _paginate(
    records: list[dict[str, Any]],
    limit: int | None,
    offset: int,
) -> dict[str, Any]:
    """Apply offset/limit to a record list and wrap with pagination metadata."""
    total = len(records)
    sliced = records[offset:]
    if limit is not None:
        sliced = sliced[:limit]
    return {"data": sliced, "total": total, "limit": limit, "offset": offset}


def _aggregate(df: pd.DataFrame, freq: str, num_cols: list[str] | None = None) -> pd.DataFrame:
    """Resample daily data to weekly ('W') or monthly ('ME') frequency.

    Numeric columns are averaged; 'day' becomes the period end date.
    """
    if df.empty or "day" not in df.columns:
        return df
    out = df.copy().sort_values("day").set_index("day")
    # Only aggregate numeric columns
    if num_cols:
        cols = [c for c in num_cols if c in out.columns]
    else:
        cols = list(out.select_dtypes(include="number").columns)
    if not cols:
        return df
    agg = out[cols].resample(freq).mean().dropna(how="all").reset_index()
    # Round for cleaner JSON
    for c in cols:
        if c in agg.columns:
            agg[c] = agg[c].round(2)
    return agg


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
            target=TargetZone(min=7500, label="7.5k+"),
        ))

    # Sedentary time (seconds → hours)
    if not activity_df.empty and "sedentary_time" in activity_df.columns:
        recent_act = activity_df.sort_values("day").tail(30)
        avg_sedentary_hrs = round(recent_act["sedentary_time"].mean() / 3600, 1)
        metrics.append(MetricSummary(
            label="Sedentary",
            value=avg_sedentary_hrs,
            unit="hrs",
            trend=_recent_trend(activity_df.sort_values("day")["sedentary_time"]),
            sparkline=_sparkline(activity_df, "sedentary_time"),
            invert_trend=True,
            target=TargetZone(max=8, label="<8 hrs"),
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

    # Resting Heart Rate
    hr_df = ds.get("heartrate", pd.DataFrame())
    if not hr_df.empty and "hr_min" in hr_df.columns:
        recent = hr_df.sort_values("day").tail(30)
        metrics.append(MetricSummary(
            label="Resting HR",
            value=round(recent["hr_min"].mean(), 1),
            unit="bpm",
            trend=_recent_trend(hr_df.sort_values("day")["hr_min"]),
            sparkline=_sparkline(hr_df, "hr_min"),
            invert_trend=True,
        ))

    # Nutrition compliance
    if not nutrition_df.empty and "calories" in nutrition_df.columns:
        total_days = len(nutrition_df)
        logged_days = len(nutrition_df[nutrition_df["calories"] > 0])
        compliance = round(logged_days / total_days * 100) if total_days else None
        metrics.append(MetricSummary(
            label="Logging",
            value=compliance,
            unit="%",
            trend=None,
            sparkline=[],
        ))

    # Weight (combine Boditrax + MFP for denser sparkline)
    body_df = ds.get("body_composition", pd.DataFrame())
    mfp_wt = ds.get("mfp_weight", pd.DataFrame())
    weight_frames = []
    if not body_df.empty and "weight_kg" in body_df.columns:
        weight_frames.append(body_df[["day", "weight_kg"]])
    if not mfp_wt.empty and "weight_kg" in mfp_wt.columns:
        weight_frames.append(mfp_wt[["day", "weight_kg"]])
    if weight_frames:
        combined_wt = pd.concat(weight_frames).sort_values("day").drop_duplicates("day", keep="first")
        filled_wt = _forward_fill_daily(combined_wt, "weight_kg")
        latest_wt = combined_wt.iloc[-1]
        metrics.append(MetricSummary(
            label="Weight",
            value=round(float(latest_wt["weight_kg"]), 1),
            unit="kg",
            trend=_recent_trend(combined_wt.sort_values("day")["weight_kg"], window=len(combined_wt)),
            sparkline=_sparkline(filled_wt, "weight_kg", days=60),
        ))

    # Caloric Balance: Intake - (BMR + Active Calories)
    bmr = None
    if not body_df.empty and "bmr" in body_df.columns:
        bmr = float(body_df.sort_values("day").iloc[-1]["bmr"])
    active_cal_col = None
    if not activity_df.empty:
        active_cal_col = next((c for c in ["active_calories"] if c in activity_df.columns), None)
    if bmr and active_cal_col and not nutrition_df.empty and "calories" in nutrition_df.columns:
        # Merge nutrition and activity on day
        nut = nutrition_df[nutrition_df["calories"] > 0][["day", "calories"]].copy()
        act = activity_df[["day", active_cal_col]].copy()
        merged = nut.merge(act, on="day", how="inner")
        if not merged.empty:
            merged["balance"] = merged["calories"] - (bmr + merged[active_cal_col])
            recent_bal = merged.sort_values("day").tail(30)
            avg_balance = round(recent_bal["balance"].mean())
            metrics.append(MetricSummary(
                label="Cal Balance",
                value=avg_balance,
                unit="kcal",
                trend=_recent_trend(merged.sort_values("day")["balance"]),
                sparkline=_sparkline(merged, "balance"),
            ))

    alerts_out = [AlertOut(**a) for a in raw_alerts]
    counts: dict[str, int] = {}
    for a in raw_alerts:
        counts[a["severity"]] = counts.get(a["severity"], 0) + 1

    return OverviewResponse(metrics=metrics, alerts=alerts_out, alert_counts=counts)


@router.get("/sleep")
def sleep_data(
    start: date | None = Query(None), end: date | None = Query(None),
    limit: int | None = Query(None, ge=1), offset: int = Query(0, ge=0),
    aggregate: str | None = Query(None, pattern="^(weekly|monthly)$"),
):
    ds = _get_datasets()
    df = _filter_dates(ds.get("sleep", pd.DataFrame()), start, end)
    if aggregate:
        df = _aggregate(df, "W" if aggregate == "weekly" else "ME")
    return _paginate(_df_to_records(df), limit, offset)


@router.get("/readiness")
def readiness_data(
    start: date | None = Query(None), end: date | None = Query(None),
    limit: int | None = Query(None, ge=1), offset: int = Query(0, ge=0),
    aggregate: str | None = Query(None, pattern="^(weekly|monthly)$"),
):
    ds = _get_datasets()
    df = _filter_dates(ds.get("readiness", pd.DataFrame()), start, end)
    if aggregate:
        df = _aggregate(df, "W" if aggregate == "weekly" else "ME")
    return _paginate(_df_to_records(df), limit, offset)


@router.get("/activity")
def activity_data(
    start: date | None = Query(None), end: date | None = Query(None),
    limit: int | None = Query(None, ge=1), offset: int = Query(0, ge=0),
    aggregate: str | None = Query(None, pattern="^(weekly|monthly)$"),
):
    ds = _get_datasets()
    df = _filter_dates(ds.get("activity", pd.DataFrame()), start, end)
    # Select useful columns only (activity has huge met.items)
    keep = ["day", "score", "steps", "active_calories", "total_calories",
            "high_activity_time", "medium_activity_time", "low_activity_time",
            "sedentary_time", "resting_time", "equivalent_walking_distance",
            "meters_to_target", "target_calories",
            "high_activity_met_minutes", "medium_activity_met_minutes",
            "low_activity_met_minutes", "sedentary_met_minutes",
            "average_met_minutes", "non_wear_time", "inactivity_alerts"]
    available = [c for c in keep if c in df.columns]
    df = df[available]
    if aggregate:
        df = _aggregate(df, "W" if aggregate == "weekly" else "ME")
    return _paginate(_df_to_records(df), limit, offset)


@router.get("/stress")
def stress_data(
    start: date | None = Query(None), end: date | None = Query(None),
    limit: int | None = Query(None, ge=1), offset: int = Query(0, ge=0),
    aggregate: str | None = Query(None, pattern="^(weekly|monthly)$"),
):
    ds = _get_datasets()
    df = _filter_dates(ds.get("stress", pd.DataFrame()), start, end)
    if aggregate:
        df = _aggregate(df, "W" if aggregate == "weekly" else "ME")
    return _paginate(_df_to_records(df), limit, offset)


@router.get("/spo2")
def spo2_data(
    start: date | None = Query(None), end: date | None = Query(None),
    limit: int | None = Query(None, ge=1), offset: int = Query(0, ge=0),
    aggregate: str | None = Query(None, pattern="^(weekly|monthly)$"),
):
    ds = _get_datasets()
    df = _filter_dates(ds.get("spo2", pd.DataFrame()), start, end)
    if aggregate:
        df = _aggregate(df, "W" if aggregate == "weekly" else "ME")
    return _paginate(_df_to_records(df), limit, offset)


@router.get("/heartrate")
def heartrate_data(
    start: date | None = Query(None), end: date | None = Query(None),
    limit: int | None = Query(None, ge=1), offset: int = Query(0, ge=0),
    aggregate: str | None = Query(None, pattern="^(weekly|monthly)$"),
):
    ds = _get_datasets()
    df = ds.get("heartrate", pd.DataFrame())
    if not df.empty and "day" in df.columns:
        df = _filter_dates(df, start, end)
    if aggregate:
        df = _aggregate(df, "W" if aggregate == "weekly" else "ME")
    return _paginate(_df_to_records(df), limit, offset)


@router.get("/readiness/contributors")
def readiness_contributors(start: date | None = Query(None), end: date | None = Query(None)):
    """Average readiness contributor scores for the period."""
    ds = _get_datasets()
    df = _filter_dates(ds.get("readiness", pd.DataFrame()), start, end)
    if df.empty:
        return {"contributors": [], "daily": []}
    contrib_cols = [c for c in df.columns if c.startswith("contributors.")]
    labels = {c: c.replace("contributors.", "").replace("_", " ").title() for c in contrib_cols}
    # Averages for radar/bar
    avgs = []
    for col in contrib_cols:
        vals = df[col].dropna()
        if not vals.empty:
            avgs.append({"contributor": labels[col], "value": round(vals.mean(), 1)})
    avgs.sort(key=lambda x: x["value"])
    # Daily breakdown for trend
    daily_keep = ["day", "score"] + contrib_cols
    available = [c for c in daily_keep if c in df.columns]
    daily = _df_to_records(df[available].sort_values("day"))
    return {"contributors": avgs, "daily": daily}


@router.get("/sleep/contributors")
def sleep_contributors(start: date | None = Query(None), end: date | None = Query(None)):
    """Average sleep contributor scores for the period."""
    ds = _get_datasets()
    df = _filter_dates(ds.get("sleep", pd.DataFrame()), start, end)
    if df.empty:
        return {"contributors": [], "daily": []}
    contrib_cols = [c for c in df.columns if c.startswith("contributors.")]
    labels = {c: c.replace("contributors.", "").replace("_", " ").title() for c in contrib_cols}
    avgs = []
    for col in contrib_cols:
        vals = df[col].dropna()
        if not vals.empty:
            avgs.append({"contributor": labels[col], "value": round(vals.mean(), 1)})
    avgs.sort(key=lambda x: x["value"])
    daily_keep = ["day", "score"] + contrib_cols
    available = [c for c in daily_keep if c in df.columns]
    daily = _df_to_records(df[available].sort_values("day"))
    return {"contributors": avgs, "daily": daily}


@router.get("/training/intensity")
def training_intensity():
    """Volume distribution by rep range: strength (1-5), hypertrophy (6-12), endurance (13+)."""
    ds = _get_datasets()
    df = ds.get("workouts", pd.DataFrame())
    if df.empty:
        return {"summary": [], "daily": []}
    working = df[(df["weight_kg"] > 0) & (df["reps"] > 0)].copy()
    if working.empty:
        return {"summary": [], "daily": []}

    def rep_zone(reps: int) -> str:
        if reps <= 5:
            return "Strength (1-5)"
        if reps <= 12:
            return "Hypertrophy (6-12)"
        return "Endurance (13+)"

    working["zone"] = working["reps"].apply(rep_zone)
    summary = working.groupby("zone")["volume"].sum().reset_index()
    summary.columns = ["zone", "volume"]
    summary = summary.sort_values("volume", ascending=False)

    # Daily breakdown
    daily = working.groupby(["day", "zone"])["volume"].sum().reset_index()
    pivoted = daily.pivot_table(index="day", columns="zone", values="volume", fill_value=0).reset_index()
    pivoted = pivoted.sort_values("day")

    return {
        "summary": _df_to_records(summary),
        "daily": _df_to_records(pivoted),
    }


@router.get("/training/set-types")
def training_set_types():
    """Distribution of set types (normal, warmup, drop_set, failure, etc.)."""
    ds = _get_datasets()
    df = ds.get("workouts", pd.DataFrame())
    if df.empty or "set_type" not in df.columns:
        return {"data": []}
    counts = df.groupby("set_type").agg(
        sets=("set_type", "count"),
        volume=("volume", "sum"),
    ).reset_index().sort_values("sets", ascending=False)
    return {"data": _df_to_records(counts)}


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


@router.get("/training/estimated-1rm")
def training_estimated_1rm():
    """Estimated 1RM trends for top compound exercises using Epley formula."""
    ds = _get_datasets()
    df = ds.get("workouts", pd.DataFrame())
    if df.empty:
        return {"data": [], "exercises": []}

    # Filter to normal working sets with meaningful weight
    working = df[(df["weight_kg"] > 0) & (df["reps"] > 0) & (df["reps"] <= 12)].copy()
    if working.empty:
        return {"data": [], "exercises": []}

    # Epley formula: 1RM = weight * (1 + reps / 30)
    working["estimated_1rm"] = working["weight_kg"] * (1 + working["reps"] / 30)

    # Best estimated 1RM per exercise per day
    best = working.groupby(["day", "exercise"])["estimated_1rm"].max().reset_index()

    # Top exercises by frequency (most sessions)
    exercise_freq = best.groupby("exercise")["day"].nunique().sort_values(ascending=False)
    top_exercises = exercise_freq.head(5).index.tolist()

    result = best[best["exercise"].isin(top_exercises)].sort_values(["exercise", "day"])

    return {
        "data": _df_to_records(result),
        "exercises": top_exercises,
    }


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
def nutrition_data(
    start: date | None = Query(None), end: date | None = Query(None),
    limit: int | None = Query(None, ge=1), offset: int = Query(0, ge=0),
    aggregate: str | None = Query(None, pattern="^(weekly|monthly)$"),
):
    ds = _get_datasets()
    df = _filter_dates(ds.get("nutrition", pd.DataFrame()), start, end)
    if df.empty:
        return _paginate([], limit, offset)

    # Select core columns (skip raw totals/meals dicts for cleaner JSON)
    keep = ["day", "calories", "protein", "carbohydrates", "fat", "fiber", "sugar",
            "sodium", "saturated_fat", "cholesterol", "potassium",
            "vitamin_a", "vitamin_c", "calcium", "iron"]
    available = [c for c in keep if c in df.columns]
    df = df[available]
    if aggregate:
        df = _aggregate(df, "W" if aggregate == "weekly" else "ME")
    return _paginate(_df_to_records(df), limit, offset)


@router.get("/body-composition")
def body_composition_data():
    ds = _get_datasets()
    df = ds.get("body_composition", pd.DataFrame())
    if df.empty:
        return {"data": []}

    keep = ["day", "weight_kg", "body_fat_pct", "muscle_mass_kg", "fat_mass_kg",
            "water_mass_kg", "bone_mass_kg", "visceral_fat", "metabolic_age",
            "bmr", "bmi",
            "phase_angle_left_arm", "phase_angle_right_arm",
            "phase_angle_left_leg", "phase_angle_right_leg",
            "left_arm_muscle_kg", "right_arm_muscle_kg",
            "left_leg_muscle_kg", "right_leg_muscle_kg",
            "left_arm_fat_kg", "right_arm_fat_kg",
            "left_leg_fat_kg", "right_leg_fat_kg",
            "trunk_muscle_kg", "trunk_fat_kg",
            "intracellular_water_kg", "extracellular_water_kg",
            "fat_free_mass_kg", "muscle_score", "boditrax_score"]
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
                lag_days=val.get("lag_days", 0),
                ci_low=val.get("ci_low"),
                ci_high=val.get("ci_high"),
                n_samples=val.get("n_samples", len(data_df)),
            ))

    items.sort(key=lambda i: abs(i.r_value) if i.r_value is not None else 0, reverse=True)
    return CorrelationsResponse(correlations=items)


@router.get("/digest")
def weekly_digest():
    """Current week vs previous week summary."""
    ds = _get_datasets()
    today = pd.Timestamp.today().normalize()
    # Current week (Mon-Sun containing today)
    day_of_week = today.weekday()  # Mon=0
    this_monday = today - pd.Timedelta(days=day_of_week)
    last_monday = this_monday - pd.Timedelta(days=7)

    def period_avg(df: pd.DataFrame, col: str, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
        if df.empty or col not in df.columns or "day" not in df.columns:
            return None
        mask = (df["day"] >= start) & (df["day"] < end)
        vals = df.loc[mask, col].dropna()
        return round(float(vals.mean()), 1) if len(vals) > 0 else None

    metrics_config = [
        ("sleep", "score", "Sleep Score", ""),
        ("readiness", "score", "Readiness", ""),
        ("activity", "steps", "Steps", "steps"),
        ("nutrition", "calories", "Calories", "kcal"),
        ("nutrition", "protein", "Protein", "g"),
    ]

    items: list[dict[str, Any]] = []
    for ds_key, col, label, unit in metrics_config:
        df = ds.get(ds_key, pd.DataFrame())
        curr = period_avg(df, col, this_monday, today + pd.Timedelta(days=1))
        prev = period_avg(df, col, last_monday, this_monday)
        delta = round(curr - prev, 1) if curr is not None and prev is not None else None
        items.append({
            "label": label,
            "unit": unit,
            "current": curr,
            "previous": prev,
            "delta": delta,
        })

    # Training sessions count
    workouts_df = ds.get("workouts", pd.DataFrame())
    if not workouts_df.empty and "day" in workouts_df.columns:
        curr_sessions = int(workouts_df[(workouts_df["day"] >= this_monday) & (workouts_df["day"] < today + pd.Timedelta(days=1))]["day"].nunique())
        prev_sessions = int(workouts_df[(workouts_df["day"] >= last_monday) & (workouts_df["day"] < this_monday)]["day"].nunique())
        items.append({
            "label": "Training Sessions",
            "unit": "",
            "current": curr_sessions,
            "previous": prev_sessions,
            "delta": curr_sessions - prev_sessions,
        })

    return {
        "current_week": this_monday.strftime("%Y-%m-%d"),
        "previous_week": last_monday.strftime("%Y-%m-%d"),
        "items": items,
    }


@router.get("/compare")
def compare_periods(
    a_start: date = Query(...), a_end: date = Query(...),
    b_start: date = Query(...), b_end: date = Query(...),
):
    """Compare metrics between two date ranges."""
    ds = _get_datasets()

    def avg_metric(df: pd.DataFrame, col: str, start: date, end: date) -> float | None:
        filtered = _filter_dates(df, start, end)
        if filtered.empty or col not in filtered.columns:
            return None
        vals = filtered[col].dropna()
        return round(float(vals.mean()), 1) if len(vals) > 0 else None

    comparisons: list[dict[str, Any]] = []

    metrics_config = [
        ("sleep", "score", "Sleep Score", "", False),
        ("readiness", "score", "Readiness", "", False),
        ("activity", "steps", "Daily Steps", "steps", False),
        ("activity", "sedentary_time", "Sedentary Time", "sec", True),
        ("nutrition", "calories", "Calories", "kcal", False),
        ("nutrition", "protein", "Protein", "g", False),
    ]

    for ds_key, col, label, unit, invert in metrics_config:
        df = ds.get(ds_key, pd.DataFrame())
        if df.empty:
            continue
        val_a = avg_metric(df, col, a_start, a_end)
        val_b = avg_metric(df, col, b_start, b_end)
        delta = round(val_b - val_a, 1) if val_a is not None and val_b is not None else None
        improved = None
        if delta is not None:
            improved = delta < 0 if invert else delta > 0
        comparisons.append({
            "label": label,
            "unit": unit,
            "period_a": val_a,
            "period_b": val_b,
            "delta": delta,
            "improved": improved,
        })

    return {"comparisons": comparisons}


@router.get("/records")
def personal_records():
    """All-time personal bests and streaks."""
    ds = _get_datasets()
    records: list[dict[str, Any]] = []

    # Best sleep score
    sleep_df = ds.get("sleep", pd.DataFrame())
    if not sleep_df.empty and "score" in sleep_df.columns:
        best = sleep_df.loc[sleep_df["score"].idxmax()]
        records.append({
            "category": "Sleep",
            "label": "Best Sleep Score",
            "value": int(best["score"]),
            "unit": "",
            "date": best["day"].strftime("%Y-%m-%d") if hasattr(best["day"], "strftime") else str(best["day"]),
        })

    # Best readiness
    readiness_df = ds.get("readiness", pd.DataFrame())
    if not readiness_df.empty and "score" in readiness_df.columns:
        best = readiness_df.loc[readiness_df["score"].idxmax()]
        records.append({
            "category": "Recovery",
            "label": "Best Readiness",
            "value": int(best["score"]),
            "unit": "",
            "date": best["day"].strftime("%Y-%m-%d") if hasattr(best["day"], "strftime") else str(best["day"]),
        })

    # Highest daily steps
    activity_df = ds.get("activity", pd.DataFrame())
    if not activity_df.empty and "steps" in activity_df.columns:
        best = activity_df.loc[activity_df["steps"].idxmax()]
        records.append({
            "category": "Activity",
            "label": "Most Steps (Day)",
            "value": int(best["steps"]),
            "unit": "steps",
            "date": best["day"].strftime("%Y-%m-%d") if hasattr(best["day"], "strftime") else str(best["day"]),
        })

        # Step streak (consecutive days >= 7500)
        sorted_act = activity_df.sort_values("day")
        streak = 0
        best_streak = 0
        for _, row in sorted_act.iterrows():
            if pd.notna(row["steps"]) and row["steps"] >= 7500:
                streak += 1
                best_streak = max(best_streak, streak)
            else:
                streak = 0
        if best_streak > 0:
            records.append({
                "category": "Activity",
                "label": "Step Streak (7.5k+)",
                "value": best_streak,
                "unit": "days",
                "date": None,
            })

    # Highest training volume week
    workouts_df = ds.get("workouts", pd.DataFrame())
    if not workouts_df.empty and "volume" in workouts_df.columns:
        daily_vol = workouts_df.groupby("day")["volume"].sum().reset_index()
        daily_vol["day"] = pd.to_datetime(daily_vol["day"])
        weekly = daily_vol.set_index("day").resample("W-MON")["volume"].sum()
        if not weekly.empty:
            best_week = weekly.idxmax()
            records.append({
                "category": "Training",
                "label": "Best Volume (Week)",
                "value": int(weekly.max()),
                "unit": "kg",
                "date": best_week.strftime("%Y-%m-%d"),
            })

        # Heaviest estimated 1RM
        working = workouts_df[(workouts_df["weight_kg"] > 0) & (workouts_df["reps"] > 0) & (workouts_df["reps"] <= 12)].copy()
        if not working.empty:
            working["e1rm"] = working["weight_kg"] * (1 + working["reps"] / 30)
            best_idx = working["e1rm"].idxmax()
            best = working.loc[best_idx]
            records.append({
                "category": "Training",
                "label": f"Best 1RM ({best['exercise']})",
                "value": round(float(best["e1rm"]), 1),
                "unit": "kg",
                "date": best["day"].strftime("%Y-%m-%d") if hasattr(best["day"], "strftime") else str(best["day"]),
            })

    return {"records": records}


@router.get("/alerts")
def alerts_data():
    ds = _get_datasets()
    correlations = compute_correlations(ds)
    raw_alerts = compute_alerts(ds, correlations)
    return {"alerts": raw_alerts}


@router.get("/intervention-impact")
def intervention_impact(intervention_date: date = Query(...), window: int = Query(14)):
    """Compare metric averages before vs after an intervention date."""
    ds = _get_datasets()
    d = pd.Timestamp(intervention_date)
    before_start = d - pd.Timedelta(days=window)
    after_end = d + pd.Timedelta(days=window)

    metrics_config = [
        ("sleep", "score", "Sleep Score", "", False),
        ("readiness", "score", "Readiness", "", False),
        ("activity", "steps", "Daily Steps", "steps", False),
        ("nutrition", "calories", "Calories", "kcal", False),
        ("nutrition", "protein", "Protein", "g", False),
    ]

    # Add stress if available
    stress_df = ds.get("stress", pd.DataFrame())
    if not stress_df.empty and "stress_high" in stress_df.columns:
        metrics_config.append(("stress", "stress_high", "Stress (high min)", "min", True))

    results: list[dict[str, Any]] = []
    for ds_key, col, label, unit, invert in metrics_config:
        df = ds.get(ds_key, pd.DataFrame())
        if df.empty or col not in df.columns or "day" not in df.columns:
            continue
        before = df[(df["day"] >= before_start) & (df["day"] < d)]
        after = df[(df["day"] >= d) & (df["day"] <= after_end)]
        before_vals = before[col].dropna()
        after_vals = after[col].dropna()
        before_avg = round(float(before_vals.mean()), 1) if len(before_vals) > 0 else None
        after_avg = round(float(after_vals.mean()), 1) if len(after_vals) > 0 else None
        delta = round(after_avg - before_avg, 1) if before_avg is not None and after_avg is not None else None
        improved = None
        if delta is not None:
            improved = delta < 0 if invert else delta > 0
        results.append({
            "label": label,
            "unit": unit,
            "before": before_avg,
            "after": after_avg,
            "delta": delta,
            "improved": improved,
        })

    return {"metrics": results, "window_days": window}


@router.get("/streaks")
def streaks_data():
    """Current and best streaks for key metrics."""
    ds = _get_datasets()
    streaks: list[dict[str, Any]] = []

    def _compute_streak(series: pd.Series, threshold: float, direction: str = "above") -> tuple[int, int]:
        """Return (current_streak, best_streak)."""
        current = 0
        best = 0
        running = 0
        for val in series:
            if pd.isna(val):
                running = 0
                continue
            hit = val >= threshold if direction == "above" else val <= threshold
            if hit:
                running += 1
                best = max(best, running)
            else:
                running = 0
        # Current streak = count from the end
        current = 0
        for val in reversed(series.values):
            if pd.isna(val):
                break
            hit = val >= threshold if direction == "above" else val <= threshold
            if hit:
                current += 1
            else:
                break
        return current, best

    # Sleep score ≥ 75
    sleep_df = ds.get("sleep", pd.DataFrame())
    if not sleep_df.empty and "score" in sleep_df.columns:
        sorted_sleep = sleep_df.sort_values("day")
        curr, best = _compute_streak(sorted_sleep["score"], 75, "above")
        streaks.append({
            "metric": "Sleep Score",
            "target": "≥ 75",
            "current": curr,
            "best": best,
            "unit": "days",
        })

    # Readiness ≥ 70
    readiness_df = ds.get("readiness", pd.DataFrame())
    if not readiness_df.empty and "score" in readiness_df.columns:
        sorted_r = readiness_df.sort_values("day")
        curr, best = _compute_streak(sorted_r["score"], 70, "above")
        streaks.append({
            "metric": "Readiness",
            "target": "≥ 70",
            "current": curr,
            "best": best,
            "unit": "days",
        })

    # Steps ≥ 7500
    activity_df = ds.get("activity", pd.DataFrame())
    steps_col = next((c for c in ["steps", "total_steps"] if c in activity_df.columns), None) if not activity_df.empty else None
    if steps_col:
        sorted_a = activity_df.sort_values("day")
        curr, best = _compute_streak(sorted_a[steps_col], 7500, "above")
        streaks.append({
            "metric": "Daily Steps",
            "target": "≥ 7,500",
            "current": curr,
            "best": best,
            "unit": "days",
        })

    # Logging compliance (calories > 0)
    nutrition_df = ds.get("nutrition", pd.DataFrame())
    if not nutrition_df.empty and "calories" in nutrition_df.columns:
        sorted_n = nutrition_df.sort_values("day")
        curr, best = _compute_streak(sorted_n["calories"], 1, "above")
        streaks.append({
            "metric": "Logging",
            "target": "logged",
            "current": curr,
            "best": best,
            "unit": "days",
        })

    # Training frequency (≥ 1 session per 3 days → streak of training days with ≤2 day gaps)
    workouts_df = ds.get("workouts", pd.DataFrame())
    if not workouts_df.empty and "day" in workouts_df.columns:
        training_days = sorted(workouts_df["day"].unique())
        if len(training_days) >= 2:
            # Weekly training streak: weeks with ≥3 sessions
            wk_df = pd.DataFrame({"day": training_days})
            wk_df["day"] = pd.to_datetime(wk_df["day"])
            wk_df["week"] = wk_df["day"].dt.isocalendar().week.astype(int)
            wk_df["year"] = wk_df["day"].dt.isocalendar().year.astype(int)
            weekly_counts = wk_df.groupby(["year", "week"])["day"].nunique()
            curr = 0
            best = 0
            running = 0
            for count in weekly_counts:
                if count >= 3:
                    running += 1
                    best = max(best, running)
                else:
                    running = 0
            for count in reversed(weekly_counts.values):
                if count >= 3:
                    curr += 1
                else:
                    break
            streaks.append({
                "metric": "Training (3+/wk)",
                "target": "≥ 3 sessions",
                "current": curr,
                "best": best,
                "unit": "weeks",
            })

    return {"streaks": streaks}


@router.get("/training/recommendation")
def training_recommendation():
    """Readiness-based training intensity recommendation for today."""
    ds = _get_datasets()
    readiness_df = ds.get("readiness", pd.DataFrame())
    workouts_df = ds.get("workouts", pd.DataFrame())

    if readiness_df.empty or "score" not in readiness_df.columns:
        return {"score": None, "intensity": "unknown", "detail": "Insufficient readiness data."}

    sorted_r = readiness_df.sort_values("day")
    today_readiness = float(sorted_r["score"].iloc[-1])

    # HRV balance component
    hrv_col = next((c for c in ["contributors.hrv_balance", "hrv_balance"] if c in sorted_r.columns), None)
    hrv_score = float(sorted_r[hrv_col].iloc[-1]) if hrv_col and pd.notna(sorted_r[hrv_col].iloc[-1]) else 50

    # Recent training load (last 3 days volume)
    recent_load = 0.0
    if not workouts_df.empty and "volume" in workouts_df.columns:
        three_days_ago = sorted_r["day"].iloc[-1] - pd.Timedelta(days=3)
        recent = workouts_df[workouts_df["day"] >= three_days_ago]
        recent_load = float(recent["volume"].sum())

    # 14-day average volume per 3-day window for comparison
    avg_3day_load = 0.0
    if not workouts_df.empty and "volume" in workouts_df.columns:
        fourteen_ago = sorted_r["day"].iloc[-1] - pd.Timedelta(days=14)
        last_14 = workouts_df[workouts_df["day"] >= fourteen_ago]
        if not last_14.empty:
            total_14d = float(last_14["volume"].sum())
            avg_3day_load = total_14d / 14 * 3

    # Composite training readiness score (0-100)
    # Readiness: 50% weight, HRV: 30% weight, load ratio: 20% weight
    load_factor = 50.0  # neutral
    if avg_3day_load > 0:
        ratio = recent_load / avg_3day_load
        # High recent load → lower readiness for training
        load_factor = max(0, min(100, 100 - (ratio - 1) * 50))

    composite = today_readiness * 0.5 + hrv_score * 0.3 + load_factor * 0.2
    composite = round(max(0, min(100, composite)))

    # Intensity recommendation
    if composite >= 80:
        intensity = "hard"
        detail = "Recovery markers are strong. Good day for heavy compounds or high-volume work."
    elif composite >= 65:
        intensity = "moderate"
        detail = "Decent recovery. Train normally but listen to your body — don't push PRs."
    elif composite >= 45:
        intensity = "light"
        detail = "Recovery is below average. Stick to lighter weights, isolation work, or active recovery."
    else:
        intensity = "rest"
        detail = "Recovery is low. Consider a rest day or very light mobility/stretching only."

    return {
        "score": composite,
        "intensity": intensity,
        "detail": detail,
        "components": {
            "readiness": round(today_readiness),
            "hrv_balance": round(hrv_score),
            "load_factor": round(load_factor),
            "recent_volume": round(recent_load),
        },
    }


@router.get("/forecasts")
def forecasts():
    """Trend extrapolation for body composition metrics."""
    ds = _get_datasets()
    body_df = ds.get("body_composition", pd.DataFrame())
    if body_df.empty:
        return {"forecasts": []}

    sorted_body = body_df.sort_values("day")
    results: list[dict[str, Any]] = []

    forecast_metrics = [
        ("weight_kg", "Weight", "kg"),
        ("body_fat_pct", "Body Fat", "%"),
        ("muscle_mass_kg", "Muscle Mass", "kg"),
    ]

    for col, label, unit in forecast_metrics:
        if col not in sorted_body.columns:
            continue
        vals = sorted_body[[col, "day"]].dropna(subset=[col])
        if len(vals) < 3:
            continue

        # Compute slope (change per day) using linear regression
        y = vals[col].values.astype(float)
        x = (vals["day"] - vals["day"].iloc[0]).dt.days.values.astype(float)
        if len(x) < 3 or x[-1] - x[0] == 0:
            continue

        x_mean = x.mean()
        y_mean = y.mean()
        num = ((x - x_mean) * (y - y_mean)).sum()
        den = ((x - x_mean) ** 2).sum()
        if den == 0:
            continue
        slope_per_day = num / den
        slope_per_month = slope_per_day * 30

        current = float(y[-1])
        span_days = int(x[-1] - x[0])

        result: dict[str, Any] = {
            "metric": label,
            "unit": unit,
            "current": round(current, 1),
            "rate_per_month": round(slope_per_month, 2),
            "direction": "increasing" if slope_per_month > 0 else "decreasing" if slope_per_month < 0 else "stable",
            "data_span_days": span_days,
            "data_points": len(vals),
        }

        # Project 3 and 6 month forecasts
        result["forecast_3m"] = round(current + slope_per_day * 90, 1)
        result["forecast_6m"] = round(current + slope_per_day * 180, 1)

        results.append(result)

    return {"forecasts": results}


# Reference ranges for blood work markers based on Dashboard Business Rules
REFERENCE_RANGES = {
    # Domain 1: Hormonal
    "testosterone_nmol": {
        "green": [20, 100],
        "amber": [15, 20],
        "red": [12, 15],
        "critical": [0, 12],
        "unit": "nmol/l",
        "label": "Total Testosterone"
    },
    "free_testosterone_nmol": {
        "green": [0.50, 2.0],
        "amber": [0.40, 0.50],
        "red": [0.30, 0.40],
        "critical": [0, 0.30],
        "unit": "nmol/l",
        "label": "Free Testosterone"
    },
    "oestradiol_pmol": {
        "green": [100, 150],
        "amber": [[75, 100], [150, 200]],
        "red": [[0, 75], [200, 1000]],
        "unit": "pmol/l",
        "label": "Oestradiol"
    },
    "shbg_nmol": {
        "green": [18, 30],
        "amber": [[0, 18], [30, 40]],
        "red": [40, 200],
        "unit": "nmol/l",
        "label": "SHBG"
    },
    "prolactin_miu": {
        "green": [0, 100],
        "amber": [100, 200],
        "red": [200, 350],
        "critical": [350, 5000],
        "unit": "mIU/l",
        "label": "Prolactin"
    },
    
    # Domain 2: TRT Safety
    "psa_ug": {
        "green": [0, 1.5],
        "amber": [1.5, 2.5],
        "red": [2.5, 3.5],
        "critical": [3.5, 50],
        "unit": "µg/l",
        "label": "PSA"
    },
    "haematocrit_pct": {
        "green": [0, 46],
        "amber": [46, 48],
        "red": [48, 50],
        "critical": [50, 70],
        "unit": "%",
        "label": "Haematocrit"
    },
    "haemoglobin_g": {
        "green": [0, 155],
        "amber": [155, 165],
        "red": [165, 170],
        "critical": [170, 250],
        "unit": "g/l",
        "label": "Haemoglobin"
    },
    "egfr_ml": {
        "green": [90, 300],
        "amber": [60, 90],
        "red": [45, 60],
        "critical": [0, 45],
        "unit": "ml/min",
        "label": "eGFR"
    },

    # Domain 3: Metabolic & Cardiovascular
    "total_cholesterol_mmol": {
        "green": [0, 4.5],
        "amber": [4.5, 5.2],
        "red": [5.2, 15],
        "unit": "mmol/l",
        "label": "Total Cholesterol"
    },
    "cholesterol_hdl_ratio": {
        "green": [0, 3.5],
        "amber": [3.5, 4.0],
        "red": [4.0, 5.0],
        "critical": [5.0, 20],
        "unit": "ratio",
        "label": "Total Cholesterol / HDL Ratio"
    },
    "hdl_mmol": {
        "green": [1.2, 5],
        "amber": [1.0, 1.2],
        "red": [0.9, 1.0],
        "critical": [0, 0.9],
        "unit": "mmol/l",
        "label": "HDL Cholesterol"
    },
    "hba1c_mmol": {
        "green": [0, 38],
        "amber": [38, 41],
        "red": [42, 47],
        "critical": [48, 200],
        "unit": "mmol/mol",
        "label": "HbA1c"
    },
    "mcv_fl": {
        "green": [80, 95],
        "amber": [95, 100],
        "red": [100, 150],
        "unit": "fL",
        "label": "MCV"
    }
}


@router.get("/bloodwork")
def bloodwork_data(start: date | None = Query(None), end: date | None = Query(None)):
    ds = _get_datasets()
    df = _filter_dates(ds.get("bloodwork", pd.DataFrame()), start, end)
    if df.empty:
        return {"data": [], "reference_ranges": REFERENCE_RANGES}
    return {
        "data": _df_to_records(df.sort_values("day")),
        "reference_ranges": REFERENCE_RANGES,
    }


@router.get("/bloodwork/latest")
def bloodwork_latest():
    ds = _get_datasets()
    df = ds.get("bloodwork", pd.DataFrame())
    if df.empty:
        return {"latest": None, "reference_ranges": REFERENCE_RANGES}
    
    latest = df.sort_values("day").iloc[-1].to_dict()
    # Convert Timestamp to string
    if isinstance(latest.get("day"), pd.Timestamp):
        latest["day"] = latest["day"].strftime("%Y-%m-%d")
    
    # Replace NaN with None
    import math
    for k, v in latest.items():
        if isinstance(v, float) and math.isnan(v):
            latest[k] = None
            
    return {
        "latest": latest,
        "reference_ranges": REFERENCE_RANGES,
    }


@router.get("/bloodwork/trends")
def bloodwork_trends():
    ds = _get_datasets()
    df = ds.get("bloodwork", pd.DataFrame())
    if df.empty:
        return {"trends": {}, "reference_ranges": REFERENCE_RANGES}
    
    df = df.sort_values("day")
    trends = {}
    
    # Extract time series for each marker
    markers = [c for c in df.columns if c not in ["day", "date"]]
    for marker in markers:
        points = []
        for _, row in df.iterrows():
            val = row[marker]
            if pd.notna(val):
                points.append({
                    "date": row["day"].strftime("%Y-%m-%d"),
                    "value": float(val)
                })
        if points:
            trends[marker] = points
            
    return {
        "trends": trends,
        "reference_ranges": REFERENCE_RANGES,
    }


class GoldenPhaseRecommendation(BaseModel):
    metric: str
    golden_value: float | None
    current_value: float | None
    unit: str
    target: float | None
    status: str  # "on_track", "below", "above"


class GoldenPhaseResponse(BaseModel):
    period_start: str
    period_end: str
    duration_weeks: int
    body_comp_change: dict[str, Any]
    scan_trajectory: list[dict[str, Any]]
    recommendations: list[GoldenPhaseRecommendation]
    golden_averages: dict[str, Any]
    current_averages: dict[str, Any]
    comparison_periods: list[dict[str, Any]]
    training_profile: dict[str, Any]


@router.get("/golden-phase")
def golden_phase() -> GoldenPhaseResponse:
    """Analyse historical data to identify the peak body recomposition period
    and derive recommended targets for nutrition, training, sleep, and activity."""
    ds = _get_datasets()
    body = ds.get("body_composition", pd.DataFrame())
    nutr = ds.get("nutrition", pd.DataFrame())
    workouts = ds.get("workouts", pd.DataFrame())
    sleep = ds.get("sleep", pd.DataFrame())
    readiness = ds.get("readiness", pd.DataFrame())
    activity = ds.get("activity", pd.DataFrame())
    stress = ds.get("stress", pd.DataFrame())

    # ── Identify golden phase via best recomp window ──
    # Slide a window across body-comp scans and find the period with best
    # combined muscle gain + fat loss (recomp score).
    if body.empty or len(body) < 4:
        return GoldenPhaseResponse(
            period_start="", period_end="", duration_weeks=0,
            body_comp_change={}, scan_trajectory=[], recommendations=[],
            golden_averages={}, current_averages={}, comparison_periods=[],
            training_profile={},
        )

    body_sorted = body.sort_values("day").reset_index(drop=True)
    best_score = -999.0
    best_start_idx = 0
    best_end_idx = len(body_sorted) - 1
    min_scans = 4  # require at least 4 scans in the window

    for i in range(len(body_sorted)):
        for j in range(i + min_scans - 1, len(body_sorted)):
            row_i = body_sorted.iloc[i]
            row_j = body_sorted.iloc[j]
            muscle_start = row_i.get("muscle_mass_kg")
            muscle_end = row_j.get("muscle_mass_kg")
            fat_start = row_i.get("body_fat_pct")
            fat_end = row_j.get("body_fat_pct")
            if pd.isna(muscle_start) or pd.isna(muscle_end):
                continue
            if pd.isna(fat_start) or pd.isna(fat_end):
                continue
            muscle_gain = float(muscle_end - muscle_start)
            fat_drop = float(fat_start - fat_end)  # positive = good
            days_span = (row_j["day"] - row_i["day"]).days
            if days_span < 42:  # require at least 6 weeks
                continue
            # Recomp score: muscle gained + fat% lost, normalised per 18 weeks
            norm_factor = 126.0 / max(days_span, 1)  # 18 weeks = 126 days
            score = (muscle_gain + fat_drop * 2) * norm_factor
            if score > best_score:
                best_score = score
                best_start_idx = i
                best_end_idx = j

    start_row = body_sorted.iloc[best_start_idx]
    end_row = body_sorted.iloc[best_end_idx]
    gp_start = pd.Timestamp(start_row["day"])
    gp_end = pd.Timestamp(end_row["day"])
    duration_weeks = max(1, int((gp_end - gp_start).days / 7))

    # ── Body comp change ──
    def _safe_float(v: Any) -> float | None:
        if pd.isna(v):
            return None
        return round(float(v), 1)

    body_comp_change: dict[str, Any] = {}
    for key, label in [
        ("weight_kg", "Weight"), ("muscle_mass_kg", "Muscle Mass"),
        ("body_fat_pct", "Body Fat %"), ("visceral_fat", "Visceral Fat"),
        ("bmr", "BMR"),
    ]:
        s = _safe_float(start_row.get(key))
        e = _safe_float(end_row.get(key))
        delta = round(e - s, 1) if s is not None and e is not None else None
        body_comp_change[key] = {"label": label, "start": s, "end": e, "delta": delta}

    # Fat mass (derived)
    fat_mass_start = _safe_float(start_row.get("fat_mass_kg")) if "fat_mass_kg" in start_row.index else None
    fat_mass_end = _safe_float(end_row.get("fat_mass_kg")) if "fat_mass_kg" in end_row.index else None
    if fat_mass_start is not None and fat_mass_end is not None:
        body_comp_change["fat_mass_kg"] = {
            "label": "Fat Mass",
            "start": fat_mass_start,
            "end": fat_mass_end,
            "delta": round(fat_mass_end - fat_mass_start, 1),
        }

    # ── Scan trajectory during golden phase ──
    gp_scans = body_sorted[
        (body_sorted["day"] >= gp_start) & (body_sorted["day"] <= gp_end)
    ]
    scan_trajectory = []
    for _, row in gp_scans.iterrows():
        scan_trajectory.append({
            "day": row["day"].strftime("%Y-%m-%d") if isinstance(row["day"], pd.Timestamp) else str(row["day"]),
            "weight_kg": _safe_float(row.get("weight_kg")),
            "muscle_mass_kg": _safe_float(row.get("muscle_mass_kg")),
            "body_fat_pct": _safe_float(row.get("body_fat_pct")),
        })

    # ── Compute golden phase averages ──
    def _period_avg(df: pd.DataFrame, col: str, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
        if df.empty or "day" not in df.columns or col not in df.columns:
            return None
        subset = df[(df["day"] >= start) & (df["day"] <= end)]
        vals = subset[col].dropna()
        if len(vals) < 3:
            return None
        return round(float(vals.mean()), 1)

    def _period_count_per_week(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
        """Count distinct workout days per week."""
        if df.empty or "day" not in df.columns:
            return None
        subset = df[(df["day"] >= start) & (df["day"] <= end)]
        if subset.empty:
            return None
        unique_days = subset["day"].nunique()
        weeks = max(1, (end - start).days / 7)
        return round(unique_days / weeks, 1)

    # Nutrition (only logged days)
    nutr_gp = nutr[(nutr["day"] >= gp_start) & (nutr["day"] <= gp_end)] if not nutr.empty and "day" in nutr.columns else pd.DataFrame()
    nutr_logged = nutr_gp[nutr_gp["calories"] > 0] if not nutr_gp.empty and "calories" in nutr_gp.columns else pd.DataFrame()

    gp_calories = round(float(nutr_logged["calories"].mean()), 0) if not nutr_logged.empty else None
    gp_protein = round(float(nutr_logged["protein"].mean()), 0) if not nutr_logged.empty and "protein" in nutr_logged.columns else None
    gp_carbs = round(float(nutr_logged["carbohydrates"].mean()), 0) if not nutr_logged.empty and "carbohydrates" in nutr_logged.columns else None
    gp_fat = round(float(nutr_logged["fat"].mean()), 0) if not nutr_logged.empty and "fat" in nutr_logged.columns else None

    # Macro split percentages
    total_macro_cals = ((gp_protein or 0) * 4 + (gp_carbs or 0) * 4 + (gp_fat or 0) * 9) or 1
    gp_protein_pct = round((gp_protein or 0) * 4 / total_macro_cals * 100) if gp_protein else None
    gp_carbs_pct = round((gp_carbs or 0) * 4 / total_macro_cals * 100) if gp_carbs else None
    gp_fat_pct = round((gp_fat or 0) * 9 / total_macro_cals * 100) if gp_fat else None

    # Protein per kg (using golden phase average weight)
    gp_avg_weight = _safe_float(gp_scans["weight_kg"].mean()) if not gp_scans.empty and "weight_kg" in gp_scans.columns else None
    gp_protein_per_kg = round(gp_protein / gp_avg_weight, 1) if gp_protein and gp_avg_weight else None

    gp_sleep = _period_avg(sleep, "score", gp_start, gp_end)
    gp_readiness = _period_avg(readiness, "score", gp_start, gp_end)
    gp_hrv = _period_avg(readiness, "contributors.hrv_balance", gp_start, gp_end)
    gp_steps = _period_avg(activity, "steps", gp_start, gp_end)
    gp_training_freq = _period_count_per_week(workouts, gp_start, gp_end)

    golden_averages: dict[str, Any] = {
        "calories": gp_calories,
        "protein_g": gp_protein,
        "carbs_g": gp_carbs,
        "fat_g": gp_fat,
        "protein_pct": gp_protein_pct,
        "carbs_pct": gp_carbs_pct,
        "fat_pct": gp_fat_pct,
        "protein_per_kg": gp_protein_per_kg,
        "sleep_score": gp_sleep,
        "readiness_score": gp_readiness,
        "hrv_balance": gp_hrv,
        "daily_steps": gp_steps,
        "training_sessions_per_week": gp_training_freq,
    }

    # ── Current period averages (last 30 days) ──
    now = pd.Timestamp.now()
    cur_start = now - pd.Timedelta(days=30)

    nutr_cur = nutr[(nutr["day"] >= cur_start) & (nutr["day"] <= now)] if not nutr.empty and "day" in nutr.columns else pd.DataFrame()
    nutr_cur_logged = nutr_cur[nutr_cur["calories"] > 0] if not nutr_cur.empty and "calories" in nutr_cur.columns else pd.DataFrame()

    cur_calories = round(float(nutr_cur_logged["calories"].mean()), 0) if not nutr_cur_logged.empty else None
    cur_protein = round(float(nutr_cur_logged["protein"].mean()), 0) if not nutr_cur_logged.empty and "protein" in nutr_cur_logged.columns else None
    cur_carbs = round(float(nutr_cur_logged["carbohydrates"].mean()), 0) if not nutr_cur_logged.empty and "carbohydrates" in nutr_cur_logged.columns else None
    cur_fat = round(float(nutr_cur_logged["fat"].mean()), 0) if not nutr_cur_logged.empty and "fat" in nutr_cur_logged.columns else None

    cur_sleep = _period_avg(sleep, "score", cur_start, now)
    cur_readiness = _period_avg(readiness, "score", cur_start, now)
    cur_hrv = _period_avg(readiness, "contributors.hrv_balance", cur_start, now)
    cur_steps = _period_avg(activity, "steps", cur_start, now)
    cur_training_freq = _period_count_per_week(workouts, cur_start, now)

    latest_weight = float(body_sorted.iloc[-1]["weight_kg"]) if "weight_kg" in body_sorted.columns and pd.notna(body_sorted.iloc[-1]["weight_kg"]) else None
    cur_protein_per_kg = round(cur_protein / latest_weight, 1) if cur_protein and latest_weight else None

    current_averages: dict[str, Any] = {
        "calories": cur_calories,
        "protein_g": cur_protein,
        "carbs_g": cur_carbs,
        "fat_g": cur_fat,
        "protein_per_kg": cur_protein_per_kg,
        "sleep_score": cur_sleep,
        "readiness_score": cur_readiness,
        "hrv_balance": cur_hrv,
        "daily_steps": cur_steps,
        "training_sessions_per_week": cur_training_freq,
    }

    # ── Recommendations ──
    def _rec(metric: str, golden: float | None, current: float | None, unit: str, higher_is_better: bool = True) -> GoldenPhaseRecommendation:
        if golden is None:
            return GoldenPhaseRecommendation(metric=metric, golden_value=golden, current_value=current, unit=unit, target=golden, status="unknown")
        status = "unknown"
        if current is not None:
            threshold = golden * 0.05  # 5% tolerance
            if higher_is_better:
                status = "on_track" if current >= golden - threshold else "below"
            else:
                status = "on_track" if current <= golden + threshold else "above"
        return GoldenPhaseRecommendation(metric=metric, golden_value=golden, current_value=current, unit=unit, target=golden, status=status)

    recommendations = [
        _rec("Daily Calories", gp_calories, cur_calories, "kcal"),
        _rec("Protein", gp_protein, cur_protein, "g"),
        _rec("Protein/kg", gp_protein_per_kg, cur_protein_per_kg, "g/kg"),
        _rec("Carbohydrates", gp_carbs, cur_carbs, "g"),
        _rec("Fat", gp_fat, cur_fat, "g"),
        _rec("Training Frequency", gp_training_freq, cur_training_freq, "sessions/wk"),
        _rec("Sleep Score", gp_sleep, cur_sleep, ""),
        _rec("Readiness Score", gp_readiness, cur_readiness, ""),
        _rec("HRV Balance", gp_hrv, cur_hrv, ""),
        _rec("Daily Steps", gp_steps, cur_steps, "steps"),
    ]

    # ── Training profile during golden phase ──
    training_profile: dict[str, Any] = {}
    if not workouts.empty and "day" in workouts.columns:
        gp_workouts = workouts[(workouts["day"] >= gp_start) & (workouts["day"] <= gp_end)]
        if not gp_workouts.empty:
            total_sessions = int(gp_workouts["day"].nunique())
            training_profile["total_sessions"] = total_sessions
            training_profile["sessions_per_week"] = gp_training_freq

            # Muscle group distribution
            if "muscle_group" in gp_workouts.columns and "volume" in gp_workouts.columns:
                mg_vol = gp_workouts.groupby("muscle_group")["volume"].sum().sort_values(ascending=False)
                total_vol = mg_vol.sum()
                training_profile["muscle_groups"] = [
                    {"group": g, "volume": round(float(v)), "pct": round(float(v / total_vol * 100), 1)}
                    for g, v in mg_vol.head(10).items()
                ]
                training_profile["total_volume"] = round(float(total_vol))

            # Workout titles (split identification)
            if "workout_title" in gp_workouts.columns:
                title_counts = gp_workouts.groupby("workout_title")["day"].nunique().sort_values(ascending=False)
                training_profile["workout_split"] = [
                    {"name": t, "count": int(c)} for t, c in title_counts.head(6).items()
                ]

    # ── Comparison periods (quarterly) ──
    comparison_periods: list[dict[str, Any]] = []
    if not body_sorted.empty:
        all_start = body_sorted["day"].min()
        all_end = body_sorted["day"].max()
        q_start = all_start
        while q_start < all_end:
            q_end = q_start + pd.Timedelta(days=91)  # ~13 weeks
            if q_end > all_end:
                q_end = all_end
            q_scans = body_sorted[(body_sorted["day"] >= q_start) & (body_sorted["day"] <= q_end)]
            if len(q_scans) >= 2:
                first_s = q_scans.iloc[0]
                last_s = q_scans.iloc[-1]
                muscle_delta = _safe_float(last_s.get("muscle_mass_kg", 0)) - _safe_float(first_s.get("muscle_mass_kg", 0)) if _safe_float(first_s.get("muscle_mass_kg")) and _safe_float(last_s.get("muscle_mass_kg")) else None
                fat_delta = _safe_float(last_s.get("body_fat_pct", 0)) - _safe_float(first_s.get("body_fat_pct", 0)) if _safe_float(first_s.get("body_fat_pct")) and _safe_float(last_s.get("body_fat_pct")) else None
                cal_avg = _period_avg(nutr, "calories", q_start, q_end) if not nutr.empty else None
                prot_avg = _period_avg(nutr, "protein", q_start, q_end) if not nutr.empty else None
                train_freq = _period_count_per_week(workouts, q_start, q_end)
                sleep_avg = _period_avg(sleep, "score", q_start, q_end)

                is_golden = (q_start <= gp_start <= q_end) or (q_start <= gp_end <= q_end)
                comparison_periods.append({
                    "label": f"{q_start.strftime('%b %Y')} – {q_end.strftime('%b %Y')}",
                    "start": q_start.strftime("%Y-%m-%d"),
                    "end": q_end.strftime("%Y-%m-%d"),
                    "muscle_delta_kg": muscle_delta,
                    "fat_pct_delta": fat_delta,
                    "avg_calories": cal_avg,
                    "avg_protein": prot_avg,
                    "training_per_week": train_freq,
                    "sleep_score": sleep_avg,
                    "is_golden": is_golden,
                })
            q_start = q_end + pd.Timedelta(days=1)

    return GoldenPhaseResponse(
        period_start=gp_start.strftime("%Y-%m-%d"),
        period_end=gp_end.strftime("%Y-%m-%d"),
        duration_weeks=duration_weeks,
        body_comp_change=body_comp_change,
        scan_trajectory=scan_trajectory,
        recommendations=recommendations,
        golden_averages=golden_averages,
        current_averages=current_averages,
        comparison_periods=comparison_periods,
        training_profile=training_profile,
    )


@router.post("/reload")
def reload_data():
    from src.api.server import load_datasets
    import src.api.server as server_mod
    server_mod.datasets = load_datasets()
    return {"status": "ok", "datasets": list(server_mod.datasets.keys())}
