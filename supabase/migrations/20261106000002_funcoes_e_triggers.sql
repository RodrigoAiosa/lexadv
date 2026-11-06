-- BD_LEX · Migration 02: funções auxiliares, cadastro automático, direcionamento e triggers

-- ========== updated_at ==========
create function private.set_updated_at() returns trigger language plpgsql set search_path = '' as $$
begin new.updated_at := now(); return new; end $$;

create trigger trg_updated_at before update on public.profiles for each row execute function private.set_updated_at();
create trigger trg_updated_at before update on public.profile_private for each row execute function private.set_updated_at();
create trigger trg_updated_at before update on public.clients for each row execute function private.set_updated_at();
create trigger trg_updated_at before update on public.lawyers for each row execute function private.set_updated_at();
create trigger trg_updated_at before update on public.cases for each row execute function private.set_updated_at();
create trigger trg_updated_at before update on public.fee_agreements for each row execute function private.set_updated_at();
create trigger trg_updated_at before update on public.appointments for each row execute function private.set_updated_at();
create trigger trg_updated_at before update on public.payments for each row execute function private.set_updated_at();
create trigger trg_updated_at before update on public.reviews for each row execute function private.set_updated_at();

-- ========== HELPERS DE PERMISSÃO (usados nas policies) ==========
create function private.is_admin() returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles where id = (select auth.uid()) and role = 'admin' and is_active) $$;

create function private.is_lawyer() returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles where id = (select auth.uid()) and role = 'advogado' and is_active) $$;

create function private.is_client() returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles where id = (select auth.uid()) and role = 'cliente' and is_active) $$;

create function private.is_case_client(p_case uuid) returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.cases where id = p_case and client_id = (select auth.uid())) $$;

create function private.is_case_lawyer(p_case uuid) returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.cases where id = p_case and assigned_lawyer_id = (select auth.uid())) $$;

create function private.is_case_party(p_case uuid) returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.cases where id = p_case
    and (client_id = (select auth.uid()) or assigned_lawyer_id = (select auth.uid()))) $$;

create function private.is_case_participant(p_case uuid) returns boolean language sql stable security definer set search_path = '' as $$
  select private.is_case_party(p_case) or private.is_admin() $$;

create function private.can_view_case(p_case uuid) returns boolean language sql stable security definer set search_path = '' as $$
  select private.is_case_participant(p_case)
    or exists (select 1 from public.case_matches m
               where m.case_id = p_case and m.lawyer_id = (select auth.uid())
                 and (m.status = 'aceito' or (m.status = 'sugerido' and m.expires_at > now()))) $$;

create function private.is_counterpart(p_profile uuid) returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.cases c
    where (c.client_id = (select auth.uid()) and c.assigned_lawyer_id = p_profile)
       or (c.assigned_lawyer_id = (select auth.uid()) and c.client_id = p_profile)) $$;

-- ========== CADASTRO: cria perfil automaticamente ao registrar no Supabase Auth ==========
create function private.handle_new_user() returns trigger language plpgsql security definer set search_path = '' as $$
declare v_role public.user_role;
begin
  -- só é possível se cadastrar como cliente ou advogado; admin é definido manualmente
  v_role := case when new.raw_user_meta_data->>'role' = 'advogado' then 'advogado'::public.user_role else 'cliente'::public.user_role end;
  insert into public.profiles (id, role, full_name)
    values (new.id, v_role, coalesce(new.raw_user_meta_data->>'full_name', ''));
  insert into public.profile_private (profile_id, email, phone)
    values (new.id, new.email, new.raw_user_meta_data->>'phone');
  if v_role = 'cliente' then
    insert into public.clients (profile_id) values (new.id);
  end if;
  return new;
end $$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function private.handle_new_user();

-- ========== DIRECIONAMENTO AUTOMÁTICO POR ESPECIALIDADE ==========
create function private.match_lawyers_for_case(p_case_id uuid, p_limit int default 5) returns int
language plpgsql security definer set search_path = '' as $$
declare c public.cases%rowtype; n int;
begin
  select * into c from public.cases where id = p_case_id;
  if not found or c.assigned_lawyer_id is not null or c.status in ('concluido','cancelado') then
    return 0;
  end if;

  update public.case_matches set status = 'expirado'
   where case_id = c.id and status = 'sugerido' and expires_at <= now();

  insert into public.case_matches (case_id, lawyer_id, score)
  select c.id, l.profile_id,
         (50
          + case when ls.is_primary then 20 else 0 end
          + case when c.state is not null and l.state = c.state then 15 else 0 end
          + l.avg_rating * 2
          + case when l.accepts_online then 5 else 0 end)::numeric(6,2) as score
    from public.lawyers l
    join public.lawyer_specialties ls on ls.lawyer_id = l.profile_id and ls.area_id = c.area_id
    join public.profiles p on p.id = l.profile_id and p.is_active
   where l.verification_status = 'verificado' and l.is_available
     and not exists (select 1 from public.case_matches m where m.case_id = c.id and m.lawyer_id = l.profile_id)
   order by score desc
   limit p_limit
  on conflict (case_id, lawyer_id) do nothing;
  get diagnostics n = row_count;

  if n > 0 and c.status = 'aberto' then
    update public.cases set status = 'aguardando_advogado' where id = c.id;
  end if;
  return n;
