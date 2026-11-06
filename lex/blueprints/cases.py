"""Detalhe da solicitação e todas as ações ligadas a ela (status, documentos, honorários...)."""
import uuid
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from postgrest.exceptions import APIError
from werkzeug.utils import secure_filename

from .. import services
from ..auth import current_user, get_db, login_required, role_required
from ..constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    APPOINTMENT_MODES,
    FEE_TYPES,
    MAX_UPLOAD_BYTES,
)
from ..utils import BR_TZ, db_error_message, parse_decimal, parse_int

bp = Blueprint("cases", __name__, url_prefix="/casos")


def _uuid_or_404(value):
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        abort(404)


def _load_case(case_id):
    case_id = _uuid_or_404(case_id)
    case = services.get_case(get_db(), case_id)
    if not case:
        abort(404)
    return case


def _back(case_id):
    return redirect(url_for("cases.detail", case_id=case_id))


@bp.route("/<case_id>")
@login_required
def detail(case_id):
    case = _load_case(case_id)
    client = get_db()
    user = current_user()
    uid = user["id"]
    is_client = case["client_id"] == uid
    is_lawyer = case["assigned_lawyer_id"] == uid
    is_admin = user["role"] == "admin"
    pending_match = None
    if user["role"] == "advogado" and not is_lawyer:
        pending_match = services.get_case_pending_match(client, case["id"], uid)

    ctx = {
        "case": case,
        "is_client": is_client,
        "is_lawyer": is_lawyer,
        "is_admin": is_admin,
        "pending_match": pending_match,
        "events": [], "messages": [], "documents": [], "fees": [], "appointments": [], "review": None,
        "fee_types": FEE_TYPES, "appointment_modes": APPOINTMENT_MODES,
    }
    if is_client or is_lawyer or is_admin:
        ctx.update(
            events=services.list_events(client, case["id"]),
            messages=services.list_messages(client, case["id"]),
            documents=services.list_documents(client, case["id"]),
            fees=services.list_fees(client, case["id"]),
            appointments=services.list_appointments(client, case["id"]),
            review=services.get_review(client, case["id"]),
        )
        if ctx["messages"]:
            services.mark_messages_read(client, case["id"], uid)
    return render_template("cases/detail.html", **ctx)


@bp.route("/<case_id>/status", methods=["POST"])
@login_required
def set_status(case_id):
    case = _load_case(case_id)
    action = request.form.get("action")
    new_status = {"concluir": "concluido", "cancelar": "cancelado"}.get(action)
    if not new_status:
        flash("Ação inválida.", "error")
        return _back(case["id"])
    try:
        rows = services.set_case_status(get_db(), case["id"], new_status)
    except APIError as exc:
        flash(db_error_message(exc), "error")
        return _back(case["id"])
    if not rows:
        flash("Você não tem permissão para alterar esta solicitação.", "error")
    else:
        flash("Solicitação concluída." if new_status == "concluido" else "Solicitação cancelada.", "success")
    return _back(case["id"])


@bp.route("/<case_id>/rematch", methods=["POST"])
@role_required("cliente", "admin")
def rematch(case_id):
    case = _load_case(case_id)
    try:
        count = services.rematch_case(get_db(), case["id"])
    except APIError as exc:
        flash(db_error_message(exc), "error")
        return _back(case["id"])
    if count:
        flash(f"Encontramos {count} novo(s) advogado(s) para sua solicitação.", "success")
    else:
        flash("Não há novos advogados disponíveis para esta área no momento.", "info")
    return _back(case["id"])


@bp.route("/<case_id>/documentos", methods=["POST"])
@login_required
def upload_document(case_id):
    case = _load_case(case_id)
    file = request.files.get("arquivo")
    if not file or not file.filename:
        flash("Selecione um arquivo.", "error")
        return _back(case["id"])
    name = secure_filename(file.filename) or "documento"
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        flash("Formato não permitido. Envie PDF, imagem (JPG/PNG), TXT ou Word.", "error")
        return _back(case["id"])
    data = file.read()
    if not data or len(data) > MAX_UPLOAD_BYTES:
        flash("O arquivo está vazio ou excede 20 MB.", "error")
        return _back(case["id"])
    path = f"{case['id']}/{uuid.uuid4().hex}-{name}"
    mime = file.mimetype or "application/octet-stream"
    try:
        services.upload_document(
            get_db(), case["id"], current_user()["id"], path, data, mime, name,
            request.form.get("category", "").strip() or None,
        )
    except Exception as exc:  # noqa: BLE001 - Storage e PostgREST levantam exceções diferentes
        flash(db_error_message(exc) if isinstance(exc, APIError) else "Falha ao enviar o documento.", "error")
        return _back(case["id"])
    flash("Documento enviado.", "success")
    return _back(case["id"])


