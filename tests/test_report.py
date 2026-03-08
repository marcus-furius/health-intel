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
    compute_alerts,
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


# --- compute_alerts ---


class TestComputeAlerts:
    def test_empty_datasets(self):
        """All empty → no alerts."""
        datasets = {k: pd.DataFrame() for k in [
            "sleep", "readiness", "activity", "workouts", "body_composition", "nutrition", "stress", "spo2"
        ]}
        alerts = compute_alerts(datasets, {})
        assert alerts == []

    def test_returns_list_of_dicts(self, sample_datasets):
        alerts = compute_alerts(sample_datasets, {})
        assert isinstance(alerts, list)
        for alert in alerts:
            assert isinstance(alert, dict)
            assert "severity" in alert
            assert "title" in alert
            assert "detail" in alert
            assert "intervention" in alert
            assert "category" in alert

    def test_severity_order(self, sample_datasets):
        """Alerts should be sorted: high → medium → low → positive."""
        alerts = compute_alerts(sample_datasets, {})
        if len(alerts) >= 2:
            order = {"high": 0, "medium": 1, "low": 2, "positive": 3}
            severities = [order.get(a["severity"], 99) for a in alerts]
            assert severities == sorted(severities)

    def test_low_sleep_generates_alert(self):
        """Sleep scores all below 65 → high severity alert."""
        dates = pd.date_range("2026-01-01", periods=30, freq="D")
        sleep_df = pd.DataFrame({"day": dates, "score": [50] * 30})
        datasets = {"sleep": sleep_df, "readiness": pd.DataFrame(), "activity": pd.DataFrame(),
                     "workouts": pd.DataFrame(), "body_composition": pd.DataFrame(),
                     "nutrition": pd.DataFrame(), "stress": pd.DataFrame(), "spo2": pd.DataFrame()}
        alerts = compute_alerts(datasets, {})
        sleep_alerts = [a for a in alerts if "Sleep" in a["title"] or "sleep" in a["title"].lower()]
        assert len(sleep_alerts) > 0
        assert any(a["severity"] == "high" for a in sleep_alerts)

    def test_low_steps_generates_alert(self):
        """Steps below 5000 → medium alert."""
        dates = pd.date_range("2026-01-01", periods=30, freq="D")
        activity_df = pd.DataFrame({"day": dates, "steps": [3000] * 30})
        datasets = {"sleep": pd.DataFrame(), "readiness": pd.DataFrame(), "activity": activity_df,
                     "workouts": pd.DataFrame(), "body_composition": pd.DataFrame(),
                     "nutrition": pd.DataFrame(), "stress": pd.DataFrame(), "spo2": pd.DataFrame()}
        alerts = compute_alerts(datasets, {})
        movement_alerts = [a for a in alerts if "Movement" in a["title"] or "Steps" in a["title"]]
        assert len(movement_alerts) > 0

    def test_sedentary_alert(self):
        """Sedentary > 8 hours → alert."""
        dates = pd.date_range("2026-01-01", periods=30, freq="D")
        activity_df = pd.DataFrame({"day": dates, "steps": [8000] * 30, "sedentary_time": [35000] * 30})
        datasets = {"sleep": pd.DataFrame(), "readiness": pd.DataFrame(), "activity": activity_df,
                     "workouts": pd.DataFrame(), "body_composition": pd.DataFrame(),
                     "nutrition": pd.DataFrame(), "stress": pd.DataFrame(), "spo2": pd.DataFrame()}
        alerts = compute_alerts(datasets, {})
        sed_alerts = [a for a in alerts if "Sedentary" in a["title"]]
        assert len(sed_alerts) > 0

    def test_no_crash_with_partial_data(self):
        """Only sleep data — should not crash."""
        dates = pd.date_range("2026-01-01", periods=30, freq="D")
        sleep_df = pd.DataFrame({"day": dates, "score": [75] * 30})
        datasets = {"sleep": sleep_df}
        alerts = compute_alerts(datasets, {})
        assert isinstance(alerts, list)
