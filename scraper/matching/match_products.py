#!/usr/bin/env python3
"""
Match products across stores and populate the product_matches table.

Algorithm
---------
1. Pre-filter by canonical category_id + volume_ml (exact) — big search-space reduction.
2. For every cross-source product pair in each bucket, compute Jaccard token
   similarity on cleaned normalized titles.
3. Build a similarity graph; find connected components via union-find.
4. Each multi-source component = one matched product group → one row in
   product_matches.  At most one product per source per row.

Match key
---------
The normalized_title (produced by import_products.py) is further cleaned:
  - Volume tokens (e.g. "700ml") are stripped  — volume is already used for
    bucketing and is redundant in the name comparison.
  - Category-level words ("whisky", "vodka", …) are removed — redundant inside
    a same-category bucket.
  - Single-character non-digit tokens are removed.

Threshold
---------
Default Jaccard threshold: 0.70.  Empirically safe for Croatian alcohol stores:
  - "ardbeg 10yo"  ↔  "ardbeg 10yo"         → 1.00  ✓ match
  - "jameson"      ↔  "jameson"              → 1.00  ✓ match
  - "macallan 12yo double cask"
    ↔ "macallan 12yo triple cask"            → 0.60  ✗ no match  (correct)
  - "plavac mali"  ↔  "plavac mali reserve"  → 0.67  ✗ no match  (correct)

Usage
-----
  python scraper/match_products.py                     # match all, reset table
  python scraper/match_products.py --dry-run           # compute without writing
  python scraper/match_products.py --category whisky   # one category only
  python scraper/match_products.py --no-reset          # append, skip TRUNCATE
  python scraper/match_products.py --verbose           # print each group
  python scraper/match_products.py --threshold 0.65    # custom threshold
"""

import sys
import re
import logging
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Optional

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database.db_utils import get_db

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD = 0.70

# Words stripped from match keys (category words are noise inside a bucket;
# generic fillers add no discriminating value).
NOISE_WORDS = frozenset({
    # Category / spirit type words
    'whisky', 'whiskey', 'vodka', 'gin', 'rum', 'tequila', 'mezcal',
    'konjak', 'brandy', 'cognac', 'rakija', 'bourbon', 'scotch',
    'liker', 'likeri', 'pivo', 'beer', 'vino', 'wine',
    # Generic filler
    'the', 'i', 'hrvatska', 'original',
    # Age suffix — "yo" is never discriminating on its own; the year number
    # already in the key carries all the information ("12yo" → "12yo" token,
    # but "12 yo" as two tokens → "12" stays, "yo" removed).
    'yo',
    # Croatian packaging/gift words — appear in some store titles but don't
    # distinguish the product itself (e.g. "GLENFIDDICH 12YO KUTIJA" is the
    # same product as "GLENFIDDICH 12YO"; kutija = box).
    'kutija', 'tuba', 'kartonska', 'poklon', 'pjenušac',
    # Croatian beer-style descriptors — style of an already-named product
    # (e.g. "Medvedgrad Dva Klasa pšenično" = wheat; "Crna Kraljica tamno" = dark).
    'tamno', 'pšenično',
    # RTD cocktail type words — diskontfumar prefixes A.Le Coq products with
    # "ALCOHOLIC COCTAIL"; other stores omit these words.
    'alcoholic', 'coctail', 'cocktail', 'koktel',
    # Product type descriptor appended by rotodinamic for pear brandy products.
    'viljamovka',
    # Croatian preposition used in diskontfumar internal annotations "(bez pn)".
    # normalize_title removes the parens but leaves "bez pn" as tokens.
    'bez',
    # Packaging/presentation descriptors — same liquid, different box.
    # "GLENFIDDICH 12YO CARTON BOX" = "GLENFIDDICH 12YO"; carton/naked/box/bottle
    # are meaningless for matching purposes.
    'carton', 'box', 'naked', 'bottle',
})

# Words that unambiguously distinguish product variants.
# If one product's match key contains one of these and the other's does NOT,
# they are different products regardless of Jaccard score.
# Example: "Moet Imperial" vs "Moet Rose Imperial" → different products.
# Example: "Gordon's Gin" vs "Gordon's Pink Gin" → different products.
STRONG_VARIANT_WORDS = frozenset({'rose', 'rosé', 'ice', 'pink', 'noir', 'vs', 'vsop', 'xo'})

# Source names in insertion order (must match product_matches columns)
SOURCES = ['ecuga', 'cugaklik', 'promili', 'diskontfumar', 'rotodinamic']