@bp.route("/<case_id>/documentos/<doc_id>")
@login_required
def download_document(case_id, doc_id):
    case = _load_case(case_id)
    try:
        url = services.signed_document_url(get_db(), _uuid_or_404(doc_id))
    except Exception:  # noqa: BLE001
        url = None
    if not url:
        flash("Documento indisponível.", "error")
        return _back(case["id"])
    return redirect(url)


@bp.route("/<case_id>/honorarios", methods=["POST"])
@role_required("advogado")
def propose_fee(case_id):
    case = _load_case(case_id)
    form = request.form
    fee_type = form.get("fee_type")
    amount = parse_decimal(form.get("amount"))
    percent = parse_decimal(form.get("success_percent"))
    if fee_type not in FEE_TYPES:
        flash("Escolha o tipo de honorário.", "error")
        return _back(case["id"])
    if fee_type in ("fixo", "por_hora", "misto") and amount is None:
        flash("Informe o valor dos honorários.", "error")
        return _back(case["id"])
    if fee_type in ("exito", "misto") and (percent is None or percent > 100):
        flash("Informe o percentual de êxito (0 a 100).", "error")
        return _back(case["id"])
    payload = {
        "case_id": case["id"],
        "lawyer_id": current_user()["id"],
        "fee_type": fee_type,
        "amount": str(amount) if amount is not None else None,
        "success_percent": str(percent) if percent is not None else None,
        "notes": form.get("notes", "").strip() or None,
    }
    try:
        services.propose_fee(get_db(), payload)
    except APIError as exc:
        flash(db_error_message(exc), "error")
        return _back(case["id"])
    flash("Proposta de honorários enviada ao cliente.", "success")
    return _back(case["id"])


@bp.route("/<case_id>/honorarios/<fee_id>/responder", methods=["POST"])
@role_required("cliente")
def respond_fee(case_id, fee_id):
    case = _load_case(case_id)
    status = {"aceitar": "aceita", "recusar": "recusada"}.get(request.form.get("action"))
    if not status:
        flash("Ação inválida.", "error")
        return _back(case["id"])
    try:
        rows = services.respond_fee(get_db(), _uuid_or_404(fee_id), status)
    except APIError as exc:
        flash(db_error_message(exc), "error")
        return _back(case["id"])
    flash("Resposta registrada." if rows else "Esta proposta não pode mais ser alterada.",
          "success" if rows else "warning")
    return _back(case["id"])


@bp.route("/<case_id>/agendar", methods=["POST"])
@login_required
def schedule(case_id):
    case = _load_case(case_id)
    form = request.form
    mode = form.get("mode", "online")
    try:
        when = datetime.fromisoformat(form.get("scheduled_at", "")).replace(tzinfo=BR_TZ)
    except ValueError:
        flash("Informe uma data e hora válidas.", "error")
        return _back(case["id"])
    if mode not in APPOINTMENT_MODES or when <= datetime.now(BR_TZ):
        flash("Escolha uma data futura e um formato válido.", "error")
        return _back(case["id"])
    payload = {
        "case_id": case["id"],
        "client_id": case["client_id"],
        "lawyer_id": case["assigned_lawyer_id"],
        "scheduled_at": when.isoformat(),
        "duration_minutes": parse_int(form.get("duration_minutes")) or 30,
        "mode": mode,
        "meeting_url": form.get("meeting_url", "").strip() or None,
        "notes": form.get("notes", "").strip() or None,
    }
    try:
        services.create_appointment(get_db(), payload)
    except APIError as exc:
        flash(db_error_message(exc), "error")
        return _back(case["id"])
    flash("Reunião agendada.", "success")
    return _back(case["id"])


@bp.route("/<case_id>/avaliar", methods=["POST"])
@role_required("cliente")
def review(case_id):
    case = _load_case(case_id)
    rating = parse_int(request.form.get("rating"))
    if rating not in range(1, 6):
        flash("Escolha uma nota de 1 a 5.", "error")
        return _back(case["id"])
    payload = {
        "case_id": case["id"],
        "client_id": current_user()["id"],
        "lawyer_id": case["assigned_lawyer_id"],
        "rating": rating,
        "comment": request.form.get("comment", "").strip() or None,
    }
    try:
        services.create_review(get_db(), payload)
    except APIError as exc:
        flash(db_error_message(exc), "error")
        return _back(case["id"])
    flash("Obrigado pela sua avaliação!", "success")
    return _back(case["id"])
