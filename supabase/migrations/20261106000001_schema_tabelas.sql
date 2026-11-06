-- BD_LEX · Migration 01: tipos, tabelas, índices e áreas do direito
create schema if not exists private;

-- ========== TIPOS ==========
create type public.user_role as enum ('cliente','advogado','admin');
create type public.lawyer_verification as enum ('pendente','verificado','rejeitado','suspenso');
create type public.case_status as enum ('aberto','aguardando_advogado','em_andamento','concluido','cancelado');
create type public.case_urgency as enum ('baixa','media','alta','urgente');
create type public.match_status as enum ('sugerido','aceito','recusado','expirado');
create type public.fee_type as enum ('fixo','por_hora','exito','misto');
create type public.fee_status as enum ('proposta','aceita','recusada');
create type public.appointment_mode as enum ('online','presencial','telefone');
create type public.appointment_status as enum ('agendada','confirmada','realizada','cancelada');
create type public.payment_status as enum ('pendente','pago','falhou','reembolsado');

-- ========== USUÁRIOS ==========
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role public.user_role not null default 'cliente',
  full_name text not null default '',
  avatar_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
comment on table public.profiles is 'Dados básicos (não sensíveis) de todos os usuários: clientes, advogados e admins.';

create table public.profile_private (
  profile_id uuid primary key references public.profiles(id) on delete cascade,
  email text,
  phone text,
  cpf text unique check (cpf is null or cpf ~ '^[0-9]{11}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
comment on table public.profile_private is 'Dados sensíveis (e-mail, telefone, CPF). Visíveis apenas ao dono e ao admin.';

create table public.clients (
  profile_id uuid primary key references public.profiles(id) on delete cascade,
  birth_date date,
  zip_code text,
  street text,
  number text,
  complement text,
  neighborhood text,
  city text,
  state char(2) check (state is null or state ~ '^[A-Z]{2}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.lawyers (
  profile_id uuid primary key references public.profiles(id) on delete cascade,
  oab_number text not null,
  oab_state char(2) not null check (oab_state ~ '^[A-Z]{2}$'),
  bio text,
  years_experience smallint check (years_experience is null or years_experience >= 0),
  hourly_rate numeric(10,2) check (hourly_rate is null or hourly_rate >= 0),
  city text,
  state char(2) check (state is null or state ~ '^[A-Z]{2}$'),
  accepts_online boolean not null default true,
  is_available boolean not null default true,
  verification_status public.lawyer_verification not null default 'pendente',
  verified_at timestamptz,
  avg_rating numeric(3,2) not null default 0,
  reviews_count integer not null default 0,
  cases_completed integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (oab_state, oab_number)
);

-- ========== ÁREAS DO DIREITO ==========
create table public.legal_areas (
  id smallint generated always as identity primary key,
  slug text not null unique,
  name text not null unique,
  description text,
  icon text,
  is_active boolean not null default true
);

create table public.lawyer_specialties (
  lawyer_id uuid not null references public.lawyers(profile_id) on delete cascade,
  area_id smallint not null references public.legal_areas(id) on delete restrict,
  is_primary boolean not null default false,
  years_experience smallint check (years_experience is null or years_experience >= 0),
  created_at timestamptz not null default now(),
  primary key (lawyer_id, area_id)
);

-- ========== SOLICITAÇÕES (CASOS) ==========
create sequence public.case_protocol_seq;

create table public.cases (
  id uuid primary key default gen_random_uuid(),
  protocol text not null unique default ('LEX-' || to_char(now(), 'YYYY') || '-' || lpad(nextval('public.case_protocol_seq')::text, 6, '0')),
  client_id uuid not null references public.clients(profile_id) on delete cascade,
  area_id smallint not null references public.legal_areas(id),
  title text not null check (char_length(title) between 5 and 200),
  description text not null check (char_length(description) >= 20),
  urgency public.case_urgency not null default 'media',
  status public.case_status not null default 'aberto',
  assigned_lawyer_id uuid references public.lawyers(profile_id) on delete set null,
  city text,
  state char(2) check (state is null or state ~ '^[A-Z]{2}$'),
  estimated_value numeric(14,2) check (estimated_value is null or estimated_value >= 0),
  opposing_party text,
  desired_outcome text,
  is_online_ok boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  closed_at timestamptz
);

create table public.case_matches (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  lawyer_id uuid not null references public.lawyers(profile_id) on delete cascade,
  score numeric(6,2) not null default 0,
  status public.match_status not null default 'sugerido',
  notified_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '48 hours'),
  responded_at timestamptz,
  decline_reason text,
  created_at timestamptz not null default now(),
  unique (case_id, lawyer_id)
);
comment on table public.case_matches is 'Direcionamento automático: advogados sugeridos para cada solicitação, de acordo com a especialidade.';

create table public.fee_agreements (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  lawyer_id uuid not null references public.lawyers(profile_id) on delete cascade,
  fee_type public.fee_type not null,
  amount numeric(12,2) check (amount is null or amount >= 0),
  success_percent numeric(5,2) check (success_percent is null or success_percent between 0 and 100),
  notes text,
  status public.fee_status not null default 'proposta',
  accepted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.case_documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  uploaded_by uuid not null references public.profiles(id),
  file_name text not null,
  storage_path text not null,
  mime_type text,
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  category text,
  created_at timestamptz not null default now()
);

create table public.case_messages (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  sender_id uuid not null references public.profiles(id),
  body text not null check (char_length(body) between 1 and 5000),
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.case_events (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  actor_id uuid references public.profiles(id) on delete set null,
  event_type text not null,
  description text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.appointments (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  client_id uuid not null references public.clients(profile_id) on delete cascade,
  lawyer_id uuid not null references public.lawyers(profile_id) on delete cascade,
  scheduled_at timestamptz not null,
  duration_minutes smallint not null default 30 check (duration_minutes > 0),
  mode public.appointment_mode not null default 'online',
  meeting_url text,
  status public.appointment_status not null default 'agendada',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.reviews (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null unique references public.cases(id) on delete cascade,
  client_id uuid not null references public.clients(profile_id) on delete cascade,
  lawyer_id uuid not null references public.lawyers(profile_id) on delete cascade,
  rating smallint not null check (rating between 1 and 5),
  comment text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.payments (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  fee_agreement_id uuid references public.fee_agreements(id) on delete set null,
  payer_id uuid not null references public.profiles(id),
  payee_id uuid not null references public.lawyers(profile_id),
  amount numeric(12,2) not null check (amount >= 0),
  platform_fee numeric(12,2) not null default 0 check (platform_fee >= 0),
  currency text not null default 'BRL',
  status public.payment_status not null default 'pendente',
  method text,
  provider text,
  provider_reference text,
  paid_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  type text not null,
  title text not null,
  body text,
  data jsonb not null default '{}'::jsonb,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

-- ========== ÍNDICES ==========
create index idx_profiles_role on public.profiles(role);
create index idx_lawyers_verif_avail on public.lawyers(verification_status, is_available);
create index idx_lawyers_state on public.lawyers(state);
create index idx_specialties_area on public.lawyer_specialties(area_id);
create index idx_cases_client on public.cases(client_id);
create index idx_cases_lawyer on public.cases(assigned_lawyer_id);
create index idx_cases_area_status on public.cases(area_id, status);
create index idx_cases_created on public.cases(created_at desc);
create index idx_matches_lawyer_status on public.case_matches(lawyer_id, status);
create index idx_fee_case on public.fee_agreements(case_id);
create index idx_fee_lawyer on public.fee_agreements(lawyer_id);
create index idx_docs_case on public.case_documents(case_id);
create index idx_docs_uploader on public.case_documents(uploaded_by);
create index idx_msgs_case_created on public.case_messages(case_id, created_at);
create index idx_msgs_sender on public.case_messages(sender_id);
create index idx_events_case_created on public.case_events(case_id, created_at);
create index idx_events_actor on public.case_events(actor_id);
create index idx_appt_case on public.appointments(case_id);
create index idx_appt_lawyer_when on public.appointments(lawyer_id, scheduled_at);
create index idx_appt_client_when on public.appointments(client_id, scheduled_at);
create index idx_reviews_lawyer on public.reviews(lawyer_id);
create index idx_reviews_client on public.reviews(client_id);
create index idx_pay_case on public.payments(case_id);
create index idx_pay_payer on public.payments(payer_id);
create index idx_pay_payee on public.payments(payee_id);
create index idx_pay_fee on public.payments(fee_agreement_id);
create index idx_notif_user_unread on public.notifications(user_id, created_at desc) where read_at is null;

-- ========== ÁREAS JURÍDICAS INICIAIS ==========
insert into public.legal_areas (slug, name, description, icon) values
 ('trabalhista','Direito Trabalhista','Rescisão, horas extras, assédio, vínculo empregatício, verbas trabalhistas','briefcase'),
 ('civil','Direito Civil','Contratos, indenizações, responsabilidade civil, cobranças','scale'),
 ('familia','Família e Sucessões','Divórcio, pensão alimentícia, guarda, inventário, testamento','users'),
 ('criminal','Direito Criminal','Defesa criminal, inquéritos, habeas corpus, queixa-crime','shield'),
 ('consumidor','Direito do Consumidor','Produtos e serviços defeituosos, cobranças indevidas, negativação','shopping-cart'),
 ('previdenciario','Direito Previdenciário','Aposentadoria, auxílio-doença, BPC/LOAS, revisões do INSS','landmark'),
 ('tributario','Direito Tributário','Planejamento tributário, execuções fiscais, restituição de impostos','receipt'),
 ('empresarial','Direito Empresarial','Abertura de empresas, contratos societários, recuperação judicial','building'),
 ('imobiliario','Direito Imobiliário','Compra e venda, locação, usucapião, distrato, condomínio','home'),
 ('administrativo','Direito Administrativo','Concursos públicos, licitações, servidores públicos','file-text'),
 ('digital','Direito Digital e LGPD','Proteção de dados, crimes virtuais, remoção de conteúdo','laptop'),
 ('saude','Direito da Saúde','Planos de saúde, medicamentos, cirurgias, erro médico','heart-pulse'),
 ('transito','Direito de Trânsito','Multas, suspensão de CNH, acidentes de trânsito','car'),
 ('ambiental','Direito Ambiental','Licenciamento, infrações e danos ambientais','leaf'),
 ('bancario','Direito Bancário','Juros abusivos, revisão de contratos, fraudes bancárias','banknote');
