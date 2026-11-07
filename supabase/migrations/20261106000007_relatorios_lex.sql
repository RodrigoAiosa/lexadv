-- Relatórios do LEX (equivalentes às views de vendas, no modelo de casos e advogados).
-- Todas usam security_invoker: respeitam o RLS de quem consulta. O panorama completo só aparece para admin;
-- cliente e advogado veem apenas os números dos casos a que já têm acesso.

-- casos por mês e status (equivale a "meta de vendas mensal")
create or replace view public.vw_relatorio_casos_mensal with (security_invoker = true) as
select
  date_trunc('month', c.created_at) as month,
  c.status as case_status,
  count(*) as cases_count,
  count(*) filter (where c.urgency in ('alta', 'urgente')) as urgent_count,
  count(c.assigned_lawyer_id) as assigned_count
from public.cases c
group by date_trunc('month', c.created_at), c.status
order by month desc, case_status;

-- áreas do direito mais demandadas (equivale a "produtos mais vendidos")
create or replace view public.vw_relatorio_areas_mais_demandadas with (security_invoker = true) as
select
  a.id as area_id,
  a.name as area_name,
  count(c.id) as total_cases,
  count(c.assigned_lawyer_id) as assigned_cases,
  count(c.id) filter (where c.status = 'concluido') as closed_cases,
  round(100.0 * count(c.assigned_lawyer_id) / nullif(count(c.id), 0), 1) as assigned_rate_pct
from public.legal_areas a
left join public.cases c on c.area_id = a.id
group by a.id, a.name
order by total_cases desc, a.name;

-- resumo por cliente (equivale a "clientes resumo")
create or replace view public.vw_relatorio_clientes_resumo with (security_invoker = true) as
select
  p.id as client_id,
  p.full_name as client_name,
  pp.email,
  cl.city,
  cl.state,
  p.created_at as client_created_at,
  count(c.id) as cases_count,
  count(c.id) filter (where c.status in ('aberto', 'aguardando_advogado', 'em_andamento')) as open_cases,
  count(c.id) filter (where c.status = 'concluido') as closed_cases,
  max(c.created_at) as last_case_at
from public.clients cl
join public.profiles p on p.id = cl.profile_id
left join public.profile_private pp on pp.profile_id = p.id
left join public.cases c on c.client_id = cl.profile_id
group by p.id, p.full_name, pp.email, cl.city, cl.state, p.created_at;

-- ranking de advogados
create or replace view public.vw_relatorio_advogados_ranking with (security_invoker = true) as
select
  l.profile_id as lawyer_id,
  p.full_name as lawyer_name,
  l.oab_number,
  l.oab_state,
  l.city,
  l.state,
  l.verification_status,
  l.is_available,
  l.avg_rating,
  l.reviews_count,
  l.cases_completed,
  (select count(*) from public.cases c where c.assigned_lawyer_id = l.profile_id) as cases_assigned,
  m.received as matches_received,
  m.accepted as matches_accepted,
  round(100.0 * m.accepted / nullif(m.received, 0), 1) as acceptance_rate_pct
from public.lawyers l
join public.profiles p on p.id = l.profile_id
left join lateral (
  select count(*) as received, count(*) filter (where cm.status = 'aceito') as accepted
  from public.case_matches cm
  where cm.lawyer_id = l.profile_id
) m on true
order by l.avg_rating desc, l.cases_completed desc;

-- indicações de advogados por caso, em detalhe (equivale a "vendas detalhado")
create or replace view public.vw_relatorio_indicacoes_detalhado with (security_invoker = true) as
select
  m.id as match_id,
  c.id as case_id,
  c.protocol,
  a.name as area_name,
  m.lawyer_id,
  lp.full_name as lawyer_name,
  m.score,
  m.status as match_status,
  m.notified_at,
  m.responded_at,
  round(extract(epoch from (m.responded_at - m.notified_at)) / 3600.0, 1) as response_hours,
  m.decline_reason
from public.case_matches m
join public.cases c on c.id = m.case_id
join public.legal_areas a on a.id = c.area_id
join public.profiles lp on lp.id = m.lawyer_id;

revoke all on public.vw_relatorio_casos_mensal, public.vw_relatorio_areas_mais_demandadas,
  public.vw_relatorio_clientes_resumo, public.vw_relatorio_advogados_ranking,
  public.vw_relatorio_indicacoes_detalhado from anon;
grant select on public.vw_relatorio_casos_mensal, public.vw_relatorio_areas_mais_demandadas,
  public.vw_relatorio_clientes_resumo, public.vw_relatorio_advogados_ranking,
  public.vw_relatorio_indicacoes_detalhado to authenticated;
