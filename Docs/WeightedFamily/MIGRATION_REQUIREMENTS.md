# Migration Requirements — ing-fm-poc to Company GCP Project

**Source environment:** `dulcet-radar-508218-c5` (personal GCP project)
**Target environment:** `<COMPANY-PROJECT-ID>` (to be provisioned)
**Environment type:** Demo / POC (not production)
**Region:** `europe-west1` (matching source; can differ)
**Migration owner:** Rajarshi Pathak (rajarshi.pathak@cognizant.com)
**Date:** 24 September 2026

---

## Purpose

Migrate the **ING Financial Markets Deal Intelligence Platform** (`ing-fm-poc`)
from a personal GCP project to a company-owned project.

The platform is a demo/pilot: an AI-assisted origination workspace that
ingests corporate signals, synthesises a grounded mandate narrative, and
produces an 11-slide pitchbook. It runs as a FastAPI backend on Cloud Run
with a Cloud SQL PostgreSQL 15 database and Vertex AI (Gemini 2.5 Flash)
for LLM calls. Three independent Cloud Run services render three brand
configurations (ING, BFS AI Lab, Acme Financial) from the same Docker
image, selected by a `BRAND` environment variable.

This document lists the resources, APIs, and IAM roles the target project
requires. It is a provisioning checklist for the company GCP admin.

---

## 1. Project

| Item | Value |
|---|---|
| Target project ID | `<COMPANY-PROJECT-ID>` |
| Preferred region | `europe-west1` |
| Billing | Company billing account |
| Environment type | Demo / POC |

---

## 2. APIs to Enable

| API | Service ID | Why needed |
|---|---|---|
| Vertex AI | `aiplatform.googleapis.com` | All LLM calls: signal extraction, mandate synthesis, Copilot, compliance audit |
| Cloud Run Admin | `run.googleapis.com` | Three services: `ing-fm-poc-service`, `bfs-ai-lab-service`, `acme-service` |
| Cloud Build | `cloudbuild.googleapis.com` | Container image builds from source (`gcloud run deploy --source .`) |
| Artifact Registry | `artifactregistry.googleapis.com` | Stores built container images |
| Secret Manager | `secretmanager.googleapis.com` | Stores the Cloud SQL password |
| Cloud SQL Admin | `sqladmin.googleapis.com` | PostgreSQL instance for the `ca` schema |
| Cloud Storage | `storage.googleapis.com` | Cloud Build staging buckets, source uploads |
| Compute Engine | `compute.googleapis.com` | Underlying infrastructure for Cloud Run, Cloud SQL, and Cloud Build |
| Cloud Workstations | `workstations.googleapis.com` | Optional — developer workstation (skip if using an existing environment) |

All enabled via:

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
  --project=<COMPANY-PROJECT-ID>
```

## 3. Cloud SQL
Target instance name: ing-postgres-db (same as source, for path consistency)

Setting	Value
Database version	PostgreSQL 15
Edition	ENTERPRISE
Region	europe-west1
Zone	Any (source uses europe-west1-b)
Tier	db-custom-1-3840 (1 vCPU, 3.75 GB)
Storage	10 GB HDD (PD_HDD), auto-resize enabled
Availability	ZONAL
Public IP	Enabled (Cloud SQL Auth Connector is used; no authorized networks needed)
SSL mode	ALLOW_UNENCRYPTED_AND_ENCRYPTED (Connector uses TLS; tightening to ENCRYPTED_ONLY is safe)
Backups	Recommend enabling (source has it off)
Deletion protection	Recommend enabling (source has it off)
Database name	postgres
User	postgres (BUILT_IN, password auth)
Extensions	pgvector (installed by the schema DDL)
Connection name (used in all env vars):

```text
<COMPANY-PROJECT-ID>:europe-west1:ing-postgres-db
```

## 4. Secret Manager
Secret name	Value	Access needed
db-postgres-pass	The Cloud SQL postgres password	Compute SA needs roles/secretmanager.secretAccessor

Create command:

```bash
echo -n "<DB_PASSWORD>" | gcloud secrets create db-postgres-pass \
  --data-file=- \
  --project=<COMPANY-PROJECT-ID> \
  --replication-policy="automatic"
```

## 5. Service Account
One runtime service account — the default Compute Engine service account:

``text
<PROJECT-NUMBER>-compute@developer.gserviceaccount.com
```

Created automatically when the project is provisioned. This is the identity
that Cloud Run services, Cloud Build, and the platform itself use.

Required IAM roles on this SA (8 specific roles)

