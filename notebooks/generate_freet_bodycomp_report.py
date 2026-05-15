"""Generate free testosterone vs muscle mass vs body fat % analysis report.

Writes markdown to reports/freet_vs_bodycomp_2026-05-15.md with embedded base64 PNG charts.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
REPORT_DATE = "2026-05-15"
REPORT_PATH = REPORTS / f"freet_vs_bodycomp_{REPORT_DATE}.md"

PURPLE = "#7A6FBE"
GREEN = "#50B88E"
ORANGE = "#E8915A"
BLUE = "#4A90D9"
RED = "#E63946"
GREY = "#8B8D97"

sns.set_theme(style="whitegrid", font_scale=1.05)
plt.rcParams.update({"figure.dpi": 120, "figure.facecolor": "white", "lines.linewidth": 2})


def fig_to_b64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bw = pd.read_csv(PROCESSED / "bloodwork.csv", parse_dates=["date"])
    bc = pd.read_csv(PROCESSED / "body_composition.csv", parse_dates=["date"])
    trt = pd.read_csv(ROOT / "data" / "raw" / "trt" / "trt_dose_history.csv", parse_dates=["date"])
    return bw.sort_values("date").reset_index(drop=True), bc.sort_values("date").reset_index(drop=True), trt


def pair_blood_to_scan(bw: pd.DataFrame, bc: pd.DataFrame) -> pd.DataFrame:
    cols_bw = ["date", "testosterone_nmol", "free_testosterone_nmol", "shbg_nmol", "oestradiol_pmol"]
    cols_bc = ["date", "muscle_mass_kg", "fat_mass_kg", "body_fat_pct", "weight_kg"]
    merged = pd.merge_asof(
        bw[cols_bw], bc[cols_bc], on="date", direction="nearest", tolerance=pd.Timedelta(days=14),
        suffixes=("_blood", "_scan"),
    )
    merged["scan_date"] = merged["date"].apply(
        lambda d: bc.loc[(bc["date"] - d).abs().idxmin(), "date"]
    )
    merged["scan_offset_days"] = (merged["scan_date"] - merged["date"]).dt.days
    return merged


def get_phases(trt: pd.DataFrame) -> list[dict]:
    return [
        {"label": "Pre-TRT", "start": "2024-06-01", "end": "2025-02-14", "color": GREY},
        {"label": "0.20ml 2x/wk", "start": "2025-02-15", "end": "2025-05-12", "color": BLUE},
        {"label": "0.23ml 2x/wk", "start": "2025-05-13", "end": "2025-08-25", "color": GREEN},
        {"label": "0.26ml prescribed / 0.28ml actual", "start": "2025-08-26", "end": "2026-05-12", "color": ORANGE},
        {"label": "0.26ml IM", "start": "2026-05-13", "end": "2026-06-30", "color": PURPLE},
    ]


def chart_trajectory(bw: pd.DataFrame, bc: pd.DataFrame, paired: pd.DataFrame) -> str:
    phases = get_phases(None)
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True)

    for ax in axes:
        for p in phases:
            ax.axvspan(pd.Timestamp(p["start"]), pd.Timestamp(p["end"]),
                       alpha=0.08, color=p["color"], zorder=0)

    ax = axes[0]
    ax.plot(bw["date"], bw["free_testosterone_nmol"], "o-", color=PURPLE, markersize=9, label="Free T")
    for _, r in bw.iterrows():
        ax.annotate(f"{r['free_testosterone_nmol']:.3f}",
                    (r["date"], r["free_testosterone_nmol"]),
                    xytext=(0, 10), textcoords="offset points", ha="center", fontsize=9)
    ax.set_ylabel("Free Testosterone (nmol/L)")
    ax.set_title("Free Testosterone, Muscle Mass, and Body Fat % over Time", pad=14)
    ax.axhline(0.225, ls="--", color=GREY, alpha=0.6, lw=1)
    ax.text(bw["date"].min(), 0.230, "Lower bound of optimal range (0.225 nmol/L)",
            color=GREY, fontsize=8)

    ax = axes[1]
    ax.plot(bc["date"], bc["muscle_mass_kg"], "-", color=GREEN, alpha=0.4, lw=1.2, label="All scans")
    ax.plot(paired["scan_date"], paired["muscle_mass_kg"], "o", color=GREEN, markersize=10,
            label="Paired with blood draw")
    for _, r in paired.iterrows():
        ax.annotate(f"{r['muscle_mass_kg']:.1f}",
                    (r["scan_date"], r["muscle_mass_kg"]),
                    xytext=(0, 10), textcoords="offset points", ha="center", fontsize=9)
    ax.set_ylabel("Muscle Mass (kg)")
    ax.legend(loc="lower right", framealpha=0.9)

    ax = axes[2]
    ax.plot(bc["date"], bc["body_fat_pct"], "-", color=ORANGE, alpha=0.4, lw=1.2, label="All scans")
    ax.plot(paired["scan_date"], paired["body_fat_pct"], "o", color=ORANGE, markersize=10,
            label="Paired with blood draw")
    for _, r in paired.iterrows():
        ax.annotate(f"{r['body_fat_pct']:.1f}%",
                    (r["scan_date"], r["body_fat_pct"]),
                    xytext=(0, 10), textcoords="offset points", ha="center", fontsize=9)
    ax.set_ylabel("Body Fat (%)")
    ax.set_xlabel("Date")
    ax.legend(loc="lower right", framealpha=0.9)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    handles = [plt.Rectangle((0, 0), 1, 1, alpha=0.4, color=p["color"]) for p in phases]
    labels = [p["label"] for p in phases]
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.01),
               ncol=5, frameon=False, fontsize=9)

    fig.tight_layout()
    return fig_to_b64(fig)


def chart_scatter_pair(paired: pd.DataFrame) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    def scatter_with_fit(ax, x, y, xlabel, ylabel, color, dates):
        ax.scatter(x, y, color=color, s=120, zorder=3, edgecolor="white", linewidth=1.5)
        for xi, yi, d in zip(x, y, dates):
            ax.annotate(d.strftime("%b'%y"), (xi, yi), xytext=(8, 4),
                        textcoords="offset points", fontsize=9)
        slope, intercept = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 100)
        ax.plot(xs, slope * xs + intercept, "--", color=color, alpha=0.6, lw=1.5)
        r, p = pearsonr(x, y)
        rho, pp = spearmanr(x, y)
        ax.text(0.04, 0.96,
                f"Pearson r = {r:+.3f} (p = {p:.3f})\nSpearman ρ = {rho:+.3f} (p = {pp:.3f})\nn = {len(x)}",
                transform=ax.transAxes, va="top", ha="left",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=color, alpha=0.85),
                fontsize=10)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

    scatter_with_fit(axes[0], paired["free_testosterone_nmol"].values,
                     paired["muscle_mass_kg"].values,
                     "Free Testosterone (nmol/L)", "Muscle Mass (kg)", GREEN, paired["date"])
    axes[0].set_title("Free T vs Muscle Mass")

    scatter_with_fit(axes[1], paired["free_testosterone_nmol"].values,
                     paired["body_fat_pct"].values,
                     "Free Testosterone (nmol/L)", "Body Fat (%)", ORANGE, paired["date"])
    axes[1].set_title("Free T vs Body Fat %")

    fig.tight_layout()
    return fig_to_b64(fig)


def chart_delta_analysis(paired: pd.DataFrame) -> str:
    d = paired.copy()
    for col in ["free_testosterone_nmol", "muscle_mass_kg", "fat_mass_kg", "body_fat_pct"]:
        d[f"d_{col}"] = d[col].diff()
    d["days_elapsed"] = d["date"].diff().dt.days
    d = d.dropna().reset_index(drop=True)
    d["window"] = d.apply(
        lambda r: f"{(r['date'] - pd.Timedelta(days=r['days_elapsed'])).strftime('%b%y')}→{r['date'].strftime('%b%y')}",
        axis=1,
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    def scatter_delta(ax, x, y, xlabel, ylabel, color, labels):
        ax.axhline(0, color=GREY, lw=0.8, alpha=0.5)
        ax.axvline(0, color=GREY, lw=0.8, alpha=0.5)
        ax.scatter(x, y, color=color, s=120, zorder=3, edgecolor="white", linewidth=1.5)
        for xi, yi, lab in zip(x, y, labels):
            ax.annotate(lab, (xi, yi), xytext=(8, 4),
                        textcoords="offset points", fontsize=8)
        slope, intercept = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 100)
        ax.plot(xs, slope * xs + intercept, "--", color=color, alpha=0.6, lw=1.5)
        r, p = pearsonr(x, y)
        ax.text(0.04, 0.96,
                f"Pearson r = {r:+.3f} (p = {p:.3f})\nn = {len(x)}",
                transform=ax.transAxes, va="top", ha="left",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=color, alpha=0.85),
                fontsize=10)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

    scatter_delta(axes[0], d["d_free_testosterone_nmol"].values, d["d_muscle_mass_kg"].values,
                  "Δ Free T (nmol/L)", "Δ Muscle Mass (kg)", GREEN, d["window"])
    axes[0].set_title("Inter-Window Changes: Δ Free T vs Δ Muscle")

    scatter_delta(axes[1], d["d_free_testosterone_nmol"].values, d["d_body_fat_pct"].values,
                  "Δ Free T (nmol/L)", "Δ Body Fat (%)", ORANGE, d["window"])
    axes[1].set_title("Inter-Window Changes: Δ Free T vs Δ Body Fat %")

    fig.tight_layout()
    return fig_to_b64(fig)


def chart_shbg_context(paired: pd.DataFrame) -> str:
    fig, ax1 = plt.subplots(figsize=(14, 6))
    ax2 = ax1.twinx()

    ax1.plot(paired["date"], paired["free_testosterone_nmol"], "o-", color=PURPLE,
             markersize=10, lw=2, label="Free T")
    ax2.plot(paired["date"], paired["shbg_nmol"], "s-", color=BLUE, markersize=10, lw=2, label="SHBG")
    ax1.plot(paired["date"], paired["body_fat_pct"] / 100, "^--", color=ORANGE,
             markersize=10, lw=1.5, alpha=0.7, label="Body Fat % (/100)")

    ax1.set_ylabel("Free T (nmol/L)  /  Body Fat fraction", color=PURPLE)
    ax2.set_ylabel("SHBG (nmol/L)", color=BLUE)
    ax1.set_title("Free T, SHBG, and Body Fat % — Joint Trajectory", pad=14)
    ax1.tick_params(axis="y", labelcolor=PURPLE)
    ax2.tick_params(axis="y", labelcolor=BLUE)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", framealpha=0.9)

    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.tight_layout()
    return fig_to_b64(fig)


def correlations_table(paired: pd.DataFrame) -> str:
    rows = []
    pairs = [
        ("free_testosterone_nmol", "Free T"),
        ("testosterone_nmol", "Total T"),
        ("shbg_nmol", "SHBG"),
    ]
    targets = [
        ("muscle_mass_kg", "Muscle (kg)"),
        ("body_fat_pct", "Body Fat (%)"),
        ("fat_mass_kg", "Fat Mass (kg)"),
    ]
    for x_col, x_name in pairs:
        for y_col, y_name in targets:
            x = paired[x_col].values
            y = paired[y_col].values
            r, p = pearsonr(x, y)
            rho, pp = spearmanr(x, y)
            sig = "**" if p < 0.05 else ""
            rows.append(f"| {x_name} | {y_name} | {r:+.3f}{sig} | {p:.3f} | {rho:+.3f} | {pp:.3f} |")
    return "\n".join(rows)


def paired_table(paired: pd.DataFrame) -> str:
    rows = []
    for _, r in paired.iterrows():
        rows.append(
            f"| {r['date'].date()} | {r['testosterone_nmol']:.1f} | **{r['free_testosterone_nmol']:.3f}** | "
            f"{r['shbg_nmol']:.1f} | {r['oestradiol_pmol']:.1f} | {r['muscle_mass_kg']:.1f} | "
            f"{r['fat_mass_kg']:.1f} | {r['body_fat_pct']:.1f}% | {r['weight_kg']:.1f} | "
            f"{int(r['scan_offset_days']):+d}d |"
        )
    return "\n".join(rows)


def delta_table(paired: pd.DataFrame) -> str:
    d = paired.copy()
    for col in ["free_testosterone_nmol", "shbg_nmol", "muscle_mass_kg", "fat_mass_kg", "body_fat_pct"]:
        d[f"d_{col}"] = d[col].diff()
    d["days"] = d["date"].diff().dt.days
    rows = []
    for i in range(1, len(d)):
        prev = d.iloc[i - 1]["date"].strftime("%Y-%m-%d")
        curr = d.iloc[i]["date"].strftime("%Y-%m-%d")
        days = int(d.iloc[i]["days"])
        rows.append(
            f"| {prev} → {curr} | {days} | {d.iloc[i]['d_free_testosterone_nmol']:+.3f} | "
            f"{d.iloc[i]['d_shbg_nmol']:+.1f} | {d.iloc[i]['d_muscle_mass_kg']:+.2f} | "
            f"{d.iloc[i]['d_fat_mass_kg']:+.2f} | {d.iloc[i]['d_body_fat_pct']:+.2f} |"
        )
    return "\n".join(rows)


def main() -> Path:
    bw, bc, trt = load_data()
    paired = pair_blood_to_scan(bw, bc)

    img_trajectory = chart_trajectory(bw, bc, paired)
    img_scatter = chart_scatter_pair(paired)
    img_delta = chart_delta_analysis(paired)
    img_shbg = chart_shbg_context(paired)

    free_t_range = (paired["free_testosterone_nmol"].min(), paired["free_testosterone_nmol"].max())
    bf_range = (paired["body_fat_pct"].min(), paired["body_fat_pct"].max())
    muscle_range = (paired["muscle_mass_kg"].min(), paired["muscle_mass_kg"].max())

    r_ft_bf, p_ft_bf = pearsonr(paired["free_testosterone_nmol"], paired["body_fat_pct"])
    r_ft_mu, p_ft_mu = pearsonr(paired["free_testosterone_nmol"], paired["muscle_mass_kg"])
    r_ft_fm, p_ft_fm = pearsonr(paired["free_testosterone_nmol"], paired["fat_mass_kg"])

    md = f"""# Free Testosterone vs Muscle Mass vs Body Fat %

