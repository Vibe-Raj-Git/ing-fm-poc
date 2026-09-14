# ING Financial Markets AI Agentic Platform — Operational Runbook

**Version:** 14 September 2026
**Status:** Authoritative
**Supersedes:** Previous `runbook (1).md`

---

## 1. Quick Start

For a new Cloud Shell session, run:

```bash
cd ~/ing-fm-poc
source ./session-init.sh
```

`session-init.sh` handles:

1. GCP authentication check (runs `gcloud auth login` if needed)
2. Project and region configuration
3. DB password retrieval from Secret Manager
4. Cloud SQL connection string resolution
5. Cloud SQL Auth Proxy startup on `127.0.0.1:5432`
6. Database connectivity verification
7. Environment banner with current service URL

After `session-init.sh` completes, all required environment variables are exported and the proxy is running. You can immediately run `deploy-poc` or run local Python scripts that connect via `127.0.0.1:5432`.

---

## 2. System Persistence Model

| Layer | Persistence |
|---|---|
| **Cloud SQL data** | Permanent. Schemas and pgvector embeddings persist across sessions. |
| **Cloud Run service** | Permanent. Scales to zero when idle. |
| **Cloud Shell workspace** | Persistent `$HOME` disk (`~/ing-fm-poc`) across sessions. |
| **Environment variables** | Reset on session expiry. `session-init.sh` re-exports them. |
| **GCP credentials** | Cached in Cloud Shell. Active account may need re-selection. |

`session-init.sh` handles the re-selection and re-export automatically.

---

## 3. Environment Reference

After `session-init.sh` runs, these variables are available:

| Variable | Value |
|---|---|
| `GCP_PROJECT` | `dulcet-radar-508218-c5` |
| `REGION` | `europe-west1` |
| `SQL_INSTANCE` | `ing-postgres-db` |
| `INSTANCE_CONN` | `dulcet-radar-508218-c5:europe-west1:ing-postgres-db` |
| `DB_USER` | `postgres` |
| `DB_NAME` | `postgres` |
| `DB_PASS` | Retrieved from Secret Manager (`db-postgres-pass`) |
| `SERVICE_URL` | Resolved from Cloud Run service |

**Never hardcode `DB_PASS` in any file.** It lives only in Secret Manager. The session-init script retrieves it at runtime.

---

## 4. Preflight Validation

Run after `session-init.sh`:

```bash
# Cloud SQL status
gcloud sql instances describe "$SQL_INSTANCE" \
  --format="value(state,settings.activationPolicy)"

# Cloud Run URL
gcloud run services describe ing-fm-poc-service \
  --region "$REGION" \
  --project "$GCP_PROJECT" \
  --format="value(status.url)"

# Local proxy is alive?
pgrep -f "cloud-sql-proxy" >/dev/null && echo "✓ proxy running" || echo "✗ proxy not running"
```

Expected Cloud SQL state: `RUNNABLE ALWAYS`

If state is `RUNNABLE NEVER` or `STOPPED NEVER`, see §5.

---

## 5. Cloud SQL Lifecycle

### 5.1 Check status

```bash
gcloud sql instances describe "$SQL_INSTANCE" \
  --format="value(state,settings.activationPolicy)"
```

### 5.2 Start

```bash
gcloud sql instances patch "$SQL_INSTANCE" \
  --activation-policy=ALWAYS
```

Wait for `RUNNABLE` before running application code.

### 5.3 Stop (cost control)

```bash
gcloud sql instances patch "$SQL_INSTANCE" \
  --activation-policy=NEVER
```

Data, schemas, and pgvector embeddings persist while the instance is stopped.

---

## 6. Codebase Structure

| File | Purpose |
|---|---|
| `main.py` | FastAPI backend — all API endpoints |
| `pitchbook_builder.py` | PPTX generation (python-pptx) |
| `frontend/src/App.jsx` | React workspace (dashboard, cards, modal, copilot) |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Two-stage build (node → python) |
| `session-init.sh` | Environment bootstrap |
| `test_parity.py` | 13-gate parity audit |

