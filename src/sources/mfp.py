"""MyFitnessPal source — nutrition diary and macros via python-myfitnesspal.

Auth: v2.1.2 uses browser cookies via browser_cookie3.
On Windows without admin, we manually extract Chrome/Edge cookies
from the correct path (Network/Cookies) and pass them to the client.
"""

import http.cookiejar
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MFP_DOMAINS = [".myfitnesspal.com", "www.myfitnesspal.com"]


def _load_chrome_cookies_manual() -> http.cookiejar.CookieJar:
    """Manually load cookies from Chrome/Edge cookie database.

    Works without admin by copying the cookie file (browser must be closed
    or file not locked).
    """
    candidates = [
        ("Chrome", Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/Network/Cookies"),
        ("Edge", Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default/Network/Cookies"),
        # Legacy paths
        ("Chrome", Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/Cookies"),
        ("Edge", Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default/Cookies"),
    ]

    for browser_name, cookie_path in candidates:
        if not cookie_path.exists():
            continue

        logger.info("Trying %s cookies at %s", browser_name, cookie_path)
        tmp_path = Path(tempfile.gettempdir()) / f"mfp_{browser_name.lower()}_cookies"
        try:
            shutil.copy2(cookie_path, tmp_path)
            conn = sqlite3.connect(str(tmp_path))
            cursor = conn.execute(
                "SELECT host_key, name, value, path, is_secure, expires_utc "
                "FROM cookies WHERE host_key LIKE '%myfitnesspal%'"
            )
            rows = cursor.fetchall()
            conn.close()
            os.unlink(tmp_path)

            if not rows:
                logger.info("No MFP cookies found in %s", browser_name)
                continue

            cj = http.cookiejar.CookieJar()
            for host_key, name, value, path, is_secure, expires_utc in rows:
                cookie = http.cookiejar.Cookie(
                    version=0, name=name, value=value,
                    port=None, port_specified=False,
                    domain=host_key, domain_specified=True, domain_initial_dot=host_key.startswith("."),
                    path=path or "/", path_specified=bool(path),
                    secure=bool(is_secure),
                    expires=expires_utc if expires_utc else None,
                    discard=not bool(expires_utc),
                    comment=None, comment_url=None,
                    rest={}, rfc2109=False,
                )
                cj.set_cookie(cookie)

            logger.info("Loaded %d MFP cookies from %s", len(rows), browser_name)
            return cj

        except Exception:
            logger.warning("Failed to read %s cookies, trying next browser", browser_name, exc_info=True)
            if tmp_path.exists():
                os.unlink(tmp_path)
            continue

    raise RuntimeError(
        "Could not load MFP cookies from any browser. "
        "Ensure you are logged into MyFitnessPal in Chrome or Edge."
    )


class MfpSource:
    """Client for MyFitnessPal via python-myfitnesspal library."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self) -> Any:
        """Lazy-init the MFP client."""
        if self._client is None:
            import myfitnesspal

            # Try standard browser_cookie3 first, fall back to manual extraction
            try:
                self._client = myfitnesspal.Client()
                logger.info("MFP client authenticated via browser_cookie3")
            except Exception:
                logger.info("browser_cookie3 failed, trying manual cookie extraction")
                cookiejar = _load_chrome_cookies_manual()
                self._client = myfitnesspal.Client(cookiejar=cookiejar)
                logger.info("MFP client authenticated via manual cookie extraction")
        return self._client

    def pull(self, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
        """Pull daily nutrition data from MFP day by day.

        Adds 0.5s delay between requests to avoid rate limiting.
        """
        client = self._get_client()
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        diary_entries: list[dict[str, Any]] = []
        current = start

        while current <= end:
            try:
                day_data = client.get_date(current.year, current.month, current.day)
                entry = self._serialize_day(current, day_data)
                diary_entries.append(entry)
            except Exception:
                logger.warning("MFP: failed to fetch data for %s, recording as empty day", current)
                diary_entries.append(self._empty_day(current))

            current += timedelta(days=1)
            time.sleep(0.5)

            if len(diary_entries) % 30 == 0:
                logger.info("MFP: pulled %d days so far...", len(diary_entries))

        logger.info("MFP: pulled %d diary days total", len(diary_entries))
        return {"diary": diary_entries}

    def _serialize_day(self, date: Any, day_data: Any) -> dict[str, Any]:
        """Convert a MFP day object to a serialisable dict."""
        totals = day_data.totals if hasattr(day_data, "totals") else {}
        meals_data = []
        if hasattr(day_data, "meals"):
            for meal in day_data.meals:
                meal_items = []
                if hasattr(meal, "entries"):
                    for item in meal.entries:
                        meal_items.append({
                            "name": str(item.name) if hasattr(item, "name") else str(item),
                            "nutrition": dict(item.nutrition_information) if hasattr(item, "nutrition_information") else {},
                        })
                meals_data.append({
                    "name": str(meal.name) if hasattr(meal, "name") else "Unknown",
                    "items": meal_items,
                })

        return {
            "date": str(date),
            "totals": dict(totals) if totals else {},
            "meals": meals_data,
            "calories": totals.get("calories", 0) if totals else 0,
            "protein": totals.get("protein", 0) if totals else 0,
            "carbohydrates": totals.get("carbohydrates", 0) if totals else 0,
            "fat": totals.get("fat", 0) if totals else 0,
            "sodium": totals.get("sodium", 0) if totals else 0,
            "sugar": totals.get("sugar", 0) if totals else 0,
        }

    def _empty_day(self, date: Any) -> dict[str, Any]:
        """Return a zero-calorie day record (gaps are analytically meaningful)."""
        return {
            "date": str(date),
            "totals": {},
            "meals": [],
            "calories": 0,
            "protein": 0,
            "carbohydrates": 0,
            "fat": 0,
            "sodium": 0,
            "sugar": 0,
        }

    def save_raw(self, data: dict[str, list[dict[str, Any]]], raw_dir: Path,
                 start_date: str, end_date: str) -> dict[str, int]:
        """Save raw diary data as monthly JSON batches and return record counts."""
        raw_dir.mkdir(parents=True, exist_ok=True)
        diary = data.get("diary", [])

        monthly: dict[str, list[dict[str, Any]]] = {}
        for entry in diary:
            month_key = entry["date"][:7]
            monthly.setdefault(month_key, []).append(entry)

        for month_key, entries in monthly.items():
            filepath = raw_dir / f"mfp_diary_{month_key}.json"
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(entries, fh, indent=2, default=str)
            logger.info("Saved %d MFP diary entries to %s", len(entries), filepath.name)

        counts = {"diary": len(diary)}
        meta = {
            "source": "mfp",
            "last_sync": datetime.now().isoformat(),
            "start_date": start_date,
            "end_date": end_date,
            "record_counts": counts,
        }
        with open(raw_dir / "_metadata.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        return counts
