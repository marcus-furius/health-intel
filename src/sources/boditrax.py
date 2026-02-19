"""Boditrax source — body composition data via CSV import or browser scraper."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Map native Boditrax metric names to our standardised column names
METRIC_MAP = {
    "BodyWeight": "weight_kg",
    "FatMass": "fat_mass_kg",
    "MuscleMass": "muscle_mass_kg",
    "WaterMass": "water_mass_kg",
    "BoneMass": "bone_mass_kg",
    "VisceralFatRating": "visceral_fat",
    "MetabolicAge": "metabolic_age",
    "BasalMetabolicRatekJ": "bmr_kj",
    "BodyMassIndex": "bmi",
    "FatFreeMass": "fat_free_mass_kg",
    "BoditraxScore": "boditrax_score",
    "IntraCellularWaterMass": "intracellular_water_kg",
    "ExtraCellularWaterMass": "extracellular_water_kg",
    # Segmental
    "TrunkMuscleMass": "trunk_muscle_kg",
    "TrunkFatMass": "trunk_fat_kg",
    "LeftArmMuscleMass": "left_arm_muscle_kg",
    "LeftArmFatMass": "left_arm_fat_kg",
    "RightArmMuscleMass": "right_arm_muscle_kg",
    "RightArmFatMass": "right_arm_fat_kg",
    "LeftLegMuscleMass": "left_leg_muscle_kg",
    "LeftLegFatMass": "left_leg_fat_kg",
    "RightLegMuscleMass": "right_leg_muscle_kg",
    "RightLegFatMass": "right_leg_fat_kg",
    # Phase angles
    "PhaseAngleLeftArm": "phase_angle_left_arm",
    "PhaseAngleRightArm": "phase_angle_right_arm",
    "PhaseAngleLeftLeg": "phase_angle_left_leg",
    "PhaseAngleRightLeg": "phase_angle_right_leg",
    "PhaseAngleLeftLegLeftArm": "phase_angle_left_leg_left_arm",
    "PhaseAngleRightLegLeftLeg": "phase_angle_right_leg_left_leg",
    # Scores
    "LegMuscleScore": "leg_muscle_score",
    "MuscleScore": "muscle_score",
    "BmrScore": "bmr_score",
}


class BoditraxSource:
    """Boditrax data ingestion — native export CSV or simple wide-format CSV."""

    def __init__(self, mode: str = "csv") -> None:
        self.mode = mode

    def pull(self, start_date: str, end_date: str, raw_dir: Path | None = None) -> dict[str, list[dict[str, Any]]]:
        """Pull Boditrax data based on configured mode."""
        if self.mode == "csv":
            return self._pull_csv(raw_dir, start_date, end_date)
        elif self.mode == "scraper":
            return self._pull_scraper(start_date, end_date)
        else:
            logger.error("Unknown Boditrax mode: %s", self.mode)
            return {"scans": []}

    def _pull_csv(self, raw_dir: Path | None, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
        """Read Boditrax CSV files from raw directory.

        Supports two formats:
        1. Native Boditrax account export (BoditraxAccount_*.csv) — long format with
           header sections and BodyMetricTypeId,Value,CreatedDate rows
        2. Simple wide-format CSVs (boditrax_scan_*.csv) — one row per scan
        """
        if raw_dir is None:
            logger.warning("No raw directory provided for Boditrax CSV mode")
            return {"scans": []}

        all_scans: list[dict[str, Any]] = []

        # Try native Boditrax account exports first
        native_files = sorted(raw_dir.glob("BoditraxAccount_*.csv"))
        for csv_file in native_files:
            scans = self._parse_native_export(csv_file, start_date, end_date)
            all_scans.extend(scans)

        # Also try simple wide-format CSVs
        simple_files = sorted(raw_dir.glob("boditrax_scan_*.csv"))
        for csv_file in simple_files:
            try:
                scan_df = pd.read_csv(csv_file)
                for _, row in scan_df.iterrows():
                    record = row.to_dict()
                    scan_date = str(record.get("date", ""))[:10]
                    if start_date <= scan_date <= end_date:
                        all_scans.append(record)
            except Exception:
                logger.exception("Failed to read Boditrax CSV: %s", csv_file)

        if not all_scans:
            logger.warning("No Boditrax scan data found in %s", raw_dir)
        else:
            logger.info("Boditrax: loaded %d scans", len(all_scans))

        return {"scans": all_scans}

    def _parse_native_export(self, filepath: Path, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Parse a native BoditraxAccount export CSV (long format).

        The file has header sections then rows of: MetricName,Value,CreatedDate
        We pivot these into one dict per scan date.
        """
        rows: list[tuple[str, str, str]] = []
        in_scan_section = False

        with open(filepath, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line == "BodyMetricTypeId,Value,CreatedDate":
                    in_scan_section = True
                    continue
                if not in_scan_section:
                    continue
                if not line or line.startswith("BodyMetricTypeId"):
                    continue
                parts = line.split(",")
                if len(parts) >= 3:
                    metric_id = parts[0]
                    value = parts[1]
                    created_date = ",".join(parts[2:])
                    rows.append((metric_id, value, created_date))

        if not rows:
            return []

        # Build a DataFrame and pivot
        raw_df = pd.DataFrame(rows, columns=["metric", "value", "created_date"])
        raw_df["value"] = pd.to_numeric(raw_df["value"], errors="coerce")
        # Drop rows with non-numeric values (e.g. login details section)
        raw_df = raw_df.dropna(subset=["value"])

        # Map metric names (drops unknown metrics like Username, IpAddress)
        raw_df["metric"] = raw_df["metric"].map(METRIC_MAP)
        raw_df = raw_df.dropna(subset=["metric"])

        raw_df["created_date"] = pd.to_datetime(raw_df["created_date"], format="mixed", dayfirst=False)
        raw_df["date"] = raw_df["created_date"].dt.strftime("%Y-%m-%d")

        # Pivot: one row per scan date, columns = metrics
        pivoted = raw_df.pivot_table(index="date", columns="metric", values="value", aggfunc="first")
        pivoted = pivoted.reset_index()

        # Compute derived columns
        if "bmr_kj" in pivoted.columns:
            pivoted["bmr"] = pivoted["bmr_kj"] / 4.184  # kJ to kcal
        if "weight_kg" in pivoted.columns and "fat_mass_kg" in pivoted.columns:
            pivoted["body_fat_pct"] = (pivoted["fat_mass_kg"] / pivoted["weight_kg"]) * 100

        # Filter to date range
        scans: list[dict[str, Any]] = []
        for _, row in pivoted.iterrows():
            scan_date = str(row["date"])[:10]
            if start_date <= scan_date <= end_date:
                scans.append(row.to_dict())

        logger.info("Parsed %d scans from native export: %s", len(scans), filepath.name)
        return scans

    def _pull_scraper(self, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
        """Attempt to scrape Boditrax data using browser cookies."""
        try:
            import browser_cookie3
            logger.info("Boditrax scraper mode — attempting browser cookie auth")
            logger.warning("Boditrax scraper not fully implemented — falling back to CSV mode")
            return {"scans": []}
        except ImportError:
            logger.error("browser_cookie3 not available. Install it or switch to BODITRAX_MODE=csv")
            return {"scans": []}

    def save_raw(self, data: dict[str, list[dict[str, Any]]], raw_dir: Path,
                 start_date: str, end_date: str) -> dict[str, int]:
        """Save parsed scan data as JSON and return record counts."""
        raw_dir.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {}
        scans = data.get("scans", [])
        if scans:
            filepath = raw_dir / f"scans_{start_date}_{end_date}.json"
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(scans, fh, indent=2, default=str)
            logger.info("Saved %d Boditrax scans to %s", len(scans), filepath.name)
        counts["scans"] = len(scans)

        meta = {
            "source": "boditrax",
            "last_sync": datetime.now().isoformat(),
            "start_date": start_date,
            "end_date": end_date,
            "record_counts": counts,
        }
        with open(raw_dir / "_metadata.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        return counts
