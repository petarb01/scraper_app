"""
Admin blueprint routes — HTML pages and internal API endpoints.

HTML pages (Jinja2, Basic Auth required):
  GET  /admin/review        Review queue page (JS-driven card interface)
  GET  /admin/history       History page (server-rendered table)

Internal JSON API (Basic Auth required, not exposed to user CORS):
  GET  /admin/api/queue             Paginated list of pending candidates
  GET  /admin/api/queue/<id>        Single candidate detail
  POST /admin/api/review/<id>       Submit decision: confirm / reject / skip
  POST /admin/api/undo/<id>         Reset a confirmed/rejected row to pending
  GET  /admin/api/stats             Counts per review_status
"""

import logging
from datetime import datetime
from decimal import Decimal

from flask import jsonify, render_template, request
from psycopg2.extras import RealDictCursor

log = logging.getLogger(__name__)

from database import get_db

from .auth import require_admin
from . import admin_bp

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCES = ['ecuga', 'cugaklik', 'promili', 'diskontfumar', 'rotodinamic']

SOURCE_DISPLAY = {
    'ecuga':        'eCuga',
    'cugaklik':     'Cugaklik',
    'promili':      'Promili',
    'diskontfumar': 'Diskontfumar',
    'rotodinamic':  'Rotodinamic',
}

SUGGESTION_LABELS = {
    'near_miss':        'Near Miss',
    'compare_matchers': 'Overlap Disagreement',
    'seed_inspection':  'Manual Seed',
    'seed_edge_cases':  'Edge Case Seed',
}

