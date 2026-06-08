"""
Flask backend for price comparison web application.
"""
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from extensions import limiter

# Import blueprints
from api.groups import groups_bp
from api.search import search_bp
from api.categories import categories_bp
from api.vendors import vendors_bp
from api.stats import stats_bp
from admin import admin_bp


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Accept /api/groups and /api/groups/ interchangeably — the frontend
    # calls routes without trailing slashes; Flask's default 308 redirects
    # cause issues with Vite proxy and some fetch clients.
    app.url_map.strict_slashes = False

    # Rate limiting
    limiter.init_app(app)

    # Enable CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": Config.CORS_ORIGINS,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Register blueprints
    app.register_blueprint(groups_bp,     url_prefix='/api/groups')
    app.register_blueprint(search_bp,     url_prefix='/api/search')
    app.register_blueprint(categories_bp, url_prefix='/api/categories')
    app.register_blueprint(vendors_bp,    url_prefix='/api/vendors')
    app.register_blueprint(stats_bp,      url_prefix='/api/stats')

    # Admin review UI — mounted at /admin/, intentionally outside the /api/* CORS scope.
    # Protected by HTTP Basic Auth (ADMIN_USER / ADMIN_PASSWORD env vars).
    app.register_blueprint(admin_bp)

    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'success': True,
            'message': 'Backend API is running',
            'version': '1.0.0'
        })

    # Root endpoint
    @app.route('/', methods=['GET'])
    def root():
        return jsonify({
            'name': 'Price Comparison API',
            'version': '1.0.0',
            'endpoints': {
                'health': '/api/health',
                'groups': '/api/groups',
                'search': '/api/search',
                'categories': '/api/categories',
                'vendors': '/api/vendors',
                'stats': '/api/stats',
            }
        })

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
