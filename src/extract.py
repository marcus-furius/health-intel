"""Data extraction orchestration — pulls from all available sources."""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
        logger.info("Extracting from Oura Ring...")
        try:
            from src.sources.oura import OuraSource
            oura = OuraSource(oura_token)
            oura_data = oura.pull(start_date, end_date)
            all_counts["oura"] = oura.save_raw(oura_data, raw_dir / "oura", start_date, end_date)
        except Exception:
            logger.exception("Oura extraction failed")
            all_counts["oura"] = {}
    else:
        logger.warning("OURA_TOKEN not set — skipping Oura")

    # --- Hevy ---
    hevy_key = os.getenv("HEVY_API_KEY")
    if hevy_key:
        logger.info("Extracting from Hevy...")
        try:
            from src.sources.hevy import HevySource
            hevy = HevySource(hevy_key)
            hevy_data = hevy.pull(start_date, end_date)
            all_counts["hevy"] = hevy.save_raw(hevy_data, raw_dir / "hevy", start_date, end_date)
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
        all_counts["boditrax"] = boditrax.save_raw(boditrax_data, boditrax_raw_dir, start_date, end_date)
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
            all_counts["mfp"] = mfp.save_raw(mfp_data, mfp_raw_dir, start_date, end_date)
        except Exception:
            logger.exception(
                "MFP extraction failed. Place your MFP Premium CSV export "
                "in data/raw/mfp/. Set MFP_ENABLED=false to skip."
            )
            all_counts["mfp"] = {}
    else:
        logger.info("MFP_ENABLED=false — skipping MyFitnessPal")

    return all_counts
