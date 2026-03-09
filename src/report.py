"""Markdown report generation with embedded base64 PNG charts — multi-source."""

import base64
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

logger = logging.getLogger(__name__)

plt.rcParams.update({
    "figure.figsize": (10, 4),
    "figure.dpi": 120,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "font.size": 10,
})


def _fig_to_base64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _embed_chart(fig: plt.Figure, alt_text: str = "chart") -> str:
    encoded = _fig_to_base64(fig)
    return f"![{alt_text}](data:image/png;base64,{encoded})"


def _weekly_resample(df: pd.DataFrame, date_col: str, value_col: str) -> pd.DataFrame:
    temp = df[[date_col, value_col]].dropna().copy()
    temp = temp.set_index(date_col)
    weekly = temp.resample("W").mean().dropna().reset_index()
    return weekly


def _corr_strength(corr: float | None) -> str:
    if corr is None:
        return "insufficient data"
    abs_c = abs(corr)
    if abs_c > 0.6:
        return "strong"
    if abs_c > 0.3:
        return "moderate"
    return "weak"


# ── Blood Work Section ──

def _bloodwork_section(datasets: dict[str, pd.DataFrame]) -> str:
    lines = ["## Blood Work (TRT Monitoring)", ""]
    bw_df = datasets.get("bloodwork", pd.DataFrame())

    if bw_df.empty:
        lines.append("*No blood work data available for this period.*\n")
        return "\n".join(lines)

    latest = bw_df.sort_values("day").iloc[-1]
    lines.append(f"**Latest Test:** {latest['day'].strftime('%Y-%m-%d') if hasattr(latest['day'], 'strftime') else latest['day']}\n")

    # Key markers summary
    markers = [
        ("testosterone_nmol", "Total Testosterone", "nmol/l"),
        ("free_testosterone_nmol", "Free Testosterone", "nmol/l"),
        ("oestradiol_pmol", "Oestradiol", "pmol/l"),
        ("haematocrit_pct", "Haematocrit", "%"),
        ("psa_ug", "PSA", "µg/l"),
        ("hba1c_mmol", "HbA1c", "mmol/mol"),
    ]
    for col, label, unit in markers:
        if col in latest.index and pd.notna(latest[col]):
            lines.append(f"- **{label}:** {latest[col]:.2f} {unit}")
    lines.append("")

    # Testosterone Trend Chart
    if len(bw_df) >= 2 and "testosterone_nmol" in bw_df.columns:
        fig, ax = plt.subplots()
        ax.plot(bw_df["day"], bw_df["testosterone_nmol"], marker="o", color="#7A6FBE", label="Total Testosterone")
        if "free_testosterone_nmol" in bw_df.columns:
            ax2 = ax.twinx()
            ax2.plot(bw_df["day"], bw_df["free_testosterone_nmol"], marker="s", color="#50B88E", label="Free Testosterone")
            ax2.set_ylabel("Free T (nmol/l)")
            lines.append(_embed_chart(fig, "Testosterone Trend"))
        else:
            ax.set_ylabel("Total T (nmol/l)")
            lines.append(_embed_chart(fig, "Testosterone Trend"))
        lines.append("")

    # Haematocrit Trend
    if len(bw_df) >= 2 and "haematocrit_pct" in bw_df.columns:
        fig, ax = plt.subplots()
        ax.plot(bw_df["day"], bw_df["haematocrit_pct"], marker="o", color="#E63946")
        ax.axhline(y=50, color="#E63946", linestyle="--", alpha=0.5, label="Upper limit (50%)")
        ax.set_ylabel("Haematocrit (%)")
        ax.set_title("Haematocrit Trend (TRT Safety)")
        ax.legend(loc="upper left", fontsize=8)
        lines.append(_embed_chart(fig, "Haematocrit Trend"))
        lines.append("")

    return "\n".join(lines)


# ── Nutrition Section (MFP) ──

def _nutrition_section(datasets: dict[str, pd.DataFrame]) -> str:
    lines = ["## Nutrition (MyFitnessPal)", ""]
    nutr_df = datasets.get("nutrition", pd.DataFrame())
    body_comp_df = datasets.get("body_composition", pd.DataFrame())

    if nutr_df.empty:
        lines.append("*No MyFitnessPal data available for this period.*\n")
        return "\n".join(lines)

    # Logging compliance
    logged_days = (nutr_df["calories"] > 0).sum() if "calories" in nutr_df.columns else 0
    total_days = len(nutr_df)
    compliance = logged_days / total_days * 100 if total_days > 0 else 0
    lines.append(f"**Nutrition Logging Compliance:** {logged_days}/{total_days} days ({compliance:.0f}%)\n")

    # Filter to logged days for averages
    logged = nutr_df[nutr_df["calories"] > 0] if "calories" in nutr_df.columns else nutr_df

    if "calories" in logged.columns and not logged.empty:
        avg_cal = logged["calories"].mean()
        lines.append(f"**Average Daily Calories:** {avg_cal:,.0f} kcal\n")

    # Macro split
    macro_cols = {"protein": "Protein", "carbohydrates": "Carbs", "fat": "Fat"}
    available_macros = {k: v for k, v in macro_cols.items() if k in logged.columns}
    if available_macros and not logged.empty:
        macro_avgs = {label: logged[col].mean() for col, label in available_macros.items()}
        total_macro_g = sum(macro_avgs.values())
        lines.append("**Average Daily Macros:**\n")
        for label, avg_g in macro_avgs.items():
            cal_factor = 4 if label != "Fat" else 9
            pct = (avg_g * cal_factor) / (avg_cal) * 100 if avg_cal > 0 else 0
            lines.append(f"- {label}: {avg_g:.0f}g ({pct:.0f}%)")
        lines.append("")

        # Protein per kg bodyweight
        if "protein" in logged.columns and not body_comp_df.empty and "weight_kg" in body_comp_df.columns:
            latest_weight = body_comp_df.sort_values("day")["weight_kg"].iloc[-1]
            protein_per_kg = logged["protein"].mean() / latest_weight
            target_status = "within" if 1.6 <= protein_per_kg <= 2.2 else "below" if protein_per_kg < 1.6 else "above"
            lines.append(f"**Protein per kg bodyweight:** {protein_per_kg:.1f} g/kg ({target_status} 1.6–2.2g/kg target)\n")

    # Calorie trend chart
    if "calories" in nutr_df.columns and "day" in nutr_df.columns:
        weekly = _weekly_resample(nutr_df[nutr_df["calories"] > 0], "day", "calories")
        if len(weekly) > 1:
            fig, ax = plt.subplots()
            ax.plot(weekly["day"], weekly["calories"], marker="o", markersize=3, linewidth=1.5, color="#E8915A")
            ax.set_ylabel("Calories (kcal)")
            ax.set_title("Weekly Average Daily Calories")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            fig.autofmt_xdate()
            lines.append(_embed_chart(fig, "Weekly Calorie Trend"))
            lines.append("")

    # Macro split stacked area chart (weekly)
    macro_weekly_cols = {k: v for k, v in {"protein": "Protein", "carbohydrates": "Carbs", "fat": "Fat"}.items()
                        if k in logged.columns}
    if len(macro_weekly_cols) == 3 and "day" in logged.columns and len(logged) > 7:
        weekly_macros = logged[["day"] + list(macro_weekly_cols.keys())].set_index("day").resample("W").mean().dropna()
        if len(weekly_macros) > 1:
            fig, ax = plt.subplots()
            colours = {"protein": "#50B88E", "carbohydrates": "#E8915A", "fat": "#7A6FBE"}
            bottom = None
            for col, label in macro_weekly_cols.items():
                vals = weekly_macros[col]
                if bottom is None:
                    ax.bar(weekly_macros.index, vals, width=5, label=label, color=colours[col], alpha=0.85)
                    bottom = vals.copy()
                else:
                    ax.bar(weekly_macros.index, vals, width=5, bottom=bottom, label=label,
                           color=colours[col], alpha=0.85)
                    bottom = bottom + vals
            ax.set_ylabel("Grams")
            ax.set_title("Weekly Average Daily Macros")
            ax.legend(loc="upper left", fontsize=8)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            fig.autofmt_xdate()
            lines.append(_embed_chart(fig, "Weekly Macro Split"))
            lines.append("")

    # Protein per kg bodyweight trend (weekly)
    if "protein" in logged.columns and not body_comp_df.empty and "weight_kg" in body_comp_df.columns:
        latest_weight = body_comp_df.sort_values("day")["weight_kg"].iloc[-1]
        weekly_protein = _weekly_resample(logged, "day", "protein")
        if len(weekly_protein) > 1:
            weekly_protein["protein_per_kg"] = weekly_protein["protein"] / latest_weight
            fig, ax = plt.subplots()
            ax.plot(weekly_protein["day"], weekly_protein["protein_per_kg"],
                    marker="o", markersize=3, linewidth=1.5, color="#50B88E")
            ax.axhspan(1.6, 2.2, color="#50B88E", alpha=0.1, label="Target range (1.6–2.2 g/kg)")
            ax.axhline(y=1.6, color="#50B88E", linestyle="--", linewidth=0.8, alpha=0.5)
            ax.axhline(y=2.2, color="#50B88E", linestyle="--", linewidth=0.8, alpha=0.5)
            ax.set_ylabel("Protein (g/kg)")
            ax.set_title("Weekly Protein per kg Bodyweight")
            ax.legend(loc="lower left", fontsize=8)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            fig.autofmt_xdate()
            lines.append(_embed_chart(fig, "Weekly Protein per kg Trend"))
            lines.append("")

    # Meal calorie distribution
    if "meals" in nutr_df.columns:
        meal_cals: dict[str, list[float]] = {}
        for meals_raw in nutr_df["meals"]:
            meals_list = meals_raw if isinstance(meals_raw, list) else []
            for meal in meals_list:
                if isinstance(meal, dict) and "calories" in meal:
                    name = meal.get("name", "Unknown")
                    meal_cals.setdefault(name, []).append(float(meal["calories"]))
        if meal_cals:
            avg_by_meal = {name: sum(vals) / len(vals) for name, vals in meal_cals.items() if vals}
            # Sort by calorie contribution
            sorted_meals = sorted(avg_by_meal.items(), key=lambda x: x[1], reverse=True)
            names = [m[0] for m in sorted_meals]
            values = [m[1] for m in sorted_meals]
            colours = ["#4A90D9", "#E8915A", "#50B88E", "#7A6FBE", "#F4845F"]
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.barh(names[::-1], values[::-1], color=colours[:len(names)][::-1])
            ax.set_xlabel("Average Calories (kcal)")
            ax.set_title("Average Calories by Meal")
            lines.append(_embed_chart(fig, "Meal Calorie Distribution"))
            lines.append("")

    # Surplus/deficit estimate
    activity_df = datasets.get("activity", pd.DataFrame())
    if not logged.empty and not body_comp_df.empty and not activity_df.empty:
        if "calories" in logged.columns and "bmr" in body_comp_df.columns:
            latest_bmr = body_comp_df.sort_values("day")["bmr"].iloc[-1]
            active_cal_col = next((c for c in ["active_calories"] if c in activity_df.columns), None)
            if active_cal_col:
                avg_active = activity_df[active_cal_col].mean()
                avg_intake = logged["calories"].mean()
                tdee_est = latest_bmr + avg_active
                balance = avg_intake - tdee_est
                status = "surplus" if balance > 0 else "deficit"
                lines.append(f"**Estimated Daily Caloric Balance:** {balance:+,.0f} kcal ({status})")
                lines.append(f"*(Based on BMR {latest_bmr:.0f} + avg active calories {avg_active:.0f} = ~{tdee_est:.0f} TDEE)*\n")

    return "\n".join(lines)


