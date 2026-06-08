"""
Product groups API endpoints.

A "group" is the browse/search unit. It is either:
  - A matched group  (group_id = "g{match_id}")   — same product across ≥2 stores
  - A singleton      (group_id = "p{product_id}")  — product found in only 1 store

GET /api/groups          — browse with filters, sort, pagination
GET /api/groups/<id>     — full price comparison detail for one group
"""
from decimal import Decimal
from flask import Blueprint, request, jsonify
from database import get_db
from config import Config

groups_bp = Blueprint('groups', __name__)

# ── Constants ──────────────────────────────────────────────────────────────

# Sort clauses come from this whitelist only — never from raw user input.
SORT_MAPPING = {
    'cijena_rast': 'min_price ASC,  display_title ASC',
    'cijena_pad':  'min_price DESC, display_title ASC',
    'naziv_rast':  'display_title ASC',
    'naziv_pad':   'display_title DESC',
    'usteda_pad':  '(max_price - min_price) DESC, min_price ASC',
}
DEFAULT_SORT = 'display_title ASC'

# Source names in the order they appear as columns in product_matches.
SOURCES = ['ecuga', 'cugaklik', 'diskontfumar', 'promili', 'rotodinamic']


# ── Helpers ────────────────────────────────────────────────────────────────

def _f(v):
    """Convert Decimal (returned by psycopg2 for NUMERIC columns) to float."""
    if isinstance(v, Decimal):
        return float(v)
    return v


def _parse_group_id(raw: str):
    """
    Parse a group_id string like "g123" or "p456".
    Returns ('g', 123) or ('p', 456).
    Raises ValueError on bad format.
    """
    if not raw or len(raw) < 2:
        raise ValueError('Neispravan group_id')
    kind = raw[0]
    if kind not in ('g', 'p'):
        raise ValueError("group_id mora počinjati s 'g' ili 'p'")
    try:
        int_id = int(raw[1:])
    except ValueError:
        raise ValueError('Sufiks group_id mora biti broj')
    return kind, int_id


def _format_group_row(row) -> dict:
    """Convert a v_product_groups row to the standard API shape."""
    return {
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
    }


# ── GET /api/groups ────────────────────────────────────────────────────────

@groups_bp.route('/', methods=['GET'])
def get_groups():
    """
    Browse product groups with pagination and filtering.

    Query params:
        page         int   default 1
        limit        int   default 24, max 100
        kategorija   str   repeat for multiple: ?kategorija=whisky&kategorija=rum
        min_cijena   float filter by min_price >= value
        max_cijena   float filter by min_price <= value
        volumen      int   exact volume_ml match
        ducani       int   minimum store_count (e.g. 2 = only matched groups)
        sortiraj     str   cijena_rast|cijena_pad|naziv_rast|naziv_pad|usteda_pad
    """
    # ── Parse & validate params ──────────────────────────────────────────
    try:
        page  = max(1, int(request.args.get('page',  1)))
        limit = min(max(1, int(request.args.get('limit', Config.DEFAULT_PAGE_SIZE))),
                    Config.MAX_PAGE_SIZE)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Neispravan parametar stranice'}), 400

    try:
        min_cijena = float(request.args['min_cijena']) if 'min_cijena' in request.args else None
        max_cijena = float(request.args['max_cijena']) if 'max_cijena' in request.args else None
    except ValueError:
        return jsonify({'success': False, 'error': 'Neispravan parametar cijene'}), 400

    try:
        volumen = int(request.args['volumen']) if 'volumen' in request.args else None
    except ValueError:
        return jsonify({'success': False, 'error': 'Neispravan parametar volumena'}), 400

    try:
        ducani = int(request.args['ducani']) if 'ducani' in request.args else None
        if ducani is not None and ducani < 1:
            ducani = None
    except ValueError:
        return jsonify({'success': False, 'error': 'Neispravan parametar dućana'}), 400

    # Category slugs — may be repeated
    kategorija_list = request.args.getlist('kategorija')

    # Sort — unknown value silently falls back to default
    sort_clause = SORT_MAPPING.get(request.args.get('sortiraj', ''), DEFAULT_SORT)

    offset = (page - 1) * limit

    # ── Build WHERE clauses ───────────────────────────────────────────────
    where = []
    params = []

    if kategorija_list:
        # Placeholders built from len (not user values) — safe
        ph = ', '.join(['%s'] * len(kategorija_list))
        where.append(f'category_slug IN ({ph})')
        params.extend(kategorija_list)

    if min_cijena is not None:
        where.append('min_price >= %s')
        params.append(min_cijena)

    if max_cijena is not None:
        where.append('min_price <= %s')
        params.append(max_cijena)

    if volumen is not None:
        where.append('volume_ml = %s')
        params.append(volumen)

    if ducani is not None:
        where.append('store_count >= %s')
        params.append(ducani)

    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    # ── Execute ───────────────────────────────────────────────────────────
    try:
        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            # sort_clause is from SORT_MAPPING whitelist — safe to interpolate
            cur.execute(f"""
                SELECT
                    group_id,
                    match_id,
                    singleton_id,
                    display_title,
                    display_image_url,
                    volume_ml,
                    category_slug,
                    category_name,
                    ROUND(min_price::numeric, 2)              AS min_price,
                    ROUND(max_price::numeric, 2)              AS max_price,
                    store_count,
                    ROUND((max_price - min_price)::numeric, 2) AS usteda
                FROM v_product_groups
                {where_sql}
                ORDER BY {sort_clause}
                LIMIT %s OFFSET %s
            """, params + [limit, offset])

            groups = [_format_group_row(row) for row in cur.fetchall()]

            cur.execute(f"""
                SELECT COUNT(*) AS total
                FROM v_product_groups
                {where_sql}
            """, params)

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
        })

    except Exception:
        return jsonify({'success': False, 'error': 'Interna greška poslužitelja'}), 500


