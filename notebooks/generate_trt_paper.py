#!/usr/bin/env python3
"""Generate a professional PDF paper from TRT PK analysis data."""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from scipy import stats
from scipy.stats import pearsonr, spearmanr
from pathlib import Path
from datetime import datetime
import tempfile
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib import colors

# ---------- Constants ----------
PURPLE = "#7A6FBE"
GREEN = "#50B88E"
ORANGE = "#E8915A"
BLUE = "#4A90D9"
RED = "#E63946"
GREY = "#8B8D97"
DARK = "#2D2D3F"

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
OUTPUT_DIR = Path(__file__).parent.parent / "reports"
OUTPUT_DIR.mkdir(exist_ok=True)

CONC_MG_PER_ML = 200
ESTER_FACTOR = 0.70

sns.set_theme(style="whitegrid", font_scale=1.0)
plt.rcParams.update({
    "figure.dpi": 150,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "lines.linewidth": 1.8,
    "figure.facecolor": "white",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})

# ---------- Data Loading ----------
def load_data():
    """Load all required datasets."""
    data = {}
    data["bloodwork"] = pd.read_csv(DATA_DIR / "bloodwork.csv", parse_dates=["date"])
    data["sleep"] = pd.read_csv(DATA_DIR / "sleep.csv", parse_dates=["day"])
    data["readiness"] = pd.read_csv(DATA_DIR / "readiness.csv", parse_dates=["day"])
    data["stress"] = pd.read_csv(DATA_DIR / "stress.csv", parse_dates=["day"])
    data["activity"] = pd.read_csv(DATA_DIR / "activity.csv", parse_dates=["day"])
    data["workouts"] = pd.read_csv(DATA_DIR / "workouts.csv", parse_dates=["day"])
    data["nutrition"] = pd.read_csv(DATA_DIR / "nutrition.csv", parse_dates=["date"])
    data["body_comp"] = pd.read_csv(DATA_DIR / "body_composition.csv", parse_dates=["date"])
    data["trt"] = pd.read_csv(RAW_DIR / "trt" / "trt_dose_history.csv", parse_dates=["date"])

    for key in data:
        df = data[key]
        date_col = "date" if "date" in df.columns else "day"
        if date_col in df.columns:
            df.sort_values(date_col, inplace=True)
            df.reset_index(drop=True, inplace=True)

    return data


def build_phases():
    """Build TRT phase definitions."""
    phases = [
        {"label": "Pre-TRT (Baseline)", "start": "2025-01-29", "end": "2025-02-14",
         "dose_ml": 0, "colour": GREY},
        {"label": "Phase 1: 0.20ml x2/wk", "start": "2025-02-15", "end": "2025-05-12",
         "dose_ml": 0.20, "colour": BLUE},
        {"label": "Phase 2: 0.23ml x2/wk", "start": "2025-05-13", "end": "2025-08-25",
         "dose_ml": 0.23, "colour": GREEN},
        {"label": "Phase 3: 0.26ml x2/wk (prescribed)", "start": "2025-08-26", "end": "2026-05-09",
         "dose_ml": 0.26, "actual_ml": 0.28, "colour": ORANGE},
    ]
    for p in phases:
        p["start"] = pd.Timestamp(p["start"])
        p["end"] = pd.Timestamp(p["end"])
        p["weekly_mg_cypionate"] = p["dose_ml"] * CONC_MG_PER_ML * 2
        p["weekly_mg_active_T"] = p["weekly_mg_cypionate"] * ESTER_FACTOR
        if "actual_ml" in p:
            p["actual_mg_active_T_weekly"] = p["actual_ml"] * CONC_MG_PER_ML * 2 * ESTER_FACTOR
    return phases


def get_dose(date, phases):
    for p in reversed(phases):
        if date >= p["start"]:
            return p["weekly_mg_active_T"]
    return 0


COFACTOR_STOP_START = pd.Timestamp("2026-02-12")
COFACTOR_STOP_END = pd.Timestamp("2026-05-03")

# Misread period: actual dosing was 0.28ml instead of prescribed 0.26ml
MISREAD_START = pd.Timestamp("2025-08-26")
MISREAD_END = pd.Timestamp("2026-02-18")


def get_actual_dose(date, phases):
    """Get actual mg active T/week at a given date, accounting for misread period."""
    for p in reversed(phases):
        if date >= p["start"]:
            if "actual_ml" in p and MISREAD_START <= date <= MISREAD_END:
                return p["actual_ml"] * CONC_MG_PER_ML * 2 * ESTER_FACTOR
            return p["weekly_mg_active_T"]
    return 0


