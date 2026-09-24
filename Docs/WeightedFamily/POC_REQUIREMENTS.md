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

Once the target project is provisioned, the development owner will:

1. Create the Cloud SQL instance
2. Store the DB password in Secret Manager
3. Configure the Cloud Workstation `session-init.sh` with the connection name
4. Run `schema_setup.sql` to create the POC data schema
5. Load the reference dataset (curated demo data — 13 clients, synthetic/curated)
6. Deploy three Cloud Run services from the repository
7. Verify: platform health check, `/api/brand` on all three services, spot check against the primary demo client

**Estimated time from approval to live POC:** 2 hours.

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