end $$;

-- ao criar solicitação: registra evento e já direciona aos advogados
create function private.cases_after_insert() returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.case_events (case_id, actor_id, event_type, description)
    values (new.id, new.client_id, 'caso_criado', 'Solicitação criada pelo cliente');
  perform private.match_lawyers_for_case(new.id);
  return new;
end $$;
create trigger trg_cases_after_insert after insert on public.cases
  for each row execute function private.cases_after_insert();

-- regras de transição de status / quem pode editar o quê
create function private.cases_before_update() returns trigger language plpgsql set search_path = '' as $$
declare uid uuid := auth.uid();
begin
  if current_user = 'authenticated' and not private.is_admin() then
    if uid = old.client_id then
      if old.status in ('concluido','cancelado') then
        raise exception 'Solicitação encerrada não pode ser alterada';
      end if;
      if new.status is distinct from old.status and new.status <> 'cancelado' then
        raise exception 'O cliente só pode cancelar a solicitação';
      end if;
    elsif uid = old.assigned_lawyer_id then
      if (to_jsonb(new) - 'status' - 'updated_at' - 'closed_at') is distinct from (to_jsonb(old) - 'status' - 'updated_at' - 'closed_at') then
        raise exception 'O advogado só pode alterar o status do caso';
      end if;
      if old.status in ('concluido','cancelado') then
        raise exception 'Solicitação encerrada não pode ser alterada';
      end if;
      if new.status is distinct from old.status and new.status not in ('em_andamento','concluido') then
        raise exception 'Transição de status não permitida';
      end if;
    else
      raise exception 'Sem permissão para alterar esta solicitação';
    end if;
  end if;
  if new.status is distinct from old.status and new.status in ('concluido','cancelado') then
    new.closed_at := now();
  end if;
  return new;
end $$;
create trigger trg_cases_before_update before update on public.cases
  for each row execute function private.cases_before_update();

-- histórico + notificações + contador de casos concluídos
create function private.cases_after_update() returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.status is distinct from old.status then
    insert into public.case_events (case_id, actor_id, event_type, description, metadata)
      values (new.id, auth.uid(), 'status_alterado',
              'Status alterado de ' || old.status::text || ' para ' || new.status::text,
              jsonb_build_object('de', old.status, 'para', new.status));
    insert into public.notifications (user_id, type, title, body, data)
      select u, 'status_caso', 'Atualização na solicitação ' || new.protocol, 'Novo status: ' || new.status::text,
             jsonb_build_object('case_id', new.id)
        from unnest(array[new.client_id, new.assigned_lawyer_id]) as u
       where u is not null and u is distinct from auth.uid();
    if new.status = 'concluido' and new.assigned_lawyer_id is not null then
      update public.lawyers set cases_completed = cases_completed + 1 where profile_id = new.assigned_lawyer_id;
    end if;
  end if;
  return new;
end $$;
create trigger trg_cases_after_update after update on public.cases
  for each row execute function private.cases_after_update();

-- ========== MATCHES ==========
create function private.matches_after_insert() returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.notifications (user_id, type, title, body, data)
    select new.lawyer_id, 'novo_caso', 'Nova solicitação compatível com sua especialidade', c.title,
           jsonb_build_object('case_id', c.id, 'match_id', new.id)
      from public.cases c where c.id = new.case_id;
  return new;
end $$;
create trigger trg_matches_after_insert after insert on public.case_matches
  for each row execute function private.matches_after_insert();

create function private.matches_before_update() returns trigger language plpgsql set search_path = '' as $$
begin
  if new.status is distinct from old.status then new.responded_at := now(); end if;
  return new;
end $$;
create trigger trg_matches_before_update before update on public.case_matches
  for each row execute function private.matches_before_update();

-- advogado aceitou: atribui o caso (o primeiro que aceitar leva) e encerra as demais sugestões
create function private.match_accepted() returns trigger language plpgsql security definer set search_path = '' as $$
declare v_case public.cases%rowtype;
begin
  update public.cases set assigned_lawyer_id = new.lawyer_id, status = 'em_andamento'
   where id = new.case_id and assigned_lawyer_id is null and status in ('aberto','aguardando_advogado')
   returning * into v_case;
  if not found then
    raise exception 'Esta solicitação não está mais disponível';
  end if;

  update public.case_matches set status = 'expirado', responded_at = now()
   where case_id = new.case_id and id <> new.id and status = 'sugerido';

  insert into public.case_events (case_id, actor_id, event_type, description)
    values (new.case_id, new.lawyer_id, 'advogado_aceitou', 'Um advogado aceitou a solicitação');
  insert into public.notifications (user_id, type, title, body, data)
    values (v_case.client_id, 'advogado_aceitou', 'Um advogado aceitou sua solicitação', v_case.title,
            jsonb_build_object('case_id', v_case.id, 'lawyer_id', new.lawyer_id));
  return new;
