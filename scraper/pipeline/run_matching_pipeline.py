#!/usr/bin/env python3
"""
Full match + suggestion pipeline runner.

Runs the complete sequence in the correct order:

  Step 1 — match_products.py
      Deletes algorithm-generated rows from product_matches, re-runs the
      Jaccard/trigram algorithm, and inserts confirmed match groups.
      Human-confirmed rows (match_source='human_confirmed') are untouched.

  Step 2 — apply_confirmed.py
      Re-applies any human-confirmed decisions whose product_matches row is
      missing (e.g. after a full DB wipe).  Idempotent: already-present rows
      are skipped.

  Step 3 — suggest_matches.py
      Finds near-miss pairs (0.55–0.69) and overlap-disagreement pairs that
      the main algorithm didn't match, and queues them in possible_matches
      for human review.

  Step 4 — seed_possible_matches.py   [skippable with --skip-seed]
      One-time seed of the 11 ambiguous groups from claude_prompts/inspection.json.
      Safe to re-run (fingerprint deduplication means nothing is inserted twice).

Usage
-----
  python scraper/start_flow.py                   # full run
  python scraper/start_flow.py --dry-run         # preview only, no DB writes
  python scraper/start_flow.py --category whisky # one category (steps 1 + 3)
  python scraper/start_flow.py --skip-seed       # omit step 4
  python scraper/start_flow.py --verbose         # verbose output for all steps
"""

import sys
import time
import argparse
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT     = Path(__file__).parent.parent.parent   # project root
SCRAPER  = Path(__file__).parent.parent          # scraper/
MATCHING = SCRAPER / 'matching'                  # scraper/matching/

STEPS = [
    {
        'name':   'match_products',
        'script': MATCHING / 'match_products.py',
        'desc':   'Algorithm matching → product_matches',
        'args':   ['--category', '--no-reset', '--threshold'],  # pass-through keys
    },
    {
        'name':   'apply_confirmed',
        'script': MATCHING / 'apply_confirmed.py',
        'desc':   'Re-apply human-confirmed decisions → product_matches',
        'args':   [],
    },
    {
        'name':   'suggest_matches',
        'script': MATCHING / 'suggest_matches.py',
        'desc':   'Near-miss + overlap pairs → possible_matches',
        'args':   ['--category', '--near-miss-min'],
    },
    {
        'name':   'seed_possible_matches',
        'script': MATCHING / 'seed_possible_matches.py',
        'desc':   'Manual seed of inspection.json ambiguous groups → possible_matches',
        'args':   [],
    },
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_dir  = ROOT / 'logs'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_step(
    step:      dict,
    extra_args: list[str],
    dry_run:   bool,
    verbose:   bool,
) -> tuple[bool, float]:
    """
    Execute one pipeline step as a subprocess.

    Returns (success, elapsed_seconds).
    Streams output directly to stdout/stderr so the user sees progress live.
    """
    cmd = [sys.executable, str(step['script'])] + extra_args
    if dry_run:
        cmd.append('--dry-run')
    if verbose:
        cmd.append('--verbose')

    log.info(f"  Command: {' '.join(str(c) for c in cmd)}")
    t0 = time.time()

    result = subprocess.run(cmd, cwd=ROOT)

    elapsed = time.time() - t0
    ok = result.returncode == 0
    return ok, elapsed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Run the full match + suggestion pipeline.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Pass --dry-run to every step; nothing is written to the DB.',
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Pass --verbose to every step.',
    )
    parser.add_argument(
        '--category', metavar='SLUG',
        help='Limit matching and suggestion to one category (e.g. whisky).',
    )
    parser.add_argument(
        '--skip-seed', action='store_true',
        help='Skip step 4 (seed_possible_matches.py). Use after the first run.',
    )
    parser.add_argument(
        '--near-miss-min', type=float, metavar='SCORE',
        help='Override near-miss lower bound passed to suggest_matches.py (default 0.55).',
    )
    parser.add_argument(
        '--threshold', type=float, metavar='SCORE',
        help='Override Jaccard threshold passed to match_products.py (default 0.70).',
    )
    args = parser.parse_args()

    # ---- Print header ----
    bar = '═' * 64
    log.info(bar)
    log.info('MATCH + SUGGESTION PIPELINE')
    log.info(f'Started : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    if args.dry_run:
        log.info('Mode    : DRY RUN — no DB writes')
    if args.category:
        log.info(f'Category: {args.category}')
    log.info(bar)

    # ---- Build per-step extra args ----
    # match_products.py
    mp_args: list[str] = []
    if args.category:
        mp_args += ['--category', args.category]
    if args.threshold:
        mp_args += ['--threshold', str(args.threshold)]

    # suggest_matches.py
    sm_args: list[str] = []
    if args.category:
        sm_args += ['--category', args.category]
    if args.near_miss_min:
        sm_args += ['--near-miss-min', str(args.near_miss_min)]

    steps_to_run = [
        (STEPS[0], mp_args),             # match_products
        (STEPS[1], []),                  # apply_confirmed
        (STEPS[2], sm_args),             # suggest_matches
    ]
    if not args.skip_seed:
        steps_to_run.append((STEPS[3], []))   # seed_possible_matches

    # ---- Execute ----
    results: list[dict] = []

    for i, (step, extra) in enumerate(steps_to_run, 1):
        log.info('')
        log.info(f'[{i}/{len(steps_to_run)}] {step["name"]}')
        log.info(f'  {step["desc"]}')

        ok, elapsed = run_step(step, extra, dry_run=args.dry_run, verbose=args.verbose)

        results.append({'name': step['name'], 'ok': ok, 'elapsed': elapsed})

        if ok:
            log.info(f'  ✓ Done in {elapsed:.1f}s')
        else:
            log.error(f'  ✗ Failed after {elapsed:.1f}s — stopping pipeline')
            break   # do not continue if a step fails

    # ---- Summary ----
    log.info('')
    log.info(bar)
    log.info('PIPELINE SUMMARY')
    log.info(bar)
    if args.dry_run:
        log.info('  ⚠  DRY RUN — nothing was written to the database')
    for r in results:
        status = '✓' if r['ok'] else '✗'
        log.info(f'  {status}  {r["name"]:<28}  {r["elapsed"]:>6.1f}s')

    total = sum(r['elapsed'] for r in results)
    all_ok = all(r['ok'] for r in results)

    log.info(bar)
    log.info(f'  Total elapsed : {total:.1f}s')
    log.info(f'  Log file      : {log_file}')
    log.info(bar)

    if not all_ok:
        log.info('')
        log.info('Pipeline did not complete — fix the failing step and re-run.')
        log.info('Re-running is safe: each step is idempotent.')

    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
