"""Tests for src/api — route helpers and endpoint logic."""

import math

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.routes import _aggregate, _df_to_records, _filter_dates, _forward_fill_daily, _paginate, _sparkline


# --- _filter_dates ---


class TestFilterDates:
    def _make_df(self, n=10):
        dates = pd.date_range("2026-01-01", periods=n, freq="D")
        return pd.DataFrame({"day": dates, "score": range(n)})

    def test_no_filters(self):
        df = self._make_df()
        result = _filter_dates(df, None, None)
        assert len(result) == 10

    def test_start_only(self):
        from datetime import date
        df = self._make_df()
        result = _filter_dates(df, date(2026, 1, 5), None)
        assert len(result) == 6  # Jan 5-10

    def test_end_only(self):
        from datetime import date
        df = self._make_df()
        result = _filter_dates(df, None, date(2026, 1, 5))
        assert len(result) == 5  # Jan 1-5

    def test_both_dates(self):
        from datetime import date
        df = self._make_df()
        result = _filter_dates(df, date(2026, 1, 3), date(2026, 1, 7))
        assert len(result) == 5  # Jan 3-7

    def test_empty_df(self):
        df = pd.DataFrame()
        result = _filter_dates(df, None, None)
        assert result.empty

    def test_no_day_column(self):
        df = pd.DataFrame({"score": [1, 2, 3]})
        result = _filter_dates(df, None, None)
        assert len(result) == 3  # returned unchanged

    def test_range_with_no_data(self):
        from datetime import date
        df = self._make_df()
        result = _filter_dates(df, date(2026, 6, 1), date(2026, 6, 30))
        assert result.empty


# --- _df_to_records ---


class TestDfToRecords:
    def test_basic_conversion(self):
        df = pd.DataFrame({"day": pd.to_datetime(["2026-01-01"]), "score": [75.0]})
        records = _df_to_records(df)
        assert len(records) == 1
        assert records[0]["day"] == "2026-01-01"
        assert records[0]["score"] == 75.0

    def test_nan_to_none(self):
        df = pd.DataFrame({"day": pd.to_datetime(["2026-01-01"]), "score": [float("nan")]})
        records = _df_to_records(df)
        assert records[0]["score"] is None

    def test_inf_to_none(self):
        df = pd.DataFrame({"day": pd.to_datetime(["2026-01-01"]), "val": [float("inf")]})
        records = _df_to_records(df)
        assert records[0]["val"] is None

    def test_neg_inf_to_none(self):
        df = pd.DataFrame({"day": pd.to_datetime(["2026-01-01"]), "val": [float("-inf")]})
        records = _df_to_records(df)
        assert records[0]["val"] is None

    def test_empty_df(self):
        df = pd.DataFrame()
        records = _df_to_records(df)
        assert records == []

    def test_datetime_formatting(self):
        df = pd.DataFrame({"day": pd.to_datetime(["2026-03-15"]), "v": [1]})
        records = _df_to_records(df)
        assert records[0]["day"] == "2026-03-15"


# --- _forward_fill_daily ---


class TestForwardFillDaily:
    def test_fills_gaps(self):
        dates = pd.to_datetime(["2026-01-01", "2026-01-03", "2026-01-05"])
        df = pd.DataFrame({"day": dates, "weight_kg": [80.0, 81.0, 82.0]})
        result = _forward_fill_daily(df, "weight_kg")
        assert len(result) == 5  # Jan 1-5, daily
        # Jan 2 should be forward-filled from Jan 1
        assert result.iloc[1]["weight_kg"] == 80.0
        # Jan 4 should be forward-filled from Jan 3
        assert result.iloc[3]["weight_kg"] == 81.0

    def test_empty_df(self):
        result = _forward_fill_daily(pd.DataFrame(), "weight_kg")
        assert result.empty

    def test_missing_column(self):
        df = pd.DataFrame({"day": pd.to_datetime(["2026-01-01"]), "score": [1]})
        result = _forward_fill_daily(df, "weight_kg")
        assert len(result) == len(df)  # returned unchanged

    def test_no_day_column(self):
        df = pd.DataFrame({"weight_kg": [80.0]})
        result = _forward_fill_daily(df, "weight_kg")
        assert len(result) == len(df)  # returned unchanged


