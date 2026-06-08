#!/usr/bin/env python3
"""
Re-apply human-confirmed matches from possible_matches into product_matches.

Why this script exists
----------------------
match_products.py now uses:

    DELETE FROM product_matches WHERE match_source = 'algorithm'

instead of TRUNCATE, so rows with match_source = 'human_confirmed' survive
every algorithm re-run automatically.  This script is therefore needed in
two specific situations:

  1. A new admin decision was just confirmed (the UI marks the possible_matches
     row as 'confirmed' but does not insert into product_matches itself —
     that is this script's job).

  2. After a full DB wipe + re-import, when all product_matches rows are gone
     and every confirmed decision must be re-applied from scratch.

The script is fully idempotent: if confirmed_match_id already points to an
existing human_confirmed row in product_matches, that group is skipped.

New scrape cycle
----------------
  scrape
  → import_products.py
  → match_products.py       (deletes algorithm rows, re-populates)
  → apply_confirmed.py      (ensures all confirmed decisions are in product_matches)
  → suggest_matches.py      (finds new near-miss candidates for review)

Usage
-----
  python scraper/apply_confirmed.py
  python scraper/apply_confirmed.py --dry-run
  python scraper/apply_confirmed.py --verbose
"""

import sys
import logging
import argparse
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.db_utils import get_db

# Source names in insertion order — must match product_matches column names.
SOURCES = ['ecuga', 'cugaklik', 'promili', 'diskontfumar', 'rotodinamic']


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def fetch_confirmed(cursor) -> list[dict]:
    """Return all confirmed possible_matches rows."""
    cursor.execute("""
        SELECT id,
               ecuga_id, cugaklik_id, promili_id,
               diskontfumar_id, rotodinamic_id,
               confirmed_match_id
          FROM possible_matches
         WHERE review_status = 'confirmed'
         ORDER BY id
    """)
    return [dict(row) for row in cursor.fetchall()]


def match_row_exists(cursor, match_id: int) -> bool:
    """Return True if a human_confirmed product_matches row with this id exists."""
    cursor.execute(
        """
        SELECT 1 FROM product_matches
         WHERE id = %s AND match_source = 'human_confirmed'
        """,
        (match_id,),
    )
    return cursor.fetchone() is not None


def all_products_available(cursor, pm: dict) -> tuple[bool, list[str]]:
    """
    Check that every non-null product in this possible_matches row is still
    present and marked available.

    Returns (ok: bool, missing_sources: list[str]).
    """
    id_by_source = {
        src: pm[f'{src}_id']
        for src in SOURCES
        if pm[f'{src}_id'] is not None
    }
    if not id_by_source:
        return False, list(SOURCES)

    ids = list(id_by_source.values())
    cursor.execute(
        """
        SELECT id FROM products
         WHERE id = ANY(%s) AND is_available = true
        """,
        (ids,),
    )
    available_ids = {row['id'] for row in cursor.fetchall()}
    missing = [src for src, pid in id_by_source.items() if pid not in available_ids]
    return len(missing) == 0, missing


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def apply_confirmed(
    conn,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Ensure every confirmed possible_match has a corresponding row in
    product_matches with match_source = 'human_confirmed'.

    Returns a stats dict.
    """
    stats = {
        'confirmed_loaded':         0,
        'rows_already_present':     0,
        'rows_skipped_unavailable': 0,
        'rows_inserted':            0,
    }

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        confirmed = fetch_confirmed(cur)
        stats['confirmed_loaded'] = len(confirmed)
        logging.info(f"Found {len(confirmed)} confirmed possible_match(es).")

        for pm in confirmed:
            pm_id = pm['id']

            # If confirmed_match_id already points to a live human_confirmed row,
            # nothing to do — it survived the last match_products.py run.
            existing_mid = pm['confirmed_match_id']
            if existing_mid is not None and match_row_exists(cur, existing_mid):
                logging.debug(
                    f"  PM {pm_id}: product_matches id={existing_mid} still present — skip"
                )
                stats['rows_already_present'] += 1
                continue

            # Guard: all referenced products must still be available.
            ok, missing = all_products_available(cur, pm)
            if not ok:
                logging.warning(
                    f"  PM {pm_id}: products unavailable for "
                    f"{', '.join(missing)} — skipping"
                )
                stats['rows_skipped_unavailable'] += 1
                continue

            sources_present = [s for s in SOURCES if pm[f'{s}_id'] is not None]
            if verbose:
                logging.info(
                    f"  PM {pm_id}: inserting human_confirmed row "
                    f"({', '.join(sources_present)})"
                )

            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO product_matches
                        (ecuga_id, cugaklik_id, promili_id,
                         diskontfumar_id, rotodinamic_id,
                         match_source)
                    VALUES (%s, %s, %s, %s, %s, 'human_confirmed')
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    [pm[f'{src}_id'] for src in SOURCES],
                )
                row = cur.fetchone()
                if row:
                    new_id = row['id']
                    logging.debug(f"  PM {pm_id}: created product_matches id={new_id}")
                else:
                    # Conflict: one of the product IDs is already in product_matches.
                    # Find the existing row and use it as the back-reference.
                    ids = [pm[f'{src}_id'] for src in SOURCES if pm[f'{src}_id'] is not None]
                    placeholders = ','.join(['%s'] * len(ids))
                    cur.execute(
                        f"""
                        SELECT id FROM product_matches
                         WHERE ecuga_id = ANY(%s::int[])
                            OR cugaklik_id = ANY(%s::int[])
                            OR promili_id = ANY(%s::int[])
                            OR diskontfumar_id = ANY(%s::int[])
                            OR rotodinamic_id = ANY(%s::int[])
                         LIMIT 1
                        """,
                        [ids] * 5,
                    )
                    existing = cur.fetchone()
                    new_id = existing['id'] if existing else None
                    logging.debug(
                        f"  PM {pm_id}: conflict — reusing product_matches id={new_id}"
                    )

                # Update the back-reference so future runs can skip this row.
                cur.execute(
                    """
                    UPDATE possible_matches
                       SET confirmed_match_id = %s,
                           updated_at         = CURRENT_TIMESTAMP
                     WHERE id = %s
                    """,
                    (new_id, pm_id),
                )

            stats['rows_inserted'] += 1

    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Re-apply human-confirmed matches from possible_matches into '
            'product_matches (idempotent).'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be inserted without writing to the database.',
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Print each confirmed group as it is processed.',
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s  %(levelname)-7s %(message)s',
        datefmt='%H:%M:%S',
    )

    if args.dry_run:
        logging.info('DRY RUN — nothing will be written to the database.')

    db = get_db()
    db.initialize_pool()

    with db.get_connection() as conn:
        stats = apply_confirmed(conn, dry_run=args.dry_run, verbose=args.verbose)

    print(f'\n{"═" * 60}')
    print('APPLY CONFIRMED SUMMARY')
    print(f'{"═" * 60}')
    if args.dry_run:
        print('  ⚠  DRY RUN — nothing was written to the database')
    print(f'  Confirmed possible_matches loaded : {stats["confirmed_loaded"]}')
    print(f'  Already in product_matches        : {stats["rows_already_present"]}')
    print(f'  Skipped (products unavailable)    : {stats["rows_skipped_unavailable"]}')
    print(f'  Newly inserted                    : {stats["rows_inserted"]}')
    print(f'{"═" * 60}')


if __name__ == '__main__':
    main()
