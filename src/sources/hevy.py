"""Hevy API source — workout history, exercises, routines."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hevyapp.com"


class HevySource:
    """Client for the Hevy API (requires Pro subscription)."""

    def __init__(self, api_key: str, max_retries: int = 5) -> None:
        self.session = requests.Session()
        self.session.headers.update({"api-key": api_key})
        self.max_retries = max_retries

    def _get_paginated(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Paginated GET using page/pageSize params."""
        url = f"{BASE_URL}{endpoint}"
        params = dict(params) if params else {}
        params.setdefault("pageSize", 10)  # Hevy API max is 10
        page = 1
        all_data: list[dict[str, Any]] = []

        while True:
            params["page"] = page
            response = self._request_with_retries(url, params)
            body = response.json()

            page_data = body.get("workouts", body.get("exercise_templates", body.get("routines", [])))
            if not page_data:
                break

            all_data.extend(page_data)
            page_count = body.get("page_count", 1)
            if page >= page_count:
                break
            page += 1

        logger.info("Fetched %d records from %s", len(all_data), endpoint)
        return all_data

    def _request_with_retries(self, url: str, params: dict[str, Any]) -> requests.Response:
        """Execute request with exponential backoff on 429."""
        for attempt in range(self.max_retries):
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                return response
            if response.status_code == 429:
                wait_time = 2 ** attempt
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    wait_time = max(wait_time, int(retry_after))
                logger.warning("Rate limited (429). Waiting %ds (attempt %d/%d)",
                               wait_time, attempt + 1, self.max_retries)
                time.sleep(wait_time)
                continue
            response.raise_for_status()

        raise requests.exceptions.HTTPError(f"Max retries ({self.max_retries}) exceeded for {url}")

    def pull(self, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
        """Pull workouts and exercise templates from Hevy."""
        results: dict[str, list[dict[str, Any]]] = {}

        logger.info("Hevy: pulling workouts")
        try:
            workouts = self._get_paginated("/v1/workouts")
            # Filter to date range
            filtered = []
            for workout in workouts:
                workout_date = workout.get("start_time", workout.get("created_at", ""))[:10]
                if start_date <= workout_date <= end_date:
                    filtered.append(workout)
            results["workouts"] = filtered
            logger.info("Hevy: %d workouts in date range", len(filtered))
        except Exception:
            logger.exception("Failed to pull Hevy workouts")
            results["workouts"] = []

        logger.info("Hevy: pulling exercise templates")
        try:
            results["exercise_templates"] = self._get_paginated("/v1/exercise_templates")
        except Exception:
            logger.exception("Failed to pull Hevy exercise templates")
            results["exercise_templates"] = []

        return results

    def save_raw(self, data: dict[str, list[dict[str, Any]]], raw_dir: Path,
                 start_date: str, end_date: str) -> dict[str, int]:
        """Save raw JSON files and return record counts."""
        raw_dir.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {}
        for name, records in data.items():
            if records:
                filepath = raw_dir / f"{name}_{start_date}_{end_date}.json"
                with open(filepath, "w", encoding="utf-8") as fh:
                    json.dump(records, fh, indent=2, default=str)
                logger.info("Saved %d records to %s", len(records), filepath.name)
            counts[name] = len(records)

        meta = {
            "source": "hevy",
            "last_sync": datetime.now().isoformat(),
            "start_date": start_date,
            "end_date": end_date,
            "record_counts": counts,
        }
        with open(raw_dir / "_metadata.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        return counts
