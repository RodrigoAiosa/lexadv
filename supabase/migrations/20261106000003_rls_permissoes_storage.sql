-- BD_LEX · Migration 03: RLS, permissões por coluna, Storage e Realtime

-- ========== RLS ==========
alter table public.profiles enable row level security;
alter table public.profile_private enable row level security;
alter table public.clients enable row level security;
alter table public.lawyers enable row level security;
alter table public.legal_areas enable row level security;
alter table public.lawyer_specialties enable row level security;
alter table public.cases enable row level security;
alter table public.case_matches enable row level security;
alter table public.fee_agreements enable row level security;
alter table public.case_documents enable row level security;
alter table public.case_messages enable row level security;
alter table public.case_events enable row level security;
alter table public.appointments enable row level security;
alter table public.reviews enable row level security;
alter table public.payments enable row level security;
alter table public.notifications enable row level security;

-- profiles
create policy profiles_select on public.profiles for select to authenticated using (
  id = (select auth.uid())
  or (select private.is_admin())
  or exists (select 1 from public.lawyers l where l.profile_id = profiles.id and l.verification_status = 'verificado')
  or (select private.is_counterpart(profiles.id)));
create policy profiles_update_own on public.profiles for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- profile_private
create policy pp_select on public.profile_private for select to authenticated
  using (profile_id = (select auth.uid()) or (select private.is_admin()));
create policy pp_update_own on public.profile_private for update to authenticated
  using (profile_id = (select auth.uid())) with check (profile_id = (select auth.uid()));

-- clients
create policy clients_select on public.clients for select to authenticated
  using (profile_id = (select auth.uid()) or (select private.is_admin()));
create policy clients_update_own on public.clients for update to authenticated
  using (profile_id = (select auth.uid())) with check (profile_id = (select auth.uid()));

-- lawyers
create policy lawyers_select on public.lawyers for select to authenticated
  using (verification_status = 'verificado' or profile_id = (select auth.uid()) or (select private.is_admin()));
create policy lawyers_insert_own on public.lawyers for insert to authenticated
  with check (profile_id = (select auth.uid()) and (select private.is_lawyer()));
create policy lawyers_update_own on public.lawyers for update to authenticated
  using (profile_id = (select auth.uid())) with check (profile_id = (select auth.uid()));

-- legal_areas (leitura pública, para a tela de cadastro/solicitação)
create policy areas_select on public.legal_areas for select to anon, authenticated using (is_active);

-- lawyer_specialties
create policy spec_select on public.lawyer_specialties for select to authenticated using (true);
create policy spec_insert_own on public.lawyer_specialties for insert to authenticated
  with check (lawyer_id = (select auth.uid()));
create policy spec_update_own on public.lawyer_specialties for update to authenticated
  using (lawyer_id = (select auth.uid())) with check (lawyer_id = (select auth.uid()));
create policy spec_delete_own on public.lawyer_specialties for delete to authenticated
  using (lawyer_id = (select auth.uid()));

-- cases
create policy cases_select on public.cases for select to authenticated using ((select private.can_view_case(id)));
create policy cases_insert_client on public.cases for insert to authenticated
  with check (client_id = (select auth.uid()) and (select private.is_client()));
create policy cases_update on public.cases for update to authenticated
  using (client_id = (select auth.uid()) or assigned_lawyer_id = (select auth.uid()) or (select private.is_admin()))
  with check (client_id = (select auth.uid()) or assigned_lawyer_id = (select auth.uid()) or (select private.is_admin()));

-- case_matches
create policy matches_select on public.case_matches for select to authenticated using (
  lawyer_id = (select auth.uid()) or (select private.is_case_client(case_id)) or (select private.is_admin()));
create policy matches_respond on public.case_matches for update to authenticated
  using (lawyer_id = (select auth.uid()) and status = 'sugerido' and expires_at > now())
  with check (lawyer_id = (select auth.uid()) and status in ('aceito','recusado'));

-- fee_agreements
create policy fee_select on public.fee_agreements for select to authenticated
  using ((select private.is_case_participant(case_id)));
create policy fee_insert_lawyer on public.fee_agreements for insert to authenticated
  with check (lawyer_id = (select auth.uid()) and (select private.is_case_lawyer(case_id)));
create policy fee_update_party on public.fee_agreements for update to authenticated
  using ((select private.is_case_party(case_id))) with check ((select private.is_case_party(case_id)));

-- case_documents
create policy docs_select on public.case_documents for select to authenticated
  using ((select private.is_case_participant(case_id)));
create policy docs_insert on public.case_documents for insert to authenticated
  with check (uploaded_by = (select auth.uid()) and (select private.is_case_party(case_id)));
create policy docs_delete_own on public.case_documents for delete to authenticated
  using (uploaded_by = (select auth.uid()) and (select private.is_case_party(case_id)));

-- case_messages
create policy msgs_select on public.case_messages for select to authenticated
  using ((select private.is_case_participant(case_id)));
create policy msgs_insert on public.case_messages for insert to authenticated
  with check (
    sender_id = (select auth.uid())
    and (select private.is_case_party(case_id))
    and exists (select 1 from public.cases c where c.id = case_messages.case_id
                and c.assigned_lawyer_id is not null and c.status <> 'cancelado'));
create policy msgs_mark_read on public.case_messages for update to authenticated
  using ((select private.is_case_party(case_id)) and sender_id <> (select auth.uid()))
  with check ((select private.is_case_party(case_id)) and sender_id <> (select auth.uid()));

-- case_events
create policy events_select on public.case_events for select to authenticated
  using ((select private.is_case_participant(case_id)));
create policy events_insert on public.case_events for insert to authenticated
  with check (actor_id = (select auth.uid()) and (select private.is_case_party(case_id)));

