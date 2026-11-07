"""Páginas públicas, painel e notificações."""
from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from .. import db, places, services
from ..auth import current_user, get_db, home_for, login_required

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    try:
        areas = services.list_areas(db.anon_client())
    except Exception:  # noqa: BLE001 - a home deve abrir mesmo com o banco indisponível
        areas = []
    return render_template("index.html", areas=areas)


@bp.route("/cidades/<uf>")
def cities(uf):
    """Cidades do estado (público: usado no cadastro, antes do login)."""
    items = places.cities_for(uf)
    if not items:
        return jsonify({"error": "UF inválida"}), 404
    response = jsonify(items)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@bp.route("/termos")
def terms():
    return render_template("legal/termos.html")


@bp.route("/privacidade")
def privacy():
    return render_template("legal/privacidade.html")


@bp.route("/painel")
@login_required
def painel():
    return redirect(url_for(home_for(current_user()["role"])))


@bp.route("/notificacoes", methods=["GET", "POST"])
@login_required
def notifications():
    client = get_db()
    if request.method == "POST":
        services.mark_notifications_read(client)
        return redirect(url_for("main.notifications"))
    return render_template("notifications.html", items=services.list_notifications(client))


@bp.route("/healthz")
def healthz():
    return jsonify(status="ok")