Historical or scratch files (not used by the running service) may exist in the working tree (`main_14Sep*.py`, `App_*.jsx`, `.bak.*` files). They are excluded from the Docker image by the Dockerfile's explicit `COPY` statements.

---

## 7. Code Change Workflow

### 7.1 For any change to `main.py`, `pitchbook_builder.py`, or `frontend/src/App.jsx`

```bash
cd ~/ing-fm-poc
deploy-poc
```

`deploy-poc` is a bash alias that runs:

```bash
gcloud run deploy ing-fm-poc-service \
  --source . \
  --project="dulcet-radar-508218-c5" \
  --region="europe-west1" \
  --set-env-vars="INSTANCE_CONNECTION_NAME=dulcet-radar-508218-c5:europe-west1:ing-postgres-db,DB_USER=postgres,DB_NAME=postgres,GCP_PROJECT=dulcet-radar-508218-c5,REGION=europe-west1" \
  --set-secrets="DB_PASS=db-postgres-pass:latest" \
  --quiet
```

The Dockerfile builds the React frontend in stage 1 (node:20-alpine), then installs Python deps and copies the backend in stage 2 (python:3.11-slim). The container listens on port **8080**.

Deploy takes ~5 minutes.

### 7.2 Pre-deploy checks (optional but recommended)

```bash
# Python syntax
python3 -c "import ast; ast.parse(open('main.py').read())" && \
python3 -c "import ast; ast.parse(open('pitchbook_builder.py').read())" && \
echo "✓ Python files parse"

# JSX brace balance (rough sanity)
python3 -c "
js = open('frontend/src/App.jsx').read()
o, c = js.count('{'), js.count('}')
assert o == c, f'Brace mismatch: {o} vs {c}'
print(f'✓ JSX braces balanced ({o})')
"

# Parity audit (requires proxy + DB)
python3 test_parity.py
```

---

## 8. Deployment Details

| Setting | Value |
|---|---|
| Service name | `ing-fm-poc-service` |
| Project | `dulcet-radar-508218-c5` |
| Region | `europe-west1` |
| Port | `8080` |
| CPU | 1 vCPU (1000m) |
| Memory | 512 MiB |
| Min instances | 1 |
| Max instances | 1 |
| Env vars | `INSTANCE_CONNECTION_NAME`, `DB_USER`, `DB_NAME`, `GCP_PROJECT`, `REGION` |
| Secrets | `DB_PASS` from `db-postgres-pass:latest` |

**Why min/max = 1:** the mandate synthesis cache (`_MANDATE_SYNTH_CACHE`) is in-memory. Multiple instances would each have their own empty cache.

---

## 9. Post-Deploy Verification

### 9.1 Confirm the new revision is serving

```bash
gcloud run revisions list \
  --service ing-fm-poc-service \
  --region europe-west1 \
  --project dulcet-radar-508218-c5 \
  --limit 3 \
  --format "table(metadata.name, metadata.creationTimestamp)"
```

The top row should have a timestamp from the last few minutes.

### 9.2 Refresh the service URL

```bash
export SERVICE_URL=$(gcloud run services describe ing-fm-poc-service \
  --region europe-west1 \
  --project dulcet-radar-508218-c5 \
  --format "value(status.url)")
echo "$SERVICE_URL"
```

### 9.3 Warm the cache and verify

```bash
# First call — cache miss, synthesis runs (~5s)
time curl -s "$SERVICE_URL/api/opportunities" > /dev/null

# Second call — cache hit (~1s)
time curl -s "$SERVICE_URL/api/opportunities" > /dev/null

# Confirm the whitelisted client renders
curl -s "$SERVICE_URL/api/opportunities" | python3 -c "
import json, sys
for o in json.load(sys.stdin):
    if o.get('id') == 'CLI101':
        print(f\"Client: {o.get('name')}\")
        print(f\"RM:     {o.get('rm_name')}\")
        print(f\"Action: {(o.get('action') or '')[:150]}\")
        break
"
```