# ── Sleep & Recovery Section (Oura) ──

def _sleep_recovery_section(datasets: dict[str, pd.DataFrame]) -> str:
    lines = ["## Sleep & Recovery (Oura Ring)", ""]
    sleep_df = datasets.get("sleep", pd.DataFrame())
    readiness_df = datasets.get("readiness", pd.DataFrame())

    if sleep_df.empty and readiness_df.empty:
        lines.append("*No Oura sleep/readiness data available for this period.*\n")
        return "\n".join(lines)

    # Sleep score
    score_col = "score" if not sleep_df.empty and "score" in sleep_df.columns else None
    if score_col:
        avg_score = sleep_df[score_col].mean()
        lines.append(f"**Average Sleep Score:** {avg_score:.0f}\n")

        weekly = _weekly_resample(sleep_df, "day", score_col)
        if len(weekly) > 1:
            fig, ax = plt.subplots()
            ax.plot(weekly["day"], weekly[score_col], marker="o", markersize=3, linewidth=1.5, color="#4A90D9")
            ax.set_ylabel("Sleep Score")
            ax.set_title("Weekly Average Sleep Score")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            fig.autofmt_xdate()
            lines.append(_embed_chart(fig, "Weekly Sleep Score Trend"))
            lines.append("")
            trend = "improving" if weekly[score_col].iloc[-1] > weekly[score_col].iloc[0] else "declining"
            lines.append(f"Sleep scores have been **{trend}** over the period, ranging from "
                         f"{weekly[score_col].min():.0f} to {weekly[score_col].max():.0f} weekly average.\n")

    # Sleep stage breakdown
    stage_cols = {c: c for c in sleep_df.columns
                  if any(k in c.lower() for k in ["rem", "deep", "light"]) and "duration" in c.lower()
                  } if not sleep_df.empty else {}
    if stage_cols:
        stage_means = {n: sleep_df[c].dropna().mean() / 3600 for n, c in stage_cols.items()}
        if any(v > 0 for v in stage_means.values()):
            fig, ax = plt.subplots()
            labels = [c.replace("_", " ").title() for c in stage_means]
            values = list(stage_means.values())
            ax.bar(labels, values, color=["#5B8BD9", "#2D5F91", "#A8C8F0"][:len(labels)])
            ax.set_ylabel("Hours")
            ax.set_title("Average Sleep Stage Duration")
            lines.append(_embed_chart(fig, "Sleep Stage Breakdown"))
            lines.append("\nAverage nightly time spent in each sleep stage.\n")

    # Readiness
    readiness_col = "score" if not readiness_df.empty and "score" in readiness_df.columns else None
    if readiness_col:
        avg_readiness = readiness_df[readiness_col].mean()
        lines.append(f"**Average Readiness Score:** {avg_readiness:.0f}\n")

        weekly = _weekly_resample(readiness_df, "day", readiness_col)
        if len(weekly) > 1:
            fig, ax = plt.subplots()
            ax.plot(weekly["day"], weekly[readiness_col], marker="o", markersize=3, linewidth=1.5, color="#50B88E")
            ax.set_ylabel("Readiness Score")
            ax.set_title("Weekly Average Readiness Score")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            fig.autofmt_xdate()
            lines.append(_embed_chart(fig, "Weekly Readiness Trend"))
            lines.append("")

    # HRV trend
    if not readiness_df.empty:
        hrv_col = next((c for c in ["contributors.hrv_balance", "hrv_balance"] if c in readiness_df.columns), None)
        if hrv_col:
            weekly_hrv = _weekly_resample(readiness_df, "day", hrv_col)
            if len(weekly_hrv) > 1:
                fig, ax = plt.subplots()
                ax.plot(weekly_hrv["day"], weekly_hrv[hrv_col], marker="o", markersize=3, linewidth=1.5, color="#E8915A")
                ax.set_ylabel("HRV Balance")
                ax.set_title("Weekly HRV Balance Trend")
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                fig.autofmt_xdate()
                lines.append(_embed_chart(fig, "Weekly HRV Trend"))
                lines.append("\nHRV balance reflects heart rate variability relative to your personal baseline.\n")

    # Recovery patterns
    if readiness_col:
        high = (readiness_df[readiness_col] >= 80).sum()
        low = (readiness_df[readiness_col] < 60).sum()
        total = len(readiness_df)
        lines.append(f"**Recovery patterns:** {high} high-readiness days ({high/total*100:.0f}%), "
                     f"{low} low-readiness days ({low/total*100:.0f}%) out of {total} total.\n")

    return "\n".join(lines)


# ── Stress Section (Oura) ──

def _stress_section(datasets: dict[str, pd.DataFrame]) -> str:
    lines = ["## Stress & Recovery Balance (Oura Ring)", ""]
    stress_df = datasets.get("stress", pd.DataFrame())

    if stress_df.empty:
        lines.append("*No stress data available for this period.*\n")
        return "\n".join(lines)

    has_stress_high = "stress_high" in stress_df.columns
    has_recovery_high = "recovery_high" in stress_df.columns
    has_summary = "day_summary" in stress_df.columns

    if has_stress_high and has_recovery_high:
        avg_stress = stress_df["stress_high"].mean()
        avg_recovery = stress_df["recovery_high"].mean()
        lines.append(f"**Average Daily High Stress:** {avg_stress:.0f} minutes")
        lines.append(f"**Average Daily High Recovery:** {avg_recovery:.0f} minutes")
        ratio = avg_recovery / avg_stress if avg_stress > 0 else float("inf")
        lines.append(f"**Recovery:Stress Ratio:** {ratio:.1f}:1\n")

        if ratio < 1:
            lines.append("*Recovery time is lower than stress time — prioritise rest and recovery activities.*\n")

        # Weekly trend chart — stress and recovery stacked
        weekly_stress = _weekly_resample(stress_df, "day", "stress_high")
        weekly_recovery = _weekly_resample(stress_df, "day", "recovery_high")
        if len(weekly_stress) > 1 and len(weekly_recovery) > 1:
            merged_weekly = weekly_stress.merge(weekly_recovery, on="day", suffixes=("_stress", "_recovery"))
            fig, ax = plt.subplots()
            width = 5
            ax.bar(merged_weekly["day"], merged_weekly["stress_high"],
                   width=width, color="#E63946", alpha=0.8, label="High Stress")
            ax.bar(merged_weekly["day"], merged_weekly["recovery_high"],
                   width=width, bottom=merged_weekly["stress_high"],
                   color="#50B88E", alpha=0.8, label="High Recovery")
            ax.set_ylabel("Minutes")
            ax.set_title("Weekly Avg Daily Stress vs Recovery")
            ax.legend(loc="upper left", fontsize=8)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            fig.autofmt_xdate()
            lines.append(_embed_chart(fig, "Weekly Stress vs Recovery"))
            lines.append("")

        # Stress trend
        trend = _recent_trend(stress_df["stress_high"])
        if trend is not None:
            if trend > 0.5:
                lines.append("Daily stress has been **increasing** over the past 28 days.\n")
            elif trend < -0.5:
                lines.append("Daily stress has been **decreasing** over the past 28 days.\n")
            else:
                lines.append("Daily stress has been **stable** over the past 28 days.\n")

    # Day summary distribution
    if has_summary:
        summary_counts = stress_df["day_summary"].value_counts()
        total = len(stress_df)
        lines.append("**Day Summary Distribution:**\n")
        for summary, count in summary_counts.items():
            lines.append(f"- {summary}: {count} days ({count/total*100:.0f}%)")
        lines.append("")

    return "\n".join(lines)


# ── Training Section (Hevy) ──

