-- US001 - Schema inicial (Supabase / PostgreSQL)
-- Tabelas:
-- - colaboradores(id, nome, link_pasta)
-- - certificacoes(id, colaborador_id, nome_certificado, data_emissao, data_validade, link_pdf)
--
-- Notas de robustez para o worker:
-- - `link_pasta` armazena o folderId do Drive (ou URL) e é UNIQUE para permitir upsert do colaborador.
-- - `pdf_file_id` ajuda a evitar duplicatas do mesmo PDF no Drive (UNIQUE).

create extension if not exists "pgcrypto";

create table if not exists public.colaboradores (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  link_pasta text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Se a tabela já existia (schema antigo), garante a coluna necessária
alter table public.colaboradores
  add column if not exists link_pasta text;

create unique index if not exists colaboradores_link_pasta_uq
  on public.colaboradores (link_pasta);

create table if not exists public.certificacoes (
  id uuid primary key default gen_random_uuid(),
  colaborador_id uuid not null references public.colaboradores(id) on delete cascade,
  nome_certificado text not null,
  data_emissao date null,
  data_validade date null,
  link_pdf text not null,
  -- campos extras para evitar duplicação e facilitar auditoria
  pdf_file_id text null,
  pdf_file_name text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Se a tabela já existia (schema antigo), garante colunas novas
alter table public.certificacoes
  add column if not exists pdf_file_id text;
alter table public.certificacoes
  add column if not exists pdf_file_name text;

create unique index if not exists certificacoes_pdf_file_id_uq
  on public.certificacoes (pdf_file_id);

create index if not exists certificacoes_colaborador_id_idx
  on public.certificacoes (colaborador_id);

create index if not exists certificacoes_nome_certificado_idx
  on public.certificacoes (nome_certificado);

-- Currículo (1 atual por colaborador, com rastreio do PDF)
create table if not exists public.curriculos (
  id uuid primary key default gen_random_uuid(),
  colaborador_id uuid not null references public.colaboradores(id) on delete cascade,
  link_pdf text not null,
  pdf_file_id text null,
  pdf_file_name text null,
  updated_at timestamptz not null default now()
);

alter table public.curriculos
  add column if not exists pdf_file_id text;
alter table public.curriculos
  add column if not exists pdf_file_name text;
alter table public.curriculos
  add column if not exists updated_at timestamptz not null default now();

-- Um currículo "vigente" por colaborador (upsert por colaborador_id)
create unique index if not exists curriculos_colaborador_id_uq
  on public.curriculos (colaborador_id);

-- Evita duplicidade de mesmo arquivo em colaboradores distintos
create unique index if not exists curriculos_pdf_file_id_uq
  on public.curriculos (pdf_file_id);

-- Auditoria do chat (pergunta -> retorno)
create table if not exists public.chat_logs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  message text not null,
  normalized_message text null,
  intent text null,
  person_hint text null,
  cert_hint text null,
  answer text null,
  evidence jsonb null,
  success boolean not null default false,
  http_status integer not null,
  error_detail text null,
  -- governança de perguntas
  question_fit_status text not null default 'unknown',
  needs_knowledge_update boolean not null default false,
  knowledge_gap_type text null,
  review_reason text null
);

create index if not exists chat_logs_created_at_idx
  on public.chat_logs (created_at desc);

create index if not exists chat_logs_intent_idx
  on public.chat_logs (intent);

create index if not exists chat_logs_success_idx
  on public.chat_logs (success);

create index if not exists chat_logs_question_fit_status_idx
  on public.chat_logs (question_fit_status);

create index if not exists chat_logs_needs_knowledge_update_idx
  on public.chat_logs (needs_knowledge_update);

-- Fila de revisão manual de perguntas
create table if not exists public.chat_review_queue (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  chat_log_id uuid not null references public.chat_logs(id) on delete cascade,
  message text not null,
  intent text null,
  gap_type text not null,
  reason text null,
  status text not null default 'open', -- open | approved | rejected | done
  owner text null,
  resolution_note text null
);

create index if not exists chat_review_queue_status_created_at_idx
  on public.chat_review_queue (status, created_at desc);

