# Health Intel Dashboard: TODO

## ✅ Completed

### Data Gaps & Consistency
- [x] **Heart Rate Integration:** Surface Resting Heart Rate (RHR) trends in the Sleep/Recovery dashboard and Overview.
- [x] **Nutrition Compliance Metric:** Add a chart/metric for logging consistency (percentage of days with >0 calories logged).
- [x] **Body Composition Handling:** Implement "Last Known Value" logic for sparse Boditrax data to prevent gaps in sparklines/cards.
- [x] **Data Reload UI:** Add a button in the Dashboard UI to trigger the `/api/reload` endpoint.

### Visualisation & UX
- [x] **Contextual Thresholds:** Add "Target Zones" to `MetricCard` (e.g., green for 1.6-2.2g/kg protein, 7.5k+ steps).
- [x] **Multi-Series Alignment:** Create overlay charts (e.g., Calories vs. Weight, Training Volume vs. HRV).
- [x] **Interactive Alerts:** Make `AlertCard` clickable to navigate to the relevant detail page.
- [x] **Mobile Optimization:** Ensure the dashboard layout remains functional on smaller screens (sidebar/grid adjustments).

### Analytical Improvements
- [x] **Rolling Averages:** Add a toggle for 7-day rolling averages on daily charts to smooth "weekend noise".
- [x] **Time-Lagged Correlations:** Implement correlations that account for delay (e.g., Yesterday's Stress -> Today's Sleep).
- [x] **Sophisticated Alert Logic:** Combine metrics for smarter alerts (e.g., "Safe Deload" vs "Overtraining" based on Volume + HRV).
- [x] **Trend Direction Sensitivity:** Adjust `trendArrow` logic to be context-aware (e.g., Increasing Stress = Red, Increasing Sleep = Green).

### New Features
- [x] **Caloric Balance Metric:** Calculate and display `Intake - (BMR + Active Calories)` on the Overview page.
- [x] **Strength Progress Tracking:** Add "Estimated 1RM" trends for top 3 compound exercises on the Training page.
- [x] **PDF Export Enhancement:** Improve the "Print/Export" styling for a more professional-looking health report.
- [x] **Theme Persistence:** Ensure the light/dark mode preference persists across sessions. *(Already implemented — useTheme persists to localStorage)*

---

## 📊 Surface Underutilised Data

- [x] **Readiness Score Drivers:** Expose readiness contributor breakdown (HRV balance, body temp, sleep balance, recovery index, etc.) via `/api/readiness/contributors` and add a breakdown chart to SleepRecovery page.
- [x] **Sleep Score Drivers:** Expose sleep contributor breakdown (efficiency, latency, deep sleep, restfulness, timing) and add a chart showing what's pulling scores down.
- [x] **Deep Sleep & REM Cards:** Add KPI cards for Deep Sleep % and REM % to SleepRecovery with targets (20-25% deep, ~20% REM).
- [x] **Activity Intensity Distribution:** Surface `high/medium/low/sedentary_met_minutes` and `sedentary_time` from activity data. Add intensity breakdown chart and sedentary time card to Overview.
- [x] **Segmental Body Composition:** Display left/right arm/leg muscle and fat mass from Boditrax data. Add asymmetry detection table flagging >5% imbalances.
- [x] **Training Intensity Profile:** Categorize sets by rep range (1-5 strength, 6-12 hypertrophy, 13+ endurance) to show training methodology distribution on Training page.
- [x] **Water Distribution Chart:** Show intracellular vs. extracellular water trends from Boditrax data on BodyComposition page.
- [x] **Phase Angle Trend:** Add phase angle (cellular health indicator) chart to BodyComposition page.
- [x] **Set Type Breakdown:** Show distribution of set types (normal, warmup, drop set, failure) on Training page.
- [x] **Sleep Latency Trend:** Chart time-to-fall-asleep trend on SleepRecovery page.

## 🎨 Visualisation & UX

