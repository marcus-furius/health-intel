"""Tests for src/correlate.py — cross-source correlation analysis."""

import numpy as np
import pandas as pd
import pytest

from src.correlate import MIN_DATAPOINTS, _merge_on_day, _safe_corr, compute_correlations


# --- _safe_corr ---


def test_safe_corr_sufficient_data():
    """20 data points → returns float in [-1, 1]."""
    a = pd.Series(range(20), dtype=float)
    b = pd.Series([x * 2 + 1 for x in range(20)], dtype=float)
    result = _safe_corr(a, b)
    assert result is not None
    assert -1 <= result <= 1


def test_safe_corr_insufficient_data():
    """13 points (< MIN_DATAPOINTS) → None."""
    a = pd.Series(range(13), dtype=float)
    b = pd.Series(range(13), dtype=float)
    result = _safe_corr(a, b)
    assert result is None


def test_safe_corr_boundary_14():
    """Exactly 14 points → should return float, not None."""
    a = pd.Series(range(14), dtype=float)
    b = pd.Series(range(14), dtype=float)
    result = _safe_corr(a, b)
    assert result is not None
    assert isinstance(result, float)


def test_safe_corr_all_nan():
    """All NaN → None."""
    a = pd.Series([float("nan")] * 20)
    b = pd.Series([float("nan")] * 20)
    result = _safe_corr(a, b)
    assert result is None


def test_safe_corr_perfect_correlation():
    """Perfectly correlated series → r ≈ 1.0."""
    a = pd.Series(range(20), dtype=float)
    b = pd.Series(range(20), dtype=float)
    result = _safe_corr(a, b)
    assert result == pytest.approx(1.0)


def test_safe_corr_symmetric():
    """corr(a, b) == corr(b, a)."""
    rng = np.random.default_rng(42)
    a = pd.Series(rng.normal(size=20))
    b = pd.Series(rng.normal(size=20))
    assert _safe_corr(a, b) == pytest.approx(_safe_corr(b, a))


# --- _merge_on_day ---


def test_merge_on_day_inner_join():
    """Only matching days should appear in the result."""
    dates_a = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"])
    dates_b = pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04"])
    df_a = pd.DataFrame({"day": dates_a, "score": [70, 80, 75]})
    df_b = pd.DataFrame({"day": dates_b, "steps": [5000, 6000, 7000]})

    merged = _merge_on_day(df_a, df_b, ["score"], ["steps"])
    assert len(merged) == 2
    assert set(merged["day"]) == {pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-03")}


def test_merge_on_day_no_overlap():
    """No overlapping days → empty DataFrame."""
    df_a = pd.DataFrame({"day": pd.to_datetime(["2026-01-01"]), "score": [70]})
    df_b = pd.DataFrame({"day": pd.to_datetime(["2026-02-01"]), "steps": [5000]})
    merged = _merge_on_day(df_a, df_b, ["score"], ["steps"])
    assert merged.empty


def test_merge_on_day_empty_input():
    """Empty input DataFrames → empty result."""
    df_a = pd.DataFrame({"day": pd.Series(dtype="datetime64[ns]"), "score": pd.Series(dtype=float)})
    df_b = pd.DataFrame({"day": pd.Series(dtype="datetime64[ns]"), "steps": pd.Series(dtype=float)})
    merged = _merge_on_day(df_a, df_b, ["score"], ["steps"])
    assert merged.empty


# --- compute_correlations ---


def test_compute_correlations_all_empty():
    """All empty DataFrames → empty results dict."""
    datasets = {k: pd.DataFrame() for k in ["sleep", "readiness", "activity", "workouts", "nutrition"]}
    result = compute_correlations(datasets)
    assert result == {}


def test_compute_correlations_with_data(sample_sleep_df, sample_readiness_df):
    """Sleep + readiness data → sleep_vs_readiness key present."""
    datasets = {
        "sleep": sample_sleep_df,
        "readiness": sample_readiness_df,
    }
    result = compute_correlations(datasets)
    assert "sleep_vs_readiness" in result
    corr_val = result["sleep_vs_readiness"]["correlation"]
    assert corr_val is None or isinstance(corr_val, float)


def test_compute_correlations_stress(sample_stress_df, sample_sleep_df):
    """Stress + sleep data → stress_vs_sleep key present."""
    datasets = {
        "stress": sample_stress_df,
        "sleep": sample_sleep_df,
    }
    result = compute_correlations(datasets)
    assert "stress_vs_sleep" in result
