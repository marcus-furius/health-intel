"""MyFitnessPal source — nutrition, measurements, and exercise from CSV export.

MFP Premium allows exporting data as CSV files from the website.
The export contains three files:
  - Nutrition-Summary (meal-level macros/micros)
  - Measurement-Summary (weight entries)
  - Exercise-Summary (cardio, steps)

This client reads the export directory, aggregates meal-level nutrition
to daily totals, and produces the standard pipeline format.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Column mapping from MFP export headers to pipeline names
NUTRITION_COL_MAP = {
    "Date": "date",
    "Meal": "meal",
    "Calories": "calories",
    "Fat (g)": "fat",
    "Saturated Fat": "saturated_fat",
    "Polyunsaturated Fat": "polyunsaturated_fat",
    "Monounsaturated Fat": "monounsaturated_fat",
    "Trans Fat": "trans_fat",
    "Cholesterol": "cholesterol",
    "Sodium (mg)": "sodium",
    "Potassium": "potassium",
    "Carbohydrates (g)": "carbohydrates",
    "Fiber": "fiber",
    "Sugar": "sugar",
    "Protein (g)": "protein",
    "Vitamin A": "vitamin_a",
    "Vitamin C": "vitamin_c",
    "Calcium": "calcium",
    "Iron": "iron",
    "Note": "note",
}

# Numeric columns to aggregate per day
NUMERIC_COLS = [
    "calories", "fat", "saturated_fat", "polyunsaturated_fat",
    "monounsaturated_fat", "trans_fat", "cholesterol", "sodium",
    "potassium", "carbohydrates", "fiber", "sugar", "protein",
    "vitamin_a", "vitamin_c", "calcium", "iron",
]


class MfpSource:
    """Client for MyFitnessPal via Premium CSV export."""

    def __init__(self) -> None:
        pass

    def _find_export_dir(self, raw_dir: Path) -> Path | None:
        """Find the most recent MFP export directory."""
        export_dirs = sorted(
            [d for d in raw_dir.iterdir() if d.is_dir() and d.name.startswith("File-Export-")],
            reverse=True,
        )
        if export_dirs:
            return export_dirs[0]
        return None

    def _find_csv(self, export_dir: Path, prefix: str) -> Path | None:
        """Find a CSV file by prefix within the export directory."""
        matches = list(export_dir.glob(f"{prefix}*.csv"))
        return matches[0] if matches else None

    def _parse_nutrition(self, csv_path: Path, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Parse Nutrition-Summary CSV and aggregate meals to daily totals."""
        df = pd.read_csv(csv_path)
        df = df.rename(columns=NUTRITION_COL_MAP)

        # Ensure date column and filter to range
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

        if df.empty:
            return []

        # Coerce numeric columns
        for col in NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Build per-meal breakdown before aggregating
        meal_details: dict[str, list[dict[str, Any]]] = {}
        for _, row in df.iterrows():
            date = row["date"]
            meal_details.setdefault(date, [])
            meal_entry = {"name": row.get("meal", "Unknown")}
            for col in NUMERIC_COLS:
                if col in row:
                    meal_entry[col] = float(row[col])
            meal_details[date].append(meal_entry)

        # Aggregate to daily totals
        agg_cols = [col for col in NUMERIC_COLS if col in df.columns]
        daily = df.groupby("date")[agg_cols].sum().reset_index()

        entries: list[dict[str, Any]] = []
        for _, row in daily.iterrows():
            date = row["date"]
            totals = {col: float(row[col]) for col in agg_cols}
            entries.append({
                "date": date,
                **totals,
                "totals": totals,
                "meals": meal_details.get(date, []),
            })

        return entries

    def _parse_measurements(self, csv_path: Path, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Parse Measurement-Summary CSV (weight entries)."""
        df = pd.read_csv(csv_path)
        df.columns = [c.strip().lower() for c in df.columns]

        if "date" not in df.columns:
            return []

        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

        entries: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            entry = {"date": row["date"]}
            if "weight" in row:
                entry["weight_kg"] = float(row["weight"])
            entries.append(entry)

        return entries

    def _parse_exercise(self, csv_path: Path, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Parse Exercise-Summary CSV."""
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]

        col_map = {
            "Date": "date",
            "Exercise": "exercise",
            "Type": "type",
            "Exercise Calories": "exercise_calories",
            "Exercise Minutes": "exercise_minutes",
            "Sets": "sets",
            "Reps Per Set": "reps_per_set",
            "Kilograms": "kilograms",
            "Steps": "steps",
            "Note": "note",
        }
        df = df.rename(columns=col_map)

        if "date" not in df.columns:
            return []

        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

        entries: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            entry = {}
            for col in ["date", "exercise", "type", "exercise_calories",
                        "exercise_minutes", "sets", "reps_per_set", "kilograms",
                        "steps", "note"]:
                if col in row and pd.notna(row[col]):
                    entry[col] = row[col]
                    if isinstance(entry[col], float) and entry[col] == int(entry[col]):
                        entry[col] = int(entry[col])
            entries.append(entry)

        return entries

    def pull(self, start_date: str, end_date: str, raw_dir: Path | None = None) -> dict[str, list[dict[str, Any]]]:
        """Read MFP CSV export and return structured data.

        Looks for a File-Export-* directory inside raw_dir containing
        Nutrition-Summary, Measurement-Summary, and Exercise-Summary CSVs.
        """
        if raw_dir is None:
            logger.warning("No raw directory provided for MFP CSV import")
            return {"diary": [], "measurements": [], "exercise": []}

        export_dir = self._find_export_dir(raw_dir)
        if export_dir is None:
            logger.warning("No MFP export directory found in %s", raw_dir)
            return {"diary": [], "measurements": [], "exercise": []}

        logger.info("Using MFP export: %s", export_dir.name)
        result: dict[str, list[dict[str, Any]]] = {
            "diary": [],
            "measurements": [],
            "exercise": [],
        }

        # Nutrition
        nutrition_csv = self._find_csv(export_dir, "Nutrition-Summary")
        if nutrition_csv:
            result["diary"] = self._parse_nutrition(nutrition_csv, start_date, end_date)
            logger.info("MFP nutrition: %d daily entries from %s", len(result["diary"]), nutrition_csv.name)
        else:
            logger.warning("No Nutrition-Summary CSV found in %s", export_dir)

        # Measurements
        measurement_csv = self._find_csv(export_dir, "Measurement-Summary")
        if measurement_csv:
            result["measurements"] = self._parse_measurements(measurement_csv, start_date, end_date)
            logger.info("MFP measurements: %d entries from %s", len(result["measurements"]), measurement_csv.name)
        else:
            logger.info("No Measurement-Summary CSV found in %s", export_dir)

        # Exercise
        exercise_csv = self._find_csv(export_dir, "Exercise-Summary")
        if exercise_csv:
            result["exercise"] = self._parse_exercise(exercise_csv, start_date, end_date)
            logger.info("MFP exercise: %d entries from %s", len(result["exercise"]), exercise_csv.name)
        else:
            logger.info("No Exercise-Summary CSV found in %s", export_dir)

        return result

    def save_raw(self, data: dict[str, list[dict[str, Any]]], raw_dir: Path,
                 start_date: str, end_date: str) -> dict[str, int]:
        """Save parsed data as JSON and return record counts."""
        raw_dir.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {}

        # Save diary as monthly JSON batches (compatible with transform layer)
        diary = data.get("diary", [])
        if diary:
            monthly: dict[str, list[dict[str, Any]]] = {}
            for entry in diary:
                month_key = entry["date"][:7]
                monthly.setdefault(month_key, []).append(entry)

            for month_key, entries in monthly.items():
                filepath = raw_dir / f"mfp_diary_{month_key}.json"
                with open(filepath, "w", encoding="utf-8") as fh:
                    json.dump(entries, fh, indent=2, default=str)
                logger.info("Saved %d MFP diary entries to %s", len(entries), filepath.name)
        counts["diary"] = len(diary)

        # Save measurements
        measurements = data.get("measurements", [])
        if measurements:
            filepath = raw_dir / f"mfp_measurements_{start_date}_{end_date}.json"
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(measurements, fh, indent=2, default=str)
        counts["measurements"] = len(measurements)

        # Save exercise
        exercise = data.get("exercise", [])
        if exercise:
            filepath = raw_dir / f"mfp_exercise_{start_date}_{end_date}.json"
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(exercise, fh, indent=2, default=str)
        counts["exercise"] = len(exercise)

        # Metadata
        meta = {
            "source": "mfp",
            "mode": "csv",
            "last_sync": datetime.now().isoformat(),
            "start_date": start_date,
            "end_date": end_date,
            "record_counts": counts,
        }
        with open(raw_dir / "_metadata.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        return counts
