"""
routes/views.py — Rotas de páginas HTML.
"""
from flask import Blueprint, render_template
from flask_login import login_required

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
@login_required
def index():
    return render_template("index.html")
