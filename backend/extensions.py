"""
Shared Flask extensions — imported by both app.py and individual blueprints.

Defining extensions here avoids circular imports: blueprints import from
extensions, app.py imports from extensions and calls init_app().
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri="memory://",
)
