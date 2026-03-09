# Dashboard Business Rules — Health & Fitness Monitoring
**Profile:** Dean Harris | 50yo | 191cm | TRT-Optimised | Clean Bulk Phase  
**Last Updated:** March 2026  
**Version:** 1.0

---

## Rule Architecture

Each rule follows this structure:

```
RULE_ID | Metric | Condition | Severity | Intervention | Review Cadence
```

**Severity Levels:**
- 🟢 `GREEN` — Within optimal range, no action required
- 🟡 `AMBER` — Monitor closely, prepare intervention
- 🔴 `RED` — Immediate action required
- ⚫ `CRITICAL` — Stop protocol, seek medical review

---

## Domain 1: Blood Panel — Hormonal

### BR-H01 | Total Testosterone
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| ≥ 20 nmol/L | 🟢 GREEN | Maintain current dose |
| 15–19.9 nmol/L | 🟡 AMBER | Review timing of blood draw; confirm pre-injection trough sample |
| 12–14.9 nmol/L | 🔴 RED | Contact Manual clinic — discuss dose adjustment |
| < 12 nmol/L | ⚫ CRITICAL | Contact Manual clinic immediately |

**Notes:** Current = 17.7 nmol/L (AMBER). Context: drawn ~10 AM post-exercise, not a true trough. Trough (pre-injection Monday AM) likely lower. Next draw should be standardised to pre-injection fasted morning.

---

### BR-H02 | Free Testosterone
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| > 0.50 nmol/L | 🟢 GREEN | Maintain |
| 0.40–0.50 nmol/L | 🟡 AMBER | Check SHBG trend; consider boron optimisation |
| 0.30–0.39 nmol/L | 🔴 RED | Review SHBG, dose timing, discuss with clinic |
| < 0.30 nmol/L | ⚫ CRITICAL | Clinical review required |

**Notes:** Current = 0.449 nmol/L (AMBER). If SHBG rises, free T will drop independent of total T.

---

### BR-H03 | Oestradiol (E2)
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| 100–150 pmol/L | 🟢 GREEN | Optimal — maintain |
| 75–99 pmol/L | 🟡 AMBER | Monitor libido, joint comfort, mood; may be suboptimal |
| 150–200 pmol/L | 🟡 AMBER | Watch for bloating, nipple sensitivity, mood changes |
| < 75 pmol/L | 🔴 RED | Risk: joint pain, low libido, mood depression — clinical review |
| > 200 pmol/L | 🔴 RED | Risk: gynecomastia, water retention — clinical review |

**Notes:** Current = 86.8 pmol/L (AMBER — trending low). Previous was 117 pmol/L. Decline of 26% since last panel. Supports case for dose increase. Do NOT use AI (aromatase inhibitor) without clinical direction.

---

### BR-H04 | SHBG
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| 18–30 nmol/L | 🟢 GREEN | Optimal free testosterone bioavailability |
| 30–40 nmol/L | 🟡 AMBER | Consider boron 6–10mg/day; recheck in 6–8 weeks |
| > 40 nmol/L | 🔴 RED | Clinical review; high SHBG binding excess testosterone |
| < 18 nmol/L | 🟡 AMBER | Monitor — very low SHBG can indicate insulin resistance |

**Notes:** Current = 22.5 nmol/L (🟢 GREEN). Trending down from 23.2 — boron likely contributing. Continue monitoring.

---

### BR-H05 | Prolactin
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| < 100 mIU/L | 🟢 GREEN | Optimal |
| 100–200 mIU/L | 🟡 AMBER | Monitor libido and sexual function; recheck in 3 months |
| 200–350 mIU/L | 🔴 RED | Clinical review — elevated prolactin suppresses libido and testosterone effect |
| > 350 mIU/L | ⚫ CRITICAL | Rule out prolactinoma — urgent GP/endocrinology referral |

**Notes:** Current = 116 mIU/L (🟡 AMBER, but significantly improved from 210 mIU/L). Trajectory is positive. Ashwagandha and stress reduction likely contributing. Target < 100.

---

## Domain 2: Blood Panel — TRT Safety

### BR-S01 | PSA (Prostate-Specific Antigen)
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| < 1.5 ng/mL | 🟢 GREEN | Maintain 6-monthly monitoring |
| 1.5–2.5 ng/mL | 🟡 AMBER | Continue 6-monthly; track velocity closely |
| 2.5–3.5 ng/mL | 🔴 RED | Increase to 3-monthly monitoring; clinical review |
| > 3.5 ng/mL | ⚫ CRITICAL | Stop TRT protocol adjustment; urgent urology referral |