Expected:
- First request 5-6s
- Second request <1.5s
- Enel (CLI101) appears with Giulia Romano and the anchored mandate narrative

### 9.4 Health endpoint

**There is no working `/health` or `/healthz` endpoint.** Cloud Run intercepts `/healthz` and returns its own 404. Use `/api/opportunities` for reachability checks.

```bash
curl -s -o /dev/null -w "GET /api/opportunities → HTTP %{http_code}\n" "$SERVICE_URL/api/opportunities"
```

Expected: `HTTP 200`.

---

## 10. Public Access Management

The service is deployed with public IAM access (`allUsers` granted `roles/run.invoker`).

### 10.1 Disable public access

```bash
gcloud run services remove-iam-policy-binding ing-fm-poc-service \
  --region=europe-west1 \
  --project=dulcet-radar-508218-c5 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

### 10.2 Re-enable public access

```bash
gcloud run services add-iam-policy-binding ing-fm-poc-service \
  --region=europe-west1 \
  --project=dulcet-radar-508218-c5 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

---

## 11. Logs

### 11.1 Recent logs

```bash
gcloud run services logs read ing-fm-poc-service \
  --region europe-west1 \
  --project dulcet-radar-508218-c5 \
  --limit 100
```

### 11.2 Filter for specific messages

```bash
# Cache behavior
gcloud run services logs read ing-fm-poc-service \
  --region europe-west1 \
  --project dulcet-radar-508218-c5 \
  --limit 100 | grep -iE 'cache|synthesis|drift'

# Errors
gcloud run services logs read ing-fm-poc-service \
  --region europe-west1 \
  --project dulcet-radar-508218-c5 \
  --limit 100 | grep -iE 'error|exception'
```

Expected healthy synthesis pattern:

```
Mandate synthesis cache MISS for CLI101, refreshed (TTL 300s)
Persisted fresh synthesis for CLI101
Mandate synthesis cache HIT for CLI101
```

---

## 12. Local Development

The Cloud Shell workspace connects to Cloud SQL via the Cloud SQL Auth Proxy on `127.0.0.1:5432`. This proxy is started by `session-init.sh`.

Local Python scripts use:

```python
import os, pg8000.native
conn = pg8000.native.Connection(
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASS"],
    host="127.0.0.1",
    port=5432,
    database=os.environ["DB_NAME"],
)
```

Running the FastAPI app locally (not required for the deploy workflow) would need the proxy and the same env vars.

---

## 13. Cost-Control Shutdown

When the POC is not in use:

```bash
gcloud sql instances patch "$SQL_INSTANCE" \
  --activation-policy=NEVER
```

Verify:

```bash
gcloud sql instances describe "$SQL_INSTANCE" \
  --format="value(state,settings.activationPolicy)"
```

Desired inactive state: `STOPPED NEVER`.

Cloud Run scales to zero when idle, so it can stay deployed.

---

## 14. Current Architecture

```
                  Google Cloud (dulcet-radar-508218-c5)
                                │
                ┌───────────────┴───────────────┐
                │                               │
            Cloud Run                       Vertex AI
        ing-fm-poc-service            gemini-2.5-flash
        (React + FastAPI)             text-embedding-004
        port 8080                            │
                │                            │
                └────────────┬───────────────┘
                             │
                        Cloud SQL
                   ing-postgres-db
              PostgreSQL 15 + pgvector
                             │
              ┌──────────────┴──────────────┐
              │                             │
      Relational tables              Vector chunks
      (ca schema, 12 tables)      (ca.document_vector_chunks)
```

**Request flow:**

