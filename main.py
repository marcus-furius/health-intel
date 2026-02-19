"""Unified Health Intelligence Pipeline — main entry point.

Orchestrates: extract → transform → correlate → report.
Handles partial source availability gracefully.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
REPORTS_DIR = PROJECT_DIR / "reports"


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified Health Intelligence Pipeline")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD). Default: 365 days ago.")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD). Default: today.")
    parser.add_argument("--skip-extract", action="store_true", help="Skip extraction, use existing raw data.")
    args = parser.parse_args()

    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = args.start_date or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    # Load .env
    load_dotenv(PROJECT_DIR / ".env")

    # Check what sources are available
    sources_status = {
        "Oura": bool(os.getenv("OURA_TOKEN")),
        "Hevy": bool(os.getenv("HEVY_API_KEY")),
        "Boditrax": True,  # CSV mode always available
        "MFP": os.getenv("MFP_ENABLED", "true").lower() != "false",
    }
    available = [name for name, ready in sources_status.items() if ready]
    unavailable = [name for name, ready in sources_status.items() if not ready]

    if unavailable:
        logger.warning("Unavailable sources (missing credentials): %s", ", ".join(unavailable))
    logger.info("Available sources: %s", ", ".join(available))
    logger.info("Pipeline: %s to %s", start_date, end_date)

    # Step 1: Extract
    if not args.skip_extract:
        from src.extract import extract_all
        logger.info("=== EXTRACTION ===")
        counts = extract_all(start_date, end_date, DATA_DIR)
        for source, source_counts in counts.items():
            logger.info("  %s: %s", source, source_counts)
    else:
        logger.info("Skipping extraction (--skip-extract)")

    # Step 2: Transform
    from src.transform import transform_all
    logger.info("=== TRANSFORMATION ===")
    datasets = transform_all(DATA_DIR)

    # Step 3: Correlate
    from src.correlate import compute_correlations
    logger.info("=== CORRELATION ANALYSIS ===")
    correlations = compute_correlations(datasets)

    # Step 4: Report
    from src.report import generate_report
    logger.info("=== REPORT GENERATION ===")
    report_path = generate_report(start_date, end_date, datasets, correlations, REPORTS_DIR)
    logger.info("Report saved to: %s", report_path)

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()
