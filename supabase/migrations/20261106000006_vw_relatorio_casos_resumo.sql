-- Relatório resumido de casos (equivalente ao relatório de vendas, no modelo do LEX).
-- security_invoker: a view respeita o RLS de quem consulta (cliente vê os seus, advogado os seus, admin todos).
create or replace view public.vw_relatorio_casos_resumo
with (security_invoker = true) as
select
  c.id as case_id,
  c.protocol,
  c.created_at,
  c.status as case_status,
  c.urgency,
  c.state,
  c.city,
  c.area_id,
  a.name as area_name,
  c.client_id,
  cp.full_name as client_name,
  c.assigned_lawyer_id,
  lp.full_name as lawyer_name,
  (select count(*) from public.case_matches m where m.case_id = c.id) as total_matches,
  (select count(*) from public.case_messages ms where ms.case_id = c.id) as total_messages,
  (select count(*) from public.case_documents d where d.case_id = c.id) as total_documents,
  (select count(*) from public.appointments ap where ap.case_id = c.id) as total_appointments,
  fa.fee_type,
  fa.amount as fee_amount,
  fa.success_percent as fee_success_percent,
  fa.status as fee_status,
  r.rating as review_rating,
  c.closed_at,
  extract(day from (coalesce(c.closed_at, now()) - c.created_at))::int as days_open
from public.cases c
join public.legal_areas a on a.id = c.area_id
join public.profiles cp on cp.id = c.client_id
left join public.profiles lp on lp.id = c.assigned_lawyer_id
left join lateral (
  select f.fee_type, f.amount, f.success_percent, f.status
  from public.fee_agreements f
  where f.case_id = c.id
  order by f.created_at desc
  limit 1
) fa on true
left join lateral (
  select rv.rating
  from public.reviews rv
  where rv.case_id = c.id
  order by rv.created_at desc
  limit 1
) r on true;

revoke all on public.vw_relatorio_casos_resumo from anon;
grant select on public.vw_relatorio_casos_resumo to authenticated;
