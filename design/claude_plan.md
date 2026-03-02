# Interactive Health Dashboard

## Context

The health-intel project has a mature Python ETL pipeline producing processed CSVs (sleep, readiness, activity, workouts, nutrition, body composition, stress, SpO2) and a static markdown report. The goal is to replace the markdown report with a professional interactive dashboard — visually on par with Anthropic/Apple/Google products. The pipeline already produces all the data; we need a presentation layer.

## Tech Stack

**React (Vite) + Tailwind CSS + Recharts + FastAPI backend**

- **FastAPI** serves the existing processed CSVs as JSON — thin layer, reuses existing `correlate.py` and alert logic from `report.py`
- **React 18 + TypeScript** for the frontend — maximum control over design polish
- **Tailwind CSS** for utility-first styling — clean typography, dark mode, spacing
- **Recharts** for data visualisation — composable SVG charts, easily styled
- **TanStack Query** for data fetching — caching, background refetching, retries, loading states out of the box (replaces custom useApi hook)
- **Shadcn/UI + Radix primitives** for accessible base components — DateRangePicker, dialogs, dropdowns; hand-roll only chart and metric components
- **Pydantic response models** on all FastAPI endpoints — typed contracts, auto-generated OpenAPI docs
- Dash/Streamlit rejected: lower ceiling for the "Anthropic/Apple" aesthetic

## Project Structure

```
health-intel/
├── src/api/                        # NEW — FastAPI backend
│   ├── __init__.py
│   ├── server.py                   # App, CORS, lifespan (loads CSVs on startup)
│   └── routes.py                   # All endpoints in one file (data is small)
├── dashboard/                      # NEW — React frontend
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                 # Router, theme provider, layout shell
│       ├── index.css               # Tailwind directives, Inter font, custom props
│       ├── lib/
│       │   ├── api.ts              # Fetch wrapper, types
│       │   ├── colors.ts           # Design tokens
│       │   └── format.ts           # Number/date formatting helpers
│       ├── hooks/
│       │   ├── queries.ts          # TanStack Query hooks for all endpoints
│       │   ├── useDateRange.ts     # Global date range context
│       │   └── useTheme.ts         # Dark/light toggle
│       ├── components/
│       │   ├── layout/
│       │   │   ├── Shell.tsx       # Sidebar + main area
│       │   │   ├── Sidebar.tsx     # Nav links with icons
│       │   │   └── Header.tsx      # Page title + date range picker
│       │   ├── charts/
│       │   │   ├── TrendChart.tsx   # Area/line chart (most-used)
│       │   │   ├── BarChart.tsx
│       │   │   ├── StackedBar.tsx
│       │   │   ├── ScatterPlot.tsx
│       │   │   └── SparkLine.tsx
│       │   └── ui/
│       │       ├── MetricCard.tsx   # KPI with sparkline + trend arrow
│       │       ├── AlertCard.tsx    # Severity-coded alert
│       │       ├── ChartCard.tsx    # Chart wrapper with title + loading
│       │       ├── Badge.tsx
│       │       ├── DateRangePicker.tsx # Built on Radix Popover + react-day-picker
│       │       ├── Skeleton.tsx
│       │       └── PrintExport.tsx  # PDF/print export button (window.print with @media print styles)
│       └── pages/
│           ├── Overview.tsx         # KPI grid + key charts + alerts
│           ├── SleepRecovery.tsx    # Sleep + readiness + HRV + SpO2
│           ├── Training.tsx         # Volume, muscle groups, overload
│           ├── Nutrition.tsx        # Calories, macros, protein/kg
│           ├── BodyComposition.tsx  # Weight, body fat, muscle mass
│           ├── Correlations.tsx     # Scatter plots grid
│           └── Alerts.tsx           # All alerts grouped by severity
├── requirements.txt                # Add: fastapi, uvicorn
└── (existing src/, data/, tests/)
```

## API Design

FastAPI loads all processed CSVs into memory at startup (~5K rows total). Endpoints:

| Endpoint | Returns |
|---|---|
| `GET /api/overview` | KPI summary, 30-day sparklines, alert counts |
| `GET /api/sleep?start=&end=` | Daily sleep data + weekly aggregates |
| `GET /api/readiness?start=&end=` | Daily readiness + HRV balance |
| `GET /api/activity?start=&end=` | Daily steps, active calories |
| `GET /api/stress?start=&end=` | Daily stress/recovery minutes |
| `GET /api/spo2?start=&end=` | Daily SpO2 + breathing index |
| `GET /api/training?start=&end=` | Daily session summaries (aggregated from set-level) |
| `GET /api/training/exercises` | Per-exercise volume history |
| `GET /api/training/muscle-groups` | Volume by muscle group |
| `GET /api/nutrition?start=&end=` | Daily nutrition + meal breakdowns |
| `GET /api/body-composition` | All scans (sparse, no date filter needed) |
| `GET /api/weight` | Combined Boditrax + MFP weight series |
| `GET /api/correlations` | All correlation r-values + scatter data |
| `GET /api/alerts` | Structured alerts with severity + interventions |
| `POST /api/reload` | Re-read CSVs after pipeline run |

All list endpoints accept optional `start` and `end` query params (ISO dates).

## Dashboard Pages

### Overview (landing page)
- **6 MetricCards** in 3×2 grid: Sleep Score, Readiness Score, Daily Steps, Avg Calories, Training Volume/wk, Current Weight — each with 30-day sparkline and trend arrow
- **Two half-width charts**: Sleep+Readiness overlay trend (weekly), Stress vs Recovery stacked bar (weekly)
- **Top 3 alerts** as AlertCards
- **Correlation highlights**: top 3 strongest correlations as mini scatter previews

