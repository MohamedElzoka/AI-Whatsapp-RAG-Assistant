# AI WhatsApp Customer Support Assistant

An AI-powered customer support assistant that talks to customers over **WhatsApp**,
answers questions using **Retrieval-Augmented Generation (RAG)** over your own
knowledge base, escalates to a human agent when it isn't confident, and gives
your team a **Streamlit admin dashboard** to manage documents, review
conversations, and monitor performance.

## Architecture

```
                          ┌─────────────────────┐
                          │   WhatsApp Cloud API  │
                          └──────────┬────────────┘
                                     │ webhook (HTTPS)
                                     ▼
   ┌────────────────────────────────────────────────────────────┐
   │                         Nginx (TLS)                          │
   └───────────────┬───────────────────────────────┬─────────────┘
                    │                               │
                    ▼                               ▼
        ┌───────────────────────┐        ┌───────────────────────┐
        │   FastAPI backend      │        │  Streamlit dashboard   │
        │  /webhook               │◄──────►│  (documents, convos,   │
        │  /documents/*           │  REST  │   analytics, feedback) │
        │  /conversations          │        └───────────────────────┘
        │  /analytics              │
        └───┬───────┬───────┬─────┘
            │        │       │
            ▼        ▼       ▼
       ┌────────┐┌───────┐┌─────────┐
       │Postgres││ Redis ││ Qdrant  │
       │(durable││(short-││(vector  │
       │ store) ││ term  ││ search) │
       │        ││memory)││         │
       └────────┘└───────┘└─────────┘
                    │
                    ▼
            ┌───────────────┐
            │  OpenAI API    │
            │ GPT-4o +       │
            │ text-embedding-│
            │ 3-small        │
            └───────────────┘
```

**Backend (FastAPI)**
- `POST/GET /webhook` — WhatsApp Cloud API verification + inbound message handling
- `POST /documents/upload` — upload PDF/DOCX/TXT into the knowledge base
- `POST /documents/reindex` — rebuild the entire vector index
- `GET /conversations`, `GET /conversations/{id}`, `POST /conversations/messages/{id}/feedback`
- `GET /analytics` — KPIs and timeseries for the dashboard

**Data layer**
- **PostgreSQL** — durable storage: `users`, `conversations`, `messages`, `feedback`, `documents`, `event_logs`
- **Redis** — short-term rolling conversation memory per customer (multi-turn context)
- **Qdrant** — vector store for semantic search over knowledge base chunks

**AI**
- **GPT-4o** generates grounded answers and a self-reported confidence score
- **text-embedding-3-small** embeds both knowledge base chunks and incoming questions

**Admin Dashboard (Streamlit)**
- Upload/manage knowledge base documents and trigger reindexing
- Browse full conversation threads, including escalations
- Analytics: messages, LLM requests, errors over time
- Customer feedback ratings

## Escalation logic

A conversation is escalated to a human agent (flagged in the dashboard, and
optionally pinged to an internal WhatsApp number) when **any** of the
following are true:

1. No knowledge base documents were found at all.
2. The best-matching chunk's similarity score is below `SIMILARITY_THRESHOLD`.
3. The LLM's own self-reported confidence is below `CONFIDENCE_ESCALATION_THRESHOLD`.

Both thresholds are configurable via environment variables.

## Quick start

> Full step-by-step instructions (including WhatsApp Cloud API setup) are in
> [`docs/SETUP.md`](docs/SETUP.md). This is the condensed version.

### 1. Prerequisites

- Docker and Docker Compose
- An OpenAI API key with access to `gpt-4o` and `text-embedding-3-small`
- A Meta developer account with a WhatsApp Cloud API app (for production use;
  you can develop locally with a test number first)

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `OPENAI_API_KEY`
- `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`
- `FIELD_ENCRYPTION_KEY` (generate with the command in the file's comments)
- `ADMIN_API_KEY`, `SECRET_KEY`, `POSTGRES_PASSWORD` (use strong random values)

### 3. TLS certificates

A self-signed certificate is already generated under `nginx/certs/` so you
can run everything locally out of the box. For production, replace it with a
real certificate (see `nginx/certs/README.md`) — **WhatsApp requires a
trusted certificate on your public webhook URL.**

### 4. Build and run

```bash
docker compose up --build -d
docker compose ps
```

This starts: `postgres`, `redis`, `qdrant`, `backend` (FastAPI), `dashboard`
(Streamlit), and `nginx` (TLS reverse proxy).

- Dashboard: `https://localhost/` (accept the self-signed cert warning locally)
- API docs (Swagger): `https://localhost/docs`
- Health check: `https://localhost/health`

### 5. Upload knowledge base documents

Open the dashboard → **Documents** page → upload a PDF/DOCX/TXT. It will be
chunked, embedded, and indexed into Qdrant automatically.

### 6. Connect WhatsApp

Expose your local server publicly (e.g. with `ngrok http 443` during
development) or deploy to a server with a real domain + certificate, then in
the Meta App Dashboard:

1. WhatsApp → Configuration → Webhook → set Callback URL to
   `https://<your-domain>/webhook` and Verify Token to your
   `WHATSAPP_VERIFY_TOKEN` value.
2. Subscribe to the `messages` webhook field.
3. Send a WhatsApp message to your test/business number and watch the
   conversation appear in the dashboard.

See `docs/SETUP.md` for the detailed walkthrough, including ngrok setup and
troubleshooting tips.

## Security notes

- All secrets (OpenAI key, WhatsApp token/app secret, DB password, encryption
  key, admin API key) are read from environment variables — never hardcoded.
- Inbound WhatsApp webhook requests are verified via HMAC-SHA256
  (`X-Hub-Signature-256`) using `WHATSAPP_APP_SECRET`.
- Dashboard-facing endpoints (`/documents/*`, `/conversations/*`,
  `/analytics`) require an `X-Admin-Api-Key` header matching `ADMIN_API_KEY`.
- `app/security.py` provides `encrypt_value` / `decrypt_value` (Fernet/AES)
  helpers for encrypting sensitive fields at rest if you extend the schema
  to store PII beyond phone numbers.
- All public traffic is terminated at Nginx over HTTPS; internal service-to-
  service traffic stays on the private Docker network.

## Project layout

```
ai-whatsapp-rag-assistant/
├── docker-compose.yml
├── .env.example
├── backend/                 # FastAPI service
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── security.py
│   │   ├── redis_client.py
│   │   ├── vectorstore.py
│   │   ├── routers/         # webhook, documents, conversations, analytics
│   │   ├── services/        # rag, llm, embeddings, whatsapp, escalation...
│   │   └── utils/logger.py
│   └── Dockerfile
├── dashboard/                # Streamlit admin dashboard
│   ├── app.py
│   ├── api_client.py
│   ├── pages/
│   └── Dockerfile
├── nginx/                    # TLS reverse proxy
│   ├── nginx.conf
│   └── certs/
└── docs/
    └── SETUP.md
```

## Tech stack

| Layer            | Technology                          |
|-------------------|--------------------------------------|
| Backend API        | FastAPI (Python)                    |
| Messaging channel   | WhatsApp Cloud API                  |
| LLM                | GPT-4o                              |
| Embeddings         | text-embedding-3-small              |
| Vector database    | Qdrant                              |
| Relational database| PostgreSQL                          |
| Conversation cache | Redis                               |
| Admin dashboard    | Streamlit                           |
| Deployment         | Docker + Docker Compose + Nginx     |

## License

This project is provided as a reference implementation. Adapt freely for
your own use.
