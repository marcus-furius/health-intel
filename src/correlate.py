"""Cross-source correlation analysis."""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

MIN_DATAPOINTS = 14  # Minimum data points before drawing trend conclusions


def _safe_corr(series_a: pd.Series, series_b: pd.Series) -> float | None:
    """Compute correlation if enough valid data points exist."""
    valid = pd.DataFrame({"a": series_a, "b": series_b}).dropna()
    if len(valid) < MIN_DATAPOINTS:
        return None
    return valid["a"].corr(valid["b"])


def _merge_on_day(df_a: pd.DataFrame, df_b: pd.DataFrame,
                  cols_a: list[str], cols_b: list[str]) -> pd.DataFrame:
    """Inner join two DataFrames on 'day' column with selected columns."""
    left = df_a[["day"] + cols_a].copy()
    right = df_b[["day"] + cols_b].copy()
    return left.merge(right, on="day", how="inner")


def compute_correlations(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Compute all cross-source correlations.

    Returns a dict of correlation results keyed by analysis name.
    """
    results: dict[str, Any] = {}

    sleep_df = datasets.get("sleep", pd.DataFrame())
    readiness_df = datasets.get("readiness", pd.DataFrame())
    activity_df = datasets.get("activity", pd.DataFrame())
    workouts_df = datasets.get("workouts", pd.DataFrame())
    nutrition_df = datasets.get("nutrition", pd.DataFrame())
    body_comp_df = datasets.get("body_composition", pd.DataFrame())

    # --- Recovery & Performance ---

    # Sleep → Readiness
    if not sleep_df.empty and not readiness_df.empty:
        sleep_col = "score" if "score" in sleep_df.columns else None
        readiness_col = "score" if "score" in readiness_df.columns else None
        if sleep_col and readiness_col:
            merged = _merge_on_day(sleep_df, readiness_df, [sleep_col], [readiness_col])
            if not merged.empty:
                merged.columns = ["day", "sleep_score", "readiness_score"]
                corr = _safe_corr(merged["sleep_score"], merged["readiness_score"])
                results["sleep_vs_readiness"] = {
                    "correlation": corr,
                    "data": merged,
                    "x_label": "Sleep Score",
                    "y_label": "Readiness Score",
                }

    # Training Load → Next-Day Recovery (Hevy + Oura)
    if not workouts_df.empty and not readiness_df.empty:
        readiness_col = "score" if "score" in readiness_df.columns else None
        if readiness_col:
            daily_volume = workouts_df.groupby("day")["volume"].sum().reset_index()
            daily_volume["day"] = daily_volume["day"] + pd.Timedelta(days=1)  # Shift to next day
            merged = daily_volume.merge(readiness_df[["day", readiness_col]], on="day")
            if len(merged) >= MIN_DATAPOINTS:
                corr = _safe_corr(merged["volume"], merged[readiness_col])
                results["training_volume_vs_recovery"] = {
                    "correlation": corr,
                    "data": merged.rename(columns={readiness_col: "readiness_score"}),
                    "x_label": "Training Volume (kg)",
                    "y_label": "Next-Day Readiness Score",
                }

    # Sleep → Training Performance (Oura + Hevy)
    if not sleep_df.empty and not workouts_df.empty:
        sleep_col = "score" if "score" in sleep_df.columns else None
        if sleep_col:
            daily_volume = workouts_df.groupby("day")["volume"].sum().reset_index()
            merged = sleep_df[["day", sleep_col]].merge(daily_volume, on="day")
            if len(merged) >= MIN_DATAPOINTS:
                corr = _safe_corr(merged[sleep_col], merged["volume"])
                results["sleep_vs_training"] = {
                    "correlation": corr,
                    "data": merged.rename(columns={sleep_col: "sleep_score"}),
                    "x_label": "Sleep Score",
                    "y_label": "Training Volume (kg)",
                }

    # Activity → Sleep
    if not activity_df.empty and not sleep_df.empty:
        steps_col = next((c for c in ["steps", "total_steps"] if c in activity_df.columns), None)
        sleep_col = "score" if "score" in sleep_df.columns else None
        if steps_col and sleep_col:
            activity_shifted = activity_df[["day", steps_col]].copy()
            activity_shifted["day"] = activity_shifted["day"] + pd.Timedelta(days=1)
            merged = activity_shifted.merge(sleep_df[["day", sleep_col]], on="day")
            if len(merged) >= MIN_DATAPOINTS:
                corr = _safe_corr(merged[steps_col], merged[sleep_col])
                results["activity_vs_sleep"] = {
                    "correlation": corr,
                    "data": merged.rename(columns={steps_col: "steps", sleep_col: "sleep_score"}),
                    "x_label": "Daily Steps",
                    "y_label": "Next-Night Sleep Score",
                }

    # --- Nutrition & Recovery ---

    if not nutrition_df.empty and not readiness_df.empty:
        readiness_col = "score" if "score" in readiness_df.columns else None
        if readiness_col and "protein" in nutrition_df.columns:
            # Protein → Next-Day Recovery
            nutr_shifted = nutrition_df[["day", "protein"]].copy()
            nutr_shifted["day"] = nutr_shifted["day"] + pd.Timedelta(days=1)
            merged = nutr_shifted.merge(readiness_df[["day", readiness_col]], on="day")
            if len(merged) >= MIN_DATAPOINTS:
                corr = _safe_corr(merged["protein"], merged[readiness_col])
                results["protein_vs_recovery"] = {
                    "correlation": corr,
                    "data": merged.rename(columns={readiness_col: "readiness_score"}),
                    "x_label": "Protein (g)",
                    "y_label": "Next-Day Readiness Score",
                }

    if not nutrition_df.empty and not sleep_df.empty:
        sleep_col = "score" if "score" in sleep_df.columns else None
        if sleep_col and "calories" in nutrition_df.columns:
            # Calories → Sleep
            nutr_shifted = nutrition_df[["day", "calories"]].copy()
            nutr_shifted["day"] = nutr_shifted["day"] + pd.Timedelta(days=1)
            merged = nutr_shifted.merge(sleep_df[["day", sleep_col]], on="day")
            if len(merged) >= MIN_DATAPOINTS:
                corr = _safe_corr(merged["calories"], merged[sleep_col])
                results["calories_vs_sleep"] = {
                    "correlation": corr,
                    "data": merged.rename(columns={sleep_col: "sleep_score"}),
                    "x_label": "Calories (kcal)",
                    "y_label": "Next-Night Sleep Score",
                }

    # --- Nutrition & Body Composition ---

    if not nutrition_df.empty and not body_comp_df.empty:
        if "calories" in nutrition_df.columns and "weight_kg" in body_comp_df.columns:
            results["nutrition_vs_body_comp"] = {
                "nutrition": nutrition_df,
                "body_comp": body_comp_df,
                "available": True,
            }

    # --- Training & Body Composition ---

    if not workouts_df.empty and not body_comp_df.empty:
        if "muscle_mass_kg" in body_comp_df.columns:
            results["training_vs_body_comp"] = {
                "workouts": workouts_df,
                "body_comp": body_comp_df,
                "available": True,
            }

    logger.info("Computed %d correlation analyses", len(results))
    return results