Role	Why
roles/aiplatform.user	Call Vertex AI — Gemini 2.5 Flash, text-embedding-004
roles/artifactregistry.admin	Push and pull container images
roles/cloudbuild.builds.builder	Trigger Cloud Build for gcloud run deploy --source .
roles/cloudsql.client	Connect to the Cloud SQL instance
roles/run.admin	Deploy and update Cloud Run services
roles/iam.serviceAccountUser	Act as the runtime service account
roles/secretmanager.secretAccessor	Read the DB password secret
roles/storage.admin	Cloud Build staging bucket access

Apply commands:
PROJECT_ID="<COMPANY-PROJECT-ID>"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SA="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for role in \
    roles/aiplatform.user \
    roles/artifactregistry.admin \
    roles/cloudbuild.builds.builder \
    roles/cloudsql.client \
    roles/run.admin \
    roles/iam.serviceAccountUser \
    roles/secretmanager.secretAccessor \
    roles/storage.admin; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="$SA" --role="$role" --condition=None
done

Also required: Cloud Build service agent
The Cloud Build service account (<PROJECT-NUMBER>@cloudbuild.gserviceaccount.com)
needs roles/cloudbuild.builds.builder. This is granted automatically when
the Cloud Build API is enabled, but worth confirming:

```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder" --condition=None
```

Minimal-privilege note
The source project has roles/editor on the compute SA as a legacy grant.
The migration does not require it. The eight specific roles above are
sufficient and follow minimal-privilege practice.

## 6. Cloud Run
Three services, all in europe-west1, all from the same container image.

**Service**	        **Purpose**	            **BRAND value**
ing-fm-poc-service	ING branding	        ING
bfs-ai-lab-service	BFS AI Lab branding	    BFS_AI_LAB
acme-service	    Acme Financial branding	ACME_FINANCIAL

## Per-service configuration
**Setting**	        **Value**
Container port	    8080
Memory	            512 MiB
CPU	                1000m (1 vCPU)
Min instances	    1 (ING only) / 0 (BFS, Acme)
Max instances	    1 (required — in-memory synthesis cache coherence)
Timeout	            300s
Concurrency	        80
Ingress	            All
Public access	    `allUsers` with `roles/run.invoker`
Service account	    `<PROJECT-NUMBER>-compute@developer.gserviceaccount.com`
Image registry	    `europe-west1-docker.pkg.dev/<PROJECT-ID>/cloud-run-source-deploy/<service>`

## Environment variables (identical except BRAND)
INSTANCE_CONNECTION_NAME=<COMPANY-PROJECT-ID>:europe-west1:ing-postgres-db
DB_USER=postgres
DB_NAME=postgres
GCP_PROJECT=<COMPANY-PROJECT-ID>
REGION=europe-west1
BRAND=<ING | BFS_AI_LAB | ACME_FINANCIAL>

## Secret mount (all three services)
DB_PASS=db-postgres-pass:latest

## Public access binding (all three services)
for svc in ing-fm-poc-service bfs-ai-lab-service acme-service; do
  gcloud run services add-iam-policy-binding $svc \
    --region=europe-west1 \
    --project=<COMPANY-PROJECT-ID> \
    --member="allUsers" \
    --role="roles/run.invoker"
done

## 7. Artifact Registry
Repository	            Format	Location	    Purpose
cloud-run-source-deploy	DOCKER	europe-west1	Cloud Run source deploys

Cloud Run creates this automatically on first `gcloud run deploy --source` .,
but pre-creating avoids permission issues:

bash
gcloud artifacts repositories create cloud-run-source-deploy \
  --repository-format=docker \
  --location=europe-west1 \
  --project=<COMPANY-PROJECT-ID>

## 8. Cloud Workstation (Optional)
If a Cloud Workstation is provisioned on the target project:

Setting	        Value
Config name	    Any (source uses ing-fm-dev-config-optimized)
Machine type	e2-standard-4 (4 vCPU, 16 GB)
Image	        europe-west1-docker.pkg.dev/cloud-workstations-images/predefined/code-oss:latest
Region	        europe-west1

Not strictly required. The codebase can be cloned and run from any
environment with Python 3.11, `gcloud` CLI, and network access to Cloud SQL.

## 9. Org Policy Exceptions
Some company GCP organizations restrict the following by default. If any are
enforced, the migration needs an exception or an alternative design.

