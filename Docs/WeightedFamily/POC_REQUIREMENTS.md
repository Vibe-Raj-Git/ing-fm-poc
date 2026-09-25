# POC Requirements — Financial Markets Deal Intelligence Platform

**Target project:** `cb9279820a-techmod-gc`
**Environment type:** Demo / POC
**Region:** `europe-west1`
**Development owner:** Rajarshi Pathak (rajarshi.pathak@cognizant.com)
**Date:** 24 September 2026

---

## Purpose

Build and deploy the **Financial Markets Deal Intelligence Platform**
as a POC into the corporate GCP project `cb9279820a-techmod-gc`.

The platform is an AI-assisted origination workspace for wholesale banking.
It ingests corporate signals, uses Vertex AI (Gemini 2.5 Flash) to
synthesise a grounded mandate narrative, and produces an 11-slide
pitchbook. It runs as a FastAPI backend on Cloud Run with a Cloud SQL
PostgreSQL 15 database.

The same Docker image runs as three independent Cloud Run services, each
rendering a different brand configuration (ING, BFS AI Lab, Acme Financial)
selected by a `BRAND` environment variable. This lets the same POC be
demonstrated under multiple brand identities without a code fork.

This document lists the resources, APIs, and IAM roles the POC requires.
It is a provisioning checklist for the Cloud Admin team.

---

## 1. Project

| Item | Value |
|---|---|
| Target project ID | `cb9279820a-techmod-gc` |
| Region | `europe-west1` |
| Environment type | Demo / POC (not production) |

---

## 2. APIs to Enable

| API | Service ID | Why needed |
|---|---|---|
| Vertex AI | `aiplatform.googleapis.com` | All LLM calls: signal extraction, mandate synthesis, Copilot, compliance audit |
| Cloud Run Admin | `run.googleapis.com` | Three POC services: `ing-fm-poc-service`, `bfs-ai-lab-service`, `acme-service` |
| Cloud Build | `cloudbuild.googleapis.com` | Container image builds from source |
| Artifact Registry | `artifactregistry.googleapis.com` | Stores built container images |
| Secret Manager | `secretmanager.googleapis.com` | Stores the Cloud SQL password |
| Cloud SQL Admin | `sqladmin.googleapis.com` | PostgreSQL instance for the POC data schema |
| Cloud Storage | `storage.googleapis.com` | Cloud Build staging buckets |
| Compute Engine | `compute.googleapis.com` | Underlying infrastructure for Cloud Run, Cloud SQL, Cloud Build |
| Cloud Workstations | `workstations.googleapis.com` | Optional — developer workstation for the POC |

Enable command:

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  compute.googleapis.com \
  workstations.googleapis.com \
  --project=cb9279820a-techmod-gc
