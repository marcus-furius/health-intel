# CLAUDE.md — Unified Health Intelligence Project

## Project Overview

This project consolidates personal health and fitness data from four sources — **Oura Ring** (sleep, recovery, HRV), **Hevy** (strength training), **Boditrax** (body composition), and **MyFitnessPal** (nutrition) — into a single data pipeline. Raw data is stored as structured files, transformations are reproducible, and markdown health reports are generated with trend analysis and cross-source correlations. Everything follows a **data-as-code** approach — version-controlled and reproducible.

## Tech Stack & Conventions

- **Language:** Python 3.11+
- **Package management:** `pip` with `requirements.txt`
- **Key libraries:** `requests`, `pandas`, `matplotlib`, `python-dotenv`, `pyarrow`
- **Testing:** `pytest`
- **Environment config:** `.env` file (never committed — listed in `.gitignore`)
- **Output format:** Markdown reports with embedded base64 PNG charts

## Project Structure

```
health-intel/
├── CLAUDE.md                  # This file — project instructions for Claude Code
├── .env                       # API tokens and credentials (not committed)
├── .gitignore
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── oura.py            # Oura Ring API v2 client
│   │   ├── hevy.py            # Hevy API client
│   │   ├── boditrax.py        # Boditrax scraper / CSV ingestion
│   │   └── mfp.py             # MyFitnessPal CSV export parser
│   ├── extract.py             # Orchestrates pulls from all sources
│   ├── transform.py           # Cleaning, normalisation, cross-source alignment
│   ├── correlate.py           # Cross-source correlation analysis
│   └── report.py              # Markdown report generation with charts
├── data/
│   ├── raw/
│   │   ├── oura/              # Raw JSON from Oura API
│   │   ├── hevy/              # Raw JSON from Hevy API
│   │   ├── boditrax/          # Scraped JSON or manually placed CSVs
│   │   └── mfp/               # Raw JSON from MyFitnessPal
│   └── processed/             # Cleaned, unified datasets
├── reports/                   # Generated markdown health reports
└── tests/
    ├── __init__.py
    ├── conftest.py            # Shared fixtures (sample DataFrames, MFP CSV data)
    ├── test_transform.py      # Transform pipeline tests (20 tests)
    ├── test_mfp.py            # MFP CSV parsing tests (15 tests)
    ├── test_correlate.py      # Correlation analysis tests (12 tests)
    └── test_report.py         # Report generation tests (15 tests)
```

## Environment Variables

```env
# Oura Ring — https://cloud.ouraring.com/personal-access-tokens
OURA_TOKEN=your_oura_token

# Hevy (requires Pro) — https://hevy.com/settings?developer
HEVY_API_KEY=your_hevy_api_key

# MyFitnessPal — no credentials needed; uses Premium CSV export
# Export from: https://www.myfitnesspal.com/reports
# Place export directory in data/raw/mfp/

# Boditrax — no token; uses native account CSV export or manual CSV import
# Set to 'scraper' or 'csv' to control ingestion method
BODITRAX_MODE=csv
```

---

## Data Source 1: Oura Ring API v2

### Connection Details

- **Base URL:** `https://api.ouraring.com`
- **Auth:** Bearer token via `Authorization: Bearer {OURA_TOKEN}`
- **Date params:** All endpoints accept `start_date` and `end_date` as `YYYY-MM-DD`
- **Pagination:** Responses may include `next_token` — always handle this

### Endpoints

| Endpoint | Purpose | Key Metrics |
|---|---|---|
| `/v2/usercollection/daily_sleep` | Sleep scores | Score, duration, efficiency |
| `/v2/usercollection/sleep` | Sleep stages | REM, deep, light, awake durations |
| `/v2/usercollection/daily_readiness` | Recovery | Score, HRV balance, temp deviation |
| `/v2/usercollection/daily_activity` | Movement | Steps, calories, active time |
| `/v2/usercollection/heartrate` | Heart rate | Continuous HR (5-min intervals) — high volume |
| `/v2/usercollection/daily_spo2` | Blood oxygen | SpO2 averages |

### Oura-Specific Rules

