import pytest

from lex import create_app, utils
from lex.config import INSECURE_DEFAULT_KEY, Config, TestConfig

from .conftest import ADMIN_ID, CASE_ID, CLIENT_ID, LAWYER_ID, make_case


# ---------- públicas ----------
def test_home_lists_areas(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Direito Trabalhista" in html and "Criar conta" in html


def test_healthz(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}


def test_404_page(client):
    assert client.get("/nao-existe").status_code == 404


def test_security_headers(client):
    res = client.get("/")
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["X-Content-Type-Options"] == "nosniff"


# ---------- autenticação ----------
def test_protected_routes_redirect_to_login(client):
    res = client.get("/cliente/")
    assert res.status_code == 302 and "/login" in res.headers["Location"]


def test_login_success_redirects_by_role(client, fake):
    fake.users["maria@teste.com"] = {"id": CLIENT_ID, "password": "senha1234"}
    fake.seed("profiles", {"id": CLIENT_ID, "role": "cliente", "full_name": "Maria"})
    res = client.post("/login", data={"email": "Maria@teste.com", "password": "senha1234"})
    assert res.status_code == 302 and res.headers["Location"].endswith("/cliente/")
    with client.session_transaction() as sess:
        assert sess["user"]["role"] == "cliente"


def test_login_invalid_credentials(client):
    res = client.post("/login", data={"email": "x@y.com", "password": "errada123"})
    assert res.status_code == 401
    assert "inválidos" in res.get_data(as_text=True)


def test_login_blocks_open_redirect(client, fake):
    fake.users["m@t.com"] = {"id": CLIENT_ID, "password": "senha1234"}
    fake.seed("profiles", {"id": CLIENT_ID, "role": "cliente", "full_name": "M"})
    res = client.post("/login?next=//evil.com", data={"email": "m@t.com", "password": "senha1234"})
    assert "evil.com" not in res.headers["Location"]


def test_register_validation(client):
    res = client.post("/cadastro", data={"role": "cliente", "full_name": "A", "email": "x", "password": "1"})
    assert res.status_code == 400


def test_register_cannot_choose_admin(client):
    res = client.post("/cadastro", data={
        "role": "admin", "full_name": "Fulano de Tal", "email": "f@t.com",
        "password": "senha1234", "password_confirm": "senha1234", "terms": "1",
    })
    assert res.status_code == 400


BASE_REGISTER = {
    "full_name": "Fulano de Tal", "email": "f@t.com", "phone": "11999999999", "state": "SP", "city": "São Paulo",
    "password": "senha1234", "password_confirm": "senha1234", "terms": "1",
}


def test_register_lawyer_sends_metadata_with_oab(client, fake):
    data = {**BASE_REGISTER, "role": "advogado", "oab_number": "123.456", "oab_state": "sp"}
    res = client.post("/cadastro", data=data)
    assert res.status_code == 302 and "/login" in res.headers["Location"]
    assert fake.signups[0]["options"]["data"] == {
        "role": "advogado", "full_name": "Fulano de Tal", "phone": "(11) 99999-9999", "state": "SP",
        "city": "São Paulo", "oab_number": "123456", "oab_state": "SP",
    }


def test_register_lawyer_requires_oab(client, fake):
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "advogado"})
    assert res.status_code == 400 and not fake.signups
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "advogado", "oab_number": "ABC", "oab_state": "SP"})
    assert res.status_code == 400 and not fake.signups
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "advogado", "oab_number": "123456"})
    assert res.status_code == 400 and not fake.signups


def test_register_client_needs_state_and_city_but_not_oab(client, fake):
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "cliente", "city": ""})
    assert res.status_code == 400
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "cliente", "state": "XX"})
    assert res.status_code == 400 and not fake.signups
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "cliente", "oab_number": "999"})
    assert res.status_code == 302
    assert fake.signups[0]["options"]["data"] == {
        "role": "cliente", "full_name": "Fulano de Tal", "phone": "(11) 99999-9999", "state": "SP",
        "city": "São Paulo",
    }


@pytest.mark.parametrize("email", [
    "sem-arroba.com", "a@b", "a b@c.com", "a@@c.com", "a@c..com", "açaí@dominio.com", "a@dominio.c", "@dominio.com",
])
def test_register_rejects_bad_email(client, fake, email):
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "cliente", "email": email})
    assert res.status_code == 400 and not fake.signups


@pytest.mark.parametrize("phone", [
    "123", "(00) 91234-5678", "(11) 81234-5678", "(11) 61234-5678", "abcdefghijk", "(11) 91234-56789",
])
def test_register_rejects_bad_phone(client, fake, phone):
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "cliente", "phone": phone})
    assert res.status_code == 400 and not fake.signups