# --- _sparkline ---


class TestSparkline:
    def test_basic(self):
        dates = pd.date_range("2026-01-01", periods=5, freq="D")
        df = pd.DataFrame({"day": dates, "score": [70, 75, 80, 85, 90]})
        points = _sparkline(df, "score", days=5)
        assert len(points) == 5
        assert points[0].date == "2026-01-01"
        assert points[0].value == 70

    def test_limits_to_n_days(self):
        dates = pd.date_range("2026-01-01", periods=60, freq="D")
        df = pd.DataFrame({"day": dates, "score": range(60)})
        points = _sparkline(df, "score", days=30)
        assert len(points) == 30

    def test_nan_value(self):
        dates = pd.date_range("2026-01-01", periods=3, freq="D")
        df = pd.DataFrame({"day": dates, "score": [70, float("nan"), 80]})
        points = _sparkline(df, "score", days=3)
        assert points[1].value is None

    def test_empty_df(self):
        points = _sparkline(pd.DataFrame(), "score")
        assert points == []

    def test_missing_column(self):
        df = pd.DataFrame({"day": pd.to_datetime(["2026-01-01"]), "other": [1]})
        points = _sparkline(df, "score")
        assert points == []


# --- API endpoint integration tests ---


@pytest.fixture
def app_client(sample_datasets):
    """Create a test client with sample datasets loaded."""
    import src.api.server as server_mod
    from src.api.server import app
    server_mod.datasets = sample_datasets
    return TestClient(app)


def test_sleep_endpoint_returns_data(app_client):
    resp = app_client.get("/api/sleep")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) > 0
    assert "day" in data[0]
    assert "score" in data[0]


def test_sleep_endpoint_date_filter(app_client):
    resp = app_client.get("/api/sleep?start=2026-01-10&end=2026-01-20")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for row in data:
        assert row["day"] >= "2026-01-10"
        assert row["day"] <= "2026-01-20"


def test_readiness_endpoint(app_client):
    resp = app_client.get("/api/readiness")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) > 0


def test_activity_endpoint(app_client):
    resp = app_client.get("/api/activity")
    assert resp.status_code == 200


def test_stress_endpoint(app_client):
    resp = app_client.get("/api/stress")
    assert resp.status_code == 200


def test_training_endpoint(app_client):
    resp = app_client.get("/api/training")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "daily" in body


def test_nutrition_endpoint(app_client):
    resp = app_client.get("/api/nutrition")
    assert resp.status_code == 200


def test_correlations_endpoint(app_client):
    resp = app_client.get("/api/correlations")
    assert resp.status_code == 200
    body = resp.json()
    assert "correlations" in body
    for corr in body["correlations"]:
        assert "key" in corr
        assert "r_value" in corr
        assert "ci_low" in corr
        assert "ci_high" in corr
        assert "n_samples" in corr
        assert "lag_days" in corr