# Pre-compiled pattern for stripping volume tokens (e.g. "700ml", "1000ml")
_VOL_RE = re.compile(r'\b\d+ml\b')


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def make_match_key(normalized_title: str) -> list[str]:
    """
    Produce a list of meaningful tokens for Jaccard comparison.

    Removes:
      - Volume tokens already standardised to Nml form by normalize_title
      - Category / noise words
      - Single-character non-digit tokens

    The result is order-independent (comparison uses sets), so token list order
    doesn't matter — but we keep it as a list for display convenience.
    """
    text = _VOL_RE.sub('', normalized_title or '')
    tokens = text.split()
    # Normalize fused age tokens produced by normalize_title's age regex:
    # "ABERLOUR 12YO" → normalize_title → "aberlour 12yo" → token "12yo"
    # NOISE_WORDS strips standalone "yo" but not the fused "12yo" token.
    # Converting "12yo" → "12" ensures it matches "12" from stores that write
    # "12 YO" (where "yo" was already a separate token and gets stripped).
    tokens = [re.sub(r'^(\d+)yo$', r'\1', t) for t in tokens]
    return [
        t for t in tokens
        if t not in NOISE_WORDS and (len(t) > 1 or t.isdigit())
    ]


def jaccard(a: list[str], b: list[str]) -> float:
    """Jaccard similarity coefficient on token sets."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _trigrams(text: str, n: int = 3) -> set[str]:
    """Character n-grams from a joined match-key string."""
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def trigram_jaccard(a: list[str], b: list[str]) -> float:
    """Jaccard similarity on character trigrams of the joined match keys.

    Acts as a secondary signal: catches cases where word tokens differ due to
    minor typos (e.g. 'Resposado' vs 'Reposado') or concatenation artefacts
    that survive normalisation.
    """
    g1 = _trigrams(' '.join(a))
    g2 = _trigrams(' '.join(b))
    if not g1 and not g2:
        return 1.0
    if not g1 or not g2:
        return 0.0
    return len(g1 & g2) / len(g1 | g2)


def is_match(key1: list[str], key2: list[str], threshold: float) -> bool:
    """
    Two products are a match if:
      1. Neither product has a strong variant word (rose, ice, pink…) that the
         other lacks — those words unambiguously signal different products.
      2. Jaccard token similarity >= threshold  OR
         character trigram Jaccard >= threshold.

    Using OR of two independent signals means we catch:
      - Standard name matches (Jaccard)
      - Minor typos or concatenation artefacts that only trigram handles

    The variant check prevents indirect bridges like:
      "Moet Imperial"  →  connects to both  →  "Moet Rose Imperial"
                                            →  "Moet Ice Imperial"
    which would incorrectly merge Rose and Ice into one group.

    Trigram exception — numeric tokens (age expressions, edition numbers):
    Character trigrams almost always bridge different two-digit numbers because
    they share the leading "1" (e.g. "12" and "18" share trigram " 1").  If both
    keys have pure-digit tokens AND those sets differ, trigram is disabled and
    only Jaccard decides.  This prevents "Chivas 12" ↔ "Chivas 18" false matches
    while still allowing typo-catching for non-numeric differences (e.g.
    "Resposado" ↔ "Reposado") and the "18y" ↔ "18" diskontfumar quirk (where
    "18y" is not a pure-digit token, so only one side has digits).
    """
    s1, s2 = set(key1), set(key2)
    if (s1 & STRONG_VARIANT_WORDS) != (s2 & STRONG_VARIANT_WORDS):
        return False

    j = jaccard(key1, key2)
    if j >= threshold:
        return True

    # Check whether trigram is safe to use: disable it when both sides carry
    # different pure-digit tokens (age/edition numbers).
    digits1 = {t for t in s1 if t.isdigit()}
    digits2 = {t for t in s2 if t.isdigit()}
    if digits1 and digits2 and digits1 != digits2:
        return False  # different numeric tokens — Jaccard already decided above

    return trigram_jaccard(key1, key2) >= threshold


# ---------------------------------------------------------------------------
# Union-Find (connected components)
# ---------------------------------------------------------------------------

class UnionFind:
    def __init__(self, nodes):
        self.parent = {n: n for n in nodes}
        self.rank   = {n: 0 for n in nodes}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path compression
            x = self.parent[x]
        return x

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def get_components(self) -> dict:
        """Return {root_id: [member_ids, …]}."""
        groups: dict = defaultdict(list)
        for node in self.parent:
            groups[self.find(node)].append(node)
        return dict(groups)


# ---------------------------------------------------------------------------
# Core matching logic
# ---------------------------------------------------------------------------

def match_group(
    products: list[dict],
    threshold: float,
) -> list[list[dict]]:
    """
    Given all products in one (category, volume) bucket, find match clusters.

    Each cluster is a list of product dicts representing the same product across
    different stores (at most one product per source per cluster).

    Returns only multi-source clusters (single-store entries are unmatched).
    """
    if len(products) < 2:
        return []

    # Compute and cache match keys
    for p in products:
        p['_key'] = make_match_key(p['normalized_title'] or '')

    ids = [p['id'] for p in products]
    by_id = {p['id']: p for p in products}

    uf = UnionFind(ids)

    # Compare every cross-source pair — O(n²) but buckets are small
    for i in range(len(products)):
        for j in range(i + 1, len(products)):
            p1, p2 = products[i], products[j]
            if p1['source_name'] == p2['source_name']:
                continue  # Never match products from the same store
            if is_match(p1['_key'], p2['_key'], threshold):
                uf.union(p1['id'], p2['id'])

    clusters: list[list[dict]] = []

    for member_ids in uf.get_components().values():
        if len(member_ids) < 2:
            continue

        members = [by_id[pid] for pid in member_ids]

        # Ensure at most one product per source.
        # When a source has multiple candidates in one component (can happen via
        # indirect chains), keep the one with the highest average Jaccard to all
        # other-source products in the component.
        by_source: dict[str, list[dict]] = defaultdict(list)
        for p in members:
            by_source[p['source_name']].append(p)

        resolved: list[dict] = []
        for src, candidates in by_source.items():
            if len(candidates) == 1:
                resolved.append(candidates[0])
            else:
                others = [p for p in members if p['source_name'] != src]
                best = max(
                    candidates,
                    key=lambda c: (
                        sum(jaccard(c['_key'], o['_key']) for o in others)
                        / max(len(others), 1)
                    ),
                )
                resolved.append(best)

        if len({p['source_name'] for p in resolved}) >= 2:
            clusters.append(resolved)

    return clusters


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def fetch_products(cursor, category_id: Optional[int] = None) -> list[dict]:
    """Fetch all available products with source and category info."""
    query = """
        SELECT
            p.id,
            p.source_id,
            s.name        AS source_name,
            p.category_id,
            c.slug        AS category_slug,
            p.normalized_title,
            p.volume_ml,
            p.title
        FROM products p
        JOIN sources    s ON p.source_id    = s.id
        JOIN categories c ON p.category_id  = c.id
        WHERE p.is_available   = true
          AND p.category_id IS NOT NULL
    """
    params: list = []
    if category_id is not None:
        query += " AND p.category_id = %s"
        params.append(category_id)
    query += " ORDER BY p.category_id, p.volume_ml NULLS LAST, p.source_id"
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def insert_match_row(cursor, cluster: list[dict]) -> bool:
    """Insert one algorithm-generated matched group into product_matches.

    Returns True if a row was inserted, False if skipped due to a conflict
    with an existing human-confirmed row (unique index per source column).
    """
    id_by_source = {p['source_name']: p['id'] for p in cluster}
    cursor.execute(
        """
        INSERT INTO product_matches
            (ecuga_id, cugaklik_id, promili_id, diskontfumar_id, rotodinamic_id,
             match_source)
        VALUES (%s, %s, %s, %s, %s, 'algorithm')
        ON CONFLICT DO NOTHING
        """,
        [id_by_source.get(src) for src in SOURCES],
    )
    return cursor.rowcount == 1


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_matching(
    conn,
    category_slug: Optional[str] = None,
    reset: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """
    Full matching pipeline.

    Returns a stats dict:
      categories, volume_groups, clusters_found, rows_inserted
    """
    stats = {
        'categories': 0,
        'volume_groups': 0,
        'clusters_found': 0,
        'rows_inserted': 0,
    }

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Resolve category slug → id (if requested)
        category_id: Optional[int] = None
        if category_slug:
            cur.execute(
                "SELECT id FROM categories WHERE slug = %s", (category_slug,)
            )
            row = cur.fetchone()
            if not row:
                logging.error(f"Unknown category slug: '{category_slug}'")
                return stats
            category_id = row['id']

        # Optionally clear algorithm-generated rows.
        # We DELETE only rows with match_source = 'algorithm' so that
        # human-confirmed rows (match_source = 'human_confirmed') survive
        # every re-scrape cycle without needing to be re-applied manually.
        if reset and not dry_run:
            cur.execute(
                "DELETE FROM product_matches WHERE match_source = 'algorithm'"
            )
            logging.info("Cleared algorithm-generated rows from product_matches.")

        # Load products
        products = fetch_products(cur, category_id)
        logging.info(f"Loaded {len(products):,} available products from DB.")

        # Group: category_id → volume_ml → [products]
        grouped: dict[int, dict] = defaultdict(lambda: defaultdict(list))
        for p in products:
            grouped[p['category_id']][p['volume_ml']].append(p)

        # --- Process each (category, volume) bucket ---
        for cat_id in sorted(grouped):
            vol_map = grouped[cat_id]
            cat_slug = next(
                p['category_slug'] for p in products if p['category_id'] == cat_id
            )
            stats['categories'] += 1

            # RC1 fix: products with volume_ml=None never appeared in any
            # explicit-volume bucket, so they were never compared against
            # volumed products.  Augment each non-NULL bucket with the
            # NULL-volume products from the same category.  The NULL bucket
            # itself is still processed alone for NULL-NULL pairs.
            null_products = vol_map.get(None, [])

            cat_clusters_raw: list[list[dict]] = []

            for vol_ml in sorted(vol_map, key=lambda v: (v is None, v or 0)):
                stats['volume_groups'] += 1

                if vol_ml is None:
                    # NULL bucket: compare NULL-volume products among themselves.
                    # Cross-volume comparisons happen inside each non-NULL bucket.
                    bucket = vol_map[vol_ml]
                else:
                    # Augment with NULL-volume products so they get compared
                    # against every explicit volume in this category.
                    bucket = vol_map[vol_ml] + null_products

                # Need at least 2 different sources in the bucket to attempt matching
                sources_in_bucket = {p['source_name'] for p in bucket}
                if len(sources_in_bucket) < 2:
                    continue

                cat_clusters_raw.extend(match_group(bucket, threshold))

            # Deduplicate clusters: a NULL-volume product appears in every
            # augmented non-NULL bucket, so the same pair can surface in
            # multiple buckets.  Keep the most-source cluster when there is
            # product-ID overlap; discard the smaller one.
            cat_clusters_raw.sort(
                key=lambda c: len({p['source_name'] for p in c}), reverse=True
            )
            seen_ids: set[int] = set()
            cat_clusters: list[list[dict]] = []
            for cluster in cat_clusters_raw:
                ids = {p['id'] for p in cluster}
                if ids & seen_ids:
                    continue  # overlaps a richer cluster already kept
                seen_ids |= ids
                cat_clusters.append(cluster)

            stats['clusters_found'] += len(cat_clusters)

            for cluster in cat_clusters:
                sources_in_cluster = sorted(p['source_name'] for p in cluster)

                if verbose:
                    # Print one line per match group: pick shortest title as label
                    label = min(cluster, key=lambda p: len(p['title']))['title']
                    vols = sorted(
                        {p['volume_ml'] for p in cluster if p['volume_ml'] is not None}
                    )
                    vol_label = (
                        f"{vols[0]}ml" if len(vols) == 1
                        else ('mixed-vol' if vols else 'no-vol')
                    )
                    logging.info(
                        f"  [{cat_slug} | {vol_label}]  "
                        f"{label[:55]!r}  "
                        f"({', '.join(sources_in_cluster)})"
                    )
                    for p in sorted(cluster, key=lambda x: x['source_name']):
                        logging.debug(
                            f"      {p['source_name']:<15} {p['title']}"
                        )

                if not dry_run:
                    if insert_match_row(cur, cluster):
                        stats['rows_inserted'] += 1
                    else:
                        stats['rows_skipped_conflict'] = stats.get('rows_skipped_conflict', 0) + 1

            logging.info(
                f"  {cat_slug:<12} {len(cat_clusters):>5} match groups  "
                f"({len(vol_map)} volume buckets)"
            )

    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Match products across stores → populate product_matches.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--category',
        metavar='SLUG',
        help='Only match this category (e.g. whisky, vodka, gin). Default: all.',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Compute matches and print stats without writing to the database.',
    )
    parser.add_argument(
        '--no-reset',
        action='store_true',
        help='Skip TRUNCATE; append new matches to the existing table.',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print each matched group (one line per group).',
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f'Jaccard similarity threshold 0–1 (default: {DEFAULT_THRESHOLD}).',
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s  %(levelname)-7s %(message)s',
        datefmt='%H:%M:%S',
    )

    if args.dry_run:
        logging.info('DRY RUN — no changes will be written to the database.')

    db = get_db()
    db.initialize_pool()

    with db.get_connection() as conn:
        stats = run_matching(
            conn,
            category_slug=args.category,
            reset=not args.no_reset,
            dry_run=args.dry_run,
            verbose=args.verbose,
            threshold=args.threshold,
        )

    print(f'\n{"═" * 60}')
    print('MATCHING SUMMARY')
    print(f'{"═" * 60}')
    if args.dry_run:
        print('  ⚠  DRY RUN — nothing was written to the database')
    print(f'  Categories processed : {stats["categories"]}')
    print(f'  Volume buckets       : {stats["volume_groups"]}')
    print(f'  Match clusters found : {stats["clusters_found"]}')
    print(f'  Rows inserted        : {stats["rows_inserted"]}')
    print(f'{"═" * 60}')


if __name__ == '__main__':
    main()
