#!/usr/bin/env python3
"""
Compare multiple product-matching algorithms side by side.

Algorithms
----------
  jaccard   Word-token Jaccard similarity (production reference, same as match_products.py)
  tfidf     TF-IDF cosine similarity – rare/brand tokens weighted higher via IDF
  trigram   Character trigram Jaccard – character-level, different failure modes
  overlap   Overlap coefficient |A∩B|/min(|A|,|B|) – handles asymmetric title lengths

All algorithms share:
  • Same pre-filtering: canonical category + exact volume_ml bucketing
  • Same STRONG_VARIANT_WORDS guard (rose/rosé/ice/pink/noir)
  • Same Union-Find connected component discovery
  • Same single-source conflict resolution
  • Cross-source pairs only — never matches products from the same store

Nothing is written to the database.

Usage
-----
  python scraper/compare_matchers.py
  python scraper/compare_matchers.py --category whisky
  python scraper/compare_matchers.py --threshold 0.70
  python scraper/compare_matchers.py --examples 5
  python scraper/compare_matchers.py --verbose
"""

import sys
import re
import math
import logging
import argparse
from pathlib import Path
from collections import defaultdict
from itertools import combinations
from typing import Callable, Optional

import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database.db_utils import get_db

# ---------------------------------------------------------------------------
# Constants (mirrors match_products.py)
# ---------------------------------------------------------------------------

NOISE_WORDS = frozenset({
    'whisky', 'whiskey', 'vodka', 'gin', 'rum', 'tequila', 'mezcal',
    'konjak', 'brandy', 'cognac', 'rakija', 'bourbon', 'scotch',
    'liker', 'likeri', 'pivo', 'beer', 'vino', 'wine',
    'the', 'i', 'hrvatska', 'original',
    'yo',
})

STRONG_VARIANT_WORDS = frozenset({'rose', 'rosé', 'ice', 'pink', 'noir'})

_VOL_RE = re.compile(r'\b\d+ml\b')


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def make_match_key(normalized_title: str) -> list[str]:
    text = _VOL_RE.sub('', normalized_title or '')
    return [
        t for t in text.split()
        if t not in NOISE_WORDS and (len(t) > 1 or t.isdigit())
    ]


def variant_guard(key1: list[str], key2: list[str]) -> bool:
    """Return True if the variant guard should REJECT this pair."""
    s1, s2 = set(key1), set(key2)
    return (s1 & STRONG_VARIANT_WORDS) != (s2 & STRONG_VARIANT_WORDS)


# ---------------------------------------------------------------------------
# Similarity functions
# ---------------------------------------------------------------------------

# --- 1. Jaccard (word tokens) ---

def jaccard_sim(key1: list[str], key2: list[str], **_) -> float:
    sa, sb = set(key1), set(key2)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# --- 2. TF-IDF cosine (word tokens, IDF-weighted) ---

def build_idf(products: list[dict]) -> dict[str, float]:
    """
    Compute sklearn-style smoothed IDF for every token in the corpus.

    IDF(t) = log((N + 1) / (df(t) + 1)) + 1

    Tokens appearing in all N products get IDF ≈ 1 (unimportant).
    Tokens appearing in only 1 product get IDF ≈ log(N) + 1 (very important).
    This makes brand-specific tokens dominate the cosine score.
    """
    N = len(products)
    df: dict[str, int] = defaultdict(int)
    for p in products:
        for token in set(p['_key']):
            df[token] += 1
    return {
        token: math.log((N + 1) / (count + 1)) + 1
        for token, count in df.items()
    }