### Sleep & Recovery
- KPIs: Sleep score avg, Readiness avg, HRV balance, SpO2 avg
- Charts: Sleep score trend (area), Readiness trend (area), HRV balance (line), Sleep stage breakdown (stacked bar), SpO2 trend (line with 95% threshold), Breathing disturbance index

### Training
- KPIs: Sessions/week, Weekly volume, Progressive overload indicator
- Charts: Weekly volume (bar), Muscle group distribution (horizontal bar), Exercise selector + progressive overload line, Training frequency heatmap

### Nutrition
- KPIs: Avg calories, Protein/day, Protein per kg, Logging compliance %, Caloric balance
- Charts: Calorie trend (area), Macro split (stacked bar), Protein/kg with 1.6–2.2 target band, Meal calorie distribution (horizontal bar)

### Body Composition
- KPIs: Weight, Body fat %, Muscle mass, Visceral fat, Metabolic age
- Charts: Weight trajectory (Boditrax scans + MFP daily), Body fat % trend, Muscle mass trend
- Table: First vs latest scan comparison

### Correlations
- 2-column grid of ScatterPlots, each with r-value badge (strong/moderate/weak), hover tooltips showing date + values
- 9 scatter correlations + 2 body comp narrative cards

### Alerts
- Grouped by severity (high → medium → low → positive)
- Each card: severity icon, title, detail, expandable intervention list
- Filter toggles by severity

## Design System

**Dark mode default** (toggle to light):
- Backgrounds: `#0A0A0B` (base) → `#141416` (cards) → `#1C1C1F` (elevated)
- Light mode: `#FAFAFA` → `#FFFFFF` → `#F4F4F5`
- Text: `#F4F4F5` primary, `#A1A1AA` secondary, `#71717A` muted
- Borders: `#27272A` subtle, `#3F3F46` default

**Chart palette** (works on dark and light):
- Blue `#3B82F6` — sleep
- Emerald `#10B981` — recovery/positive
- Amber `#F59E0B` — warnings
- Rose `#F43F5E` — stress/high alerts
- Violet `#8B5CF6` — training
- Orange `#F97316` — nutrition
- Cyan `#06B6D4` — SpO2

**Typography**: Inter font, Tailwind scale. KPI values at `text-4xl font-semibold`, card titles `text-lg font-medium`.

**Cards**: `rounded-xl`, `border` with subtle border color, `p-6`, hover brightens border + adds shadow. No gridlines on charts. Generous whitespace (`gap-6` between cards, `gap-8` between sections).

## Implementation Sequence

### Phase 1: Backend API
1. Add `fastapi`, `uvicorn` to `requirements.txt`
2. Create `src/api/server.py` — app with lifespan CSV loader, CORS
3. Create `src/api/routes.py` — all endpoints reading from in-memory DataFrames
4. Extract alert logic from `report.py` into reusable `compute_alerts()` function
5. Verify: `curl localhost:8000/api/overview` returns JSON

### Phase 2: Frontend scaffold
1. Init Vite + React + TypeScript in `dashboard/`
2. Install + configure Tailwind, Shadcn/UI, TanStack Query, add Inter font
3. Build layout: `Shell`, `Sidebar`, `Header`, `ThemeToggle`
4. Set up React Router with all 7 page routes
5. Implement TanStack Query hooks (`queries.ts`), `useDateRange`, `useTheme`
6. Vite proxy config → `/api` proxied to `:8000`

### Phase 3: Reusable components
1. `MetricCard` with `SparkLine`
2. `TrendChart` (area/line), `BarChart`, `StackedBar`, `ScatterPlot`
3. `ChartCard`, `AlertCard`, `Badge`, `DateRangePicker`, `Skeleton`

### Phase 4: Pages
1. Overview → the most important page, build first
2. Sleep & Recovery
3. Training
4. Nutrition
5. Body Composition
6. Correlations
7. Alerts

### Phase 5: Polish
1. Dark/light transitions, loading skeletons, empty states
2. Chart tooltip styling, hover interactions
3. Responsive tweaks for narrower viewports
4. PDF/print export — `@media print` stylesheet that renders a clean single-page report from the Overview page, preserving the archival use case of the old markdown report

## Existing Code to Reuse

- `src/correlate.py:compute_correlations()` — called directly by the API to produce correlation data
- `src/report.py:_alerts_section()` (lines 791–1177) — alert logic extracted into a `compute_alerts()` function returning `list[dict]` instead of markdown
- `src/report.py:_corr_strength()` — reused for correlation strength labels
- `src/report.py:_recent_trend()` — reused for KPI trend calculations
- `data/processed/*.csv` — read by FastAPI at startup, served as JSON

## Changes to Existing Files

- `requirements.txt` — add `fastapi`, `uvicorn[standard]`
- `src/report.py` — extract alert computation into standalone `compute_alerts()` function (existing `_alerts_section` calls it and formats as markdown; API calls it and returns JSON)

## Verification

```bash
# Backend
.venv/bin/uvicorn src.api.server:app --port 8000
curl http://localhost:8000/api/overview | python -m json.tool

# Frontend
cd dashboard && npm run dev
# Open http://localhost:5173 — should show Overview with live data

# Full stack
cd dashboard && npm run dev:full
# Runs both servers concurrently
```
