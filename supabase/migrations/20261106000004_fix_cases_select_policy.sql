-- BD_LEX · Migration 04: correção da policy de leitura de `cases`.
-- A policy anterior chamava uma função que não enxerga a linha recém-inserida, o que quebrava
-- INSERT ... RETURNING (usado pelo supabase-js/supabase-py). Agora usa colunas diretamente.
drop policy if exists cases_select on public.cases;
create policy cases_select on public.cases for select to authenticated using (
  client_id = (select auth.uid())
  or assigned_lawyer_id = (select auth.uid())
  or (select private.is_admin())
  or exists (select 1 from public.case_matches m
             where m.case_id = cases.id and m.lawyer_id = (select auth.uid())
               and (m.status = 'aceito' or (m.status = 'sugerido' and m.expires_at > now()))));
