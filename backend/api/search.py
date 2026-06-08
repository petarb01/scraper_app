"""
Search API endpoints.

GET /api/search               — full search across all group titles
GET /api/search/autocomplete  — fast prefix suggestions for the search bar

Search strategy:
  - Matched groups: searched by normalized_title across *all* store products
    in the group (a group can match if any of its store titles contains the
    query, which is important when stores name the same product differently).
    Implemented as a UNION of 5 JOINs so each branch can use the
    idx_products_normalized index independently.
  - Singletons: searched by their own normalized_title.
  - Both sets are combined with UNION ALL, then category-filtered and paginated.
"""
from decimal import Decimal
from flask import Blueprint, request, jsonify
from database import get_db
from config import Config
from extensions import limiter

search_bp = Blueprint('search', __name__)

# Same whitelist as groups.py — search results use the same sort options
SORT_MAPPING = {
    'cijena_rast': 'min_price ASC,  display_title ASC',
    'cijena_pad':  'min_price DESC, display_title ASC',
    'naziv_rast':  'display_title ASC',
    'naziv_pad':   'display_title DESC',
    'usteda_pad':  '(max_price - min_price) DESC, min_price ASC',
}
DEFAULT_SORT = 'display_title ASC'


def _f(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


# ── Core search SQL ────────────────────────────────────────────────────────
#
# Part 1: Matched groups — find any product_matches row where at least one
#   of its 5 store products has a matching normalized_title.
#   UNION (deduplicating) ensures each match_id appears once even if
#   several stores match the query.
#
# Part 2: Singletons — direct match on their own normalized_title.
#
# Parameters for this template: [ilike] * 5 + [ilike]   (6 total)
#
_SEARCH_INNER = """
    WITH matching_groups AS (
        SELECT DISTINCT pm.id AS match_id
        FROM product_matches pm
        JOIN products p ON p.id = pm.ecuga_id        AND p.normalized_title ILIKE %s
        UNION
        SELECT DISTINCT pm.id AS match_id
        FROM product_matches pm
        JOIN products p ON p.id = pm.cugaklik_id     AND p.normalized_title ILIKE %s
        UNION
        SELECT DISTINCT pm.id AS match_id
        FROM product_matches pm
        JOIN products p ON p.id = pm.diskontfumar_id AND p.normalized_title ILIKE %s
        UNION
        SELECT DISTINCT pm.id AS match_id
        FROM product_matches pm
        JOIN products p ON p.id = pm.promili_id      AND p.normalized_title ILIKE %s
        UNION
        SELECT DISTINCT pm.id AS match_id
        FROM product_matches pm
        JOIN products p ON p.id = pm.rotodinamic_id  AND p.normalized_title ILIKE %s
    )
    SELECT
        vg.group_id,
        vg.match_id,
        vg.singleton_id,
        vg.display_title,
        vg.display_image_url,
        vg.volume_ml,
        vg.category_slug,
        vg.category_name,
        ROUND(vg.min_price::numeric, 2)                   AS min_price,
        ROUND(vg.max_price::numeric, 2)                   AS max_price,
        vg.store_count,
        ROUND((vg.max_price - vg.min_price)::numeric, 2)  AS usteda
    FROM v_product_groups vg
    JOIN matching_groups mg ON mg.match_id = vg.match_id

    UNION ALL

    SELECT
        vg.group_id,
        vg.match_id,
        vg.singleton_id,
        vg.display_title,
        vg.display_image_url,
        vg.volume_ml,
        vg.category_slug,
        vg.category_name,
        ROUND(vg.min_price::numeric, 2)                   AS min_price,
        ROUND(vg.max_price::numeric, 2)                   AS max_price,
        vg.store_count,
        ROUND(0::numeric, 2)                              AS usteda
    FROM v_product_groups vg
    JOIN products p ON p.id = vg.singleton_id
    WHERE p.normalized_title ILIKE %s
"""


# ── GET /api/search ────────────────────────────────────────────────────────

@search_bp.route('/', methods=['GET'])
@limiter.limit("60 per minute")
def search_products():
    """
    Search product groups by query string.

    Query params:
        q          str   required, min 2 chars
        page       int   default 1
        limit      int   default 24, max 100
        kategorija str   optional category slug filter
        sortiraj   str   cijena_rast|cijena_pad|naziv_rast|naziv_pad|usteda_pad
    """
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({
            'success': False,
            'error': 'Upit mora imati najmanje 2 znaka',
        }), 400

    try:
        page  = max(1, int(request.args.get('page',  1)))
        limit = min(max(1, int(request.args.get('limit', Config.DEFAULT_PAGE_SIZE))),
                    Config.MAX_PAGE_SIZE)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Neispravan parametar stranice'}), 400

    kategorija_list = request.args.getlist('kategorija')
    sort_clause = SORT_MAPPING.get(request.args.get('sortiraj', ''), DEFAULT_SORT)
    offset = (page - 1) * limit
    ilike = f'%{q}%'  # 6 uses: 5 matched-group branches + 1 singleton branch

    # ── Build outer WHERE from all filter params ──────────────────────────
    conditions = []
    filter_params = []

    if kategorija_list:
        ph = ', '.join(['%s'] * len(kategorija_list))
        conditions.append(f'category_slug IN ({ph})')
        filter_params.extend(kategorija_list)

    try:
        raw_min = request.args.get('min_cijena')
        raw_max = request.args.get('max_cijena')
        raw_vol = request.args.get('volumen')
        if raw_min:
            conditions.append('min_price >= %s')
            filter_params.append(float(raw_min))
        if raw_max:
            conditions.append('min_price <= %s')
            filter_params.append(float(raw_max))
        if raw_vol:
            conditions.append('volume_ml = %s')
            filter_params.append(int(raw_vol))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Neispravan parametar filtera'}), 400

    if request.args.get('ducani') == '2':
        conditions.append('store_count >= 2')

    outer_where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    base_params = [ilike] * 6  # one per branch in _SEARCH_INNER

    try:
        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            # sort_clause comes from SORT_MAPPING whitelist — safe to interpolate
            cur.execute(f"""
                SELECT *
                FROM ({_SEARCH_INNER}) results
                {outer_where}
                ORDER BY {sort_clause}
                LIMIT %s OFFSET %s
            """, base_params + filter_params + [limit, offset])

            groups = [{
                'group_id':          row['group_id'],
                'match_id':          row['match_id'],
                'singleton_id':      row['singleton_id'],
                'display_title':     row['display_title'],
                'display_image_url': row['display_image_url'],
                'volume_ml':         row['volume_ml'],
                'category_slug':     row['category_slug'],
                'category_name':     row['category_name'],
                'min_price':         _f(row['min_price']),
                'max_price':         _f(row['max_price']),
                'store_count':       row['store_count'],
                'usteda':            _f(row['usteda']),
            } for row in cur.fetchall()]

            cur.execute(f"""
                SELECT COUNT(*) AS total
                FROM ({_SEARCH_INNER}) results
                {outer_where}
            """, base_params + filter_params)

            total = cur.fetchone()['total']

        return jsonify({
            'success': True,
            'data': groups,
            'pagination': {
                'page':  page,
                'limit': limit,
                'total': total,
                'pages': max(1, (total + limit - 1) // limit),
            },
            'query': q,
        })

    except Exception:
        return jsonify({'success': False, 'error': 'Interna greška poslužitelja'}), 500


# ── GET /api/search/autocomplete ──────────────────────────────────────────

@search_bp.route('/autocomplete', methods=['GET'])
@limiter.limit("60 per minute")
def autocomplete():
    """
    Fast title-based suggestions for the search bar dropdown.

    Searches display_title — the canonical name the user will see and click.
    Results sorted by store_count DESC, min_price ASC (most-compared first).

    Query params:
        q      str  required, min 2 chars
        limit  int  default 8, max 20
    """
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'success': True, 'data': []})

    try:
        limit = min(max(1, int(request.args.get('limit', 8))), 20)
    except (ValueError, TypeError):
        limit = 8

    try:
        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            cur.execute("""
                SELECT
                    group_id,
                    display_title,
                    category_name,
                    ROUND(min_price::numeric, 2) AS min_price
                FROM v_product_groups
                WHERE display_title ILIKE %s
                ORDER BY store_count DESC, min_price ASC
                LIMIT %s
            """, (f'%{q}%', limit))

            suggestions = [{
                'group_id':      row['group_id'],
                'display_title': row['display_title'],
                'category_name': row['category_name'],
                'min_price':     _f(row['min_price']),
            } for row in cur.fetchall()]

        return jsonify({'success': True, 'data': suggestions})

    except Exception:
        return jsonify({'success': False, 'error': 'Interna greška poslužitelja'}), 500
