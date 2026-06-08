"""HTTP Basic Auth decorator for all admin routes."""
import os
import secrets
from functools import wraps
from flask import request, Response

_CHALLENGE = {'WWW-Authenticate': 'Basic realm="Price Scraper Admin"'}


def require_admin(f):
    """Decorator that enforces HTTP Basic Auth on an admin route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Read at request time so Docker env vars and load_dotenv both work.
        admin_user     = os.getenv('ADMIN_USER', 'admin')
        admin_password = os.getenv('ADMIN_PASSWORD', '')

        if not admin_password:
            return Response('Admin credentials not configured.', 503)

        auth = request.authorization
        if not auth:
            return Response('Admin access required.', 401, _CHALLENGE)

        # Constant-time comparison prevents timing-based username/password enumeration.
        user_ok = secrets.compare_digest(auth.username, admin_user)
        pass_ok = secrets.compare_digest(auth.password, admin_password)
        if not (user_ok and pass_ok):
            return Response('Admin access required.', 401, _CHALLENGE)

        return f(*args, **kwargs)
    return decorated
