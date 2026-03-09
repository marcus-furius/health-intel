"""Cross-source correlation analysis."""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_DATAPOINTS = 14  # Minimum data points before drawing trend conclusions
BOOTSTRAP_ITERATIONS = 1000


def _safe_corr(series_a: pd.Series, series_b: pd.Series) -> float | None:
    """Compute correlation if enough valid data points exist."""
    valid = pd.DataFrame({"a": series_a, "b": series_b}).dropna()
    if len(valid) < MIN_DATAPOINTS:
        return None
    return valid["a"].corr(valid["b"])


def _bootstrap_ci(series_a: pd.Series, series_b: pd.Series,
                   n_iter: int = BOOTSTRAP_ITERATIONS) -> tuple[float, float, int] | None:
    """Compute 95% bootstrap confidence interval for Pearson correlation.

    Returns (ci_low, ci_high, n_samples) or None if insufficient data.
    """
    valid = pd.DataFrame({"a": series_a, "b": series_b}).dropna()
    n = len(valid)
    if n < MIN_DATAPOINTS:
        return None
    rng = np.random.default_rng(42)
    boot_corrs = np.empty(n_iter)
    a_vals = valid["a"].values
    b_vals = valid["b"].values
    for i in range(n_iter):
        idx = rng.integers(0, n, size=n)
        boot_corrs[i] = np.corrcoef(a_vals[idx], b_vals[idx])[0, 1]
    ci_low = float(np.percentile(boot_corrs, 2.5))
    ci_high = float(np.percentile(boot_corrs, 97.5))
    return (round(ci_low, 3), round(ci_high, 3), n)


def _merge_on_day(df_a: pd.DataFrame, df_b: pd.DataFrame,
                  cols_a: list[str], cols_b: list[str]) -> pd.DataFrame:
    """Inner join two DataFrames on 'day' column with selected columns."""
    left = df_a[["day"] + cols_a].copy()
    right = df_b[["day"] + cols_b].copy()
    return left.merge(right, on="day", how="inner")


def _best_lag_corr(
    df_x: pd.DataFrame, x_col: str,
    df_y: pd.DataFrame, y_col: str,
    max_lag: int = 3,
) -> tuple[float | None, int, pd.DataFrame]:
    """Test lags 0..max_lag and return (best_corr, best_lag, merged_data)."""
    best_corr: float | None = None
    best_lag = 0
    best_merged = pd.DataFrame()

    # Handle column name collision when both sides use the same column
    x_merge_col = x_col
    y_merge_col = y_col
    if x_col == y_col:
        x_merge_col = f"{x_col}_x"
        y_merge_col = f"{y_col}_y"

    for lag in range(max_lag + 1):
        x_shifted = df_x[["day", x_col]].copy()
        if x_col == y_col:
            x_shifted = x_shifted.rename(columns={x_col: x_merge_col})
        if lag > 0:
            x_shifted["day"] = x_shifted["day"] + pd.Timedelta(days=lag)
        y_side = df_y[["day", y_col]].copy()
        if x_col == y_col:
            y_side = y_side.rename(columns={y_col: y_merge_col})
        merged = x_shifted.merge(y_side, on="day", how="inner")
        if len(merged) < MIN_DATAPOINTS:
            continue
        corr = merged[x_merge_col].corr(merged[y_merge_col])
        if corr is not None and not np.isnan(corr):
            if best_corr is None or abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag
                best_merged = merged

    return best_corr, best_lag, best_merged