**Velocity Sub-Rule (BR-S01a):**
| Annual Velocity | Severity | Intervention |
|----------------|----------|--------------|
| < 0.50 ng/mL/yr | 🟢 GREEN | Expected TRT stabilisation |
| 0.50–0.75 ng/mL/yr | 🟡 AMBER | Monitor — likely prostate adaptation |
| > 0.75 ng/mL/yr sustained | 🔴 RED | Clinical review regardless of absolute value |
| Re-acceleration after plateau | 🔴 RED | Investigate — not expected pattern |

**Notes:** Current = 1.56 ng/mL (🟡 AMBER). Velocity: +0.79/yr over 12 months, but decelerating (6→12 months = +0.68/yr annualised). Next reading (18 months) is the critical checkpoint — expect plateau near 1.6–2.0.

---

### BR-S02 | Haematocrit
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| < 46% | 🟢 GREEN | No action |
| 46–48% | 🟡 AMBER | Optimise hydration; increase water intake to 4L/day |
| 48–50% | 🔴 RED | Hold dose increase; discuss venesection with clinic |
| > 50% | ⚫ CRITICAL | Pause TRT; urgent clinical review; consider therapeutic phlebotomy |

**Notes:** Current = 46.7% (🟡 AMBER — borderline). Proposed dose increase (0.28 → 0.32ml) projected at ~47.5% — still within safe range, but watch closely. Hydration is the primary lever.

---

### BR-S03 | Haemoglobin
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| < 155 g/L | 🟢 GREEN | Optimal |
| 155–165 g/L | 🟡 AMBER | Monitor with haematocrit |
| 165–170 g/L | 🔴 RED | Clinical review |
| > 170 g/L | ⚫ CRITICAL | Urgent review; cardiovascular risk elevated |

**Notes:** Current = 156 g/L (🟡 AMBER). Trending up from 150 g/L. Dose increase will likely push further — monitor at 6 weeks post any change.

---

### BR-S04 | eGFR (Kidney Function)
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| > 90 ml/min | 🟢 GREEN | Optimal |
| 60–90 ml/min | 🟡 AMBER | Monitor protein intake; check creatinine trend |
| 45–60 ml/min | 🔴 RED | Reduce protein to 1.8g/kg; clinical review |
| < 45 ml/min | ⚫ CRITICAL | Urgent nephrology review; suspend high protein protocol |

**Notes:** Current = 93 ml/min (🟢 GREEN, improved from 106). Creatine supplementation and high protein can mildly suppress eGFR — ensure consistent pre-test conditions (no training, consistent hydration day before).

---

## Domain 3: Blood Panel — Metabolic & Cardiovascular

### BR-C01 | Total Cholesterol
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| < 4.5 mmol/L | 🟢 GREEN | Optimal |
| 4.5–5.2 mmol/L | 🟡 AMBER | Review dietary fat composition; increase omega-3 |
| > 5.2 mmol/L | 🔴 RED | Clinical review; consider statin discussion with GP |

**Notes:** Current = 3.38 mmol/L (🟢 GREEN, improved from 3.64). Excellent cardiovascular profile.

---

### BR-C02 | Total Cholesterol / HDL Ratio
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| < 3.5 | 🟢 GREEN | Optimal cardiovascular risk |
| 3.5–4.0 | 🟡 AMBER | Target HDL improvement — increase omega-3 to 3g EPA/DHA |
| 4.0–5.0 | 🔴 RED | Clinical review; dietary intervention |
| > 5.0 | ⚫ CRITICAL | Urgent cardiovascular risk assessment |

**Notes:** Current = 3.76 (🟡 AMBER, improved from 4.0). Primary lever is raising HDL (currently 0.9 mmol/L — below 1.0 threshold). See BR-C03.

---

### BR-C03 | HDL Cholesterol
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| > 1.2 mmol/L | 🟢 GREEN | Optimal cardioprotective |
| 1.0–1.2 mmol/L | 🟡 AMBER | Increase aerobic activity; omega-3 3g/day |
| 0.9–1.0 mmol/L | 🔴 RED | Structured aerobic work 3x/week; review TRT dose (exogenous T suppresses HDL) |
| < 0.9 mmol/L | ⚫ CRITICAL | Clinical review; dose increase on hold until improved |

