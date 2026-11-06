"""Fábrica de clientes Supabase.

Cada requisição usa um cliente autenticado com o JWT do próprio usuário, assim as regras de
RLS do banco (BD_LEX) são sempre aplicadas: o Flask nunca usa a service_role.
"""
from flask import current_app

from supabase import ClientOptions, create_client


def _options(token: str | None = None) -> ClientOptions:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return ClientOptions(headers=headers, auto_refresh_token=False, persist_session=False)


def anon_client():
    """Cliente sem usuário (cadastro, login e leitura pública das áreas do direito)."""
    return create_client(
        current_app.config["SUPABASE_URL"], current_app.config["SUPABASE_KEY"], options=_options()
    )


def user_client(access_token: str):
    """Cliente que age em nome do usuário logado (RLS aplicada)."""
    return create_client(
        current_app.config["SUPABASE_URL"],
        current_app.config["SUPABASE_KEY"],
        options=_options(access_token),
    )
