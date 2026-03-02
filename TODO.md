# Health Intel TODO

## Completed
- [x] **MFP Data Integration**: Rewrote `mfp.py` to parse MFP Premium CSV export. 248 days of nutrition data now flowing through the full pipeline with 17 nutrient columns. Removed broken `python-myfitnesspal` / `browser_cookie3` dependencies.
- [x] **Progressive Overload Tracking**: Implemented in report — tracks top exercises over time.
- [x] **Trend Alerts**: 15+ alert types with severity levels and actionable interventions.

## Up Next
- [ ] **Report Enhancement**: Improve/extend the report:
    - [x] Add SpO2 section (avg SpO2, trend chart, breathing disturbance index with thresholds)
    - [x] Add heart rate trends section (RHR avg, weekly trend chart, HR variability, trend narrative — ready for re-extract, currently only 2 days of raw HR data)
    - [x] Add MFP weight measurements to body composition section (114 daily weight points overlaid on Boditrax scan trajectory)
    - [x] Richer nutrition charts (weekly macro stacked bar, protein/kg trend with target band, meal calorie distribution)
    - [ ] Add MFP exercise/step data to activity section (2,417 entries available but no Health Connect step data in date range)
- [x] **Testing**: Add tests — build confidence for refactoring (62 tests, all passing):
    - [x] Transform functions with fixture data (20 tests: helpers, Oura, Hevy, Boditrax, MFP)
    - [x] MFP CSV parsing edge cases (15 tests: missing columns, empty days, date filtering, NaN exclusion, monthly batching)
    - [x] Correlation validation (12 tests: minimum data points, boundary cases, symmetry, compute_correlations)
    - [x] Report section smoke tests (15 tests: corr_strength, recent_trend, weekly_resample, section outputs, generate_report)
- [ ] **Refactor `report.py`**: Break down the 953-line report generator into modular components (`report/sections/`, `report/alerts.py`, `report/charts.py`).
- [ ] **Weekly vs Monthly Report Modes**: Add `--mode weekly|monthly` flag for different time granularities and comparison against previous period.
- [x] **CLAUDE.md Update**: Updated MFP section to document CSV export workflow, added testing section, updated report sections list, removed defunct keyring/browser_cookie3 references.