```

---

## 3. Cloud SQL

**POC instance name:** `ing-postgres-db`

| Setting | Value |
|---|---|
| Database version | PostgreSQL 15 |
| Edition | ENTERPRISE |
| Region | `europe-west1` |
| Tier | `db-custom-1-3840` (1 vCPU, 3.75 GB) |
| Storage | 10 GB HDD (`PD_HDD`), auto-resize enabled |
| Availability | `ZONAL` |
| Public IP | Enabled (Cloud SQL Auth Connector is used; no authorized networks needed) |
| SSL mode | `ALLOW_UNENCRYPTED_AND_ENCRYPTED` (Connector uses TLS) |
| Backups | Recommend enabling for the POC |
| Deletion protection | Recommend enabling |
| Database name | `postgres` |
| User | `postgres` (BUILT_IN, password auth) |
| Extensions | `pgvector` (installed by the schema DDL) |

Connection name:

```
cb9279820a-techmod-gc:europe-west1:ing-postgres-db
```

---

## 4. Secret Manager

| Secret name | Value | Access needed |
|---|---|---|
| `db-postgres-pass` | The Cloud SQL `postgres` password | Compute SA needs `roles/secretmanager.secretAccessor` |

---

## 5. Service Account

**One service account for the POC** — the default Compute Engine service account:

```
<PROJECT-NUMBER>-compute@developer.gserviceaccount.com
```

This will be the runtime identity for the Cloud Run services and Cloud Build.

### Required IAM roles on this SA (8 specific roles)

| Role | Why |
|---|---|
| `roles/aiplatform.user` | Call Vertex AI (Gemini, embeddings) |
| `roles/artifactregistry.admin` | Push and pull container images |
| `roles/cloudbuild.builds.builder` | Trigger Cloud Build |
| `roles/cloudsql.client` | Connect to the Cloud SQL instance |
| `roles/run.admin` | Deploy and update Cloud Run services |
| `roles/iam.serviceAccountUser` | Act as the runtime identity |
| `roles/secretmanager.secretAccessor` | Read the DB password |
| `roles/storage.admin` | Cloud Build staging bucket |

**Minimal-privilege note:** the POC does not require `roles/editor` or
`roles/owner`. The eight specific roles above are sufficient and follow
minimal-privilege practice.

**Also required:** the Cloud Build service account
(`<PROJECT-NUMBER>@cloudbuild.gserviceaccount.com`) needs
`roles/cloudbuild.builds.builder`. This is granted automatically when the
Cloud Build API is enabled, but worth confirming.

**Developer access:** the development owner (rajarshi.pathak@cognizant.com)
needs either:
- Membership in a group that can deploy to the project, OR
- `roles/iam.serviceAccountTokenCreator` on the SA above, so the developer
  can impersonate it from their Cloud Workstation

---

## 6. Cloud Run — Three Services

| Service | Purpose | `BRAND` value |
|---|---|---|
| `ing-fm-poc-service` | ING branding | `ING` |
| `bfs-ai-lab-service` | BFS AI Lab branding | `BFS_AI_LAB` |
| `acme-service` | Acme Financial branding | `ACME_FINANCIAL` |

### Per-service configuration

| Setting | Value |
|---|---|
| Container port | 8080 |
| Memory | 512 MiB |
| CPU | 1000m (1 vCPU) |
| Min instances | 1 (ING only) / 0 (BFS, Acme) |
| **Max instances** | **1** (required — in-memory synthesis cache) |
| Timeout | 300s |
| Concurrency | 80 |
| Ingress | All |
| Public access | `allUsers` with `roles/run.invoker` (subject to org policy) |
| Service account | `<PROJECT-NUMBER>-compute@developer.gserviceaccount.com` |

### Environment variables (identical except `BRAND`)

```
INSTANCE_CONNECTION_NAME=cb9279820a-techmod-gc:europe-west1:ing-postgres-db
DB_USER=postgres
DB_NAME=postgres
GCP_PROJECT=cb9279820a-techmod-gc
REGION=europe-west1
BRAND=<ING | BFS_AI_LAB | ACME_FINANCIAL>
```

### Secret mount (all three services)

```
DB_PASS=db-postgres-pass:latest
```

---

## 7. Artifact Registry

| Repository | Format | Location |
|---|---|---|
| `cloud-run-source-deploy` | DOCKER | `europe-west1` |

Cloud Run creates this automatically on first `gcloud run deploy --source .`,
but pre-creating avoids permission issues.

---

## 8. Cloud Workstation (Optional)

| Setting | Value |
|---|---|
| Machine type | `e2-standard-4` (4 vCPU, 16 GB) |
| Image | `code-oss:latest` |
| Region | `europe-west1` |

Not strictly required — the codebase can be developed from any environment
with Python 3.11, `gcloud` CLI, and network access to Cloud SQL.

---

## 9. Corporate Policy Compliance

The POC design assumes the standard GCP deployment pattern:

- Cloud Run services with public ingress for demo URLs
- Cloud SQL instance with public IP, accessed via the Cloud SQL Auth Connector
- Cloud Workstation with outbound internet access

If any of these conflict with corporate org policy, please advise during
review. The POC can be adapted, but the above represents the standard
pattern and the minimum viable scope for the demo use case.

---

## 10. Approvals Needed

| Item | Approver |
|---|---|
| API enablement (9 services) | Cloud Admin |
| IAM role bindings on the compute SA (8 roles) | Cloud Admin |
| Deployment access for the developer (SA impersonation or group membership) | Cloud Admin |
| Org policy exceptions (if applicable) | Cloud Admin |

---

## 11. Development Plan (post-provisioning)

Once the API enablement and IAM role bindings are in place, the development
owner will build and deploy the POC. All post-provisioning steps are
performed by the development owner — no further admin action needed.

### 11.1 Cloud SQL provisioning

1. Create the Cloud SQL instance `ing-postgres-db` (PostgreSQL 15, tier
   `db-custom-1-3840`, 10 GB HDD, region `europe-west1`)
2. Set the `postgres` user password
3. Store the password in Secret Manager as `db-postgres-pass`
4. Enable `pgvector` extension on the `postgres` database

### 11.2 Cloud Shell / Cloud Workstation connectivity

The developer environment (Cloud Shell or Cloud Workstation) connects to
Cloud SQL through the **Cloud SQL Auth Connector**, which requires:

- The `gcloud` CLI authenticated to the corporate account
- The `cloud-sql-proxy` binary (installed by the session-init script)
- Network egress from the developer environment
- Either `roles/cloudsql.client` on the developer's account, OR
  impersonation of the service account that has this role

Once the connection is established, the developer environment reaches
Cloud SQL on `localhost:5432` via the proxy. Cloud Run reaches it through
the same Auth Connector from the runtime service account.

**No VPC peering, no authorized networks, no firewall rules needed** —
the Auth Connector handles authentication and encryption end-to-end.

### 11.3 Data schema and seed

1. Run `schema_setup.sql` against the new instance to create the `ca`
   schema and all tables
2. Load the reference dataset via the seed script — 13 clients, ~90
   signals, ~40 document chunks

### 11.4 Application deployment

1. Deploy three Cloud Run services via `gcloud run deploy --source .`:
   `ing-fm-poc-service`, `bfs-ai-lab-service`, `acme-service`
2. Configure each service with the env vars listed in §6
3. Bind the `allUsers` invoker member (subject to policy)

### 11.5 Verification

1. `/api/brand` returns the correct brand profile on all three services
2. Parity check passes
3. Spot check against the primary demo client

**Estimated time from API enablement to live POC:** 2 hours.

---

## Appendix — Resource Summary

| Resource | Count |
|---|---|
| Cloud SQL instance | 1 |
| Secret Manager secret | 1 |
| Service account | 1 (default compute, auto-created) |
| IAM roles on compute SA | 8 |
| Cloud Run services | 3 |
| Artifact Registry repo | 1 |
| Cloud Workstation config | 0–1 (optional) |

---

## Data Statement

The POC database contains **curated, non-production data** for demonstration
purposes. Client data (Enel S.p.A., BASF SE, and 11 additional synthetic
clients) is sourced from **public filings and news**. No customer data,
no PII, no confidential client information is involved.

---

*Prepared by Rajarshi Pathak (rajarshi.pathak@cognizant.com) | Sr. Manager | AI Consulting CoE*
*Environment: Demo / POC — not production*
```