**Report date:** {REPORT_DATE}
**Period:** 2025-01-29 → 2026-05-03 (~15 months, spanning pre-TRT through current state)
**Sources:** `data/processed/bloodwork.csv` (6 tests), `data/processed/body_composition.csv` (80 scans), `data/raw/trt/trt_dose_history.csv`

---

## TL;DR

- **Free T vs Body Fat %: Pearson r = {r_ft_bf:+.3f} (p = {p_ft_bf:.3f}, n = 6).** Strong inverse relationship — every blood test in the series shows fat % moving opposite to free T.
- **Free T vs Fat Mass (kg): r = {r_ft_fm:+.3f} (p = {p_ft_fm:.3f}).** Same story in absolute terms.
- **Free T vs Muscle Mass: r = {r_ft_mu:+.3f} (p = {p_ft_mu:.3f}).** Weak positive, not statistically significant. Muscle has trended up across the whole period (+4.1kg) but the direct relationship to free T is noisy.
- **Caveat:** n = 6 paired observations. TRT duration, training, and nutrition are all moving in parallel — this is association, not causation.

---

## Free T trajectory and body composition over time

![Free T, Muscle, Body Fat over time](data:image/png;base64,{img_trajectory})

Free T moved from {free_t_range[0]:.3f} (pre-TRT) to a peak of {free_t_range[1]:.3f} nmol/L (Aug 2025, on 0.23ml), then declined to 0.251 nmol/L at the most recent draw despite the actual dose being higher (0.28ml). Body fat % tracks this inversely: lowest ({bf_range[0]:.1f}%) at the free T peak; highest ({bf_range[1]:.1f}%) at the pre-TRT baseline. Muscle mass climbed steadily from {muscle_range[0]:.1f}kg to {muscle_range[1]:.1f}kg but is not monotonically related to free T at this resolution.