# Single large SELECT reused by both the queue API and the single-item API.
# All price values are cast to TEXT to avoid Decimal serialisation issues.
_CANDIDATE_SELECT = """
    SELECT
        pm.id,
        pm.suggestion_source,
        pm.jaccard_score,
        pm.trigram_score,
        pm.review_status,
        pm.reviewed_at,
        pm.reviewer_notes,
        pm.confirmed_match_id,
        pm.created_at,

        pm.ecuga_id,
        ep.title        AS ecuga_title,
        CAST(ep.price AS TEXT) AS ecuga_price,
        ep.product_url  AS ecuga_url,
        ep.volume_ml    AS ecuga_vol,
        ec.slug         AS ecuga_cat,

        pm.cugaklik_id,
        cp.title        AS cugaklik_title,
        CAST(cp.price AS TEXT) AS cugaklik_price,
        cp.product_url  AS cugaklik_url,
        cp.volume_ml    AS cugaklik_vol,
        cc.slug         AS cugaklik_cat,

        pm.promili_id,
        pp.title        AS promili_title,
        CAST(pp.price AS TEXT) AS promili_price,
        pp.product_url  AS promili_url,
        pp.volume_ml    AS promili_vol,
        pc.slug         AS promili_cat,

        pm.diskontfumar_id,
        dp.title        AS diskontfumar_title,
        CAST(dp.price AS TEXT) AS diskontfumar_price,
        dp.product_url  AS diskontfumar_url,
        dp.volume_ml    AS diskontfumar_vol,
        dc.slug         AS diskontfumar_cat,

        pm.rotodinamic_id,
        rp.title        AS rotodinamic_title,
        CAST(rp.price AS TEXT) AS rotodinamic_price,
        rp.product_url  AS rotodinamic_url,
        rp.volume_ml    AS rotodinamic_vol,
        rc.slug         AS rotodinamic_cat

    FROM possible_matches pm
    LEFT JOIN products   ep ON pm.ecuga_id        = ep.id
    LEFT JOIN categories ec ON ep.category_id     = ec.id
    LEFT JOIN products   cp ON pm.cugaklik_id     = cp.id
    LEFT JOIN categories cc ON cp.category_id     = cc.id
    LEFT JOIN products   pp ON pm.promili_id      = pp.id
    LEFT JOIN categories pc ON pp.category_id     = pc.id
    LEFT JOIN products   dp ON pm.diskontfumar_id = dp.id
    LEFT JOIN categories dc ON dp.category_id     = dc.id
    LEFT JOIN products   rp ON pm.rotodinamic_id  = rp.id
    LEFT JOIN categories rc ON rp.category_id     = rc.id
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_candidate(row: dict) -> dict:
    """Convert a flat DB row (from _CANDIDATE_SELECT) into a structured dict."""
    stores = []
    for src in SOURCES:
        if row[f'{src}_id'] is None:
            continue
        price_raw = row[f'{src}_price']
        try:
            price_f = float(price_raw) if price_raw is not None else 0.0
        except (TypeError, ValueError):
            price_f = 0.0
        stores.append({
            'source':       src,
            'display_name': SOURCE_DISPLAY[src],
            'title':        row[f'{src}_title'],
            'price':        price_f,
            'url':          row[f'{src}_url'],
            'volume_ml':    row[f'{src}_vol'],
            'category':     row[f'{src}_cat'],
        })

    # Derive shared category and volume from first store that has them
    category  = next((s['category']  for s in stores if s['category']),  None)
    volume_ml = next((s['volume_ml'] for s in stores if s['volume_ml']), None)

    def _dt(v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    def _score(v):
        return float(v) if v is not None else None

    return {
        'id':                     row['id'],
        'suggestion_source':      row['suggestion_source'],
        'suggestion_source_label': SUGGESTION_LABELS.get(
            row['suggestion_source'], row['suggestion_source']
        ),
        'jaccard_score':          _score(row['jaccard_score']),
        'trigram_score':          _score(row['trigram_score']),
        'review_status':          row['review_status'],
        'reviewed_at':            _dt(row.get('reviewed_at')),
        'reviewer_notes':         row.get('reviewer_notes'),
        'confirmed_match_id':     row.get('confirmed_match_id'),
        'created_at':             _dt(row.get('created_at')),
        'category':               category,
        'volume_ml':              volume_ml,
        'stores':                 stores,
    }


# ---------------------------------------------------------------------------
# HTML page routes
# ---------------------------------------------------------------------------

@admin_bp.route('/review')
@require_admin
def review_page():
    """Serve the review queue HTML shell (JS fetches data from /admin/api/queue)."""
    return render_template('admin/review.html')


@admin_bp.route('/history')
@require_admin
def history_page():
    """Serve the history page (server-side rendered)."""
    db = get_db()
    db.initialize_pool()

    with db.get_cursor() as cur:
        cur.execute(
            _CANDIDATE_SELECT
            + " WHERE pm.review_status IN ('confirmed', 'rejected', 'superseded')"
              " ORDER BY pm.reviewed_at DESC NULLS LAST"
              " LIMIT 200"
        )
        rows = [_format_candidate(dict(r)) for r in cur.fetchall()]

        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE review_status = 'pending')    AS pending,
                COUNT(*) FILTER (WHERE review_status = 'confirmed')  AS confirmed,
                COUNT(*) FILTER (WHERE review_status = 'rejected')   AS rejected,
                COUNT(*) FILTER (WHERE review_status = 'superseded') AS superseded
            FROM possible_matches
        """)
        counts = dict(cur.fetchone())

    return render_template('admin/history.html', rows=rows, counts=counts)


# ---------------------------------------------------------------------------
# Queue API
# ---------------------------------------------------------------------------

