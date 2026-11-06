"""Configuração da aplicação (lida de variáveis de ambiente / arquivo .env)."""
import os
from datetime import timedelta

INSECURE_DEFAULT_KEY = "dev-insecure-change-me"


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development")
    SECRET_KEY = os.environ.get("SECRET_KEY") or INSECURE_DEFAULT_KEY

    # Supabase (use a chave *publishable/anon*; nunca a service_role no front/app)
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
    # URL pública do site, usada no link de confirmação de e-mail (opcional)
    SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("APP_ENV", "development") == "production"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 21 * 1024 * 1024  # um pouco acima do limite de 20 MB do upload


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SUPABASE_URL = "https://test.supabase.co"
    SUPABASE_KEY = "test-key"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
