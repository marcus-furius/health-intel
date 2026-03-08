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


@router.post("/reload")
def reload_data():
    from src.api.server import load_datasets
    import src.api.server as server_mod
    server_mod.datasets = load_datasets()
    return {"status": "ok", "datasets": list(server_mod.datasets.keys())}
