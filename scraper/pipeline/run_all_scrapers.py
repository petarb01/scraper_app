#!/usr/bin/env python3
"""
Master orchestrator script for running all web scrapers sequentially.
This script runs all scrapers one by one to respect compute resource limitations.
"""

import sys
import time
import logging
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Configure logging
log_dir = Path(__file__).parent.parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / f"scraper_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Define all scrapers to run
SCRAPERS = [
    {
        "name": "ecuga",
        "path": "scrapers/ecuga/__init__.py",
        "description": "E-Cuga website scraper"
    },
    {
        "name": "cugaklik",
        "path": "scrapers/cugaklik/__init__.py",
        "description": "Cugaklik website scraper"
    },
    {
        "name": "promili",
        "path": "scrapers/promili/__init__.py",
        "description": "Promili website scraper"
    },
    {
        "name": "diskontfumar",
        "path": "scrapers/diskontfumar/__init__.py",
        "description": "Diskont Fumar website scraper"
    },
    {
        "name": "rotodinamic",
        "path": "scrapers/rotodinamic/__init__.py",
        "description": "Rotodinamic website scraper"
    }
]

# Delay between scrapers (in seconds) to avoid overwhelming resources
INTER_SCRAPER_DELAY = 10


def check_xvfb_available() -> bool:
    """Check if Xvfb is available on the system."""
    try:
        result = subprocess.run(
            ["which", "xvfb-run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def run_scraper(scraper: Dict[str, str], use_xvfb: bool = False) -> Tuple[bool, str, float]:
    """
    Run a single scraper and return success status, output, and execution time.

    Args:
        scraper: Dictionary containing scraper information
        use_xvfb: Whether to use Xvfb for virtual display

    Returns:
        Tuple of (success, output, execution_time)
    """
    scraper_name = scraper["name"]
    scraper_path = Path(__file__).parent.parent / scraper["path"]

    logger.info(f"{'='*60}")
    logger.info(f"Starting scraper: {scraper_name}")
    logger.info(f"Description: {scraper['description']}")
    logger.info(f"Path: {scraper_path}")
    logger.info(f"{'='*60}")

    if not scraper_path.exists():
        logger.error(f"Scraper file not found: {scraper_path}")
        return False, f"File not found: {scraper_path}", 0.0

    # Build command
    if use_xvfb:
        cmd = ["xvfb-run", "-a", sys.executable, str(scraper_path)]
        logger.info("Using Xvfb for virtual display")
    else:
        cmd = [sys.executable, str(scraper_path)]

    start_time = time.time()

    try:
        # Run the scraper with timeout
        result = subprocess.run(
            cmd,
            cwd=scraper_path.parent,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout per scraper
        )

        execution_time = time.time() - start_time

        # Log output
        if result.stdout:
            logger.info(f"STDOUT from {scraper_name}:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"STDERR from {scraper_name}:\n{result.stderr}")

        success = result.returncode == 0

        if success:
            logger.info(f"✓ Scraper {scraper_name} completed successfully in {execution_time:.2f}s")
        else:
            logger.error(f"✗ Scraper {scraper_name} failed with return code {result.returncode}")

        output = result.stdout + result.stderr
        return success, output, execution_time

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        logger.error(f"✗ Scraper {scraper_name} timed out after {execution_time:.2f}s")
        return False, "Timeout expired", execution_time

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"✗ Scraper {scraper_name} failed with exception: {e}")
        return False, str(e), execution_time


def main():
    """Main orchestrator function."""
    logger.info("="*80)
    logger.info("WEB SCRAPER ORCHESTRATOR - Starting")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Total scrapers to run: {len(SCRAPERS)}")
    logger.info("="*80)

    # Check for Xvfb
    use_xvfb = check_xvfb_available()
    if use_xvfb:
        logger.info("✓ Xvfb detected - will use virtual display for stability")
    else:
        logger.warning("⚠ Xvfb not found - running without virtual display")
        logger.warning("  Install with: sudo apt-get install xvfb")

    results = []
    total_start_time = time.time()

    for idx, scraper in enumerate(SCRAPERS, 1):
        logger.info(f"\n[{idx}/{len(SCRAPERS)}] Processing scraper: {scraper['name']}")

        success, output, exec_time = run_scraper(scraper, use_xvfb=use_xvfb)

        results.append({
            "scraper": scraper["name"],
            "success": success,
            "execution_time": exec_time,
            "timestamp": datetime.now().isoformat()
        })

        # Delay between scrapers (except after the last one)
        if idx < len(SCRAPERS):
            logger.info(f"Waiting {INTER_SCRAPER_DELAY}s before next scraper...")
            time.sleep(INTER_SCRAPER_DELAY)

    total_time = time.time() - total_start_time

    # Summary
    logger.info("\n" + "="*80)
    logger.info("EXECUTION SUMMARY")
    logger.info("="*80)

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    logger.info(f"Total scrapers: {len(results)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total execution time: {total_time:.2f}s ({total_time/60:.2f} minutes)")
    logger.info("")

    # Individual scraper results
    for result in results:
        status = "✓ SUCCESS" if result["success"] else "✗ FAILED"
        logger.info(f"  {status} - {result['scraper']}: {result['execution_time']:.2f}s")

    # Save results summary
    summary_file = log_dir / "last_run_summary.json"
    with open(summary_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_time": total_time,
            "successful": successful,
            "failed": failed,
            "scrapers": results
        }, f, indent=2)

    logger.info(f"\nSummary saved to: {summary_file}")
    logger.info(f"Full log saved to: {log_file}")
    logger.info("="*80)

    # Exit with error code if any scraper failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