# ── GET /api/groups/<group_id> ────────────────────────────────────────────

@groups_bp.route('/<group_id>', methods=['GET'])
def get_group_detail(group_id):
    """
    Full price comparison detail for a single product group.

    group_id format:
        g{match_id}    — matched group (product in ≥2 stores)
        p{product_id}  — singleton (product in 1 store)
    """
    try:
        kind, int_id = _parse_group_id(group_id)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    try:
        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            data = (_fetch_matched(cur, int_id)
                    if kind == 'g'
                    else _fetch_singleton(cur, int_id))

        if data is None:
            return jsonify({'success': False, 'error': 'Proizvod nije pronađen'}), 404

        return jsonify({'success': True, 'data': data})

    except Exception:
        return jsonify({'success': False, 'error': 'Interna greška poslužitelja'}), 500


def _fetch_matched(cur, match_id: int):
    """
    Fetch detail for a matched group — all 5 store columns in one wide row,
    then build a clean stores list in Python.
    """
    cur.execute("""
        SELECT
            pm.id AS match_id,
            COALESCE(ppr.title, pe.title, pd.title, pc.title, pr.title)
                AS display_title,
            COALESCE(pe.volume_ml, pc.volume_ml, pd.volume_ml, ppr.volume_ml, pr.volume_ml)
                AS volume_ml,
            COALESCE(ce.slug,  cc.slug,  cd.slug,  cpr.slug,  cr.slug)
                AS category_slug,
            COALESCE(ce.display_name, cc.display_name, cd.display_name,
                     cpr.display_name, cr.display_name)
                AS category_name,

            pe.id              AS ecuga_product_id,
            pe.title           AS ecuga_title,
            pe.price           AS ecuga_price,
            pe.price_original  AS ecuga_price_original,
            pe.product_url     AS ecuga_url,
            pe.image_url       AS ecuga_image_url,
            se.display_name    AS ecuga_store_display_name,
            se.website_url     AS ecuga_store_url,

            pc.id              AS cugaklik_product_id,
            pc.title           AS cugaklik_title,
            pc.price           AS cugaklik_price,
            pc.price_original  AS cugaklik_price_original,
            pc.product_url     AS cugaklik_url,
            pc.image_url       AS cugaklik_image_url,
            sc.display_name    AS cugaklik_store_display_name,
            sc.website_url     AS cugaklik_store_url,

            pd.id              AS diskontfumar_product_id,
            pd.title           AS diskontfumar_title,
            pd.price           AS diskontfumar_price,
            pd.price_original  AS diskontfumar_price_original,
            pd.product_url     AS diskontfumar_url,
            pd.image_url       AS diskontfumar_image_url,
            sd.display_name    AS diskontfumar_store_display_name,
            sd.website_url     AS diskontfumar_store_url,

            ppr.id             AS promili_product_id,
            ppr.title          AS promili_title,
            ppr.price          AS promili_price,
            ppr.price_original AS promili_price_original,
            ppr.product_url    AS promili_url,
            ppr.image_url      AS promili_image_url,
            spr.display_name   AS promili_store_display_name,
            spr.website_url    AS promili_store_url,

            pr.id              AS rotodinamic_product_id,
            pr.title           AS rotodinamic_title,
            pr.price           AS rotodinamic_price,
            pr.price_original  AS rotodinamic_price_original,
            pr.product_url     AS rotodinamic_url,
            pr.image_url       AS rotodinamic_image_url,
            sr.display_name    AS rotodinamic_store_display_name,
            sr.website_url     AS rotodinamic_store_url

        FROM product_matches pm

        LEFT JOIN products   pe  ON pe.id  = pm.ecuga_id        AND pe.is_available AND pe.price > 0
        LEFT JOIN categories ce  ON ce.id  = pe.category_id
        LEFT JOIN sources    se  ON se.id  = pe.source_id

        LEFT JOIN products   pc  ON pc.id  = pm.cugaklik_id     AND pc.is_available AND pc.price > 0
        LEFT JOIN categories cc  ON cc.id  = pc.category_id
        LEFT JOIN sources    sc  ON sc.id  = pc.source_id

        LEFT JOIN products   pd  ON pd.id  = pm.diskontfumar_id AND pd.is_available AND pd.price > 0
        LEFT JOIN categories cd  ON cd.id  = pd.category_id
        LEFT JOIN sources    sd  ON sd.id  = pd.source_id

        LEFT JOIN products   ppr ON ppr.id = pm.promili_id      AND ppr.is_available AND ppr.price > 0
        LEFT JOIN categories cpr ON cpr.id = ppr.category_id
        LEFT JOIN sources    spr ON spr.id = ppr.source_id

        LEFT JOIN products   pr  ON pr.id  = pm.rotodinamic_id  AND pr.is_available AND pr.price > 0
        LEFT JOIN categories cr  ON cr.id  = pr.category_id
        LEFT JOIN sources    sr  ON sr.id  = pr.source_id

        WHERE pm.id = %s
    """, (match_id,))

    row = cur.fetchone()
    if not row:
        return None

    # Build stores list — only include sources with a non-NULL product_id
    stores = []
    for src in SOURCES:
        if row[f'{src}_product_id'] is None:
            continue
        stores.append({
            'store_name':          src,
            'store_display_name':  row[f'{src}_store_display_name'],
            'store_url':           row[f'{src}_store_url'],
            'product_title':       row[f'{src}_title'],
            'price':               _f(row[f'{src}_price']),
            'price_original':      row[f'{src}_price_original'],
            'product_url':         row[f'{src}_url'],
            'image_url':           row[f'{src}_image_url'],
            'is_cheapest':         False,
        })

    if not stores:
        return None

    stores.sort(key=lambda s: s['price'])
    stores[0]['is_cheapest'] = True

    min_price = stores[0]['price']
    max_price = stores[-1]['price']
    usteda = round(max_price - min_price, 2)
    usteda_posto = round((usteda / max_price * 100) if max_price > 0 else 0.0, 1)

    return {
        'group_id':      f'g{match_id}',
        'display_title': row['display_title'],
        'volume_ml':     row['volume_ml'],
        'category_slug': row['category_slug'],
        'category_name': row['category_name'],
        'stores':        stores,
        'min_price':     round(min_price, 2),
        'max_price':     round(max_price, 2),
        'usteda':        usteda,
        'usteda_posto':  usteda_posto,
    }


