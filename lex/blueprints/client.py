"""Área do cliente: painel e criação de solicitações."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from postgrest.exceptions import APIError

from .. import services
from ..auth import current_user, get_db, role_required
from ..constants import STATES, URGENCY
from ..utils import db_error_message, parse_decimal, parse_int

bp = Blueprint("client", __name__, url_prefix="/cliente")


@bp.route("/")
@role_required("cliente")
def dashboard():
    cases = services.list_client_cases(get_db(), current_user()["id"])
    active = [c for c in cases if c["status"] in ("aberto", "aguardando_advogado", "em_andamento")]
    return render_template("client/dashboard.html", cases=cases, active_count=len(active))


@bp.route("/solicitacoes/nova", methods=["GET", "POST"])
@role_required("cliente")
def new_case():
    client = get_db()
    areas = services.list_areas(client)
    if request.method == "POST":
        form = request.form
        area_id = parse_int(form.get("area_id"))
        title = form.get("title", "").strip()
        description = form.get("description", "").strip()
        urgency = form.get("urgency", "media")
        state = form.get("state", "").strip().upper() or None
        errors = []
        if area_id not in {a["id"] for a in areas}:
            errors.append("Escolha a área do direito da sua solicitação.")
        if not 5 <= len(title) <= 200:
            errors.append("O título deve ter entre 5 e 200 caracteres.")
        if len(description) < 20:
            errors.append("Descreva o problema com pelo menos 20 caracteres.")
        if urgency not in URGENCY:
            errors.append("Urgência inválida.")
        if state and state not in STATES:
            errors.append("Estado inválido.")
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("client/new_case.html", areas=areas, form=form), 400

        payload = {
            "client_id": current_user()["id"],
            "area_id": area_id,
            "title": title,
            "description": description,
            "urgency": urgency,
            "city": form.get("city", "").strip() or None,
            "state": state,
            "opposing_party": form.get("opposing_party", "").strip() or None,
            "desired_outcome": form.get("desired_outcome", "").strip() or None,
            "is_online_ok": bool(form.get("is_online_ok")),
        }
        value = parse_decimal(form.get("estimated_value"))
        if value is not None:
            payload["estimated_value"] = str(value)
        try:
            case = services.create_case(client, payload)
        except APIError as exc:
            flash(db_error_message(exc), "error")
            return render_template("client/new_case.html", areas=areas, form=form), 400
        flash("Solicitação enviada! Já estamos direcionando para advogados da área.", "success")
        return redirect(url_for("cases.detail", case_id=case["id"]))
    return render_template("client/new_case.html", areas=areas, form={"is_online_ok": "1"})