Right — the admin will **enable the APIs** but they won't **create the Cloud SQL instance** or set up connectivity. That's on you after approval. The requirements doc should make that clear, and I should give you the exact commands so you're ready the moment you get the green light.

## What the admin will and won't do

| Item | Who does it |
|---|---|
| Enable the 9 APIs | Admin |
| Grant the service account + roles | Admin |
| Grant you impersonation rights (or group membership) | Admin |
| **Create the Cloud SQL instance** | **You** |
| **Set the postgres password, store it in Secret Manager** | **You** |
| **Run `schema_setup.sql`** | **You** |
| **Run `load_baseline.py`** | **You** |
| **Create the Artifact Registry repo** (or let Cloud Run auto-create) | **You** |
| **Deploy 3 Cloud Run services** | **You** |
| **Set up Cloud Shell ↔ Cloud SQL connectivity** | **You** |

The admin grants access. You build. That's normal.

## What needs to be added to `POC_REQUIREMENTS.md`

A section that makes the "you build it" part explicit. Currently §11 says "Development Plan (post-provisioning)" but it's vague. Let me tighten it.

**Find §11:**

```markdown
## 11. Development Plan (post-provisioning)

Once the target project is provisioned, the development owner will:

1. Create the Cloud SQL instance
2. Store the DB password in Secret Manager
3. Configure the Cloud Workstation `session-init.sh` with the connection name
4. Run `schema_setup.sql` to create the POC data schema
5. Load the reference dataset (curated demo data — 13 clients, synthetic/curated)
6. Deploy three Cloud Run services from the repository
7. Verify: platform health check, `/api/brand` on all three services, spot check against the primary demo client

**Estimated time from approval to live POC:** 2 hours.
```

**Replace with:**