```
Browser → Cloud Run (React SPA + FastAPI)
             │
             ├─ /api/opportunities → Cloud SQL joins → Gemini synthesis (whitelisted)
             ├─ /api/signals       → Cloud SQL query (filtered to _DEMO_CLIENT_IDS)
             ├─ /api/copilot/chat  → Gemini with hydrated deck state
             ├─ /api/check-compliance → Gemini audit
             └─ /api/pitchbook/generate → python-pptx build
```

---

## 15. Troubleshooting

### 15.1 First page load takes >20 seconds

Possible causes:

1. **Container cold start** — check min-instances:
   ```bash
   gcloud run services describe ing-fm-poc-service \
     --region europe-west1 \
     --project dulcet-radar-508218-c5 \
     --format "value(spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])"
   ```
   Expected: `1`. If empty, run:
   ```bash
   gcloud run services update ing-fm-poc-service \
     --region europe-west1 \
     --project dulcet-radar-508218-c5 \
     --min-instances=1
   ```

2. **Cache is cold** — warm it:
   ```bash
   curl -s "$SERVICE_URL/api/opportunities" > /dev/null
   ```

3. **Synthesis is failing** — check logs for `Dynamic synthesis skipped` or `Tenor drift detected`.

### 15.2 DB connection fails from Cloud Shell

```bash
# Is the proxy running?
pgrep -f cloud-sql-proxy

# Test connection
python3 -c "
import os, pg8000.native
conn = pg8000.native.Connection(
    user=os.environ['DB_USER'], password=os.environ['DB_PASS'],
    host='127.0.0.1', port=5432, database=os.environ['DB_NAME']
)
print('✓ DB OK')
conn.close()
"
```

If the proxy isn't running, re-run `source ./session-init.sh`.

### 15.3 Deploy fails with "container failed to start"

Check the Cloud Build logs (URL printed by `deploy-poc`) or:

```bash
gcloud builds list --project dulcet-radar-508218-c5 --limit 5
```

Common causes: Python syntax error, missing dependency in `requirements.txt`, or a `COPY` statement in the Dockerfile pointing at a nonexistent file.

---

## 16. Operational Principle

- **Cloud Shell** is the development workspace.
- **Cloud Run** is the deployed application runtime.
- **Cloud SQL** is the persistent system of record.
- **Vertex AI** provides LLM reasoning and embeddings.

Source-code changes are developed in Cloud Shell, validated with `test_parity.py` where applicable, then deployed via `deploy-poc`.

Cloud SQL should be stopped when not in use to reduce compute cost.

**Never hardcode the DB password.** It lives only in Secret Manager.

---

## 17. Changelog — 14 Sep 2026

Corrected from the previous version:

- **Project ID corrected.** `ing-fm-demo-2026` → `dulcet-radar-508218-c5`.
- **DB password handling corrected.** Removed hardcoded literal. Directs to Secret Manager (`db-postgres-pass`).
- **File names corrected.** `app.py`, `gui.py`, `seed_db.py`, `seed_runner.py` → `main.py`, `pitchbook_builder.py`, `frontend/src/App.jsx`.
- **Deploy port corrected.** `8501` → `8080`.
- **Deploy command replaced.** The actual `deploy-poc` alias is used. Removed `--clear-base-image`, `--allow-unauthenticated`, `--add-cloudsql-instances` — none are in the live command.
- **Health endpoint corrected.** `/health` does not exist. Use `/api/opportunities` for reachability.
- **Architecture diagram corrected.** Streamlit + Flask replaced with React + FastAPI.
- **POC flow corrected.** Streamlit tabs replaced with the React workspace's actual layout.
- **§4 Preflight Validation added.** Proxy check, Cloud SQL state, service URL.
- **§9 Post-Deploy Verification added.** Cache warm, revision check, response shape.
- **§15 Troubleshooting added.**
- **`session-init.sh` documented** as the required first step.

---

*End of document.*