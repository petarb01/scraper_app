#!/usr/bin/env python3
"""
Populate possible_matches with candidates for human review.

Two candidate types are detected and written to possible_matches:

  near_miss        — cross-source pairs whose best similarity score
                     (max of Jaccard and trigram) falls in the window
                     [NEAR_MISS_LOW, MAIN_THRESHOLD).  Default: [0.55, 0.70).

  compare_matchers — cross-source pairs where the overlap coefficient
                     (|A∩B| / min(|A|, |B|)) reaches OVERLAP_THRESHOLD (0.70)
                     but neither Jaccard nor trigram does, and the best of the
                     two word/character scores is still ≥ 0.50 to filter noise.
                     These capture the "producer name prepended" and "short brand
                     + one extra descriptor" patterns (RC5 / RC8 from inspection.md).

Both candidate types:
  • Apply the same STRONG_VARIANT_WORDS guard as match_products.py — pairs
    that differ on rose/rosé/ice/pink/noir/vs/vsop/xo are never suggested.
  • Use the same NULL-volume bucket augmentation as match_products.py so that
    products without a volume token are compared against every explicit-volume
    bucket in their category.
  • Skip products already in product_matches (already handled by the algorithm).
  • Are deduplicated by group_fingerprint, so re-running this script is safe
    and idempotent at any time.

Usage
-----
  python scraper/suggest_matches.py                    # all categories
  python scraper/suggest_matches.py --category whisky
  python scraper/suggest_matches.py --dry-run
  python scraper/suggest_matches.py --near-miss-min 0.50
  python scraper/suggest_matches.py --verbose
"""

import sys
import logging
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Optional

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # project root → database.*
sys.path.insert(0, str(Path(__file__).parent))               # matching/    → match_products

from database.db_utils import get_db, make_group_fingerprint