def _training_section(datasets: dict[str, pd.DataFrame]) -> str:
    lines = ["## Training (Hevy)", ""]
    workouts_df = datasets.get("workouts", pd.DataFrame())

    if workouts_df.empty:
        lines.append("*No Hevy workout data available for this period.*\n")
        return "\n".join(lines)

    # Session count and frequency
    sessions = workouts_df.groupby("day").first().reset_index()
    num_sessions = len(sessions)
    if num_sessions > 0:
        date_range_days = (sessions["day"].max() - sessions["day"].min()).days or 1
        weeks = max(date_range_days / 7, 1)
        sessions_per_week = num_sessions / weeks
        lines.append(f"**Total Sessions:** {num_sessions} ({sessions_per_week:.1f}/week)\n")

    # Weekly volume trend
    weekly_volume = workouts_df.groupby("day")["volume"].sum().reset_index()
    weekly_volume = weekly_volume.set_index("day").resample("W").sum().reset_index()
    weekly_volume = weekly_volume[weekly_volume["volume"] > 0]

    if len(weekly_volume) > 1:
        fig, ax = plt.subplots()
        ax.bar(weekly_volume["day"], weekly_volume["volume"], width=5, color="#7A6FBE", alpha=0.8)
        ax.set_ylabel("Volume (kg)")
        ax.set_title("Weekly Training Volume")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        fig.autofmt_xdate()
        lines.append(_embed_chart(fig, "Weekly Training Volume"))
        lines.append("")

        first_half = weekly_volume["volume"].iloc[:len(weekly_volume)//2].mean()
        second_half = weekly_volume["volume"].iloc[len(weekly_volume)//2:].mean()
        if second_half > first_half:
            lines.append(f"Training volume has **increased** — first half avg {first_half:,.0f} kg/week "
                         f"vs second half avg {second_half:,.0f} kg/week, indicating progressive overload.\n")
        else:
            lines.append(f"Training volume has been **stable or declining** — first half avg {first_half:,.0f} kg/week "
                         f"vs second half avg {second_half:,.0f} kg/week.\n")

    # Muscle group distribution
    if "muscle_group" in workouts_df.columns:
        muscle_volumes = workouts_df.groupby("muscle_group")["volume"].sum().sort_values(ascending=False)
        muscle_volumes = muscle_volumes[muscle_volumes > 0].head(10)
        if not muscle_volumes.empty:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.barh(muscle_volumes.index[::-1], muscle_volumes.values[::-1], color="#5B8BD9")
            ax.set_xlabel("Total Volume (kg)")
            ax.set_title("Volume by Muscle Group")
            lines.append(_embed_chart(fig, "Muscle Group Distribution"))
            lines.append("\nVolume distribution across muscle groups shows training emphasis.\n")

    # Progressive overload — top exercises
    if "exercise" in workouts_df.columns:
        top_exercises = workouts_df.groupby("exercise")["volume"].sum().nlargest(5).index.tolist()
        overload_notes: list[str] = []
        for exercise_name in top_exercises:
            ex_data = workouts_df[workouts_df["exercise"] == exercise_name].copy()
            daily_max = ex_data.groupby("day")["weight_kg"].max().reset_index()
            if len(daily_max) >= 3:
                first_max = daily_max["weight_kg"].iloc[0]
                last_max = daily_max["weight_kg"].iloc[-1]
                if last_max > first_max:
                    overload_notes.append(f"- **{exercise_name}**: {first_max:.1f} kg → {last_max:.1f} kg (+{last_max-first_max:.1f} kg)")
                elif last_max == first_max:
                    overload_notes.append(f"- **{exercise_name}**: maintained at {last_max:.1f} kg")
        if overload_notes:
            lines.append("**Progressive Overload (top exercises):**\n")
            lines.extend(overload_notes)
            lines.append("")

    return "\n".join(lines)


# ── Body Composition Section (Boditrax) ──

def _body_composition_section(datasets: dict[str, pd.DataFrame]) -> str:
    lines = ["## Body Composition (Boditrax)", ""]
    body_df = datasets.get("body_composition", pd.DataFrame())
    mfp_weight_df = datasets.get("mfp_weight", pd.DataFrame())
    if not mfp_weight_df.empty and "day" in mfp_weight_df.columns:
        mfp_weight_df = mfp_weight_df.copy()
        mfp_weight_df["day"] = pd.to_datetime(mfp_weight_df["day"])

    if body_df.empty:
        lines.append("*No Boditrax scan data available for this period.*\n")
        return "\n".join(lines)

    latest = body_df.sort_values("day").iloc[-1]
    lines.append(f"**Latest Scan:** {latest['day'].strftime('%Y-%m-%d') if hasattr(latest['day'], 'strftime') else latest['day']}\n")

    metrics = [
        ("weight_kg", "Weight", "kg"),
        ("body_fat_pct", "Body Fat", "%"),
        ("muscle_mass_kg", "Muscle Mass", "kg"),
        ("water_mass_kg", "Water Mass", "kg"),
        ("visceral_fat", "Visceral Fat", "rating"),
        ("metabolic_age", "Metabolic Age", "years"),
        ("bmr", "BMR", "kcal"),
        ("bmi", "BMI", "kg/m²"),
        ("phase_angle", "Phase Angle", "°"),
    ]
    for col, label, unit in metrics:
        if col in latest.index and pd.notna(latest[col]):
            lines.append(f"- **{label}:** {latest[col]:.1f} {unit}")
    lines.append("")

    # Trajectory chart if multiple scans
    if len(body_df) >= 2:
        plot_cols = [c for c in ["weight_kg", "body_fat_pct", "muscle_mass_kg"] if c in body_df.columns]
        if plot_cols:
            fig, axes = plt.subplots(1, len(plot_cols), figsize=(4*len(plot_cols), 4))
            if len(plot_cols) == 1:
                axes = [axes]
            colors = ["#4A90D9", "#E8915A", "#50B88E"]
            for idx, col in enumerate(plot_cols):
                axes[idx].plot(body_df["day"], body_df[col], marker="o", color=colors[idx], linewidth=1.5,
                               label="Boditrax scan")
                # Overlay MFP daily weight on the weight panel
                if col == "weight_kg" and not mfp_weight_df.empty:
                    axes[idx].scatter(mfp_weight_df["day"], mfp_weight_df["weight_kg"],
                                      color="#4A90D9", alpha=0.25, s=12, label="MFP daily weight")
                    axes[idx].legend(fontsize=7, loc="best")
                axes[idx].set_title(col.replace("_", " ").title())
                axes[idx].xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
                fig.autofmt_xdate()
            fig.suptitle("Body Composition Trajectory", y=1.02)
            fig.tight_layout()
            lines.append(_embed_chart(fig, "Body Composition Trajectory"))
            lines.append("")

        # Change since first scan
        first = body_df.sort_values("day").iloc[0]
        changes: list[str] = []
        for col, label, unit in [("weight_kg", "Weight", "kg"), ("body_fat_pct", "Body Fat", "%"),
                                  ("muscle_mass_kg", "Muscle Mass", "kg")]:
            if col in body_df.columns and pd.notna(first.get(col)) and pd.notna(latest.get(col)):
                delta = latest[col] - first[col]
                changes.append(f"- **{label}:** {delta:+.1f} {unit}")
        if changes:
            lines.append("**Changes since first scan:**\n")
            lines.extend(changes)
            lines.append("")

    return "\n".join(lines)


# ── Activity Section (Oura) ──

def _activity_section(datasets: dict[str, pd.DataFrame]) -> str:
    lines = ["## Activity & Movement (Oura Ring)", ""]
    activity_df = datasets.get("activity", pd.DataFrame())

    if activity_df.empty:
        lines.append("*No Oura activity data available for this period.*\n")
        return "\n".join(lines)

    steps_col = next((c for c in ["steps", "total_steps"] if c in activity_df.columns), None)
    if steps_col:
        avg_steps = activity_df[steps_col].mean()
        lines.append(f"**Average Daily Steps:** {avg_steps:,.0f}\n")

        weekly = _weekly_resample(activity_df, "day", steps_col)
        if len(weekly) > 1:
            fig, ax = plt.subplots()
            ax.bar(weekly["day"], weekly[steps_col], width=5, color="#7A6FBE", alpha=0.8)
            ax.set_ylabel("Steps")
            ax.set_title("Weekly Average Daily Steps")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            fig.autofmt_xdate()
            lines.append(_embed_chart(fig, "Weekly Steps Trend"))
            lines.append("")

    cal_col = next((c for c in ["total_calories", "calories", "active_calories"] if c in activity_df.columns), None)
    if cal_col:
        lines.append(f"**Average Daily {cal_col.replace('_', ' ').title()}:** {activity_df[cal_col].mean():,.0f} kcal\n")

    if steps_col:
        above = (activity_df[steps_col] >= 7500).sum()
        total = len(activity_df)
        lines.append(f"**Step Consistency:** {above}/{total} days at 7,500+ steps ({above/total*100:.0f}%)\n")

    return "\n".join(lines)


# ── Heart Rate Section ──

def _heartrate_section(datasets: dict[str, pd.DataFrame]) -> str:
    lines = ["## Heart Rate Trends (Oura Ring)", ""]
    hr_df = datasets.get("heartrate", pd.DataFrame())

    if hr_df.empty or len(hr_df) < 3:
        lines.append("*Insufficient heart rate data for trend analysis (need 3+ days).*\n")
        return "\n".join(lines)

    if "hr_mean" in hr_df.columns:
        avg_rhr = hr_df["hr_mean"].mean()
        lines.append(f"**Average Resting Heart Rate:** {avg_rhr:.0f} bpm")
        lines.append(f"**Range:** {hr_df['hr_min'].min():.0f} – {hr_df['hr_max'].max():.0f} bpm")
        lines.append(f"**Days with data:** {len(hr_df)}\n")

        # Weekly trend chart
        weekly = _weekly_resample(hr_df, "day", "hr_mean")
        if len(weekly) > 1:
            fig, ax = plt.subplots()
            ax.plot(weekly["day"], weekly["hr_mean"], color="#E63946", linewidth=2, marker="o", markersize=3)
            ax.fill_between(weekly["day"], weekly["hr_mean"], alpha=0.15, color="#E63946")
            ax.set_ylabel("Heart Rate (bpm)")
            ax.set_title("Weekly Average Resting Heart Rate")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            fig.autofmt_xdate()
            lines.append(_embed_chart(fig, "Weekly RHR Trend"))
            lines.append("")

        # Daily variability chart (std dev)
        if "hr_std" in hr_df.columns and len(hr_df) > 7:
            weekly_std = _weekly_resample(hr_df, "day", "hr_std")
            if len(weekly_std) > 1:
                fig, ax = plt.subplots()
                ax.bar(weekly_std["day"], weekly_std["hr_std"], width=5, color="#F4845F", alpha=0.8)
                ax.set_ylabel("HR Std Dev (bpm)")
                ax.set_title("Weekly Heart Rate Variability (Intra-day)")
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                fig.autofmt_xdate()
                lines.append(_embed_chart(fig, "Weekly HR Variability"))
                lines.append("")

        # Trend narrative
        trend = _recent_trend(hr_df["hr_mean"])
        if trend is not None:
            if trend < -0.05:
                lines.append("Resting heart rate has been **trending downward** (improving) over the past 28 days.\n")
            elif trend > 0.05:
                lines.append("Resting heart rate has been **trending upward** over the past 28 days — "
                             "may indicate accumulated fatigue or under-recovery.\n")
            else:
                lines.append("Resting heart rate has been **stable** over the past 28 days.\n")

    return "\n".join(lines)


# ── SpO2 & Breathing Section ──

def _spo2_section(datasets: dict[str, pd.DataFrame]) -> str:
    lines = ["## Blood Oxygen & Breathing (Oura Ring)", ""]
    spo2_df = datasets.get("spo2", pd.DataFrame())

    if spo2_df.empty:
        lines.append("*No SpO2 data available for this period.*\n")
        return "\n".join(lines)

    spo2_col = "spo2_percentage.average"
    bdi_col = "breathing_disturbance_index"

    # --- SpO2 Average ---
    if spo2_col in spo2_df.columns:
        avg_spo2 = spo2_df[spo2_col].mean()
        min_spo2 = spo2_df[spo2_col].min()
        max_spo2 = spo2_df[spo2_col].max()
        lines.append(f"**Average Nightly SpO2:** {avg_spo2:.1f}%")
        lines.append(f"**Range:** {min_spo2:.1f}% – {max_spo2:.1f}%\n")

        # Flag if average is below normal
        if avg_spo2 < 95:
            lines.append("*Note: Average SpO2 below 95% — consider discussing with a healthcare provider.*\n")

        # Low nights count
        low_nights = (spo2_df[spo2_col] < 95).sum()
        total_nights = len(spo2_df)
        lines.append(f"**Nights below 95%:** {low_nights}/{total_nights} ({low_nights/total_nights*100:.0f}%)\n")

        # Weekly trend chart
        weekly = _weekly_resample(spo2_df, "day", spo2_col)
        if len(weekly) > 1:
            fig, ax = plt.subplots()
            ax.plot(weekly["day"], weekly[spo2_col], color="#3A86FF", linewidth=2, marker="o", markersize=3)
            ax.fill_between(weekly["day"], weekly[spo2_col], alpha=0.15, color="#3A86FF")
            ax.axhline(y=95, color="#E63946", linestyle="--", linewidth=1, alpha=0.6, label="95% threshold")
            ax.set_ylabel("SpO2 (%)")
            ax.set_title("Weekly Average Nightly SpO2")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            ax.legend(loc="lower left", fontsize=8)
            fig.autofmt_xdate()
            lines.append(_embed_chart(fig, "Weekly SpO2 Trend"))
            lines.append("")

        # Trend narrative
        trend = _recent_trend(spo2_df[spo2_col])
        if trend is not None:
            if trend > 0.01:
                lines.append("SpO2 has been **trending upward** over the past 28 days.\n")
            elif trend < -0.01:
                lines.append("SpO2 has been **trending downward** over the past 28 days.\n")
            else:
                lines.append("SpO2 has been **stable** over the past 28 days.\n")

    # --- Breathing Disturbance Index ---
    if bdi_col in spo2_df.columns:
        bdi_valid = spo2_df[bdi_col].dropna()
        if len(bdi_valid) > 0:
            avg_bdi = bdi_valid.mean()
            lines.append(f"**Average Breathing Disturbance Index:** {avg_bdi:.1f}\n")

            # Interpret BDI (events per hour — lower is better)
            if avg_bdi < 5:
                lines.append("Breathing disturbance is **normal** (< 5 events/hr).\n")
            elif avg_bdi < 15:
                lines.append("Breathing disturbance is **mild** (5–15 events/hr).\n")
            elif avg_bdi < 30:
                lines.append("Breathing disturbance is **moderate** (15–30 events/hr) — consider a sleep study.\n")
            else:
                lines.append("Breathing disturbance is **severe** (30+ events/hr) — strongly consider a sleep study.\n")

            # Weekly BDI chart
            weekly_bdi = _weekly_resample(spo2_df, "day", bdi_col)
            if len(weekly_bdi) > 1:
                fig, ax = plt.subplots()
                ax.bar(weekly_bdi["day"], weekly_bdi[bdi_col], width=5, color="#F77F00", alpha=0.8)
                ax.axhline(y=5, color="#E63946", linestyle="--", linewidth=1, alpha=0.6, label="Normal threshold (5)")
                ax.set_ylabel("Events / hr")
                ax.set_title("Weekly Avg Breathing Disturbance Index")
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                ax.legend(loc="upper left", fontsize=8)
                fig.autofmt_xdate()
                lines.append(_embed_chart(fig, "Weekly Breathing Disturbance Trend"))
                lines.append("")

    return "\n".join(lines)


# ── Correlations Section ──

def _correlations_section(correlations: dict[str, Any]) -> str:
    lines = ["## Cross-Source Correlations & Insights", ""]

    if not correlations:
        lines.append("*Insufficient cross-source data to compute correlations.*\n")
        return "\n".join(lines)

    scatter_analyses = [
        ("sleep_vs_readiness", "Sleep vs Readiness"),
        ("training_volume_vs_recovery", "Training Volume vs Next-Day Recovery"),
        ("sleep_vs_training", "Sleep vs Training Performance"),
        ("activity_vs_sleep", "Activity vs Next-Night Sleep"),
        ("protein_vs_recovery", "Protein Intake vs Next-Day Recovery"),
        ("calories_vs_sleep", "Caloric Intake vs Next-Night Sleep"),
        ("stress_vs_sleep", "Stress vs Next-Night Sleep"),
        ("stress_vs_recovery", "Stress vs Next-Day Recovery"),
        ("stress_vs_training", "Stress vs Training Performance"),
    ]

    for key, title in scatter_analyses:
        if key not in correlations:
            continue
        result = correlations[key]
        corr = result.get("correlation")
        data = result.get("data", pd.DataFrame())
        x_label = result.get("x_label", "X")
        y_label = result.get("y_label", "Y")

        if data.empty or corr is None:
            continue

        x_col = [c for c in data.columns if c != "day"][0]
        y_col = [c for c in data.columns if c != "day"][1]

        fig, ax = plt.subplots()
        ax.scatter(data[x_col], data[y_col], alpha=0.4, s=15, color="#4A90D9")
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_title(f"{title} (r = {corr:.2f})")
        lines.append(f"### {title}\n")
        lines.append(_embed_chart(fig, title))
        lines.append("")

        strength = _corr_strength(corr)
        direction = "positive" if corr > 0 else "negative"
        lines.append(f"A **{strength} {direction} correlation** (r = {corr:.2f}) — "
                     f"{'suggesting a meaningful relationship' if strength != 'weak' else 'no strong linear relationship detected'}.\n")

    # Narrative for body comp correlations
    if "nutrition_vs_body_comp" in correlations:
        lines.append("### Nutrition & Body Composition\n")
        lines.append("Nutrition and body composition data are both available. "
                     "Caloric balance trends can be compared against body composition scan changes "
                     "to assess whether intake is tracking with weight/fat/muscle trends.\n")

    if "training_vs_body_comp" in correlations:
        lines.append("### Training & Body Composition\n")
        lines.append("Training volume data and body composition scans are both available. "
                     "Progressive overload trends can be compared against muscle mass changes.\n")

    return "\n".join(lines)


# ── Alerts & Interventions Section ──

def _recent_trend(series: pd.Series, window: int = 28) -> float | None:
    """Compute the slope of the last `window` values using simple linear regression.

    Returns slope per day, or None if insufficient data.
    """
    recent = series.dropna().tail(window)
    if len(recent) < 7:
        return None
    x = range(len(recent))
    x_mean = sum(x) / len(x)
    y_mean = recent.mean()
    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, recent))
    denominator = sum((xi - x_mean) ** 2 for xi in x)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def compute_alerts(datasets: dict[str, pd.DataFrame], correlations: dict[str, Any]) -> list[dict[str, str]]:
    """Compute structured alerts from datasets and correlations.

    Returns a list of dicts, each with keys: severity, title, detail, intervention.
    Sorted by severity (high → medium → low → positive).
    """
    alerts: list[dict[str, str]] = []

    sleep_df = datasets.get("sleep", pd.DataFrame())
    readiness_df = datasets.get("readiness", pd.DataFrame())
    activity_df = datasets.get("activity", pd.DataFrame())
    workouts_df = datasets.get("workouts", pd.DataFrame())
    body_df = datasets.get("body_composition", pd.DataFrame())
    nutrition_df = datasets.get("nutrition", pd.DataFrame())
    spo2_df = datasets.get("spo2", pd.DataFrame())

    # ── Body Composition Alerts ──

    if not body_df.empty and len(body_df) >= 3:
        sorted_body = body_df.sort_values("day")

        # Muscle mass trend (last 4+ scans)
        if "muscle_mass_kg" in sorted_body.columns:
            recent_muscle = sorted_body["muscle_mass_kg"].tail(6)
            slope = _recent_trend(recent_muscle, window=len(recent_muscle))
            if slope is not None and slope < -0.05:
                first_val = recent_muscle.iloc[0]
                last_val = recent_muscle.iloc[-1]
                alerts.append({
                    "severity": "high",
                    "category": "body",
                    "title": "Muscle Mass Declining",
                    "detail": f"Muscle mass has dropped from {first_val:.1f} kg to {last_val:.1f} kg "
                              f"over recent scans ({last_val - first_val:+.1f} kg).",
                    "intervention": (
                        "- Increase training volume, particularly for lagging muscle groups\n"
                        "- Ensure protein intake is at least 1.6–2.2 g/kg bodyweight daily\n"
                        "- Prioritise sleep quality (target 8+ hours) to support muscle protein synthesis\n"
                        "- Consider a deload week if overreaching is suspected (check HRV trends)"
                    ),
                })
            elif slope is not None and slope > 0.05:
                alerts.append({
                    "severity": "positive",
                    "category": "body",
                    "title": "Muscle Mass Increasing",
                    "detail": f"Muscle mass is trending upward over recent scans — current trajectory is favourable.",
                    "intervention": "- Maintain current training and nutrition approach\n- Continue monitoring to ensure the trend sustains",
                })

        # Fat mass / body fat trend
        if "body_fat_pct" in sorted_body.columns:
            recent_fat = sorted_body["body_fat_pct"].tail(6)
            slope = _recent_trend(recent_fat, window=len(recent_fat))
            if slope is not None and slope > 0.1:
                first_val = recent_fat.iloc[0]
                last_val = recent_fat.iloc[-1]
                alerts.append({
                    "severity": "high" if last_val > 20 else "medium",
                    "category": "body",
                    "title": "Body Fat Increasing",
                    "detail": f"Body fat has risen from {first_val:.1f}% to {last_val:.1f}% over recent scans.",
                    "intervention": (
                        "- Review caloric intake — you may be in a larger surplus than intended\n"
                        "- Increase daily movement (target 10,000+ steps) to raise TDEE\n"
                        "- Add 1–2 conditioning sessions per week (e.g. 20 min incline walk, rowing)\n"
                        "- If intentionally bulking, monitor the rate — aim for <0.5% body fat gain per month"
                    ),
                })
            elif slope is not None and slope < -0.1:
                alerts.append({
                    "severity": "positive",
                    "category": "body",
                    "title": "Body Fat Decreasing",
                    "detail": f"Body fat is trending downward — current approach is working.",
                    "intervention": "- Maintain current deficit and activity levels\n- Watch for muscle loss alongside fat loss (check muscle mass trend)",
                })

        # Visceral fat warning
        if "visceral_fat" in sorted_body.columns:
            latest_vf = sorted_body["visceral_fat"].iloc[-1]
            if pd.notna(latest_vf) and latest_vf >= 12:
                alerts.append({
                    "severity": "high",
                    "category": "body",
                    "title": "Elevated Visceral Fat",
                    "detail": f"Visceral fat rating is {latest_vf:.0f} (healthy range: 1–12, ideal: <9).",
                    "intervention": (
                        "- Prioritise reducing overall body fat through caloric deficit\n"
                        "- Increase aerobic activity — visceral fat responds well to consistent cardio\n"
                        "- Reduce alcohol and refined sugar intake\n"
                        "- Consider consulting a healthcare professional if persistently elevated"
                    ),
                })

        # Unfavourable recomposition: gaining fat while losing muscle
        if "muscle_mass_kg" in sorted_body.columns and "fat_mass_kg" in sorted_body.columns:
            recent_muscle = sorted_body["muscle_mass_kg"].tail(4)
            recent_fat_mass = sorted_body["fat_mass_kg"].tail(4)
            if len(recent_muscle) >= 3:
                muscle_delta = recent_muscle.iloc[-1] - recent_muscle.iloc[0]
                fat_delta = recent_fat_mass.iloc[-1] - recent_fat_mass.iloc[0]
                if muscle_delta < -0.3 and fat_delta > 0.3:
                    alerts.append({
                        "severity": "high",
                        "category": "body",
                        "title": "Unfavourable Recomposition",
                        "detail": f"Losing muscle ({muscle_delta:+.1f} kg) while gaining fat ({fat_delta:+.1f} kg) "
                                  f"over recent scans — this is the opposite of the desired direction.",
                        "intervention": (
                            "- Urgently review training stimulus — ensure progressive overload is maintained\n"
                            "- Increase protein to 2.0+ g/kg bodyweight\n"
                            "- Reduce caloric surplus or move to maintenance calories\n"
                            "- Prioritise compound movements and adequate training volume (10+ hard sets per muscle group/week)"
                        ),
                    })

    # ── Sleep & Recovery Alerts ──

    if not sleep_df.empty and "score" in sleep_df.columns:
        recent_sleep = sleep_df.sort_values("day").tail(28)
        avg_recent = recent_sleep["score"].mean()
        low_sleep_days = (recent_sleep["score"] < 60).sum()

        if avg_recent < 65:
            alerts.append({
                "severity": "high",
                "category": "sleep",
                "title": "Poor Recent Sleep Quality",
                "detail": f"Average sleep score over the last 28 days is {avg_recent:.0f} (below 65 threshold).",
                "intervention": (
                    "- Establish a consistent sleep/wake schedule (±30 min even on weekends)\n"
                    "- Avoid screens 1 hour before bed; keep the bedroom cool (18–19°C)\n"
                    "- Limit caffeine after 2pm and alcohol within 3 hours of bedtime\n"
                    "- Consider magnesium glycinate supplementation (200–400 mg before bed)"
                ),
            })
        elif low_sleep_days >= 7:
            alerts.append({
                "severity": "medium",
                "category": "sleep",
                "title": "Frequent Poor Sleep Nights",
                "detail": f"{low_sleep_days} nights with sleep score below 60 in the last 28 days.",
                "intervention": (
                    "- Identify patterns — are poor nights linked to late training, alcohol, or screen time?\n"
                    "- Track evening habits alongside sleep scores to find your triggers\n"
                    "- Consider adjusting training intensity on days following poor sleep"
                ),
            })

        # Declining sleep trend
        slope = _recent_trend(sleep_df.sort_values("day")["score"], window=28)
        if slope is not None and slope < -0.2:
            alerts.append({
                "severity": "medium",
                "category": "sleep",
                "title": "Declining Sleep Trend",
                "detail": "Sleep scores are trending downward over the last 4 weeks.",
                "intervention": (
                    "- Assess potential stressors (work, life changes, overtraining)\n"
                    "- Review training load — a deload week may help if HRV is also declining\n"
                    "- Ensure adequate wind-down routine before bed"
                ),
            })

    # ── Readiness / HRV Alerts ──

    if not readiness_df.empty and "score" in readiness_df.columns:
        recent_readiness = readiness_df.sort_values("day").tail(14)
        low_readiness_streak = 0
        for val in reversed(recent_readiness["score"].values):
            if val < 60:
                low_readiness_streak += 1
            else:
                break

        if low_readiness_streak >= 3:
            alerts.append({
                "severity": "high",
                "category": "sleep",
                "title": "Sustained Low Readiness",
                "detail": f"{low_readiness_streak} consecutive days with readiness below 60 — possible overreaching.",
                "intervention": (
                    "- Take a deload or rest day immediately\n"
                    "- Reduce training volume by 40–50% for the next 3–5 days\n"
                    "- Prioritise sleep, hydration, and nutrition\n"
                    "- If readiness remains low for 7+ days, consider a full deload week"
                ),
            })

        hrv_col = next((c for c in ["contributors.hrv_balance", "hrv_balance"] if c in readiness_df.columns), None)
        if hrv_col:
            slope = _recent_trend(readiness_df.sort_values("day")[hrv_col], window=28)
            if slope is not None and slope < -0.15:
                alerts.append({
                    "severity": "medium",
                    "category": "sleep",
                    "title": "HRV Balance Declining",
                    "detail": "HRV balance has been trending downward — this often precedes illness or overtraining.",
                    "intervention": (
                        "- Reduce training intensity (keep volume, lower load) for the next week\n"
                        "- Increase sleep opportunity by 30–60 minutes\n"
                        "- Check for early signs of illness (sore throat, fatigue)\n"
                        "- Ensure adequate micronutrient intake (vitamin D, zinc, magnesium)"
                    ),
                })

    # ── Training Alerts ──

    if not workouts_df.empty:
        sorted_workouts = workouts_df.sort_values("day")
        recent_cutoff = sorted_workouts["day"].max() - pd.Timedelta(days=14)
        recent_sessions = sorted_workouts[sorted_workouts["day"] >= recent_cutoff]["day"].nunique()

        if recent_sessions < 2:
            alerts.append({
                "severity": "medium",
                "category": "training",
                "title": "Training Frequency Drop",
                "detail": f"Only {recent_sessions} training session(s) in the last 14 days.",
                "intervention": (
                    "- If recovering from illness/injury, ease back with reduced volume\n"
                    "- If motivation is low, switch to shorter sessions (even 30 min counts)\n"
                    "- Consistency matters more than intensity — 3×/week minimum recommended"
                ),
            })

        # Volume declining over last 8 weeks
        weekly_vol = sorted_workouts.groupby("day")["volume"].sum().resample("W").sum()
        if len(weekly_vol) >= 8:
            first_4w = weekly_vol.iloc[-8:-4].mean()
            last_4w = weekly_vol.iloc[-4:].mean()
            if first_4w > 0 and last_4w < first_4w * 0.7:
                alerts.append({
                    "severity": "medium",
                    "category": "training",
                    "title": "Training Volume Declining",
                    "detail": f"Weekly volume dropped from ~{first_4w:,.0f} kg to ~{last_4w:,.0f} kg "
                              f"over the last 8 weeks ({(last_4w/first_4w - 1)*100:+.0f}%).",
                    "intervention": (
                        "- If intentional (deload), this is fine — plan to ramp back up\n"
                        "- If unintentional, review programming — are you progressing or stalling?\n"
                        "- Check recovery markers (sleep, readiness) — under-recovery limits training capacity"
                    ),
                })

        # Muscle group imbalance
        if "muscle_group" in sorted_workouts.columns:
            group_vol = sorted_workouts.groupby("muscle_group")["volume"].sum()
            group_vol = group_vol[group_vol > 0].sort_values(ascending=False)
            if len(group_vol) >= 4:
                # Check push/pull balance
                push_groups = ["chest", "shoulders", "triceps"]
                pull_groups = ["lats", "upper_back", "biceps"]
                push_vol = group_vol[group_vol.index.isin(push_groups)].sum()
                pull_vol = group_vol[group_vol.index.isin(pull_groups)].sum()
                if push_vol > 0 and pull_vol > 0:
                    ratio = push_vol / pull_vol
                    if ratio > 1.5:
                        alerts.append({
                            "severity": "medium",
                            "category": "training",
                            "title": "Push/Pull Imbalance",
                            "detail": f"Push volume is {ratio:.1f}× pull volume — ideally this should be close to 1:1.",
                            "intervention": (
                                "- Add more rowing and pulling movements (cable rows, face pulls, pull-ups)\n"
                                "- Aim for equal sets of horizontal push and pull per week\n"
                                "- Imbalance increases shoulder injury risk over time"
                            ),
                        })
                    elif ratio < 0.67:
                        alerts.append({
                            "severity": "medium",
                            "category": "training",
                            "title": "Pull-Dominant Imbalance",
                            "detail": f"Pull volume is {1/ratio:.1f}× push volume.",
                            "intervention": "- Add more pressing movements to balance the ratio\n- Ensure adequate chest and shoulder training",
                        })

                # Check lower vs upper
                lower_groups = ["quadriceps", "hamstrings", "glutes", "calves", "adductors", "abductors"]
                upper_groups = push_groups + pull_groups
                lower_vol = group_vol[group_vol.index.isin(lower_groups)].sum()
                upper_vol = group_vol[group_vol.index.isin(upper_groups)].sum()
                if upper_vol > 0 and lower_vol > 0:
                    ratio = upper_vol / lower_vol
                    if ratio > 2.0:
                        alerts.append({
                            "severity": "low",
                            "category": "training",
                            "title": "Upper-Body Dominant Training",
                            "detail": f"Upper body volume is {ratio:.1f}× lower body volume.",
                            "intervention": "- Consider adding a dedicated leg day or extra lower-body compounds\n- Squats, deadlifts, and lunges build a strong foundation",
                        })

                # Neglected muscle groups (< 3% of total volume)
                total_vol = group_vol.sum()
                neglected = [g for g, v in group_vol.items() if v / total_vol < 0.03 and g != "other"]
                if neglected:
                    alerts.append({
                        "severity": "low",
                        "category": "training",
                        "title": "Undertrained Muscle Groups",
                        "detail": f"These groups receive less than 3% of total volume: {', '.join(neglected)}.",
                        "intervention": f"- Add targeted accessory work for {', '.join(neglected)}\n- Even 2–3 sets per week can prevent imbalances",
                    })

    # ── Stress Alerts ──

    stress_df = datasets.get("stress", pd.DataFrame())
    if not stress_df.empty and "stress_high" in stress_df.columns:
        recent_stress = stress_df.sort_values("day").tail(14)
        avg_recent_stress = recent_stress["stress_high"].mean()
        if "recovery_high" in recent_stress.columns:
            avg_recent_recovery = recent_stress["recovery_high"].mean()
            if avg_recent_stress > 0 and avg_recent_recovery / avg_recent_stress < 0.5:
                alerts.append({
                    "severity": "medium",
                    "category": "sleep",
                    "title": "Low Recovery-to-Stress Ratio",
                    "detail": (f"Over the last 14 days, avg high recovery ({avg_recent_recovery:.0f} min) "
                               f"is less than half of avg high stress ({avg_recent_stress:.0f} min)."),
                    "intervention": (
                        "- Schedule deliberate recovery activities (walking, meditation, breathwork)\n"
                        "- Review sleep hygiene — recovery largely happens during sleep\n"
                        "- Consider reducing training intensity temporarily if readiness is also declining"
                    ),
                })

        stress_trend = _recent_trend(stress_df["stress_high"])
        if stress_trend is not None and stress_trend > 1.0:
            alerts.append({
                "severity": "medium",
                "category": "sleep",
                "title": "Stress Rapidly Increasing",
                "detail": f"High stress minutes trending sharply upward over the past 28 days (slope: +{stress_trend:.1f} min/day).",
                "intervention": (
                    "- Identify and address stressors (work, sleep debt, overtraining)\n"
                    "- Increase parasympathetic activity: deep breathing, cold exposure, nature walks\n"
                    "- Monitor HRV and readiness scores for downstream impact"
                ),
            })

    # ── Activity Alerts ──

    if not activity_df.empty:
        steps_col = next((c for c in ["steps", "total_steps"] if c in activity_df.columns), None)
        if steps_col:
            recent_steps = activity_df.sort_values("day").tail(14)
            avg_recent_steps = recent_steps[steps_col].mean()
            if avg_recent_steps < 5000:
                alerts.append({
                    "severity": "medium",
                    "category": "sleep",
                    "title": "Low Daily Movement",
                    "detail": f"Average steps over the last 14 days: {avg_recent_steps:,.0f} (below 5,000).",
                    "intervention": (
                        "- Set a daily step target and use hourly movement reminders\n"
                        "- Add a 10–15 min walk after meals (improves glucose regulation too)\n"
                        "- Low NEAT (non-exercise activity) limits fat loss regardless of gym training"
                    ),
                })

    # ── Cross-Source Alerts ──

    # Training load → poor recovery pattern
    if "training_volume_vs_recovery" in correlations:
        corr = correlations["training_volume_vs_recovery"].get("correlation")
        if corr is not None and corr < -0.3:
            alerts.append({
                "severity": "medium",
                "category": "correlations",
                "title": "Heavy Training Hurting Recovery",
                "detail": f"Strong negative correlation (r={corr:.2f}) between training volume and next-day readiness.",
                "intervention": (
                    "- Space heavy sessions 48+ hours apart\n"
                    "- Add a light recovery day (walking, mobility) after high-volume sessions\n"
                    "- Ensure post-workout nutrition (protein + carbs within 2 hours)"
                ),
            })

    # ── Combined-Metric Alerts ──

    # Overtraining vs Safe Deload: high volume + declining HRV + low readiness
    hrv_col = None
    if not readiness_df.empty:
        hrv_col = next((c for c in ["contributors.hrv_balance", "hrv_balance"] if c in readiness_df.columns), None)
    if not workouts_df.empty and hrv_col and not readiness_df.empty:
        recent_readiness = readiness_df.sort_values("day").tail(14)
        avg_readiness_14d = recent_readiness["score"].mean() if "score" in recent_readiness.columns else None
        hrv_slope = _recent_trend(readiness_df.sort_values("day")[hrv_col], window=14)

        sorted_workouts_2 = workouts_df.sort_values("day")
        recent_cutoff_2 = sorted_workouts_2["day"].max() - pd.Timedelta(days=14)
        recent_vol = sorted_workouts_2[sorted_workouts_2["day"] >= recent_cutoff_2]
        vol_per_session = recent_vol.groupby("day")["volume"].sum().mean() if not recent_vol.empty else 0

        if avg_readiness_14d and avg_readiness_14d < 65 and hrv_slope is not None and hrv_slope < -0.1 and vol_per_session > 0:
            alerts.append({
                "severity": "high",
                "category": "training",
                "title": "Overtraining Risk Detected",
                "detail": (
                    f"Low readiness ({avg_readiness_14d:.0f} avg), declining HRV, and maintained training volume "
                    f"({vol_per_session:,.0f} kg/session) — classic overtraining pattern."
                ),
                "intervention": (
                    "- Take an immediate deload: reduce volume by 50% for 5–7 days\n"
                    "- Prioritise sleep (8+ hours) and nutrition (maintenance calories, high protein)\n"
                    "- Add rest days between sessions — avoid back-to-back training\n"
                    "- Resume normal volume only when readiness returns above 70 and HRV stabilises"
                ),
            })
        elif avg_readiness_14d and avg_readiness_14d >= 70 and hrv_slope is not None and hrv_slope >= 0 and vol_per_session > 0:
            # Check if volume recently dropped (intentional deload) with good recovery markers
            prev_cutoff = sorted_workouts_2["day"].max() - pd.Timedelta(days=28)
            prev_vol = sorted_workouts_2[
                (sorted_workouts_2["day"] >= prev_cutoff) & (sorted_workouts_2["day"] < recent_cutoff_2)
            ]
            prev_vol_avg = prev_vol.groupby("day")["volume"].sum().mean() if not prev_vol.empty else 0
            if prev_vol_avg > 0 and vol_per_session < prev_vol_avg * 0.7:
                alerts.append({
                    "severity": "positive",
                    "category": "training",
                    "title": "Effective Deload in Progress",
                    "detail": (
                        f"Volume reduced ({vol_per_session:,.0f} vs {prev_vol_avg:,.0f} kg/session) while "
                        f"readiness ({avg_readiness_14d:.0f}) and HRV are healthy — recovery is working."
                    ),
                    "intervention": (
                        "- Continue the deload for the planned duration (typically 5–7 days)\n"
                        "- Ramp volume back up gradually (80% → 100% over 1–2 weeks)"
                    ),
                })

    # High protein + high training volume + good sleep = growth conditions
    if not nutrition_df.empty and not workouts_df.empty and not sleep_df.empty:
        logged_nutr = nutrition_df[nutrition_df["calories"] > 0] if "calories" in nutrition_df.columns else pd.DataFrame()
        if not logged_nutr.empty and "protein" in logged_nutr.columns:
            recent_protein = logged_nutr.sort_values("day").tail(14)["protein"].mean()
            recent_sleep_avg = sleep_df.sort_values("day").tail(14)["score"].mean() if "score" in sleep_df.columns else 0
            recent_train_days = workouts_df.sort_values("day").tail(14)["day"].nunique() if not workouts_df.empty else 0
            latest_weight = None
            if not body_df.empty and "weight_kg" in body_df.columns:
                latest_weight = float(body_df.sort_values("day").iloc[-1]["weight_kg"])
            protein_per_kg = recent_protein / latest_weight if latest_weight else 0

            if protein_per_kg >= 1.6 and recent_sleep_avg >= 75 and recent_train_days >= 3:
                alerts.append({
                    "severity": "positive",
                    "category": "training",
                    "title": "Optimal Growth Conditions",
                    "detail": (
                        f"Protein intake ({protein_per_kg:.1f} g/kg), sleep quality ({recent_sleep_avg:.0f}), "
                        f"and training frequency ({recent_train_days} sessions/14d) are all in the growth zone."
                    ),
                    "intervention": (
                        "- Maintain current approach — this is the formula for muscle gain\n"
                        "- Focus on progressive overload to capitalise on recovery capacity"
                    ),
                })

    # ── Sleep Pattern Alerts ──

    if not sleep_df.empty:
        sorted_sleep = sleep_df.sort_values("day")

        # Sleep latency increasing
        if "contributors.latency" in sorted_sleep.columns:
            latency_slope = _recent_trend(sorted_sleep["contributors.latency"], window=28)
            if latency_slope is not None and latency_slope < -0.2:
                alerts.append({
                    "severity": "medium",
                    "category": "sleep",
                    "title": "Sleep Latency Worsening",
                    "detail": "Sleep latency contributor score is declining — you may be taking longer to fall asleep.",
                    "intervention": (
                        "- Avoid stimulants (caffeine, intense exercise) within 4 hours of bedtime\n"
                        "- Establish a wind-down routine: dim lights, no screens 30–60 min before bed\n"
                        "- Try relaxation techniques (4-7-8 breathing, progressive muscle relaxation)\n"
                        "- Keep a consistent bedtime — irregular schedules worsen latency"
                    ),
                })

        # Sleep efficiency declining
        if "contributors.efficiency" in sorted_sleep.columns:
            eff_slope = _recent_trend(sorted_sleep["contributors.efficiency"], window=28)
            if eff_slope is not None and eff_slope < -0.2:
                alerts.append({
                    "severity": "medium",
                    "category": "sleep",
                    "title": "Sleep Efficiency Declining",
                    "detail": "Sleep efficiency contributor score is trending down — more time in bed is spent awake.",
                    "intervention": (
                        "- Only go to bed when truly sleepy — avoid lying awake in bed\n"
                        "- Keep the bedroom exclusively for sleep (no work, no scrolling)\n"
                        "- Maintain a cool, dark environment (18–19°C, blackout curtains)\n"
                        "- Avoid alcohol before bed — it fragments sleep despite feeling sedating"
                    ),
                })

        # Deep sleep % low
        if "deep_sleep_duration" in sorted_sleep.columns and "total_sleep_duration" in sorted_sleep.columns:
            recent = sorted_sleep.tail(14)
            total = recent["total_sleep_duration"].sum()
            deep = recent["deep_sleep_duration"].sum()
            if total > 0:
                deep_pct = deep / total * 100
                if deep_pct < 15:
                    alerts.append({
                        "severity": "medium",
                        "category": "sleep",
                        "title": "Low Deep Sleep Percentage",
                        "detail": f"Deep sleep is {deep_pct:.0f}% of total sleep over the last 14 nights (target: 20–25%).",
                        "intervention": (
                            "- Exercise regularly (but not within 3 hours of bedtime)\n"
                            "- Avoid alcohol — it significantly reduces deep sleep\n"
                            "- Keep a cool bedroom — cooler temperatures promote deep sleep\n"
                            "- Consider magnesium supplementation (supports slow-wave sleep)"
                        ),
                    })

        # Sleep regularity — check bedtime variance via timestamp
        if "timestamp" in sorted_sleep.columns:
            recent = sorted_sleep.tail(14)
            timestamps = pd.to_datetime(recent["timestamp"], errors="coerce").dropna()
            if len(timestamps) >= 7:
                bedtimes_hour = timestamps.dt.hour + timestamps.dt.minute / 60
                # Handle wrap-around midnight (e.g. 23:00 and 01:00 should be close)
                bedtimes_adj = bedtimes_hour.copy()
                bedtimes_adj[bedtimes_adj < 12] += 24  # Shift early AM times
                spread = bedtimes_adj.max() - bedtimes_adj.min()
                if spread > 2.0:
                    alerts.append({
                        "severity": "low",
                        "category": "sleep",
                        "title": "Irregular Sleep Schedule",
                        "detail": f"Bedtime varies by {spread:.1f} hours over the last 14 nights (>2 hour spread).",
                        "intervention": (
                            "- Set a consistent bedtime and wake time — even on weekends\n"
                            "- Irregular schedules disrupt circadian rhythm and reduce sleep quality\n"
                            "- Use an alarm for bedtime, not just wake-up"
                        ),
                    })

    # Breathing disturbances (from SpO2 data)
    if not spo2_df.empty and "breathing_disturbance_index" in spo2_df.columns:
        recent_spo2 = spo2_df.sort_values("day").tail(14)
        bdi_vals = recent_spo2["breathing_disturbance_index"].dropna()
        if len(bdi_vals) >= 3:
            avg_bdi = bdi_vals.mean()
            if avg_bdi > 10:
                alerts.append({
                    "severity": "high",
                    "category": "sleep",
                    "title": "Elevated Breathing Disturbances",
                    "detail": f"Average breathing disturbance index is {avg_bdi:.1f} over the last 14 nights (elevated >10).",
                    "intervention": (
                        "- Avoid sleeping on your back — try side sleeping\n"
                        "- Avoid alcohol and sedatives before bed\n"
                        "- If persistent, consult a sleep specialist — this may indicate sleep apnea\n"
                        "- Elevated BDI impairs deep sleep and next-day recovery"
                    ),
                })
            elif avg_bdi > 5:
                alerts.append({
                    "severity": "low",
                    "category": "sleep",
                    "title": "Mild Breathing Disturbances",
                    "detail": f"Average breathing disturbance index is {avg_bdi:.1f} — slightly elevated.",
                    "intervention": (
                        "- Monitor the trend — occasional mild disturbances can be normal\n"
                        "- Try elevating your head slightly and avoiding back sleeping\n"
                        "- Nasal congestion or allergies may contribute — address if applicable"
                    ),
                })

    # ── Additional Activity Alerts ──

    if not activity_df.empty:
        sorted_activity = activity_df.sort_values("day")

        # Sedentary >8 hours/day
        if "sedentary_time" in sorted_activity.columns:
            recent = sorted_activity.tail(14)
            avg_sedentary_hrs = recent["sedentary_time"].mean() / 3600
            if avg_sedentary_hrs > 8:
                high_days = (recent["sedentary_time"] > 8 * 3600).sum()
                alerts.append({
                    "severity": "medium",
                    "category": "activity",
                    "title": "Excessive Sedentary Time",
                    "detail": f"Average sedentary time is {avg_sedentary_hrs:.1f} hrs/day over the last 14 days "
                              f"({high_days} days above 8 hours).",
                    "intervention": (
                        "- Set hourly movement reminders — stand and walk for 2–5 minutes each hour\n"
                        "- Take walking meetings or phone calls\n"
                        "- Consider a standing desk for part of the workday\n"
                        "- Prolonged sedentary time increases cardiovascular risk independent of exercise"
                    ),
                })

        # Steps declining for 2+ weeks
        steps_col = next((c for c in ["steps", "total_steps"] if c in sorted_activity.columns), None)
        if steps_col and len(sorted_activity) >= 28:
            first_14 = sorted_activity.tail(28).head(14)[steps_col].mean()
            last_14 = sorted_activity.tail(14)[steps_col].mean()
            if first_14 > 0 and last_14 < first_14 * 0.8:
                alerts.append({
                    "severity": "low",
                    "category": "activity",
                    "title": "Steps Declining",
                    "detail": f"Average steps dropped from {first_14:,.0f} to {last_14:,.0f} "
                              f"over the last 2 weeks ({(last_14/first_14 - 1)*100:+.0f}%).",
                    "intervention": (
                        "- Identify the cause — weather, schedule change, injury?\n"
                        "- Set a minimum daily step target to maintain baseline activity\n"
                        "- Even a short daily walk preserves NEAT and metabolic health"
                    ),
                })

        # Low activity intensity (mostly sedentary, not enough high/medium)
        if ("high_activity_time" in sorted_activity.columns
                and "medium_activity_time" in sorted_activity.columns
                and "sedentary_time" in sorted_activity.columns):
            recent = sorted_activity.tail(14)
            avg_high = recent["high_activity_time"].mean()
            avg_medium = recent["medium_activity_time"].mean()
            avg_sedentary = recent["sedentary_time"].mean()
            active_time = avg_high + avg_medium
            if avg_sedentary > 0 and active_time / avg_sedentary < 0.05:
                alerts.append({
                    "severity": "low",
                    "category": "activity",
                    "title": "Low Activity Intensity",
                    "detail": (f"High+medium activity averages {active_time/60:.0f} min/day vs "
                               f"{avg_sedentary/3600:.1f} hrs sedentary — very little vigorous movement."),
                    "intervention": (
                        "- Add short bursts of higher-intensity movement throughout the day\n"
                        "- Even 10 minutes of brisk walking or stair climbing counts as medium activity\n"
                        "- Health guidelines recommend 150+ min/week of moderate or 75+ min/week of vigorous activity"
                    ),
                })

    # ── Additional Training Alerts ──

    if not workouts_df.empty:
        sorted_wk = workouts_df.sort_values("day")

        # Training volume plateaued — no progressive overload for 4+ weeks
        if "volume" in sorted_wk.columns:
            daily_vol = sorted_wk.groupby("day")["volume"].sum()
            if len(daily_vol) >= 28:
                weekly_vol = daily_vol.resample("W").sum()
                if len(weekly_vol) >= 4:
                    last_4w = weekly_vol.tail(4)
                    vol_slope = _recent_trend(last_4w, window=len(last_4w))
                    vol_cv = last_4w.std() / last_4w.mean() if last_4w.mean() > 0 else 0
                    if vol_slope is not None and abs(vol_slope) < 50 and vol_cv < 0.1 and last_4w.mean() > 0:
                        alerts.append({
                            "severity": "low",
                            "category": "training",
                            "title": "Training Volume Plateaued",
                            "detail": f"Weekly volume has been flat (~{last_4w.mean():,.0f} kg/week) for 4+ weeks "
                                      f"with minimal variation (CV={vol_cv:.0%}).",
                            "intervention": (
                                "- Progressive overload is key — aim to increase volume by 5–10% per week\n"
                                "- Add reps, weight, or sets incrementally\n"
                                "- If intentionally maintaining, ensure it aligns with your goals\n"
                                "- Consider periodisation: accumulation → intensification → deload"
                            ),
                        })

        # Exercise stagnation — same exercises for 2+ months
        if "exercise" in sorted_wk.columns:
            cutoff_recent = sorted_wk["day"].max() - pd.Timedelta(days=28)
            cutoff_older = cutoff_recent - pd.Timedelta(days=28)
            recent_exercises = set(sorted_wk[sorted_wk["day"] >= cutoff_recent]["exercise"].unique())
            older_exercises = set(
                sorted_wk[(sorted_wk["day"] >= cutoff_older) & (sorted_wk["day"] < cutoff_recent)]["exercise"].unique()
            )
            if recent_exercises and older_exercises:
                overlap = recent_exercises & older_exercises
                if len(recent_exercises) > 0 and len(overlap) / len(recent_exercises) > 0.9 and len(recent_exercises) >= 5:
                    alerts.append({
                        "severity": "low",
                        "category": "training",
                        "title": "Exercise Selection Stagnation",
                        "detail": (f"{len(overlap)}/{len(recent_exercises)} exercises are identical to the previous month "
                                   f"— limited exercise variety."),
                        "intervention": (
                            "- Rotate accessory exercises every 4–6 weeks to provide novel stimulus\n"
                            "- Keep compound lifts but vary grips, stances, and tempos\n"
                            "- New movement patterns can break plateaus and reduce overuse injury risk"
                        ),
                    })

    # ── Nutrition Alerts ──

    if not nutrition_df.empty and "calories" in nutrition_df.columns:
        logged_nutr = nutrition_df[nutrition_df["calories"] > 0].sort_values("day")

        # Caloric deficit too aggressive (>500 kcal/day)
        if not logged_nutr.empty:
            bmr_val = None
            if not body_df.empty and "bmr" in body_df.columns:
                bmr_val = float(body_df.sort_values("day").iloc[-1]["bmr"])
            active_cal_col = None
            if not activity_df.empty:
                active_cal_col = next((c for c in ["active_calories"] if c in activity_df.columns), None)
            if bmr_val and active_cal_col:
                nut = logged_nutr[["day", "calories"]].tail(14).copy()
                act = activity_df[["day", active_cal_col]].copy()
                merged = nut.merge(act, on="day", how="inner")
                if not merged.empty:
                    merged["deficit"] = merged["calories"] - (bmr_val + merged[active_cal_col])
                    avg_deficit = merged["deficit"].mean()
                    if avg_deficit < -500:
                        alerts.append({
                            "severity": "high",
                            "category": "nutrition",
                            "title": "Aggressive Caloric Deficit",
                            "detail": f"Average daily deficit is {avg_deficit:,.0f} kcal over the last 14 days "
                                      f"(>500 kcal deficit risks lean mass loss).",
                            "intervention": (
                                "- Reduce deficit to 300–500 kcal/day to preserve muscle mass\n"
                                "- Ensure protein intake is at least 2.0 g/kg during a cut\n"
                                "- Aggressive deficits increase cortisol and impair recovery\n"
                                "- Consider diet breaks (2 weeks at maintenance) every 6–8 weeks"
                            ),
                        })

        # Micronutrient gaps
        micro_checks = [
            ("calcium", "Calcium", 800, "mg", "- Add dairy, fortified foods, or leafy greens\n- Consider supplementation if consistently low"),
            ("vitamin_c", "Vitamin C", 60, "%DV", "- Eat more citrus fruits, peppers, and berries\n- Vitamin C supports immune function and collagen synthesis"),
            ("iron", "Iron", 80, "%DV", "- Include iron-rich foods: red meat, lentils, spinach\n- Pair with vitamin C for better absorption"),
        ]
        for col, name, threshold, unit, fix in micro_checks:
            if col in logged_nutr.columns:
                recent_vals = logged_nutr[col].tail(14).dropna()
                if len(recent_vals) >= 7:
                    avg_val = recent_vals.mean()
                    low_days = (recent_vals < threshold).sum()
                    if low_days >= 10:
                        alerts.append({
                            "severity": "medium",
                            "category": "nutrition",
                            "title": f"Low {name} Intake",
                            "detail": f"{name} is below {threshold} {unit} on {low_days}/14 recent logged days "
                                      f"(average: {avg_val:.0f}).",
                            "intervention": fix,
                        })

    # ── Additional Body Composition Alerts ──

    if not body_df.empty and len(body_df) >= 2:
        sorted_body = body_df.sort_values("day")

        # Segmental muscle asymmetry >5%
        limb_pairs = [
            ("left_arm_muscle_kg", "right_arm_muscle_kg", "Arm"),
            ("left_leg_muscle_kg", "right_leg_muscle_kg", "Leg"),
        ]
        for left_col, right_col, limb_name in limb_pairs:
            if left_col in sorted_body.columns and right_col in sorted_body.columns:
                latest = sorted_body.iloc[-1]
                left_val = latest[left_col]
                right_val = latest[right_col]
                if pd.notna(left_val) and pd.notna(right_val) and max(left_val, right_val) > 0:
                    avg_val = (left_val + right_val) / 2
                    diff_pct = abs(left_val - right_val) / avg_val * 100
                    if diff_pct > 5:
                        weaker = "left" if left_val < right_val else "right"
                        alerts.append({
                            "severity": "medium",
                            "category": "body",
                            "title": f"{limb_name} Muscle Asymmetry",
                            "detail": f"{limb_name} muscle imbalance: L={left_val:.2f} kg, R={right_val:.2f} kg "
                                      f"({diff_pct:.1f}% difference, {weaker} side weaker).",
                            "intervention": (
                                f"- Add unilateral exercises targeting the {weaker} {limb_name.lower()}\n"
                                f"- Start sets with the weaker side and match reps on the stronger side\n"
                                "- >5% asymmetry increases injury risk — address proactively"
                            ),
                        })

        # BMR declining despite stable weight (possible muscle loss)
        if "bmr" in sorted_body.columns and "weight_kg" in sorted_body.columns and len(sorted_body) >= 3:
            recent = sorted_body.tail(4)
            weight_change = abs(recent["weight_kg"].iloc[-1] - recent["weight_kg"].iloc[0])
            bmr_change = recent["bmr"].iloc[-1] - recent["bmr"].iloc[0]
            if weight_change < 1.0 and bmr_change < -30:
                alerts.append({
                    "severity": "medium",
                    "category": "body",
                    "title": "BMR Declining (Stable Weight)",
                    "detail": f"BMR dropped by {bmr_change:+.0f} kcal while weight stayed within 1 kg — "
                              f"possible shift from muscle to fat.",
                    "intervention": (
                        "- Review body composition trends — is muscle mass declining?\n"
                        "- Increase resistance training volume and protein intake\n"
                        "- BMR decline at stable weight suggests unfavourable body composition shift"
                    ),
                })

        # Metabolic age increasing
        if "metabolic_age" in sorted_body.columns and len(sorted_body) >= 3:
            recent = sorted_body.tail(4)
            met_age_vals = recent["metabolic_age"].dropna()
            if len(met_age_vals) >= 2:
                met_age_change = met_age_vals.iloc[-1] - met_age_vals.iloc[0]
                if met_age_change > 1:
                    alerts.append({
                        "severity": "low",
                        "category": "body",
                        "title": "Metabolic Age Increasing",
                        "detail": f"Metabolic age has increased by {met_age_change:.0f} year(s) "
                                  f"over recent scans (now {met_age_vals.iloc[-1]:.0f}).",
                        "intervention": (
                            "- Increase lean muscle mass through progressive resistance training\n"
                            "- Reduce body fat percentage — this is the primary driver of metabolic age\n"
                            "- Metabolic age reflects body composition relative to chronological age"
                        ),
                    })

        # Phase angle declining
        phase_cols = [c for c in sorted_body.columns if c.startswith("phase_angle_")]
        if phase_cols and len(sorted_body) >= 3:
            # Average phase angle across available limbs
            recent = sorted_body.tail(4)
            avg_phase = recent[phase_cols].mean(axis=1)
            if len(avg_phase.dropna()) >= 2:
                phase_change = avg_phase.dropna().iloc[-1] - avg_phase.dropna().iloc[0]
                if phase_change < -0.3:
                    alerts.append({
                        "severity": "medium",
                        "category": "body",
                        "title": "Phase Angle Declining",
                        "detail": f"Average phase angle decreased by {phase_change:+.1f}° over recent scans "
                                  f"(now {avg_phase.dropna().iloc[-1]:.1f}°).",
                        "intervention": (
                            "- Phase angle reflects cellular health and muscle quality\n"
                            "- Ensure adequate protein (1.6–2.2 g/kg) and hydration\n"
                            "- Maintain consistent resistance training\n"
                            "- If persistently declining, review overall nutrition and recovery"
                        ),
                    })

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2, "positive": 3}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 99))

    return alerts


