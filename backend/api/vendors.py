"""
Vendor/Source API endpoints.
"""
from flask import Blueprint, jsonify
from database import get_db

vendors_bp = Blueprint('vendors', __name__)


@vendors_bp.route('/', methods=['GET'])
def get_vendors():
    """Get all vendors/sources."""
    try:
        db = get_db()
        db.initialize_pool()

        with db.get_cursor() as cur:
            cur.execute("""
                SELECT
                    s.id,
                    s.name,
                    s.display_name,
                    s.website_url,
                    s.logo_url,
                    s.is_active,
                    COUNT(p.id) as product_count
                FROM sources s
                LEFT JOIN products p ON s.id = p.source_id AND p.is_available = true AND p.price > 0
                WHERE s.is_active = true
                GROUP BY s.id, s.name, s.display_name, s.website_url, s.logo_url, s.is_active
                ORDER BY s.display_name ASC
            """)

            vendors = cur.fetchall()

        return jsonify({
            'success': True,
            'data': vendors
        })

    except Exception:
        return jsonify({'success': False, 'error': 'Interna greška poslužitelja'}), 500