Policy	Needed because	Alternative if blocked
constraints/iam.allowedPolicyMemberDomains	allUsers is outside the org's domain; needed for public demo URLs	Use Identity-Aware Proxy (IAP) with authenticated users
constraints/run.allowedIngress	Services need ingress: all for public access	Internal-only ingress + load balancer with IAP
constraints/sql.restrictPublicIp	Cloud SQL instance has a public IP	Private IP + Serverless VPC Connector
constraints/compute.vmExternalIpAccess	Cloud Workstation and Cloud Build need egress	NAT gateway for outbound traffic

Highest priority: the allUsers binding on Cloud Run. Without it, the
demo URLs are not reachable from a browser. If your org policy forbids
allUsers, we need to discuss the IAP alternative before provisioning.

## 10. Approvals Needed
Item	                                            Approver
Target project creation (if not exists)	            Company GCP admin
API enablement (9 services)	                        Company GCP admin
IAM role bindings on the compute SA (8 roles)	    Company GCP admin
Org policy exceptions (if applicable)	            Company GCP admin
Billing account assignment	                        Finance / GCP admin

## 11. Post-Provisioning Steps (migration owner)
Once the target project is provisioned per this document, the migration owner
performs:

- Create the Cloud SQL instance (ing-postgres-db, PostgreSQL 15, db-custom-1-3840)
- Set the postgres password; store it as db-postgres-pass in Secret Manager
- Update session-init.sh with the new INSTANCE_CONNECTION_NAME
- Run schema_setup.sql against the new instance — creates the ca schema and all 12 tables
- Run load_baseline.py — loads the snapshot (13 clients, 89 signals, 41 chunks)
- Deploy three Cloud Run services via the deploy-poc, deploy-bfs, deploy-acme shell aliases
- Verify: test_parity.py (13/13 gates), /api/brand on all three services, and a spot check against CLI101

Estimated time: 1–2 hours after project provisioning, plus Cloud SQL
instance startup (~5 minutes) and three Cloud Build runs (~3 minutes each).

Appendix — Resource Summary
Resource	                Count	    Notes
GCP Project	                1	        <COMPANY-PROJECT-ID>
Cloud SQL instance	        1	        ing-postgres-db
Secret	                    1	        db-postgres-pass
Service account	            1	        default compute SA (auto-created)
IAM roles on compute SA	    8	        specific, minimal privilege
Cloud Run services	        3	        ing-fm-poc-service, bfs-ai-lab-service, acme-service
Artifact Registry repo	    1	        cloud-run-source-deploy
Cloud Workstation config	0–1	        optional


======================================================  
EMAIL TO CLOUD TEAM
======================================================

Here's the email-ready plain-text version. No markdown syntax, no code fences, ready to paste into an email or Word document.

---

**Subject:** GCP Project Provisioning Request — ING Financial Markets Deal Intelligence Platform (Demo)

**To:** Cloud Admin Team

**From:** Rajarshi Pathak (rajarshi.pathak@cognizant.com) | Sr. Manager | AI Consulting CoE

**Date:** 24 September 2026

---

Hi Team,

I am requesting provisioning of a new GCP project to host a demo/pilot platform I have built. Currently it runs under my personal GCP project and I need to migrate it to a company-owned project.

I have prepared the full requirements below. The current setup is a demo environment, not production, so the resource sizing is modest.

Please let me know if you need any clarification or if anything in the request needs adjustment to fit company policy.

Thanks,
Rajarshi

---

## MIGRATION REQUIREMENTS — ing-fm-poc to Company GCP Project

**Source environment:** dulcet-radar-508218-c5 (personal project)
**Target environment:** to be provisioned
**Environment type:** Demo / POC (not production)
**Region:** europe-west1 (matching source; can differ)
**Migration owner:** Rajarshi Pathak

---

### PURPOSE

The platform is an AI-assisted origination workspace for wholesale banking. It ingests corporate signals across five channels, uses Vertex AI (Gemini 2.5 Flash) to synthesise a grounded mandate narrative, and produces an 11-slide pitchbook. It runs as a FastAPI backend on Cloud Run, backed by Cloud SQL PostgreSQL 15.

The same Docker image runs as three independent Cloud Run services, each rendering a different brand configuration — ING, BFS AI Lab, and Acme Financial — selected by a BRAND environment variable. This is a demo/pilot, so the resource sizing is intentionally small.

---

### 1. PROJECT

- Target project ID: to be assigned
- Preferred region: europe-west1
- Billing: company billing account
- Environment type: demo / POC

---

### 2. APIs TO ENABLE (9 services)

The following Google Cloud APIs need to be enabled on the target project:

