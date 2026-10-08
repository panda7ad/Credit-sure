begin;
create table if not exists public.credit_assessments (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    applicant_name text not null check (char_length(applicant_name) between 1 and 120),
    payload jsonb not null,
    result jsonb not null,
    created_at timestamptz not null default now()
);

create index if not exists credit_assessments_user_created_idx
    on public.credit_assessments (user_id, created_at desc);

alter table public.credit_assessments enable row level security;

revoke all on public.credit_assessments from anon, public, authenticated;
grant usage on schema public to authenticated;

drop policy if exists "Users can read their own assessments" on public.credit_assessments;
create policy "Users can read their own assessments"
    on public.credit_assessments for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can add their own assessments" on public.credit_assessments;
create policy "Users can add their own assessments"
    on public.credit_assessments for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can delete their own assessments" on public.credit_assessments;
create policy "Users can delete their own assessments"
    on public.credit_assessments for delete
    to authenticated
    using ((select auth.uid()) = user_id);

-- Upgrade: replace all previous policies, including any permissive custom policies.
do $$
declare p record;
begin
  for p in select policyname from pg_policies where schemaname='public' and tablename='credit_assessments'
  loop execute format('drop policy %I on public.credit_assessments', p.policyname); end loop;
end $$;
create policy "Owner read only" on public.credit_assessments for select to authenticated
  using ((select auth.uid()) = user_id and created_at > now() - interval '90 days');
grant select on public.credit_assessments to authenticated;
grant all on public.credit_assessments to service_role;

alter table public.credit_assessments add column if not exists request_id uuid;
alter table public.credit_assessments add column if not exists payload_sha256 text;
alter table public.credit_assessments add column if not exists model_version text;
create unique index if not exists assessment_request_unique on public.credit_assessments(user_id, request_id);

create table if not exists public.account_consents (
  user_id uuid not null references auth.users(id) on delete cascade,
  policy_version text not null check (char_length(policy_version) <= 64),
  accepted_at timestamptz not null default now(),
  primary key (user_id, policy_version)
);
create table if not exists public.assessment_usage (
  user_id uuid not null references auth.users(id) on delete cascade,
  usage_day date not null,
  count integer not null check (count between 0 and 100),
  primary key (user_id, usage_day)
);
alter table public.account_consents enable row level security;
alter table public.assessment_usage enable row level security;
revoke all on public.account_consents, public.assessment_usage from public, anon, authenticated;
grant all on public.account_consents, public.assessment_usage to service_role;

create or replace function public.accept_research_policy(p_user_id uuid, p_policy_version text)
returns void language plpgsql security invoker set search_path = '' as $$
begin
  if p_policy_version <> '2026-10-08-research-v1' then raise exception 'invalid_policy'; end if;
  insert into public.account_consents(user_id, policy_version) values(p_user_id, p_policy_version)
    on conflict do nothing;
end $$;
revoke all on function public.accept_research_policy(uuid,text) from public, anon, authenticated;
grant execute on function public.accept_research_policy(uuid,text) to service_role;

create or replace function public.save_research_assessment(
  p_user_id uuid, p_request_id uuid, p_payload_hash text, p_payload jsonb,
  p_result jsonb, p_model_version text
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare prior public.credit_assessments%rowtype;
declare used integer;
begin
  -- Serialize quota and idempotency decisions across every server instance.
  perform pg_advisory_xact_lock(hashtextextended(p_user_id::text, 0));
  select * into prior from public.credit_assessments where user_id=p_user_id and request_id=p_request_id;
  if found then
    if prior.payload_sha256 <> p_payload_hash then raise exception 'idempotency_conflict'; end if;
    return prior.result;
  end if;
  if not exists(select 1 from public.account_consents where user_id=p_user_id and policy_version='2026-10-08-research-v1')
    then raise exception 'consent_required'; end if;
  if p_payload_hash !~ '^[a-f0-9]{64}$' or p_model_version !~ '^[a-f0-9]{64}$'
      or jsonb_typeof(p_payload) <> 'object' or jsonb_typeof(p_result) <> 'object'
      or octet_length(p_payload::text) > 8192 or octet_length(p_result::text) > 8192
      or p_result->>'risk_band' not in ('LOW','MEDIUM','HIGH')
      or not (p_result ?& array['credit_score','default_probability','risk_band','key_factors'])
      or jsonb_typeof(p_result->'key_factors') <> 'array'
      then raise exception 'invalid_assessment'; end if;
  if (p_result->>'credit_score')::numeric not between 300 and 900
      or (p_result->>'default_probability')::numeric not between 0 and 1
      then raise exception 'invalid_assessment'; end if;
  select count into used from public.assessment_usage where user_id=p_user_id and usage_day=(now() at time zone 'UTC')::date;
  if coalesce(used,0) >= 100 or (select count(*) from public.credit_assessments where user_id=p_user_id) >= 500
    then raise exception 'quota_exceeded'; end if;
  insert into public.assessment_usage values(p_user_id, (now() at time zone 'UTC')::date, 1)
    on conflict(user_id,usage_day) do update set count=public.assessment_usage.count+1;
  insert into public.credit_assessments(user_id,applicant_name,payload,result,request_id,payload_sha256,model_version)
    values(p_user_id,p_payload->>'applicant_name',p_payload,p_result,p_request_id,p_payload_hash,p_model_version);
  return p_result;
end $$;
revoke all on function public.save_research_assessment(uuid,uuid,text,jsonb,jsonb,text) from public, anon, authenticated;
grant execute on function public.save_research_assessment(uuid,uuid,text,jsonb,jsonb,text) to service_role;

create or replace function public.research_schema_version()
returns integer language sql security invoker set search_path = '' as $$
  select case when not has_table_privilege('authenticated','public.credit_assessments','INSERT')
    and not has_table_privilege('authenticated','public.credit_assessments','UPDATE')
    and not has_table_privilege('authenticated','public.credit_assessments','DELETE')
    and not has_function_privilege('authenticated','public.save_research_assessment(uuid,uuid,text,jsonb,jsonb,text)','EXECUTE')
    and not has_function_privilege('anon','public.save_research_assessment(uuid,uuid,text,jsonb,jsonb,text)','EXECUTE')
    and not has_function_privilege('authenticated','public.accept_research_policy(uuid,text)','EXECUTE')
    and not has_function_privilege('anon','public.accept_research_policy(uuid,text)','EXECUTE')
    and not has_table_privilege('anon','public.credit_assessments','SELECT')
    and (select relrowsecurity from pg_class where oid='public.credit_assessments'::regclass)
    then 2 else 0 end;
$$;
revoke all on function public.research_schema_version() from public, anon, authenticated;
grant execute on function public.research_schema_version() to service_role;

create or replace function public.purge_expired_research()
returns void language sql security invoker set search_path = '' as $$
  delete from public.credit_assessments where created_at < now() - interval '90 days';
  delete from public.assessment_usage where usage_day < (now() at time zone 'UTC')::date - 2;
$$;
revoke all on function public.purge_expired_research() from public, anon, authenticated;
grant execute on function public.purge_expired_research() to service_role;
commit;
