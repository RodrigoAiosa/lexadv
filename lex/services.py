"""Camada de acesso a dados (BD_LEX / Supabase).

Todas as funções recebem um cliente Supabase já autenticado como o usuário; quem decide o que
cada pessoa pode ver ou alterar é o RLS do banco.
"""
from datetime import datetime, timezone

from .constants import STORAGE_BUCKET


def _rows(response):
    return (response.data if response is not None else None) or []


def _first(response):
    rows = _rows(response)
    return rows[0] if rows else None


# ---------- áreas / perfis ----------
def list_areas(db):
    return _rows(
        db.table("legal_areas")
        .select("id, slug, name, description, icon")
        .eq("is_active", True)
        .order("name")
        .execute()
    )


def get_profile(db, uid):
    return _first(
        db.table("profiles").select("id, role, full_name, avatar_url").eq("id", uid).limit(1).execute()
    )


def get_lawyer(db, uid):
    return _first(
        db.table("lawyers")
        .select("*, lawyer_specialties(area_id, is_primary)")
        .eq("profile_id", uid)
        .limit(1)
        .execute()
    )


def save_lawyer(db, uid, data: dict, area_ids: list[int], primary_area: int | None, creating: bool):
    if creating:
        db.table("lawyers").insert({"profile_id": uid, **data}).execute()
    else:
        db.table("lawyers").update(data).eq("profile_id", uid).execute()
    db.table("lawyer_specialties").delete().eq("lawyer_id", uid).execute()
    if area_ids:
        db.table("lawyer_specialties").insert(
            [{"lawyer_id": uid, "area_id": a, "is_primary": a == primary_area} for a in area_ids]
        ).execute()


# ---------- solicitações ----------
CASE_LIST_COLUMNS = (
    "id, protocol, title, status, urgency, created_at, city, state, "
    "legal_areas!area_id(name), "
    "lawyers!assigned_lawyer_id(oab_number, oab_state, profiles!profile_id(full_name))"
)


def create_case(db, payload: dict):
    return _first(db.table("cases").insert(payload).execute())


def list_client_cases(db, uid):
    return _rows(
        db.table("cases")
        .select(CASE_LIST_COLUMNS)
        .eq("client_id", uid)
        .order("created_at", desc=True)
        .execute()
    )


def list_lawyer_cases(db, uid):
    return _rows(
        db.table("cases")
        .select(CASE_LIST_COLUMNS)
        .eq("assigned_lawyer_id", uid)
        .order("created_at", desc=True)
        .execute()
    )


def list_pending_matches(db, uid):
    now = datetime.now(timezone.utc).isoformat()
    return _rows(
        db.table("case_matches")
        .select(
            "id, score, expires_at, status, "
            "cases!case_id(id, protocol, title, description, urgency, city, state, created_at, "
            "legal_areas!area_id(name))"
        )
        .eq("lawyer_id", uid)
        .eq("status", "sugerido")
        .gt("expires_at", now)
        .order("score", desc=True)
        .execute()
    )


def respond_match(db, match_id, status: str, reason: str | None = None):
    payload = {"status": status}
    if reason:
        payload["decline_reason"] = reason
    return _rows(db.table("case_matches").update(payload).eq("id", match_id).execute())


def get_case(db, case_id):
    return _first(
        db.table("cases")
        .select(
            "*, legal_areas!area_id(name), "
            "lawyers!assigned_lawyer_id(profile_id, oab_number, oab_state, avg_rating, "
            "profiles!profile_id(full_name))"
        )
        .eq("id", case_id)
        .limit(1)
        .execute()
    )


def get_case_pending_match(db, case_id, uid):
    return _first(
        db.table("case_matches")
        .select("id, status, expires_at")
        .eq("case_id", case_id)
        .eq("lawyer_id", uid)
        .eq("status", "sugerido")
        .limit(1)
        .execute()
    )


def list_events(db, case_id):
    return _rows(db.table("case_events").select("*").eq("case_id", case_id).order("created_at").execute())