1. aiplatform.googleapis.com — Vertex AI. Used for all LLM calls: signal extraction, mandate synthesis, Copilot responses, compliance audit.
2. run.googleapis.com — Cloud Run Admin. Hosts the three services: ing-fm-poc-service, bfs-ai-lab-service, acme-service.
3. cloudbuild.googleapis.com — Cloud Build. Builds container images when deploying from source (gcloud run deploy --source .).
4. artifactregistry.googleapis.com — Artifact Registry. Stores the built container images.
5. secretmanager.googleapis.com — Secret Manager. Stores the Cloud SQL password.
6. sqladmin.googleapis.com — Cloud SQL Admin. Manages the PostgreSQL instance.
7. storage.googleapis.com — Cloud Storage. Cloud Build staging buckets and source uploads.
8. compute.googleapis.com — Compute Engine. Underlying infrastructure for Cloud Run, Cloud SQL, and Cloud Build.
9. workstations.googleapis.com — Cloud Workstations. Optional, for a developer workstation. Skip if using an existing environment.

---

### 3. CLOUD SQL

Target instance name: ing-postgres-db (same as source, for consistency)

Configuration:

- Database version: PostgreSQL 15
- Edition: ENTERPRISE
- Region: europe-west1
- Zone: any (source uses europe-west1-b)
- Tier: db-custom-1-3840 (1 vCPU, 3.75 GB RAM)
- Storage: 10 GB HDD (PD_HDD), auto-resize enabled
- Availability: ZONAL (single zone)
- Public IP: enabled — connection uses the Cloud SQL Auth Connector, so no authorized networks needed
- SSL mode: ALLOW_UNENCRYPTED_AND_ENCRYPTED (the Connector uses TLS; can be tightened to ENCRYPTED_ONLY if preferred)
- Backups: recommend enabling (source has it off; enabling is better practice)
- Deletion protection: recommend enabling
- Database name: postgres
- User: postgres (BUILT_IN password authentication)
- Required extension: pgvector (installed automatically by our schema DDL)

Connection name: <PROJECT-ID>:europe-west1:ing-postgres-db

---

### 4. SECRET MANAGER

One secret required:

- Name: db-postgres-pass
- Value: the Cloud SQL postgres user password
- Access: the compute service account needs roles/secretmanager.secretAccessor

---

### 5. SERVICE ACCOUNT AND IAM ROLES

The default Compute Engine service account will be used as the runtime identity:

<PROJECT-NUMBER>-compute@developer.gserviceaccount.com

This service account needs the following 8 specific IAM roles on the target project:

1. roles/aiplatform.user — call Vertex AI (Gemini 2.5 Flash, text-embedding-004)
2. roles/artifactregistry.admin — push and pull container images
3. roles/cloudbuild.builds.builder — trigger Cloud Build for source deploys
4. roles/cloudsql.client — connect to the Cloud SQL instance
5. roles/run.admin — deploy and update Cloud Run services
6. roles/iam.serviceAccountUser — act as the runtime service account
7. roles/secretmanager.secretAccessor — read the DB password secret
8. roles/storage.admin — Cloud Build staging bucket access

Additionally, the Cloud Build service account needs roles/cloudbuild.builds.builder:

<PROJECT-NUMBER>@cloudbuild.gserviceaccount.com

This is usually granted automatically when the Cloud Build API is enabled, but please confirm.

MINIMAL-PRIVILEGE NOTE: The source project has roles/editor on the compute SA as a legacy grant. The migration does NOT require roles/editor. The 8 specific roles above are sufficient.

---

### 6. CLOUD RUN — THREE SERVICES

Three Cloud Run services, all in europe-west1, all from the same container image:

- ing-fm-poc-service — ING branding, BRAND=ING
- bfs-ai-lab-service — BFS AI Lab branding, BRAND=BFS_AI_LAB
- acme-service — Acme Financial branding, BRAND=ACME_FINANCIAL

Per-service configuration (identical for all three):

- Container port: 8080
- Memory: 512 MiB
- CPU: 1000m (1 vCPU)
- Min instances: 1 (for ing-fm-poc-service only) / 0 (for the other two)
- Max instances: 1 (this is important — the platform uses an in-memory synthesis cache that requires a single instance)
- Timeout: 300 seconds
- Concurrency: 80
- Ingress: all
- Public access: allUsers with roles/run.invoker (see org policy section below)
- Service account: the compute SA listed in section 5
- Image registry: europe-west1-docker.pkg.dev/<PROJECT-ID>/cloud-run-source-deploy/<service>

Environment variables (identical for all three except BRAND):

