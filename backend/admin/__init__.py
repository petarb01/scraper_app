"""Admin blueprint — human review UI for product match candidates."""
from flask import Blueprint

admin_bp = Blueprint(
    'admin',
    __name__,
    template_folder='templates',
    url_prefix='/admin',
)

from . import routes  # noqa: F401, E402 — registers routes with the blueprint