def list_documents(db, case_id):
    return _rows(
        db.table("case_documents")
        .select("id, file_name, size_bytes, category, created_at, uploaded_by")
        .eq("case_id", case_id)
        .order("created_at", desc=True)
        .execute()
    )


def list_fees(db, case_id):
    return _rows(
        db.table("fee_agreements").select("*").eq("case_id", case_id).order("created_at", desc=True).execute()
    )


def list_appointments(db, case_id):
    return _rows(
        db.table("appointments").select("*").eq("case_id", case_id).order("scheduled_at").execute()
    )


def get_review(db, case_id):
    return _first(db.table("reviews").select("*").eq("case_id", case_id).limit(1).execute())


def set_case_status(db, case_id, status: str):
    return _rows(db.table("cases").update({"status": status}).eq("id", case_id).execute())


def rematch_case(db, case_id):
    return db.rpc("rematch_case", {"p_case_id": case_id}).execute().data


# ---------- documentos (Storage) ----------
def upload_document(db, case_id, uid, path: str, data: bytes, mime: str, name: str, category: str | None):
    db.storage.from_(STORAGE_BUCKET).upload(path=path, file=data, file_options={"content-type": mime})
    db.table("case_documents").insert(
        {
            "case_id": case_id,
            "uploaded_by": uid,
            "file_name": name,
            "storage_path": path,
            "mime_type": mime,
            "size_bytes": len(data),
            "category": category,
        }
    ).execute()


def signed_document_url(db, doc_id, expires_in: int = 300):
    doc = _first(db.table("case_documents").select("storage_path").eq("id", doc_id).limit(1).execute())
    if not doc:
        return None
    signed = db.storage.from_(STORAGE_BUCKET).create_signed_url(doc["storage_path"], expires_in)
    return signed.get("signedURL") or signed.get("signedUrl")


# ---------- honorários, agenda, avaliação ----------
def propose_fee(db, payload: dict):
    db.table("fee_agreements").insert(payload).execute()


def respond_fee(db, fee_id, status: str):
    return _rows(db.table("fee_agreements").update({"status": status}).eq("id", fee_id).execute())


def create_appointment(db, payload: dict):
    db.table("appointments").insert(payload).execute()


def create_review(db, payload: dict):
    db.table("reviews").insert(payload).execute()


# ---------- chat ----------
def list_messages(db, case_id, after: str | None = None):
    query = db.table("case_messages").select("id, body, sender_id, created_at, read_at").eq("case_id", case_id)
    if after:
        query = query.gt("created_at", after)
    return _rows(query.order("created_at").execute())


def send_message(db, case_id, uid, body: str):
    return _first(
        db.table("case_messages").insert({"case_id": case_id, "sender_id": uid, "body": body}).execute()
    )


def mark_messages_read(db, case_id, uid):
    now = datetime.now(timezone.utc).isoformat()
    db.table("case_messages").update({"read_at": now}).eq("case_id", case_id).neq(
        "sender_id", uid
    ).is_("read_at", "null").execute()


# ---------- notificações ----------
def count_unread_notifications(db):
    res = db.table("notifications").select("id", count="exact").is_("read_at", "null").limit(1).execute()
    return getattr(res, "count", None) or 0


def list_notifications(db, limit: int = 50):
    return _rows(
        db.table("notifications").select("*").order("created_at", desc=True).limit(limit).execute()
    )


def mark_notifications_read(db):
    now = datetime.now(timezone.utc).isoformat()
    db.table("notifications").update({"read_at": now}).is_("read_at", "null").execute()


# ---------- administração ----------
def list_lawyers_admin(db):
    return _rows(
        db.table("lawyers")
        .select(
            "profile_id, oab_number, oab_state, city, state, verification_status, created_at, "
            "profiles!profile_id(full_name)"
        )
        .order("created_at", desc=True)
        .execute()
    )


def set_lawyer_verification(db, lawyer_id, status: str):
    db.rpc("admin_set_lawyer_verification", {"p_lawyer_id": lawyer_id, "p_status": status}).execute()