**Notes:** Current = 0.9 mmol/L (🔴 RED). This is the single most actionable blood marker right now. TRT is a known HDL suppressant. Any dose increase must be weighed against further HDL suppression. Interventions: increase walking to 5km/day, add structured Zone 2 cardio 2x/week, maximise omega-3.

---

### BR-C04 | HbA1c (Insulin Sensitivity)
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| < 38 mmol/mol (5.7%) | 🟢 GREEN | Optimal insulin sensitivity |
| 38–41 mmol/mol (5.7–5.9%) | 🟡 AMBER | Monitor; review refined carb intake |
| 42–47 mmol/mol (6.0–6.4%) | 🔴 RED | Pre-diabetic range; clinical review; reduce refined carbs |
| ≥ 48 mmol/mol (≥ 6.5%) | ⚫ CRITICAL | Diabetic range; urgent clinical review |

**Notes:** Current = 33.66 mmol/mol (🟢 GREEN). Exceptional for age. Clean bulk with controlled carb timing and daily walking is the primary driver.

---

### BR-C05 | MCV (Mean Corpuscular Volume)
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| 80–95 fL | 🟢 GREEN | Normal |
| 95–100 fL | 🟡 AMBER | Monitor B12/folate |
| > 100 fL | 🔴 RED | B12/folate deficiency likely — supplement audit; retest in 8 weeks |

**Notes:** Current = 99.2 fL (🟡 AMBER — approaching threshold). Ensure methylcobalamin B12 is active form, dose 1000mcg/day. Add methylfolate (L-5-MTHF) 400mcg if not already included. Retest at next panel.

---

## Domain 4: Body Composition (Boditrax)

### BR-B01 | Muscle Mass — Absolute
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| Increasing trend ≥ +0.3kg/month | 🟢 GREEN | Optimal — maintain protocol |
| Stable (±0.3kg/month) | 🟡 AMBER | Review caloric surplus; confirm protein ≥ 190g/day |
| Declining > 0.3kg/month | 🔴 RED | Check for overtraining, under-eating, illness; add deload |
| Declining > 0.5kg/month | ⚫ CRITICAL | Investigate acute cause; clinical review if unexplained |

**Notes:** Current = 69.8kg. Target = 72kg by June 2026 (+2.2kg over ~7 months = +0.31kg/month minimum). Currently tracking ahead of target.

---

### BR-B02 | Fat Mass — Absolute
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| < 13.0kg (< 15% BF) | 🟢 GREEN | Optimal recomp or cut outcome |
| 13.0–14.5kg (15–16.5% BF) | 🟡 AMBER | Tighten nutrition; ensure caloric surplus not excessive |
| 14.5–16.0kg (16.5–18% BF) | 🔴 RED | Initiate mini-cut: –300 kcal/day, maintain protein |
| > 16.0kg (> 18% BF) | ⚫ CRITICAL | Stop bulk; structured cut required |

**Notes:** Current = 13.0kg (🟢 GREEN — at lower bound). Golden phase ongoing. Clean Bulk Protocol red flag trigger = 15.5kg.

---

### BR-B03 | Muscle:Fat Gain Ratio (Bulk Phase)
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| > 3:1 muscle:fat | 🟢 GREEN | Exceptional lean bulk — maintain |
| 2:1 to 3:1 | 🟡 AMBER | Acceptable; monitor trend |
| 1:1 to 2:1 | 🔴 RED | Reduce surplus by 100–150 kcal; audit food quality |
| < 1:1 (more fat than muscle) | ⚫ CRITICAL | Stop bulk; reassess protocol |

---

### BR-B04 | Visceral Fat Rating
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| ≤ 7 | 🟢 GREEN | Optimal — cardiovascular risk minimised |
| 8–9 | 🟡 AMBER | Tighten dietary fat; increase walking volume |
| 10–12 | 🔴 RED | Initiate cut; prioritise visceral fat reduction |
| > 12 | ⚫ CRITICAL | Clinical review; significant metabolic risk |

**Notes:** Current = 7 (🟢 GREEN — maintained throughout 18-month history). Priority marker for longevity.

---

### BR-B05 | Right Leg Asymmetry
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| ≤ 0.1kg difference | 🟢 GREEN | Symmetry achieved |
| 0.1–0.2kg difference | 🟡 AMBER | Maintain unilateral priority (right leg first on all exercises) |
| 0.2–0.4kg difference | 🔴 RED | Add dedicated unilateral session: extra set right leg per exercise |
| > 0.4kg difference | ⚫ CRITICAL | Investigate neurological or structural cause |

