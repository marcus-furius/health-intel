"""Data extraction orchestration — pulls from all available sources."""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_last_sync(raw_dir: Path, source: str) -> str | None:
    """Read _metadata.json for a source's last sync date."""
    meta_file = raw_dir / source / "_metadata.json"
    if not meta_file.exists():
        return None
    try:
        with open(meta_file, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        return meta.get("last_sync_date")
    except (json.JSONDecodeError, OSError):
        return None


def _save_sync_meta(raw_dir: Path, source: str, end_date: str, counts: dict[str, int]) -> None:
    """Update _metadata.json with the latest sync info."""
    meta_file = raw_dir / source / "_metadata.json"
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {}
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    meta["last_sync_date"] = end_date
    meta["last_sync_at"] = datetime.now().isoformat()
    meta["record_counts"] = counts
    with open(meta_file, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)


def _incremental_start(raw_dir: Path, source: str, requested_start: str) -> str:
    """Return the effective start date for incremental sync.

    If a previous sync exists and its end date is after the requested start,
    use (last_sync_date - 1 day) as the start to get a small overlap for dedup.
    """
    last = _get_last_sync(raw_dir, source)
    if not last:
        return requested_start
    try:
        last_dt = datetime.strptime(last, "%Y-%m-%d")
        req_dt = datetime.strptime(requested_start, "%Y-%m-%d")
        # Only use incremental if last sync is after requested start
        if last_dt > req_dt:
            # 1-day overlap to catch any edge-case missing records
            effective = (last_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            logger.info(
                "%s: incremental sync from %s (last sync: %s, requested: %s)",
                source, effective, last, requested_start,
            )
            return effective
    except ValueError:
        pass
    return requested_start


def extract_all(start_date: str, end_date: str, data_dir: Path) -> dict[str, dict[str, int]]:
    """Extract data from all configured sources.

    Returns a nested dict: source -> endpoint -> record count.
    Continues gracefully if any source is unavailable.
    """
    raw_dir = data_dir / "raw"
    all_counts: dict[str, dict[str, int]] = {}

    # --- Oura ---
    oura_token = os.getenv("OURA_TOKEN")
    if oura_token:
        eff_start = _incremental_start(raw_dir, "oura", start_date)
        logger.info("Extracting from Oura Ring (%s to %s)...", eff_start, end_date)
        try:
            from src.sources.oura import OuraSource
            oura = OuraSource(oura_token)
            oura_data = oura.pull(eff_start, end_date)
            counts = oura.save_raw(oura_data, raw_dir / "oura", eff_start, end_date)
            all_counts["oura"] = counts
            _save_sync_meta(raw_dir, "oura", end_date, counts)
        except Exception:
            logger.exception("Oura extraction failed")
            all_counts["oura"] = {}
    else:
        logger.warning("OURA_TOKEN not set — skipping Oura")

    # --- Hevy ---
    hevy_key = os.getenv("HEVY_API_KEY")
    if hevy_key:
        eff_start = _incremental_start(raw_dir, "hevy", start_date)
        logger.info("Extracting from Hevy (%s to %s)...", eff_start, end_date)
        try:
            from src.sources.hevy import HevySource
            hevy = HevySource(hevy_key)
            hevy_data = hevy.pull(eff_start, end_date)
            counts = hevy.save_raw(hevy_data, raw_dir / "hevy", eff_start, end_date)
            all_counts["hevy"] = counts
            _save_sync_meta(raw_dir, "hevy", end_date, counts)
        except Exception:
            logger.exception("Hevy extraction failed")
            all_counts["hevy"] = {}
    else:
        logger.warning("HEVY_API_KEY not set — skipping Hevy")

    # --- Boditrax ---
    boditrax_mode = os.getenv("BODITRAX_MODE", "csv")
    logger.info("Extracting from Boditrax (mode: %s)...", boditrax_mode)
    try:
        from src.sources.boditrax import BoditraxSource
        boditrax = BoditraxSource(mode=boditrax_mode)
        boditrax_raw_dir = raw_dir / "boditrax"
        boditrax_data = boditrax.pull(start_date, end_date, raw_dir=boditrax_raw_dir)
        counts = boditrax.save_raw(boditrax_data, boditrax_raw_dir, start_date, end_date)
        all_counts["boditrax"] = counts
        _save_sync_meta(raw_dir, "boditrax", end_date, counts)
    except Exception:
        logger.exception("Boditrax extraction failed")
        all_counts["boditrax"] = {}

    # --- MyFitnessPal (CSV export from MFP Premium) ---
    mfp_enabled = os.getenv("MFP_ENABLED", "true").lower() != "false"
    if mfp_enabled:
        logger.info("Extracting from MyFitnessPal (CSV export)...")
        try:
            from src.sources.mfp import MfpSource
            mfp = MfpSource()
            mfp_raw_dir = raw_dir / "mfp"
            mfp_data = mfp.pull(start_date, end_date, raw_dir=mfp_raw_dir)
            counts = mfp.save_raw(mfp_data, mfp_raw_dir, start_date, end_date)
            all_counts["mfp"] = counts
            _save_sync_meta(raw_dir, "mfp", end_date, counts)
        except Exception:
            logger.exception(
                "MFP extraction failed. Place your MFP Premium CSV export "
                "in data/raw/mfp/. Set MFP_ENABLED=false to skip."
            )
            all_counts["mfp"] = {}
    else:
        logger.info("MFP_ENABLED=false — skipping MyFitnessPal")

    # --- Bloodwork ---
    logger.info("Extracting from Bloodwork (manual JSON)...")
    try:
        from src.sources.bloodwork import BloodworkSource
        bloodwork = BloodworkSource()
        bloodwork_data = bloodwork.pull()
        counts = bloodwork.save_raw(bloodwork_data, raw_dir / "bloodwork")
        all_counts["bloodwork"] = {"results": counts}
        _save_sync_meta(raw_dir, "bloodwork", end_date, {"results": counts})
    except Exception:
        logger.exception("Bloodwork extraction failed")
        all_counts["bloodwork"] = {}

    return all_counts
