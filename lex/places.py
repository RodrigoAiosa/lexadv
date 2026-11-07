"""Municípios por estado (base do IBGE embutida no projeto), para validar e listar cidades sem depender de rede."""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data" / "municipios.json"


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).lower().split())


@lru_cache(maxsize=1)
def _load() -> dict:
    with _DATA.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    return {uf: (tuple(names), {_norm(n): n for n in names}) for uf, names in raw.items()}


def cities_for(uf: str) -> list[str]:
    """Lista de cidades do estado (vazia se a UF for inválida)."""
    entry = _load().get((uf or "").upper())
    return list(entry[0]) if entry else []


def canonical_city(uf: str, city: str) -> str | None:
    """Nome oficial da cidade se ela pertence ao estado (ignora maiúsculas e acentos); senão None."""
    entry = _load().get((uf or "").upper())
    return entry[1].get(_norm(city)) if entry else None
