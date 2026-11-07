"""LEX — plataforma que conecta clientes a advogados especialistas."""
from dotenv import load_dotenv

load_dotenv()  # precisa rodar antes de importar a config, que lê as variáveis ao carregar

from flask import Flask, render_template  # noqa: E402
from flask_wtf.csrf import CSRFError, CSRFProtect  # noqa: E402

from . import constants, utils  # noqa: E402
from .config import INSECURE_DEFAULT_KEY, Config  # noqa: E402

csrf = CSRFProtect()


def create_app(config_object=None):
    """Cria e configura o app (usado pelos testes)."""
    app = Flask(__name__, template_folder="../templates", static_folder="../public/static")
    return configure_app(app, config_object)


def configure_app(app, config_object=None):
    """Aplica configuração, extensões, blueprints e tratadores de erro a um Flask já criado.

    Em `app.py` o objeto Flask é criado explicitamente (a Vercel só reconhece o app assim) e passa por aqui.
    """
    app.config.from_object(config_object or Config)

    if app.config["APP_ENV"] == "production" and not app.testing:
        if app.config["SECRET_KEY"] == INSECURE_DEFAULT_KEY:
            raise RuntimeError("Defina a variável de ambiente SECRET_KEY em produção.")
        if not app.config["SUPABASE_URL"] or not app.config["SUPABASE_KEY"]:
            raise RuntimeError("Defina SUPABASE_URL e SUPABASE_KEY.")

    csrf.init_app(app)

    from . import auth
    from .blueprints import admin, api, cases, client, lawyer, main

    for module in (main, auth, client, lawyer, cases, api, admin):
        app.register_blueprint(module.bp)

    app.add_template_filter(utils.datebr, "datebr")
    app.add_template_filter(utils.money, "money")
    app.add_template_filter(utils.filesize, "filesize")

    @app.context_processor
    def inject_globals():
        return {"user": auth.current_user(), "L": constants, "STATES": constants.STATES}

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        message = "Sessão do formulário expirada. Recarregue a página e tente de novo."
        return render_template("error.html", code=400, message=message), 400

    @app.errorhandler(403)
    def forbidden(error):
        message = "Você não tem permissão para acessar esta página."
        return render_template("error.html", code=403, message=message), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="Página não encontrada."), 404

    @app.errorhandler(413)
    def too_large(error):
        message = "O arquivo enviado é grande demais (máximo de 20 MB)."
        return render_template("error.html", code=413, message=message), 413

    @app.errorhandler(500)
    def server_error(error):
        message = "Algo deu errado do nosso lado. Tente novamente em instantes."
        return render_template("error.html", code=500, message=message), 500

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    return app
