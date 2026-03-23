"""Create the 4-day recomposition workout split as routines in Hevy.

Usage:
    python -m src.create_routines [--dry-run]

Requires HEVY_API_KEY in .env file.
"""

import json
import logging
import sys
import time
from typing import Any

import requests
from dotenv import dotenv_values

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://api.hevyapp.com"
MAX_RETRIES = 5

# ---------------------------------------------------------------------------
# Exercise template IDs (from data/raw/hevy/exercise_templates)
# ---------------------------------------------------------------------------
EX = {
    "incline_bench_press_db": "07B38369",
    "iso_lateral_row": "AA1EB7D8",
    "butterfly_pec_deck": "9DCE2D64",
    "reverse_fly_cable": "9264ADA1",
    "triceps_extension_machine": "3092FADD",
    "ez_bar_curl": "01A35BF9",
    "hanging_leg_raise": "F8356514",
    "hack_squat_machine": "1E42FD5F",
    "romanian_deadlift_bb": "2B4B7310",
    "leg_press_machine": "C7973E0E",
    "hip_thrust_bb": "D57C2EC7",
    "leg_extension_machine": "75A4F6C4",
    "hip_adduction_machine": "8BEBFED6",
    "standing_calf_raise_smith": "AA52E8D2",
    "pull_up": "1B2B1E7C",
    "pull_up_assisted": "2C37EC5E",
    "shoulder_press_machine": "059E835D",
    "lat_pulldown_cable": "6A6C31A5",
    "lateral_raise_cable": "DE68C825",
    "triceps_dip_weighted": "10347BAC",
    "incline_chest_fly_db": "D3E2AB55",
    "crunch_machine": "EB43ADD4",
    "deadlift_bb": "C6272009",
    "rear_kick_machine": "1ADF8723",
    "lying_leg_curl": "B8127AD1",
    "back_extension_weighted": "091737FA",
    "hip_abduction_machine": "F4B4C6EE",
    "calf_extension_machine": "47B9DF13",
}


def _make_sets(set_type: str, weight_kg: float | None, reps: int, count: int) -> list[dict[str, Any]]:
    """Build a list of identical sets."""
    s: dict[str, Any] = {
        "type": set_type,
        "weight_kg": weight_kg,
        "reps": reps,
        "distance_meters": None,
        "duration_seconds": None,
        "custom_metric": None,
    }
    return [dict(s) for _ in range(count)]


def _exercise(template_id: str, rest_seconds: int, notes: str,
              sets: list[dict[str, Any]]) -> dict[str, Any]:
    """Build an exercise entry for the routine payload."""
    return {
        "exercise_template_id": template_id,
        "superset_id": None,
        "rest_seconds": rest_seconds,
        "notes": notes,
        "sets": sets,
    }


# ---------------------------------------------------------------------------
# Routine definitions
# ---------------------------------------------------------------------------

def build_upper_a() -> dict[str, Any]:
    """Day 1 — Upper A (Horizontal Push/Pull)."""
    return {
        "title": "Recomp Upper A",
        "folder_id": None,
        "notes": "Horizontal push/pull focus. Chest + upper back priority.",
        "exercises": [
            _exercise(EX["incline_bench_press_db"], 120,
                      "Warm-up then 3 working sets. Progress via double progression.",
                      _make_sets("warmup", 24, 12, 1) + _make_sets("normal", 52, 8, 3)),
            _exercise(EX["iso_lateral_row"], 120,
                      "Upper back priority. Control the eccentric.",
                      _make_sets("warmup", 40, 12, 1) + _make_sets("normal", 85, 10, 3)),
            _exercise(EX["butterfly_pec_deck"], 90,
                      "Slow eccentric, squeeze at peak contraction.",
                      _make_sets("normal", 62.5, 10, 3)),
            _exercise(EX["reverse_fly_cable"], 60,
                      "Rear delt + upper back support.",
                      _make_sets("normal", None, 12, 3)),
            _exercise(EX["triceps_extension_machine"], 60, "",
                      _make_sets("normal", 60, 12, 3)),
            _exercise(EX["ez_bar_curl"], 60, "",
                      _make_sets("normal", 25, 10, 3)),
            _exercise(EX["hanging_leg_raise"], 60,
                      "Controlled reps, no swinging.",
                      _make_sets("normal", None, 12, 3)),
        ],
    }


def build_lower_a() -> dict[str, Any]:
    """Day 2 — Lower A (Quad + Glute)."""
    return {
        "title": "Recomp Lower A",
        "folder_id": None,
        "notes": "Quad + glute focus. High foot placement on leg press for glute bias.",
        "exercises": [
            _exercise(EX["hack_squat_machine"], 120,
                      "Primary quad compound.",
                      _make_sets("warmup", 50, 12, 1) + _make_sets("normal", 70, 8, 3)),
            _exercise(EX["romanian_deadlift_bb"], 120,
                      "Glute/ham emphasis. Slow eccentric, hinge at hips.",
                      _make_sets("warmup", 20, 12, 1) + _make_sets("normal", 70, 10, 3)),
            _exercise(EX["leg_press_machine"], 90,
                      "High foot placement for glute bias.",
                      _make_sets("normal", 180, 10, 3)),
            _exercise(EX["hip_thrust_bb"], 90,
                      "New addition - addresses glute deficit. Start moderate, build up.",
                      _make_sets("normal", 60, 10, 3)),
            _exercise(EX["leg_extension_machine"], 60,
                      "Reduced volume vs previous split.",
                      _make_sets("normal", 67.5, 12, 2)),
            _exercise(EX["hip_adduction_machine"], 60, "",
                      _make_sets("normal", 60, 12, 3)),
            _exercise(EX["standing_calf_raise_smith"], 60,
                      "Full ROM, pause at bottom stretch.",
                      _make_sets("normal", 80, 15, 4)),
        ],
    }


