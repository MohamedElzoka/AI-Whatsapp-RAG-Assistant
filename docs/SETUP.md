# Setup Guide

This guide walks through installing, configuring, and running the AI
WhatsApp Customer Support Assistant from scratch, including connecting a
real WhatsApp Cloud API number.

## 1. Prerequisites

- Docker Engine 24+ and Docker Compose v2
- An [OpenAI](https://platform.openai.com) account with API access to
  `gpt-4o` and `text-embedding-3-small`
- A [Meta for Developers](https://developers.facebook.com) account
- (For local development) [ngrok](https://ngrok.com) or a similar tunnel,
  since WhatsApp requires a publicly reachable HTTPS webhook URL
- `openssl` (for generating local TLS certificates — usually pre-installed)

## 2. Clone and configure

```bash
cd ai-whatsapp-rag-assistant
cp .env.example .env
```

Open `.env` and fill in the required values. At minimum:

| Variable | How to get it |
|---|---|
| `OPENAI_API_KEY` | platform.openai.com → API Keys |
| `POSTGRES_PASSWORD` | choose a strong password |
| `SECRET_KEY`, `ADMIN_API_KEY` | any long random string (e.g. `openssl rand -hex 32`) |
| `FIELD_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `WHATSAPP_VERIFY_TOKEN` | any string you choose — you'll enter the same value in Meta's dashboard |

The WhatsApp-specific variables (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
`WHATSAPP_APP_SECRET`) come from the Meta App Dashboard — see step 5 below.
You can leave them blank to develop the RAG/document pipeline first and wire
up WhatsApp later.

## 3. TLS certificate

A self-signed certificate ships in `nginx/certs/` so `docker compose up`
works immediately. To regenerate it (e.g. for a different hostname):

```bash
cd nginx/certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout selfsigned.key -out selfsigned.crt -subj "/CN=localhost"
cd ../..
```

For a real deployment, replace these two files with a certificate from a
trusted CA (Let's Encrypt is free) — **Meta will refuse to deliver webhooks
to a self-signed certificate.**

## 4. Build and start all services

```bash
docker compose up --build -d
docker compose ps        # confirm all services are healthy
docker compose logs -f backend   # tail backend logs
```

Verify the backend is up:

```bash
curl -k https://localhost/health
# {"status":"ok","service":"AI WhatsApp Customer Support Assistant",...}
```

Open the dashboard in a browser: `https://localhost/` (your browser will
warn about the self-signed certificate locally — that's expected).

## 5. Upload your knowledge base

1. Go to the dashboard's **Documents** page.
2. Upload a PDF, DOCX, or TXT file containing your FAQs, policies, or
   product info.
3. Watch the status move from `pending` → `indexing` → `indexed`. If it
   shows `failed`, check the `error_message` column and the backend logs.
4. Use **Reindex entire knowledge base** any time you change chunking
   settings in `.env` (`CHUNK_SIZE`, `CHUNK_OVERLAP`) or want to rebuild from
   scratch.

You can test retrieval directly via the API docs at `https://localhost/docs`
before connecting WhatsApp.

## 6. Connect a WhatsApp Cloud API number

### 6.1 Create a Meta App

1. Go to [developers.facebook.com/apps](https://developers.facebook.com/apps) → **Create App** → choose **Business**.
2. Add the **WhatsApp** product to the app.
3. Under WhatsApp → **API Setup**, note your:
   - **Temporary access token** (or generate a permanent one via a System User — recommended for production)
   - **Phone number ID**
   - **WhatsApp Business Account ID**
4. Put these into `.env` as `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`.
5. Under App Settings → Basic, copy the **App Secret** into `WHATSAPP_APP_SECRET`.
6. Restart the backend to pick up the new values:
   ```bash
   docker compose restart backend
   ```

### 6.2 Expose your webhook publicly (development)

```bash
ngrok http https://localhost:443
```

Copy the `https://xxxx.ngrok-free.app` URL ngrok gives you.

(In production, point a real domain at your server's public IP instead of
using ngrok, and use a CA-signed certificate.)

### 6.3 Configure the webhook in Meta's dashboard

1. WhatsApp → **Configuration** → **Webhook** → **Edit**.
2. **Callback URL:** `https://<your-ngrok-or-domain>/webhook`
3. **Verify Token:** the exact value you set as `WHATSAPP_VERIFY_TOKEN`.
4. Click **Verify and Save** — the backend's `GET /webhook` handler will
   confirm the handshake.
5. Click **Manage** next to webhook fields and subscribe to **messages**.

### 6.4 Send a test message

From the **API Setup** page, send a test message to your own WhatsApp
number from the test business number (or, once approved, have a real
customer message your business number). Within a few seconds you should:

- See the message appear under the dashboard's **Conversations** page
- Receive an AI-generated reply on WhatsApp
- See the request reflected in **Analytics**

## 7. Tuning escalation behavior

In `.env`:

- `SIMILARITY_THRESHOLD` (default `0.55`) — minimum vector similarity for a
  retrieved chunk to be considered relevant. Raise it to be stricter about
  what counts as "found in the knowledge base."
- `CONFIDENCE_ESCALATION_THRESHOLD` (default `0.45`) — minimum LLM
  self-reported confidence before escalating to a human.
- `HUMAN_ESCALATION_PHONE` — optional WhatsApp number (no leading `+`) that
  receives an automatic notification whenever a conversation escalates.

After changing thresholds, restart the backend:
```bash
docker compose restart backend
```

## 8. Monitoring & logs

- Dashboard **Analytics** page: messages, LLM requests, errors, escalation
  rate, average confidence, average customer rating, all over a selectable
  time window.
- Raw logs: `docker compose logs -f backend` or the rotating file at
  `backend/logs/app.log` (mounted via the `backend_logs` volume).
- Every inbound message, LLM call, error, escalation, document index, and
  feedback submission is also recorded as a row in the `event_logs` table
  for ad-hoc SQL analysis.

## 9. Common issues

| Symptom | Likely cause |
|---|---|
| Webhook verification fails in Meta dashboard | `WHATSAPP_VERIFY_TOKEN` mismatch, or your URL isn't publicly reachable over HTTPS |
| `401 Invalid signature` in backend logs | `WHATSAPP_APP_SECRET` is wrong or missing |
| Dashboard shows "Failed to reach backend" | `ADMIN_API_KEY` mismatch between `.env` and the dashboard container, or backend isn't healthy yet |
| Document stuck on `failed` | Check `error_message` in the Documents table — usually an unsupported/corrupted file or an OpenAI API error (check `OPENAI_API_KEY`) |
| Replies never arrive on WhatsApp | Check `backend` logs for `httpx` errors — usually an expired/invalid `WHATSAPP_TOKEN` |
| Every message escalates | Knowledge base is empty, or `SIMILARITY_THRESHOLD` / `CONFIDENCE_ESCALATION_THRESHOLD` are set too high — upload documents and/or lower the thresholds |

## 10. Production checklist

- [ ] Use a permanent WhatsApp access token (System User), not the 24-hour temporary one
- [ ] Replace the self-signed certificate with a CA-signed one
- [ ] Set strong, unique values for `SECRET_KEY`, `ADMIN_API_KEY`, `FIELD_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`
- [ ] Restrict `CORS_ALLOW_ORIGINS` to your actual dashboard origin instead of `["*"]`
- [ ] Put Postgres/Redis/Qdrant volumes on durable, backed-up storage
- [ ] Set up log shipping/alerting on the `error_logs`/`event_logs` error rate
- [ ] Review Meta's WhatsApp Business Platform policies for production messaging limits and templates