@pytest.mark.parametrize("raw, expected", [
    ("(21) 98765-4321", "(21) 98765-4321"), ("21987654321", "(21) 98765-4321"),
    ("+55 21 98765-4321", "(21) 98765-4321"), ("(21) 2345-6789", "(21) 2345-6789"), ("", ""),
])
def test_register_accepts_and_formats_phone(client, fake, raw, expected):
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "cliente", "phone": raw})
    assert res.status_code == 302
    assert fake.signups[0]["options"]["data"]["phone"] == expected


def test_register_city_must_belong_to_state(client, fake):
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "cliente", "state": "RJ", "city": "São Paulo"})
    assert res.status_code == 400 and not fake.signups
    assert "Escolha uma cidade da lista" in res.get_data(as_text=True)
    data = {**BASE_REGISTER, "role": "cliente", "state": "SP", "city": "Cidade Inexistente"}
    res = client.post("/cadastro", data=data)
    assert res.status_code == 400 and not fake.signups


def test_register_city_is_normalized_to_official_name(client, fake):
    res = client.post("/cadastro", data={**BASE_REGISTER, "role": "cliente", "state": "PR", "city": "foz do iguacu"})
    assert res.status_code == 302
    assert fake.signups[0]["options"]["data"]["city"] == "Foz do Iguaçu"


def test_register_error_page_keeps_city_options_of_state(client):
    html = client.post("/cadastro", data={**BASE_REGISTER, "role": "cliente", "terms": ""}).get_data(as_text=True)
    assert '<option value="Campinas"' in html and "Escolha o estado primeiro" not in html


def test_cities_endpoint(client):
    res = client.get("/cidades/sp")
    assert res.status_code == 200 and "São Paulo" in res.get_json() and len(res.get_json()) == 645
    assert "max-age" in res.headers["Cache-Control"]
    assert client.get("/cidades/XX").status_code == 404
    assert client.get("/cidades/DF").get_json() == ["Brasília"]


def test_register_page_has_place_and_oab_fields(client):
    html = client.get("/cadastro?perfil=advogado").get_data(as_text=True)
    for name in ('name="state"', 'name="city"', 'name="oab_number"', 'name="oab_state"'):
        assert name in html
    assert 'id="oab-box" hidden' not in html
    assert 'id="oab-box" hidden' in client.get("/cadastro").get_data(as_text=True)


def test_logout_clears_session(client, login):
    login("cliente")
    client.post("/sair")
    assert client.get("/cliente/").status_code == 302


def test_token_refresh_when_expiring(client, login, fake):
    login("cliente")
    with client.session_transaction() as sess:
        sess["expires_at"] = 0
    client.get("/healthz")
    with client.session_transaction() as sess:
        assert sess["access_token"] == "tok2"


# ---------- cliente ----------
def test_client_dashboard_renders_cases(client, login, fake):
    login("cliente")
    fake.seed("cases", make_case())
    res = client.get("/cliente/")
    html = res.get_data(as_text=True)
    assert res.status_code == 200 and "Rescisão sem pagamento" in html and "Dr. João Lima" in html


def test_role_isolation(client, login):
    login("cliente")
    assert client.get("/advogado/").status_code == 403
    assert client.get("/admin/").status_code == 403


def test_new_case_validation(client, login):
    login("cliente")
    res = client.post("/cliente/solicitacoes/nova", data={"title": "x", "description": "curto"})
    assert res.status_code == 400


def test_new_case_creates_and_opens_detail(client, login, fake):
    login("cliente")
    res = client.post("/cliente/solicitacoes/nova", data={
        "area_id": "1", "title": "Demissão sem justa causa",
        "description": "Fui demitido e a empresa não pagou nada do que devia.",
        "urgency": "alta", "state": "sp", "estimated_value": "1.500,50", "is_online_ok": "1",
    })
    assert res.status_code == 302
    row = fake.tables["cases"][0]
    assert row["client_id"] == CLIENT_ID and row["area_id"] == 1 and row["state"] == "SP"
    assert row["estimated_value"] == "1500.50"
    assert client.get(res.headers["Location"]).status_code == 200


# ---------- advogado ----------
def test_lawyer_without_profile_is_sent_to_profile(client, login):
    login("advogado")
    res = client.get("/advogado/")
    assert res.status_code == 302 and res.headers["Location"].endswith("/advogado/perfil")


