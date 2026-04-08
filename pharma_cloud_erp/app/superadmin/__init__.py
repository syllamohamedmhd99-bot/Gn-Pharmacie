from flask import Blueprint

bp_superadmin = Blueprint('superadmin', __name__)

from app.superadmin import routes
