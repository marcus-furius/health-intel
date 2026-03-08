"""Data transformation — converts raw JSON/CSV to cleaned DataFrames."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Physiologically plausible ranges: column → (min, max)
_VALID_RANGES: dict[str, tuple[float, float]] = {
    # Oura scores are 0-100
    "score": (0, 100),
    # Heart rate
    "bpm": (25, 250),
    "hr_mean": (25, 250),
    "hr_min": (25, 250),
    "hr_max": (25, 250),
    # Activity
    "steps": (0, 120_000),
    "active_calories": (0, 10_000),
    "total_calories": (0, 15_000),
    # SpO2
    "spo2_percentage.average": (50, 100),
    # Stress/recovery (minutes)
    "stress_high": (0, 1440),
    "recovery_high": (0, 1440),
    # Nutrition
    "calories": (0, 15_000),
    "protein": (0, 1000),
    "carbohydrates": (0, 2000),
    "fat": (0, 1000),
    "fiber": (0, 200),
    "sugar": (0, 1000),
    "sodium": (0, 20_000),
    # Body composition
    "weight_kg": (20, 300),
    "body_fat_pct": (2, 70),
    "muscle_mass_kg": (10, 150),
    "bmr": (500, 5000),
    "bmi": (10, 80),
    "metabolic_age": (10, 120),
    "visceral_fat": (0, 60),
    "phase_angle_left_arm": (0, 20),
    "phase_angle_right_arm": (0, 20),
    "phase_angle_left_leg": (0, 20),
    "phase_angle_right_leg": (0, 20),
    # Training
    "weight_kg_training": (0, 500),  # mapped from workout weight_kg
    "reps": (0, 200),
}


def _validate_ranges(df: pd.DataFrame, context: str = "") -> pd.DataFrame:
    """Clamp outliers to NaN and log warnings for out-of-range values."""
    if df.empty:
        return df
    out = df.copy()
    for col, (lo, hi) in _VALID_RANGES.items():
        if col not in out.columns:
            continue
        if not pd.api.types.is_numeric_dtype(out[col]):
            continue
        mask = (out[col] < lo) | (out[col] > hi)
        n_bad = int(mask.sum())
        if n_bad > 0:
            logger.warning(
                "%s: %d values in '%s' outside [%s, %s] — set to NaN",
                context or "validate", n_bad, col, lo, hi,
            )
            out.loc[mask, col] = pd.NA
    return out


def _load_raw_json(directory: Path, pattern: str) -> list[dict[str, Any]]:
    """Load and combine ALL JSON files matching a pattern, dedup by 'day'/'date'.

    Files are sorted newest-first, so when duplicates exist the most recent
    file's records take priority (kept first by drop_duplicates).
    """
    files = sorted(directory.glob(pattern), reverse=True)
    if not files:
        return []
    all_records: list[dict[str, Any]] = []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as fh:
            all_records.extend(json.load(fh))
    if not all_records:
        return []
    # Dedup: use 'day' or 'date' as the key, prefer first occurrence (newest file)
    key_field = "day" if "day" in all_records[0] else "date" if "date" in all_records[0] else None
    if key_field:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for rec in all_records:
            k = str(rec.get(key_field, ""))
            if k and k not in seen:
                seen.add(k)
                deduped.append(rec)
        if len(deduped) < len(all_records):
            logger.info(
                "%s: deduped %d → %d records (by %s)",
                pattern, len(all_records), len(deduped), key_field,
            )
        return deduped
    return all_records


def _dedup_by_day(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate day rows, keeping the last occurrence (most recent data)."""
    if df.empty or "day" not in df.columns:
        return df
    before = len(df)
    df = df.drop_duplicates(subset="day", keep="last").reset_index(drop=True)
    if len(df) < before:
        logger.info("Deduped %d → %d rows by day", before, len(df))
    return df


def _load_all_json(directory: Path, pattern: str) -> list[dict[str, Any]]:
    """Load and combine ALL matching JSON files (for MFP monthly batches)."""
    files = sorted(directory.glob(pattern))
    all_data: list[dict[str, Any]] = []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as fh:
            all_data.extend(json.load(fh))
    return all_data