def test_lawyer_profile_create(client, login, fake):
    login("advogado")
    assert client.get("/advogado/perfil").status_code == 200
    res = client.post("/advogado/perfil", data={
        "oab_number": "123456", "oab_state": "sp", "areas": ["1", "2"], "primary_area": "2",
        "state": "SP", "years_experience": "5", "hourly_rate": "350,00", "accepts_online": "1",
    })
    assert res.status_code == 302
    lawyer = fake.tables["lawyers"][0]
    assert lawyer["oab_state"] == "SP" and lawyer["hourly_rate"] == "350.00"
    specialties = {s["area_id"]: s["is_primary"] for s in fake.tables["lawyer_specialties"]}
    assert specialties == {1: False, 2: True}


def test_lawyer_profile_invalid_oab(client, login):
    login("advogado")
    res = client.post("/advogado/perfil", data={"oab_number": "ab", "oab_state": "SP", "areas": ["1"]})
    assert res.status_code == 400


def lawyer_row(**overrides):
    row = {
        "profile_id": LAWYER_ID, "oab_number": "123456", "oab_state": "SP", "verification_status": "verificado",
        "avg_rating": 4.5, "reviews_count": 2, "cases_completed": 3, "accepts_online": True, "is_available": True,
        "lawyer_specialties": [{"area_id": 1, "is_primary": True}], "bio": None, "years_experience": None,
        "hourly_rate": None, "city": None, "state": "SP",
    }
    row.update(overrides)
    return row


def test_lawyer_dashboard_with_matches(client, login, fake):
    login("advogado")
    fake.seed("lawyers", lawyer_row())
    fake.seed("case_matches", {
        "id": "m1", "lawyer_id": LAWYER_ID, "status": "sugerido", "score": 80,
        "expires_at": "2999-01-01T00:00:00+00:00",
        "cases": {"id": CASE_ID, "protocol": "P", "title": "Caso novo", "description": "Descrição longa do caso",
                  "urgency": "media", "city": "SP", "state": "SP", "created_at": "2026-11-06T22:00:00+00:00",
                  "legal_areas": {"name": "Direito Civil"}},
    })
    html = client.get("/advogado/").get_data(as_text=True)
    assert "Caso novo" in html and "Aceitar" in html


def test_unverified_lawyer_gets_no_matches(client, login, fake):
    login("advogado")
    fake.seed("lawyers", lawyer_row(verification_status="pendente"))
    html = client.get("/advogado/").get_data(as_text=True)
    assert "em análise" in html


def test_lawyer_accepts_match(client, login, fake):
    login("advogado")
    fake.seed("case_matches", {"id": "m1", "lawyer_id": LAWYER_ID, "status": "sugerido"})
    res = client.post("/advogado/oportunidades/m1/responder", data={"action": "aceitar", "case_id": CASE_ID})
    assert res.status_code == 302 and CASE_ID in res.headers["Location"]
    assert fake.tables["case_matches"][0]["status"] == "aceito"


def test_lawyer_respond_unavailable_match(client, login):
    login("advogado")
    res = client.post("/advogado/oportunidades/zzz/responder", data={"action": "aceitar"}, follow_redirects=True)
    assert "não está mais disponível" in res.get_data(as_text=True)


# ---------- detalhe do caso ----------
def seed_full_case(fake):
    fake.seed("cases", make_case())
    fake.seed("case_events", {"id": "e1", "case_id": CASE_ID, "event_type": "caso_criado",
                              "created_at": "2026-11-06T22:00:00+00:00"})
    fake.seed("case_messages", {"id": "g1", "case_id": CASE_ID, "sender_id": CLIENT_ID, "body": "Olá, doutor!",
                                "created_at": "2026-11-06T22:05:00+00:00", "read_at": None})
    fake.seed("case_documents", {"id": "d1", "case_id": CASE_ID, "file_name": "contrato.pdf", "size_bytes": 2048,
                                 "created_at": "2026-11-06T22:06:00+00:00", "category": "contrato",
                                 "storage_path": f"{CASE_ID}/abc-contrato.pdf"})
    fake.seed("fee_agreements", {"id": "f1", "case_id": CASE_ID, "fee_type": "misto", "amount": "1000.00",
                                 "success_percent": "20", "status": "proposta", "notes": "Parcelado",
                                 "created_at": "2026-11-06T22:07:00+00:00"})
    fake.seed("appointments", {"id": "a1", "case_id": CASE_ID, "scheduled_at": "2026-12-01T13:00:00+00:00",
                               "duration_minutes": 30, "mode": "online", "status": "agendada", "meeting_url": "https://meet.test/x"})


