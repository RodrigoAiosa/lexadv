import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lex import create_app, db  # noqa: E402
from lex.config import TestConfig  # noqa: E402

from .fakes import FakeDB  # noqa: E402

CLIENT_ID = "11111111-1111-4111-8111-111111111111"
LAWYER_ID = "22222222-2222-4222-8222-222222222222"
ADMIN_ID = "33333333-3333-4333-8333-333333333333"
CASE_ID = "44444444-4444-4444-8444-444444444444"

PEOPLE = {
    "cliente": (CLIENT_ID, "Maria Souza"),
    "advogado": (LAWYER_ID, "Dr. João Lima"),
    "admin": (ADMIN_ID, "Admin LEX"),
}


@pytest.fixture
def fake(monkeypatch):
    fake_db = FakeDB()
    fake_db.seed(
        "legal_areas",
        {"id": 1, "slug": "trabalhista", "name": "Direito Trabalhista", "description": "Rescisão", "is_active": True},
        {"id": 2, "slug": "civil", "name": "Direito Civil", "description": "Contratos", "is_active": True},
    )
    monkeypatch.setattr(db, "anon_client", lambda: fake_db)
    monkeypatch.setattr(db, "user_client", lambda _token: fake_db)
    return fake_db


@pytest.fixture
def app(fake):
    return create_app(TestConfig)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    def _login(role):
        uid, name = PEOPLE[role]
        with client.session_transaction() as sess:
            sess["access_token"] = "tok"
            sess["refresh_token"] = "ref"
            sess["expires_at"] = time.time() + 3600
            sess["user"] = {"id": uid, "email": f"{role}@teste.com", "role": role, "full_name": name}
        return uid

    return _login


def make_case(**overrides):
    case = {
        "id": CASE_ID,
        "protocol": "LEX-2026-000001",
        "client_id": CLIENT_ID,
        "area_id": 1,
        "title": "Rescisão sem pagamento",
        "description": "Fui demitido sem justa causa e não recebi as verbas.",
        "urgency": "alta",
        "status": "em_andamento",
        "assigned_lawyer_id": LAWYER_ID,
        "city": "São Paulo",
        "state": "SP",
        "estimated_value": "15000.00",
        "opposing_party": "Empresa X",
        "desired_outcome": "Receber verbas",
        "is_online_ok": True,
        "created_at": "2026-11-06T22:00:00+00:00",
        "legal_areas": {"name": "Direito Trabalhista"},
        "lawyers": {
            "profile_id": LAWYER_ID, "oab_number": "123456", "oab_state": "SP", "avg_rating": 4.5,
            "profiles": {"full_name": "Dr. João Lima"},
        },
    }
    case.update(overrides)
    return case