end $$;
create trigger trg_match_accepted after update of status on public.case_matches
  for each row when (new.status = 'aceito' and old.status is distinct from 'aceito')
  execute function private.match_accepted();

-- ========== MENSAGENS ==========
create function private.message_after_insert() returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.notifications (user_id, type, title, body, data)
    select case when c.client_id = new.sender_id then c.assigned_lawyer_id else c.client_id end,
           'nova_mensagem', 'Nova mensagem na solicitação ' || c.protocol, left(new.body, 140),
           jsonb_build_object('case_id', c.id)
      from public.cases c
     where c.id = new.case_id
       and (case when c.client_id = new.sender_id then c.assigned_lawyer_id else c.client_id end) is not null;
  return new;
end $$;
create trigger trg_message_after_insert after insert on public.case_messages
  for each row execute function private.message_after_insert();

-- ========== HONORÁRIOS ==========
create function private.fee_before_update() returns trigger language plpgsql set search_path = '' as $$
begin
  if current_user = 'authenticated' then
    if old.status <> 'proposta' then
      raise exception 'Este acordo de honorários já foi respondido';
    end if;
    if new.status is distinct from old.status then
      if not private.is_case_client(new.case_id) then
        raise exception 'Somente o cliente pode aceitar ou recusar a proposta';
      end if;
      if (new.fee_type, new.amount, new.success_percent, new.notes) is distinct from (old.fee_type, old.amount, old.success_percent, old.notes) then
        raise exception 'Não é possível alterar valores ao responder a proposta';
      end if;
    elsif not private.is_case_lawyer(new.case_id) then
      raise exception 'Somente o advogado pode editar a proposta';
    end if;
  end if;
  if new.status = 'aceita' and old.status is distinct from 'aceita' then
    new.accepted_at := now();
  end if;
  return new;
end $$;
create trigger trg_fee_before_update before update on public.fee_agreements
  for each row execute function private.fee_before_update();

-- ========== AVALIAÇÕES: recalcula a nota do advogado ==========
create function private.reviews_after_write() returns trigger language plpgsql security definer set search_path = '' as $$
begin
  update public.lawyers l set
    avg_rating = coalesce((select round(avg(r.rating)::numeric, 2) from public.reviews r where r.lawyer_id = new.lawyer_id), 0),
    reviews_count = (select count(*) from public.reviews r where r.lawyer_id = new.lawyer_id)
   where l.profile_id = new.lawyer_id;
  return new;
end $$;
create trigger trg_reviews_after_write after insert or update on public.reviews
  for each row execute function private.reviews_after_write();

-- ========== RPCs PÚBLICAS (com checagem interna) ==========
create function public.admin_set_lawyer_verification(p_lawyer_id uuid, p_status public.lawyer_verification)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not private.is_admin() then raise exception 'Acesso negado'; end if;
  update public.lawyers
     set verification_status = p_status,
         verified_at = case when p_status = 'verificado' then now() else null end
   where profile_id = p_lawyer_id;
  if not found then raise exception 'Advogado não encontrado'; end if;
  insert into public.notifications (user_id, type, title, body)
    values (p_lawyer_id, 'verificacao_oab', 'Atualização da verificação da sua OAB', 'Novo status: ' || p_status::text);
end $$;

create function public.rematch_case(p_case_id uuid) returns int
language plpgsql security definer set search_path = '' as $$
begin
  if not (private.is_admin() or private.is_case_client(p_case_id)) then
    raise exception 'Acesso negado';
  end if;
  return private.match_lawyers_for_case(p_case_id);
end $$;

revoke execute on function public.admin_set_lawyer_verification(uuid, public.lawyer_verification) from public, anon;
revoke execute on function public.rematch_case(uuid) from public, anon;
grant execute on function public.admin_set_lawyer_verification(uuid, public.lawyer_verification) to authenticated;
grant execute on function public.rematch_case(uuid) to authenticated;

-- ========== PERMISSÕES NO SCHEMA private ==========
revoke all on all functions in schema private from public, anon, authenticated;
grant usage on schema private to authenticated;
grant execute on function
  private.is_admin(), private.is_lawyer(), private.is_client(),
  private.is_case_client(uuid), private.is_case_lawyer(uuid), private.is_case_party(uuid),
  private.is_case_participant(uuid), private.can_view_case(uuid), private.is_counterpart(uuid)
to authenticated;
