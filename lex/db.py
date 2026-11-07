"""Fábrica de clientes Supabase.

Cada requisição usa um cliente autenticado com o JWT do próprio usuário, assim as regras de
RLS do banco (BD_LEX) são sempre aplicadas: o Flask nunca usa a service_role.
"""
import httpx
from flask import current_app

from supabase import ClientOptions, create_client


def _options(token: str | None = None, flow_type: str = "pkce") -> ClientOptions:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return ClientOptions(
        headers=headers, auto_refresh_token=False, persist_session=False, flow_type=flow_type
    )


def anon_client(flow_type: str = "pkce"):
    """Cliente sem usuário (cadastro, login e leitura pública das áreas do direito).

    `flow_type="implicit"` é usado na recuperação de senha: o servidor não guarda estado entre as
    requisições, então o fluxo PKCE (que precisa lembrar um verificador) não funcionaria.
    """
    return create_client(
        current_app.config["SUPABASE_URL"],
        current_app.config["SUPABASE_KEY"],
        options=_options(flow_type=flow_type),
    )


def user_client(access_token: str):
    """Cliente que age em nome do usuário logado (RLS aplicada)."""
    return create_client(
        current_app.config["SUPABASE_URL"],
        current_app.config["SUPABASE_KEY"],
        options=_options(access_token),
    )


def update_password(access_token: str, password: str) -> tuple[bool, str]:
    """Define a nova senha com o token do link de recuperação. Devolve (ok, mensagem de erro)."""
    try:
        res = httpx.put(
            f"{current_app.config['SUPABASE_URL']}/auth/v1/user",
            headers={
                "apikey": current_app.config["SUPABASE_KEY"],
                "Authorization": f"Bearer {access_token}",
            },
            json={"password": password},
            timeout=15,
        )
    except httpx.HTTPError:
        return False, "Não foi possível falar com o servidor agora. Tente de novo em instantes."
    if res.status_code == 200:
        return True, ""
    if res.status_code in (401, 403):
        return False, "Este link expirou ou já foi usado. Peça um novo link de recuperação."
    try:
        detail = res.json().get("msg") or res.json().get("message") or ""
    except ValueError:
        detail = ""
    if "different from the old" in detail.lower():
        return False, "A nova senha precisa ser diferente da senha atual."
    if "password" in detail.lower():
        return False, "Escolha uma senha mais forte (mínimo de 8 caracteres)."
    return False, "Não foi possível alterar a senha. Tente de novo."