**Notes:** Current asymmetry = 0.3kg (Right 10.9kg, Left 10.6kg — right is larger, left is lagging). Correction: start all unilateral work with left leg.

---

### BR-B06 | Phase Angles (Cellular Health)
| Segment | GREEN | AMBER | RED |
|---------|-------|-------|-----|
| Right Arm | > -6.0° | -5.5° to -6.0° | < -5.5° |
| Left Arm | > -5.8° | -5.3° to -5.8° | < -5.3° |
| Right Leg | > -5.5° | -5.0° to -5.5° | < -5.0° |
| Left Leg | > -5.5° | -5.0° to -5.5° | < -5.0° |

**Declining trend rule:** Any phase angle declining > 0.3° over consecutive scans = 🟡 AMBER — review hydration, protein intake, training load.

**Notes:** Current values all in GREEN/high-AMBER range. Phase angles are sensitive to hydration — ensure consistent scan conditions (same time, fasted, no intense training prior day).

---

### BR-B07 | Metabolic Age
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| ≤ 38 (≤ 12yr advantage) | 🟢 GREEN | Exceptional |
| 39–42 (8–11yr advantage) | 🟡 AMBER | Review sleep, stress, training consistency |
| 43–46 (4–7yr advantage) | 🔴 RED | Full protocol audit — something is regressing |
| ≥ 47 (≤ 3yr advantage) | ⚫ CRITICAL | Clinical review; investigate hormonal or metabolic cause |

**Notes:** Current = 35 (15-year advantage). This is the headline metric — protect it at all costs.

---

### BR-B08 | Boditrax Score
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| ≥ 820 | 🟢 GREEN | Peak performance zone |
| 800–819 | 🟡 AMBER | Solid; review which sub-components are dragging |
| 780–799 | 🔴 RED | Multiple metrics regressing; full protocol review |
| < 780 | ⚫ CRITICAL | Significant regression — clinical + protocol review |

**Notes:** Current = 808 (🟡 AMBER). Target ≥ 820 by June 2026.

---

## Domain 5: Body Weight & Bulk Phase Management

### BR-W01 | Weekly Average Weight Change (Bulk Phase)
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| +0.15 to +0.25kg/week | 🟢 GREEN | Optimal lean bulk rate |
| +0.10 to +0.15kg/week | 🟡 AMBER | Add 100 kcal; monitor for 2 more weeks |
| +0.25 to +0.35kg/week | 🟡 AMBER | Reduce 100 kcal; risk of excess fat gain |
| < +0.10kg/week for 3 weeks | 🔴 RED | Add 150–200 kcal; review training volume |
| > +0.35kg/week for 2 weeks | 🔴 RED | Reduce 200 kcal immediately; check fat mass at next Boditrax |

---

## Domain 6: Training & Recovery

### BR-T01 | Progressive Overload — Strength Stagnation
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| Volume/strength increasing | 🟢 GREEN | Continue |
| No progression for 2 weeks | 🟡 AMBER | Check sleep, nutrition, recovery |
| No progression for 4 weeks | 🔴 RED | Implement deload week; audit caloric surplus |
| Strength regression for 3+ weeks | ⚫ CRITICAL | Investigate overtraining, illness, hormonal issue |

---

### BR-T02 | Deload Trigger Rules
Trigger deload if **any 2 or more** of the following are present:
- Strength regression on main lifts for 2+ consecutive weeks
- Resting HR elevated > 8 bpm above baseline for 5+ days
- HRV (Oura) suppressed > 15% below 30-day average for 5+ days (adjusted for known nicotine impact)
- Sleep quality (Oura score) < 65 for 3+ consecutive nights
- Joint pain > 3/10 on any major joint
- Subjective energy < 4/10 for 5+ consecutive days

**Protocol:** Reduce sets by 40%, maintain weight/reps, 7 days, then return.

---

### BR-T03 | HRV — Oura Ring (Adjusted for Nicotine Baseline)
| Condition | Severity | Intervention |
|-----------|----------|--------------|
| > 40ms | 🟢 GREEN | Above personal baseline — train hard |
| 35–40ms | 🟡 AMBER | At personal baseline — train normally, monitor |
| 28–35ms | 🔴 RED | Suppressed — reduce intensity; prioritise recovery |
| < 28ms | ⚫ CRITICAL | Skip training; investigate acute cause (illness, injury, stress) |