# --- Oura transforms ---

def transform_oura_sleep(raw_dir: Path) -> pd.DataFrame:
    """Transform Oura daily_sleep and sleep detail data."""
    daily_data = _load_raw_json(raw_dir / "oura", "daily_sleep_*.json")
    detail_data = _load_raw_json(raw_dir / "oura", "sleep_*.json")

    if not daily_data:
        return pd.DataFrame()

    daily_df = pd.json_normalize(daily_data)
    if "day" in daily_df.columns:
        daily_df["day"] = pd.to_datetime(daily_df["day"])
        daily_df = daily_df.sort_values("day").reset_index(drop=True)

    if detail_data:
        detail_df = pd.json_normalize(detail_data)
        if "day" in detail_df.columns:
            detail_df["day"] = pd.to_datetime(detail_df["day"])
            stage_cols = [c for c in detail_df.columns
                         if any(k in c for k in ["rem", "deep", "light", "awake", "total_sleep_duration"])]
            if stage_cols:
                detail_agg = detail_df.groupby("day")[stage_cols].first().reset_index()
                daily_df = daily_df.merge(detail_agg, on="day", how="left", suffixes=("", "_detail"))

    daily_df = _dedup_by_day(daily_df)
    daily_df = _validate_ranges(daily_df, "oura_sleep")
    logger.info("Oura sleep: %d rows", len(daily_df))
    return daily_df


def transform_oura_readiness(raw_dir: Path) -> pd.DataFrame:
    """Transform Oura daily readiness data."""
    data = _load_raw_json(raw_dir / "oura", "daily_readiness_*.json")
    if not data:
        return pd.DataFrame()
    df = pd.json_normalize(data)
    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
    df = _dedup_by_day(df)
    df = _validate_ranges(df, "oura_readiness")
    logger.info("Oura readiness: %d rows", len(df))
    return df


def transform_oura_activity(raw_dir: Path) -> pd.DataFrame:
    """Transform Oura daily activity data."""
    data = _load_raw_json(raw_dir / "oura", "daily_activity_*.json")
    if not data:
        return pd.DataFrame()
    df = pd.json_normalize(data)
    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
    df = _dedup_by_day(df)
    df = _validate_ranges(df, "oura_activity")
    logger.info("Oura activity: %d rows", len(df))
    return df


def transform_oura_heartrate(raw_dir: Path) -> pd.DataFrame:
    """Transform Oura heart rate data into daily summaries."""
    data = _load_raw_json(raw_dir / "oura", "heartrate_*.json")
    if not data:
        return pd.DataFrame()
    hr_df = pd.json_normalize(data)
    if "timestamp" in hr_df.columns:
        hr_df["timestamp"] = pd.to_datetime(hr_df["timestamp"])
        hr_df["day"] = hr_df["timestamp"].dt.date
    if "bpm" in hr_df.columns and "day" in hr_df.columns:
        summary = hr_df.groupby("day")["bpm"].agg(
            hr_mean="mean", hr_min="min", hr_max="max", hr_std="std", hr_count="count"
        ).reset_index()
        summary["day"] = pd.to_datetime(summary["day"])
        summary = _dedup_by_day(summary)
        summary = _validate_ranges(summary, "oura_heartrate")
        logger.info("Oura HR: %d daily summaries", len(summary))
        return summary
    return hr_df


def transform_oura_spo2(raw_dir: Path) -> pd.DataFrame:
    """Transform Oura daily SpO2 data."""
    data = _load_raw_json(raw_dir / "oura", "daily_spo2_*.json")
    if not data:
        return pd.DataFrame()
    df = pd.json_normalize(data)
    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
    df = _dedup_by_day(df)
    df = _validate_ranges(df, "oura_spo2")
    logger.info("Oura SpO2: %d rows", len(df))
    return df


