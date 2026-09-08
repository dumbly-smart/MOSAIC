-- MOSAIC Supabase schema: cases, private documents, verification records and BGE-M3 vectors.
create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create table if not exists public.cases (
    id uuid primary key,
    created_by uuid not null references auth.users(id) on delete restrict,
    tender_title text not null check (char_length(tender_title) between 3 and 200),
    description text check (description is null or char_length(description) <= 2000),
    status text not null default 'draft'
        check (status in ('draft', 'processing', 'ready_for_review', 'closed')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.documents (
    id uuid primary key,
    case_id uuid not null references public.cases(id) on delete cascade,
    created_by uuid not null references auth.users(id) on delete restrict,
    kind text not null check (kind in ('tender', 'bidder')),
    bucket text not null,
    object_path text not null,
    original_filename text not null,
    content_type text not null,
    size_bytes bigint not null check (size_bytes > 0),
    sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
    processing_status text not null default 'uploaded'
        check (processing_status in ('uploaded', 'processing', 'ready', 'failed')),
    created_at timestamptz not null default now(),
    unique (bucket, object_path)
);

create table if not exists public.verification_runs (
    id uuid primary key,
    case_id uuid not null references public.cases(id) on delete cascade,
    created_by uuid not null references auth.users(id) on delete restrict,
    status text not null default 'queued'
        check (status in ('queued', 'running', 'completed', 'failed', 'needs_manual_review')),
    policy_version text not null,
    score integer check (score between 0 and 100),
    result jsonb,
    error_message text,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz
);

create table if not exists public.criteria (
    id uuid primary key,
    verification_run_id uuid not null references public.verification_runs(id) on delete cascade,
    criterion_id text not null,
    rule_version text not null,
    definition jsonb not null,
    created_at timestamptz not null default now(),
    unique (verification_run_id, criterion_id)
);

create table if not exists public.findings (
    id uuid primary key,
    verification_run_id uuid not null references public.verification_runs(id) on delete cascade,
    criterion_id text not null,
    status text not null,
    severity text not null,
    earned_points numeric not null default 0,
    explanation text not null,
    evidence jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.document_chunks (
    id text primary key,
    document_id uuid not null references public.documents(id) on delete cascade,
    corpus_hash text not null,
    embedding_model text not null,
    page_number integer not null check (page_number > 0),
    line_number integer check (line_number is null or line_number > 0),
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    embedding extensions.vector(1024) not null,
    created_at timestamptz not null default now(),
    unique (corpus_hash, embedding_model, id)
);

create index if not exists document_chunks_embedding_hnsw
    on public.document_chunks using hnsw (embedding extensions.vector_cosine_ops);
create index if not exists documents_case_id_idx on public.documents(case_id);
create index if not exists verification_runs_case_id_idx on public.verification_runs(case_id);
create index if not exists findings_run_id_idx on public.findings(verification_run_id);

create table if not exists public.audit_events (
    id uuid primary key,
    case_id uuid not null references public.cases(id) on delete restrict,
    actor_id uuid not null references auth.users(id) on delete restrict,
    event_type text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create or replace function public.prevent_audit_mutation()
returns trigger language plpgsql as $$
begin
    raise exception 'audit_events is append-only';
end;
$$;

drop trigger if exists audit_events_no_update on public.audit_events;
create trigger audit_events_no_update before update or delete on public.audit_events
for each row execute function public.prevent_audit_mutation();

alter table public.cases enable row level security;
alter table public.documents enable row level security;
alter table public.verification_runs enable row level security;
alter table public.criteria enable row level security;
alter table public.findings enable row level security;
alter table public.document_chunks enable row level security;
alter table public.audit_events enable row level security;

drop policy if exists "officers manage own cases" on public.cases;
create policy "officers manage own cases" on public.cases
for all to authenticated using (created_by = auth.uid()) with check (created_by = auth.uid());

drop policy if exists "officers manage own documents" on public.documents;
create policy "officers manage own documents" on public.documents
for all to authenticated
using (created_by = auth.uid())
with check (created_by = auth.uid() and exists (
    select 1 from public.cases c where c.id = case_id and c.created_by = auth.uid()
));

drop policy if exists "officers manage own runs" on public.verification_runs;
create policy "officers manage own runs" on public.verification_runs
for all to authenticated
using (created_by = auth.uid())
with check (created_by = auth.uid() and exists (
    select 1 from public.cases c where c.id = case_id and c.created_by = auth.uid()
));

drop policy if exists "officers read own criteria" on public.criteria;
create policy "officers read own criteria" on public.criteria
for select to authenticated using (exists (
    select 1 from public.verification_runs r
    where r.id = verification_run_id and r.created_by = auth.uid()
));

drop policy if exists "officers read own findings" on public.findings;
create policy "officers read own findings" on public.findings
for select to authenticated using (exists (
    select 1 from public.verification_runs r
    where r.id = verification_run_id and r.created_by = auth.uid()
));

drop policy if exists "officers read own chunks" on public.document_chunks;
create policy "officers read own chunks" on public.document_chunks
for select to authenticated using (exists (
    select 1 from public.documents d where d.id = document_id and d.created_by = auth.uid()
));

drop policy if exists "officers read own audit" on public.audit_events;
create policy "officers read own audit" on public.audit_events
for select to authenticated using (exists (
    select 1 from public.cases c where c.id = case_id and c.created_by = auth.uid()
));

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('mosaic-documents', 'mosaic-documents', false, 52428800, array['application/pdf'])
on conflict (id) do update set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "officers upload to own storage folder" on storage.objects;
create policy "officers upload to own storage folder" on storage.objects
for insert to authenticated with check (
    bucket_id = 'mosaic-documents' and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists "officers read own storage folder" on storage.objects;
create policy "officers read own storage folder" on storage.objects
for select to authenticated using (
    bucket_id = 'mosaic-documents' and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists "officers delete own storage files" on storage.objects;
create policy "officers delete own storage files" on storage.objects
for delete to authenticated using (
    bucket_id = 'mosaic-documents' and (storage.foldername(name))[1] = auth.uid()::text
);