- INSTANCE_CONNECTION_NAME=<PROJECT-ID>:europe-west1:ing-postgres-db
- DB_USER=postgres
- DB_NAME=postgres
- GCP_PROJECT=<PROJECT-ID>
- REGION=europe-west1
- BRAND=ING or BFS_AI_LAB or ACME_FINANCIAL

Secret mounted as environment variable on all three:

- DB_PASS=db-postgres-pass:latest

Public access binding (all three services):

The services need the allUsers member with role roles/run.invoker for browser access to the demo URLs. This is the same pattern as the source project.

---

### 7. ARTIFACT REGISTRY

One repository:

- Name: cloud-run-source-deploy
- Format: DOCKER
- Location: europe-west1
- Purpose: Cloud Run source deploys

Cloud Run creates this automatically on the first deploy, but pre-creating it avoids permission issues.

---

### 8. CLOUD WORKSTATION (OPTIONAL)

If a Cloud Workstation is provisioned on the target project:

- Config name: any (source uses ing-fm-dev-config-optimized)
- Machine type: e2-standard-4 (4 vCPU, 16 GB RAM)
- Image: europe-west1-docker.pkg.dev/cloud-workstations-images/predefined/code-oss:latest
- Region: europe-west1

Not strictly required. The codebase can be cloned and run from any environment with Python 3.11, the gcloud CLI, and network access to Cloud SQL.

---

### 9. ORG POLICY EXCEPTIONS (IF APPLICABLE)

Some company GCP organizations restrict the following by default. If any are enforced, we need an exception or a design alternative.

1. constraints/iam.allowedPolicyMemberDomains — allUsers is outside the org's domain. Needed for public demo URLs. Alternative: Identity-Aware Proxy (IAP) with authenticated users.
2. constraints/run.allowedIngress — services need ingress: all for public access. Alternative: internal-only ingress plus a load balancer with IAP.
3. constraints/sql.restrictPublicIp — the Cloud SQL instance has a public IP. Alternative: private IP plus Serverless VPC Connector.
4. constraints/compute.vmExternalIpAccess — Cloud Workstation and Cloud Build need outbound internet. Alternative: NAT gateway for outbound traffic.

HIGHEST PRIORITY: the allUsers binding on Cloud Run. Without it, the demo URLs are not reachable from a browser. If company policy forbids allUsers, please advise so we can discuss the IAP alternative before provisioning.

---

### 10. APPROVALS NEEDED

- Target project creation (if not exists): Company GCP admin
- API enablement (9 services): Company GCP admin
- IAM role bindings on the compute service account (8 roles): Company GCP admin
- Org policy exceptions (if applicable): Company GCP admin
- Billing account assignment: Finance / GCP admin

---

### 11. POST-PROVISIONING STEPS (performed by migration owner)

Once the target project is provisioned, I will:

1. Create the Cloud SQL instance (ing-postgres-db, PostgreSQL 15, db-custom-1-3840)
2. Set the postgres password and store it as db-postgres-pass in Secret Manager
3. Update the workstation session-init script with the new connection name
4. Run the schema DDL to create the ca schema and all 12 tables
5. Load the data snapshot (13 clients, 89 signals, 41 chunks)
6. Deploy the three Cloud Run services from the repository
7. Verify: parity check (13 gates), API health check on all three services, and a spot check against the primary demo client

Estimated time: 1–2 hours after provisioning, plus Cloud SQL startup (about 5 minutes) and three Cloud Build runs (about 3 minutes each).

---

### RESOURCE SUMMARY

- 1 GCP project
- 1 Cloud SQL instance
- 1 Secret Manager secret
- 1 service account (default compute, auto-created)
- 8 IAM roles on the compute service account
- 3 Cloud Run services
- 1 Artifact Registry repository
- 0 or 1 Cloud Workstation config (optional)

---

Prepared by Rajarshi Pathak (rajarshi.pathak@cognizant.com) | Sr. Manager | AI Consulting CoE
Environment: Demo / POC — not production

---

## What to do with this

**Copy the block from "Hi Team," through "not production"** into your email client. Two things to adjust:

1. **Replace any `<PROJECT-ID>` or `<PROJECT-NUMBER>` placeholders** — they're intentional placeholders since the target project doesn't exist yet. Leave them as-is and note they'll be filled in once the admin assigns a project ID.

2. **Add your manager / sponsor** on CC if appropriate — the request has more weight with a senior stakeholder visible.

## After you send

The admin team will either:
- **Provision as requested** → you get a project ID back, we run the migration
- **Ask for clarification** → paste their response here, I'll help draft the reply
- **Request modifications** → paste them, I'll adjust the plan

**Send the email. Paste back the admin's response when you have it.**