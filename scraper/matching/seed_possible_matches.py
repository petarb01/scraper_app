#!/usr/bin/env python3
"""
One-time seed: populate possible_matches with the ambiguous groups identified
during manual inspection of matched_products.json.

Source file: claude_prompts/inspection.json
Seed scope:  groups with classification = "ambiguous" (11 groups total)

These are products the algorithm cannot resolve because they involve:
  — gift sets / value-added packs (glasses, chocolates, tubes bundled)
  — limited / lux editions with significant price premiums
  — multi-pack + different sub-brand (double ambiguity)
  — vintage vs non-vintage champagne
  — a store consistently dropping a product qualifier (XO)

For each group this script:
  1. Looks up each entry's product in the DB by (source_name, original_title).
  2. Skips the whole group if any resolved product is already in product_matches
     (meaning it was auto-matched after the NOISE_WORDS improvements).
  3. Inserts a possible_matches row with suggestion_source = 'seed_inspection'.
  4. Uses ON CONFLICT (group_fingerprint) DO NOTHING, so re-running is safe.

Notes
-----
  • Group 29 (BUMBU CREAM): ecuga entry has no volume in its title — it was a
    NULL-volume product.  After the RC1 NULL-bucket fix to match_products.py it
    may already be auto-matched; step 2 above handles that.

  • Group 46 (DICTADOR XO PLATINUM): ecuga omits "XO".  After adding 'xo' to
    STRONG_VARIANT_WORDS the main algorithm correctly rejects this pair, so it
    will not be in product_matches and will be seeded here for human review.

  • Group 49 (BUMBU XO): all entries contain "XO", so the variant guard passes.
    The ambiguity is TUBE vs TUBE LIMITED EDITION vs Gift Box Tuba.

  • Group 70 (MOET CHANDON ROSÉ): two rotodinamic entries exist for what appears
    to be the same base wine.  We take the first rotodinamic entry found (shorter
    title = more canonical listing).

Usage
-----
  python scraper/seed_possible_matches.py
  python scraper/seed_possible_matches.py --dry-run
  python scraper/seed_possible_matches.py --verbose
"""

import sys
import json
import logging
import argparse
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.db_utils import get_db, make_group_fingerprint

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

INSPECTION_JSON = (
    Path(__file__).parent.parent / 'claude_prompts' / 'inspection.json'
)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def fetch_matched_product_ids(cursor) -> set[int]:
    """Return every product ID already committed to product_matches."""
    cursor.execute("""
        SELECT ecuga_id, cugaklik_id, promili_id, diskontfumar_id, rotodinamic_id
        FROM product_matches
    """)
    ids: set[int] = set()
    for row in cursor.fetchall():
        for pid in row.values():
            if pid is not None:
                ids.add(pid)
    return ids


