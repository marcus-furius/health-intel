"""Bloodwork source — manual blood work data from JSON."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

class BloodworkSource:
    """Reads pre-extracted blood work data from data/raw/manual/bloodwork.json."""
    
    def __init__(self, raw_dir: str = "data/raw/manual"):
        self.raw_dir = Path(raw_dir)
        self.source_file = self.raw_dir / "bloodwork.json"

    def pull(self) -> dict[str, Any]:
        """Read blood work data from the JSON file."""
        if not self.source_file.exists():
            logger.warning("Bloodwork file not found at %s", self.source_file)
            return {"results": []}

        try:
            with open(self.source_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return {"results": data}
        except Exception as e:
            logger.error("Error reading bloodwork data: %s", e)
            return {"results": []}

    def save_raw(self, data: dict[str, Any], output_dir: str = "data/raw/bloodwork") -> int:
        """Save raw bloodwork data to the versioned raw directory."""
        if not data["results"]:
            return 0

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # Sort results by date to find range
        results = sorted(data["results"], key=lambda x: x["date"])
        start_date = results[0]["date"]
        end_date = results[-1]["date"]

        filename = f"results_{start_date}_{end_date}.json"
        with open(out_path / filename, "w", encoding="utf-8") as fh:
            json.dump(data["results"], fh, indent=2)

        # Update metadata
        meta = {
            "last_pulled": datetime.now().isoformat(),
            "start_date": start_date,
            "end_date": end_date,
            "record_count": len(results),
        }
        with open(out_path / "_metadata.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        return len(results)