def _add_correlation(
    results: dict[str, Any],
    key: str,
    df_x: pd.DataFrame, x_col: str, x_label: str,
    df_y: pd.DataFrame, y_col: str, y_label: str,
    max_lag: int = 3,
    rename_x: str | None = None,
    rename_y: str | None = None,
) -> None:
    """Test multi-lag correlation and add to results with bootstrap CI."""
    if df_x.empty or df_y.empty:
        return
    if x_col not in df_x.columns or y_col not in df_y.columns:
        return
    if "day" not in df_x.columns or "day" not in df_y.columns:
        return

    corr, lag, merged = _best_lag_corr(df_x, x_col, df_y, y_col, max_lag)
    if corr is None or merged.empty:
        return

    # Determine actual column names in merged (may have _x/_y suffix)
    actual_x = f"{x_col}_x" if x_col == y_col else x_col
    actual_y = f"{y_col}_y" if x_col == y_col else y_col

    # Bootstrap CI
    ci = _bootstrap_ci(merged[actual_x], merged[actual_y])

    if rename_x:
        merged = merged.rename(columns={actual_x: rename_x})
    elif x_col == y_col:
        merged = merged.rename(columns={actual_x: f"{x_col}_x"})
    if rename_y:
        merged = merged.rename(columns={actual_y: rename_y})
    elif x_col == y_col:
        merged = merged.rename(columns={actual_y: f"{y_col}_y"})

    results[key] = {
        "correlation": corr,
        "data": merged,
        "x_label": x_label,
        "y_label": y_label + (f" (+{lag}d)" if lag > 0 else ""),
        "lag_days": lag,
        "ci_low": ci[0] if ci else None,
        "ci_high": ci[1] if ci else None,
        "n_samples": ci[2] if ci else len(merged),
    }


def _bloodwork_context(results: dict[str, Any], bloodwork_df: pd.DataFrame, datasets: dict[str, pd.DataFrame]) -> None:
    """For each blood test date, compute surrounding health metric averages."""
    if bloodwork_df.empty:
        return

    # Metrics to window-average around test dates (14-day window)
    window_configs = [
        ("sleep", "score", "Sleep Score"),
        ("readiness", "score", "Readiness Score"),
        ("activity", "steps", "Steps"),
    ]

    context_rows = []
    for _, row in bloodwork_df.iterrows():
        test_date = row["day"]
        window_start = test_date - pd.Timedelta(days=14)
        
        entry = {"day": test_date, "testosterone_nmol": row.get("testosterone_nmol")}
        
        for ds_key, col, label in window_configs:
            df = datasets.get(ds_key, pd.DataFrame())
            if not df.empty and "day" in df.columns and col in df.columns:
                mask = (df["day"] >= window_start) & (df["day"] <= test_date)
                window_vals = df.loc[mask, col].dropna()
                if not window_vals.empty:
                    entry[f"{label} (14d avg)"] = round(float(window_vals.mean()), 1)
        
        context_rows.append(entry)
    
    if context_rows:
        results["bloodwork_context"] = {
            "data": pd.DataFrame(context_rows),
            "x_label": "Test Date",
            "y_label": "Metrics",
            "title": "Blood Work & Lifestyle Context",
        }


