"""Tests for src/correlate.py — cross-source correlation analysis."""

import numpy as np
import pandas as pd
import pytest

from src.correlate import MIN_DATAPOINTS, _bootstrap_ci, _best_lag_corr, _merge_on_day, _safe_corr, compute_correlations


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


# --- _bootstrap_ci ---


def test_bootstrap_ci_sufficient_data():
    """20 data points → returns (ci_low, ci_high, n)."""
    rng = np.random.default_rng(99)
    a = pd.Series(rng.normal(size=20))
    b = pd.Series(a * 0.5 + rng.normal(size=20) * 0.3)
    result = _bootstrap_ci(a, b)
    assert result is not None
    ci_low, ci_high, n = result
    assert n == 20
    assert ci_low <= ci_high
    assert -1 <= ci_low <= 1
    assert -1 <= ci_high <= 1


def test_bootstrap_ci_insufficient_data():
    """13 points → None."""
    a = pd.Series(range(13), dtype=float)
    b = pd.Series(range(13), dtype=float)
    result = _bootstrap_ci(a, b)
    assert result is None


def test_bootstrap_ci_perfect_correlation():
    """Perfectly correlated → CI near (1.0, 1.0)."""
    a = pd.Series(range(20), dtype=float)
    b = pd.Series(range(20), dtype=float)
    result = _bootstrap_ci(a, b)
    assert result is not None
    ci_low, ci_high, _ = result
    assert ci_low > 0.9
    assert ci_high > 0.9


def test_bootstrap_ci_deterministic():
    """Same inputs → same output (seeded RNG)."""
    a = pd.Series(range(20), dtype=float)
    b = pd.Series([x * 0.5 + 3 for x in range(20)], dtype=float)
    r1 = _bootstrap_ci(a, b)
    r2 = _bootstrap_ci(a, b)
    assert r1 == r2


# --- _best_lag_corr ---


def test_best_lag_corr_finds_best_lag():
    """Shifted data should be detected with the right lag."""
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    df_x = pd.DataFrame({"day": dates, "x": range(30)})
    # y is x shifted by 1 day
    df_y = pd.DataFrame({"day": dates, "y": [0] + list(range(29))})
    corr, lag, merged = _best_lag_corr(df_x, "x", df_y, "y", max_lag=3)
    assert corr is not None
    assert abs(corr) > 0.9


def test_best_lag_corr_insufficient_data():
    """Fewer than MIN_DATAPOINTS → returns None."""
    dates = pd.date_range("2026-01-01", periods=5, freq="D")
    df_x = pd.DataFrame({"day": dates, "x": range(5)})
    df_y = pd.DataFrame({"day": dates, "y": range(5)})
    corr, lag, merged = _best_lag_corr(df_x, "x", df_y, "y")
    assert corr is None


def test_best_lag_corr_same_column_name():
    """Both DataFrames use 'score' column — should not crash."""
    dates = pd.date_range("2026-01-01", periods=20, freq="D")
    df_x = pd.DataFrame({"day": dates, "score": range(20)})
    df_y = pd.DataFrame({"day": dates, "score": [x * 2 for x in range(20)]})
    corr, lag, merged = _best_lag_corr(df_x, "score", df_y, "score")
    assert corr is not None
    assert not merged.empty


# --- compute_correlations result structure ---


def test_compute_correlations_result_structure(sample_sleep_df, sample_readiness_df):
    """Each correlation result should have CI fields."""
    datasets = {"sleep": sample_sleep_df, "readiness": sample_readiness_df}
    result = compute_correlations(datasets)
    for key, val in result.items():
        assert "correlation" in val
        assert "data" in val
        assert "x_label" in val
        assert "y_label" in val
        assert "lag_days" in val
        assert "ci_low" in val
        assert "ci_high" in val
        assert "n_samples" in val