def _alerts_section(datasets: dict[str, pd.DataFrame], correlations: dict[str, Any]) -> str:
    """Generate alerts markdown section."""
    lines = ["## Alerts & Interventions", ""]
    alerts = compute_alerts(datasets, correlations)

    if not alerts:
        lines.append("No alerts to report — all metrics are within healthy ranges.\n")
        return "\n".join(lines)

    severity_icons = {"high": "🔴", "medium": "🟡", "low": "🔵", "positive": "🟢"}

    for alert in alerts:
        icon = severity_icons.get(alert["severity"], "⚪")
        lines.append(f"### {icon} {alert['title']}\n")
        lines.append(f"{alert['detail']}\n")
        lines.append(f"**Recommended actions:**\n")
        lines.append(alert["intervention"])
        lines.append("")

    counts: dict[str, int] = {}
    for alert in alerts:
        counts[alert["severity"]] = counts.get(alert["severity"], 0) + 1
    summary_parts = []
    for sev in ["high", "medium", "low", "positive"]:
        if sev in counts:
            summary_parts.append(f"{severity_icons[sev]} {counts[sev]} {sev}")
    lines.append(f"*Alert summary: {' | '.join(summary_parts)}*\n")

    return "\n".join(lines)


# ── Summary Section ──

def _summary_section(datasets: dict[str, pd.DataFrame], correlations: dict[str, Any]) -> str:
    lines = ["## Summary — Top Observations", ""]
    observations: list[str] = []

    # Sleep insight
    sleep_df = datasets.get("sleep", pd.DataFrame())
    if not sleep_df.empty and "score" in sleep_df.columns:
        avg = sleep_df["score"].mean()
        if avg >= 85:
            observations.append(f"Sleep quality is excellent (avg score {avg:.0f}) — a strong foundation for recovery.")
        elif avg >= 70:
            observations.append(f"Sleep quality is good (avg score {avg:.0f}) — room for improvement on consistency.")
        else:
            observations.append(f"Sleep quality needs attention (avg score {avg:.0f}) — this may be limiting recovery.")

    # Training insight
    workouts_df = datasets.get("workouts", pd.DataFrame())
    if not workouts_df.empty:
        sessions = workouts_df["day"].nunique()
        date_range = (workouts_df["day"].max() - workouts_df["day"].min()).days
        if date_range > 0:
            freq = sessions / (date_range / 7)
            observations.append(f"Training frequency averages {freq:.1f} sessions/week across {sessions} total sessions.")

    # Nutrition insight
    nutr_df = datasets.get("nutrition", pd.DataFrame())
    if not nutr_df.empty and "calories" in nutr_df.columns:
        logged = nutr_df[nutr_df["calories"] > 0]
        compliance = len(logged) / len(nutr_df) * 100
        if compliance < 70:
            observations.append(f"Nutrition tracking compliance is {compliance:.0f}% — more consistent logging would improve insights.")

    # Correlation insights
    for key, label in [("sleep_vs_readiness", "sleep-readiness"), ("protein_vs_recovery", "protein-recovery")]:
        if key in correlations:
            corr = correlations[key].get("correlation")
            if corr is not None and abs(corr) > 0.3:
                observations.append(f"Notable {label} correlation (r={corr:.2f}) — worth monitoring.")

    # Body comp insight
    body_df = datasets.get("body_composition", pd.DataFrame())
    if not body_df.empty and len(body_df) >= 2:
        first = body_df.sort_values("day").iloc[0]
        last = body_df.sort_values("day").iloc[-1]
        if "muscle_mass_kg" in body_df.columns:
            delta = last["muscle_mass_kg"] - first["muscle_mass_kg"]
            observations.append(f"Muscle mass change: {delta:+.1f} kg over the period.")

    if not observations:
        observations.append("Add more data sources to unlock cross-source insights.")

    for idx, obs in enumerate(observations[:5], 1):
        lines.append(f"{idx}. {obs}")
    lines.append("")

    return "\n".join(lines)


