"""Health screening engine — composite health scoring across all data sources."""

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.report import _recent_trend, compute_alerts

logger = logging.getLogger(__name__)

VO2MAX_PATH = Path("data/processed/vo2max.json")

# ── Domain weights for overall score ──

DOMAIN_WEIGHTS: dict[str, float] = {
    "cardiovascular": 0.20,
    "body_composition": 0.15,
    "sleep_recovery": 0.18,
    "training": 0.12,
    "nutrition": 0.12,
    "metabolic": 0.13,
    "hormonal": 0.10,
}

DOMAIN_LABELS: dict[str, str] = {
    "cardiovascular": "Cardiovascular Fitness",
    "body_composition": "Body Composition",
    "sleep_recovery": "Sleep & Recovery",
    "training": "Training & Fitness",
    "nutrition": "Nutrition",
    "metabolic": "Metabolic Health",
    "hormonal": "Hormonal Health",
}

# ── VO2 Max thresholds (male, age 50-59) ──

VO2MAX_THRESHOLDS = {
    "male_50_59": (31.0, 35.1, 39.1, 43.3),  # poor, fair, good, excellent boundaries
}


# ── VO2 Max persistence ──


def load_vo2max() -> list[dict[str, Any]]:
    """Load VO2 Max entries from JSON file, seeding if absent."""
    if not VO2MAX_PATH.exists():
        seed = [{"date": "2026-01-06", "value": 46, "method": "manual"}]
        save_vo2max(seed)
        return seed
    data = json.loads(VO2MAX_PATH.read_text())
    return data if isinstance(data, list) else []


def save_vo2max(entries: list[dict[str, Any]]) -> None:
    """Persist VO2 Max entries to JSON file."""
    VO2MAX_PATH.parent.mkdir(parents=True, exist_ok=True)
    VO2MAX_PATH.write_text(json.dumps(entries, indent=2))


def add_vo2max_entry(
    date: str, value: float, method: str = "manual"
) -> list[dict[str, Any]]:
    """Add a new VO2 Max entry, sort by date, persist, and return all entries."""
    entries = load_vo2max()
    entries.append({"date": date, "value": value, "method": method})
    entries.sort(key=lambda e: e["date"])
    save_vo2max(entries)
    return entries


# ── VO2 Max classification ──


def classify_vo2max(value: float) -> dict[str, Any]:
    """Classify VO2 Max into fitness category for male aged 50-59.

    Returns dict with category, score (0-100), and value.
    """
    poor_max, fair_max, good_max, excellent_max = VO2MAX_THRESHOLDS["male_50_59"]

    if value <= poor_max:
        category = "Poor"
        score = max(5.0, (value / poor_max) * 30)
    elif value <= fair_max:
        category = "Fair"
        score = 30 + (value - poor_max) / (fair_max - poor_max) * 20
    elif value <= good_max:
        category = "Good"
        score = 50 + (value - fair_max) / (good_max - fair_max) * 20
    elif value <= excellent_max:
        category = "Excellent"
        score = 70 + (value - good_max) / (excellent_max - good_max) * 20
    else:
        category = "Superior"
        score = 90 + min(10.0, (value - excellent_max) / 5 * 10)

    return {"category": category, "score": round(min(score, 100), 1), "value": value}


# ── Trend direction helper ──


def _trend_direction(slope: float | None, threshold: float = 0.01) -> str:
    """Convert a numeric slope to a direction label."""
    if slope is None:
        return "stable"
    if slope > threshold:
        return "improving"
    if slope < -threshold:
        return "declining"
    return "stable"


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return round(max(lo, min(hi, value)), 1)


# ── Domain scorers ──