```markdown
## 11. Development Plan (post-provisioning)

Once the API enablement and IAM role bindings are in place, the development
owner will build and deploy the POC. All post-provisioning steps are
performed by the development owner — no further admin action needed.

### 11.1 Cloud SQL provisioning

1. Create the Cloud SQL instance `ing-postgres-db` (PostgreSQL 15, tier
   `db-custom-1-3840`, 10 GB HDD, region `europe-west1`)
2. Set the `postgres` user password
3. Store the password in Secret Manager as `db-postgres-pass`
4. Enable `pgvector` extension on the `postgres` database

### 11.2 Cloud Shell / Cloud Workstation connectivity

The developer environment (Cloud Shell or Cloud Workstation) connects to
Cloud SQL through the **Cloud SQL Auth Connector**, which requires:

- The `gcloud` CLI authenticated to the corporate account
- The `cloud-sql-proxy` binary (installed by the session-init script)
- Network egress from the developer environment
- Either `roles/cloudsql.client` on the developer's account, OR
  impersonation of the service account that has this role

Once the connection is established, the developer environment reaches
Cloud SQL on `localhost:5432` via the proxy. Cloud Run reaches it through
the same Auth Connector from the runtime service account.

**No VPC peering, no authorized networks, no firewall rules needed** —
the Auth Connector handles authentication and encryption end-to-end.

### 11.3 Data schema and seed

1. Run `schema_setup.sql` against the new instance to create the `ca`
   schema and all tables
2. Load the reference dataset via the seed script — 13 clients, ~90
   signals, ~40 document chunks

### 11.4 Application deployment

1. Deploy three Cloud Run services via `gcloud run deploy --source .`:
   `ing-fm-poc-service`, `bfs-ai-lab-service`, `acme-service`
2. Configure each service with the env vars listed in §6
3. Bind the `allUsers` invoker member (subject to policy)

### 11.5 Verification

1. `/api/brand` returns the correct brand profile on all three services
2. Parity check passes
3. Spot check against the primary demo client

**Estimated time from API enablement to live POC:** 2 hours.
```

This section now explicitly tells the admin: **"you don't need to do any of this — it's on me."** That's the reassurance they want.

## And here are the exact commands you'll run

Save these. You'll execute them the moment approval lands.

### Step 1 — Create the Cloud SQL instance

```bash
gcloud sql instances create ing-postgres-db \
  --database-version=POSTGRES_15 \
  --tier=db-custom-1-3840 \
  --region=europe-west1 \
  --storage-type=HDD \
  --storage-size=10GB \
  --storage-auto-increase \
  --availability-type=ZONAL \
  --edition=ENTERPRISE \
  --project=cb9279820a-techmod-gc
```

**Expected:** 3–5 minutes for provisioning. Ends with `Created [https://sqladmin.googleapis.com/...]`.

### Step 2 — Set the postgres password and store in Secret Manager

```bash
# Generate a strong password
DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

# Set it on Cloud SQL
gcloud sql users set-password postgres \
  --instance=ing-postgres-db \
  --password="$DB_PASS" \
  --project=cb9279820a-techmod-gc

# Store in Secret Manager
echo -n "$DB_PASS" | gcloud secrets create db-postgres-pass \
  --data-file=- \
  --replication-policy=automatic \
  --project=cb9279820a-techmod-gc
```

**Do not paste `DB_PASS` anywhere.** Keep it in your shell. It's stored securely in Secret Manager.

### Step 3 — Get the connection name

```bash
gcloud sql instances describe ing-postgres-db \
  --project=cb9279820a-techmod-gc \
  --format="value(connectionName)"
```

**Expected:** `cb9279820a-techmod-gc:europe-west1:ing-postgres-db`.

### Step 4 — Enable pgvector

```bash
gcloud sql databases create postgres \
  --instance=ing-postgres-db \
  --project=cb9279820a-techmod-gc 2>&1 | head -3 || echo "database exists, continuing"

# Connect and enable the extension
gcloud sql connect ing-postgres-db \
  --user=postgres \
  --project=cb9279820a-techmod-gc \
  --quiet <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
\q
SQL
```

**Expected:** `CREATE EXTENSION`.

### Step 5 — Set up Cloud Shell ↔ Cloud SQL connectivity

**Two options:**

**Option A — Session-init script (recommended, matches current setup):**

Update `session-init.sh` with the new project, then run it:

```bash
# Edit session-init.sh to point at the new project
sed -i 's/dulcet-radar-508218-c5/cb9279820a-techmod-gc/g' session-init.sh
sed -i 's/rajarshipathak30aug@gmail.com/rajarshi.pathak@cognizant.com/g' session-init.sh

# Source it
source ./session-init.sh
```

The script handles:
- GCP auth check
- Project config
- Password retrieval from Secret Manager
- Connection name fetch
- Cloud SQL Auth Proxy start
- Connectivity test

**Option B — Manual proxy:**

```bash
# Download cloud-sql-proxy (once)
mkdir -p ~/bin
curl -s -o ~/bin/cloud-sql-proxy \
  https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.0/cloud-sql-proxy.linux.amd64
chmod +x ~/bin/cloud-sql-proxy

# Start the proxy
~/bin/cloud-sql-proxy --port 5432 \
  cb9279820a-techmod-gc:europe-west1:ing-postgres-db &

# Test
psql "host=127.0.0.1 port=5432 dbname=postgres user=postgres" -c "SELECT 1;"
```

**Option A is what you already use.** Go with it.

### Step 6 — Run schema and load data

```bash
cd ~/ing-fm-poc
source ./session-init.sh

# Create schema
python3 -c "
import os, pg8000.native
conn = pg8000.native.Connection(
    user='postgres', password=os.environ['DB_PASS'],
    host='127.0.0.1', port=5432, database='postgres'
)
with open('schema_setup.sql') as f:
    conn.run(f.read())
conn.close()
print('Schema created')
"

# Load data
python3 load_baseline.py
```

**Expected:** schema created, then `load_baseline.py` reports loads per client. First run inserts everything; second run reports 0 for PK'd tables.

### Step 7 — Deploy the three Cloud Run services

```bash
# Ensure aliases point at the new project
grep deploy- ~/.bashrc | head -3

# If needed, update aliases
sed -i 's/dulcet-radar-508218-c5/cb9279820a-techmod-gc/g' ~/.bashrc
source <(grep '^alias deploy-' ~/.bashrc)

# Deploy
deploy-poc
deploy-bfs
deploy-acme
```

**Each takes 3–5 minutes.** First deploy builds the image; subsequent deploys reuse the Cloud Build cache.

### Step 8 — Grant public access on the new services

```bash
for svc in ing-fm-poc-service bfs-ai-lab-service acme-service; do
  gcloud run services add-iam-policy-binding $svc \
    --region=europe-west1 \
    --project=cb9279820a-techmod-gc \
    --member="allUsers" \
    --role="roles/run.invoker"
done
```

**Subject to org policy.** If `allUsers` is blocked, this fails — you'll get an error and we adapt.

### Step 9 — Verify

```bash
# Brand check on all three
for svc in ing-fm-poc-service bfs-ai-lab-service acme-service; do
  URL=$(gcloud run services describe $svc \
    --region=europe-west1 --project=cb9279820a-techmod-gc \
    --format='value(status.url)')
  echo "== $svc =="
  curl -s "$URL/api/brand" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])"
done
```

**Expected:**
```
== ing-fm-poc-service ==
ING
== bfs-ai-lab-service ==
BFS AI Lab
== acme-service ==
Acme Financial
```

## Summary

**What you add to `POC_REQUIREMENTS.md`:**

Replace §11 with the detailed 11.1–11.5 version above. It tells the admin explicitly: **"All post-provisioning steps are performed by the development owner — no further admin action needed."** That's reassuring.

**What you save for yourself:**

The 9 commands above. You run them after approval. Total execution time ~2 hours.

## Run the §11 replacement

Open the file:

```bash
code ~/ing-fm-poc/Docs/WeightedFamily/POC_REQUIREMENTS.md
```

Find §11 and replace with the detailed version. Save.

Then:

```bash
grep -c "11.1 Cloud SQL provisioning\|11.2 Cloud Shell\|11.3 Data schema" ~/ing-fm-poc/Docs/WeightedFamily/POC_REQUIREMENTS.md
grep -c $'\x08' ~/ing-fm-poc/Docs/WeightedFamily/POC_REQUIREMENTS.md
```

**Expected:** `3`, `0`.

**Paste back those two lines.** Then we commit and the doc is final.

**After that — file the ticket. The commands are ready for when approval lands.**