def test_case_detail_as_client(client, login, fake):
    login("cliente")
    seed_full_case(fake)
    html = client.get(f"/casos/{CASE_ID}").get_data(as_text=True)
    for expected in ("Olá, doutor!", "contrato.pdf", "Misto", "Link da reunião", "Cancelar solicitação", "Aceitar"):
        assert expected in html
    assert fake.tables["case_messages"][0]["read_at"] is None  # a própria mensagem não é marcada como lida


def test_case_detail_as_lawyer_shows_conclude(client, login, fake):
    login("advogado")
    seed_full_case(fake)
    html = client.get(f"/casos/{CASE_ID}").get_data(as_text=True)
    assert "Marcar como concluído" in html and "Enviar proposta de honorários" in html
    assert fake.tables["case_messages"][0]["read_at"] is not None


def test_case_detail_review_form_when_concluded(client, login, fake):
    login("cliente")
    fake.seed("cases", make_case(status="concluido"))
    assert "Enviar avaliação" in client.get(f"/casos/{CASE_ID}").get_data(as_text=True)


def test_case_detail_candidate_lawyer_sees_accept(client, login, fake):
    login("advogado")
    fake.seed("cases", make_case(assigned_lawyer_id=None, status="aguardando_advogado", lawyers=None))
    fake.seed("case_matches", {"id": "m1", "case_id": CASE_ID, "lawyer_id": LAWYER_ID, "status": "sugerido"})
    html = client.get(f"/casos/{CASE_ID}").get_data(as_text=True)
    assert "Aceitar caso" in html and "Olá" not in html


def test_case_detail_invalid_or_missing(client, login):
    login("cliente")
    assert client.get("/casos/nao-e-uuid").status_code == 404
    assert client.get(f"/casos/{CASE_ID}").status_code == 404


def test_set_status_conclude_and_cancel(client, login, fake):
    login("cliente")
    fake.seed("cases", make_case())
    client.post(f"/casos/{CASE_ID}/status", data={"action": "cancelar"})
    assert fake.tables["cases"][0]["status"] == "cancelado"


def test_rematch_calls_rpc(client, login, fake):
    login("cliente")
    fake.seed("cases", make_case(assigned_lawyer_id=None, status="aberto", lawyers=None))
    fake.rpc_returns["rematch_case"] = 2
    client.post(f"/casos/{CASE_ID}/rematch")
    assert fake.rpc_calls == [("rematch_case", {"p_case_id": CASE_ID})]


def test_upload_document_validates_and_stores(client, login, fake):
    import io

    login("cliente")
    fake.seed("cases", make_case())
    base = f"/casos/{CASE_ID}/documentos"
    bad = client.post(base, data={"arquivo": (io.BytesIO(b"x"), "virus.exe")}, content_type="multipart/form-data")
    assert bad.status_code == 302 and not fake.uploads
    client.post(base, data={"arquivo": (io.BytesIO(b"%PDF-1.4"), "Meu Contrato.pdf"), "category": "contrato"},
                content_type="multipart/form-data")
    assert len(fake.uploads) == 1
    path = next(iter(fake.uploads))
    assert path.startswith(f"{CASE_ID}/") and path.endswith("Meu_Contrato.pdf")
    assert fake.tables["case_documents"][0]["uploaded_by"] == CLIENT_ID


def test_download_document_redirects_to_signed_url(client, login, fake):
    login("cliente")
    seed_full_case(fake)
    res = client.get(f"/casos/{CASE_ID}/documentos/55555555-5555-4555-8555-555555555555")
    assert res.status_code == 302  # id inexistente: volta para o caso com aviso
    fake.tables["case_documents"][0]["id"] = "55555555-5555-4555-8555-555555555555"
    res = client.get(f"/casos/{CASE_ID}/documentos/55555555-5555-4555-8555-555555555555")
    assert res.headers["Location"].startswith("https://files.test/")


def test_propose_and_respond_fee(client, login, fake):
    login("advogado")
    fake.seed("cases", make_case())
    client.post(f"/casos/{CASE_ID}/honorarios", data={"fee_type": "exito", "success_percent": "30"})
    fee = fake.tables["fee_agreements"][0]
    assert fee["lawyer_id"] == LAWYER_ID and fee["success_percent"] == "30"
    login("cliente")
    client.post(f"/casos/{CASE_ID}/honorarios/{fee['id']}/responder", data={"action": "aceitar"})
    assert fake.tables["fee_agreements"][0]["status"] == "aceita"


def test_fee_requires_amount(client, login, fake):
    login("advogado")
    fake.seed("cases", make_case())
    client.post(f"/casos/{CASE_ID}/honorarios", data={"fee_type": "fixo"})
    assert not fake.tables.get("fee_agreements")