def _score_cardiovascular(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Cardiovascular fitness: VO2 Max, RHR, HRV balance, SpO2."""
    components: list[dict[str, Any]] = []
    weights: dict[str, float] = {}

    # VO2 Max
    vo2max_entries = load_vo2max()
    if vo2max_entries:
        latest_vo2 = vo2max_entries[-1]
        classification = classify_vo2max(latest_vo2["value"])
        components.append({
            "name": "VO2 Max",
            "score": classification["score"],
            "weight": 0.40,
            "detail": f'{latest_vo2["value"]} ml/kg/min ({classification["category"]})',
        })
        weights["vo2max"] = 0.40
    else:
        classification = None

    # RHR (lower is better) — from readiness contributors.resting_heart_rate
    readiness_df = datasets.get("readiness", pd.DataFrame())
    if not readiness_df.empty and "contributors.resting_heart_rate" in readiness_df.columns:
        rhr_series = readiness_df.sort_values("day")["contributors.resting_heart_rate"].dropna()
        if len(rhr_series) >= 7:
            avg_rhr_score = rhr_series.tail(14).mean()
            # Oura RHR contributor is already 0-100 (higher = better RHR)
            rhr_score = _clamp(avg_rhr_score)
            rhr_trend = _recent_trend(rhr_series)
            components.append({
                "name": "Resting Heart Rate",
                "score": rhr_score,
                "weight": 0.20,
                "detail": f"RHR contributor score {rhr_score:.0f}/100",
            })
            weights["rhr"] = 0.20

    # HRV Balance — from readiness contributors.hrv_balance
    if not readiness_df.empty and "contributors.hrv_balance" in readiness_df.columns:
        hrv_series = readiness_df.sort_values("day")["contributors.hrv_balance"].dropna()
        if len(hrv_series) >= 7:
            avg_hrv = hrv_series.tail(14).mean()
            hrv_score = _clamp(avg_hrv)
            components.append({
                "name": "HRV Balance",
                "score": hrv_score,
                "weight": 0.25,
                "detail": f"HRV balance score {hrv_score:.0f}/100",
            })
            weights["hrv"] = 0.25

    # SpO2
    spo2_df = datasets.get("spo2", pd.DataFrame())
    if not spo2_df.empty and "spo2_percentage.average" in spo2_df.columns:
        spo2_series = spo2_df.sort_values("day")["spo2_percentage.average"].dropna()
        if len(spo2_series) >= 7:
            avg_spo2 = spo2_series.tail(14).mean()
            if avg_spo2 >= 97:
                spo2_score = 100.0
            elif avg_spo2 >= 95:
                spo2_score = 60 + (avg_spo2 - 95) / 2 * 40
            else:
                spo2_score = max(10.0, avg_spo2 - 85) * 6
            components.append({
                "name": "Blood Oxygen (SpO2)",
                "score": _clamp(spo2_score),
                "weight": 0.15,
                "detail": f"{avg_spo2:.1f}% average",
            })
            weights["spo2"] = 0.15

    if not weights:
        return {
            "name": "cardiovascular", "label": DOMAIN_LABELS["cardiovascular"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    # Normalise weights and compute weighted score
    total_w = sum(weights.values())
    score = sum(c["score"] * c["weight"] / total_w for c in components)
    for comp in components:
        comp["weight"] = round(comp["weight"] / total_w, 3)

    # Trend from HRV
    hrv_trend = None
    if not readiness_df.empty and "contributors.hrv_balance" in readiness_df.columns:
        hrv_trend = _recent_trend(
            readiness_df.sort_values("day")["contributors.hrv_balance"].dropna()
        )

    key_metric = None
    if classification:
        key_metric = f'VO2 Max: {classification["value"]} ({classification["category"]})'

    return {
        "name": "cardiovascular", "label": DOMAIN_LABELS["cardiovascular"],
        "score": _clamp(score), "trend": _trend_direction(hrv_trend),
        "available": True, "components": components, "key_metric": key_metric,
    }


def _score_body_composition(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Body composition: fat %, muscle trend, visceral fat, BMI, metabolic age."""
    body_df = datasets.get("body_composition", pd.DataFrame())
    if body_df.empty:
        return {
            "name": "body_composition", "label": DOMAIN_LABELS["body_composition"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    latest = body_df.sort_values("day").iloc[-1]
    components: list[dict[str, Any]] = []
    weights: dict[str, float] = {}

    # Body fat %
    if "body_fat_pct" in latest and pd.notna(latest["body_fat_pct"]):
        bf = latest["body_fat_pct"]
        if 12 <= bf <= 18:
            bf_score = 100 - abs(bf - 15) * 5  # peak at 15%
        elif bf < 12:
            bf_score = max(40.0, 70 - (12 - bf) * 10)
        elif bf <= 22:
            bf_score = max(40.0, 80 - (bf - 18) * 10)
        elif bf <= 25:
            bf_score = max(20.0, 40 - (bf - 22) * 7)
        else:
            bf_score = max(10.0, 20 - (bf - 25) * 2)
        components.append({
            "name": "Body Fat %",
            "score": _clamp(bf_score),
            "weight": 0.30,
            "detail": f"{bf:.1f}%",
        })
        weights["bf"] = 0.30

    # Muscle mass trend
    if "muscle_mass_kg" in body_df.columns:
        muscle_series = body_df.sort_values("day")["muscle_mass_kg"].dropna()
        if len(muscle_series) >= 3:
            muscle_trend = _recent_trend(muscle_series, window=10)
            if muscle_trend is not None:
                monthly_rate = muscle_trend * 30
                if monthly_rate >= 0.3:
                    muscle_score = 95.0
                elif monthly_rate >= 0.1:
                    muscle_score = 75.0
                elif monthly_rate >= -0.1:
                    muscle_score = 60.0
                elif monthly_rate >= -0.3:
                    muscle_score = 35.0
                else:
                    muscle_score = 15.0
                components.append({
                    "name": "Muscle Mass Trend",
                    "score": _clamp(muscle_score),
                    "weight": 0.25,
                    "detail": f"{monthly_rate:+.2f} kg/month",
                })
                weights["muscle"] = 0.25

    # Visceral fat
    if "visceral_fat" in latest and pd.notna(latest["visceral_fat"]):
        vf = latest["visceral_fat"]
        if vf <= 7:
            vf_score = 100.0
        elif vf <= 9:
            vf_score = 70.0
        elif vf <= 12:
            vf_score = 40.0
        else:
            vf_score = max(10.0, 20 - (vf - 13) * 5)
        components.append({
            "name": "Visceral Fat",
            "score": _clamp(vf_score),
            "weight": 0.20,
            "detail": f"Rating {vf:.0f}",
        })
        weights["vf"] = 0.20

    # BMI (adjusted for muscular build)
    if "bmi" in latest and pd.notna(latest["bmi"]):
        bmi = latest["bmi"]
        high_muscle = (
            "muscle_mass_kg" in latest
            and pd.notna(latest.get("muscle_mass_kg"))
            and latest["muscle_mass_kg"] > 35
        )
        if 18.5 <= bmi <= 24.9:
            bmi_score = 90.0
        elif 25 <= bmi <= 27 and high_muscle:
            bmi_score = 75.0  # muscular build adjustment
        elif 25 <= bmi <= 27:
            bmi_score = 60.0
        elif 27 < bmi <= 30:
            bmi_score = 40.0
        else:
            bmi_score = 20.0
        components.append({
            "name": "BMI",
            "score": _clamp(bmi_score),
            "weight": 0.10,
            "detail": f"{bmi:.1f} kg/m²",
        })
        weights["bmi"] = 0.10

    # Metabolic age gap (user chronological age ~52)
    if "metabolic_age" in latest and pd.notna(latest["metabolic_age"]):
        met_age = latest["metabolic_age"]
        gap = 52 - met_age  # positive = younger metabolic age = good
        if gap >= 5:
            ma_score = 100.0
        elif gap >= 0:
            ma_score = 70 + gap * 6
        elif gap >= -5:
            ma_score = 70 + gap * 6  # 70 at 0 gap, 40 at -5
        else:
            ma_score = max(10.0, 40 + gap * 4)
        components.append({
            "name": "Metabolic Age",
            "score": _clamp(ma_score),
            "weight": 0.15,
            "detail": f"{met_age:.0f} years (gap {gap:+.0f})",
        })
        weights["ma"] = 0.15

    if not weights:
        return {
            "name": "body_composition", "label": DOMAIN_LABELS["body_composition"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    total_w = sum(weights.values())
    score = sum(c["score"] * c["weight"] / total_w for c in components)
    for comp in components:
        comp["weight"] = round(comp["weight"] / total_w, 3)

    # Trend from body fat
    bf_trend = None
    if "body_fat_pct" in body_df.columns:
        bf_trend = _recent_trend(body_df.sort_values("day")["body_fat_pct"].dropna(), window=10)
    # For body fat, declining trend is improving (invert)
    trend_dir = _trend_direction(bf_trend)
    if trend_dir == "improving":
        trend_dir = "declining"
    elif trend_dir == "declining":
        trend_dir = "improving"

    key_metric = None
    if "body_fat_pct" in latest and pd.notna(latest["body_fat_pct"]):
        key_metric = f'{latest["body_fat_pct"]:.1f}% body fat'

    return {
        "name": "body_composition", "label": DOMAIN_LABELS["body_composition"],
        "score": _clamp(score), "trend": trend_dir,
        "available": True, "components": components, "key_metric": key_metric,
    }


def _score_sleep_recovery(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Sleep & recovery: sleep score, readiness, stress/recovery ratio, deep sleep %."""
    sleep_df = datasets.get("sleep", pd.DataFrame())
    readiness_df = datasets.get("readiness", pd.DataFrame())
    stress_df = datasets.get("stress", pd.DataFrame())

    components: list[dict[str, Any]] = []
    weights: dict[str, float] = {}

    # Sleep score (already 0-100)
    if not sleep_df.empty and "score" in sleep_df.columns:
        sleep_series = sleep_df.sort_values("day")["score"].dropna()
        if len(sleep_series) >= 7:
            avg_sleep = sleep_series.tail(14).mean()
            components.append({
                "name": "Sleep Score",
                "score": _clamp(avg_sleep),
                "weight": 0.30,
                "detail": f"{avg_sleep:.0f}/100 (14-day avg)",
            })
            weights["sleep"] = 0.30

    # Readiness score (already 0-100)
    if not readiness_df.empty and "score" in readiness_df.columns:
        ready_series = readiness_df.sort_values("day")["score"].dropna()
        if len(ready_series) >= 7:
            avg_ready = ready_series.tail(14).mean()
            components.append({
                "name": "Readiness Score",
                "score": _clamp(avg_ready),
                "weight": 0.25,
                "detail": f"{avg_ready:.0f}/100 (14-day avg)",
            })
            weights["readiness"] = 0.25

    # Stress/recovery ratio
    if not stress_df.empty and "recovery_high" in stress_df.columns and "stress_high" in stress_df.columns:
        recent_stress = stress_df.sort_values("day").tail(14)
        total_recovery = recent_stress["recovery_high"].sum()
        total_stress = recent_stress["stress_high"].sum()
        if total_stress > 0:
            ratio = total_recovery / total_stress
            if ratio >= 1.5:
                sr_score = 100.0
            elif ratio >= 1.0:
                sr_score = 60 + (ratio - 1.0) * 80
            elif ratio >= 0.5:
                sr_score = 30 + (ratio - 0.5) * 60
            else:
                sr_score = max(10.0, ratio * 60)
            components.append({
                "name": "Stress/Recovery Balance",
                "score": _clamp(sr_score),
                "weight": 0.20,
                "detail": f"{ratio:.2f} ratio (14-day)",
            })
            weights["stress_recovery"] = 0.20

    # Deep sleep %
    if not sleep_df.empty and "deep_sleep_duration" in sleep_df.columns and "total_sleep_duration" in sleep_df.columns:
        recent_sleep = sleep_df.sort_values("day").tail(14).dropna(subset=["deep_sleep_duration", "total_sleep_duration"])
        if len(recent_sleep) >= 7:
            total_deep = recent_sleep["deep_sleep_duration"].sum()
            total_sleep_dur = recent_sleep["total_sleep_duration"].sum()
            if total_sleep_dur > 0:
                deep_pct = (total_deep / total_sleep_dur) * 100
                if 20 <= deep_pct <= 25:
                    ds_score = 100.0
                elif 15 <= deep_pct < 20:
                    ds_score = 60 + (deep_pct - 15) * 8
                elif deep_pct > 25:
                    ds_score = max(70.0, 100 - (deep_pct - 25) * 5)
                else:
                    ds_score = max(20.0, deep_pct * 4)
                components.append({
                    "name": "Deep Sleep",
                    "score": _clamp(ds_score),
                    "weight": 0.25,
                    "detail": f"{deep_pct:.1f}% of total sleep",
                })
                weights["deep"] = 0.25

    if not weights:
        return {
            "name": "sleep_recovery", "label": DOMAIN_LABELS["sleep_recovery"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    total_w = sum(weights.values())
    score = sum(c["score"] * c["weight"] / total_w for c in components)
    for comp in components:
        comp["weight"] = round(comp["weight"] / total_w, 3)

    sleep_trend = None
    if not sleep_df.empty and "score" in sleep_df.columns:
        sleep_trend = _recent_trend(sleep_df.sort_values("day")["score"].dropna())

    key_metric = None
    if components:
        key_metric = components[0]["detail"]

    return {
        "name": "sleep_recovery", "label": DOMAIN_LABELS["sleep_recovery"],
        "score": _clamp(score), "trend": _trend_direction(sleep_trend),
        "available": True, "components": components, "key_metric": key_metric,
    }


def _score_training(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Training & fitness: frequency, volume trend, progressive overload, muscle group balance."""
    workouts_df = datasets.get("workouts", pd.DataFrame())

    if workouts_df.empty or "day" not in workouts_df.columns:
        return {
            "name": "training", "label": DOMAIN_LABELS["training"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    components: list[dict[str, Any]] = []
    weights: dict[str, float] = {}
    sorted_w = workouts_df.sort_values("day")

    # Training frequency (sessions per week, last 4 weeks)
    recent_days = sorted_w["day"].max() - pd.Timedelta(days=28)
    recent = sorted_w[sorted_w["day"] >= recent_days]
    if not recent.empty:
        sessions = recent.groupby("day").ngroups
        sessions_per_week = sessions / 4
        if 4 <= sessions_per_week <= 5:
            freq_score = 100.0
        elif 3 <= sessions_per_week < 4:
            freq_score = 80.0
        elif sessions_per_week >= 6:
            freq_score = 85.0  # slight overtraining risk
        elif 2 <= sessions_per_week < 3:
            freq_score = 60.0
        elif 1 <= sessions_per_week < 2:
            freq_score = 40.0
        else:
            freq_score = 10.0
        components.append({
            "name": "Training Frequency",
            "score": _clamp(freq_score),
            "weight": 0.25,
            "detail": f"{sessions_per_week:.1f} sessions/week",
        })
        weights["freq"] = 0.25

    # Volume trend (weekly total volume over last 8 weeks)
    if "volume" in sorted_w.columns:
        eight_weeks_ago = sorted_w["day"].max() - pd.Timedelta(days=56)
        vol_data = sorted_w[sorted_w["day"] >= eight_weeks_ago].copy()
        if not vol_data.empty:
            vol_data["week"] = vol_data["day"].dt.isocalendar().week.astype(int)
            weekly_vol = vol_data.groupby("week")["volume"].sum()
            if len(weekly_vol) >= 4:
                vol_trend = _recent_trend(weekly_vol, window=8)
                if vol_trend is not None:
                    if vol_trend > 50:
                        vt_score = 90.0
                    elif vol_trend > 0:
                        vt_score = 70.0
                    elif vol_trend > -50:
                        vt_score = 50.0
                    else:
                        vt_score = 30.0
                    components.append({
                        "name": "Volume Trend",
                        "score": _clamp(vt_score),
                        "weight": 0.30,
                        "detail": f"{vol_trend:+.0f} kg/week change",
                    })
                    weights["vol"] = 0.30

    # Progressive overload (compare top exercises last 4w vs previous 4w)
    if "exercise" in sorted_w.columns and "weight_kg" in sorted_w.columns:
        four_weeks_ago = sorted_w["day"].max() - pd.Timedelta(days=28)
        eight_weeks_ago = sorted_w["day"].max() - pd.Timedelta(days=56)
        current_period = sorted_w[sorted_w["day"] >= four_weeks_ago]
        prev_period = sorted_w[(sorted_w["day"] >= eight_weeks_ago) & (sorted_w["day"] < four_weeks_ago)]

        if not current_period.empty and not prev_period.empty:
            current_max = current_period.groupby("exercise")["weight_kg"].max()
            prev_max = prev_period.groupby("exercise")["weight_kg"].max()
            common = current_max.index.intersection(prev_max.index)
            if len(common) >= 3:
                progressing = sum(1 for ex in common if current_max[ex] > prev_max[ex])
                pct_progressing = progressing / len(common)
                po_score = _clamp(pct_progressing * 100)
                components.append({
                    "name": "Progressive Overload",
                    "score": po_score,
                    "weight": 0.25,
                    "detail": f"{progressing}/{len(common)} exercises progressing",
                })
                weights["overload"] = 0.25

    # Muscle group balance (CV of volume across muscle groups)
    if "muscle_group" in recent.columns and "volume" in recent.columns:
        mg_vol = recent.groupby("muscle_group")["volume"].sum()
        if len(mg_vol) >= 3:
            cv = mg_vol.std() / mg_vol.mean() if mg_vol.mean() > 0 else 1.0
            if cv < 0.3:
                bal_score = 90.0
            elif cv < 0.5:
                bal_score = 70.0
            elif cv < 0.7:
                bal_score = 50.0
            else:
                bal_score = 30.0
            components.append({
                "name": "Muscle Group Balance",
                "score": _clamp(bal_score),
                "weight": 0.20,
                "detail": f"CV = {cv:.2f}",
            })
            weights["balance"] = 0.20

    if not weights:
        return {
            "name": "training", "label": DOMAIN_LABELS["training"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    total_w = sum(weights.values())
    score = sum(c["score"] * c["weight"] / total_w for c in components)
    for comp in components:
        comp["weight"] = round(comp["weight"] / total_w, 3)

    vol_slope = _recent_trend(
        sorted_w.groupby("day")["volume"].sum().reset_index(drop=True), window=14
    ) if "volume" in sorted_w.columns else None

    key_metric = components[0]["detail"] if components else None

    return {
        "name": "training", "label": DOMAIN_LABELS["training"],
        "score": _clamp(score), "trend": _trend_direction(vol_slope, threshold=5),
        "available": True, "components": components, "key_metric": key_metric,
    }


def _score_nutrition(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Nutrition: caloric balance, protein g/kg, logging compliance, micronutrients."""
    nutrition_df = datasets.get("nutrition", pd.DataFrame())

    if nutrition_df.empty or "calories" not in nutrition_df.columns:
        return {
            "name": "nutrition", "label": DOMAIN_LABELS["nutrition"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    components: list[dict[str, Any]] = []
    weights: dict[str, float] = {}
    sorted_n = nutrition_df.sort_values("day")
    recent_30 = sorted_n.tail(30)

    # Get latest body weight for protein/kg
    body_df = datasets.get("body_composition", pd.DataFrame())
    latest_weight = None
    if not body_df.empty and "weight_kg" in body_df.columns:
        weight_series = body_df.sort_values("day")["weight_kg"].dropna()
        if len(weight_series) > 0:
            latest_weight = weight_series.iloc[-1]

    # Get active calories + BMR for caloric balance
    activity_df = datasets.get("activity", pd.DataFrame())
    bmr = None
    if not body_df.empty and "bmr" in body_df.columns:
        bmr_series = body_df.sort_values("day")["bmr"].dropna()
        if len(bmr_series) > 0:
            bmr = bmr_series.iloc[-1]

    # Caloric balance
    if bmr is not None and not activity_df.empty and "active_calories" in activity_df.columns:
        # Match nutrition days with activity days
        avg_intake = recent_30["calories"].mean()
        recent_activity = activity_df.sort_values("day").tail(30)
        avg_active = recent_activity["active_calories"].mean()
        tdee = bmr + avg_active
        deficit = avg_intake - tdee
        abs_deficit = abs(deficit)
        if abs_deficit <= 200:
            cal_score = 95.0
        elif abs_deficit <= 400:
            cal_score = 75.0
        elif abs_deficit <= 600:
            cal_score = 55.0
        else:
            cal_score = max(20.0, 55 - (abs_deficit - 600) * 0.05)
        components.append({
            "name": "Caloric Balance",
            "score": _clamp(cal_score),
            "weight": 0.25,
            "detail": f"{deficit:+.0f} kcal/day vs TDEE",
        })
        weights["cal"] = 0.25

    # Protein per kg bodyweight
    if latest_weight and "protein" in recent_30.columns:
        avg_protein = recent_30["protein"].mean()
        pkg = avg_protein / latest_weight
        if 1.6 <= pkg <= 2.2:
            prot_score = 100.0
        elif 1.4 <= pkg < 1.6:
            prot_score = 70.0
        elif pkg > 2.2:
            prot_score = 90.0  # slightly above is fine
        elif 1.0 <= pkg < 1.4:
            prot_score = 45.0
        else:
            prot_score = 20.0
        components.append({
            "name": "Protein Adequacy",
            "score": _clamp(prot_score),
            "weight": 0.30,
            "detail": f"{pkg:.2f} g/kg ({avg_protein:.0f}g/day)",
        })
        weights["protein"] = 0.30

    # Logging compliance (% of last 30 calendar days with entries)
    if "day" in sorted_n.columns:
        end_date = sorted_n["day"].max()
        start_date = end_date - pd.Timedelta(days=30)
        logged_days = sorted_n[sorted_n["day"] >= start_date].shape[0]
        compliance = min(logged_days / 30 * 100, 100)
        if compliance >= 90:
            comp_score = 100.0
        elif compliance >= 70:
            comp_score = 70.0
        elif compliance >= 50:
            comp_score = 45.0
        else:
            comp_score = max(10.0, compliance * 0.8)
        components.append({
            "name": "Logging Compliance",
            "score": _clamp(comp_score),
            "weight": 0.20,
            "detail": f"{compliance:.0f}% of last 30 days",
        })
        weights["compliance"] = 0.20

    # Micronutrient coverage
    micros = {"calcium": 1000, "vitamin_c": 90, "iron": 8, "fiber": 30}
    if any(m in recent_30.columns for m in micros):
        met_count = 0
        total_checked = 0
        for nutrient, target in micros.items():
            if nutrient in recent_30.columns:
                total_checked += 1
                avg_val = recent_30[nutrient].mean()
                if avg_val >= target * 0.8:  # 80% of target counts as met
                    met_count += 1
        if total_checked > 0:
            micro_pct = met_count / total_checked
            micro_score = _clamp(micro_pct * 100)
            components.append({
                "name": "Micronutrient Coverage",
                "score": micro_score,
                "weight": 0.25,
                "detail": f"{met_count}/{total_checked} targets met",
            })
            weights["micro"] = 0.25

    if not weights:
        return {
            "name": "nutrition", "label": DOMAIN_LABELS["nutrition"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    total_w = sum(weights.values())
    score = sum(c["score"] * c["weight"] / total_w for c in components)
    for comp in components:
        comp["weight"] = round(comp["weight"] / total_w, 3)

    cal_trend = _recent_trend(sorted_n["calories"].dropna()) if "calories" in sorted_n.columns else None

    key_metric = None
    for comp in components:
        if comp["name"] == "Protein Adequacy":
            key_metric = comp["detail"]
            break
    if key_metric is None and components:
        key_metric = components[0]["detail"]

    return {
        "name": "nutrition", "label": DOMAIN_LABELS["nutrition"],
        "score": _clamp(score), "trend": _trend_direction(cal_trend),
        "available": True, "components": components, "key_metric": key_metric,
    }


def _score_metabolic(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Metabolic health: HbA1c, cholesterol/HDL ratio, BMR score, body fat trend."""
    bloodwork_df = datasets.get("bloodwork", pd.DataFrame())
    body_df = datasets.get("body_composition", pd.DataFrame())

    components: list[dict[str, Any]] = []
    weights: dict[str, float] = {}

    # HbA1c
    if not bloodwork_df.empty and "hba1c_mmol" in bloodwork_df.columns:
        latest_bw = bloodwork_df.sort_values("day").iloc[-1]
        if pd.notna(latest_bw.get("hba1c_mmol")):
            hba1c = latest_bw["hba1c_mmol"]
            if hba1c < 32:
                hba1c_score = 100.0
            elif hba1c < 38:
                hba1c_score = 90 - (hba1c - 32) * 3.3
            elif hba1c < 42:
                hba1c_score = 70 - (hba1c - 38) * 7.5
            elif hba1c < 48:
                hba1c_score = 40 - (hba1c - 42) * 4.2
            else:
                hba1c_score = max(5.0, 15 - (hba1c - 48) * 2)
            components.append({
                "name": "HbA1c",
                "score": _clamp(hba1c_score),
                "weight": 0.35,
                "detail": f"{hba1c:.0f} mmol/mol",
            })
            weights["hba1c"] = 0.35

    # Cholesterol/HDL ratio
    if not bloodwork_df.empty and "cholesterol_hdl_ratio" in bloodwork_df.columns:
        latest_bw = bloodwork_df.sort_values("day").iloc[-1]
        if pd.notna(latest_bw.get("cholesterol_hdl_ratio")):
            ratio = latest_bw["cholesterol_hdl_ratio"]
            if ratio < 3.5:
                chol_score = 100.0
            elif ratio < 4.0:
                chol_score = 80.0
            elif ratio < 5.0:
                chol_score = 50.0
            else:
                chol_score = max(10.0, 30 - (ratio - 5) * 10)
            components.append({
                "name": "Cholesterol/HDL Ratio",
                "score": _clamp(chol_score),
                "weight": 0.30,
                "detail": f"{ratio:.2f}",
            })
            weights["chol"] = 0.30

    # BMR score from Boditrax
    if not body_df.empty and "bmr_score" in body_df.columns:
        latest_body = body_df.sort_values("day").iloc[-1]
        if pd.notna(latest_body.get("bmr_score")):
            bmr_s = latest_body["bmr_score"]
            bmr_score = _clamp(bmr_s * 10)  # 0-10 scale → 0-100
            components.append({
                "name": "BMR Score",
                "score": bmr_score,
                "weight": 0.15,
                "detail": f"{bmr_s:.1f}/10",
            })
            weights["bmr"] = 0.15

    # Body fat trend
    if not body_df.empty and "body_fat_pct" in body_df.columns:
        bf_series = body_df.sort_values("day")["body_fat_pct"].dropna()
        if len(bf_series) >= 3:
            bf_trend = _recent_trend(bf_series, window=10)
            if bf_trend is not None:
                latest_bf = bf_series.iloc[-1]
                # If body fat is already low, stable is good
                if latest_bf <= 15:
                    if bf_trend <= 0:
                        bft_score = 90.0
                    else:
                        bft_score = 70.0
                else:
                    # Higher body fat: declining is good
                    if bf_trend < -0.05:
                        bft_score = 90.0
                    elif bf_trend < 0:
                        bft_score = 75.0
                    elif bf_trend < 0.05:
                        bft_score = 55.0
                    else:
                        bft_score = 30.0
                components.append({
                    "name": "Body Fat Trend",
                    "score": _clamp(bft_score),
                    "weight": 0.20,
                    "detail": f"{bf_trend * 30:+.2f}%/month",
                })
                weights["bf_trend"] = 0.20

    if not weights:
        return {
            "name": "metabolic", "label": DOMAIN_LABELS["metabolic"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    total_w = sum(weights.values())
    score = sum(c["score"] * c["weight"] / total_w for c in components)
    for comp in components:
        comp["weight"] = round(comp["weight"] / total_w, 3)

    key_metric = components[0]["detail"] if components else None

    return {
        "name": "metabolic", "label": DOMAIN_LABELS["metabolic"],
        "score": _clamp(score), "trend": "stable",
        "available": True, "components": components, "key_metric": key_metric,
    }


def _score_hormonal(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Hormonal health: total T, free T, E2 balance, trend."""
    bloodwork_df = datasets.get("bloodwork", pd.DataFrame())

    if bloodwork_df.empty:
        return {
            "name": "hormonal", "label": DOMAIN_LABELS["hormonal"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    sorted_bw = bloodwork_df.sort_values("day")
    latest = sorted_bw.iloc[-1]
    components: list[dict[str, Any]] = []
    weights: dict[str, float] = {}

    # Total Testosterone
    if "testosterone_nmol" in latest and pd.notna(latest["testosterone_nmol"]):
        val = latest["testosterone_nmol"]
        if val < 12:
            t_score = 10.0
        elif val < 15:
            t_score = 30.0
        elif val < 20:
            t_score = 50.0
        elif val <= 30:
            t_score = 90.0
        elif val <= 35:
            t_score = 100.0
        else:
            t_score = 85.0  # supraphysiological
        components.append({
            "name": "Total Testosterone",
            "score": _clamp(t_score),
            "weight": 0.35,
            "detail": f"{val:.1f} nmol/L",
        })
        weights["total_t"] = 0.35

    # Free Testosterone
    if "free_testosterone_nmol" in latest and pd.notna(latest["free_testosterone_nmol"]):
        val = latest["free_testosterone_nmol"]
        if val < 0.30:
            ft_score = 10.0
        elif val < 0.40:
            ft_score = 30.0
        elif val <= 0.50:
            ft_score = 50.0
        elif val <= 0.80:
            ft_score = 90.0
        else:
            ft_score = 100.0
        components.append({
            "name": "Free Testosterone",
            "score": _clamp(ft_score),
            "weight": 0.30,
            "detail": f"{val:.3f} nmol/L",
        })
        weights["free_t"] = 0.30

    # Oestradiol balance (sweet spot: 100-150 pmol/L)
    if "oestradiol_pmol" in latest and pd.notna(latest["oestradiol_pmol"]):
        val = latest["oestradiol_pmol"]
        if 100 <= val <= 150:
            e2_score = 100.0
        elif 75 <= val < 100:
            e2_score = 70.0
        elif 150 < val <= 200:
            e2_score = 70.0
        elif val < 75:
            e2_score = 30.0
        else:
            e2_score = 30.0
        components.append({
            "name": "Oestradiol Balance",
            "score": _clamp(e2_score),
            "weight": 0.25,
            "detail": f"{val:.0f} pmol/L",
        })
        weights["e2"] = 0.25

    # Trend (latest vs previous test)
    if len(sorted_bw) >= 2 and "testosterone_nmol" in sorted_bw.columns:
        prev = sorted_bw.iloc[-2]
        if pd.notna(latest.get("testosterone_nmol")) and pd.notna(prev.get("testosterone_nmol")):
            t_change = latest["testosterone_nmol"] - prev["testosterone_nmol"]
            if t_change > 2:
                trend_score = 90.0
            elif t_change > 0:
                trend_score = 70.0
            elif t_change > -2:
                trend_score = 50.0
            else:
                trend_score = 30.0
            components.append({
                "name": "Testosterone Trend",
                "score": _clamp(trend_score),
                "weight": 0.10,
                "detail": f"{t_change:+.1f} nmol/L vs previous",
            })
            weights["trend"] = 0.10

    if not weights:
        return {
            "name": "hormonal", "label": DOMAIN_LABELS["hormonal"],
            "score": 0, "trend": "stable", "available": False,
            "components": [], "key_metric": None,
        }

    total_w = sum(weights.values())
    score = sum(c["score"] * c["weight"] / total_w for c in components)
    for comp in components:
        comp["weight"] = round(comp["weight"] / total_w, 3)

    # Determine trend
    trend_dir = "stable"
    if len(sorted_bw) >= 2 and "testosterone_nmol" in sorted_bw.columns:
        if pd.notna(latest.get("testosterone_nmol")) and pd.notna(sorted_bw.iloc[-2].get("testosterone_nmol")):
            t_diff = latest["testosterone_nmol"] - sorted_bw.iloc[-2]["testosterone_nmol"]
            trend_dir = _trend_direction(t_diff, threshold=1.0)

    key_metric = None
    if "testosterone_nmol" in latest and pd.notna(latest["testosterone_nmol"]):
        key_metric = f'Total T: {latest["testosterone_nmol"]:.1f} nmol/L'

    return {
        "name": "hormonal", "label": DOMAIN_LABELS["hormonal"],
        "score": _clamp(score), "trend": trend_dir,
        "available": True, "components": components, "key_metric": key_metric,
    }


# ── Main composite scoring ──


def _generate_interventions(
    domain_scores: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate prioritised interventions for domains scoring below 70."""
    intervention_map: dict[str, dict[str, str]] = {
        "cardiovascular": {
            "action": "Add 2-3 sessions of zone 2 cardio (30-45 min) per week to improve VO2 Max and cardiovascular efficiency.",
            "expected_impact": "VO2 Max improvement of 2-5 ml/kg/min over 8-12 weeks",
        },
        "body_composition": {
            "action": "Review caloric intake relative to TDEE; ensure sufficient protein (1.6-2.2 g/kg) and progressive resistance training.",
            "expected_impact": "Favourable body composition shift within 4-8 weeks",
        },
        "sleep_recovery": {
            "action": "Establish consistent sleep/wake times; limit screens 1hr before bed; keep bedroom cool (16-18°C).",
            "expected_impact": "Sleep score improvement of 5-10 points within 2-3 weeks",
        },
        "training": {
            "action": "Ensure progressive overload each mesocycle; balance push/pull/legs volume; include deload weeks.",
            "expected_impact": "Improved volume trend and exercise progression within 4 weeks",
        },
        "nutrition": {
            "action": "Log meals consistently; prioritise protein at each meal; track micronutrient intake.",
            "expected_impact": "Better caloric balance and nutrient coverage within 2 weeks",
        },
        "metabolic": {
            "action": "Reduce refined carbohydrates; increase NEAT (non-exercise activity); monitor HbA1c at next blood test.",
            "expected_impact": "Improved metabolic markers over 8-12 weeks",
        },
        "hormonal": {
            "action": "Review TRT protocol timing; ensure blood draws are trough samples; discuss E2 management with clinic.",
            "expected_impact": "Optimised hormonal balance at next blood test",
        },
    }

    interventions = []
    for name, domain in domain_scores.items():
        if not domain["available"] or domain["score"] >= 70:
            continue
        weight = DOMAIN_WEIGHTS.get(name, 0.1)
        priority_raw = weight * (100 - domain["score"])
        priority = min(5, max(1, int(priority_raw / 5) + 1))
        info = intervention_map.get(name, {
            "action": f"Review {DOMAIN_LABELS.get(name, name)} metrics and address lowest-scoring components.",
            "expected_impact": "Improvement expected within 4-8 weeks",
        })
        interventions.append({
            "priority": priority,
            "domain": DOMAIN_LABELS.get(name, name),
            "action": info["action"],
            "expected_impact": info["expected_impact"],
        })

    interventions.sort(key=lambda x: x["priority"], reverse=True)
    return interventions


def compute_health_screening(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Compute composite health screening from all data sources.

    Returns dict with overall score, domain breakdowns, risk factors,
    prioritised interventions, and VO2 Max data.
    """
    # Score all domains
    scorers = {
        "cardiovascular": _score_cardiovascular,
        "body_composition": _score_body_composition,
        "sleep_recovery": _score_sleep_recovery,
        "training": _score_training,
        "nutrition": _score_nutrition,
        "metabolic": _score_metabolic,
        "hormonal": _score_hormonal,
    }

    domain_scores: dict[str, dict[str, Any]] = {}
    for name, scorer in scorers.items():
        try:
            domain_scores[name] = scorer(datasets)
        except Exception:
            logger.exception("Error scoring domain %s", name)
            domain_scores[name] = {
                "name": name, "label": DOMAIN_LABELS[name],
                "score": 0, "trend": "stable", "available": False,
                "components": [], "key_metric": None,
            }

    # Compute overall score with weight redistribution
    available = {k: v for k, v in domain_scores.items() if v["available"]}
    total_weight = sum(DOMAIN_WEIGHTS[k] for k in available)

    if total_weight > 0:
        overall_score = sum(
            v["score"] * DOMAIN_WEIGHTS[k] / total_weight
            for k, v in available.items()
        )
    else:
        overall_score = 0.0

    # Overall trend (weighted vote)
    trend_votes = {"improving": 0.0, "stable": 0.0, "declining": 0.0}
    for k, v in available.items():
        trend_votes[v["trend"]] += DOMAIN_WEIGHTS[k]
    overall_trend = max(trend_votes, key=trend_votes.get)  # type: ignore[arg-type]

    data_completeness = len(available) / len(scorers) if scorers else 0.0

    # Risk factors from existing alerts
    try:
        from src.correlate import compute_correlations
        correlations = compute_correlations(datasets)
        raw_alerts = compute_alerts(datasets, correlations)
    except Exception:
        logger.exception("Error computing alerts for screening")
        raw_alerts = []

    # Filter to health-screening relevant categories
    screening_categories = {"bloodwork", "body", "sleep", "training", "nutrition", "activity"}
    risk_factors = [
        a for a in raw_alerts
        if a.get("category", "") in screening_categories
        and a.get("severity") in ("critical", "high", "medium")
    ]

    # Generate interventions
    interventions = _generate_interventions(domain_scores)

    # VO2 Max data
    vo2max_entries = load_vo2max()
    vo2max_classification = None
    if vo2max_entries:
        vo2max_classification = classify_vo2max(vo2max_entries[-1]["value"])

    return {
        "overall_score": round(overall_score, 1),
        "overall_trend": overall_trend,
        "data_completeness": round(data_completeness, 2),
        "domains": list(domain_scores.values()),
        "risk_factors": risk_factors,
        "interventions": interventions,
        "vo2max": vo2max_classification,
        "vo2max_history": vo2max_entries,
    }
