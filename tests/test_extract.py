"""Tests for src/extract.py — incremental sync helpers."""

import json

import pytest

from src.extract import _get_last_sync, _incremental_start, _save_sync_meta


def test_get_last_sync_no_file(tmp_path):
    assert _get_last_sync(tmp_path, "oura") is None


def test_get_last_sync_with_meta(tmp_path):
    oura_dir = tmp_path / "oura"
    oura_dir.mkdir()
    meta = {"last_sync_date": "2026-02-15"}
    (oura_dir / "_metadata.json").write_text(json.dumps(meta))
    assert _get_last_sync(tmp_path, "oura") == "2026-02-15"


def test_save_sync_meta_creates_file(tmp_path):
    _save_sync_meta(tmp_path, "hevy", "2026-03-01", {"workouts": 42})
    meta_file = tmp_path / "hevy" / "_metadata.json"
    assert meta_file.exists()
    meta = json.loads(meta_file.read_text())
    assert meta["last_sync_date"] == "2026-03-01"
    assert meta["record_counts"]["workouts"] == 42


def test_save_sync_meta_updates_existing(tmp_path):
    _save_sync_meta(tmp_path, "oura", "2026-01-01", {"sleep": 30})
    _save_sync_meta(tmp_path, "oura", "2026-02-01", {"sleep": 60})
    meta = json.loads((tmp_path / "oura" / "_metadata.json").read_text())
    assert meta["last_sync_date"] == "2026-02-01"
    assert meta["record_counts"]["sleep"] == 60


def test_incremental_start_no_prior_sync(tmp_path):
    result = _incremental_start(tmp_path, "oura", "2025-01-01")
    assert result == "2025-01-01"


def test_incremental_start_with_prior_sync(tmp_path):
    oura_dir = tmp_path / "oura"
    oura_dir.mkdir()
    meta = {"last_sync_date": "2026-02-15"}
    (oura_dir / "_metadata.json").write_text(json.dumps(meta))
    # Requested start is earlier, so incremental start should be last_sync - 1 day
    result = _incremental_start(tmp_path, "oura", "2025-01-01")
    assert result == "2026-02-14"


def test_incremental_start_requested_after_last_sync(tmp_path):
    oura_dir = tmp_path / "oura"
    oura_dir.mkdir()
    meta = {"last_sync_date": "2025-06-01"}
    (oura_dir / "_metadata.json").write_text(json.dumps(meta))
    # Requested start is after last sync — use requested start
    result = _incremental_start(tmp_path, "oura", "2026-01-01")
    assert result == "2026-01-01"
