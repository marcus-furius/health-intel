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
    """Compute structured alerts from datasets and correlations based on Dashboard Business Rules.

    Returns a list of dicts, each with keys: severity, title, detail, intervention.
    Sorted by severity (critical → high → medium → low → positive).
    """
    alerts: list[dict[str, str]] = []

    sleep_df = datasets.get("sleep", pd.DataFrame())
    readiness_df = datasets.get("readiness", pd.DataFrame())
    activity_df = datasets.get("activity", pd.DataFrame())
    workouts_df = datasets.get("workouts", pd.DataFrame())
    body_df = datasets.get("body_composition", pd.DataFrame())
    nutrition_df = datasets.get("nutrition", pd.DataFrame())
    spo2_df = datasets.get("spo2", pd.DataFrame())
    bloodwork_df = datasets.get("bloodwork", pd.DataFrame())
    mfp_weight_df = datasets.get("mfp_weight", pd.DataFrame())

    # ── Domain 1 & 2: Blood Work (Hormonal & TRT Safety) ──

    if not bloodwork_df.empty:
        latest = bloodwork_df.sort_values("day").iloc[-1]
        
        # BR-H01 | Total Testosterone
        if "testosterone_nmol" in latest and pd.notna(latest["testosterone_nmol"]):
            val = latest["testosterone_nmol"]
            if val < 12:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Critical Low Testosterone",
                    "detail": f"Total Testosterone is {val:.1f} nmol/L (BR-H01 < 12).",
                    "intervention": "Contact Manual clinic immediately."
                })
            elif val < 15:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "Low Testosterone",
                    "detail": f"Total Testosterone is {val:.1f} nmol/L (BR-H01 12–14.9).",
                    "intervention": "Contact Manual clinic — discuss dose adjustment."
                })
            elif val < 20:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Suboptimal Testosterone",
                    "detail": f"Total Testosterone is {val:.1f} nmol/L (BR-H01 15–19.9).",
                    "intervention": "Review timing of blood draw; confirm pre-injection trough sample."
                })

        # BR-H02 | Free Testosterone
        if "free_testosterone_nmol" in latest and pd.notna(latest["free_testosterone_nmol"]):
            val = latest["free_testosterone_nmol"]
            if val < 0.30:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Critical Low Free T",
                    "detail": f"Free Testosterone is {val:.3f} nmol/L (BR-H02 < 0.30).",
                    "intervention": "Clinical review required."
                })
            elif val < 0.40:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "Low Free Testosterone",
                    "detail": f"Free Testosterone is {val:.3f} nmol/L (BR-H02 0.30–0.39).",
                    "intervention": "Review SHBG, dose timing, discuss with clinic."
                })
            elif val <= 0.50:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Suboptimal Free Testosterone",
                    "detail": f"Free Testosterone is {val:.3f} nmol/L (BR-H02 0.40–0.50).",
                    "intervention": "Check SHBG trend; consider boron optimisation."
                })

        # BR-H03 | Oestradiol (E2)
        if "oestradiol_pmol" in latest and pd.notna(latest["oestradiol_pmol"]):
            val = latest["oestradiol_pmol"]
            if val < 75:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "Low Oestradiol",
                    "detail": f"Oestradiol is {val:.1f} pmol/L (BR-H03 < 75).",
                    "intervention": "Risk: joint pain, low libido, mood depression — clinical review."
                })
            elif val > 200:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "High Oestradiol",
                    "detail": f"Oestradiol is {val:.1f} pmol/L (BR-H03 > 200).",
                    "intervention": "Risk: gynecomastia, water retention — clinical review."
                })
            elif val < 100:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Suboptimal Oestradiol",
                    "detail": f"Oestradiol is {val:.1f} pmol/L (BR-H03 75–99).",
                    "intervention": "Monitor libido, joint comfort, mood; may be suboptimal."
                })
            elif val > 150:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Elevated Oestradiol",
                    "detail": f"Oestradiol is {val:.1f} pmol/L (BR-H03 150–200).",
                    "intervention": "Watch for bloating, nipple sensitivity, mood changes."
                })

        # BR-H04 | SHBG
        if "shbg_nmol" in latest and pd.notna(latest["shbg_nmol"]):
            val = latest["shbg_nmol"]
            if val > 40:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "High SHBG",
                    "detail": f"SHBG is {val:.1f} nmol/L (BR-H04 > 40).",
                    "intervention": "Clinical review; high SHBG binding excess testosterone."
                })
            elif val > 30:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Elevated SHBG",
                    "detail": f"SHBG is {val:.1f} nmol/L (BR-H04 30–40).",
                    "intervention": "Consider boron 6–10mg/day; recheck in 6–8 weeks."
                })
            elif val < 18:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Low SHBG",
                    "detail": f"SHBG is {val:.1f} nmol/L (BR-H04 < 18).",
                    "intervention": "Monitor — very low SHBG can indicate insulin resistance."
                })

        # BR-H05 | Prolactin
        if "prolactin_miu" in latest and pd.notna(latest["prolactin_miu"]):
            val = latest["prolactin_miu"]
            if val > 350:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Critical High Prolactin",
                    "detail": f"Prolactin is {val:.1f} mIU/L (BR-H05 > 350).",
                    "intervention": "Rule out prolactinoma — urgent GP/endocrinology referral."
                })
            elif val > 200:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "High Prolactin",
                    "detail": f"Prolactin is {val:.1f} mIU/L (BR-H05 200–350).",
                    "intervention": "Clinical review — elevated prolactin suppresses libido and testosterone effect."
                })
            elif val > 100:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Elevated Prolactin",
                    "detail": f"Prolactin is {val:.1f} mIU/L (BR-H05 100–200).",
                    "intervention": "Monitor libido and sexual function; recheck in 3 months."
                })

        # BR-S01 | PSA
        if "psa_ug" in latest and pd.notna(latest["psa_ug"]):
            val = latest["psa_ug"]
            if val > 3.5:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Critical PSA",
                    "detail": f"PSA is {val:.2f} µg/l (BR-S01 > 3.5).",
                    "intervention": "Stop TRT protocol adjustment; urgent urology referral."
                })
            elif val > 2.5:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "High PSA",
                    "detail": f"PSA is {val:.2f} µg/l (BR-S01 2.5–3.5).",
                    "intervention": "Increase to 3-monthly monitoring; clinical review."
                })
            elif val >= 1.5:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Elevated PSA",
                    "detail": f"PSA is {val:.2f} µg/l (BR-S01 1.5–2.5).",
                    "intervention": "Continue 6-monthly; track velocity closely."
                })

        # BR-S02 | Haematocrit
        if "haematocrit_pct" in latest and pd.notna(latest["haematocrit_pct"]):
            val = latest["haematocrit_pct"]
            if val > 50:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Critical Haematocrit",
                    "detail": f"Haematocrit is {val:.1f}% (BR-S02 > 50%).",
                    "intervention": "Pause TRT; urgent clinical review; consider therapeutic phlebotomy."
                })
            elif val >= 48:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "High Haematocrit",
                    "detail": f"Haematocrit is {val:.1f}% (BR-S02 48–50%).",
                    "intervention": "Hold dose increase; discuss venesection with clinic."
                })
            elif val >= 46:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Elevated Haematocrit",
                    "detail": f"Haematocrit is {val:.1f}% (BR-S02 46–48%).",
                    "intervention": "Optimise hydration; increase water intake to 4L/day."
                })

        # BR-S03 | Haemoglobin
        if "haemoglobin_g" in latest and pd.notna(latest["haemoglobin_g"]):
            val = latest["haemoglobin_g"]
            if val > 170:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Critical Haemoglobin",
                    "detail": f"Haemoglobin is {val:.0f} g/L (BR-S03 > 170).",
                    "intervention": "Urgent review; cardiovascular risk elevated."
                })
            elif val > 165:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "High Haemoglobin",
                    "detail": f"Haemoglobin is {val:.0f} g/L (BR-S03 165–170).",
                    "intervention": "Clinical review."
                })
            elif val >= 155:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Elevated Haemoglobin",
                    "detail": f"Haemoglobin is {val:.0f} g/L (BR-S03 155–165).",
                    "intervention": "Monitor with haematocrit."
                })

        # BR-S04 | eGFR
        if "egfr_ml" in latest and pd.notna(latest["egfr_ml"]):
            val = latest["egfr_ml"]
            if val < 45:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Critical Low eGFR",
                    "detail": f"eGFR is {val:.1f} ml/min (BR-S04 < 45).",
                    "intervention": "Urgent nephrology review; suspend high protein protocol."
                })
            elif val < 60:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "Low eGFR",
                    "detail": f"eGFR is {val:.1f} ml/min (BR-S04 45–60).",
                    "intervention": "Reduce protein to 1.8g/kg; clinical review."
                })
            elif val <= 90:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Suboptimal eGFR",
                    "detail": f"eGFR is {val:.1f} ml/min (BR-S04 60–90).",
                    "intervention": "Monitor protein intake; check creatinine trend."
                })

        # BR-C02 & C03 | HDL & Ratio
        if "hdl_mmol" in latest and pd.notna(latest["hdl_mmol"]):
            hdl = latest["hdl_mmol"]
            if hdl < 0.9:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Critical Low HDL",
                    "detail": f"HDL is {hdl:.2f} mmol/L (BR-C03 < 0.9).",
                    "intervention": "Clinical review; dose increase on hold until improved."
                })
            elif hdl <= 1.0:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "Low HDL",
                    "detail": f"HDL is {hdl:.2f} mmol/L (BR-C03 0.9–1.0).",
                    "intervention": "Structured aerobic work 3x/week; review TRT dose."
                })
            elif hdl <= 1.2:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Suboptimal HDL",
                    "detail": f"HDL is {hdl:.2f} mmol/L (BR-C03 1.0–1.2).",
                    "intervention": "Increase aerobic activity; omega-3 3g/day."
                })

        if "cholesterol_hdl_ratio" in latest and pd.notna(latest["cholesterol_hdl_ratio"]):
            ratio = latest["cholesterol_hdl_ratio"]
            if ratio > 5.0:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Critical Chol/HDL Ratio",
                    "detail": f"Chol/HDL ratio is {ratio:.2f} (BR-C02 > 5.0).",
                    "intervention": "Urgent cardiovascular risk assessment."
                })
            elif ratio >= 4.0:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "High Chol/HDL Ratio",
                    "detail": f"Chol/HDL ratio is {ratio:.2f} (BR-C02 4.0–5.0).",
                    "intervention": "Clinical review; dietary intervention."
                })
            elif ratio >= 3.5:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Suboptimal Chol/HDL Ratio",
                    "detail": f"Chol/HDL ratio is {ratio:.2f} (BR-C02 3.5–4.0).",
                    "intervention": "Target HDL improvement — increase omega-3 to 3g EPA/DHA."
                })

        # BR-C04 | HbA1c
        if "hba1c_mmol" in latest and pd.notna(latest["hba1c_mmol"]):
            val = latest["hba1c_mmol"]
            if val >= 48:
                alerts.append({
                    "severity": "critical", "category": "bloodwork", "title": "Diabetic Range HbA1c",
                    "detail": f"HbA1c is {val:.1f} mmol/mol (BR-C04 >= 48).",
                    "intervention": "Urgent clinical review."
                })
            elif val >= 42:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "Pre-diabetic HbA1c",
                    "detail": f"HbA1c is {val:.1f} mmol/mol (BR-C04 42–47).",
                    "intervention": "Clinical review; reduce refined carbs."
                })
            elif val >= 38:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Suboptimal HbA1c",
                    "detail": f"HbA1c is {val:.1f} mmol/mol (BR-C04 38–41).",
                    "intervention": "Monitor; review refined carb intake."
                })

        # BR-C05 | MCV
        if "mcv_fl" in latest and pd.notna(latest["mcv_fl"]):
            val = latest["mcv_fl"]
            if val > 100:
                alerts.append({
                    "severity": "high", "category": "bloodwork", "title": "High MCV (B12/Folate)",
                    "detail": f"MCV is {val:.1f} fL (BR-C05 > 100).",
                    "intervention": "B12/folate deficiency likely — supplement audit; retest in 8 weeks."
                })
            elif val > 95:
                alerts.append({
                    "severity": "medium", "category": "bloodwork", "title": "Elevated MCV",
                    "detail": f"MCV is {val:.1f} fL (BR-C05 95–100).",
                    "intervention": "Monitor B12/folate; confirm methylcobalamin form."
                })

    # ── Domain 4: Body Composition (Boditrax) ──

    if not body_df.empty:
        sorted_body = body_df.sort_values("day")
        latest_body = sorted_body.iloc[-1]

        # BR-B01 | Muscle Mass trend
        if "muscle_mass_kg" in sorted_body.columns and len(sorted_body) >= 2:
            recent_muscle = sorted_body["muscle_mass_kg"].tail(4)
            slope = _recent_trend(recent_muscle, window=len(recent_muscle))
            if slope is not None:
                rate_per_month = slope * 30
                if rate_per_month < -0.5:
                    alerts.append({
                        "severity": "critical", "category": "body", "title": "Critical Muscle Loss",
                        "detail": f"Muscle mass declining at {rate_per_month:.2f} kg/month (BR-B01).",
                        "intervention": "Investigate acute cause; clinical review if unexplained."
                    })
                elif rate_per_month < -0.3:
                    alerts.append({
                        "severity": "high", "category": "body", "title": "Significant Muscle Loss",
                        "detail": f"Muscle mass declining at {rate_per_month:.2f} kg/month (BR-B01).",
                        "intervention": "Check for overtraining, under-eating, illness; add deload."
                    })
                elif rate_per_month < 0.3:
                    alerts.append({
                        "severity": "medium", "category": "body", "title": "Stagnant Muscle Growth",
                        "detail": f"Muscle mass stable ({rate_per_month:+.2f} kg/month).",
                        "intervention": "Review caloric surplus; confirm protein ≥ 190g/day."
                    })
                elif rate_per_month >= 0.3:
                    alerts.append({
                        "severity": "positive", "category": "body", "title": "Optimal Muscle Gain",
                        "detail": f"Muscle mass increasing at {rate_per_month:.2f} kg/month.",
                        "intervention": "Optimal — maintain protocol."
                    })

        # BR-B02 | Fat Mass
        if "fat_mass_kg" in latest_body and pd.notna(latest_body["fat_mass_kg"]):
            val = latest_body["fat_mass_kg"]
            if val > 16.0:
                alerts.append({
                    "severity": "critical", "category": "body", "title": "Excessive Fat Mass",
                    "detail": f"Fat mass is {val:.1f} kg (BR-B02 > 16kg).",
                    "intervention": "Stop bulk; structured cut required."
                })
            elif val >= 14.5:
                alerts.append({
                    "severity": "high", "category": "body", "title": "High Fat Mass",
                    "detail": f"Fat mass is {val:.1f} kg (BR-B02 14.5–16kg).",
                    "intervention": "Initiate mini-cut: –300 kcal/day, maintain protein."
                })
            elif val >= 13.0:
                alerts.append({
                    "severity": "medium", "category": "body", "title": "Fat Mass Increasing",
                    "detail": f"Fat mass is {val:.1f} kg (BR-B02 13–14.5kg).",
                    "intervention": "Tighten nutrition; ensure caloric surplus not excessive."
                })

        # BR-B04 | Visceral Fat
        if "visceral_fat" in latest_body and pd.notna(latest_body["visceral_fat"]):
            val = latest_body["visceral_fat"]
            if val > 12:
                alerts.append({
                    "severity": "critical", "category": "body", "title": "Critical Visceral Fat",
                    "detail": f"Visceral fat rating is {val:.0f} (BR-B04 > 12).",
                    "intervention": "Clinical review; significant metabolic risk."
                })
            elif val >= 10:
                alerts.append({
                    "severity": "high", "category": "body", "title": "High Visceral Fat",
                    "detail": f"Visceral fat rating is {val:.0f} (BR-B04 10–12).",
                    "intervention": "Initiate cut; prioritise visceral fat reduction."
                })
            elif val >= 8:
                alerts.append({
                    "severity": "medium", "category": "body", "title": "Elevated Visceral Fat",
                    "detail": f"Visceral fat rating is {val:.0f} (BR-B04 8–9).",
                    "intervention": "Tighten dietary fat; increase walking volume."
                })

        # BR-B05 | Right Leg Asymmetry
        if "right_leg_muscle_kg" in latest_body and "left_leg_muscle_kg" in latest_body:
            diff = abs(latest_body["right_leg_muscle_kg"] - latest_body["left_leg_muscle_kg"])
            if diff > 0.4:
                alerts.append({
                    "severity": "critical", "category": "body", "title": "Critical Leg Asymmetry",
                    "detail": f"Leg asymmetry is {diff:.2f} kg (BR-B05 > 0.4kg).",
                    "intervention": "Investigate neurological or structural cause."
                })
            elif diff >= 0.2:
                alerts.append({
                    "severity": "high", "category": "body", "title": "High Leg Asymmetry",
                    "detail": f"Leg asymmetry is {diff:.2f} kg (BR-B05 0.2–0.4kg).",
                    "intervention": "Add dedicated unilateral session: extra set right leg per exercise."
                })
            elif diff >= 0.1:
                alerts.append({
                    "severity": "medium", "category": "body", "title": "Mild Leg Asymmetry",
                    "detail": f"Leg asymmetry is {diff:.2f} kg (BR-B05 0.1–0.2kg).",
                    "intervention": "Maintain unilateral priority (right leg first on all exercises)."
                })

        # BR-B07 | Metabolic Age
        if "metabolic_age" in latest_body and pd.notna(latest_body["metabolic_age"]):
            val = latest_body["metabolic_age"]
            if val >= 47:
                alerts.append({
                    "severity": "critical", "category": "body", "title": "Critical Metabolic Age",
                    "detail": f"Metabolic age is {val:.0f} (BR-B07 >= 47).",
                    "intervention": "Clinical review; investigate hormonal or metabolic cause."
                })
            elif val >= 43:
                alerts.append({
                    "severity": "high", "category": "body", "title": "Poor Metabolic Age",
                    "detail": f"Metabolic age is {val:.0f} (BR-B07 43–46).",
                    "intervention": "Full protocol audit — something is regressing."
                })
            elif val >= 39:
                alerts.append({
                    "severity": "medium", "category": "body", "title": "Elevated Metabolic Age",
                    "detail": f"Metabolic age is {val:.0f} (BR-B07 39–42).",
                    "intervention": "Review sleep, stress, training consistency."
                })

        # BR-B08 | Boditrax Score
        if "boditrax_score" in latest_body and pd.notna(latest_body["boditrax_score"]):
            val = latest_body["boditrax_score"]
            if val < 780:
                alerts.append({
                    "severity": "critical", "category": "body", "title": "Critical Boditrax Score",
                    "detail": f"Boditrax score is {val:.0f} (BR-B08 < 780).",
                    "intervention": "Significant regression — clinical + protocol review."
                })
            elif val < 800:
                alerts.append({
                    "severity": "high", "category": "body", "title": "Low Boditrax Score",
                    "detail": f"Boditrax score is {val:.0f} (BR-B08 780–799).",
                    "intervention": "Multiple metrics regressing; full protocol review."
                })
            elif val < 820:
                alerts.append({
                    "severity": "medium", "category": "body", "title": "Suboptimal Boditrax Score",
                    "detail": f"Boditrax score is {val:.0f} (BR-B08 800–819).",
                    "intervention": "Solid; review which sub-components are dragging."
                })

    # ── Domain 5: Body Weight Change ──

    if not mfp_weight_df.empty:
        sorted_weight = mfp_weight_df.sort_values("day")
        if len(sorted_weight) >= 14:
            recent_avg = sorted_weight.tail(7)["weight_kg"].mean()
            prev_avg = sorted_weight.tail(14).head(7)["weight_kg"].mean()
            weekly_change = recent_avg - prev_avg
            
            if weekly_change > 0.35:
                alerts.append({
                    "severity": "high", "category": "nutrition", "title": "Weight Gain Too Rapid",
                    "detail": f"Weekly average weight change is +{weekly_change:.2f} kg (BR-W01 > 0.35).",
                    "intervention": "Reduce 200 kcal immediately; check fat mass at next Boditrax."
                })
            elif weekly_change > 0.25:
                alerts.append({
                    "severity": "medium", "category": "nutrition", "title": "Fast Weight Gain",
                    "detail": f"Weekly average weight change is +{weekly_change:.2f} kg (BR-W01 0.25–0.35).",
                    "intervention": "Reduce 100 kcal; risk of excess fat gain."
                })
            elif weekly_change < 0.10:
                alerts.append({
                    "severity": "medium", "category": "nutrition", "title": "Slow Weight Gain",
                    "detail": f"Weekly average weight change is +{weekly_change:.2f} kg (BR-W01 0.10–0.15).",
                    "intervention": "Add 100 kcal; monitor for 2 more weeks."
                })

    # ── Domain 6: Training & Recovery ──

    # BR-T03 | HRV
    if not readiness_df.empty:
        hrv_col = next((c for c in ["contributors.hrv_balance", "hrv_balance"] if c in readiness_df.columns), None)
        if hrv_col:
            recent_hrv = readiness_df.sort_values("day").tail(5)[hrv_col].mean()
            if recent_hrv < 28:
                alerts.append({
                    "severity": "critical", "category": "sleep", "title": "Critical Low HRV",
                    "detail": f"5-day avg HRV is {recent_hrv:.0f} ms (BR-T03 < 28).",
                    "intervention": "Skip training; investigate acute cause (illness, injury, stress)."
                })
            elif recent_hrv < 35:
                alerts.append({
                    "severity": "high", "category": "sleep", "title": "Suppressed HRV",
                    "detail": f"5-day avg HRV is {recent_hrv:.0f} ms (BR-T03 28–35).",
                    "intervention": "Suppressed — reduce intensity; prioritise recovery."
                })
            elif recent_hrv < 40:
                alerts.append({
                    "severity": "medium", "category": "sleep", "title": "Low Normal HRV",
                    "detail": f"5-day avg HRV is {recent_hrv:.0f} ms (BR-T03 35–40).",
                    "intervention": "At personal baseline — train normally, monitor."
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

        # Sleep regularity
        if "timestamp" in sorted_sleep.columns:
            recent = sorted_sleep.tail(14)
            timestamps = pd.to_datetime(recent["timestamp"], errors="coerce").dropna()
            if len(timestamps) >= 7:
                bedtimes_hour = timestamps.dt.hour + timestamps.dt.minute / 60
                bedtimes_adj = bedtimes_hour.copy()
                bedtimes_adj[bedtimes_adj < 12] += 24
                spread = bedtimes_adj.max() - bedtimes_adj.min()
                if spread > 2.0:
                    alerts.append({
                        "severity": "low",
                        "category": "sleep",
                        "title": "Irregular Sleep Schedule",
                        "detail": f"Bedtime varies by {spread:.1f} hours over the last 14 nights (>2 hour spread).",
                        "intervention": (
                            "- Set a consistent bedtime and wake time — even on weekends\n"
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
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "positive": 4}
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
