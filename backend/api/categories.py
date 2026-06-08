"""
Category API endpoints.

GET /api/categories  — list all categories with group counts from v_product_groups.

The /<slug>/products route has been intentionally removed.
Category-filtered browsing is handled by GET /api/groups?kategorija=<slug>.
"""
from flask import Blueprint, jsonify
from database import get_db

categories_bp = Blueprint('categories', __name__)


@categories_bp.route('/', methods=['GET'])
def get_categories():
    """
    Return all categories that have at least one available product group,
    ordered by their defined sort_order.

    Counts come from v_product_groups so they reflect matched groups +
    singletons (not raw individual store products).
    """
    try:
        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.name,
                    c.display_name,
                    c.slug,
                    c.sort_order,
                    COUNT(vg.group_id) AS product_count
                FROM categories c
                LEFT JOIN v_product_groups vg ON vg.category_slug = c.slug
                GROUP BY c.id, c.name, c.display_name, c.slug, c.sort_order
                HAVING COUNT(vg.group_id) > 0
                ORDER BY c.sort_order ASC
            """)

            categories = [dict(row) for row in cur.fetchall()]

        return jsonify({'success': True, 'data': categories})

    except Exception:
        return jsonify({'success': False, 'error': 'Interna greška poslužitelja'}), 500