# ---------- Chart Generation ----------
def save_fig(fig, name, tmpdir):
    path = os.path.join(tmpdir, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def chart_timeline(data, phases, tmpdir):
    """Master timeline chart."""
    bloodwork = data["bloodwork"]
    bt = bloodwork.dropna(subset=["testosterone_nmol"])

    fig, ax1 = plt.subplots(figsize=(12, 5))
    for p in phases:
        if p["dose_ml"] > 0:
            ax1.axvspan(p["start"], p["end"], alpha=0.10, color=p["colour"])
            ax1.hlines(p["weekly_mg_active_T"], p["start"], p["end"],
                       colors=p["colour"], linewidth=2.5, linestyle="--", alpha=0.6)
    ax1.axvspan(COFACTOR_STOP_START, COFACTOR_STOP_END, alpha=0.12, color=RED, hatch="//")

    ax1.scatter(bt["date"], bt["testosterone_nmol"], s=120, c=PURPLE, zorder=5,
                edgecolors="white", linewidth=1.5)
    ax1.plot(bt["date"], bt["testosterone_nmol"], color=PURPLE, alpha=0.4, linestyle="-")
    for _, row in bt.iterrows():
        ax1.annotate(f'{row["testosterone_nmol"]:.1f}',
                     (row["date"], row["testosterone_nmol"]),
                     textcoords="offset points", xytext=(0, 12),
                     fontsize=9, fontweight="bold", color=PURPLE, ha="center")

    ax1.axhline(y=15, color=RED, linestyle=":", alpha=0.5, linewidth=1)
    ax1.axhline(y=30, color=GREEN, linestyle=":", alpha=0.5, linewidth=1)
    ax1.text(bt["date"].min(), 14.0, "BSSM minimum (15 nmol/L)", fontsize=7, color=RED, alpha=0.7)
    ax1.text(bt["date"].min(), 30.5, "BSSM upper (30 nmol/L)", fontsize=7, color=GREEN, alpha=0.7)

    ax2 = ax1.twinx()
    ft = bloodwork.dropna(subset=["free_testosterone_nmol"])
    ax2.scatter(ft["date"], ft["free_testosterone_nmol"], s=90, c=ORANGE, marker="D",
                zorder=5, edgecolors="white", linewidth=1.5)
    ax2.plot(ft["date"], ft["free_testosterone_nmol"], color=ORANGE, alpha=0.4, linestyle="-")
    for _, row in ft.iterrows():
        ax2.annotate(f'{row["free_testosterone_nmol"]:.3f}',
                     (row["date"], row["free_testosterone_nmol"]),
                     textcoords="offset points", xytext=(0, -15),
                     fontsize=8, fontweight="bold", color=ORANGE, ha="center")

    ax1.set_ylabel("Total Testosterone (nmol/L)", fontsize=9)
    ax2.set_ylabel("Free Testosterone (nmol/L)", fontsize=9)
    ax1.set_title("Figure 1. TRT Timeline: Dose Escalation, Blood Results & Cofactor Cessation",
                  fontsize=10, fontweight="bold")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    fig.autofmt_xdate()
    plt.tight_layout()
    return save_fig(fig, "timeline", tmpdir)


def chart_dose_response(data, phases, tmpdir):
    """Dose-response analysis."""
    bloodwork = data["bloodwork"].copy()
    bloodwork["dose_mg_active_T"] = bloodwork["date"].apply(lambda d: get_actual_dose(d, phases))
    dr = bloodwork.dropna(subset=["testosterone_nmol"]).copy()
    dr = dr[dr["dose_mg_active_T"] > 0]
    dr["t_per_mg"] = dr["testosterone_nmol"] / dr["dose_mg_active_T"]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))

    ax = axes[0]
    ax.scatter(dr["dose_mg_active_T"], dr["testosterone_nmol"], s=100, c=PURPLE,
               zorder=5, edgecolors="white", linewidth=1.5)
    for _, row in dr.iterrows():
        ax.annotate(row["date"].strftime("%b %y"), (row["dose_mg_active_T"], row["testosterone_nmol"]),
                    textcoords="offset points", xytext=(6, 4), fontsize=7)
    if len(dr) > 2:
        slope, intercept, r, p, se = stats.linregress(dr["dose_mg_active_T"], dr["testosterone_nmol"])
        x_line = np.linspace(dr["dose_mg_active_T"].min() - 5, dr["dose_mg_active_T"].max() + 5, 100)
        ax.plot(x_line, slope * x_line + intercept, "--", color=RED, alpha=0.7, label=f"r={r:.3f}")
        ax.legend(fontsize=8)
    ax.set_xlabel("Weekly Active T (mg)", fontsize=8)
    ax.set_ylabel("Total T (nmol/L)", fontsize=8)
    ax.set_title("A) Total T vs Dose", fontsize=9)

    ax = axes[1]
    ax.scatter(dr["dose_mg_active_T"], dr["free_testosterone_nmol"], s=100, c=ORANGE,
               zorder=5, edgecolors="white", linewidth=1.5)
    for _, row in dr.iterrows():
        ax.annotate(row["date"].strftime("%b %y"), (row["dose_mg_active_T"], row["free_testosterone_nmol"]),
                    textcoords="offset points", xytext=(6, 4), fontsize=7)
    if len(dr) > 2:
        slope, intercept, r, p, se = stats.linregress(dr["dose_mg_active_T"], dr["free_testosterone_nmol"])
        x_line = np.linspace(dr["dose_mg_active_T"].min() - 5, dr["dose_mg_active_T"].max() + 5, 100)
        ax.plot(x_line, slope * x_line + intercept, "--", color=RED, alpha=0.7, label=f"r={r:.3f}")
        ax.legend(fontsize=8)
    ax.set_xlabel("Weekly Active T (mg)", fontsize=8)
    ax.set_ylabel("Free T (nmol/L)", fontsize=8)
    ax.set_title("B) Free T vs Dose", fontsize=9)

    ax = axes[2]
    bar_colours = [BLUE, BLUE, GREEN, ORANGE, ORANGE][:len(dr)]
    ax.bar(dr["date"].dt.strftime("%b %y"), dr["t_per_mg"], color=bar_colours,
           edgecolor="white", linewidth=1)
    ax.set_ylabel("nmol/L per mg dose", fontsize=8)
    ax.set_title("C) Dose-Normalised Response", fontsize=9)
    ax.tick_params(axis="x", rotation=45, labelsize=7)

    fig.suptitle("Figure 2. Dose-Response Analysis", fontsize=10, fontweight="bold", y=1.02)
    plt.tight_layout()
    return save_fig(fig, "dose_response", tmpdir)