def _fetch_singleton(cur, product_id: int):
    """Fetch detail for a singleton — single product, single store."""
    cur.execute("""
        SELECT
            p.id,
            p.title,
            p.price,
            p.price_original,
            p.product_url,
            p.image_url,
            p.volume_ml,
            c.slug         AS category_slug,
            c.display_name AS category_name,
            s.name         AS store_name,
            s.display_name AS store_display_name,
            s.website_url  AS store_url
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        JOIN  sources s        ON s.id = p.source_id
        WHERE p.id = %s
          AND p.is_available
          AND p.price > 0
    """, (product_id,))

    row = cur.fetchone()
    if not row:
        return None

    price = _f(row['price'])

    return {
        'group_id':      f'p{product_id}',
        'display_title': row['title'],
        'volume_ml':     row['volume_ml'],
        'category_slug': row['category_slug'],
        'category_name': row['category_name'],
        'stores': [{
            'store_name':         row['store_name'],
            'store_display_name': row['store_display_name'],
            'store_url':          row['store_url'],
            'product_title':      row['title'],
            'price':              price,
            'price_original':     row['price_original'],
            'product_url':        row['product_url'],
            'image_url':          row['image_url'],
            'is_cheapest':        True,
        }],
        'min_price':    round(price, 2),
        'max_price':    round(price, 2),
        'usteda':       0.0,
        'usteda_posto': 0.0,
    }