def build_upper_b() -> dict[str, Any]:
    """Day 3 — Upper B (Vertical Push/Pull)."""
    return {
        "title": "Recomp Upper B",
        "folder_id": None,
        "notes": "Vertical push/pull focus. Pull-up progression + shoulder press.",
        "exercises": [
            _exercise(EX["pull_up"], 120,
                      "Goal: progress to full unassisted sets. Use assisted variant if needed.",
                      _make_sets("normal", None, 6, 4)),
            _exercise(EX["shoulder_press_machine"], 120,
                      "Primary pressing compound.",
                      _make_sets("warmup", 40, 8, 1) + _make_sets("normal", 70, 8, 3)),
            _exercise(EX["lat_pulldown_cable"], 90,
                      "Back width. Complements pull-ups.",
                      _make_sets("normal", 70, 8, 3)),
            _exercise(EX["lateral_raise_cable"], 60,
                      "Medial delt isolation.",
                      _make_sets("normal", None, 12, 3)),
            _exercise(EX["triceps_dip_weighted"], 90,
                      "Compound tricep/chest movement.",
                      _make_sets("normal", None, 6, 3)),
            _exercise(EX["incline_chest_fly_db"], 60,
                      "Upper chest stretch focus.",
                      _make_sets("normal", 36, 10, 3)),
            _exercise(EX["crunch_machine"], 60, "",
                      _make_sets("normal", 50, 15, 3)),
        ],
    }


def build_lower_b() -> dict[str, Any]:
    """Day 4 — Lower B (Posterior Chain + Glute)."""
    return {
        "title": "Recomp Lower B",
        "folder_id": None,
        "notes": "Posterior chain + glute focus. Deadlift day.",
        "exercises": [
            _exercise(EX["deadlift_bb"], 150,
                      "Primary posterior chain compound. Brace hard.",
                      _make_sets("warmup", 20, 12, 1) + _make_sets("normal", 90, 6, 3)),
            _exercise(EX["rear_kick_machine"], 60,
                      "Glute isolation. Addresses glute deficit.",
                      _make_sets("normal", 80, 10, 4)),
            _exercise(EX["lying_leg_curl"], 60,
                      "Hamstring isolation.",
                      _make_sets("normal", 32.5, 10, 3)),
            _exercise(EX["leg_press_machine"], 90,
                      "Moderate weight, full depth.",
                      _make_sets("normal", 140, 10, 3)),
            _exercise(EX["back_extension_weighted"], 60,
                      "Lower back is severely under-trained. Build up gradually.",
                      _make_sets("normal", None, 12, 3)),
            _exercise(EX["hip_abduction_machine"], 60, "",
                      _make_sets("normal", 65, 12, 3)),
            _exercise(EX["calf_extension_machine"], 60,
                      "Full ROM.",
                      _make_sets("normal", 100, 15, 4)),
        ],
    }


# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------

def create_routine(session: requests.Session, routine: dict[str, Any]) -> dict[str, Any]:
    """POST a routine to Hevy API with retry logic."""
    url = f"{BASE_URL}/v1/routines"
    payload = {"routine": routine}

    for attempt in range(MAX_RETRIES):
        response = session.post(url, json=payload)

        if response.status_code in (200, 201):
            result = response.json()
            logger.info("Created routine: %s", routine["title"])
            return result

        if response.status_code == 429:
            wait_time = 2 ** attempt
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                wait_time = max(wait_time, int(retry_after))
            logger.warning("Rate limited (429). Waiting %ds (attempt %d/%d)",
                           wait_time, attempt + 1, MAX_RETRIES)
            time.sleep(wait_time)
            continue

        logger.error("Failed to create routine '%s': %d %s",
                     routine["title"], response.status_code, response.text[:500])
        response.raise_for_status()

    raise requests.exceptions.HTTPError(
        f"Max retries ({MAX_RETRIES}) exceeded creating routine '{routine['title']}'")


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    config = dotenv_values(".env")
    api_key = config.get("HEVY_API_KEY", "")
    if not api_key:
        logger.error("HEVY_API_KEY not found in .env")
        sys.exit(1)

    routines = [
        build_upper_a(),
        build_lower_a(),
        build_upper_b(),
        build_lower_b(),
    ]

    if dry_run:
        logger.info("DRY RUN — printing payloads without sending to API")
        for routine in routines:
            print(json.dumps({"routine": routine}, indent=2, default=str))
            print()
        return

    session = requests.Session()
    session.headers.update({"api-key": api_key})

    created = []
    for routine in routines:
        result = create_routine(session, routine)
        created.append(result)
        # Small delay between creations to be respectful of rate limits
        time.sleep(1)

    logger.info("Successfully created %d routines in Hevy", len(created))
    for r in created:
        routine_data = r.get("routine", r)
        if isinstance(routine_data, list):
            routine_data = routine_data[0] if routine_data else {}
        logger.info("  - %s (id: %s)", routine_data.get("title"), routine_data.get("id"))


if __name__ == "__main__":
    main()