-- appointments
create policy appt_select on public.appointments for select to authenticated
  using ((select private.is_case_participant(case_id)));
create policy appt_insert on public.appointments for insert to authenticated
  with check (
    (select private.is_case_party(case_id))
    and exists (select 1 from public.cases c where c.id = appointments.case_id
                and c.client_id = appointments.client_id and c.assigned_lawyer_id = appointments.lawyer_id));
create policy appt_update on public.appointments for update to authenticated
  using ((select private.is_case_party(case_id))) with check ((select private.is_case_party(case_id)));

-- reviews
create policy reviews_select on public.reviews for select to authenticated using (true);
create policy reviews_insert on public.reviews for insert to authenticated
  with check (
    client_id = (select auth.uid())
    and exists (select 1 from public.cases c where c.id = reviews.case_id and c.client_id = (select auth.uid())
                and c.status = 'concluido' and c.assigned_lawyer_id = reviews.lawyer_id));
create policy reviews_update_own on public.reviews for update to authenticated
  using (client_id = (select auth.uid())) with check (client_id = (select auth.uid()));

-- payments (somente leitura para os envolvidos; escrita via service_role / webhook do gateway)
create policy pay_select on public.payments for select to authenticated using (
  payer_id = (select auth.uid()) or payee_id = (select auth.uid()) or (select private.is_admin()));

-- notifications
create policy notif_select_own on public.notifications for select to authenticated using (user_id = (select auth.uid()));
create policy notif_update_own on public.notifications for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy notif_delete_own on public.notifications for delete to authenticated using (user_id = (select auth.uid()));

-- ========== GRANTS (mínimo necessário, por coluna onde há campos protegidos) ==========
do $$ declare r record; begin
  for r in select tablename from pg_tables where schemaname = 'public' loop
    execute format('revoke all on table public.%I from anon, authenticated', r.tablename);
  end loop;
end $$;

grant select on public.legal_areas to anon, authenticated;

grant select on public.profiles to authenticated;
grant update (full_name, avatar_url) on public.profiles to authenticated;

grant select on public.profile_private to authenticated;
grant update (phone, cpf) on public.profile_private to authenticated;

grant select on public.clients to authenticated;
grant update (birth_date, zip_code, street, number, complement, neighborhood, city, state) on public.clients to authenticated;

grant select on public.lawyers to authenticated;
grant insert (profile_id, oab_number, oab_state, bio, years_experience, hourly_rate, city, state, accepts_online) on public.lawyers to authenticated;
grant update (bio, years_experience, hourly_rate, city, state, accepts_online, is_available) on public.lawyers to authenticated;

grant select, insert, delete on public.lawyer_specialties to authenticated;
grant update (is_primary, years_experience) on public.lawyer_specialties to authenticated;

grant select on public.cases to authenticated;
grant insert (client_id, area_id, title, description, urgency, city, state, estimated_value, opposing_party, desired_outcome, is_online_ok) on public.cases to authenticated;
grant update (title, description, urgency, status, city, state, estimated_value, opposing_party, desired_outcome, is_online_ok) on public.cases to authenticated;
grant usage on sequence public.case_protocol_seq to authenticated;

grant select on public.case_matches to authenticated;
grant update (status, decline_reason) on public.case_matches to authenticated;

grant select on public.fee_agreements to authenticated;
grant insert (case_id, lawyer_id, fee_type, amount, success_percent, notes) on public.fee_agreements to authenticated;
grant update (fee_type, amount, success_percent, notes, status) on public.fee_agreements to authenticated;

grant select, delete on public.case_documents to authenticated;
grant insert (case_id, uploaded_by, file_name, storage_path, mime_type, size_bytes, category) on public.case_documents to authenticated;

grant select on public.case_messages to authenticated;
grant insert (case_id, sender_id, body) on public.case_messages to authenticated;
grant update (read_at) on public.case_messages to authenticated;

grant select on public.case_events to authenticated;
grant insert (case_id, actor_id, event_type, description, metadata) on public.case_events to authenticated;

grant select on public.appointments to authenticated;
grant insert (case_id, client_id, lawyer_id, scheduled_at, duration_minutes, mode, meeting_url, notes) on public.appointments to authenticated;
grant update (scheduled_at, duration_minutes, mode, meeting_url, status, notes) on public.appointments to authenticated;

grant select on public.reviews to authenticated;
grant insert (case_id, client_id, lawyer_id, rating, comment) on public.reviews to authenticated;
grant update (rating, comment) on public.reviews to authenticated;

grant select on public.payments to authenticated;

grant select, delete on public.notifications to authenticated;
grant update (read_at) on public.notifications to authenticated;

-- ========== STORAGE: bucket privado para documentos (pasta = id da solicitação) ==========
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types) values (
  'case-documents', 'case-documents', false, 20971520,
  array['application/pdf','image/jpeg','image/png','text/plain','application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'])
on conflict (id) do nothing;

create policy case_docs_read on storage.objects for select to authenticated
  using (bucket_id = 'case-documents' and (select private.is_case_participant(((storage.foldername(name))[1])::uuid)));
create policy case_docs_upload on storage.objects for insert to authenticated
  with check (bucket_id = 'case-documents' and (select private.is_case_party(((storage.foldername(name))[1])::uuid)));
create policy case_docs_delete on storage.objects for delete to authenticated
  using (bucket_id = 'case-documents' and owner_id = (select auth.uid()::text)
         and (select private.is_case_party(((storage.foldername(name))[1])::uuid)));

-- ========== REALTIME (chat e notificações ao vivo) ==========
do $$ begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table public.case_messages, public.notifications;
  end if;
end $$;
