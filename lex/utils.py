"""Utilitários: formatação, validação e tratamento de erros do Supabase."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from postgrest.exceptions import APIError

BR_TZ = ZoneInfo("America/Sao_Paulo")


def datebr(value, fmt="%d/%m/%Y %H:%M"):
    """Converte um timestamp ISO (UTC) para o horário de Brasília."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    return dt.astimezone(BR_TZ).strftime(fmt)


def money(value):
    if value in (None, ""):
        return "—"
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return str(value)
    text = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def filesize(value):
    if not value:
        return ""
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def parse_decimal(text, minimum=Decimal("0")):
    """Aceita '1.234,56' ou '1234.56'; devolve Decimal ou None se vazio/inválido."""
    text = (text or "").strip()
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number >= minimum else None


def parse_int(text):
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def db_error_message(exc: Exception) -> str:
    """Mensagem amigável a partir de um erro do PostgREST (inclui os `raise exception` do banco)."""
    if isinstance(exc, APIError):
        message = (exc.message or "").strip()
        if "row-level security" in message or "permission denied" in message:
            return "Você não tem permissão para realizar esta ação."
        if "duplicate key" in message:
            return "Este registro já existe."
        return message or "Não foi possível concluir a operação."
    return "Não foi possível concluir a operação. Tente novamente."
