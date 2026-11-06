"""Área do advogado: painel, perfil profissional e resposta às oportunidades."""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from postgrest.exceptions import APIError

from .. import services
from ..auth import current_user, get_db, role_required
from ..constants import STATES
from ..utils import db_error_message, parse_decimal, parse_int

bp = Blueprint("lawyer", __name__, url_prefix="/advogado")

OAB_RE = re.compile(r"^[0-9]{1,7}[A-Z]?$")


@bp.route("/")
@role_required("advogado")
def dashboard():
    client = get_db()
    uid = current_user()["id"]
    lawyer = services.get_lawyer(client, uid)
    if lawyer is None:
        flash("Complete seu perfil profissional (OAB e especialidades) para receber solicitações.", "info")
        return redirect(url_for("lawyer.profile"))
    matches = services.list_pending_matches(client, uid) if lawyer["verification_status"] == "verificado" else []
    cases = services.list_lawyer_cases(client, uid)
    return render_template("lawyer/dashboard.html", lawyer=lawyer, matches=matches, cases=cases)


@bp.route("/perfil", methods=["GET", "POST"])
@role_required("advogado")
def profile():
    client = get_db()
    uid = current_user()["id"]
    lawyer = services.get_lawyer(client, uid)
    areas = services.list_areas(client)
    valid_areas = {a["id"] for a in areas}
    selected = {s["area_id"] for s in (lawyer or {}).get("lawyer_specialties", [])}
    primary = next((s["area_id"] for s in (lawyer or {}).get("lawyer_specialties", []) if s["is_primary"]), None)

    if request.method == "POST":
        form = request.form
        errors = []
        area_ids = sorted({a for a in (parse_int(x) for x in form.getlist("areas")) if a in valid_areas})
        primary_area = parse_int(form.get("primary_area"))
        if not area_ids:
            errors.append("Selecione ao menos uma área de atuação.")
        if primary_area not in area_ids:
            primary_area = area_ids[0] if area_ids else None
        state = form.get("state", "").strip().upper() or None
        if state and state not in STATES:
            errors.append("Estado inválido.")
        years = parse_int(form.get("years_experience")) if form.get("years_experience") else None
        if years is not None and years < 0:
            errors.append("Anos de experiência inválido.")
        rate = parse_decimal(form.get("hourly_rate"))
        data = {
            "bio": form.get("bio", "").strip() or None,
            "years_experience": years,
            "hourly_rate": str(rate) if rate is not None else None,
            "city": form.get("city", "").strip() or None,
            "state": state,
            "accepts_online": bool(form.get("accepts_online")),
        }
        if lawyer is None:
            oab_number = form.get("oab_number", "").strip().upper()
            oab_state = form.get("oab_state", "").strip().upper()
            if not OAB_RE.match(oab_number):
                errors.append("Número da OAB inválido (ex.: 123456).")
            if oab_state not in STATES:
                errors.append("Selecione o estado da sua inscrição na OAB.")
            data.update({"oab_number": oab_number, "oab_state": oab_state})
        else:
            data["is_available"] = bool(form.get("is_available"))
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "lawyer/profile.html", lawyer=lawyer, areas=areas, form=form,
                selected={int(x) for x in form.getlist("areas") if x.isdigit()}, primary=primary_area,
            ), 400
        try:
            services.save_lawyer(client, uid, data, area_ids, primary_area, creating=lawyer is None)
        except APIError as exc:
            message = db_error_message(exc)
            if "duplicate" in message.lower() or "já existe" in message:
                message = "Já existe um advogado cadastrado com esta inscrição na OAB."
            flash(message, "error")
            return render_template("lawyer/profile.html", lawyer=lawyer, areas=areas, form=form,
                                   selected=set(area_ids), primary=primary_area), 400
        flash("Perfil salvo. Sua inscrição na OAB será analisada pela equipe do LEX." if lawyer is None
              else "Perfil atualizado.", "success")
        return redirect(url_for("lawyer.dashboard"))

    form = {}
    if lawyer:
        form = {k: ("" if v is None else v) for k, v in lawyer.items() if k != "lawyer_specialties"}
        form["accepts_online"] = "1" if lawyer["accepts_online"] else ""
        form["is_available"] = "1" if lawyer["is_available"] else ""
    else:
        form = {"accepts_online": "1"}
    return render_template("lawyer/profile.html", lawyer=lawyer, areas=areas, form=form,
                           selected=selected, primary=primary)


@bp.route("/oportunidades/<match_id>/responder", methods=["POST"])
@role_required("advogado")
def respond(match_id):
    action = request.form.get("action")
    status = {"aceitar": "aceito", "recusar": "recusado"}.get(action)
    if not status:
        flash("Ação inválida.", "error")
        return redirect(url_for("lawyer.dashboard"))
    case_id = request.form.get("case_id")
    try:
        rows = services.respond_match(get_db(), match_id, status, request.form.get("reason", "").strip() or None)
    except APIError as exc:
        flash(db_error_message(exc), "error")
        return redirect(url_for("lawyer.dashboard"))
    if not rows:
        flash("Esta oportunidade não está mais disponível.", "warning")
        return redirect(url_for("lawyer.dashboard"))
    if status == "aceito":
        flash("Você assumiu esta solicitação. Entre em contato com o cliente pelo chat.", "success")
        return redirect(url_for("cases.detail", case_id=case_id) if case_id else url_for("lawyer.dashboard"))
    flash("Solicitação recusada.", "info")
    return redirect(url_for("lawyer.dashboard"))