def tfidf_sim(key1: list[str], key2: list[str], idf: dict[str, float] = None, **_) -> float:
    """
    Cosine similarity with binary TF × IDF weights.

    Since match keys are short token sets, binary TF (present/absent) is used.
    The score is high when products share rare brand-specific tokens.
    """
    if idf is None:
        return jaccard_sim(key1, key2)
    s1, s2 = set(key1), set(key2)
    common = s1 & s2
    if not common:
        return 0.0
    dot  = sum(idf.get(t, 1.0) ** 2 for t in common)
    mag1 = math.sqrt(sum(idf.get(t, 1.0) ** 2 for t in s1))
    mag2 = math.sqrt(sum(idf.get(t, 1.0) ** 2 for t in s2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


# --- 3. Character trigram Jaccard ---

def _trigrams(key: list[str], n: int = 3) -> set[str]:
    text = ' '.join(key)
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def trigram_sim(key1: list[str], key2: list[str], **_) -> float:
    """
    Jaccard similarity on character trigrams of the joined match key.

    Operates at character level — robust to tokenisation differences and
    minor spelling variants. Different failure modes from word-Jaccard:
    shares trigrams from common substrings like brand roots even when exact
    tokens differ slightly.
    """
    g1, g2 = _trigrams(key1), _trigrams(key2)
    if not g1 and not g2:
        return 1.0
    if not g1 or not g2:
        return 0.0
    return len(g1 & g2) / len(g1 | g2)


# --- 4. Overlap coefficient (word tokens) ---

def overlap_sim(key1: list[str], key2: list[str], **_) -> float:
    """
    Overlap coefficient = |A∩B| / min(|A|, |B|).

    Asymmetric: only the shorter key must be covered by the other.
    Good when one store uses shorter, less descriptive titles.
    Tends to produce more matches than Jaccard — a higher threshold
    may be needed for fair comparison.
    """
    s1, s2 = set(key1), set(key2)
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / min(len(s1), len(s2))


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------

class UnionFind:
    def __init__(self, nodes):
        self.parent = {n: n for n in nodes}
        self.rank   = {n: 0 for n in nodes}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
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
        groups: dict = defaultdict(list)
        for node in self.parent:
            groups[self.find(node)].append(node)
        return dict(groups)


# ---------------------------------------------------------------------------
# Generic matcher (same structure as match_products.py, pluggable sim fn)
# ---------------------------------------------------------------------------

def run_matcher(
    buckets: dict[tuple, list[dict]],
    sim_fn: Callable,
    threshold: float,
    sim_kwargs: dict = None,
) -> set[frozenset]:
    """
    Run one similarity function across all buckets.

    Returns a set of frozensets of (id_a, id_b) pairs — one frozenset per
    matched pair (including all pairs within multi-product clusters). This
    pair representation makes it straightforward to compare algorithms via
    set operations.
    """
    if sim_kwargs is None:
        sim_kwargs = {}

    all_pairs: set[frozenset] = set()

    for bucket in buckets.values():
        if len({p['source_name'] for p in bucket}) < 2:
            continue

        by_id = {p['id']: p for p in bucket}
        uf    = UnionFind(list(by_id))

        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                p1, p2 = bucket[i], bucket[j]
                if p1['source_name'] == p2['source_name']:
                    continue
                if variant_guard(p1['_key'], p2['_key']):
                    continue
                if sim_fn(p1['_key'], p2['_key'], **sim_kwargs) >= threshold:
                    uf.union(p1['id'], p2['id'])

        for member_ids in uf.get_components().values():
            if len(member_ids) < 2:
                continue

            members    = [by_id[pid] for pid in member_ids]
            by_source  = defaultdict(list)
            for p in members:
                by_source[p['source_name']].append(p)

            # Conflict resolution: if a source has >1 candidate in the
            # component (via indirect chain), keep the highest avg-Jaccard one.
            resolved: list[dict] = []
            for src, candidates in by_source.items():
                if len(candidates) == 1:
                    resolved.append(candidates[0])
                else:
                    others = [p for p in members if p['source_name'] != src]
                    best = max(
                        candidates,
                        key=lambda c: sum(
                            jaccard_sim(c['_key'], o['_key']) for o in others
                        ) / max(len(others), 1),
                    )
                    resolved.append(best)

            if len({p['source_name'] for p in resolved}) < 2:
                continue

            for a, b in combinations(sorted(p['id'] for p in resolved), 2):
                all_pairs.add(frozenset({a, b}))

    return all_pairs


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def fetch_and_prepare(cursor, category_id: Optional[int] = None):
    """Load products, compute match keys, group into (cat, vol) buckets."""
    query = """
        SELECT
            p.id,
            s.name      AS source_name,
            p.category_id,
            c.slug      AS category_slug,
            p.normalized_title,
            p.volume_ml,
            p.title
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
    products = [dict(row) for row in cursor.fetchall()]

    for p in products:
        p['_key'] = make_match_key(p['normalized_title'] or '')

    buckets: dict[tuple, list] = defaultdict(list)
    for p in products:
        buckets[(p['category_id'], p['volume_ml'])].append(p)

    return products, dict(buckets)


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def pairs_to_group_stats(pairs: set[frozenset], by_id: dict) -> dict:
    """Reconstruct match clusters from pairs and count by store count."""
    if not pairs:
        return {'total': 0, 'pairs': 0, 'by_store_count': {}}

    all_ids = set()
    for p in pairs:
        all_ids.update(p)

    uf = UnionFind(list(all_ids))
    for pair in pairs:
        a, b = list(pair)
        uf.union(a, b)

    by_store_count: dict[int, int] = defaultdict(int)
    total = 0
    for member_ids in uf.get_components().values():
        srcs = {by_id[pid]['source_name'] for pid in member_ids if pid in by_id}
        if len(srcs) < 2:
            continue
        total += 1
        by_store_count[len(srcs)] += 1

    return {'total': total, 'pairs': len(pairs), 'by_store_count': dict(by_store_count)}


def print_pair_examples(pairs: set[frozenset], by_id: dict, n: int = 3) -> None:
    shown = 0
    for pair in pairs:
        if shown >= n:
            break
        ids = sorted(pair)
        if len(ids) != 2:
            continue
        p1, p2 = by_id.get(ids[0]), by_id.get(ids[1])
        if not p1 or not p2:
            continue
        vol = p1.get('volume_ml') or p2.get('volume_ml')
        vol_label = f"{vol}ml" if vol else "no-vol"
        print(
            f"    [{p1['category_slug']} | {vol_label}]\n"
            f"      {p1['source_name']:<15} {p1['title']}\n"
            f"      {p2['source_name']:<15} {p2['title']}"
        )
        shown += 1
    if shown == 0:
        print("    (no printable examples)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Compare product-matching algorithms without writing to DB.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--category', metavar='SLUG',
                        help='Restrict to one category (e.g. whisky, vino).')
    parser.add_argument('--threshold', type=float, default=0.70,
                        help='Similarity threshold for all algorithms (default: 0.70).')
    parser.add_argument('--examples', type=int, default=3,
                        help='Number of disagreement examples to print (default: 3).')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Debug logging.')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s  %(levelname)-7s %(message)s',
        datefmt='%H:%M:%S',
    )

    db = get_db()
    db.initialize_pool()

    with db.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            category_id = None
            if args.category:
                cur.execute("SELECT id FROM categories WHERE slug = %s", (args.category,))
                row = cur.fetchone()
                if not row:
                    logging.error(f"Unknown category slug: '{args.category}'")
                    sys.exit(1)
                category_id = row['id']

            products, buckets = fetch_and_prepare(cur, category_id)

    if not products:
        print("No products found.")
        return

    by_id    = {p['id']: p for p in products}
    idf      = build_idf(products)
    n_active = sum(
        1 for b in buckets.values()
        if len({p['source_name'] for p in b}) >= 2
    )

    logging.info(
        f"Loaded {len(products):,} products | "
        f"{len(buckets):,} buckets | "
        f"{n_active} buckets with ≥2 sources"
    )

    # Define the four matchers: (label, sim_fn, extra_kwargs)
    MATCHERS = [
        ('jaccard', jaccard_sim, {}),
        ('tfidf',   tfidf_sim,   {'idf': idf}),
        ('trigram', trigram_sim, {}),
        ('overlap', overlap_sim, {}),
    ]

    # Run all matchers
    results: dict[str, set[frozenset]] = {}
    for name, sim_fn, kwargs in MATCHERS:
        logging.info(f"Running '{name}' ...")
        results[name] = run_matcher(buckets, sim_fn, args.threshold, kwargs)
        logging.info(f"  '{name}' → {len(results[name]):,} matched pairs")

    # -----------------------------------------------------------------------
    # Print results
    # -----------------------------------------------------------------------
    W = 65
    CAT_LABEL = args.category or 'all'

    print(f'\n{"━" * W}')
    print(f' MATCHER COMPARISON   threshold={args.threshold}   category={CAT_LABEL}')
    print(f'{"━" * W}')
    print(f' Products : {len(products):,}   '
          f'Active buckets (≥2 sources) : {n_active:,}')
    print()

    # --- Per-algorithm summary table ---
    print(f' {"Algorithm":<10}  {"Groups":>6}  {"Pairs":>6}  '
          f'{"2-src":>5}  {"3-src":>5}  {"4-src":>5}  {"5-src":>5}')
    print(f' {"─" * 10}  {"─" * 6}  {"─" * 6}  '
          f'{"─" * 5}  {"─" * 5}  {"─" * 5}  {"─" * 5}')

    all_stats: dict[str, dict] = {}
    for name, _, _ in MATCHERS:
        s  = pairs_to_group_stats(results[name], by_id)
        all_stats[name] = s
        bc = s.get('by_store_count', {})
        print(
            f' {name:<10}  {s["total"]:>6}  {s["pairs"]:>6}  '
            f'{bc.get(2, 0):>5}  {bc.get(3, 0):>5}  '
            f'{bc.get(4, 0):>5}  {bc.get(5, 0):>5}'
        )

    # --- Consensus row: pairs ALL algorithms agree on ---
    consensus = results['jaccard']
    for name in results:
        consensus = consensus & results[name]
    s  = pairs_to_group_stats(consensus, by_id)
    bc = s.get('by_store_count', {})
    print(f' {"─" * 10}  {"─" * 6}  {"─" * 6}  '
          f'{"─" * 5}  {"─" * 5}  {"─" * 5}  {"─" * 5}')
    print(
        f' {"ALL AGREE":<10}  {s["total"]:>6}  {s["pairs"]:>6}  '
        f'{bc.get(2, 0):>5}  {bc.get(3, 0):>5}  '
        f'{bc.get(4, 0):>5}  {bc.get(5, 0):>5}'
    )

    # --- Pairwise agreement matrix ---
    names = [m[0] for m in MATCHERS]
    print(f'\n{"─" * W}')
    print(' PAIRWISE AGREEMENT  (matched pairs in common)')
    print(f'{"─" * W}')
    header = f' {"":>10}' + ''.join(f'  {n:>8}' for n in names)
    print(header)
    for n1 in names:
        row = f' {n1:<10}'
        for n2 in names:
            if n1 == n2:
                row += f'  {"—":>8}'
            else:
                common = len(results[n1] & results[n2])
                pct    = common / max(len(results[n1]), 1) * 100
                row   += f'  {common:>5}({pct:3.0f}%)'
        print(row)
    print(f'  (% = share of the row algorithm\'s pairs that the column also found)')

    # --- Disagreements vs reference Jaccard ---
    ref_name = 'jaccard'
    ref      = results[ref_name]

    print(f'\n{"─" * W}')
    print(f' DISAGREEMENTS vs {ref_name.upper()} (reference)')
    print(f'{"─" * W}')

    for name, _, _ in MATCHERS:
        if name == ref_name:
            continue

        only_ref   = ref - results[name]      # Jaccard matched, other didn't
        only_other = results[name] - ref       # Other matched, Jaccard didn't
        both       = ref & results[name]

        print(f'\n  ── {name} ──')
        print(f'  Both match            : {len(both):,} pairs')
        print(f'  {ref_name} only       : {len(only_ref):,} pairs  '
              f'(Jaccard matched, {name} did NOT)')
        print(f'  {name} only           : {len(only_only := only_other):,} pairs  '
              f'({name} matched, Jaccard did NOT)')

        if args.examples > 0 and only_ref:
            print(f'\n  Examples — Jaccard matched but {name} did NOT:')
            print_pair_examples(only_ref, by_id, args.examples)

        if args.examples > 0 and only_other:
            print(f'\n  Examples — {name} matched but Jaccard did NOT:')
            print_pair_examples(only_other, by_id, args.examples)

    print(f'\n{"━" * W}')
    print(f' Consensus (ALL 4 agree): {s["total"]} groups / {s["pairs"]} pairs')
    print(f'{"━" * W}\n')


if __name__ == '__main__':
    main()