def transform_oura_stress(raw_dir: Path) -> pd.DataFrame:
    """Transform Oura daily stress data."""
    data = _load_raw_json(raw_dir / "oura", "daily_stress_*.json")
    if not data:
        return pd.DataFrame()
    df = pd.json_normalize(data)
    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
    # Ensure numeric columns and convert seconds to minutes
    for col in ["stress_high", "recovery_high"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            # Oura API returns values in seconds — convert to minutes
            if df[col].median() > 300:
                df[col] = (df[col] / 60).round(1)
    df = _dedup_by_day(df)
    df = _validate_ranges(df, "oura_stress")
    logger.info("Oura stress: %d rows", len(df))
    return df


# --- Hevy transforms ---

def transform_hevy_workouts(raw_dir: Path) -> pd.DataFrame:
    """Transform Hevy workout data into a flat exercise-level DataFrame."""
    data = _load_raw_json(raw_dir / "hevy", "workouts_*.json")
    if not data:
        return pd.DataFrame()

    # Build exercise template lookup for muscle groups
    templates = _load_raw_json(raw_dir / "hevy", "exercise_templates_*.json")
    template_map: dict[str, str] = {}
    if templates:
        for tmpl in templates:
            tmpl_id = tmpl.get("id", "")
            muscle = tmpl.get("primary_muscle_group", "")
            if tmpl_id and muscle:
                template_map[tmpl_id] = muscle

    rows: list[dict[str, Any]] = []
    for workout in data:
        workout_date = workout.get("start_time", workout.get("created_at", ""))[:10]
        workout_title = workout.get("title", "")
        workout_duration = workout.get("duration_seconds", 0)

        for exercise in workout.get("exercises", []):
            exercise_title = exercise.get("title", "")
            template_id = exercise.get("exercise_template_id", "")
            muscle_group = template_map.get(template_id, "other")
            for set_data in exercise.get("sets", []):
                weight_kg = set_data.get("weight_kg", 0) or 0
                reps = set_data.get("reps", 0) or 0
                volume = weight_kg * reps
                rows.append({
                    "day": workout_date,
                    "workout_title": workout_title,
                    "duration_seconds": workout_duration,
                    "exercise": exercise_title,
                    "muscle_group": muscle_group,
                    "weight_kg": weight_kg,
                    "reps": reps,
                    "volume": volume,
                    "set_type": set_data.get("type", "normal"),
                })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["day"] = pd.to_datetime(df["day"])
    df = df.sort_values("day").reset_index(drop=True)
    # Validate training-specific ranges (reps, volume)
    df = _validate_ranges(df, "hevy_workouts")
    logger.info("Hevy workouts: %d set-level rows", len(df))
    return df


# --- Boditrax transforms ---

def transform_boditrax(raw_dir: Path) -> pd.DataFrame:
    """Transform Boditrax scan data.

    Prefers the most recent native CSV export (authoritative source)
    over intermediate JSON, which may be stale from an earlier extraction.
    """
    boditrax_dir = raw_dir / "boditrax"
    df = pd.DataFrame()

    # Prefer native Boditrax CSV export (most recent file — full history)
    native_files = sorted(boditrax_dir.glob("BoditraxAccount_*.csv"), reverse=True)
    if native_files:
        from src.sources.boditrax import BoditraxSource
        bt = BoditraxSource(mode="csv")
        scans = bt._parse_native_export(native_files[0], "1900-01-01", "2999-12-31")
        if scans:
            df = pd.json_normalize(scans)

    # Fall back to simple wide-format CSVs
    if df.empty:
        simple_files = sorted(boditrax_dir.glob("boditrax_scan_*.csv"))
        if simple_files:
            frames = [pd.read_csv(f) for f in simple_files]
            df = pd.concat(frames, ignore_index=True)

    # Fall back to intermediate JSON
    if df.empty:
        data = _load_raw_json(boditrax_dir, "scans_*.json")
        if data:
            df = pd.json_normalize(data)

    if df.empty:
        return df

    if "date" in df.columns:
        df["day"] = pd.to_datetime(df["date"])
        df = df.sort_values("day").reset_index(drop=True)
    df = _dedup_by_day(df)
    df = _validate_ranges(df, "boditrax")
    logger.info("Boditrax: %d scans", len(df))
    return df


# --- MFP transforms ---

def transform_mfp(raw_dir: Path) -> pd.DataFrame:
    """Transform MFP diary data into daily nutrition summary."""
    data = _load_all_json(raw_dir / "mfp", "mfp_diary_*.json")
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if "date" in df.columns:
        df["day"] = pd.to_datetime(df["date"])
        df = df.sort_values("day").reset_index(drop=True)

    # Ensure numeric columns
    numeric_cols = [
        "calories", "protein", "carbohydrates", "fat", "sodium", "sugar",
        "fiber", "saturated_fat", "polyunsaturated_fat", "monounsaturated_fat",
        "trans_fat", "cholesterol", "potassium", "vitamin_a", "vitamin_c",
        "calcium", "iron",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = _dedup_by_day(df)
    df = _validate_ranges(df, "mfp_nutrition")
    logger.info("MFP nutrition: %d days", len(df))
    return df


def transform_mfp_weight(raw_dir: Path) -> pd.DataFrame:
    """Transform MFP weight measurement data."""
    data = _load_raw_json(raw_dir / "mfp", "mfp_measurements_*.json")
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if "date" in df.columns:
        df["day"] = pd.to_datetime(df["date"])
        df = df.sort_values("day").reset_index(drop=True)
    if "weight_kg" in df.columns:
        df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce")
    df = _dedup_by_day(df)
    df = _validate_ranges(df, "mfp_weight")
    logger.info("MFP weight: %d measurements", len(df))
    return df


# --- Orchestrator ---

def transform_all(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Run all transformations and save processed files."""
    raw_dir = data_dir / "raw"
    processed_dir = data_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    datasets: dict[str, pd.DataFrame] = {}
    record_counts: dict[str, int] = {}

    # Oura
    for name, func, fmt in [
        ("sleep", transform_oura_sleep, "csv"),
        ("readiness", transform_oura_readiness, "csv"),
        ("activity", transform_oura_activity, "csv"),
        ("heartrate", transform_oura_heartrate, "parquet"),
        ("spo2", transform_oura_spo2, "csv"),
        ("stress", transform_oura_stress, "csv"),
    ]:
        df = func(raw_dir)
        if not df.empty:
            if fmt == "parquet":
                df.to_parquet(processed_dir / f"{name}.parquet", index=False)
            else:
                df.to_csv(processed_dir / f"{name}.csv", index=False)
            datasets[name] = df
            record_counts[name] = len(df)

    # Hevy
    hevy_df = transform_hevy_workouts(raw_dir)
    if not hevy_df.empty:
        hevy_df.to_csv(processed_dir / "workouts.csv", index=False)
        datasets["workouts"] = hevy_df
        record_counts["workouts"] = len(hevy_df)

    # Boditrax
    boditrax_df = transform_boditrax(raw_dir)
    if not boditrax_df.empty:
        boditrax_df.to_csv(processed_dir / "body_composition.csv", index=False)
        datasets["body_composition"] = boditrax_df
        record_counts["body_composition"] = len(boditrax_df)

    # MFP
    mfp_df = transform_mfp(raw_dir)
    if not mfp_df.empty:
        mfp_df.to_csv(processed_dir / "nutrition.csv", index=False)
        datasets["nutrition"] = mfp_df
        record_counts["nutrition"] = len(mfp_df)

    mfp_weight_df = transform_mfp_weight(raw_dir)
    if not mfp_weight_df.empty:
        mfp_weight_df.to_csv(processed_dir / "mfp_weight.csv", index=False)
        datasets["mfp_weight"] = mfp_weight_df
        record_counts["mfp_weight"] = len(mfp_weight_df)

    # Save metadata
    meta = {"transformed_at": datetime.now().isoformat(), "record_counts": record_counts}
    with open(processed_dir / "_metadata.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    logger.info("Transformation complete. Datasets: %s", list(datasets.keys()))
    return datasets
