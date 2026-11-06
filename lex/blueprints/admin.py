"""Área administrativa: verificação da inscrição dos advogados (OAB)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from postgrest.exceptions import APIError

from .. import services
from ..auth import get_db, role_required
from ..utils import db_error_message

bp = Blueprint("admin", __name__, url_prefix="/admin")

STATUS_BY_ACTION = {"verificar": "verificado", "rejeitar": "rejeitado", "suspender": "suspenso"}


@bp.route("/")
@role_required("admin")
def dashboard():
    lawyers = services.list_lawyers_admin(get_db())
    pending = [lw for lw in lawyers if lw["verification_status"] == "pendente"]
    others = [lw for lw in lawyers if lw["verification_status"] != "pendente"]
    return render_template("admin/dashboard.html", pending=pending, others=others)


@bp.route("/advogados/<lawyer_id>/verificacao", methods=["POST"])
@role_required("admin")
def set_verification(lawyer_id):
    status = STATUS_BY_ACTION.get(request.form.get("action"))
    if not status:
        flash("Ação inválida.", "error")
        return redirect(url_for("admin.dashboard"))
    try:
        services.set_lawyer_verification(get_db(), lawyer_id, status)
    except APIError as exc:
        flash(db_error_message(exc), "error")
    else:
        flash("Status do advogado atualizado.", "success")
    return redirect(url_for("admin.dashboard"))
