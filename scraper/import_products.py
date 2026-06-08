#!/usr/bin/env python3
"""
Import scraped JSON files into the PostgreSQL database.

Pipeline: scraper/data/{source}/*.json → products table

For each JSON file:
  1. Extracts file_slug from filename  (e.g. 'whisky-1' from 'whisky-1_promili.json')
  2. Resolves canonical category via source_category_mappings table
  3. Parses price, extracts volume_ml, normalizes title
  4. Upserts into products (keyed on source_id + product_url)

Unmapped files are skipped with a warning (e.g. absinth).

Usage:
  python scraper/import_products.py                     # all sources
  python scraper/import_products.py --source ecuga      # one source only
  python scraper/import_products.py --dry-run           # preview, no DB writes
  python scraper/import_products.py --verbose           # per-product logging
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from decimal import Decimal

import psycopg2.extras

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_utils import get_db, extract_volume_ml, normalize_title, parse_price

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / 'data'

# Base URLs for resolving relative links (used as fallback)
BASE_URLS = {
    'ecuga':        'https://ecuga.com',
    'cugaklik':     'https://www.cugaklik.hr',
    'promili':      'https://promili.hr',
    'diskontfumar': 'https://diskontfumar.hr',
    'rotodinamic':  'https://rotodinamic.hr',
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_file_slug(filename: str, source_name: str) -> str:
    """
    Extract the file slug from a JSON filename.

    Examples:
        'whisky-1_promili.json',      'promili'      → 'whisky-1'
        'gin_ecuga.json',             'ecuga'        → 'gin'
        'jaka-...,Whisky_rotodinamic.json', 'rotodinamic' → 'jaka-...,Whisky'
    """
    suffix = f'_{source_name}.json'
    if filename.endswith(suffix):
        return filename[: -len(suffix)]
    # Fallback: strip .json and last _source segment
    return filename.removesuffix('.json')


def resolve_url(url: str, source_name: str) -> str:
    """
    Ensure URL is absolute. Full URLs pass through unchanged.
    Relative URLs (starting with /) are prefixed with the source base URL.
    """
    if not url:
        return ''
    if url.startswith('http'):
        return url
    base = BASE_URLS.get(source_name, '')
    if base and url.startswith('/'):
        return base + url
    return url


def get_volume_ml(product: dict) -> int | None:
    """
    Extract volume in millilitres.

    Prefers the dedicated 'size' field (present on rotodinamic, ecuga, promili).
    Falls back to extracting from the title (cugaklik, diskontfumar).

    Returns integer ml or None if volume cannot be determined.
    """
    size = product.get('size', '').strip()
    if size:
        vol = extract_volume_ml(size)
        if vol:
            return vol
    return extract_volume_ml(product.get('title', ''))


def lookup_category(cursor, source_id: int, file_slug: str) -> int | None:
    """
    Return the canonical_category_id for a (source, file_slug) pair.
    Returns None if no mapping exists (file should be skipped).
    """
    cursor.execute(
        """
        SELECT canonical_category_id
        FROM source_category_mappings
        WHERE source_id = %s AND file_slug = %s
        """,
        (source_id, file_slug),
    )
    row = cursor.fetchone()
    return row['canonical_category_id'] if row else None


def get_source_id(cursor, source_name: str) -> int | None:
    """Return the source ID for a given source name."""
    cursor.execute('SELECT id FROM sources WHERE name = %s', (source_name,))
    row = cursor.fetchone()
    return row['id'] if row else None


# ---------------------------------------------------------------------------
# Core import logic
# ---------------------------------------------------------------------------

def import_file(
    cursor,
    json_path: Path,
    source_name: str,
    source_id: int,
    dry_run: bool,
    verbose: bool,
) -> dict:
    """
    Import all products from a single JSON file.

    Returns a stats dict: {file, category_id, inserted, updated, skipped, errors, seen_urls}
    """
    stats = {
        'file': json_path.name,
        'category_id': None,
        'inserted': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'seen_urls': [],
    }

    file_slug = get_file_slug(json_path.name, source_name)
    category_id = lookup_category(cursor, source_id, file_slug)

    if category_id is None:
        logging.warning(f'    SKIP {json_path.name} — no mapping for slug "{file_slug}"')
        return stats

    stats['category_id'] = category_id

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            products = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.error(f'    ERROR reading {json_path.name}: {e}')
        stats['errors'] += 1
        return stats

    if not isinstance(products, list):
        logging.warning(f'    {json_path.name}: expected a JSON list, got {type(products).__name__}')
        return stats

    for product in products:
        try:
            title = product.get('title', '').strip()
            if not title:
                stats['skipped'] += 1
                continue

            url = resolve_url(product.get('link', ''), source_name)
            if not url:
                logging.debug(f'    Skipping product with no URL: {title[:50]}')
                stats['skipped'] += 1
                continue

            stats['seen_urls'].append(url)

            price_str = product.get('price', '').strip()
            price = parse_price(price_str)
            if price is None:
                # Non-numeric price (e.g. "Ponuda na upit") — import with price=0
                price = Decimal('0')

            volume_ml = get_volume_ml(product)
            normalized = normalize_title(title)

            if verbose:
                logging.debug(
                    f'    {title[:50]!r:<55} | {price_str!r:<12} | {volume_ml or "?":>6} ml'
                )

            if not dry_run:
                image_url = product.get('image') or None
                cursor.execute(
                    """
                    INSERT INTO products (
                        source_id, category_id,
                        title, normalized_title, volume_ml,
                        price, price_original,
                        product_url, image_url,
                        is_available, last_seen_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true, CURRENT_TIMESTAMP)
                    ON CONFLICT (source_id, product_url) DO UPDATE SET
                        category_id      = EXCLUDED.category_id,
                        title            = EXCLUDED.title,
                        normalized_title = EXCLUDED.normalized_title,
                        volume_ml        = EXCLUDED.volume_ml,
                        price            = EXCLUDED.price,
                        price_original   = EXCLUDED.price_original,
                        image_url        = EXCLUDED.image_url,
                        is_available     = true,
                        last_seen_at     = CURRENT_TIMESTAMP,
                        updated_at       = CURRENT_TIMESTAMP
                    RETURNING (xmax = 0) AS was_inserted
                    """,
                    (
                        source_id, category_id,
                        title, normalized, volume_ml,
                        price, price_str,
                        url, image_url,
                    ),
                )
                row = cursor.fetchone()
                if row and row['was_inserted']:
                    stats['inserted'] += 1
                else:
                    stats['updated'] += 1
            else:
                # Dry run: count everything as "would insert"
                stats['inserted'] += 1

        except Exception as e:
            logging.error(f'    Product error ({product.get("title", "?")[:40]}): {e}')
            stats['errors'] += 1

    return stats


def import_source(
    cursor,
    source_dir: Path,
    source_name: str,
    dry_run: bool,
    verbose: bool,
) -> dict:
    """
    Import all JSON files for a single source.

    Returns aggregated stats for this source.
    """
    source_id = get_source_id(cursor, source_name)
    if source_id is None:
        logging.error(f'  Source "{source_name}" not found in database — skipping.')
        return {}

    json_files = sorted(source_dir.glob('*.json'))
    if not json_files:
        logging.warning(f'  No JSON files found in {source_dir}')
        return {}

    totals = {'files': 0, 'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0, 'deactivated': 0}

    # Track which URLs and categories were seen in this run so we can
    # mark products no longer present in the scrape as unavailable.
    all_seen_urls: list[str] = []
    scraped_category_ids: set[int] = set()

    for json_path in json_files:
        logging.info(f'  → {json_path.name}')
        file_stats = import_file(cursor, json_path, source_name, source_id, dry_run, verbose)

        totals['files'] += 1
        totals['inserted'] += file_stats['inserted']
        totals['updated']  += file_stats['updated']
        totals['skipped']  += file_stats['skipped']
        totals['errors']   += file_stats['errors']

        if file_stats['category_id'] is not None:
            scraped_category_ids.add(file_stats['category_id'])
            all_seen_urls.extend(file_stats['seen_urls'])
            logging.info(
                f'     {file_stats["inserted"]} inserted, '
                f'{file_stats["updated"]} updated, '
                f'{file_stats["skipped"]} skipped, '
                f'{file_stats["errors"]} errors'
            )

    # Mark products that were not seen in this scrape as unavailable.
    # Only affects categories we actually scraped — unmapped categories are left alone.
    if not dry_run and scraped_category_ids:
        cursor.execute(
            """
            UPDATE products
               SET is_available = false,
                   updated_at   = CURRENT_TIMESTAMP
             WHERE source_id    = %s
               AND category_id  = ANY(%s)
               AND is_available = true
               AND product_url  != ALL(%s)
            """,
            (source_id, list(scraped_category_ids), all_seen_urls or ['']),
        )
        deactivated = cursor.rowcount
        totals['deactivated'] = deactivated
        if deactivated:
            logging.info(f'  ⚠  {deactivated} products marked unavailable (no longer in scrape)')

    return totals


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Import scraped JSON files into the PostgreSQL products table.'
    )
    parser.add_argument(
        '--source',
        help='Import only this source (e.g. ecuga, cugaklik). Default: all sources.',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Parse and validate data without writing to the database.',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Log each product as it is processed.',
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s  %(levelname)-7s %(message)s',
        datefmt='%H:%M:%S',
    )

    if args.dry_run:
        logging.info('DRY RUN — no changes will be written to the database.')

    if not DATA_DIR.exists():
        logging.error(f'Data directory not found: {DATA_DIR}')
        sys.exit(1)

    # Determine which source directories to process
    if args.source:
        source_dirs = [DATA_DIR / args.source]
        if not source_dirs[0].exists():
            logging.error(f'Source directory not found: {source_dirs[0]}')
            sys.exit(1)
    else:
        source_dirs = sorted(d for d in DATA_DIR.iterdir() if d.is_dir())

    db = get_db()
    db.initialize_pool()

    grand_totals = {'sources': 0, 'files': 0, 'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0, 'deactivated': 0}

    with db.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            for source_dir in source_dirs:
                source_name = source_dir.name
                logging.info(f'\n{"─" * 60}')
                logging.info(f'Source: {source_name}')
                logging.info(f'{"─" * 60}')

                source_totals = import_source(cursor, source_dir, source_name, args.dry_run, args.verbose)

                if source_totals:
                    grand_totals['sources'] += 1
                    for key in ('files', 'inserted', 'updated', 'skipped', 'errors', 'deactivated'):
                        grand_totals[key] += source_totals.get(key, 0)

                    logging.info(
                        f'  Source total: {source_totals["files"]} files, '
                        f'{source_totals["inserted"]} inserted, '
                        f'{source_totals["updated"]} updated, '
                        f'{source_totals["skipped"]} skipped, '
                        f'{source_totals["errors"]} errors, '
                        f'{source_totals.get("deactivated", 0)} deactivated'
                    )

    # Final summary
    print(f'\n{"═" * 60}')
    print('IMPORT SUMMARY')
    print(f'{"═" * 60}')
    if args.dry_run:
        print('  ⚠  DRY RUN — nothing was written to the database')
    print(f'  Sources processed : {grand_totals["sources"]}')
    print(f'  Files processed   : {grand_totals["files"]}')
    print(f'  Products inserted : {grand_totals["inserted"]}')
    print(f'  Products updated  : {grand_totals["updated"]}')
    print(f'  Deactivated       : {grand_totals["deactivated"]}')
    print(f'  Skipped           : {grand_totals["skipped"]}')
    print(f'  Errors            : {grand_totals["errors"]}')
    print(f'{"═" * 60}')

    if grand_totals['errors'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