**Notes:** Personal HRV baseline = ~37ms (suppressed ~10–15ms by evening nicotine use). All readings interpreted relative to this adjusted baseline. December 2025 suppression = acute lower back strain event, not overtraining.

---

## Domain 7: Supplement Stack Rules

### BR-SP01 | Supplement Redundancy on TRT
| Supplement | Rule |
|-----------|------|
| Boron | ✅ Keep — SHBG modulation, free T optimisation |
| Ashwagandha | ✅ Keep — cortisol reduction, prolactin reduction benefit demonstrated |
| ZMA (Zinc/Mag/P5P) | ✅ Keep — cofactors for hormone synthesis, sleep quality |
| Omega-3 | ✅ Keep — HDL support (critical given BR-C03 status) |
| Vitamin D | ✅ Keep — testosterone cofactor; target > 100 nmol/L |
| Maca | 🟡 Review — limited evidence on TRT; libido benefit may be placebo |
| Fenugreek | 🔴 Low ROI on TRT — consider dropping; redundant with TRT for testosterone |
| L-Citrulline + Beetroot + Tadalafil | ✅ Keep all — synergistic NO pathway, no redundancy |

---

### BR-SP02 | MCV / B12 Trigger (linked to BR-C05)
If MCV > 95 fL:
- Confirm methylcobalamin form (not cyanocobalamin)
- Dose at 1000mcg/day minimum
- Add L-5-MTHF (methylfolate) 400mcg/day
- Retest in 8 weeks; if MCV still > 95, investigate absorption (intrinsic factor)

---

## Rule Evaluation Cadence

| Domain | Frequency | Method |
|--------|-----------|--------|
| Blood panel markers | Every 6 months (3-monthly for RED flags) | Manual clinic bloods |
| PSA velocity | Every 6 months | Calculate rolling annualised rate |
| Boditrax composition | Monthly | Boditrax scanner |
| Body weight | Weekly average | Daily weigh-in → 7-day mean |
| HRV / Sleep | Daily | Oura ring |
| Training progression | Weekly | Hevy app review |
| Supplement audit | Quarterly | Against latest blood panel |

---

## Summary Dashboard — Current Status (March 2026)

| Rule | Metric | Current | Status |
|------|--------|---------|--------|
| BR-H01 | Total Testosterone | 17.7 nmol/L | 🟡 AMBER |
| BR-H02 | Free Testosterone | 0.449 nmol/L | 🟡 AMBER |
| BR-H03 | Oestradiol | 86.8 pmol/L | 🟡 AMBER |
| BR-H04 | SHBG | 22.5 nmol/L | 🟢 GREEN |
| BR-H05 | Prolactin | 116 mIU/L | 🟡 AMBER |
| BR-S01 | PSA | 1.56 ng/mL | 🟡 AMBER |
| BR-S01a | PSA Velocity | +0.68/yr (6→12m) | 🟡 AMBER |
| BR-S02 | Haematocrit | 46.7% | 🟡 AMBER |
| BR-S03 | Haemoglobin | 156 g/L | 🟡 AMBER |
| BR-S04 | eGFR | 93 ml/min | 🟢 GREEN |
| BR-C01 | Total Cholesterol | 3.38 mmol/L | 🟢 GREEN |
| BR-C02 | Chol/HDL Ratio | 3.76 | 🟡 AMBER |
| BR-C03 | HDL | 0.9 mmol/L | 🔴 RED |
| BR-C04 | HbA1c | 33.66 mmol/mol | 🟢 GREEN |
| BR-C05 | MCV | 99.2 fL | 🟡 AMBER |
| BR-B01 | Muscle Mass | 69.8kg (+trend) | 🟢 GREEN |
| BR-B02 | Fat Mass | 13.0kg | 🟢 GREEN |
| BR-B04 | Visceral Fat | Rating 7 | 🟢 GREEN |
| BR-B05 | Leg Asymmetry | 0.3kg | 🔴 RED |
| BR-B07 | Metabolic Age | 35 (−15yr) | 🟢 GREEN |
| BR-B08 | Boditrax Score | 808 | 🟡 AMBER |

**Active REDs requiring intervention:**
1. **HDL 0.9 mmol/L** — add structured Zone 2 cardio 2x/week; maximise omega-3; monitor impact of any dose increase
2. **Leg Asymmetry 0.3kg** — correct to LEFT leg first on all unilateral exercises immediately

---

*Document designed for dashboard integration. Each BR-ID maps to a metric field.  
Severity levels designed for RAG (Red/Amber/Green) dashboard display.*
