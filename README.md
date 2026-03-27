# CertiBot (SearchCertSystem)

Sistema interno para RH consultar certificações de colaboradores via chat, alimentado por PDFs no Google Drive e persistência no Supabase.

## Visão geral

O fluxo do MVP é:

1. **US002 (Drive Mapper)**: mapeia a estrutura do Google Drive (`Raiz → Colaborador → Certificação → PDFs`) e gera `output/us002.json`.
2. **US003 (PDF → Datas → Supabase)**: baixa cada PDF por `file_id`, extrai datas de **emissão** e **validade**, gera `output/us003.json` e (opcional) **faz upsert no Supabase**.
3. **US004 (FastAPI /chat)**: expõe um endpoint `POST /chat` e uma UI simples em `GET /` para consultas.
4. **Currículos**: o poller detecta PDFs de currículo (`curriculo/cv/resume`) na pasta do colaborador e persiste em `curriculos`.

## Stack

- **Python** (workers + API)
- **Google Drive API v3** (Service Account)
- **PyMuPDF** (extração de texto)
- **Supabase** (PostgreSQL + PostgREST)
- **FastAPI + Uvicorn** (API do chat)

## Estrutura do projeto

- `searchCertSystem/worker/us002/`: mapeamento Drive → `us002.json`
- `searchCertSystem/worker/us003/`: extração de datas + persistência → `us003.json` + Supabase
- `searchCertSystem/api/`: FastAPI (`GET /`, `POST /chat`)
- `searchCertSystem/supabase/schema.sql`: SQL do schema (US001)
- `output/`: arquivos gerados (ignorados no git)
- `credentials/`: credencial do Google (ignoradas no git)
- `docs/DOCUMENTACAO_TECNICA.md`: referência dos arquivos principais e responsabilidades

## Segurança (GitHub)

Este repositório **não deve** conter segredos.

- **Nunca comite** `.env` nem `credentials/`.
- Use `.env.example` como referência (sem chaves reais).

## Pré-requisitos

- Python 3.10+ (recomendado 3.11+)
- Acesso ao Google Cloud Console e Google Drive
- Projeto no Supabase

## Setup local

Na raiz do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Se o PowerShell bloquear ativação:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Variáveis de ambiente

Crie um arquivo `.env` na raiz (não comitar) baseado em `.env.example`.

### Google Drive

- `GOOGLE_DRIVE_ROOT_FOLDER_ID`: folderId da pasta raiz (ex.: pasta “Colaboradores”)
- `GOOGLE_SERVICE_ACCOUNT_FILE`: caminho do JSON da Service Account (ex.: `credentials/google-service-account.json`)
- `GOOGLE_DRIVE_INCLUDE_SHARED_DRIVES`: `true/false`

### Supabase (persistência US003)

- `SUPABASE_URL`: `https://SEU_PROJETO.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY`: chave **service_role** (para worker privado)
- `US003_PUSH_SUPABASE`: `true/false`

### API (US004)

- `API_PORT`: porta local da API (default sugerido: `8001`)

## Google Drive (Service Account)

1. No Google Cloud Console: **habilite a Google Drive API** no projeto da Service Account.
2. Baixe o JSON da Service Account e salve em `credentials/google-service-account.json`.
3. No Google Drive: compartilhe a pasta raiz (`GOOGLE_DRIVE_ROOT_FOLDER_ID`) com o `client_email` da Service Account (permissão de leitura suficiente para o MVP).

## Supabase (schema)

Abra o **SQL Editor** no Supabase e rode o arquivo:

- `searchCertSystem/supabase/schema.sql`

Ele cria:

- `public.colaboradores` (com `link_pasta` UNIQUE para upsert)
- `public.certificacoes` (FK + `pdf_file_id` UNIQUE para evitar duplicatas)
- `public.curriculos` (1 currículo vigente por colaborador, com `pdf_file_id`)
- `public.chat_logs` (auditoria de perguntas e respostas do `POST /chat`, com governança de entendimento)
- `public.chat_review_queue` (fila de revisão manual de perguntas/gaps)

### Auditoria de buscas do chat

Cada requisição ao `POST /chat` é registrada na tabela `public.chat_logs` com:

- pergunta original (`message`) e normalizada (`normalized_message`)
- intenção detectada (`intent`) e hints (`person_hint`, `cert_hint`)
- retorno (`answer`, `evidence`)
- status (`success`, `http_status`) e erro (`error_detail`, quando houver)
- governança: `question_fit_status` (`fit_answered`, `fit_no_data`, `fit_not_understood`, `out_of_scope`, `error`)
- sinalização de melhoria: `needs_knowledge_update`, `knowledge_gap_type`, `review_reason`

Consulta rápida:

```sql
select created_at, intent, success, http_status, message, answer
from public.chat_logs
order by created_at desc
limit 20;
```

### Monitorar entendimento e fila de revisão

- Taxa de entendimento e cobertura:

```sql
select question_fit_status, count(*)
from public.chat_logs
group by 1
order by 1;
```

- Pendências na fila de revisão:

```sql
select created_at, status, gap_type, message, intent, reason
from public.chat_review_queue
where status = 'open'
order by created_at desc
limit 50;
```

## US002 — Mapear Drive → `output/us002.json`

```powershell
py -m searchCertSystem.worker.us002 --out output\us002.json
```

## US003 — Extrair datas → `output/us003.json` (+ Supabase opcional)

Gerar somente o JSON:

```powershell
py -m searchCertSystem.worker.us003 --in output\us002.json --out output\us003.json --max-pages 3
```

Gerar JSON + enviar ao Supabase:

```powershell
py -m searchCertSystem.worker.us003 --in output\us002.json --out output\us003.json --max-pages 3 --push-supabase true
```

### Saída das datas

- `issue_date` / `expiry_date`: formato **BR** (`DD/MM/AAAA`) para visualização
- `issue_date_iso` / `expiry_date_iso`: formato **ISO** (`YYYY-MM-DD`) para persistência

## US004 — API do Chat (FastAPI)

Subir localmente:

```powershell
py -m uvicorn searchCertSystem.api.app:app --host 127.0.0.1 --port 8001 --reload
```

Acessar:

- UI do chat: `http://127.0.0.1:8001/`
- Healthcheck: `http://127.0.0.1:8001/health`

### Exemplos de perguntas suportadas (MVP)

- “Quais as certificações vigentes do João Silva?”
- “Joao silva tem cert ativa?”
- “Me mostre todos os funcionários com certificações ativas.”
- “Quantos POs certificados temos hoje?”
- “certicação de PO”
- “Quem tem certificação de PO?”
- “Existem POs com certificados expirados?”
- “Quais certificações do João Silva vencem este ano?”

Aliases iniciais:
 
- `Product Owner` ↔ `PO`
- `Scrum Master` ↔ `SM`

## Expor externamente (ngrok)

1) Suba a API aceitando conexões:

```powershell
py -m uvicorn searchCertSystem.api.app:app --host 0.0.0.0 --port 8001 --reload
```

2) Em outro terminal:

```powershell
ngrok http 8001
```

Abra a URL pública do ngrok e use `/` para a UI.

## Polling agendado (a cada 5 minutos)

Este modo executa automaticamente:

- US002 (Drive → `output/us002.json`)
- US003 (PDF → `output/us003.json`)
- **Persistência no Supabase** (upsert)

### Rodar uma vez (teste)

```powershell
py -m searchCertSystem.worker.poller --once
```

### Rodar continuamente (default 300s)

```powershell
py -m searchCertSystem.worker.poller
```

### Modo incremental (checkpoint)

Por padrão, o poller salva um checkpoint em `output/poller_checkpoint.json` com os `pdf_file_id` já persistidos com sucesso.
Nos próximos ciclos, ele **não reprocessa** PDFs já presentes no checkpoint.

Você pode trocar o arquivo:

```powershell
py -m searchCertSystem.worker.poller --checkpoint-file output\poller_checkpoint.json
```

### Ajustar intervalo (ex.: 5 minutos)

```powershell
py -m searchCertSystem.worker.poller --interval 300
```

Requisitos:

- `.env` com `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` configurados
- `.env` com credenciais do Google Drive (Service Account)

## Troubleshooting rápido

- **403 Google Drive**: Drive API desabilitada ou pasta não compartilhada com a Service Account.
- **400 Supabase on_conflict**: falta índice UNIQUE no campo de conflito (veja `schema.sql`).
- **POST /chat no navegador dá 405**: use a UI em `GET /` (não acesse `/chat` via GET).
