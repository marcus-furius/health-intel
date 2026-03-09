"""FastAPI server — loads processed CSVs at startup and serves JSON."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/processed")

# In-memory store populated at startup
datasets: dict[str, pd.DataFrame] = {}


def load_datasets() -> dict[str, pd.DataFrame]:
    """Read all processed CSVs/parquet into DataFrames."""
    loaded: dict[str, pd.DataFrame] = {}
    csv_files = {
        "sleep": "sleep.csv",
        "readiness": "readiness.csv",
        "activity": "activity.csv",
        "stress": "stress.csv",
        "spo2": "spo2.csv",
        "workouts": "workouts.csv",
        "nutrition": "nutrition.csv",
        "body_composition": "body_composition.csv",
        "mfp_weight": "mfp_weight.csv",
        "bloodwork": "bloodwork.csv",
    }
    for name, filename in csv_files.items():
        path = DATA_DIR / filename
        if path.exists():
            df = pd.read_csv(path)
            if "day" in df.columns:
                df["day"] = pd.to_datetime(df["day"])
            loaded[name] = df
            logger.info("Loaded %s: %d rows", name, len(df))
        else:
            logger.warning("Missing %s", path)

    # Heart rate as parquet
    hr_path = DATA_DIR / "heartrate.parquet"
    if hr_path.exists():
        loaded["heartrate"] = pd.read_parquet(hr_path)
        logger.info("Loaded heartrate: %d rows", len(loaded["heartrate"]))

    return loaded


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data on startup."""
    global datasets
    datasets = load_datasets()
    logger.info("Loaded %d datasets", len(datasets))
    yield
    datasets.clear()


app = FastAPI(title="Health Intel API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
