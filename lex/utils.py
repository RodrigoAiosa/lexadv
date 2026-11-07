"""Utilitários: formatação, validação e tratamento de erros do Supabase."""
import re
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


OAB_RE = re.compile(r"^[0-9]{1,7}[A-Z]?$")


def normalize_oab(value: str) -> str:
    """Normaliza o número da OAB: maiúsculas, sem pontos, espaços ou traços."""
    return re.sub(r"[\s.\-]", "", (value or "")).upper()


# E-mail: parte local e domínio só com caracteres comuns, domínio com ponto e TLD alfabético
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
EMAIL_MAX = 254

# DDDs em uso no Brasil
VALID_DDDS = frozenset(
    "11 12 13 14 15 16 17 18 19 21 22 24 27 28 31 32 33 34 35 37 38 41 42 43 44 45 46 47 48 49 "
    "51 53 54 55 61 62 63 64 65 66 67 68 69 71 73 74 75 77 79 "
    "81 82 83 84 85 86 87 88 89 91 92 93 94 95 96 97 98 99".split()
)


def valid_email(value: str) -> bool:
    return bool(value) and len(value) <= EMAIL_MAX and bool(EMAIL_RE.match(value)) and ".." not in value


def clean_phone(value: str) -> str | None:
    """Telefone brasileiro (com DDD) no formato (11) 91234-5678 ou (11) 1234-5678.

    Aceita digitado com ou sem máscara e com +55 na frente. Devolve None se for inválido.
    """
    digits = re.sub(r"\D", "", value or "")
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]
    if len(digits) not in (10, 11) or digits[:2] not in VALID_DDDS:
        return None
    number = digits[2:]
    if len(number) == 9 and number[0] != "9":  # celular tem 9 dígitos e começa com 9
        return None
    if len(number) == 8 and number[0] not in "2345":  # fixo tem 8 dígitos e começa com 2 a 5
        return None
    return f"({digits[:2]}) {number[:-4]}-{number[-4:]}"