@admin_bp.route('/api/queue')
@require_admin
def api_queue():
    """
    Return a paginated list of pending possible_matches, sorted by
    jaccard_score DESC (highest-confidence candidates first).

    Query params:
      page     — 1-based page number (default 1)
      per_page — items per page (default 20, max 100)
    """
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        offset   = (page - 1) * per_page

        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            cur.execute(
                _CANDIDATE_SELECT
                + " WHERE pm.review_status = 'pending'"
                  " ORDER BY pm.jaccard_score DESC NULLS LAST,"
                  "          pm.trigram_score DESC NULLS LAST,"
                  "          pm.id ASC"
                  " LIMIT %s OFFSET %s",
                (per_page, offset),
            )
            items = [_format_candidate(dict(r)) for r in cur.fetchall()]

            cur.execute(
                "SELECT COUNT(*) AS n FROM possible_matches WHERE review_status = 'pending'"
            )
            total = cur.fetchone()['n']

        return jsonify({
            'success':  True,
            'items':    items,
            'total':    total,
            'page':     page,
            'per_page': per_page,
            'pages':    max(1, (total + per_page - 1) // per_page),
        })

    except Exception:
        log.exception("Admin route error")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@admin_bp.route('/api/queue/<int:pm_id>')
@require_admin
def api_queue_item(pm_id):
    """Return a single pending candidate by ID."""
    try:
        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            cur.execute(
                _CANDIDATE_SELECT + " WHERE pm.id = %s",
                (pm_id,),
            )
            row = cur.fetchone()

        if not row:
            return jsonify({'success': False, 'error': 'Not found'}), 404

        return jsonify({'success': True, 'item': _format_candidate(dict(row))})

    except Exception:
        log.exception("Admin route error")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ---------------------------------------------------------------------------
# Review action API
# ---------------------------------------------------------------------------

@admin_bp.route('/api/review/<int:pm_id>', methods=['POST'])
@require_admin
def api_review(pm_id):
    """
    Submit a review decision for a pending candidate.

    Body (JSON):
      action  — "confirm" | "reject" | "skip"
      notes   — optional string saved to reviewer_notes
    """
    try:
        body   = request.get_json(force=True) or {}
        action = body.get('action', '')
        notes  = (body.get('notes') or '').strip() or None

        if action not in ('confirm', 'reject', 'skip'):
            return jsonify({'success': False, 'error': 'action must be confirm, reject, or skip'}), 400

        # Skip is a client-side-only operation — nothing is written to the DB.
        if action == 'skip':
            return jsonify({'success': True})

        db = get_db()
        db.initialize_pool()

        superseded_count = 0

        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Load the row and verify it is still pending
                cur.execute(
                    """
                    SELECT id, review_status,
                           ecuga_id, cugaklik_id, promili_id,
                           diskontfumar_id, rotodinamic_id
                      FROM possible_matches
                     WHERE id = %s
                    """,
                    (pm_id,),
                )
                pm = cur.fetchone()

                if not pm:
                    return jsonify({'success': False, 'error': 'Not found'}), 404

                if pm['review_status'] != 'pending':
                    return jsonify({
                        'success': False,
                        'error':   f"Already {pm['review_status']} — refresh the page",
                    }), 409

                if action == 'reject':
                    cur.execute(
                        """
                        UPDATE possible_matches
                           SET review_status  = 'rejected',
                               reviewed_at    = CURRENT_TIMESTAMP,
                               reviewer_notes = %s,
                               updated_at     = CURRENT_TIMESTAMP
                         WHERE id = %s
                        """,
                        (notes, pm_id),
                    )

                elif action == 'confirm':
                    # Determine which stores to include in the confirmed match.
                    # The UI may send a subset via confirmed_stores; default to all non-null.
                    requested = body.get('confirmed_stores')
                    if requested and isinstance(requested, list):
                        confirmed_stores = [
                            s for s in requested
                            if s in SOURCES and pm[f'{s}_id'] is not None
                        ]
                    else:
                        confirmed_stores = [s for s in SOURCES if pm[f'{s}_id'] is not None]

                    if len(confirmed_stores) < 2:
                        return jsonify({
                            'success': False,
                            'error':   'Select at least 2 stores to confirm a match',
                        }), 422

                    # Build the values list: confirmed store IDs, NULL for excluded stores.
                    id_values = [
                        pm[f'{src}_id'] if src in confirmed_stores else None
                        for src in SOURCES
                    ]

                    # Check if any of these product IDs are already in product_matches.
                    confirmed_ids = [v for v in id_values if v is not None]
                    cur.execute(
                        """
                        SELECT id
                          FROM product_matches
                         WHERE ecuga_id        = ANY(%s)
                            OR cugaklik_id     = ANY(%s)
                            OR promili_id      = ANY(%s)
                            OR diskontfumar_id = ANY(%s)
                            OR rotodinamic_id  = ANY(%s)
                        """,
                        [confirmed_ids] * 5,
                    )
                    existing = cur.fetchall()
                    if existing:
                        existing_ids = [r['id'] for r in existing]
                        return jsonify({
                            'success': False,
                            'error': (
                                f'One or more products are already matched in product_matches '
                                f'(row IDs: {existing_ids}). '
                                f'Remove the conflicting match first.'
                            ),
                        }), 409

                    cur.execute(
                        """
                        INSERT INTO product_matches
                            (ecuga_id, cugaklik_id, promili_id,
                             diskontfumar_id, rotodinamic_id,
                             match_source)
                        VALUES (%s, %s, %s, %s, %s, 'human_confirmed')
                        RETURNING id
                        """,
                        id_values,
                    )
                    new_match_id = cur.fetchone()['id']

                    cur.execute(
                        """
                        UPDATE possible_matches
                           SET review_status      = 'confirmed',
                               reviewed_at        = CURRENT_TIMESTAMP,
                               reviewer_notes     = %s,
                               confirmed_match_id = %s,
                               updated_at         = CURRENT_TIMESTAMP
                         WHERE id = %s
                        """,
                        (notes, new_match_id, pm_id),
                    )

                    # Auto-supersede any other pending candidates that share one or
                    # more product IDs with the ones we just confirmed.
                    cur.execute(
                        """
                        UPDATE possible_matches
                           SET review_status = 'superseded',
                               reviewed_at   = CURRENT_TIMESTAMP,
                               updated_at    = CURRENT_TIMESTAMP
                         WHERE id != %s
                           AND review_status = 'pending'
                           AND (
                               ecuga_id        = ANY(%s) OR
                               cugaklik_id     = ANY(%s) OR
                               promili_id      = ANY(%s) OR
                               diskontfumar_id = ANY(%s) OR
                               rotodinamic_id  = ANY(%s)
                           )
                        RETURNING id
                        """,
                        (pm_id,
                         confirmed_ids, confirmed_ids, confirmed_ids,
                         confirmed_ids, confirmed_ids),
                    )
                    superseded_count = len(cur.fetchall())

        return jsonify({'success': True, 'superseded': superseded_count})

    except Exception:
        log.exception("Admin route error")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ---------------------------------------------------------------------------
# Undo API
# ---------------------------------------------------------------------------

@admin_bp.route('/api/undo/<int:pm_id>', methods=['POST'])
@require_admin
def api_undo(pm_id):
    """
    Reset a confirmed or rejected row back to 'pending'.

    If the row was confirmed, the corresponding product_matches row (with
    match_source = 'human_confirmed') is deleted.  The possible_matches row
    reverts to 'pending' so the admin can re-review it.
    """
    try:
        db = get_db()
        db.initialize_pool()

        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, review_status, confirmed_match_id FROM possible_matches WHERE id = %s",
                    (pm_id,),
                )
                pm = cur.fetchone()

                if not pm:
                    return jsonify({'success': False, 'error': 'Not found'}), 404

                if pm['review_status'] == 'pending':
                    return jsonify({'success': False, 'error': 'Already pending'}), 409

                # If confirmed, remove the product_matches row it created.
                if pm['review_status'] == 'confirmed' and pm['confirmed_match_id']:
                    cur.execute(
                        "DELETE FROM product_matches WHERE id = %s AND match_source = 'human_confirmed'",
                        (pm['confirmed_match_id'],),
                    )

                cur.execute(
                    """
                    UPDATE possible_matches
                       SET review_status      = 'pending',
                           reviewed_at        = NULL,
                           reviewer_notes     = NULL,
                           confirmed_match_id = NULL,
                           updated_at         = CURRENT_TIMESTAMP
                     WHERE id = %s
                    """,
                    (pm_id,),
                )

        return jsonify({'success': True})

    except Exception:
        log.exception("Admin route error")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ---------------------------------------------------------------------------
# Stats API
# ---------------------------------------------------------------------------

@admin_bp.route('/api/stats')
@require_admin
def api_stats():
    """Return counts of pending / confirmed / rejected rows."""
    try:
        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE review_status = 'pending')    AS pending,
                    COUNT(*) FILTER (WHERE review_status = 'confirmed')  AS confirmed,
                    COUNT(*) FILTER (WHERE review_status = 'rejected')   AS rejected,
                    COUNT(*) FILTER (WHERE review_status = 'superseded') AS superseded
                FROM possible_matches
            """)
            row = cur.fetchone()

        return jsonify({'success': True, **dict(row)})

    except Exception:
        log.exception("Admin route error")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
