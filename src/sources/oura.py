"""Oura Ring API v2 source — sleep, readiness, activity, HR, SpO2."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ouraring.com"

ENDPOINTS = {
    "daily_sleep": "/v2/usercollection/daily_sleep",
    "sleep": "/v2/usercollection/sleep",
    "daily_readiness": "/v2/usercollection/daily_readiness",
    "daily_activity": "/v2/usercollection/daily_activity",
    "heartrate": "/v2/usercollection/heartrate",
    "daily_spo2": "/v2/usercollection/daily_spo2",
}


class OuraSource:
    """Client for the Oura Ring API v2."""

    def __init__(self, token: str, max_retries: int = 5) -> None:
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.max_retries = max_retries

    def _get(self, endpoint: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """Paginated GET with rate limit handling."""
        url = f"{BASE_URL}{endpoint}"
        params = dict(params) if params else {}
        all_data: list[dict[str, Any]] = []

        while True:
            response = self._request_with_retries(url, params)
            body = response.json()

            if "data" not in body:
                logger.warning("No 'data' key in response from %s", endpoint)
                break

            all_data.extend(body["data"])
            next_token = body.get("next_token")
            if not next_token:
                break
            params["next_token"] = next_token

        logger.info("Fetched %d records from %s", len(all_data), endpoint)
        return all_data

    def _request_with_retries(self, url: str, params: dict[str, str]) -> requests.Response:
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
        """Pull all Oura endpoints. Returns dict of endpoint_name -> records."""
        results: dict[str, list[dict[str, Any]]] = {}
        for name, path in ENDPOINTS.items():
            logger.info("Oura: pulling %s (%s to %s)", name, start_date, end_date)
            try:
                data = self._get(path, {"start_date": start_date, "end_date": end_date})
                results[name] = data
            except Exception:
                logger.exception("Failed to pull Oura endpoint: %s", name)
                results[name] = []
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

        # Write metadata
        meta = {
            "source": "oura",
            "last_sync": datetime.now().isoformat(),
            "start_date": start_date,
            "end_date": end_date,
            "record_counts": counts,
        }
        with open(raw_dir / "_metadata.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        return counts