- [x] **Calendar Heatmap:** GitHub-style heatmap for daily metrics (sleep score, steps, calories) for visual pattern recognition.
- [x] **Period Comparison:** Side-by-side "How am I doing vs. last month?" comparison for all metrics between two date ranges.
- [x] **Personal Records Dashboard:** Surface best sleep score, highest training volume week, longest step streak, heaviest 1RM. Gamification via a dedicated section or page.
- [x] **Goal Setting & Progress:** Let users set targets (8hr sleep, 10k steps, 2g/kg protein) stored in localStorage. Show progress bars/indicators on Overview.
- [x] **Chart Data Export:** Add download button on ChartCards to export the underlying data as CSV.
- [x] **Weekly Digest View:** Single-page week-over-week summary with wins/losses, formatted for quick review or print.

## 📈 Analytical Improvements

- [x] **Multi-Lag Correlation Analysis:** Test 0, 1, 2, 3-day lags for each correlation pair and surface the strongest lag. Show "Yesterday's stress predicts today's HRV better than same-day."
- [x] **Missing Correlations — Recovery:** Sedentary time → next-day readiness, sleep efficiency → training performance, sleep stage breakdown (deep/REM) → next-day HRV.
- [x] **Missing Correlations — Nutrition:** Carb intake → sleep quality, workout frequency → muscle growth, body fat % → resting heart rate, visceral fat → stress levels.
- [x] **Missing Correlations — Body Comp:** Weekly volume progression → body composition, exercise variety (unique exercises/week) → muscle growth, breathing disturbance index → readiness.
- [x] **Correlation Stability:** Add a metric indicating whether a correlation is robust or likely noise (e.g., bootstrap confidence intervals).

## 🔔 New Alert Types

- [x] **Sleep Pattern Alerts:** Sleep latency increasing, sleep efficiency declining, sleep regularity poor (bedtime varies >2 hours), breathing disturbances detected, deep sleep % low.
- [x] **Activity Alerts:** Sedentary >8 hours/day, steps declining for 2+ weeks, low activity intensity (mostly sedentary, not enough high/medium).
- [x] **Training Alerts:** Training volume plateaued (no progressive overload for 4+ weeks), muscle group neglected (<20% of balanced volume), exercise stagnation (same exercises for 2+ months).
- [x] **Nutrition Alerts:** Caloric deficit too aggressive (>500 kcal/day, risk of lean mass loss), micronutrient gaps (calcium, vitamin C, iron consistently low).
- [x] **Body Composition Alerts:** Segmental muscle asymmetry >5%, BMR declining despite stable weight (possible muscle loss), metabolic age increasing, phase angle declining.

## 🚀 New Features

- [x] **Intervention Tracking:** Log when you tried something ("started sleeping earlier", "added creatine") with a tagged date, then visualize before/after metric changes.
- [x] **Streak Tracking:** Consecutive days hitting targets (steps, sleep score, protein, logging compliance). Surface on Overview.
- [x] **Readiness-Based Training Recommendation:** Combine HRV + readiness + recent volume into a "recovery readiness for training" score with suggested intensity.
- [x] **Prediction/Forecast:** "At current rate, muscle mass goal reachable in X months" based on trend extrapolation.

## 🔧 Architecture & Performance

- [x] **API Pagination:** Add pagination support for large endpoints (`/activity`, `/sleep`, `/heartrate`).
- [x] **Server-Side Aggregation:** Add `?aggregate=weekly` query param to list endpoints to reduce client-side computation.
- [x] **Data Quality Checks:** Validate physiologically plausible ranges during transform (e.g., steps 0-100k, HR 30-250 bpm, sleep score 0-100). Flag outliers.
- [x] **Incremental Sync:** Use `_metadata.json` last-sync dates to only request new data from APIs instead of full re-extraction.
- [x] **Duplicate Day Handling:** Merge/deduplicate when data is re-extracted for overlapping date ranges.
