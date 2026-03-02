# Health Intel Dashboard: Strategic Migration Plan

This document outlines the architectural and design strategy for transitioning the **Health Intel** project from a static Markdown report generator into a world-class, interactive health intelligence dashboard.

## 1. Vision & Aesthetic
The objective is to create a "System of Intelligence" that feels like a native Google or Anthropic product:
- **Typography**: Clean, professional (Inter or Geist Sans).
- **Palette**: Minimalist "Zinc" and "Slate" with high-signal accent colors (Success/Warning/Destructive).
- **Interactivity**: Fluid transitions, meaningful tooltips, and real-time data exploration.

## 2. Technical Stack

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Frontend Framework** | Next.js 15 (App Router) | High-performance React framework with excellent developer experience. |
| **Styling** | Tailwind CSS + Shadcn/UI | Atomic CSS for speed; Shadcn for high-quality, accessible components. |
| **Data Visualization** | Recharts / Tremor | SVG-based interactive charts designed for dashboards. |
| **Backend API** | FastAPI (Python) | High-speed, typed Python API that leverages existing data logic. |
| **State Management** | TanStack Query | Robust caching and synchronization for an "alive" feel. |

---

## 3. Implementation Roadmap

### Phase 1: Backend Modernization (The "Brain")
Decouple the existing report logic from Markdown generation to serve structured JSON.
- **API Scaffold**: Create a FastAPI server in `api/` or `src/api/`.
- **Data Presenters**: Refactor `src/report.py` logic into `src/presenters/` to return Pydantic models (raw metrics, trend slopes, and correlation coefficients).
- **Core Endpoints**:
    - `GET /api/dashboard/summary`: High-level metric cards and the "Alerts" feed.
    - `GET /api/metrics/{source}`: Detailed time-series data for Sleep, Training, Nutrition, etc.
    - `GET /api/correlations`: Cross-source insight data for interactive scatter plots.

### Phase 2: Design System & Layout (The "Look")
Establish the visual foundation and navigation.
- **Scaffold Project**: Initialize Next.js with TypeScript and Tailwind.
- **Navigation Rail**: A fixed sidebar for quick switching between "Home", "Sleep", "Training", and "Analysis".
- **Theme Engine**: Implement dual-mode (Dark/Light) support using `next-themes`.
- **Global Search**: A Command Menu (Cmd+K) for jumping to specific metrics or date ranges.

### Phase 3: Intelligence & Interactivity (The "Feel")
Transform static charts into interactive windows.
- **Dynamic Time-series**: Replace Matplotlib PNGs with Recharts Area/Bar charts.
- **The "Alerts" Feed**: Interactive notification center with severity levels and "Recommended Action" buttons.
- **Correlation Explorer**: A dedicated view where users can toggle X/Y axes (e.g., "Protein vs. HRV") to discover personal biological trends.

### Phase 4: Refinement & Polish (The "Wow")
Elevate the user experience with micro-interactions.
- **Shimmer Loaders**: Elegant skeleton states while the pipeline extracts/transforms data.
- **Framer Motion**: Subtle entrance animations for dashboard widgets.
- **Export Center**: A high-fidelity "Print/PDF" mode that mirrors the dashboard's aesthetics for archival use.

---

## 4. Architectural Evolution

### Current: Monolithic CLI
- **Flow**: `main.py` -> `extract` -> `transform` -> `correlate` -> `report.py` (Markdown).
- **Output**: Static `.md` file with embedded base64 images.

### Target: Client-Server Architecture
- **Backend**: FastAPI serves as the "Orchestrator," running the pipeline and caching results in the `data/processed` layer.
- **Frontend**: Next.js fetches processed data and renders interactive visualizations on-demand.
- **Storage**: Maintain the current CSV/JSON file-based "Lakehouse" for simplicity, with an optional SQLite layer for faster querying of historical trends.

---

## 5. Success Metrics
- **Performance**: Dashboard loads in <2s (using cached data).
- **Insight Density**: Users can identify a recovery/training correlation in <3 clicks.
- **Aesthetic**: The UI is indistinguishable from a top-tier Silicon Valley productivity tool.
