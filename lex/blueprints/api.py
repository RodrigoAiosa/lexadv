"""Endpoints JSON usados pelo JavaScript (chat e contador de notificações)."""
import uuid

from flask import Blueprint, abort, jsonify, request
from postgrest.exceptions import APIError

from .. import services
from ..auth import current_user, get_db, login_required
from ..utils import db_error_message

bp = Blueprint("api", __name__, url_prefix="/api")


def _case_uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        abort(404)


def _serialize(message, uid):
    return {
        "id": message["id"],
        "body": message["body"],
        "created_at": message["created_at"],
        "mine": message["sender_id"] == uid,
    }


@bp.route("/casos/<case_id>/mensagens", methods=["GET"])
@login_required
def list_messages(case_id):
    case_id = _case_uuid(case_id)
    uid = current_user()["id"]
    client = get_db()
    try:
        messages = services.list_messages(client, case_id, request.args.get("after"))
        if any(m["sender_id"] != uid and not m["read_at"] for m in messages):
            services.mark_messages_read(client, case_id, uid)
    except APIError as exc:
        return jsonify(error=db_error_message(exc)), 400
    return jsonify(messages=[_serialize(m, uid) for m in messages])


@bp.route("/casos/<case_id>/mensagens", methods=["POST"])
@login_required
def send_message(case_id):
    case_id = _case_uuid(case_id)
    body = ((request.get_json(silent=True) or {}).get("body") or "").strip()
    if not 1 <= len(body) <= 5000:
        return jsonify(error="A mensagem deve ter entre 1 e 5000 caracteres."), 400
    try:
        message = services.send_message(get_db(), case_id, current_user()["id"], body)
    except APIError:
        return jsonify(error="Não foi possível enviar: o chat só funciona após um advogado assumir o caso."), 403
    return jsonify(message=_serialize(message, current_user()["id"])), 201


@bp.route("/notificacoes/contagem")
@login_required
def notifications_count():
    try:
        return jsonify(unread=services.count_unread_notifications(get_db()))
    except APIError:
        return jsonify(unread=0)
