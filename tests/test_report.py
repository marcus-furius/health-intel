"""Tests for src/report.py — report generation and helpers."""

import pandas as pd
import pytest

from src.report import (
    _alerts_section,
    _corr_strength,
    _nutrition_section,
    _recent_trend,
    _stress_section,
    _weekly_resample,
    generate_report,
)


# --- Helper functions ---


class TestCorrStrength:
    def test_none_returns_insufficient(self):
        assert _corr_strength(None) == "insufficient data"

    def test_strong_positive(self):
        assert _corr_strength(0.7) == "strong"

    def test_strong_negative(self):
        assert _corr_strength(-0.65) == "strong"

    def test_moderate(self):
        assert _corr_strength(0.4) == "moderate"

    def test_weak(self):
        assert _corr_strength(0.1) == "weak"


class TestRecentTrend:
    def test_increasing(self):
        """Ascending series → positive slope."""
        series = pd.Series(range(30), dtype=float)
        slope = _recent_trend(series)
        assert slope is not None
        assert slope > 0

    def test_insufficient_data(self):
        """6 values (< 7 minimum) → None."""
        series = pd.Series([1, 2, 3, 4, 5, 6], dtype=float)
        result = _recent_trend(series)
        assert result is None

    def test_constant(self):
        """All same values → slope 0.0."""
        series = pd.Series([5.0] * 30)
        result = _recent_trend(series)
        assert result == 0.0


class TestWeeklyResample:
    def test_basic(self):
        """30 daily rows → approximately 4-5 weekly rows."""
        dates = pd.date_range("2026-01-01", periods=30, freq="D")
        df = pd.DataFrame({"day": dates, "value": range(30)})
        weekly = _weekly_resample(df, "day", "value")
        assert 3 <= len(weekly) <= 6
        assert "day" in weekly.columns
        assert "value" in weekly.columns


# --- Section smoke tests ---


def test_nutrition_section_with_data(sample_datasets):
    result = _nutrition_section(sample_datasets)
    assert isinstance(result, str)
    assert "## Nutrition" in result
    assert "Calories" in result


def test_nutrition_section_empty():
    result = _nutrition_section({"nutrition": pd.DataFrame()})
    assert "No MyFitnessPal data" in result


def test_stress_section_with_data(sample_datasets):
    result = _stress_section(sample_datasets)
    assert isinstance(result, str)
    assert "## Stress" in result


def test_stress_section_empty():
    result = _stress_section({"stress": pd.DataFrame()})
    assert "No stress data" in result


def test_alerts_section_no_alerts():
    """All empty datasets → 'No alerts' message."""
    datasets = {k: pd.DataFrame() for k in ["sleep", "readiness", "activity", "workouts", "body_composition", "nutrition", "stress"]}
    result = _alerts_section(datasets, {})
    assert "No alerts" in result


def test_generate_report_creates_file(tmp_path, sample_datasets):
    report_path = generate_report(
        start_date="2026-01-01",
        end_date="2026-01-30",
        datasets=sample_datasets,
        correlations={},
        output_dir=tmp_path,
    )
    assert report_path.exists()
    content = report_path.read_text()
    assert content.startswith("# Unified")


def test_generate_report_all_empty(tmp_path):
    """All empty datasets should still produce a valid report file."""
    datasets = {k: pd.DataFrame() for k in ["sleep", "readiness", "activity", "workouts", "nutrition", "body_composition", "stress"]}
    report_path = generate_report(
        start_date="2026-01-01",
        end_date="2026-01-30",
        datasets=datasets,
        correlations={},
        output_dir=tmp_path,
    )
    assert report_path.exists()
    content = report_path.read_text()
    assert "# Unified" in content
