"""Autenticação (Supabase Auth) e controle de acesso por papel."""
import time
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from supabase import AuthApiError

from . import db, places, services
from .constants import STATES
from .utils import OAB_RE, clean_phone, normalize_oab, valid_email

bp = Blueprint("auth", __name__)

REGISTER_ROLES = ("cliente", "advogado")


# ---------- helpers ----------
def current_user():
    return session.get("user")


def get_db():
    """Cliente Supabase da requisição atual (autenticado se houver sessão)."""
    if "db" not in g:
        token = session.get("access_token")
        g.db = db.user_client(token) if token else db.anon_client()
    return g.db


def safe_next(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def home_for(role):
    return {"cliente": "client.dashboard", "advogado": "lawyer.dashboard", "admin": "admin.dashboard"}.get(
        role, "main.index"
    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Entre na sua conta para continuar.", "info")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user()["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _store_session(auth_session, user_id, email, profile):
    session.clear()
    session.permanent = True
    session["access_token"] = auth_session.access_token
    session["refresh_token"] = auth_session.refresh_token
    session["expires_at"] = auth_session.expires_at
    session["user"] = {
        "id": user_id,
        "email": email,
        "role": (profile or {}).get("role", "cliente"),
        "full_name": (profile or {}).get("full_name", ""),
    }


@bp.before_app_request
def refresh_token_if_needed():
    """Renova o JWT do Supabase pouco antes de expirar."""
    if request.endpoint == "static" or "access_token" not in session:
        return None
    if (session.get("expires_at") or 0) - time.time() > 60:
        return None
    try:
        res = db.anon_client().auth.refresh_session(session["refresh_token"])
        new = res.session
        session["access_token"] = new.access_token
        session["refresh_token"] = new.refresh_token
        session["expires_at"] = new.expires_at
    except Exception:  # noqa: BLE001 - qualquer falha de renovação encerra a sessão
        session.clear()
        flash("Sua sessão expirou. Entre novamente.", "warning")
        return redirect(url_for("auth.login"))
    return None


# ---------- rotas ----------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for(home_for(current_user()["role"])))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Informe e-mail e senha.", "error")
            return render_template("auth/login.html"), 400
        try:
            res = db.anon_client().auth.sign_in_with_password({"email": email, "password": password})
        except AuthApiError as exc:
            if "not confirmed" in str(exc).lower():
                flash("Confirme seu e-mail antes de entrar. Verifique sua caixa de entrada.", "warning")
            else:
                flash("E-mail ou senha inválidos.", "error")
            return render_template("auth/login.html"), 401
        profile = services.get_profile(db.user_client(res.session.access_token), res.user.id)
        _store_session(res.session, res.user.id, res.user.email, profile)
        target = safe_next(request.args.get("next")) or url_for(home_for(session["user"]["role"]))
        return redirect(target)
    return render_template("auth/login.html")


@bp.route("/cadastro", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for(home_for(current_user()["role"])))
    preset = request.args.get("perfil") if request.args.get("perfil") in REGISTER_ROLES else "cliente"
    if request.method == "POST":
        form = request.form
        role = form.get("role")
        name = form.get("full_name", "").strip()
        email = form.get("email", "").strip().lower()
        phone_raw = form.get("phone", "").strip()
        phone = clean_phone(phone_raw) if phone_raw else ""
        password = form.get("password", "")
        state = form.get("state", "").strip().upper()
        city = " ".join(form.get("city", "").split())
        oab_number = normalize_oab(form.get("oab_number", ""))
        oab_state = form.get("oab_state", "").strip().upper()
        errors = []
        if role not in REGISTER_ROLES:
            errors.append("Escolha se você é cliente ou advogado.")
        if len(name) < 3:
            errors.append("Informe seu nome completo.")
        if not valid_email(email):
            errors.append("Informe um e-mail válido, como nome@dominio.com.br.")
        if phone is None:
            errors.append("Informe um telefone válido com DDD, como (11) 91234-5678, ou deixe em branco.")
        if state not in STATES:
            errors.append("Selecione o seu estado.")
        city_ok = places.canonical_city(state, city) if state in STATES else None
        if state in STATES and not city_ok:
            errors.append("Escolha uma cidade da lista do estado selecionado.")
        city = city_ok or city
        if role == "advogado":
            if not OAB_RE.match(oab_number):
                errors.append("Informe o número da sua OAB (somente números, ex.: 123456).")
            if oab_state not in STATES:
                errors.append("Selecione o estado da sua inscrição na OAB.")
        if len(password) < 8:
            errors.append("A senha deve ter pelo menos 8 caracteres.")
        if password != form.get("password_confirm", ""):
            errors.append("As senhas não conferem.")
        if not form.get("terms"):
            errors.append("É necessário aceitar os termos de uso e a política de privacidade.")
        if errors:
            for message in errors:
                flash(message, "error")
            cities = places.cities_for(state)
            return render_template("auth/register.html", preset=role or preset, form=form, cities=cities), 400

        meta = {"role": role, "full_name": name, "phone": phone, "state": state, "city": city}
        if role == "advogado":
            meta.update({"oab_number": oab_number, "oab_state": oab_state})
        options = {"data": meta}
        site = current_app.config.get("SITE_URL")
        if site:
            options["email_redirect_to"] = f"{site}/login"
        try:
            res = db.anon_client().auth.sign_up({"email": email, "password": password, "options": options})
        except AuthApiError as exc:
            if "database error" in exc.message.lower():
                message = "Verifique os dados informados (a OAB pode já estar cadastrada) e tente de novo."
            else:
                message = exc.message
            flash(f"Não foi possível concluir o cadastro: {message}", "error")
            cities = places.cities_for(state)
            return render_template("auth/register.html", preset=role, form=form, cities=cities), 400

        if res.session:  # confirmação de e-mail desligada no Supabase: já entra logado
            profile = services.get_profile(db.user_client(res.session.access_token), res.user.id)
            _store_session(res.session, res.user.id, res.user.email, profile)
            flash("Conta criada com sucesso! Bem-vindo(a) ao LEX.", "success")
            return redirect(url_for(home_for(role)))
        flash("Conta criada! Enviamos um e-mail de confirmação — confirme para poder entrar.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", preset=preset, form={})


@bp.route("/esqueci-senha", methods=["GET", "POST"])
def forgot_password():
    if current_user():
        return redirect(url_for(home_for(current_user()["role"])))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not valid_email(email):
            flash("Informe um e-mail válido, como nome@dominio.com.br.", "error")
            return render_template("auth/forgot_password.html", email=email), 400
        site = current_app.config.get("SITE_URL") or request.url_root.rstrip("/")
        try:
            db.anon_client(flow_type="implicit").auth.reset_password_for_email(
                email, {"redirect_to": f"{site}/redefinir-senha"}
            )
        except AuthApiError as exc:
            if exc.status == 429:
                flash("Muitos pedidos seguidos. Aguarde alguns minutos e tente de novo.", "warning")
                return render_template("auth/forgot_password.html", email=email), 429
            current_app.logger.warning("reset_password_for_email falhou: %s", exc)
        # Mesma resposta exista ou não a conta: não revela quais e-mails estão cadastrados.
        flash("Se esse e-mail estiver cadastrado, enviamos um link para criar uma nova senha.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", email="")


@bp.route("/redefinir-senha", methods=["GET", "POST"])
def reset_password():
    """Destino do link do e-mail. O token chega no fragmento (#) da URL; o JavaScript o põe no formulário."""
    if request.method == "POST":
        token = request.form.get("access_token", "").strip()
        password = request.form.get("password", "")
        error = None
        if not token:
            error = "Link inválido. Peça um novo link de recuperação."
        elif len(password) < 8:
            error = "A senha deve ter pelo menos 8 caracteres."
        elif password != request.form.get("password_confirm", ""):
            error = "As senhas não conferem."
        if error:
            flash(error, "error")
            return render_template("auth/reset_password.html", token=token), 400
        ok, message = db.update_password(token, password)
        if not ok:
            flash(message, "error")
            return render_template("auth/reset_password.html", token=token), 400
        session.clear()
        flash("Senha alterada! Entre com a nova senha.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html")


@bp.route("/sair", methods=["POST"])
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("main.index"))