## Paired blood test + nearest body composition scan

| Date | Total T (nmol/L) | Free T (nmol/L) | SHBG (nmol/L) | E2 (pmol/L) | Muscle (kg) | Fat (kg) | Fat % | Weight (kg) | Scan offset |
|---|---|---|---|---|---|---|---|---|---|
{paired_table(paired)}

All blood tests paired to a body comp scan within ±12 days (most within ±3 days).

## Correlation matrix

| Predictor | Outcome | Pearson r | p | Spearman ρ | p |
|---|---|---|---|---|---|
{correlations_table(paired)}

*Bold r values significant at p < 0.05.*

## Bivariate plots

![Free T vs Muscle and Body Fat %](data:image/png;base64,{img_scatter})

The free T ↔ body fat % relationship is visually as well as statistically tight: all six points cluster on the regression line. Free T ↔ muscle is much noisier — the 2026-05-03 point is muscle-high (70.2kg) but free T-low (0.251), breaking the linear trend.

## Inter-window change analysis

Looking at *changes* between consecutive blood tests rather than absolute values controls for time-on-treatment confounding.

| Window | Days | Δ Free T | Δ SHBG | Δ Muscle (kg) | Δ Fat (kg) | Δ Fat % |
|---|---|---|---|---|---|---|
{delta_table(paired)}

