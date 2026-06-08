"""
Stats API endpoint.

GET /api/stats  — aggregated numbers for the landing page.

Results are cached in memory for 10 minutes so the heavy COUNT queries
on v_product_groups are not run on every page load.  No Redis required.
"""
import time
from flask import Blueprint, jsonify
from database import get_db

stats_bp = Blueprint('stats', __name__)

_CACHE_TTL = 600  # 10 minutes in seconds
_cache: dict = {'data': None, 'ts': 0.0}


@stats_bp.route('/', methods=['GET'])
def get_stats():
    """
    Return aggregated site statistics.

    Response shape:
        products_total  — total available products across all stores
        groups_total    — total browsable groups (matched + singletons)
        categories_total — categories with at least one group
        stores_total    — number of active stores
        matched_groups  — groups with prices from 2+ stores (price-comparable)
    """
    now = time.monotonic()

    # Serve from cache if still fresh
    if _cache['data'] is not None and (now - _cache['ts']) < _CACHE_TTL:
        return jsonify({'success': True, 'data': _cache['data']})

    try:
        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*)
                     FROM   products
                     WHERE  is_available AND price > 0)                    AS products_total,

                    (SELECT COUNT(*)
                     FROM   v_product_groups)                              AS groups_total,

                    (SELECT COUNT(DISTINCT category_slug)
                     FROM   v_product_groups
                     WHERE  category_slug IS NOT NULL)                     AS categories_total,

                    (SELECT COUNT(*)
                     FROM   sources
                     WHERE  is_active)                                     AS stores_total,

                    (SELECT COUNT(*)
                     FROM   v_product_groups
                     WHERE  store_count >= 2)                              AS matched_groups
            """)
            row = cur.fetchone()

        data = {
            'products_total':   row['products_total'],
            'groups_total':     row['groups_total'],
            'categories_total': row['categories_total'],
            'stores_total':     row['stores_total'],
            'matched_groups':   row['matched_groups'],
        }

        _cache['data'] = data
        _cache['ts']   = now

        return jsonify({'success': True, 'data': data})

    except Exception:
        # If the query fails but we have stale cache, return it rather than an error
        if _cache['data'] is not None:
            return jsonify({'success': True, 'data': _cache['data']})
        return jsonify({'success': False, 'error': 'Interna greška poslužitelja'}), 500