- Heart rate data is high volume — always paginate with `next_token`
- Store HR data as parquet, not CSV
- Daily endpoints return one record per day — safe as CSV

---

## Data Source 2: Hevy API

### Connection Details

- **Base URL:** `https://api.hevyapp.com`
- **Auth:** API key via `api-key` header
- **Docs:** https://api.hevyapp.com/docs/ (Swagger)
- **Requirement:** Hevy Pro subscription

### Endpoints

| Endpoint | Purpose | Key Metrics |
|---|---|---|
| `GET /v1/workouts` | Workout history | Date, duration, exercises, sets, reps, weight |
| `GET /v1/workouts/{id}` | Single workout detail | Full exercise breakdown |
| `GET /v1/routines` | Saved routines | Routine structure and exercises |
| `GET /v1/exercise_templates` | Exercise catalogue | Available exercises and muscle groups |

### Hevy-Specific Rules

- Paginated with `page` and `pageSize` params
- Workout responses include nested exercise arrays with set-level data
- Normalise weights to kg (Hevy may store in user's preferred unit)
- Calculate derived metrics: total volume (sets × reps × weight), estimated 1RM, volume per muscle group
- Track progressive overload by comparing same exercise across sessions

### MCP Integration (Optional)

There is an existing Hevy MCP server (`hevy-mcp`) that can be configured in Claude Code or OpenClaw for conversational access to training data. If using MCP alongside this pipeline, avoid duplicate API calls — let the pipeline handle batch data pulls and MCP handle ad-hoc queries.

---

## Data Source 3: Boditrax

### Connection Details

Boditrax does **not** offer a public consumer API. Two ingestion methods are supported:

#### Method A: Manual CSV Import (Recommended — `BODITRAX_MODE=csv`)

- Export or manually record scan results
- Place CSV files in `data/raw/boditrax/` with naming: `boditrax_scan_YYYY-MM-DD.csv`
- Expected columns: `date, weight_kg, body_fat_pct, muscle_mass_kg, water_mass_kg, bone_mass_kg, visceral_fat, metabolic_age, bmr, bmi, phase_angle`
- Scans are infrequent (weekly/monthly) so manual entry is acceptable

#### Method B: Browser Cookie Scraper (`BODITRAX_MODE=scraper`)

- Uses the `judgewooden/boditrax` library (install from GitHub)
- Depends on `browser_cookie3` to grab session cookies from local browser
- Fragile — may break if Boditrax changes their frontend
- Only use if you're running the pipeline on a machine where you're logged into Boditrax in a browser

### Boditrax Metrics

| Metric | Unit | Notes |
|---|---|---|
| Weight | kg | |
| Body fat mass | kg / % | |
| Muscle mass | kg | Segmental if available |
| Water mass | kg | |
| Bone mass | kg | |
| Visceral fat | rating | Abdominal cavity fat |
| Metabolic age | years | |
| BMR | kcal | Basal metabolic rate |
| BMI | kg/m² | |
| Phase angle | degrees | Cellular health indicator |

### Boditrax-Specific Rules

- Data frequency is low (weekly or monthly scans) — handle sparse timeseries gracefully
- When merging with daily Oura/Hevy data, forward-fill Boditrax values or treat as point-in-time snapshots
- Never interpolate body composition values between scans — this misrepresents actual measurements

---

## Data Source 4: MyFitnessPal

### Connection Details

- **Method:** MFP Premium CSV export (no API, no scraping, no credentials in code)
- **Export:** Download from MFP website → Reports → Export
- **Setup:** Place the `File-Export-*` directory inside `data/raw/mfp/`
- **Client:** `src/sources/mfp.py` — `MfpSource` class parses the export CSVs

### Export Files

The MFP Premium export contains three CSV files:

| File | Purpose | Pipeline Output |
|---|---|---|
| `Nutrition-Summary*.csv` | Meal-level macros/micros (17 nutrient columns) | Aggregated to daily totals with per-meal breakdown |
| `Measurement-Summary*.csv` | Weight entries | Daily weight_kg records |
| `Exercise-Summary*.csv` | Cardio, steps, strength | Exercise entries with calories, duration, steps |

### Metrics Per Day

| Metric | Source | Notes |
|---|---|---|
| Total calories | Nutrition-Summary | Sum of all meals |
| Protein | Nutrition-Summary | Grams |
| Carbohydrates | Nutrition-Summary | Grams |
| Fat | Nutrition-Summary | Grams |
| Sodium | Nutrition-Summary | Milligrams |
| Sugar | Nutrition-Summary | Grams |
| Fiber | Nutrition-Summary | Grams |
| Saturated/Poly/Mono/Trans fat | Nutrition-Summary | Grams |
| Cholesterol, Potassium, Vitamins A/C, Calcium, Iron | Nutrition-Summary | Various units |
| Meal breakdown | Nutrition-Summary | Breakfast, Lunch, Dinner, Snacks with per-meal macros |
| Weight | Measurement-Summary | kg (if logged in MFP) |
| Exercise | Exercise-Summary | Type, calories, duration, steps |

### MFP-Specific Rules

- `MfpSource._find_export_dir()` picks the most recent `File-Export-*` directory by name sort
- Meal-level rows are aggregated to daily totals; per-meal breakdown preserved in `meals` list
- Days with no entries result in zero-calorie days — do not skip them (gaps in nutrition tracking are themselves informative)
- MFP weight measurements may overlap with Boditrax weight — use Boditrax as the authoritative source for weight, MFP as supplementary
- Normalise all macros to grams, calories to kcal
- Calculate derived metrics: protein per kg bodyweight (using latest Boditrax weight), caloric surplus/deficit (MFP calories vs Oura active calories + BMR)
- `save_raw()` batches diary entries into monthly JSON files: `mfp_diary_2026-01.json`
- NaN values in exercise data are excluded from output dicts

---

## Cross-Source Correlations

The real value of this project is connecting the four data streams. The report generator should analyse:

### Recovery & Performance

| Correlation | Sources | Question |
|---|---|---|
| Sleep → Training Performance | Oura + Hevy | Does poor sleep correlate with lower training volume or intensity? |
| Training Load → Recovery | Hevy + Oura | Do heavy training days impact next-day readiness/HRV? |
| Activity → Sleep | Oura (activity + sleep) | Does higher daily movement improve sleep scores? |

### Nutrition & Recovery

| Correlation | Sources | Question |
|---|---|---|
| Protein Intake → Recovery | MFP + Oura | Do higher protein days correlate with better readiness/HRV? |
| Caloric Intake → Sleep | MFP + Oura | Do high-carb evenings affect sleep quality? |
| Hydration/Sodium → HRV | MFP + Oura | Does sodium intake correlate with HRV changes? |

### Nutrition & Body Composition

| Correlation | Sources | Question |
|---|---|---|
| Caloric Balance → Body Comp | MFP + Boditrax + Oura | Is caloric surplus/deficit tracking with weight and body fat trends? |
| Protein/kg → Muscle Mass | MFP + Boditrax | Is protein intake sufficient to support muscle gain? (target: 1.6–2.2g/kg) |
| Macro Split → Fat Mass | MFP + Boditrax | Does macro composition affect body fat independent of total calories? |

### Training & Body Composition

| Correlation | Sources | Question |
|---|---|---|
| Progressive Overload → Muscle | Hevy + Boditrax | Are muscle mass gains tracking with progressive overload? |
| Training Volume → Body Comp | Hevy + Boditrax | Does total weekly volume correlate with favourable body comp changes? |
| HRV → Body Composition | Oura + Boditrax | Does sustained high HRV correlate with favourable body composition changes? |

### Alignment Rules

- Use **date** as the universal join key across all sources
- Oura, Hevy, and MFP produce daily data; Boditrax is sparse — use nearest-scan joins for body comp
- All timestamps normalised to UTC, then converted to local time for display
- When correlating, require a minimum of 14 data points before drawing trend conclusions
- For protein/kg calculations, use the most recent Boditrax weight as the denominator
- Caloric surplus/deficit = MFP total calories − (Oura active calories + latest Boditrax BMR)

---

## Coding Standards

- Use type hints on all function signatures
- Use `pathlib.Path` for all file path handling
- Use `logging` module (not print statements) for operational output
- Handle API rate limits gracefully with retry logic and exponential backoff
- All API calls must handle pagination fully
- Store dates as ISO 8601 strings in data files
- Use descriptive variable names — no single-letter variables outside comprehensions
- Each source client in `src/sources/` must implement a common interface:
  ```python
  def pull(start_date: str, end_date: str) -> dict[str, pd.DataFrame]
  ```

## Data Handling Rules

- **Raw data is immutable** — never modify files in `data/raw/`
- Raw files named by source, endpoint, and date range: `oura_daily_sleep_2025-01-01_2025-03-31.json`
- Processed data stored as CSV (for readability) or parquet (for large datasets like HR)
- Include a `_metadata.json` per source directory tracking last sync date and record counts
- Incremental sync: check `_metadata.json` for last pull date, only request new data
- MFP diary data: store individual days as JSON during pull, consolidate into monthly CSVs during transform

## Report Generation Rules

- Reports go in `reports/` as markdown named `health_report_YYYY-MM-DD.md`
- Every report must include:
  - **Date range** covered
  - **Nutrition** (MFP): average daily calories, macro split (protein/carbs/fat as g and %), protein per kg bodyweight, caloric consistency, surplus/deficit estimate, meal calorie distribution
  - **Sleep & Recovery** (Oura): average scores, duration trends, HRV trajectory, sleep stage breakdown
  - **Stress & Recovery Balance** (Oura): stress/recovery minutes, ratio, weekly trend, day summary distribution
  - **Training** (Hevy): sessions per week, total volume trends, progressive overload tracking, muscle group distribution
  - **Body Composition** (Boditrax): latest scan results, trend since previous scan, trajectory charts, MFP weight overlay
  - **Activity** (Oura): daily steps, active calories, movement trends
  - **Heart Rate** (Oura): RHR average, weekly trend, HR variability
  - **SpO2** (Oura): average SpO2, trend chart, breathing disturbance index
  - **Correlations**: cross-source insights as described above
  - **Alerts & Interventions**: 15+ alert types with severity levels (high/medium/low/positive) and actionable recommendations
  - **Summary**: top 3–5 actionable observations
- Charts: generate with matplotlib, embed as base64 PNGs in markdown
- Use clean, minimal chart styling — no gridline clutter, clear axis labels
- Weekly aggregation is the default time granularity for trend charts
- Always include a brief narrative interpretation beneath each chart
- If a data source has no new data since last report, note this and carry forward the last known values
- Include a **nutrition compliance** metric: % of days in the period with complete food logging

## Error Handling

- If any API returns 429 (rate limit), wait and retry with exponential backoff
- If a date range returns no data, log a warning and continue — do not fail the pipeline
- Validate API responses against expected schema before processing
- If `.env` is missing required tokens, log which sources are unavailable and proceed with the rest
- If Boditrax scraper fails, fall back to CSV mode and log the error
- If MFP CSV export directory is missing, log a warning and skip MFP
- The pipeline should always produce a report even if one or more sources are unavailable — just note the gaps

## Testing

- **Framework:** pytest
- **Run:** `.venv/bin/pytest tests/ -v`
- **62 tests** across 4 test files — all tests run without API calls or real data
- `tests/conftest.py` provides shared fixtures: sample DataFrames (30-row daily series, 5-row body comp) and MFP CSV content
- Tests use `tmp_path` for filesystem interaction (JSON/CSV files written to temp directories)
- When adding new transform/source functions, add corresponding tests with small inline fixture data
- When modifying report sections, add or update smoke tests that verify the section returns a string containing expected headings

## What Not to Do

- Do not hardcode any API tokens, keys, or passwords
- Do not commit `.env` or raw API tokens
- Do not use `print()` for logging — use the `logging` module
- Do not store heart rate data in CSV — use parquet
- Do not interpolate Boditrax body composition between scans
- Do not regenerate reports without confirming the date range with the user
- Do not make assumptions about Hevy weight units — always check and normalise to kg
- Do not skip zero-calorie MFP days — logging gaps are analytically meaningful