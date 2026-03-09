"""Unit tests for bloodwork source and transformation."""

import json
from pathlib import Path
import pandas as pd
import pytest
from src.sources.bloodwork import BloodworkSource
from src.transform import transform_bloodwork

@pytest.fixture
def sample_bloodwork_json(tmp_path):
    data = [
        {
            "date": "2025-01-01",
            "markers": {
                "testosterone_nmol": 10.0,
                "free_testosterone_nmol": 0.2,
                "haematocrit_pct": 45.0
            }
        },
        {
            "date": "2025-02-01",
            "markers": {
                "testosterone_nmol": 20.0,
                "free_testosterone_nmol": 0.5,
                "haematocrit_pct": 48.0
            }
        }
    ]
    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    bloodwork_file = manual_dir / "bloodwork.json"
    with open(bloodwork_file, "w") as f:
        json.dump(data, f)
    return tmp_path

def test_bloodwork_source_pull(sample_bloodwork_json):
    source = BloodworkSource(raw_dir=str(sample_bloodwork_json / "manual"))
    data = source.pull()
    assert len(data["results"]) == 2
    assert data["results"][0]["date"] == "2025-01-01"

def test_bloodwork_transform(sample_bloodwork_json):
    df = transform_bloodwork(sample_bloodwork_json)
    assert not df.empty
    assert len(df) == 2
    assert "testosterone_nmol" in df.columns
    assert "haematocrit_pct" in df.columns
    assert df.iloc[0]["testosterone_nmol"] == 10.0
    assert pd.api.types.is_datetime64_any_dtype(df["day"])

def test_bloodwork_range_validation(sample_bloodwork_json):
    # Add an out-of-range value
    data = [
        {
            "date": "2025-03-01",
            "markers": {
                "testosterone_nmol": 500.0, # Way too high
                "haematocrit_pct": 45.0
            }
        }
    ]
    with open(sample_bloodwork_json / "manual" / "bloodwork.json", "w") as f:
        json.dump(data, f)
    
    df = transform_bloodwork(sample_bloodwork_json)
    # testosterone_nmol should be NaN (pd.NA) due to range validation [0, 100]
    assert pd.isna(df.iloc[0]["testosterone_nmol"])
    assert df.iloc[0]["haematocrit_pct"] == 45.0