def test_schedule_and_review(client, login, fake):
    login("cliente")
    fake.seed("cases", make_case(status="concluido"))
    client.post(f"/casos/{CASE_ID}/agendar", data={"scheduled_at": "2099-01-01T10:00", "mode": "online"})
    appt = fake.tables["appointments"][0]
    assert appt["lawyer_id"] == LAWYER_ID and appt["scheduled_at"].endswith("-03:00")
    client.post(f"/casos/{CASE_ID}/avaliar", data={"rating": "5", "comment": "Excelente"})
    assert fake.tables["reviews"][0]["rating"] == 5
    client.post(f"/casos/{CASE_ID}/agendar", data={"scheduled_at": "2000-01-01T10:00"})
    assert len(fake.tables["appointments"]) == 1  # data no passado é rejeitada


# ---------- API JSON ----------
def test_api_messages_roundtrip(client, login, fake):
    login("cliente")
    url = f"/api/casos/{CASE_ID}/mensagens"
    res = client.post(url, json={"body": "  Bom dia  "})
    assert res.status_code == 201 and res.get_json()["message"]["mine"] is True
    assert fake.tables["case_messages"][0]["body"] == "Bom dia"
    assert len(client.get(url).get_json()["messages"]) == 1
    assert client.post(url, json={"body": "   "}).status_code == 400
    assert client.get("/api/casos/xyz/mensagens").status_code == 404


def test_api_requires_login(client):
    assert client.get(f"/api/casos/{CASE_ID}/mensagens").status_code == 302


def test_notifications_count_and_page(client, login, fake):
    login("cliente")
    fake.seed("notifications", {"id": "n1", "user_id": CLIENT_ID, "title": "Novo status", "body": "x",
                                "read_at": None, "created_at": "2026-11-06T22:00:00+00:00",
                                "data": {"case_id": CASE_ID}})
    assert client.get("/api/notificacoes/contagem").get_json() == {"unread": 1}
    html = client.get("/notificacoes").get_data(as_text=True)
    assert "Novo status" in html and "Marcar todas como lidas" in html
    client.post("/notificacoes")
    assert fake.tables["notifications"][0]["read_at"] is not None


# ---------- admin ----------
def test_admin_dashboard_and_verification(client, login, fake):
    login("admin")
    fake.seed("lawyers", lawyer_row(verification_status="pendente", profiles={"full_name": "Dr. João Lima"},
                                    created_at="2026-11-01T10:00:00+00:00", city="São Paulo"))
    html = client.get("/admin/").get_data(as_text=True)
    assert "Dr. João Lima" in html and "Verificar" in html
    assert "cna.oab.org.br" in html and "confirmadv.oab.org.br" in html and 'name="checked_oab"' in html
    # sem a confirmação da conferência, a verificação é recusada
    client.post(f"/admin/advogados/{LAWYER_ID}/verificacao", data={"action": "verificar"})
    assert fake.rpc_calls == []
    client.post(f"/admin/advogados/{LAWYER_ID}/verificacao", data={"action": "verificar", "checked_oab": "1"})
    assert fake.rpc_calls == [("admin_set_lawyer_verification", {"p_lawyer_id": LAWYER_ID, "p_status": "verificado"})]
    # rejeitar não exige a confirmação
    client.post(f"/admin/advogados/{LAWYER_ID}/verificacao", data={"action": "rejeitar"})
    assert fake.rpc_calls[-1][1]["p_status"] == "rejeitado"
    assert ADMIN_ID  # usado só para documentar o papel


# ---------- infraestrutura ----------
def test_csrf_enforced_when_enabled(fake):
    class WithCsrf(TestConfig):
        WTF_CSRF_ENABLED = True

    res = create_app(WithCsrf).test_client().post("/login", data={"email": "a@b.com", "password": "x"})
    assert res.status_code == 400


def test_production_requires_secret_key(fake):
    class Prod(Config):
        APP_ENV = "production"
        SECRET_KEY = INSECURE_DEFAULT_KEY

    with pytest.raises(RuntimeError):
        create_app(Prod)


def test_utils_formatting():
    assert utils.money("1234.5") == "R$ 1.234,50"
    assert utils.money(None) == "—"
    assert utils.datebr("2026-11-06T23:30:00+00:00") == "06/11/2026 20:30"
    assert utils.parse_decimal("1.234,56") == utils.parse_decimal("1234.56")
    assert utils.parse_decimal("abc") is None and utils.parse_decimal("-5") is None
    assert utils.filesize(2048) == "2.0 KB"
