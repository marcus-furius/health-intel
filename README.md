# Health Intel

A unified health intelligence platform that consolidates data from **Oura Ring**, **Hevy**, **Boditrax**, and **MyFitnessPal** into a single pipeline with an interactive dashboard.

## What It Does

- **Extracts** data from four health/fitness sources via APIs and CSV imports
- **Transforms** raw data into cleaned, aligned daily datasets
- **Correlates** cross-source metrics (e.g. sleep quality vs training performance, protein intake vs recovery)
- **Visualises** everything in an interactive dashboard with trend charts, KPI cards, scatter plots, and actionable alerts

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Oura Ring   │     │    Hevy     │     │   Boditrax   │     │     MFP     │
│  (API v2)    │     │   (API)     │     │    (CSV)     │     │   (CSV)     │
└──────┬───────┘     └──────┬──────┘     └──────┬───────┘     └──────┬──────┘
       │                    │                    │                    │
       └────────────┬───────┴────────────┬───────┘                   │
                    │                    │                            │
              ┌─────▼────────────────────▼────────────────────────────▼──┐
              │                    Extract (src/extract.py)              │
              └─────────────────────────┬───────────────────────────────┘
                                        │
              ┌─────────────────────────▼───────────────────────────────┐
              │                  Transform (src/transform.py)           │
              └─────────────────────────┬───────────────────────────────┘
                                        │
                           ┌────────────▼────────────┐
                           │   data/processed/*.csv   │
                           └────────────┬────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
           ┌────────▼───────┐  ┌────────▼───────┐  ┌───────▼────────┐
           │  FastAPI (API)  │  │  Correlate     │  │  Report (.md)  │
           │  src/api/       │  │  src/correlate  │  │  src/report    │
           └────────┬───────┘  └────────────────┘  └────────────────┘
                    │
           ┌────────▼───────┐
           │   Dashboard     │
           │   (React/Vite)  │
           └────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- API tokens for Oura and Hevy (see [Environment Variables](#environment-variables))

### Setup

```bash
# Clone and set up Python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set up environment
cp .env.example .env  # Then fill in your tokens

# Install dashboard dependencies
cd dashboard && npm install && cd ..
```

### Run the Pipeline

```bash
# Extract data from all sources
.venv/bin/python -m src.extract

# Transform and process
.venv/bin/python -m src.transform

# Generate markdown report
.venv/bin/python -m src.report
```

### Run the Dashboard

```bash
# Start the API server
.venv/bin/uvicorn src.api.server:app --port 8000 --reload

# In another terminal, start the frontend
cd dashboard && npm run dev

# Or run both together
cd dashboard && npm run dev:full
```

Open **http://localhost:5173** to view the dashboard.

## Dashboard

The interactive dashboard provides 7 pages:

| Page | Content |
|---|---|
| **Overview** | KPI grid (sleep, readiness, steps, calories, training volume, weight) with sparklines, trend charts, top alerts, strongest correlations |
| **Sleep & Recovery** | Sleep score, readiness, HRV balance, SpO2 trends, sleep stage breakdown, stress vs recovery |
| **Training** | Weekly volume, muscle group distribution, progressive overload tracking per exercise |
| **Nutrition** | Calorie trends, macro split, protein per kg bodyweight with target band, logging compliance |
| **Body Composition** | Weight trajectory, body fat %, muscle mass trends, first-vs-latest scan comparison table |
| **Correlations** | Scatter plots with r-values for all cross-source correlations |
| **Alerts** | Severity-grouped alerts with expandable intervention recommendations |

### Tech Stack

- **Backend:** FastAPI serving processed CSVs as JSON
- **Frontend:** React 18 + TypeScript + Vite
- **Styling:** Tailwind CSS (dark mode default, light mode toggle)
- **Charts:** Recharts
- **Data fetching:** TanStack Query
- **Icons:** Lucide React

## Data Sources

| Source | Method | Data |
|---|---|---|
| **Oura Ring** | API v2 (Bearer token) | Sleep, readiness, activity, heart rate, SpO2, stress |
| **Hevy** | API (API key, requires Pro) | Workouts, exercises, sets, reps, weight |
| **Boditrax** | CSV export | Body composition scans (weight, body fat, muscle mass, visceral fat) |
| **MyFitnessPal** | Premium CSV export | Daily nutrition (calories, macros, micronutrients), weight |

## Environment Variables

Create a `.env` file in the project root:

```env
OURA_TOKEN=your_oura_token
HEVY_API_KEY=your_hevy_api_key
BODITRAX_MODE=csv
```

## Testing

```bash
.venv/bin/pytest tests/ -v
```

62 tests across 4 test files — all run without API calls or real data.

## Project Structure

```
health-intel/
├── src/
│   ├── sources/          # Data source clients (Oura, Hevy, Boditrax, MFP)
│   ├── api/              # FastAPI backend (server.py, routes.py)
│   ├── extract.py        # Orchestrates data pulls
│   ├── transform.py      # Cleaning, normalisation
│   ├── correlate.py      # Cross-source correlation analysis
│   └── report.py         # Markdown report generation + compute_alerts()
├── dashboard/            # React frontend (Vite + Tailwind + Recharts)
│   └── src/
│       ├── components/   # Layout, charts, UI components
│       ├── pages/        # 7 dashboard pages
│       ├── hooks/        # TanStack Query hooks, date range, theme
│       └── lib/          # API client, design tokens, formatters
├── data/
│   ├── raw/              # Immutable raw data from sources
│   └── processed/        # Cleaned CSVs consumed by API
├── reports/              # Generated markdown reports
└── tests/                # pytest test suite (62 tests)
```