# ── Main Generator ──

def generate_report(
    start_date: str,
    end_date: str,
    datasets: dict[str, pd.DataFrame],
    correlations: dict[str, Any],
    output_dir: Path,
) -> Path:
    """Generate a full multi-source markdown health report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_date = datetime.now().strftime("%Y-%m-%d")
    report_path = output_dir / f"health_report_{report_date}.md"

    sections: list[str] = []

    # Header
    sections.append("# Unified Health Intelligence Report\n")
    sections.append(f"**Date range:** {start_date} to {end_date}  ")
    sections.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ")

    available = [name for name, df in datasets.items() if not df.empty]
    total_records = sum(len(df) for df in datasets.values())
    sections.append(f"**Data sources active:** {', '.join(available) if available else 'none'}  ")
    sections.append(f"**Total records analysed:** {total_records:,}\n")
    sections.append("---\n")

    # Sections in spec order
    sections.append(_bloodwork_section(datasets))
    sections.append("---\n")
    sections.append(_nutrition_section(datasets))
    sections.append("---\n")
    sections.append(_sleep_recovery_section(datasets))
    sections.append("---\n")
    sections.append(_stress_section(datasets))
    sections.append("---\n")
    sections.append(_training_section(datasets))
    sections.append("---\n")
    sections.append(_body_composition_section(datasets))
    sections.append("---\n")
    sections.append(_activity_section(datasets))
    sections.append("---\n")
    sections.append(_heartrate_section(datasets))
    sections.append("---\n")
    sections.append(_spo2_section(datasets))
    sections.append("---\n")
    sections.append(_correlations_section(correlations))
    sections.append("---\n")
    sections.append(_alerts_section(datasets, correlations))
    sections.append("---\n")
    sections.append(_summary_section(datasets, correlations))

    report_path.write_text("\n".join(sections), encoding="utf-8")
    logger.info("Report generated: %s", report_path)
    return report_path