def compute_correlations(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Compute all cross-source correlations with multi-lag testing and bootstrap CI.

    Returns a dict of correlation results keyed by analysis name.
    """
    results: dict[str, Any] = {}

    sleep_df = datasets.get("sleep", pd.DataFrame())
    readiness_df = datasets.get("readiness", pd.DataFrame())
    activity_df = datasets.get("activity", pd.DataFrame())
    workouts_df = datasets.get("workouts", pd.DataFrame())
    nutrition_df = datasets.get("nutrition", pd.DataFrame())
    stress_df = datasets.get("stress", pd.DataFrame())
    heartrate_df = datasets.get("heartrate", pd.DataFrame())
    body_comp_df = datasets.get("body_composition", pd.DataFrame())
    bloodwork_df = datasets.get("bloodwork", pd.DataFrame())

    # Daily training volume helper
    daily_vol = pd.DataFrame()
    if not workouts_df.empty and "volume" in workouts_df.columns:
        daily_vol = workouts_df.groupby("day")["volume"].sum().reset_index()

    # --- Blood Work Context ---
    if not bloodwork_df.empty:
        _bloodwork_context(results, bloodwork_df, datasets)

    # --- Recovery & Performance ---

    # Sleep Score → Readiness
    _add_correlation(results, "sleep_vs_readiness",
                     sleep_df, "score", "Sleep Score",
                     readiness_df, "score", "Readiness Score",
                     max_lag=1, rename_x="sleep_score", rename_y="readiness_score")

    # Training Volume → Recovery
    if not daily_vol.empty:
        _add_correlation(results, "training_volume_vs_recovery",
                         daily_vol, "volume", "Training Volume (kg)",
                         readiness_df, "score", "Readiness Score",
                         max_lag=3, rename_y="readiness_score")

    # Sleep → Training Performance
    if not daily_vol.empty:
        _add_correlation(results, "sleep_vs_training",
                         sleep_df, "score", "Sleep Score",
                         daily_vol, "volume", "Training Volume (kg)",
                         max_lag=1, rename_x="sleep_score")

    # Activity (Steps) → Sleep
    steps_col = next((c for c in ["steps", "total_steps"] if c in activity_df.columns), None) if not activity_df.empty else None
    if steps_col:
        _add_correlation(results, "activity_vs_sleep",
                         activity_df, steps_col, "Daily Steps",
                         sleep_df, "score", "Sleep Score",
                         max_lag=1, rename_x="steps", rename_y="sleep_score")

    # Sedentary Time → Next-Day Readiness
    if not activity_df.empty and "sedentary_time" in activity_df.columns:
        _add_correlation(results, "sedentary_vs_readiness",
                         activity_df, "sedentary_time", "Sedentary Time (sec)",
                         readiness_df, "score", "Readiness Score",
                         max_lag=2, rename_y="readiness_score")

    # Sleep Efficiency → Training Performance
    if not sleep_df.empty and "contributors.efficiency" in sleep_df.columns and not daily_vol.empty:
        _add_correlation(results, "sleep_efficiency_vs_training",
                         sleep_df, "contributors.efficiency", "Sleep Efficiency",
                         daily_vol, "volume", "Training Volume (kg)",
                         max_lag=1)

    # Deep Sleep Duration → Next-Day HRV Balance
    if not sleep_df.empty and "deep_sleep_duration" in sleep_df.columns and \
       not readiness_df.empty and "contributors.hrv_balance" in readiness_df.columns:
        _add_correlation(results, "deep_sleep_vs_hrv",
                         sleep_df, "deep_sleep_duration", "Deep Sleep (sec)",
                         readiness_df, "contributors.hrv_balance", "HRV Balance",
                         max_lag=1)

    # --- Nutrition & Recovery ---

    # Protein → Recovery
    if not nutrition_df.empty and "protein" in nutrition_df.columns:
        _add_correlation(results, "protein_vs_recovery",
                         nutrition_df, "protein", "Protein (g)",
                         readiness_df, "score", "Readiness Score",
                         max_lag=2, rename_y="readiness_score")

    # Calories → Sleep
    if not nutrition_df.empty and "calories" in nutrition_df.columns:
        _add_correlation(results, "calories_vs_sleep",
                         nutrition_df, "calories", "Calories (kcal)",
                         sleep_df, "score", "Sleep Score",
                         max_lag=1, rename_y="sleep_score")

    # Carbs → Sleep Quality
    if not nutrition_df.empty and "carbohydrates" in nutrition_df.columns:
        _add_correlation(results, "carbs_vs_sleep",
                         nutrition_df, "carbohydrates", "Carbohydrates (g)",
                         sleep_df, "score", "Sleep Score",
                         max_lag=1, rename_y="sleep_score")

    # Sodium → Recovery
    if not nutrition_df.empty and "sodium" in nutrition_df.columns:
        sodium_df = nutrition_df[nutrition_df["sodium"] > 0].copy()
        if not sodium_df.empty:
            _add_correlation(results, "sodium_vs_recovery",
                             sodium_df, "sodium", "Sodium (mg)",
                             readiness_df, "score", "Readiness Score",
                             max_lag=2, rename_y="readiness_score")

    # --- Stress Correlations ---

    if not stress_df.empty and "stress_high" in stress_df.columns:
        # Stress → Sleep
        _add_correlation(results, "stress_vs_sleep",
                         stress_df, "stress_high", "Stress (high mins)",
                         sleep_df, "score", "Sleep Score",
                         max_lag=1, rename_y="sleep_score")

        # Stress → Recovery
        _add_correlation(results, "stress_vs_recovery",
                         stress_df, "stress_high", "Stress (high mins)",
                         readiness_df, "score", "Readiness Score",
                         max_lag=2, rename_y="readiness_score")

        # Stress → Training
        if not daily_vol.empty:
            _add_correlation(results, "stress_vs_training",
                             stress_df, "stress_high", "Stress (high mins)",
                             daily_vol, "volume", "Training Volume (kg)",
                             max_lag=1)

    # HRV Balance → Training Volume
    if not readiness_df.empty and "contributors.hrv_balance" in readiness_df.columns and not daily_vol.empty:
        _add_correlation(results, "hrv_vs_training",
                         readiness_df, "contributors.hrv_balance", "HRV Balance",
                         daily_vol, "volume", "Training Volume (kg)",
                         max_lag=1, rename_x="hrv_balance")

    # --- Body Composition Correlations ---

    # Body Fat % → Resting Heart Rate
    if not body_comp_df.empty and "body_fat_pct" in body_comp_df.columns and \
       not heartrate_df.empty and "hr_min" in heartrate_df.columns:
        _add_correlation(results, "bodyfat_vs_rhr",
                         body_comp_df, "body_fat_pct", "Body Fat %",
                         heartrate_df, "hr_min", "Resting Heart Rate (bpm)",
                         max_lag=0)

    # Weekly Training Volume → Body Composition (muscle mass)
    if not daily_vol.empty and not body_comp_df.empty and "muscle_mass_kg" in body_comp_df.columns:
        # Weekly volume around each scan date (4-week rolling average)
        if not daily_vol.empty:
            daily_vol_copy = daily_vol.copy()
            daily_vol_copy["day"] = pd.to_datetime(daily_vol_copy["day"])
            weekly_vol = daily_vol_copy.set_index("day").resample("W")["volume"].sum().reset_index()
            weekly_vol["volume_4wk_avg"] = weekly_vol["volume"].rolling(4, min_periods=1).mean()
            # Match to nearest scan
            bc = body_comp_df[["day", "muscle_mass_kg"]].copy()
            bc["day"] = pd.to_datetime(bc["day"])
            merged = pd.merge_asof(bc.sort_values("day"), weekly_vol.sort_values("day"),
                                   on="day", direction="nearest", tolerance=pd.Timedelta(days=7))
            merged = merged.dropna(subset=["volume_4wk_avg", "muscle_mass_kg"])
            if len(merged) >= MIN_DATAPOINTS:
                corr = _safe_corr(merged["volume_4wk_avg"], merged["muscle_mass_kg"])
                ci = _bootstrap_ci(merged["volume_4wk_avg"], merged["muscle_mass_kg"])
                results["volume_vs_muscle"] = {
                    "correlation": corr,
                    "data": merged[["day", "volume_4wk_avg", "muscle_mass_kg"]],
                    "x_label": "4-Week Avg Volume (kg)",
                    "y_label": "Muscle Mass (kg)",
                    "lag_days": 0,
                    "ci_low": ci[0] if ci else None,
                    "ci_high": ci[1] if ci else None,
                    "n_samples": ci[2] if ci else len(merged),
                }

    # Exercise Variety → Muscle Growth
    if not workouts_df.empty and not body_comp_df.empty and "muscle_mass_kg" in body_comp_df.columns:
        wk = workouts_df.copy()
        wk["day"] = pd.to_datetime(wk["day"])
        weekly_variety = wk.groupby(pd.Grouper(key="day", freq="W"))["exercise"].nunique().reset_index()
        weekly_variety.columns = ["day", "unique_exercises"]
        bc = body_comp_df[["day", "muscle_mass_kg"]].copy()
        bc["day"] = pd.to_datetime(bc["day"])
        merged = pd.merge_asof(bc.sort_values("day"), weekly_variety.sort_values("day"),
                               on="day", direction="nearest", tolerance=pd.Timedelta(days=7))
        merged = merged.dropna(subset=["unique_exercises", "muscle_mass_kg"])
        if len(merged) >= MIN_DATAPOINTS:
            corr = _safe_corr(merged["unique_exercises"], merged["muscle_mass_kg"])
            ci = _bootstrap_ci(merged["unique_exercises"], merged["muscle_mass_kg"])
            results["exercise_variety_vs_muscle"] = {
                "correlation": corr,
                "data": merged[["day", "unique_exercises", "muscle_mass_kg"]],
                "x_label": "Unique Exercises/Week",
                "y_label": "Muscle Mass (kg)",
                "lag_days": 0,
                "ci_low": ci[0] if ci else None,
                "ci_high": ci[1] if ci else None,
                "n_samples": ci[2] if ci else len(merged),
            }

    logger.info("Computed %d correlation analyses", len(results))
    return results
