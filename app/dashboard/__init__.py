# app/dashboard/__init__.py

from flask import Blueprint

bp = Blueprint('dashboard', __name__, template_folder='templates')

from app.dashboard import routes