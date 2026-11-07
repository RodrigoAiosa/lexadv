-- Cadastro: estado e cidade para todos; OAB (número + UF) obrigatória para advogados.
-- A regra fica no banco para valer também para chamadas diretas à API de autenticação.
create or replace function private.handle_new_user() returns trigger language plpgsql security definer set search_path = '' as $$
declare
  v_role public.user_role;
  v_meta jsonb := coalesce(new.raw_user_meta_data, '{}'::jsonb);
  v_state text := upper(nullif(btrim(v_meta->>'state'), ''));
  v_city text := left(nullif(btrim(v_meta->>'city'), ''), 120);
  v_oab text := upper(regexp_replace(coalesce(v_meta->>'oab_number', ''), '[\s.\-]', '', 'g'));
  v_oab_state text := upper(nullif(btrim(v_meta->>'oab_state'), ''));
begin
  -- só é possível se cadastrar como cliente ou advogado; admin é definido manualmente
  v_role := case when v_meta->>'role' = 'advogado' then 'advogado'::public.user_role else 'cliente'::public.user_role end;
  if v_state is not null and v_state !~ '^[A-Z]{2}$' then v_state := null; end if;

  if v_role = 'advogado' then
    if v_oab !~ '^[0-9]{1,7}[A-Z]?$' or v_oab_state is null or v_oab_state !~ '^[A-Z]{2}$' then
      raise exception 'Número e UF da OAB são obrigatórios para advogados' using errcode = '23514';
    end if;
  end if;

  insert into public.profiles (id, role, full_name)
    values (new.id, v_role, coalesce(v_meta->>'full_name', ''));
  insert into public.profile_private (profile_id, email, phone)
    values (new.id, new.email, v_meta->>'phone');

  if v_role = 'cliente' then
    insert into public.clients (profile_id, city, state) values (new.id, v_city, v_state);
  else
    insert into public.lawyers (profile_id, oab_number, oab_state, city, state)
      values (new.id, v_oab, v_oab_state, v_city, v_state);
  end if;
  return new;
end $$;