# Import shared matching logic from match_products to stay in sync with
# any future changes to NOISE_WORDS, STRONG_VARIANT_WORDS, etc.
from match_products import (
    NOISE_WORDS, STRONG_VARIANT_WORDS,   # noqa: F401 (used indirectly via make_match_key)
    make_match_key, jaccard, trigram_jaccard, UnionFind,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAIN_THRESHOLD    = 0.70   # Pairs at or above this are handled by match_products.py
NEAR_MISS_DEFAULT = 0.37   # Default lower bound of the near-miss window
OVERLAP_THRESHOLD = 0.70   # Overlap coefficient must reach this to trigger source B
OVERLAP_MIN_SCORE = 0.50   # Pairs below this (Jaccard AND trigram) are too noisy

# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------


def overlap_sim(key1: list[str], key2: list[str]) -> float:
    """Overlap coefficient = |A∩B| / min(|A|, |B|).

    Asymmetric: the shorter key only needs to be fully covered by the longer.
    Handles the common pattern where one store prepends a producer name:
        rotodinamic: ["medvedgrad", "crna", "kraljica"]   |key|=3
        cugaklik:    ["crna", "kraljica"]                  |key|=2
        overlap = 2/2 = 1.0,  Jaccard = 2/3 = 0.67  → near-miss for Jaccard,
        clear match for overlap.
    """
    s1, s2 = set(key1), set(key2)
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / min(len(s1), len(s2))


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def fetch_products(cursor, category_id: Optional[int] = None) -> list[dict]:
    """Like match_products.fetch_products but also retrieves product_url.

    product_url is needed for make_group_fingerprint — fingerprints are
    URL-based so they remain stable across full DB re-imports.
    """
    query = """
        SELECT
            p.id,
            p.source_id,
            s.name        AS source_name,
            p.category_id,
            c.slug        AS category_slug,
            p.normalized_title,
            p.volume_ml,
            p.title,
            p.product_url
        FROM products p
        JOIN sources    s ON p.source_id   = s.id
        JOIN categories c ON p.category_id = c.id
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


def fetch_queued_fingerprints(cursor) -> set[str]:
    """Return all group_fingerprints already in possible_matches (any status)."""
    cursor.execute("SELECT group_fingerprint FROM possible_matches")
    return {row['group_fingerprint'] for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Core pair-scoring
# ---------------------------------------------------------------------------


def score_pairs(bucket: list[dict]) -> dict[frozenset, dict[str, float]]:
    """Compute Jaccard, trigram, and overlap scores for every valid cross-source pair.

    Pairs blocked by the STRONG_VARIANT_WORDS guard are omitted entirely —
    they should never appear in the review queue.

    Returns {frozenset({id_a, id_b}): {'j': float, 't': float, 'o': float}}.
    """
    scores: dict[frozenset, dict[str, float]] = {}
    for i in range(len(bucket)):
        for k in range(i + 1, len(bucket)):
            p1, p2 = bucket[i], bucket[k]
            if p1['source_name'] == p2['source_name']:
                continue

            s1, s2 = set(p1['_key']), set(p2['_key'])
            if (s1 & STRONG_VARIANT_WORDS) != (s2 & STRONG_VARIANT_WORDS):
                continue  # variant guard — these are different products by definition

            digits1 = {t for t in p1['_key'] if t.isdigit()}
            digits2 = {t for t in p2['_key'] if t.isdigit()}
            digit_blocked = bool(digits1 and digits2 and digits1 != digits2)
            pk = frozenset({p1['id'], p2['id']})
            scores[pk] = {
                'j': jaccard(p1['_key'], p2['_key']),
                't': trigram_jaccard(p1['_key'], p2['_key']),
                'o': overlap_sim(p1['_key'], p2['_key']),
                'digit_blocked': digit_blocked,
            }
    return scores


# ---------------------------------------------------------------------------
# Cluster resolution
# ---------------------------------------------------------------------------


def pairs_to_clusters(
    pairs: set[frozenset],
    by_id: dict[int, dict],
) -> list[list[dict]]:
    """Union-Find over matched pairs → resolved clusters.

    Mirrors match_products.match_group's conflict-resolution logic:
    at most one product per source per cluster.  If a source has multiple
    candidates in one component (indirect chain), keep the one with the
    highest average Jaccard to all other-source members.
    """
    if not pairs:
        return []

    all_ids: set[int] = set()
    for p in pairs:
        all_ids.update(p)

    uf = UnionFind(list(all_ids))
    for pair in pairs:
        a, b = tuple(pair)
        uf.union(a, b)

    clusters: list[list[dict]] = []
    for member_ids in uf.get_components().values():
        if len(member_ids) < 2:
            continue

        members = [by_id[pid] for pid in member_ids if pid in by_id]
        if len({p['source_name'] for p in members}) < 2:
            continue

        by_source: dict[str, list] = defaultdict(list)
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


def best_cluster_scores(
    cluster: list[dict],
    pair_scores: dict[frozenset, dict[str, float]],
) -> tuple[float, float]:
    """Return (max_jaccard, max_trigram) across all pairs in the cluster."""
    best_j, best_t = 0.0, 0.0
    ids = [p['id'] for p in cluster]
    for i, id1 in enumerate(ids):
        for id2 in ids[i + 1:]:
            sc = pair_scores.get(frozenset({id1, id2}))
            if sc:
                best_j = max(best_j, sc['j'])
                best_t = max(best_t, sc['t'])
    return best_j, best_t


# ---------------------------------------------------------------------------
# DB insertion
# ---------------------------------------------------------------------------


def insert_candidate(
    cursor,
    cluster: list[dict],
    jaccard_score: float,
    trigram_score: float,
    suggestion_source: str,
    fingerprint: str,
) -> bool:
    """Insert one candidate cluster into possible_matches.

    Uses ON CONFLICT DO NOTHING so re-runs are safe.
    Returns True if a row was actually inserted, False if skipped.
    """
    id_by_source = {p['source_name']: p['id'] for p in cluster}
    cursor.execute(
        """
        INSERT INTO possible_matches
            (ecuga_id, cugaklik_id, promili_id, diskontfumar_id, rotodinamic_id,
             jaccard_score, trigram_score, suggestion_source, group_fingerprint)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (group_fingerprint) DO NOTHING
        """,
        [
            id_by_source.get('ecuga'),
            id_by_source.get('cugaklik'),
            id_by_source.get('promili'),
            id_by_source.get('diskontfumar'),
            id_by_source.get('rotodinamic'),
            round(jaccard_score, 3),
            round(trigram_score, 3),
            suggestion_source,
            fingerprint,
        ],
    )
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Per-category candidate processing
# ---------------------------------------------------------------------------


def process_candidate_clusters(
    clusters: list[list[dict]],
    suggestion_source: str,
    pair_scores: dict[frozenset, dict[str, float]],
    matched_ids: set[int],
    seen_fps: set[str],
    cursor,
    dry_run: bool,
    verbose: bool,
    cat_slug: str,
) -> tuple[int, int, int]:
    """Validate, fingerprint, and insert a list of candidate clusters.

    Returns (inserted, skipped_matched, skipped_queued).
    """
    inserted = skipped_matched = skipped_queued = 0

    for cluster in clusters:
        cluster_ids = {p['id'] for p in cluster}

        # Skip if any product is already committed to a match group
        if cluster_ids & matched_ids:
            skipped_matched += 1
            continue

        fp = make_group_fingerprint(cluster)
        if fp in seen_fps:
            skipped_queued += 1
            continue

        best_j, best_t = best_cluster_scores(cluster, pair_scores)
        sources = sorted(p['source_name'] for p in cluster)
        vols = sorted(
            {p['volume_ml'] for p in cluster if p['volume_ml'] is not None}
        )
        vol_label = (
            f"{vols[0]}ml" if len(vols) == 1
            else ('mixed-vol' if vols else 'no-vol')
        )

        if verbose:
            label = min(cluster, key=lambda p: len(p['title']))['title']
            logging.info(
                f"  [{cat_slug} | {vol_label}]  {suggestion_source:<18}  "
                f"J={best_j:.2f} T={best_t:.2f}  "
                f"{label[:40]!r}  ({', '.join(sources)})"
            )

        if not dry_run:
            if insert_candidate(cursor, cluster, best_j, best_t, suggestion_source, fp):
                seen_fps.add(fp)
                inserted += 1
            else:
                skipped_queued += 1
        else:
            seen_fps.add(fp)   # prevent double-counting within the dry-run
            inserted += 1

    return inserted, skipped_matched, skipped_queued


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_suggestions(
    conn,
    category_slug: Optional[str] = None,
    near_miss_low: float = NEAR_MISS_DEFAULT,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Full suggestion pipeline.

    Returns a stats dict:
        buckets_scanned, near_miss_inserted, overlap_inserted,
        skipped_already_matched, skipped_already_queued
    """
    stats = {
        'buckets_scanned':        0,
        'near_miss_inserted':     0,
        'overlap_inserted':       0,
        'skipped_already_matched': 0,
        'skipped_already_queued':  0,
    }

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Resolve category slug
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

        products = fetch_products(cur, category_id)
        logging.info(f"Loaded {len(products):,} products.")

        matched_ids = fetch_matched_product_ids(cur)
        queued_fps  = fetch_queued_fingerprints(cur)
        logging.info(
            f"  {len(matched_ids):,} product IDs already in product_matches  |  "
            f"{len(queued_fps):,} fingerprints already in possible_matches"
        )

        # Pre-compute match keys (same logic as match_products.py)
        for p in products:
            p['_key'] = make_match_key(p['normalized_title'] or '')

        # Group into (category, volume) buckets
        grouped: dict[int, dict] = defaultdict(lambda: defaultdict(list))
        for p in products:
            grouped[p['category_id']][p['volume_ml']].append(p)

        # In-run deduplication set: prevents double-counting within this run
        seen_fps: set[str] = set(queued_fps)

        for cat_id in sorted(grouped):
            vol_map    = grouped[cat_id]
            cat_slug   = next(
                p['category_slug'] for p in products if p['category_id'] == cat_id
            )
            # All unique products in this category (for by_id lookup in clustering)
            by_id: dict[int, dict] = {
                p['id']: p
                for bucket in vol_map.values()
                for p in bucket
            }

            # NULL-volume products get compared against every explicit-volume
            # bucket — same augmentation as match_products.py (RC1 fix).
            null_products = vol_map.get(None, [])

            # Accumulate pairs across all bucket iterations for this category
            cat_near_miss_pairs: set[frozenset] = set()
            cat_overlap_pairs:   set[frozenset] = set()
            cat_pair_scores:     dict[frozenset, dict[str, float]] = {}

            for vol_ml in sorted(vol_map, key=lambda v: (v is None, v or 0)):
                if vol_ml is None:
                    bucket = vol_map[vol_ml]
                else:
                    bucket = vol_map[vol_ml] + null_products

                if len({p['source_name'] for p in bucket}) < 2:
                    continue

                stats['buckets_scanned'] += 1
                scores = score_pairs(bucket)
                cat_pair_scores.update(scores)

                for pk, sc in scores.items():
                    # Mirror is_match() digit guard: don't let trigram bridge different age expressions
                    best = sc['j'] if sc.get('digit_blocked') else max(sc['j'], sc['t'])
                    if best >= MAIN_THRESHOLD:
                        continue  # already handled by match_products.py

                    if best >= near_miss_low:
                        cat_near_miss_pairs.add(pk)

                    # Overlap: high overlap but low Jaccard/trigram, decent baseline
                    if sc['o'] >= OVERLAP_THRESHOLD and best >= OVERLAP_MIN_SCORE:
                        cat_overlap_pairs.add(pk)

            # Overlap-only: pairs that didn't qualify as near-miss
            cat_overlap_only_pairs = cat_overlap_pairs - cat_near_miss_pairs

            # --- Resolve pairs → clusters and insert ---
            nm_clusters  = pairs_to_clusters(cat_near_miss_pairs,     by_id)
            ov_clusters  = pairs_to_clusters(cat_overlap_only_pairs,  by_id)

            nm_ins, nm_sm, nm_sq = process_candidate_clusters(
                nm_clusters, 'near_miss', cat_pair_scores,
                matched_ids, seen_fps, cur, dry_run, verbose, cat_slug,
            )
            ov_ins, ov_sm, ov_sq = process_candidate_clusters(
                ov_clusters, 'compare_matchers', cat_pair_scores,
                matched_ids, seen_fps, cur, dry_run, verbose, cat_slug,
            )

            stats['near_miss_inserted']      += nm_ins
            stats['overlap_inserted']        += ov_ins
            stats['skipped_already_matched'] += nm_sm + ov_sm
            stats['skipped_already_queued']  += nm_sq + ov_sq

            if nm_ins + ov_ins:
                logging.info(
                    f"  {cat_slug:<12}  "
                    f"+{nm_ins} near-miss  +{ov_ins} overlap-only"
                )

    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Populate possible_matches with near-miss and overlap-disagreement '
            'candidates for human review.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--category', metavar='SLUG',
        help='Restrict to one category (e.g. whisky, vino). Default: all.',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Compute candidates without writing to the database.',
    )
    parser.add_argument(
        '--near-miss-min', type=float, default=NEAR_MISS_DEFAULT,
        metavar='SCORE',
        help=(
            f'Lower bound of the near-miss similarity window '
            f'(default: {NEAR_MISS_DEFAULT}).  Upper bound is always '
            f'{MAIN_THRESHOLD} (the main algorithm threshold).'
        ),
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Print each candidate as it is found.',
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s  %(levelname)-7s %(message)s',
        datefmt='%H:%M:%S',
    )

    if args.dry_run:
        logging.info('DRY RUN — no changes will be written to the database.')

    if not (0 < args.near_miss_min < MAIN_THRESHOLD):
        logging.error(
            f'--near-miss-min must be between 0 and {MAIN_THRESHOLD} (exclusive). '
            f'Got: {args.near_miss_min}'
        )
        raise SystemExit(1)

    db = get_db()
    db.initialize_pool()

    with db.get_connection() as conn:
        stats = run_suggestions(
            conn,
            category_slug=args.category,
            near_miss_low=args.near_miss_min,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

    print(f'\n{"═" * 60}')
    print('SUGGESTION SUMMARY')
    print(f'{"═" * 60}')
    if args.dry_run:
        print('  ⚠  DRY RUN — nothing was written to the database')
    print(f'  Buckets scanned          : {stats["buckets_scanned"]}')
    print(f'  Near-miss inserted       : {stats["near_miss_inserted"]}')
    print(f'  Overlap-only inserted    : {stats["overlap_inserted"]}')
    print(f'  Skipped (already matched): {stats["skipped_already_matched"]}')
    print(f'  Skipped (already queued) : {stats["skipped_already_queued"]}')
    print(f'{"═" * 60}')


if __name__ == '__main__':
    main()
