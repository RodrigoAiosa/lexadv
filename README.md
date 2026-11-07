# LEX — plataforma que conecta clientes a advogados

O **LEX** recebe solicitações jurídicas de clientes (processo trabalhista, família, consumidor…) e as
direciona automaticamente para advogados verificados, de acordo com a especialidade, a região e a avaliação.

- **Clientes** se cadastram, descrevem o problema e acompanham tudo: status, chat, documentos, honorários e agenda.
- **Advogados** cadastram OAB e especialidades, recebem oportunidades compatíveis e aceitam os casos (o primeiro que aceitar assume).
- **Administradores** verificam a inscrição dos advogados na OAB.

**Stack:** Python 3.10+ · Flask · Supabase (Postgres + Auth + Storage, projeto `BD_LEX`) · HTML/CSS/JS puros.

## Estrutura

```
lexadv/
├── app.py                  # ponto de entrada (python app.py | gunicorn app:app)
├── requirements.txt        # dependências de produção
├── requirements-dev.txt    # + pytest e ruff
├── .env.example            # variáveis de ambiente (copie para .env)
├── lex/
│   ├── __init__.py         # create_app(): config, CSRF, blueprints, erros
│   ├── config.py           # configuração via variáveis de ambiente
│   ├── db.py               # clientes Supabase (anon e autenticado como o usuário)
│   ├── auth.py             # login, cadastro, sessão, decoradores de papel
│   ├── services.py         # acesso a dados (todas as consultas ao BD_LEX)
│   ├── utils.py            # formatação, validação, mensagens de erro
│   ├── constants.py        # rótulos em português e listas (UFs, status…)
│   └── blueprints/         # main, client, lawyer, cases, api, admin
├── templates/              # index.html, base.html e telas (Jinja2)
├── public/static/          # css/style.css, js/main.js, js/chat.js, img/ (servidos em /static)
├── supabase/migrations/    # SQL do banco (tabelas, triggers, RLS, storage)
├── tests/                  # pytest com Supabase simulado em memória
├── Dockerfile · Procfile   # deploy
└── .github/workflows/ci.yml
```

## Rodando localmente

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env               # confira SUPABASE_URL / SUPABASE_KEY e defina SECRET_KEY
python app.py                      # http://127.0.0.1:5000
```

Testes e lint:

```bash
pytest
ruff check .
```

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave da sessão do Flask. **Obrigatória em produção.** |
| `SUPABASE_URL` | URL do projeto (`https://tgfqlxvrfftcgpdxmzaw.supabase.co`). |
| `SUPABASE_KEY` | Chave *publishable/anon*. **Nunca use a `service_role` neste app.** |
| `SITE_URL` | URL pública do site, usada no link do e-mail de confirmação. |
| `APP_ENV` | `development` ou `production` (cookie `Secure` e checagens extras). |

## Banco de dados (BD_LEX)

O schema já está aplicado no projeto Supabase. Os arquivos em `supabase/migrations/` o documentam e permitem
recriá-lo em outro projeto (`supabase db push`, ou colando os SQLs em ordem no SQL Editor).

**Tabelas:** `profiles`, `profile_private`, `clients`, `lawyers`, `legal_areas`, `lawyer_specialties`, `cases`,
`case_matches`, `case_events`, `case_messages`, `case_documents`, `fee_agreements`, `appointments`, `reviews`,
`payments`, `notifications` + bucket privado `case-documents`.

**Como funciona o direcionamento:** ao criar uma solicitação, um trigger sugere até 5 advogados verificados e
disponíveis da área (pontuação por especialidade principal, mesmo estado, nota e atendimento online). O primeiro a
aceitar assume o caso e as demais sugestões expiram. O cliente pode pedir mais advogados (`rematch_case`).

**Segurança:** todas as tabelas usam RLS e o Flask sempre age com o JWT do usuário logado — quem decide o que cada
pessoa vê é o banco. Colunas sensíveis (papel, verificação, nota do advogado) não são editáveis pelos usuários.

### Primeiro administrador

Cadastre-se normalmente e, no SQL Editor do Supabase, promova a conta:

```sql
update public.profiles set role = 'admin' where id = '<uuid do usuário>';
```

Depois disso, em `/admin` você aprova os advogados (consulte a OAB antes de verificar).

### Ajustes no painel do Supabase

- **Authentication → Providers → Email:** com “Confirm email” ligado, o usuário precisa confirmar o e-mail antes de
  entrar (recomendado em produção). Configure o *Site URL* e os *Redirect URLs* com o endereço do seu site.
- **Authentication → Policies:** ative a proteção contra senhas vazadas.

## Deploy

**Docker**

```bash
docker build -t lexadv .
docker run -p 8000:8000 --env-file .env lexadv
```

**Vercel:** o `vercel.json` (framework Flask) e o `[tool.vercel]` do `pyproject.toml` apontam para `app:app`; os arquivos estáticos ficam em `public/static` para serem servidos pela CDN. Importe o repositório e, em
*Settings → Environment Variables*, defina `SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `APP_ENV=production` e
`SITE_URL` (ex.: `https://lexadv-lex.vercel.app`); depois faça um novo deploy. Para o site abrir ao público em
`*.vercel.app`, desative *Settings → Deployment Protection → Vercel Authentication* (ou use um domínio próprio).
No Supabase (*Authentication → URL Configuration*), inclua o endereço do site em *Site URL* e *Redirect URLs*.

**Render / Railway / Heroku:** o `Procfile` já executa `gunicorn app:app`. Defina as variáveis de ambiente do
quadro acima (com `APP_ENV=production`). O endpoint `/healthz` serve para o health check.

## Rotas principais

| Rota | Quem | O que faz |
|---|---|---|
| `/` | todos | Página inicial |
| `/cadastro`, `/login` | visitantes | Criar conta (cliente ou advogado) e entrar |
| `/cliente/`, `/cliente/solicitacoes/nova` | cliente | Painel e nova solicitação |
| `/advogado/`, `/advogado/perfil` | advogado | Oportunidades, casos e perfil/OAB/especialidades |
| `/casos/<id>` | partes do caso | Chat, documentos, honorários, agenda, avaliação, linha do tempo |
| `/admin/` | admin | Verificação de advogados |
| `/api/...` | logado | Mensagens do chat e contador de notificações (JSON) |

## Próximos passos sugeridos

- Pagamento dos honorários (a tabela `payments` já existe; escrever via webhook do gateway com a `service_role`).
- Envio de e-mails/WhatsApp para novas oportunidades e mensagens.
- Realtime do Supabase no chat (hoje usa polling a cada 5 s).
- Busca e diretório público de advogados.
