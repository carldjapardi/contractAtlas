-- Server-side run persistence. Apply with a privileged database migration user.
-- No browser/public policies: only the backend service_role may use this data.
begin;

create table if not exists public.atlas_runs (
  id text primary key check (id ~ '^[a-f0-9]{32}$'),
  status text not null check (status in ('queued', 'running', 'awaiting_review', 'improving', 'complete', 'error')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  document jsonb not null check (jsonb_typeof(document) = 'object'),
  constraint atlas_runs_document_id_matches check (document ->> 'id' is not null and document ->> 'id' = id),
  constraint atlas_runs_document_status_matches check (document ->> 'status' is not null and document ->> 'status' = status)
);
create index if not exists atlas_runs_created_at_idx on public.atlas_runs (created_at desc, id desc);
create index if not exists atlas_runs_active_idx on public.atlas_runs (status) where status in ('queued', 'running', 'improving');

create table if not exists public.atlas_manifests (
  key text primary key check (length(key) between 1 and 200),
  updated_at timestamptz not null default now(),
  document jsonb not null check (jsonb_typeof(document) = 'object')
);

alter table public.atlas_runs enable row level security;
alter table public.atlas_manifests enable row level security;
revoke all on public.atlas_runs from public, anon, authenticated;
revoke all on public.atlas_manifests from public, anon, authenticated;
grant select, insert, update on public.atlas_runs to service_role;
grant select, insert, update on public.atlas_manifests to service_role;

create or replace function public.atlas_create_run(p_document jsonb)
returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
  inserted_count integer;
begin
  if p_document ->> 'status' is distinct from 'queued' then
    raise exception 'New research runs must be queued' using errcode = '22023';
  end if;
  -- Both admission functions use this transaction-scoped advisory lock. It
  -- coordinates across HTTP requests, worker processes and serverless instances.
  perform pg_catalog.pg_advisory_xact_lock(724043551112411::bigint);
  if exists (select 1 from public.atlas_runs where status in ('queued', 'running', 'improving')) then
    return false;
  end if;
  insert into public.atlas_runs (id, status, created_at, updated_at, document)
  values (p_document ->> 'id', 'queued', (p_document ->> 'created_at')::timestamptz,
          (p_document ->> 'updated_at')::timestamptz, p_document)
  on conflict (id) do nothing;
  get diagnostics inserted_count = row_count;
  return inserted_count = 1;
end;
$$;
revoke all on function public.atlas_create_run(jsonb) from public, anon, authenticated;
grant execute on function public.atlas_create_run(jsonb) to service_role;

create or replace function public.atlas_claim_run(
  p_run_id text,
  p_expected_statuses text[],
  p_next_status text
) returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  result jsonb;
  changed_at timestamptz := clock_timestamp();
begin
  if p_next_status = any(p_expected_statuses) then
    raise exception 'A claim must change run status' using errcode = '22023';
  end if;
  perform pg_catalog.pg_advisory_xact_lock(724043551112411::bigint);
  if p_next_status in ('queued', 'running', 'improving') and exists (
    select 1 from public.atlas_runs
    where id <> p_run_id and status in ('queued', 'running', 'improving')
  ) then
    return null;
  end if;
  -- One UPDATE is a compare-and-set under concurrent transactions: the losing
  -- caller rechecks the status predicate after obtaining the row lock.
  update public.atlas_runs
  set status = p_next_status,
      updated_at = changed_at,
      document = jsonb_set(jsonb_set(document, '{status}', to_jsonb(p_next_status)),
                           '{updated_at}', to_jsonb(changed_at))
  where id = p_run_id and status = any(p_expected_statuses)
  returning document into result;
  return result;
end;
$$;
revoke all on function public.atlas_claim_run(text, text[], text) from public, anon, authenticated;
grant execute on function public.atlas_claim_run(text, text[], text) to service_role;

notify pgrst, 'reload schema';
commit;