def find_product(
    cursor,
    source_name: str,
    original_title: str,
) -> dict | None:
    """Locate a product in the DB by store + title.

    Strategy:
      1. Exact case-insensitive match on the full title  (fast, precise).
      2. ILIKE prefix match on the first 40 characters   (handles minor trailing
         differences — spaces, normalisation artefacts, etc.).

    Returns {'id', 'product_url', 'title', 'volume_ml'} or None.
    """
    # Pass 1: exact (case-insensitive)
    cursor.execute(
        """
        SELECT p.id, p.product_url, p.title, p.volume_ml
        FROM products p
        JOIN sources s ON p.source_id = s.id
        WHERE s.name       = %s
          AND lower(p.title) = lower(%s)
        LIMIT 1
        """,
        [source_name, original_title],
    )
    row = cursor.fetchone()
    if row:
        return dict(row)

    # Pass 2: prefix ILIKE on first 40 chars
    prefix = original_title[:40].strip()
    cursor.execute(
        """
        SELECT p.id, p.product_url, p.title, p.volume_ml
        FROM products p
        JOIN sources s ON p.source_id = s.id
        WHERE s.name   = %s
          AND p.title  ILIKE %s
        ORDER BY length(p.title)   -- prefer shorter (more canonical) title
        LIMIT 1
        """,
        [source_name, f"{prefix}%"],
    )
    row = cursor.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_seed(
    conn,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Seed possible_matches from inspection.json ambiguous groups.

    Returns a stats dict with counts for each outcome.
    """
    stats = {
        'groups_loaded':              0,
        'groups_not_ambiguous':       0,
        'groups_already_matched':     0,
        'groups_products_not_found':  0,
        'groups_already_queued':      0,
        'groups_inserted':            0,
    }

    if not INSPECTION_JSON.exists():
        logging.error(f"inspection.json not found at {INSPECTION_JSON}")
        return stats

    data   = json.loads(INSPECTION_JSON.read_text(encoding='utf-8'))
    groups = data.get('groups', [])
    logging.info(f"Loaded {len(groups)} groups from inspection.json")

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        matched_ids = fetch_matched_product_ids(cur)
        logging.info(
            f"{len(matched_ids):,} product IDs already in product_matches"
        )

        for group in groups:
            stats['groups_loaded'] += 1
            gid  = group['id']
            name = group.get('matched_name', '?')
            cat  = group.get('category', '?')

            if group.get('classification') != 'ambiguous':
                stats['groups_not_ambiguous'] += 1
                continue

            logging.debug(f"Processing group {gid}: {name} [{cat}]")

            # --- Resolve each entry to a DB product ---
            # Deduplicate by source_name: if a store appears twice (e.g. group 70
            # with two rotodinamic entries), keep the first resolved product only
            # (ORDER BY length(title) in find_product already prefers the shorter,
            # more canonical listing).
            resolved_by_source: dict[str, dict] = {}

            for entry in group.get('entries', []):
                source_name    = entry['source']
                original_title = entry['original_title']

                if source_name in resolved_by_source:
                    logging.debug(
                        f"  Group {gid}: second {source_name} entry ignored "
                        f"({original_title[:40]!r}) — first already resolved"
                    )
                    continue

                product = find_product(cur, source_name, original_title)
                if product:
                    resolved_by_source[source_name] = {
                        'source_name': source_name,
                        'id':          product['id'],
                        'product_url': product['product_url'],
                        'title':       product['title'],
                    }
                else:
                    logging.warning(
                        f"  Group {gid}: not found in DB — "
                        f"{source_name!r} / {original_title[:50]!r}"
                    )

            resolved = list(resolved_by_source.values())

            # Need at least 2 different stores resolved
            if len(resolved) < 2:
                logging.warning(
                    f"  Group {gid} ({name}): only {len(resolved)} store(s) "
                    "resolved — skipping"
                )
                stats['groups_products_not_found'] += 1
                continue

            # Skip if any product is already in a confirmed match group
            resolved_ids = {r['id'] for r in resolved}
            if resolved_ids & matched_ids:
                logging.info(
                    f"  Group {gid} ({name}): already in product_matches — skipping"
                )
                stats['groups_already_matched'] += 1
                continue

            fp = make_group_fingerprint(resolved)

            if verbose:
                sources = ', '.join(sorted(r['source_name'] for r in resolved))
                logging.info(
                    f"  Group {gid} [{cat}]  {name}  ({sources})"
                )
                for r in resolved:
                    logging.info(f"    {r['source_name']:<16} {r['title']}")

            if not dry_run:
                id_by_source = {r['source_name']: r['id'] for r in resolved}
                cur.execute(
                    """
                    INSERT INTO possible_matches
                        (ecuga_id, cugaklik_id, promili_id,
                         diskontfumar_id, rotodinamic_id,
                         suggestion_source, group_fingerprint)
                    VALUES (%s, %s, %s, %s, %s, 'seed_inspection', %s)
                    ON CONFLICT (group_fingerprint) DO NOTHING
                    """,
                    [
                        id_by_source.get('ecuga'),
                        id_by_source.get('cugaklik'),
                        id_by_source.get('promili'),
                        id_by_source.get('diskontfumar'),
                        id_by_source.get('rotodinamic'),
                        fp,
                    ],
                )
                if cur.rowcount > 0:
                    logging.info(f"  ✓ Inserted group {gid}: {name}")
                    stats['groups_inserted'] += 1
                else:
                    logging.info(
                        f"  ~ Group {gid}: fingerprint already in possible_matches"
                    )
                    stats['groups_already_queued'] += 1
            else:
                # dry-run: count as if inserted
                logging.info(f"  [dry-run] Would insert group {gid}: {name}")
                stats['groups_inserted'] += 1

    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Seed possible_matches with ambiguous groups from inspection.json '
            '(one-time operation, idempotent).'
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
        help='Print each group and its resolved products as it is processed.',
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
        stats = run_seed(conn, dry_run=args.dry_run, verbose=args.verbose)

    ambiguous = stats['groups_loaded'] - stats['groups_not_ambiguous']

    print(f'\n{"═" * 60}')
    print('SEED SUMMARY')
    print(f'{"═" * 60}')
    if args.dry_run:
        print('  ⚠  DRY RUN — nothing was written to the database')
    print(f'  Groups in inspection.json      : {stats["groups_loaded"]}')
    print(f'  Ambiguous (seed candidates)    : {ambiguous}')
    print(f'  Already in product_matches     : {stats["groups_already_matched"]}')
    print(f'  Products not found in DB       : {stats["groups_products_not_found"]}')
    print(f'  Already in possible_matches    : {stats["groups_already_queued"]}')
    print(f'  Inserted                       : {stats["groups_inserted"]}')
    print(f'{"═" * 60}')


if __name__ == '__main__':
    main()