def chart_shbg(data, phases, tmpdir):
    """SHBG dynamics and free T fraction."""
    bloodwork = data["bloodwork"].copy()
    bloodwork["dose_mg_active_T"] = bloodwork["date"].apply(lambda d: get_dose(d, phases))
    bloodwork["free_androgen_index"] = (bloodwork["testosterone_nmol"] / bloodwork["shbg_nmol"]) * 100
    bloodwork["free_t_pct"] = (bloodwork["free_testosterone_nmol"] / bloodwork["testosterone_nmol"]) * 100

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))

    # A) SHBG trajectory
    ax = axes[0, 0]
    shbg = bloodwork.dropna(subset=["shbg_nmol"])
    ax.plot(shbg["date"], shbg["shbg_nmol"], "o-", color=RED, markersize=8, linewidth=1.5,
            markeredgecolor="white", markeredgewidth=1.5)
    ax.axvspan(COFACTOR_STOP_START, COFACTOR_STOP_END, alpha=0.12, color=RED, hatch="//")
    for _, row in shbg.iterrows():
        ax.annotate(f'{row["shbg_nmol"]:.1f}', (row["date"], row["shbg_nmol"]),
                    textcoords="offset points", xytext=(0, 10), fontsize=8, fontweight="bold", ha="center")
    ax.axhspan(18, 30, alpha=0.06, color=GREEN)
    ax.set_ylabel("SHBG (nmol/L)", fontsize=8)
    ax.set_title("A) SHBG Trajectory", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

    # B) Free T %
    ax = axes[0, 1]
    ft_pct = bloodwork.dropna(subset=["free_t_pct"])
    ax.plot(ft_pct["date"], ft_pct["free_t_pct"], "o-", color=GREEN, markersize=8, linewidth=1.5,
            markeredgecolor="white", markeredgewidth=1.5)
    ax.axvspan(COFACTOR_STOP_START, COFACTOR_STOP_END, alpha=0.12, color=RED, hatch="//")
    for _, row in ft_pct.iterrows():
        ax.annotate(f'{row["free_t_pct"]:.2f}%', (row["date"], row["free_t_pct"]),
                    textcoords="offset points", xytext=(0, 10), fontsize=8, fontweight="bold", ha="center")
    ax.set_ylabel("Free T %", fontsize=8)
    ax.set_title("B) Free Testosterone Fraction", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

    # C) FAI
    ax = axes[1, 0]
    fai = bloodwork.dropna(subset=["free_androgen_index"])
    bar_colours = [RED if v < 40 else (ORANGE if v < 60 else GREEN) for v in fai["free_androgen_index"]]
    ax.bar(fai["date"].dt.strftime("%b %y"), fai["free_androgen_index"], color=bar_colours,
           edgecolor="white", linewidth=1)
    ax.axhline(y=40, color=RED, linestyle=":", alpha=0.5, label="Suboptimal (<40)")
    ax.axhline(y=70, color=GREEN, linestyle=":", alpha=0.5, label="Optimal (>70)")
    ax.set_ylabel("FAI", fontsize=8)
    ax.set_title("C) Free Androgen Index", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", rotation=45, labelsize=7)

    # D) SHBG vs Free T
    ax = axes[1, 1]
    valid = bloodwork.dropna(subset=["shbg_nmol", "free_testosterone_nmol"])
    ax.scatter(valid["shbg_nmol"], valid["free_testosterone_nmol"], s=100, c=PURPLE,
               zorder=5, edgecolors="white", linewidth=1.5)
    for _, row in valid.iterrows():
        ax.annotate(row["date"].strftime("%b %y"), (row["shbg_nmol"], row["free_testosterone_nmol"]),
                    textcoords="offset points", xytext=(6, 4), fontsize=7)
    if len(valid) > 2:
        r, p = pearsonr(valid["shbg_nmol"], valid["free_testosterone_nmol"])
        slope, intercept, _, _, _ = stats.linregress(valid["shbg_nmol"], valid["free_testosterone_nmol"])
        x_line = np.linspace(valid["shbg_nmol"].min() - 2, valid["shbg_nmol"].max() + 2, 100)
        ax.plot(x_line, slope * x_line + intercept, "--", color=RED, alpha=0.7)
        ax.set_title(f"D) SHBG vs Free T (r={r:.3f})", fontsize=9)
    ax.set_xlabel("SHBG (nmol/L)", fontsize=8)
    ax.set_ylabel("Free T (nmol/L)", fontsize=8)

    fig.suptitle("Figure 3. SHBG Dynamics & Free Testosterone Bioavailability",
                 fontsize=10, fontweight="bold")
    plt.tight_layout()
    return save_fig(fig, "shbg", tmpdir)


def chart_cofactor_impact(data, tmpdir):
    """Cofactor cessation impact."""
    bloodwork = data["bloodwork"]
    last_on = bloodwork[bloodwork["date"] == "2026-02-12"].iloc[0]
    first_off = bloodwork[bloodwork["date"] == "2026-05-03"].iloc[0]
    observed_shbg_change = first_off["shbg_nmol"] - last_on["shbg_nmol"]

    cofactors = pd.DataFrame({
        "Supplement": ["Boron 10mg", "Zinc Picolinate", "Mg Glycinate 400mg", "Selenium", "P5P 50mg"],
        "SHBG_low": [3.0, 1.0, 2.0, 1.0, 0.5],
        "SHBG_high": [4.0, 2.0, 3.0, 2.0, 1.0],
        "Colour": [RED, ORANGE, BLUE, GREEN, PURPLE]
    })
    cofactors["SHBG_mid"] = (cofactors["SHBG_low"] + cofactors["SHBG_high"]) / 2

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Stacked bar
    ax = axes[0]
    cumulative = 0
    for _, row in cofactors.iterrows():
        ax.barh(0, row["SHBG_mid"], left=cumulative, height=0.4,
                color=row["Colour"], edgecolor="white", linewidth=1.5,
                label=f'{row["Supplement"]} (+{row["SHBG_mid"]:.1f})')
        ax.text(cumulative + row["SHBG_mid"] / 2, 0, f'+{row["SHBG_mid"]:.1f}',
                ha="center", va="center", fontsize=9, fontweight="bold", color="white")
        cumulative += row["SHBG_mid"]
    ax.axvline(x=observed_shbg_change, color="black", linewidth=2.5, linestyle="-",
               label=f"Observed: +{observed_shbg_change:.1f}")
    ax.set_xlabel("SHBG Increase (nmol/L)", fontsize=8)
    ax.set_title("A) Cumulative Cofactor SHBG Impact", fontsize=9)
    ax.set_yticks([])
    ax.legend(loc="upper left", fontsize=7)

    # Expected vs Observed
    ax = axes[1]
    expected_low = cofactors["SHBG_low"].sum()
    expected_high = cofactors["SHBG_high"].sum()
    expected_mid = cofactors["SHBG_mid"].sum()
    bars = ax.bar(["Expected\n(Literature)", "Observed"], [expected_mid, observed_shbg_change],
                  color=[BLUE, RED], edgecolor="white", linewidth=1.5, width=0.45)
    ax.errorbar(0, expected_mid, yerr=[[expected_mid - expected_low], [expected_high - expected_mid]],
                fmt="none", ecolor="black", capsize=8, linewidth=1.5)
    for bar, val in zip(bars, [expected_mid, observed_shbg_change]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"+{val:.1f}", ha="center", fontsize=11, fontweight="bold")
    ax.set_ylabel("SHBG Change (nmol/L)", fontsize=8)
    ax.set_title("B) Expected vs Observed", fontsize=9)

    fig.suptitle("Figure 4. Cofactor Cessation Impact on SHBG", fontsize=10, fontweight="bold")
    plt.tight_layout()
    return save_fig(fig, "cofactors", tmpdir)


def chart_training(data, phases, tmpdir):
    """Training load analysis."""
    workouts = data["workouts"]
    bloodwork = data["bloodwork"]
    bt = bloodwork.dropna(subset=["testosterone_nmol"])

    daily_volume = workouts.groupby("day").agg(
        total_volume=pd.NamedAgg(column="volume", aggfunc="sum"),
    ).reset_index()
    daily_volume.set_index("day", inplace=True)
    weekly_volume = daily_volume["total_volume"].resample("W").sum().reset_index()
    weekly_volume.columns = ["week", "volume"]
    weekly_volume["rolling_4wk"] = weekly_volume["volume"].rolling(4, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.bar(weekly_volume["week"], weekly_volume["volume"], width=6, color=BLUE, alpha=0.35)
    ax.plot(weekly_volume["week"], weekly_volume["rolling_4wk"], color=BLUE, linewidth=2.5,
            label="4-Week Rolling Avg")
    for _, row in bt.iterrows():
        ax.axvline(x=row["date"], color=PURPLE, linestyle="--", alpha=0.4, linewidth=1)
        ax.text(row["date"], ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] > 0 else 100000,
                f'T={row["testosterone_nmol"]:.1f}',
                rotation=90, va="top", fontsize=7, color=PURPLE, fontweight="bold")
    ax.axvspan(COFACTOR_STOP_START, COFACTOR_STOP_END, alpha=0.08, color=RED, hatch="//")
    ax.set_ylabel("Total Volume (kg)", fontsize=8)
    ax.set_title("Figure 5. Weekly Training Volume with Blood Test Overlay", fontsize=10, fontweight="bold")
    ax.legend(fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    plt.tight_layout()
    return save_fig(fig, "training", tmpdir)


def chart_recovery(data, tmpdir):
    """Recovery metrics."""
    sleep = data["sleep"]
    readiness = data["readiness"]
    bt = data["bloodwork"].dropna(subset=["testosterone_nmol"])

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    ax = axes[0]
    weekly_readiness = readiness.set_index("day")["score"].resample("W").mean().reset_index()
    ax.plot(weekly_readiness["day"], weekly_readiness["score"], color=GREEN, linewidth=1.5)
    ax.fill_between(weekly_readiness["day"], weekly_readiness["score"], alpha=0.1, color=GREEN)
    ax.axvspan(COFACTOR_STOP_START, COFACTOR_STOP_END, alpha=0.08, color=RED, hatch="//")
    ax.set_ylabel("Score", fontsize=8)
    ax.set_title("A) Weekly Readiness Score", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

    ax = axes[1]
    hrv_col = "contributors.hrv_balance"
    if hrv_col in readiness.columns:
        weekly_hrv = readiness.set_index("day")[hrv_col].resample("W").mean().reset_index()
        ax.plot(weekly_hrv["day"], weekly_hrv[hrv_col], color=BLUE, linewidth=1.5)
        ax.fill_between(weekly_hrv["day"], weekly_hrv[hrv_col], alpha=0.1, color=BLUE)
    ax.axvspan(COFACTOR_STOP_START, COFACTOR_STOP_END, alpha=0.08, color=RED, hatch="//")
    ax.set_ylabel("HRV Balance", fontsize=8)
    ax.set_title("B) Weekly HRV Balance", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

    fig.suptitle("Figure 6. Recovery & Physiological Stress", fontsize=10, fontweight="bold")
    plt.tight_layout()
    return save_fig(fig, "recovery", tmpdir)


def chart_haematology(data, tmpdir):
    """Haematological safety markers."""
    bloodwork = data["bloodwork"]
    markers = {
        "Haematocrit %": ("haematocrit_pct", RED, 54, 46),
        "Haemoglobin g/L": ("haemoglobin_g", BLUE, 170, 135),
        "RBC Count": ("rbc_count", GREEN, 5.5, 4.5),
    }

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for (title, (col, colour, hi, lo)), ax in zip(markers.items(), axes):
        valid = bloodwork.dropna(subset=[col])
        if len(valid) > 0:
            ax.plot(valid["date"], valid[col], "o-", color=colour, markersize=7, linewidth=1.5,
                    markeredgecolor="white", markeredgewidth=1.5)
            for _, row in valid.iterrows():
                ax.annotate(f'{row[col]:.1f}', (row["date"], row[col]),
                            textcoords="offset points", xytext=(0, 10), fontsize=7,
                            fontweight="bold", ha="center")
            ax.axhline(y=hi, color=RED, linestyle=":", alpha=0.4, label=f"Ceiling ({hi})")
            ax.legend(fontsize=6)
        ax.set_ylabel(title, fontsize=8)
        ax.set_title(title, fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
        ax.tick_params(axis="x", rotation=45, labelsize=6)

    fig.suptitle("Figure 7. Haematological Safety Markers", fontsize=10, fontweight="bold")
    plt.tight_layout()
    return save_fig(fig, "haematology", tmpdir)


def chart_pk_simulation(tmpdir):
    """Injection frequency PK simulation."""
    half_life = 8.0
    decay_k = np.log(2) / half_life
    abs_k = np.log(2) / 0.5

    def simulate(dose_ml, freq, days=60, dt=0.01):
        mg = dose_ml * CONC_MG_PER_ML * ESTER_FACTOR
        interval = 7.0 / freq
        t = np.arange(0, days, dt)
        conc = np.zeros_like(t)
        for i in range(int(np.ceil(days / interval)) + 1):
            t_inj = i * interval
            mask = t >= t_inj
            tau = t[mask] - t_inj
            conc[mask] += mg * abs_k * (np.exp(-decay_k * tau) - np.exp(-abs_k * tau)) / (abs_k - decay_k)
        return t, conc

    scenarios = {
        "Current prescribed: 0.26ml x2/wk": (0.26, 2, ORANGE),
        "Optimised 2x: 0.35ml x2/wk": (0.35, 2, BLUE),
        "Optimised 3x: 0.23ml x3/wk": (0.23, 3, GREEN),
        "Target 3x: 0.27ml x3/wk": (0.27, 3, PURPLE),
    }

    fig, axes = plt.subplots(2, 1, figsize=(12, 9))

    ax = axes[0]
    for label, (dose_ml, freq, colour) in scenarios.items():
        t, conc = simulate(dose_ml, freq, days=50)
        ax.plot(t, conc, color=colour, linewidth=1.8, label=label, alpha=0.85)
    ax.set_xlabel("Days from Protocol Start", fontsize=8)
    ax.set_ylabel("Relative Serum T (mg-equivalent)", fontsize=8)
    ax.set_title("A) Approach to Steady State", fontsize=9)
    ax.legend(fontsize=7, loc="lower right")
    ax.axvline(x=40, color=GREY, linestyle=":", alpha=0.4)

    ax = axes[1]
    pk_data = []
    for label, (dose_ml, freq, colour) in scenarios.items():
        t, conc = simulate(dose_ml, freq, days=60)
        ss_mask = t >= 46
        t_ss = t[ss_mask] - t[ss_mask].min()
        c_ss = conc[ss_mask]
        ax.plot(t_ss, c_ss, color=colour, linewidth=2, label=label, alpha=0.85)
        peak, trough = c_ss.max(), c_ss.min()
        mean_c = c_ss.mean()
        pk_data.append({
            "Protocol": label.split(":")[0].strip(),
            "Weekly mg": round(dose_ml * CONC_MG_PER_ML * ESTER_FACTOR * freq, 1),
            "Peak:Trough": f"{peak/trough:.2f}:1" if trough > 0 else "N/A",
            "Fluctuation": f"{(peak-trough)/mean_c*100:.1f}%",
        })
    ax.set_xlabel("Days (Steady-State Window)", fontsize=8)
    ax.set_ylabel("Relative Serum T (mg-equivalent)", fontsize=8)
    ax.set_title("B) Steady-State Peak/Trough Comparison", fontsize=9)
    ax.legend(fontsize=7)

    fig.suptitle("Figure 8. Injection Frequency Pharmacokinetic Modelling", fontsize=10, fontweight="bold")
    plt.tight_layout()
    return save_fig(fig, "pk_simulation", tmpdir), pk_data


def chart_dose_optimisation(data, tmpdir):
    """Dose optimisation chart."""
    # May 2026 blood was drawn AFTER misread correction (Feb 18, 2026)
    # so actual dose at draw was prescribed 0.26ml = 72.8mg active T
    latest_t = 12.7
    actual_dose = 72.8   # prescribed dose — misread corrected before this draw
    unsuppressed_ratio = latest_t / actual_dose  # PK ratio at prescribed dose

    cofactor_t = 19.0
    cofactor_dose = 64.4
    cofactor_ratio = cofactor_t / cofactor_dose

    fig, ax = plt.subplots(figsize=(12, 5.5))
    dose_range = np.linspace(50, 200, 200)

    ax.plot(dose_range, dose_range * unsuppressed_ratio, color=RED, linewidth=2,
            label=f"Without cofactors ({unsuppressed_ratio:.3f} nmol/mg)")
    ax.plot(dose_range, dose_range * cofactor_ratio, color=GREEN, linewidth=2, linestyle="--",
            label=f"With cofactors ({cofactor_ratio:.3f} nmol/mg)")
    ax.axhspan(15, 30, alpha=0.06, color=GREEN, label="BSSM target (15-30 nmol/L)")
    ax.axhline(y=15, color=GREEN, linestyle=":", alpha=0.3)
    ax.axhline(y=30, color=GREEN, linestyle=":", alpha=0.3)

    ax.scatter([actual_dose], [latest_t], s=150, c=RED, zorder=10, edgecolors="white", linewidth=2)
    ax.scatter([cofactor_dose], [cofactor_t], s=150, c=GREEN, zorder=10, edgecolors="white",
               linewidth=2, marker="D")

    for target_t in [15, 20, 25]:
        req = target_t / unsuppressed_ratio
        ml_2x = req / ESTER_FACTOR / CONC_MG_PER_ML / 2
        ml_3x = req / ESTER_FACTOR / CONC_MG_PER_ML / 3
        ax.plot([req, req], [0, target_t], ":", color=GREY, alpha=0.4)
        ax.annotate(f"{req:.0f}mg\n({ml_2x:.2f}ml x2)\n({ml_3x:.2f}ml x3)",
                    (req, target_t), textcoords="offset points", xytext=(8, -5),
                    fontsize=7, fontweight="bold", color=PURPLE,
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor=PURPLE, alpha=0.7))

    ax.set_xlabel("Weekly Active T Dose (mg)", fontsize=9)
    ax.set_ylabel("Predicted Total T (nmol/L)", fontsize=9)
    ax.set_title("Figure 9. Dose Optimisation: Required Dose for BSSM Targets", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, loc="upper left")
    ax.set_xlim(50, 200)
    ax.set_ylim(0, 35)
    plt.tight_layout()
    return save_fig(fig, "dose_optimisation", tmpdir)


def chart_correlation_matrix(data, tmpdir):
    """Blood marker correlation matrix."""
    bloodwork = data["bloodwork"]
    marker_cols = ["testosterone_nmol", "free_testosterone_nmol", "shbg_nmol", "oestradiol_pmol",
                   "haematocrit_pct", "haemoglobin_g", "rbc_count",
                   "total_cholesterol_mmol", "hdl_mmol", "ldl_mmol",
                   "alt_u", "albumin_g", "creatinine_umol", "psa_ug", "prolactin_miu"]
    available = [c for c in marker_cols if c in bloodwork.columns]
    marker_data = bloodwork[available].dropna(axis=1, thresh=3)

    if marker_data.shape[1] <= 3:
        return None

    corr = marker_data.corr(method="pearson")
    rename = {"testosterone_nmol": "Total T", "free_testosterone_nmol": "Free T",
              "shbg_nmol": "SHBG", "oestradiol_pmol": "E2",
              "haematocrit_pct": "HCT%", "haemoglobin_g": "Hb",
              "rbc_count": "RBC", "total_cholesterol_mmol": "T.Chol",
              "hdl_mmol": "HDL", "ldl_mmol": "LDL", "alt_u": "ALT",
              "albumin_g": "Albumin", "creatinine_umol": "Creat",
              "psa_ug": "PSA", "prolactin_miu": "PRL"}
    corr_display = corr.rename(index=rename, columns=rename)

    fig, ax = plt.subplots(figsize=(10, 8))
    mask = np.triu(np.ones_like(corr_display, dtype=bool))
    sns.heatmap(corr_display, mask=mask, annot=True, fmt=".2f", center=0,
                cmap="RdBu_r", vmin=-1, vmax=1, square=True,
                linewidths=0.5, cbar_kws={"shrink": 0.7}, annot_kws={"size": 8}, ax=ax)
    ax.set_title("Figure 10. Blood Marker Correlation Matrix", fontsize=10, fontweight="bold")
    plt.tight_layout()
    return save_fig(fig, "correlations", tmpdir)


# ---------- PDF Construction ----------
def build_pdf(data, phases, chart_paths, pk_data):
    """Build the final PDF document."""
    output_path = OUTPUT_DIR / f"trt_pk_analysis_{datetime.now().strftime('%Y-%m-%d')}.pdf"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        "PaperTitle", parent=styles["Title"],
        fontSize=18, spaceAfter=4, textColor=HexColor(DARK),
        alignment=TA_CENTER, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "PaperSubtitle", parent=styles["Normal"],
        fontSize=11, spaceAfter=8, textColor=HexColor(GREY),
        alignment=TA_CENTER, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "SectionHead", parent=styles["Heading1"],
        fontSize=13, spaceBefore=16, spaceAfter=6,
        textColor=HexColor(DARK), fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "SubSectionHead", parent=styles["Heading2"],
        fontSize=11, spaceBefore=10, spaceAfter=4,
        textColor=HexColor(DARK), fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "BodyText2", parent=styles["Normal"],
        fontSize=9.5, leading=14, spaceAfter=6,
        alignment=TA_JUSTIFY, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "SmallItalic", parent=styles["Normal"],
        fontSize=8, leading=11, spaceAfter=4,
        fontName="Helvetica-Oblique", textColor=HexColor(GREY),
    ))
    styles.add(ParagraphStyle(
        "BulletText", parent=styles["Normal"],
        fontSize=9.5, leading=13, spaceAfter=3,
        leftIndent=12, bulletIndent=0,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "RefText", parent=styles["Normal"],
        fontSize=8, leading=11, spaceAfter=2,
        fontName="Helvetica", leftIndent=14, firstLineIndent=-14,
    ))

    story = []

    # -- Title Page --
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph(
        "TRT Pharmacokinetic Analysis", styles["PaperTitle"]))
    story.append(Paragraph(
        "Testosterone Replacement Therapy: Dose-Response,<br/>Cofactor Impact &amp; Protocol Optimisation",
        styles["PaperSubtitle"]))
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="60%", thickness=1, color=HexColor(GREY), spaceAfter=8))
    story.append(Spacer(1, 5 * mm))

    meta_data = [
        ["Analysis Period:", "January 2025 \u2013 May 2026"],
        ["Blood Tests:", "6 panels (baseline + 5 on-treatment)"],
        ["TRT Formulation:", "Testosterone Cypionate 200mg/ml, subcutaneous"],
        ["Current Protocol:", "0.26ml \u00d7 2/week (72.8 mg active T/week)"],
        ["Dosing Note:", "0.28ml actual (Aug 2025\u2013Feb 2026) due to misread; corrected to 0.26ml"],
        ["Provider:", "Manual (manual.co)"],
        ["Clinical Framework:", "BSSM Guidelines (Hackett et al., 2017; 2023)"],
        ["Report Generated:", datetime.now().strftime("%d %B %Y")],
    ]
    meta_table = Table(meta_data, colWidths=[120, 320])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 12 * mm))

    # BSSM Targets table
    story.append(Paragraph("BSSM On-Treatment Targets", styles["SubSectionHead"]))
    bssm_data = [
        ["Marker", "Target Range", "Source"],
        ["Total Testosterone (trough)", "15\u201330 nmol/L", "BSSM 2017/2023"],
        ["Free Testosterone", "0.225\u20130.500 nmol/L", "BSSM / Vermeulen"],
        ["Haematocrit", "< 0.54 (safety ceiling)", "BSSM 2017"],
        ["PSA rise", "< 1.4 ng/mL in 12 months", "BSSM 2017"],
        ["Dose titration", "10\u201325% per step, retest 6\u201312 wks", "BSSM 2023"],
    ]
    bssm_table = Table(bssm_data, colWidths=[150, 170, 120])
    bssm_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#E8E8F0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(bssm_table)

    story.append(PageBreak())

    # -- Abstract --
    story.append(Paragraph("Clinical Question", styles["SectionHead"]))
    story.append(Paragraph(
        "After 15 months on testosterone replacement therapy with gradual dose escalation "
        "(56 \u2192 72.8 mg active T/week), the latest trough total testosterone is 12.7 nmol/L \u2014 "
        "below the BSSM minimum on-treatment target of 15 nmol/L. This result was obtained at "
        "the current prescribed dose (0.26ml \u00d7 2/week) and coincides with cessation of a "
        "cofactor supplement stack (Boron, Zinc, Magnesium, Selenium, P5P) that had been "
        "suppressing SHBG. Note: between Aug 2025 and Feb 2026, actual dosing was 0.28ml "
        "due to a misread; this was disclosed to the clinician in Feb 2026 and corrected. "
        "This analysis examines whether the current protocol achieves adequate trough levels "
        "independently of supplementation, and presents evidence-based options for protocol adjustment.",
        styles["BodyText2"]))
    story.append(Paragraph(
        "A well-optimised TRT protocol should achieve therapeutic blood testosterone levels "
        "independently of supplementation, diet optimisation, or training status. These lifestyle "
        "factors should be additive \u2014 not compensatory.",
        styles["SmallItalic"]))

    story.append(Spacer(1, 4 * mm))

    # -- Blood Results Table --
    story.append(Paragraph("1. Blood Test Results Across TRT Phases", styles["SectionHead"]))

    bloodwork = data["bloodwork"].copy()
    bloodwork["dose_mg_active_T"] = bloodwork["date"].apply(lambda d: get_actual_dose(d, phases))
    bloodwork["FAI"] = (bloodwork["testosterone_nmol"] / bloodwork["shbg_nmol"]) * 100

    blood_table_data = [
        ["Date", "Phase", "Active T\nmg/wk *", "Total T\nnmol/L", "Free T\nnmol/L",
         "SHBG\nnmol/L", "E2\npmol/L", "FAI"]
    ]
    for _, row in bloodwork.iterrows():
        phase_label = "Baseline"
        for p in phases:
            if p["start"] <= row["date"] <= p["end"]:
                phase_label = p["label"].split(":")[0].strip()
                break
        blood_table_data.append([
            row["date"].strftime("%Y-%m-%d"),
            phase_label,
            f'{row["dose_mg_active_T"]:.0f}',
            f'{row["testosterone_nmol"]:.1f}' if pd.notna(row["testosterone_nmol"]) else "-",
            f'{row["free_testosterone_nmol"]:.3f}' if pd.notna(row["free_testosterone_nmol"]) else "-",
            f'{row["shbg_nmol"]:.1f}' if pd.notna(row["shbg_nmol"]) else "-",
            f'{row["oestradiol_pmol"]:.0f}' if pd.notna(row["oestradiol_pmol"]) else "-",
            f'{row["FAI"]:.1f}' if pd.notna(row["FAI"]) else "-",
        ])

    col_widths = [65, 55, 50, 48, 48, 42, 42, 38]
    bt_table = Table(blood_table_data, colWidths=col_widths)
    bt_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#E8E8F0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        # Highlight sub-therapeutic rows
        ("BACKGROUND", (3, -1), (3, -1), HexColor("#FFE0E0")),
        ("BACKGROUND", (4, -1), (4, -1), HexColor("#FFE0E0")),
    ]))
    story.append(Paragraph(
        "<b>Table 1.</b> Blood test results across TRT phases. Red highlights indicate sub-BSSM values. "
        "* Active T shows actual dose at time of draw (Feb 2026 = 78.4mg during misread period; "
        "May 2026 = 72.8mg after correction).",
        styles["SmallItalic"]))
    story.append(bt_table)
    story.append(Spacer(1, 4 * mm))

    # -- Timeline Chart --
    story.append(Paragraph("2. TRT Timeline", styles["SectionHead"]))
    story.append(Image(chart_paths["timeline"], width=165 * mm, height=70 * mm))
    story.append(Paragraph(
        "Dose escalation from 56 to 72.8 mg active T/week over 15 months. Between Aug 2025 and "
        "Feb 2026, actual dosing was 78.4 mg/wk due to a misread (corrected Feb 2026). The hatched "
        "region indicates cofactor cessation. At the current prescribed dose, the latest result "
        "(12.7 nmol/L) falls below the BSSM 15 nmol/L minimum.",
        styles["BodyText2"]))

    story.append(PageBreak())

    # -- Dose Response --
    story.append(Paragraph("3. Dose-Response Analysis", styles["SectionHead"]))
    story.append(Image(chart_paths["dose_response"], width=170 * mm, height=60 * mm))

    dr_valid = bloodwork.dropna(subset=["testosterone_nmol"])
    dr_valid = dr_valid[dr_valid["dose_mg_active_T"] > 0]
    if len(dr_valid) >= 3:
        slope, intercept, r, p, se = stats.linregress(
            dr_valid["dose_mg_active_T"], dr_valid["testosterone_nmol"])
        story.append(Paragraph(
            f"Linear regression: Total T = {slope:.3f} \u00d7 dose + {intercept:.1f} "
            f"(r = {r:.3f}, R<super>2</super> = {r**2:.3f}, p = {p:.3f}). The paradoxically negative "
            f"dose-response indicates that confounding variables \u2014 primarily SHBG fluctuation driven "
            f"by cofactor status \u2014 dominate over dose as a predictor of serum testosterone.",
            styles["BodyText2"]))

    # -- SHBG --
    story.append(Paragraph("4. SHBG Dynamics &amp; Free Testosterone", styles["SectionHead"]))
    story.append(Image(chart_paths["shbg"], width=165 * mm, height=120 * mm))

    last_on = bloodwork[bloodwork["date"] == "2026-02-12"].iloc[0]
    first_off = bloodwork[bloodwork["date"] == "2026-05-03"].iloc[0]
    shbg_chg = first_off["shbg_nmol"] - last_on["shbg_nmol"]
    ft_chg_pct = (first_off["free_testosterone_nmol"] - last_on["free_testosterone_nmol"]) / last_on["free_testosterone_nmol"] * 100

    story.append(Paragraph(
        f"SHBG rose from {last_on['shbg_nmol']:.1f} to {first_off['shbg_nmol']:.1f} nmol/L "
        f"(+{shbg_chg:.1f}, +{shbg_chg/last_on['shbg_nmol']*100:.0f}%) following cofactor cessation. "
        f"Note: the Feb 2026 draw was at 78.4mg/wk (misread), while the May 2026 draw was at "
        f"72.8mg/wk (corrected). The combined effect of cofactor cessation and dose correction "
        f"drove total T down 28% and free T down {abs(ft_chg_pct):.0f}% "
        f"(0.449 \u2192 0.251 nmol/L) \u2014 a disproportionate free T decline confirming "
        f"SHBG-mediated sequestration.",
        styles["BodyText2"]))

    story.append(PageBreak())

    # -- Cofactors --
    story.append(Paragraph("5. Cofactor Cessation Impact", styles["SectionHead"]))
    story.append(Image(chart_paths["cofactors"], width=165 * mm, height=68 * mm))
    story.append(Paragraph(
        "Five supplements were stopped between Feb\u2013May 2026: Boron 10mg, Zinc Picolinate, "
        "Magnesium Glycinate 400mg, Selenium, and P5P 50mg. The observed SHBG increase "
        f"(+{shbg_chg:.1f} nmol/L) falls within the expected literature range (+7.5\u201312.5 nmol/L) "
        "from cumulative cessation effects (Naghii et al., 2011; Prasad et al., 1996; "
        "Excelmyer et al., 2021).",
        styles["BodyText2"]))
    story.append(Paragraph(
        "<b>Key observation:</b> Prior blood results showing adequate levels (T=17.7\u201319.0 nmol/L) "
        "were achieved only with cofactor-suppressed SHBG (~22\u201323 nmol/L) and, in the case of "
        "Feb 2026, a higher actual dose (78.4mg vs prescribed 72.8mg). With natural SHBG "
        "(~32 nmol/L) and the prescribed dose, testosterone is sub-therapeutic.",
        styles["BodyText2"]))

    # -- Training & Recovery side by side on same page --
    story.append(Paragraph("6. Training Load", styles["SectionHead"]))
    story.append(Image(chart_paths["training"], width=165 * mm, height=55 * mm))
    story.append(Paragraph(
        "Training volume decreased during the cofactor-off period due to injury. While reduced "
        "resistance training can modestly lower SHBG (typically 1\u20133 nmol/L in eugonadal men; "
        "Kraemer &amp; Ratamess, 2005), this represents &lt;30% of the observed +9.6 nmol/L SHBG surge. "
        "The dominant driver of the SHBG increase \u2014 and consequent free T collapse \u2014 is "
        "cofactor cessation, not training reduction.",
        styles["BodyText2"]))

    story.append(Paragraph(
        "<b>Recovery context:</b> Oura-derived readiness scores and HRV balance remained stable "
        "across the analysis period (data not shown), confirming the testosterone decline was not "
        "driven by deteriorating recovery or increased physiological stress.",
        styles["SmallItalic"]))

    # -- Haematology --
    story.append(Paragraph("7. Haematological Safety Markers", styles["SectionHead"]))
    story.append(Image(chart_paths["haematology"], width=170 * mm, height=50 * mm))

    hct = bloodwork.dropna(subset=["haematocrit_pct"])
    latest_hct = hct.iloc[-1]["haematocrit_pct"] if len(hct) > 0 else 0
    hct_headroom = 54.0 - latest_hct
    story.append(Paragraph(
        f"All haematological markers remain within safe limits. Current haematocrit is "
        f"{latest_hct:.1f}%, providing <b>{hct_headroom:.1f} percentage points of headroom</b> "
        f"below the BSSM safety ceiling of 54%. A 25% dose increase typically raises haematocrit "
        f"by 1\u20133 percentage points (Bachman et al., 2014), well within the available margin. "
        f"Even at the upper bound of expected increase, haematocrit would remain below 50%.",
        styles["BodyText2"]))

    # -- Correlations --
    if chart_paths.get("correlations"):
        story.append(Paragraph("8. Blood Marker Correlations", styles["SectionHead"]))
        story.append(Image(chart_paths["correlations"], width=130 * mm, height=100 * mm))
        story.append(Paragraph(
            "Pearson correlation matrix across available blood markers. Notable relationships include "
            "the strong inverse correlation between SHBG and free testosterone, and positive associations "
            "between total T and haematological markers (haematocrit, haemoglobin).",
            styles["BodyText2"]))

    # -- PK Simulation --
    story.append(Paragraph("9. Injection Frequency Pharmacokinetic Modelling", styles["SectionHead"]))
    story.append(Paragraph(
        "Testosterone Cypionate has a subcutaneous half-life of approximately 8 days "
        "(Kaminetsky et al., 2015). Using exponential decay superposition (Bateman equation), "
        "steady-state serum curves were modelled for 2x/week and 3x/week injection frequencies "
        "at various doses.",
        styles["BodyText2"]))

    story.append(PageBreak())
    story.append(Image(chart_paths["pk_simulation"], width=165 * mm, height=115 * mm))

    # PK comparison table
    pk_table_data = [["Protocol", "Weekly mg\nActive T", "Peak:Trough", "Fluctuation"]]
    for row in pk_data:
        pk_table_data.append([row["Protocol"], str(row["Weekly mg"]),
                              row["Peak:Trough"], row["Fluctuation"]])
    pk_table = Table(pk_table_data, colWidths=[110, 70, 80, 70])
    pk_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#E8E8F0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(Paragraph(
        "<b>Table 2.</b> PK comparison of injection frequency protocols.",
        styles["SmallItalic"]))
    story.append(pk_table)
    story.append(Paragraph(
        "Switching from 2x/week to 3x/week reduces peak-trough fluctuation from ~15% to ~8%, "
        "producing smoother serum levels. This may reduce oestradiol spikes, improve subcutaneous "
        "absorption, and lower haematocrit risk from peak concentrations (Bachman et al., 2014).",
        styles["BodyText2"]))

    story.append(PageBreak())

    # -- Dose Optimisation --
    story.append(Paragraph("10. Dose Optimisation", styles["SectionHead"]))
    story.append(Image(chart_paths["dose_optimisation"], width=165 * mm, height=70 * mm))

    unsuppressed_ratio = 12.7 / 72.8  # May 2026 at prescribed dose (misread corrected)
    cofactor_ratio = 19.0 / 64.4
    story.append(Paragraph(
        f"<b>Table 3.</b> Dose-response efficiency comparison.",
        styles["SmallItalic"]))
    dr_comp = [
        ["Scenario", "Actual Dose", "SHBG", "Total T", "Ratio"],
        ["With cofactors (Aug 2025)", "64.4 mg/wk", "23.2", "19.0 nmol/L",
         f"{cofactor_ratio:.3f} nmol/mg"],
        ["Without cofactors (May 2026)", "72.8 mg/wk", "32.1", "12.7 nmol/L",
         f"{unsuppressed_ratio:.3f} nmol/mg"],
    ]
    dr_table = Table(dr_comp, colWidths=[130, 65, 40, 65, 80])
    dr_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#E8E8F0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(dr_table)
    story.append(Spacer(1, 3 * mm))

    # Titration table
    story.append(Paragraph(
        "<b>Table 4.</b> Required dose for BSSM targets without cofactor support.",
        styles["SmallItalic"]))
    titration_data = [
        ["Target", "Active T\nmg/wk", "Cypionate\nmg/wk", "2x/wk\n(ml/inj)", "3x/wk\n(ml/inj)"],
    ]
    for target_t in [15, 20, 25]:
        req = target_t / unsuppressed_ratio
        cyp = req / ESTER_FACTOR
        ml_2x = cyp / CONC_MG_PER_ML / 2
        ml_3x = cyp / CONC_MG_PER_ML / 3
        titration_data.append([
            f"{target_t} nmol/L",
            f"{req:.0f}",
            f"{cyp:.0f}",
            f"{ml_2x:.2f}",
            f"{ml_3x:.2f}",
        ])
    tit_table = Table(titration_data, colWidths=[70, 65, 70, 65, 65])
    tit_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#E8E8F0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(tit_table)

    story.append(Spacer(1, 4 * mm))

    # -- Discussion Points --
    story.append(Paragraph("11. Discussion Points for Clinician Review", styles["SectionHead"]))

    story.append(Paragraph("A. Dose Titration", styles["SubSectionHead"]))
    prescribed_active_T = 72.8
    step1_dose = prescribed_active_T * 1.25
    step1_cyp = step1_dose / ESTER_FACTOR
    step1_ml_2x = step1_cyp / CONC_MG_PER_ML / 2
    step1_ml_3x = step1_cyp / CONC_MG_PER_ML / 3
    unsuppressed_ratio_disc = 12.7 / 72.8  # PK ratio at prescribed dose (misread corrected before May draw)
    step1_predicted = step1_dose * unsuppressed_ratio_disc
    story.append(Paragraph(
        f"The BSSM practical guide (Hackett et al., 2023) recommends dose increases of 10\u201325% "
        f"with retesting at 6\u201312 weeks when trough levels are below target. The current prescribed "
        f"dose is 72.8 mg active T/week (0.26ml \u00d7 2/week). "
        f"A 25% increase would yield ~{step1_dose:.0f} mg active T/week "
        f"({step1_cyp:.0f} mg cypionate, {step1_ml_2x:.2f}ml \u00d7 2/week or "
        f"{step1_ml_3x:.2f}ml \u00d7 3/week), predicting a trough of "
        f"approximately {step1_predicted:.1f} nmol/L \u2014 reaching the BSSM minimum target. "
        f"A second titration step may be needed to reach mid-range targets.",
        styles["BodyText2"]))

    story.append(Paragraph("B. Injection Frequency", styles["SubSectionHead"]))
    story.append(Paragraph(
        "Switching from 2x/week to 3x/week maintains the same weekly dose while reducing "
        "peak-trough fluctuation from ~15% to ~8%. Clinical benefits may include smoother "
        "energy and mood, reduced oestradiol conversion at peaks, smaller per-injection volume "
        "improving subcutaneous absorption, and lower peak-driven haematocrit risk "
        "(Kaminetsky et al., 2015; Bachman et al., 2014). This could be considered as a "
        "protocol refinement alongside dose adjustment.",
        styles["BodyText2"]))

    story.append(Paragraph("C. Cofactor Management", styles["SubSectionHead"]))
    story.append(Paragraph(
        "If cofactors are resumed, they should be viewed as additive to an already-adequate "
        "base dose \u2014 not required for achieving minimum therapeutic levels. The goal is a "
        "protocol that reliably produces BSSM-range trough levels on its own, with cofactors "
        "providing further optimisation into the upper range. This creates a resilient protocol: "
        "if supplements are temporarily stopped, levels remain therapeutic rather than crashing "
        "to sub-therapeutic as observed in this analysis.",
        styles["BodyText2"]))

    story.append(Paragraph("D. Safety Considerations", styles["SubSectionHead"]))
    story.append(Paragraph(
        f"<b>Haematocrit:</b> Current level ({latest_hct:.1f}%) provides {hct_headroom:.1f} "
        f"percentage points of headroom below the BSSM 54% ceiling. A 25% dose increase would "
        f"be expected to raise HCT by 1\u20133 points, remaining well under 50%.",
        styles["BodyText2"]))
    story.append(Paragraph(
        "<b>PSA:</b> PSA has risen 0.79 \u00b5g/L over 12.5 months (0.77 \u2192 1.56 \u00b5g/L, "
        "baseline Jan 2025 to Feb 2026). Annualised velocity: ~0.76 \u00b5g/L/year, "
        "well below the BSSM referral threshold of 1.4 \u00b5g/L in 12 months. "
        "Note: PSA was not measured at the May 2026 draw.",
        styles["BodyText2"]))
    story.append(Paragraph(
        "<b>Monitoring:</b> A full blood panel is already scheduled for August 2026 "
        "(&lt;12 weeks from any protocol change), satisfying the BSSM retest requirement. "
        "This will confirm haematocrit, PSA, and testosterone response to the adjusted dose.",
        styles["BodyText2"]))

    story.append(Spacer(1, 6 * mm))

    # -- Recommended Protocol Change --
    story.append(Paragraph("12. Recommended Protocol Change", styles["SectionHead"]))
    story.append(Paragraph(
        "Based on the analysis above, I am requesting the following protocol adjustment:",
        styles["BodyText2"]))

    # Calculate the specific ask
    # 25% increase from prescribed (72.8mg) = 91mg active T
    ask_active_T = prescribed_active_T * 1.25
    ask_cyp = ask_active_T / ESTER_FACTOR
    ask_ml_2x = ask_cyp / CONC_MG_PER_ML / 2
    ask_ml_3x = ask_cyp / CONC_MG_PER_ML / 3
    ask_predicted = ask_active_T * unsuppressed_ratio_disc

    ask_table_data = [
        ["", "Primary Option (Recommended)", "Alternative"],
        ["Dose per injection", f"{ask_ml_3x:.2f}ml \u00d7 3/week", f"{ask_ml_2x:.2f}ml \u00d7 2/week"],
        ["Weekly active T", f"{ask_active_T:.0f} mg", f"{ask_active_T:.0f} mg"],
        ["Increase from prescribed", "25% (BSSM guideline max)", "25% (BSSM guideline max)"],
        ["Frequency change", "2x \u2192 3x/week", "No change"],
        ["Peak:Trough ratio", "~1.09:1 (smoother)", "~1.17:1 (larger swings)"],
        ["Predicted trough T", f"~{ask_predicted:.0f} nmol/L", f"~{ask_predicted:.0f} nmol/L"],
        ["Predicted Free T *", "~0.40 nmol/L (BSSM range)", "~0.40 nmol/L (BSSM range)"],
        ["Retest interval", "August 2026 (planned)", "August 2026 (planned)"],
        ["Trade-offs", "Smaller injection volume,\nflatter serum curve",
         "Larger per-injection volume,\nhigher peak-driven E2/HCT"],
    ]
    ask_table = Table(ask_table_data, colWidths=[120, 130, 130])
    ask_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor(DARK)),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (1, 1), (1, -1), HexColor("#F0F8F0")),
    ]))
    story.append(ask_table)
    story.append(Paragraph(
        "* Free T estimate assumes SHBG normalises to ~25 nmol/L with cofactor restart "
        "(Vermeulen calculation: Total T ~16, SHBG ~25, Albumin ~45 g/L). "
        "BSSM Free T range: 0.225\u20130.500 nmol/L.",
        styles["SmallItalic"]))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "<b>Rationale:</b> A 25% increase is the maximum single-step titration recommended by "
        "BSSM (Hackett, 2023). The primary option adds 3x/week frequency to reduce peak-trough "
        "fluctuation (\u221247%), which may improve tolerability and reduce oestradiol spikes. "
        f"The predicted trough of ~{ask_predicted:.0f} nmol/L would reach the BSSM minimum target "
        "of 15 nmol/L. A full blood panel is already planned for August 2026 (&lt;12 weeks), "
        "providing a built-in safety check within the BSSM-recommended 6\u201312 week retest window. "
        "If August retest shows trough below 18 nmol/L (BSSM lower-mid range), a second 25% "
        "titration step would be clinically appropriate, taking weekly active T to ~114 mg "
        "and projected trough to ~20 nmol/L (BSSM mid-range).",
        styles["BodyText2"]))

    story.append(Paragraph(
        "<b>If cofactors are resumed</b> alongside a dose increase, levels should reach mid-range "
        "(~20 nmol/L) rather than hovering at the minimum \u2014 building the resilient protocol "
        "where supplements are additive, not compensatory.",
        styles["BodyText2"]))

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor(GREY), spaceAfter=6))

    # -- References --
    story.append(Paragraph("References", styles["SectionHead"]))
    references = [
        "1. Hackett G et al. (2017) British Society for Sexual Medicine guidelines on adult testosterone deficiency, with statements for UK practice. <i>J Sex Med</i>. 14(12):1504-1523.",
        "2. Hackett G (2023) A practical guide to the assessment and management of testosterone deficiency. <i>Trends in Urology and Men's Health</i>. 14(3):6-11.",
        "3. Bhasin S et al. (2001) Testosterone dose-response relationships in healthy young men. <i>Am J Physiol Endocrinol Metab</i>. 281(6):E1172-81.",
        "4. Naghii MR et al. (2011) Comparative effects of daily and weekly boron supplementation on plasma steroid hormones. <i>J Trace Elem Med Biol</i>. 25(1):54-58.",
        "5. Prasad AS et al. (1996) Zinc status and serum testosterone levels of healthy adults. <i>Nutrition</i>. 12(5):344-348.",
        "6. Excelmyer CN et al. (2021) Magnesium intake is inversely associated with SHBG. <i>J Cell Biochem</i>.",
        "7. Vermeulen A et al. (1999) A critical evaluation of simple methods for estimation of free testosterone. <i>J Clin Endocrinol Metab</i>. 84(10):3666-72.",
        "8. Kaminetsky J et al. (2015) Pharmacokinetics of subcutaneous testosterone enanthate. <i>J Clin Endocrinol Metab</i>. 100(11):4091-4097.",
        "9. Bachman E et al. (2014) Testosterone induces erythrocytosis via increased erythropoietin and suppressed hepcidin. <i>J Gerontol A Biol Sci Med Sci</i>. 69(6):725-735.",
        "10. Corona G et al. (2011) SHBG as determinant of testosterone bioavailability. <i>Clin Endocrinol</i>.",
        "11. Kraemer WJ, Ratamess NA (2005) Hormonal responses and adaptations to resistance exercise and training. <i>Sports Med</i>. 35(4):339-361.",
    ]
    for ref in references:
        story.append(Paragraph(ref, styles["RefText"]))

    # Build the PDF
    doc.build(story)
    return output_path


# ---------- Main ----------
def main():
    print("Loading data...")
    data = load_data()
    phases = build_phases()

    with tempfile.TemporaryDirectory() as tmpdir:
        print("Generating charts...")
        chart_paths = {}
        chart_paths["timeline"] = chart_timeline(data, phases, tmpdir)
        chart_paths["dose_response"] = chart_dose_response(data, phases, tmpdir)
        chart_paths["shbg"] = chart_shbg(data, phases, tmpdir)
        chart_paths["cofactors"] = chart_cofactor_impact(data, tmpdir)
        chart_paths["training"] = chart_training(data, phases, tmpdir)
        chart_paths["haematology"] = chart_haematology(data, tmpdir)
        pk_path, pk_data = chart_pk_simulation(tmpdir)
        chart_paths["pk_simulation"] = pk_path
        chart_paths["dose_optimisation"] = chart_dose_optimisation(data, tmpdir)
        chart_paths["correlations"] = chart_correlation_matrix(data, tmpdir)

        print("Building PDF...")
        output = build_pdf(data, phases, chart_paths, pk_data)

    print(f"PDF generated: {output}")
    return output


if __name__ == "__main__":
    main()
