# ING Financial Markets Deal Intelligence Platform

**Current branch:** `feat/dulcet-reset-pristine-semantic-dedup-all-UI-RM-HV-Slide2_LLM_Summary_Slide3_WhyNow_Action_17-Sep`

Internal use only. This repository contains environment-specific identifiers (GCP project, Secret Manager names) intended for internal ING use.

## Getting Started

The `main` branch holds the historical state of this project from August 2026. The live, deployed code is on the feature branch named above. Clone the repository and check out that branch:

```bash
git clone https://github.com/Vibe-Raj-Git/ing-fm-poc.git
cd ing-fm-poc
git checkout feat/dulcet-reset-pristine-semantic-dedup-all-UI-RM-HV-Slide2_LLM_Summary_Slide3_WhyNow_Action_17-Sep
To start new work, branch off this working branch — not off main:

bash
git checkout feat/dulcet-reset-pristine-semantic-dedup-all-UI-RM-HV-Slide2_LLM_Summary_Slide3_WhyNow_Action_17-Sep
git checkout -b feat/your-new-feature
Architecture
The platform is a three-tier application:

Frontend: React 18 + Vite + Tailwind CSS (frontend/)

Backend: FastAPI + Python 3.11 (main.py, pitchbook_builder.py)

Data + AI: Cloud SQL PostgreSQL 15 with pgvector; Vertex AI (gemini-2.5-flash, text-embedding-004)

The platform ingests unstructured corporate touchpoints (emails, Teams chats, RSS feeds, PDFs, WorkFabric memos), extracts structured signals via Gemini, and produces an 11-slide pitchbook across four product families (FX, Green/ESG, Rates, DCM).

Every displayed value traces to a specific row in a specific PostgreSQL table, filtered by client_id. The zero-fabrication principle is described in Docs/Data_or_Fabrication.md.

Current demo scope: Enel S.p.A. (CLI101) and BASF SE (CLI103), controlled by the whitelist below.

Full Documentation
The Docs/ folder holds the complete architecture and operations reference. Key documents:

Document	Purpose
Docs/master_persona_20Sep.md	Context and persona for AI-assisted sessions (current)
Docs/architecture_flow_14Sep.md	Complete architecture reference
Docs/Data_or_Fabrication.md	Zero-fabrication principle and the reset-to-pristine mechanism
Docs/data_population.md	Field-by-field lineage of every UI element
Docs/Table_details.md	Database schema catalog
Docs/How_Signals_are_Converted_into_Opportunities.md	The ingestion-to-pitchbook pipeline
Docs/Signals,_Opportunities_&_Pitchbook_Lifecycle.md	End-to-end data lifecycle
Docs/what_changed_16Sep.md	Reconciliation change log (14–17 Sep)
Docs/Updated_Runbook.md	Operational procedures
Docs/PERFORMANCE_OPTIMIZATION.md	Performance tuning trail
Docs/Copilot_Test_Suite.md	Copilot validation suite
Docs/Live_Signal_feed.md	Signal marquee mechanics
Testing
The primary correctness gate is test_parity.py — a 13-gate dynamic parity audit. It verifies:

PostgreSQL connectivity via get_db_connection

ca.mkt_rates_curves ground truth (5Y EUR swap 2.62%, 10Y Bund 2.61%)

ca.ext_credit_spreads ground truth (Enel 5Y 78 bps, 10Y 80 bps)

/api/opportunities returns client data with rates and spreads mapped

Bundle integrity for pitchbook generation (curves, spreads, all-in yield)

Base PPTX generation

Copilot scenario override generation

Non-destructive invariance (base record preserved)

Run before every deploy:

bash
cd ~/ing-fm-poc
python3 test_parity.py
Expected output: 13/13 gates passed.

Additional utilities:

dump_baseline.py — regenerate baseline_snapshots.json from current DB state. Run after any DB content change that should become part of the pristine baseline.

enrich_basf_baseline.py — insert curated signals and chunks for CLI103 (BASF). Idempotent; safe to re-run.

Deployment
Pre-deploy verification:

bash
cd ~/ing-fm-poc
python3 test_parity.py    # expected: 13/13 gates passed
Deploy to Cloud Run via the local shell alias:

bash
deploy-poc
This is a shell alias for a gcloud run deploy command. It requires:

gcloud authenticated with access to the dulcet-radar-508218-c5 GCP project

The Cloud SQL instance ing-postgres-db in europe-west1 to be running

The db-postgres-pass secret in Secret Manager to be accessible

The Dockerfile performs a two-stage build: node:20-alpine compiles the React frontend, then python:3.11-slim installs backend requirements and copies the application code plus baseline_snapshots.json.

Post-deploy verification:

bash
SVC_URL=$(gcloud run services describe ing-fm-poc-service \
  --region europe-west1 --project dulcet-radar-508218-c5 \
  --format "value(status.url)")

curl -s "$SVC_URL/api/opportunities" | python3 -m json.tool | head -20
Repository Structure
text
.
├── main.py                       # FastAPI backend
├── pitchbook_builder.py          # PPTX generation
├── deck_model.py                 # Legacy parallel pitchbook implementation (unused)
├── baseline_snapshots.json       # Reset-to-pristine snapshot
├── dump_baseline.py              # Snapshot generator
├── enrich_basf_baseline.py       # Curated baseline content utility
├── schema_setup.sql              # Database schema (for new environments)
├── seed_db.py                    # Seed data loader
├── seed_runner.py                # Seed orchestrator
├── test_parity.py                # 13-gate parity audit (run before every deploy)
├── Dockerfile                    # Two-stage build
├── cloudbuild.yml                # Cloud Build config
├── requirements.txt              # Python dependencies
├── session-init.sh               # Session bootstrap
├── start.sh                      # Local start script
├── ca_data_dump.json             # Reference data dump
├── Structured_Data.xlsx          # Seed source data
├── Unstructured_Data.xlsx        # Seed source data
├── frontend/                     # React source (App.jsx, index.css, main.jsx)
├── Docs/                         # Architecture documentation
├── archive/                      # Historical variants (not used at runtime)
├── assets/                       # Logos and icons
└── Test_Data/                    # Test fixtures
Key Configuration
Environment variables read at runtime:

text
INSTANCE_CONNECTION_NAME=dulcet-radar-508218-c5:europe-west1:ing-postgres-db
DB_USER=postgres
DB_NAME=postgres
GCP_PROJECT=dulcet-radar-508218-c5
REGION=europe-west1
Database password is retrieved from Secret Manager (db-postgres-pass).

Demo whitelist. The platform's demo scope is controlled by two synchronized lists:

main.py — _DEMO_CLIENT_IDS

frontend/src/App.jsx — ACTIVE_UI_CLIENT_IDS

These must remain in sync. The backend list controls LLM synthesis; the frontend list controls rendering. See Docs/master_persona_20Sep.md §6 for the full rule.

Credit rating display. Credit ratings are curated in a single dict per file (_CREDIT_RATINGS) in both main.py and pitchbook_builder.py. There is no credit_rating column on ca.client_master (§7.2 forbids DDL). Adding a new demo client requires adding its rating to both dicts. See Docs/master_persona_20Sep.md §8.1.

Branching Convention
Branch	Purpose
main	Historical reference (Aug 2026). Not actively maintained.
feat/*	Active development. Branch off the current working branch.
archive/*	Optional tags for preserving specific states.
The current working branch is always the one named at the top of this README.

Verification Checklist
Before considering any deploy ready:

Syntax: python3 -c "import ast; ast.parse(open('main.py').read())" and the same for pitchbook_builder.py

Frontend: verify frontend/src/App.jsx has balanced braces

Parity audit: python3 test_parity.py — expected 13/13 gates passed

Whitelist sync: confirm _DEMO_CLIENT_IDS and ACTIVE_UI_CLIENT_IDS match

Credit rating dict sync: confirm _CREDIT_RATINGS in main.py and pitchbook_builder.py are aligned

Clean working tree: no .bak* files in the deploy path

Last updated: 20 September 2026