def test_overview_endpoint(app_client):
    resp = app_client.get("/api/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert "metrics" in body
    assert "alerts" in body
    assert "alert_counts" in body


def test_alerts_endpoint(app_client):
    resp = app_client.get("/api/alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert "alerts" in body
    for alert in body["alerts"]:
        assert "severity" in alert
        assert "title" in alert
        assert "detail" in alert
        assert "intervention" in alert


def test_streaks_endpoint(app_client):
    resp = app_client.get("/api/streaks")
    assert resp.status_code == 200
    body = resp.json()
    assert "streaks" in body


def test_training_recommendation_endpoint(app_client):
    resp = app_client.get("/api/training/recommendation")
    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert "intensity" in body
    assert "detail" in body


def test_digest_endpoint(app_client):
    resp = app_client.get("/api/digest")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body


def test_records_endpoint(app_client):
    resp = app_client.get("/api/records")
    assert resp.status_code == 200
    assert "records" in resp.json()


def test_forecasts_endpoint(app_client):
    resp = app_client.get("/api/forecasts")
    assert resp.status_code == 200
    assert "forecasts" in resp.json()


def test_reload_endpoint(app_client):
    resp = app_client.post("/api/reload")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# --- Empty dataset edge cases ---


@pytest.fixture
def empty_client():
    """Test client with all empty datasets."""
    import src.api.server as server_mod
    from src.api.server import app
    server_mod.datasets = {k: pd.DataFrame() for k in [
        "sleep", "readiness", "activity", "workouts", "nutrition",
        "body_composition", "stress", "heartrate", "spo2", "mfp_weight",
    ]}
    return TestClient(app)


def test_overview_empty(empty_client):
    resp = empty_client.get("/api/overview")
    assert resp.status_code == 200
    assert resp.json()["metrics"] == []


def test_correlations_empty(empty_client):
    resp = empty_client.get("/api/correlations")
    assert resp.status_code == 200
    assert resp.json()["correlations"] == []


def test_alerts_empty(empty_client):
    resp = empty_client.get("/api/alerts")
    assert resp.status_code == 200
    assert resp.json()["alerts"] == []


def test_streaks_empty(empty_client):
    resp = empty_client.get("/api/streaks")
    assert resp.status_code == 200
    assert resp.json()["streaks"] == []


def test_forecasts_empty(empty_client):
    resp = empty_client.get("/api/forecasts")
    assert resp.status_code == 200
    assert resp.json()["forecasts"] == []


# --- _paginate ---


class TestPaginate:
    def test_no_limit(self):
        records = [{"a": i} for i in range(10)]
        result = _paginate(records, None, 0)
        assert result["total"] == 10
        assert len(result["data"]) == 10
        assert result["limit"] is None
        assert result["offset"] == 0

    def test_with_limit(self):
        records = [{"a": i} for i in range(10)]
        result = _paginate(records, 3, 0)
        assert result["total"] == 10
        assert len(result["data"]) == 3
        assert result["data"][0]["a"] == 0

    def test_with_offset(self):
        records = [{"a": i} for i in range(10)]
        result = _paginate(records, 3, 5)
        assert result["total"] == 10
        assert len(result["data"]) == 3
        assert result["data"][0]["a"] == 5

    def test_offset_beyond_data(self):
        records = [{"a": i} for i in range(5)]
        result = _paginate(records, 10, 20)
        assert result["total"] == 5
        assert len(result["data"]) == 0

    def test_empty_records(self):
        result = _paginate([], 10, 0)
        assert result["total"] == 0
        assert result["data"] == []


# --- _aggregate ---


class TestAggregate:
    def test_weekly(self):
        dates = pd.date_range("2026-01-01", periods=21, freq="D")
        df = pd.DataFrame({"day": dates, "score": range(21)})
        result = _aggregate(df, "W")
        assert len(result) < 21
        assert "day" in result.columns
        assert "score" in result.columns

    def test_monthly(self):
        dates = pd.date_range("2026-01-01", periods=60, freq="D")
        df = pd.DataFrame({"day": dates, "score": range(60)})
        result = _aggregate(df, "ME")
        assert len(result) <= 3  # ~2 months

    def test_empty_df(self):
        result = _aggregate(pd.DataFrame(), "W")
        assert result.empty

    def test_no_day_column(self):
        df = pd.DataFrame({"score": [1, 2, 3]})
        result = _aggregate(df, "W")
        assert len(result) == 3  # returned unchanged


# --- Pagination on endpoints ---


def test_sleep_pagination(app_client):
    resp = app_client.get("/api/sleep?limit=5&offset=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 30  # sample_sleep_df has 30 rows
    assert len(body["data"]) == 5
    assert body["limit"] == 5
    assert body["offset"] == 2


def test_sleep_aggregation_weekly(app_client):
    resp = app_client.get("/api/sleep?aggregate=weekly")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] < 30  # aggregated to fewer rows
    assert len(body["data"]) > 0


def test_nutrition_pagination(app_client):
    resp = app_client.get("/api/nutrition?limit=3")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 3
    assert body["total"] == 30