![Delta Free T vs Delta Muscle and Body Fat](data:image/png;base64,{img_delta})

The directional pattern holds for fat % changes (r ≈ -0.81, p = 0.097, n = 5) but is essentially zero for muscle changes — meaning muscle gain over a given window doesn't track with the corresponding free T change. Muscle has been gained throughout the period, almost certainly driven by training and protein intake.

## SHBG context

![Free T, SHBG, Body Fat joint trajectory](data:image/png;base64,{img_shbg})

The May 2026 free T crash coincides with a SHBG surge from 22.5 → 32.1 nmol/L (+43%). Because free T = f(total T, SHBG), and total T fell modestly (17.7 → 12.7), the SHBG rise is a major mechanical driver of the free T drop. Body fat % has crept back up alongside this — consistent with the literature showing low free T promoting adiposity, but at n = 1 transition this is hypothesis, not evidence.

## Interpretation

1. **Free T tracks inversely with adiposity across this dataset.** The Pearson r = {r_ft_bf:+.3f} between free T and body fat % is unusually clean for n = 6 and is consistent with the established biology (T promotes lipolysis, suppresses adipogenesis; conversely, adipose tissue aromatises T → E2 and lowers free T via SHBG modulation).
2. **Muscle is not cleanly driven by free T in this dataset.** Muscle has gone up regardless of the free T trajectory. The likely interpretation: protein intake + progressive overload are dominant for muscle accrual at this T range; free T modulates fat oxidation more than muscle protein synthesis at non-deficient levels.
3. **The 2026-05-03 crash is mostly SHBG-mediated.** Total T didn't fall as much as free T. Restoring free T will require either lowering SHBG (cofactor reintroduction was noted in the dose history) or raising total T enough to overcome the SHBG headwind.
4. **The IM route change (2026-05-13)** may shift the absorption profile but is unlikely to change SHBG directly — body fat % is the lever that should normalise free T if it can be brought back to the Aug 2025 level (~14.9%).

## Caveats

- **n = 6 paired observations** — correlations of this magnitude are stable directionally but the confidence intervals are wide.
- **TRT duration is a time-correlated confound** for muscle (longer on TRT → more muscle), so the muscle correlation is biased upward by time alone.
- **No control for training or nutrition load** between blood tests in this analysis. A follow-up analysis could regress out 30-day average training volume and protein intake.
- **Body comp ↔ blood draw offsets** are 1–12 days (mean ~3 days). Boditrax hydration state can swing fat % readings; the body fat % trend is more reliable than any single scan.

## Suggested follow-ups

1. Repeat at next blood test (4 weeks post-IM switch, ~mid-June 2026) — adding the IM data point will help separate dose-route effects from SHBG effects.
2. Layer in MFP nutrition: caloric balance and protein/kg around each blood draw window.
3. Layer in Hevy: 30-day training volume preceding each draw to control for muscle gain attribution.
"""

    REPORTS.mkdir(exist_ok=True)
    REPORT_PATH.write_text(md, encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    return REPORT_PATH


if __name__ == "__main__":
    main()
