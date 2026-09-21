# ING Financial Markets Deal Intelligence Platform

**Current branch:** `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3`

Internal use only. This repository contains environment-specific identifiers (GCP project, Secret Manager names) intended for internal ING use.

## Product Flavors

The platform has two parallel flavors, each on its own feature branch. They share the same data tier, ingestion pipeline, database schema, and reset mechanism; they differ in the synthesis and pitchbook layers.

| Flavor | Branch | What it is |
|---|---|---|
| **Baseline (Flavor 1)** | `feat/dulcet-reset-pristine-semantic-dedup-all-UI-RM-HV-Slide2_LLM_Summary_Slide3_WhyNow_Action_17-Sep` | Slide 2 summaries, Slide 3 two-card narrative, reset-to-pristine, dedup, all common infrastructure. Frontend hardcodes the product family by keyword. |
| **Weighted-Family + Adjacencies (Flavor 2)** | `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3` | Everything in Baseline, plus: LLM-returned product family validated by weighted keyword scoring (`_FAMILY_KEYWORD_WEIGHTS`); grounded adjacent-opportunities paragraph; three-card Slide 3 with pillars moved to the orange panel; Copilot conditional fourth response section; `ensure_ascii=False` fix for `€`. |

Flavor 1 documentation is at `Docs/` root. Flavor 2 documentation is under `Docs/WeightedFamily/`.

## Getting Started

The `main` branch holds the historical state of this project from August 2026. The live, deployed code is on one of the two feature branches above. Clone the repository and check out the flavor you want:

```bash
git clone https://github.com/Vibe-Raj-Git/ing-fm-poc.git
cd ing-fm-poc

# For Flavor 1 (Baseline):
git checkout feat/dulcet-reset-pristine-semantic-dedup-all-UI-RM-HV-Slide2_LLM_Summary_Slide3_WhyNow_Action_17-Sep

# Or for Flavor 2 (Weighted-Family + Adjacencies):
git checkout feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3
```

To start new work, branch off the flavor you are targeting — not off `main`:

```bash
git checkout <the-flavor-branch>
git checkout -b feat/your-new-feature
```

## Architecture

The platform is a three-tier application:

- **Frontend:** React 18 + Vite + Tailwind CSS (`frontend/`)
- **Backend:** FastAPI + Python 3.11 (`main.py`, `pitchbook_builder.py`)
- **Data + AI:** Cloud SQL PostgreSQL 15 with `pgvector`; Vertex AI (`gemini-2.5-flash`, `text-embedding-004`)

The platform ingests unstructured corporate touchpoints (emails, Teams chats, RSS feeds, PDFs, WorkFabric memos), extracts structured signals via Gemini, and produces an 11-slide pitchbook across four product families (FX, Green/ESG, Rates, DCM).

Every displayed value traces to a specific row in a specific PostgreSQL table, filtered by `client_id`. The zero-fabrication principle is described in `Docs/Data_or_Fabrication.md` (Flavor 1) and `Docs/WeightedFamily/Data_or_Fabrication_20Sep_WeightedFamily.md` (Flavor 2).

**Current demo scope:** Enel S.p.A. (`CLI101`) is the primary demo client. BASF SE (`CLI103`) is a testable secondary. Both are controlled by the whitelist below.

## Full Documentation

The `Docs/` folder holds the complete architecture and operations reference.

### Common (both flavors)

| Document | Purpose |
|---|---|
| `Docs/Architecture_Decision_Hybrid_vs_LLM_Only.md` | Decision record — hybrid architecture over LLM-only |
| `Docs/Context_Fabric_Integration_Production.md` | Webhook ingestion spec for the Context Fabric agent |
| `Docs/Table_details.md` | Database schema catalog |
| `Docs/How_Signals_are_Converted_into_Opportunities.md` | Ingestion-to-pitchbook pipeline |
| `Docs/Signals,_Opportunities_&_Pitchbook_Lifecycle.md` | End-to-end data lifecycle |
| `Docs/Updated_Runbook.md` | Operational procedures |
| `Docs/DB_Records_Audit_Delete.md` | DB inspection runbook + reset-endpoint guidance |
| `Docs/PERFORMANCE_OPTIMIZATION.md` | Performance tuning trail |
| `Docs/Copilot_Test_Suite.md` | Copilot validation suite |
| `Docs/Live_Signal_feed.md` | Signal marquee mechanics |

### Flavor 1 (Baseline)

| Document | Purpose |
|---|---|
| `Docs/master_persona_20Sep.md` | Persona and architectural context |
| `Docs/architecture_flow_20Sep.md` | Architecture reference |
| `Docs/Data_or_Fabrication.md` | Zero-fabrication spec |
| `Docs/data_population.md` | Field-by-field UI lineage |

### Flavor 2 (Weighted-Family + Adjacencies)

| Document | Purpose |
|---|---|
| `Docs/WeightedFamily/README_WeightedFamily.md` | Flavor 2 overview and demo talking points |
| `Docs/WeightedFamily/master_persona_20Sep_WeightedFamily.md` | Persona and architectural context |
| `Docs/WeightedFamily/architecture_flow_20Sep_WeightedFamily.md` | Architecture reference |
| `Docs/WeightedFamily/Data_or_Fabrication_20Sep_WeightedFamily.md` | Zero-fabrication spec |
| `Docs/WeightedFamily/data_population_20Sep_WeightedFamily.md` | Field-by-field UI lineage |

## Testing

The primary correctness gate is `test_parity.py` — a 13-gate dynamic parity audit. It verifies:

- PostgreSQL connectivity via `get_db_connection`
- `ca.mkt_rates_curves` ground truth (5Y EUR swap 2.62%, 10Y Bund 2.61%)
- `ca.ext_credit_spreads` ground truth (Enel 5Y 78 bps, 10Y 80 bps)
- `/api/opportunities` returns client data with rates and spreads mapped
- Bundle integrity for pitchbook generation (curves, spreads, all-in yield)
- Base PPTX generation
- Copilot scenario override generation
- Non-destructive invariance (base record preserved)

Run before every deploy:

```bash
cd ~/ing-fm-poc
python3 test_parity.py
```

Expected output: `13/13 gates passed`.

Additional utilities:

- `dump_baseline.py` — regenerate `baseline_snapshots.json` from current DB state. Run after any DB content change that should become part of the pristine baseline.
- `enrich_basf_baseline.py` — insert curated signals and chunks for CLI103 (BASF). Idempotent; safe to re-run.

## Deployment

Pre-deploy verification:

```bash
cd ~/ing-fm-poc
python3 test_parity.py    # expected: 13/13 gates passed
```

Deploy to Cloud Run via the local shell alias:

```bash
deploy-poc
```

This is a shell alias for a `gcloud run deploy` command. It requires:

- `gcloud` authenticated with access to the `dulcet-radar-508218-c5` GCP project
- The Cloud SQL instance `ing-postgres-db` in `europe-west1` to be running
- The `db-postgres-pass` secret in Secret Manager to be accessible

The `Dockerfile` performs a two-stage build: `node:20-alpine` compiles the React frontend, then `python:3.11-slim` installs backend requirements and copies the application code plus `baseline_snapshots.json`.

Post-deploy verification:

```bash
SVC_URL=$(gcloud run services describe ing-fm-poc-service \
  --region europe-west1 --project dulcet-radar-508218-c5 \
  --format "value(status.url)")

curl -s "$SVC_URL/api/opportunities" | python3 -m json.tool | head -20
```

For Flavor 2, also verify the two new fields are returned for whitelisted clients:

```bash
curl -s "$SVC_URL/api/opportunities" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for o in d:
    if o.get('id') in ('CLI101', 'CLI103'):
        print(o.get('id'), '| family:', o.get('family'), '| adjacent present:', bool(o.get('adjacent_opportunities')))
"
```

## Repository Structure

```text
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
├── Docs/                         # Architecture documentation (common + Flavor 1)
│   └── WeightedFamily/           # Flavor 2 documentation set
├── archive/                      # Historical variants (not used at runtime)
├── assets/                       # Logos and icons
└── Test_Data/                    # Test fixtures
```

## Key Configuration

Environment variables read at runtime:

```text
INSTANCE_CONNECTION_NAME=dulcet-radar-508218-c5:europe-west1:ing-postgres-db
DB_USER=postgres
DB_NAME=postgres
GCP_PROJECT=dulcet-radar-508218-c5
REGION=europe-west1
```

Database password is retrieved from Secret Manager (`db-postgres-pass`).

**Demo whitelist.** The platform's demo scope is controlled by two synchronized lists:

- `main.py` — `_DEMO_CLIENT_IDS`
- `frontend/src/App.jsx` — `ACTIVE_UI_CLIENT_IDS`

These must remain in sync. The backend list controls LLM synthesis; the frontend list controls rendering. See `Docs/master_persona_20Sep.md` §6 (Flavor 1) or `Docs/WeightedFamily/master_persona_20Sep_WeightedFamily.md` §6 (Flavor 2).

**Credit rating display (both flavors).** Credit ratings are curated in a single dict per file (`_CREDIT_RATINGS`) in both `main.py` and `pitchbook_builder.py`. There is no `credit_rating` column on `ca.client_master` (§7.2 forbids DDL). Adding a new demo client requires adding its rating to both dicts.

**Product family weights (Flavor 2 only).** `_FAMILY_KEYWORD_WEIGHTS` is a weighted vocabulary for product family classification — also curated in both `main.py` and `pitchbook_builder.py`, and the two copies must remain byte-identical. See `Docs/WeightedFamily/master_persona_20Sep_WeightedFamily.md` §7.11 and §8.7.

## Branching Convention

| Branch | Purpose |
|---|---|
| `main` | Historical reference (Aug 2026). Not actively maintained. |
| `feat/dulcet-reset-pristine-...17-Sep` | Flavor 1 (Baseline). Preserved. |
| `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3` | Flavor 2 (Weighted-Family + Adjacencies). Current. |
| `feat/*` | Active development. Branch off the flavor you are working on. |
| `archive/*` | Optional tags for preserving specific states. |

The current working branch is always the one named at the top of this README.

## Verification Checklist

Before considering any deploy ready:

1. **Syntax:** `python3 -c "import ast; ast.parse(open('main.py').read())"` and the same for `pitchbook_builder.py`
2. **Frontend:** verify `frontend/src/App.jsx` has balanced braces
3. **Parity audit:** `python3 test_parity.py` — expected 13/13 gates passed
4. **Whitelist sync:** confirm `_DEMO_CLIENT_IDS` and `ACTIVE_UI_CLIENT_IDS` match
5. **Credit rating dict sync:** confirm `_CREDIT_RATINGS` in `main.py` and `pitchbook_builder.py` are aligned
6. **Family weights dict sync (Flavor 2):** confirm `_FAMILY_KEYWORD_WEIGHTS` in `main.py` and `pitchbook_builder.py` are byte-identical
7. **Clean working tree:** no `.bak*` files in the deploy path

Last updated: 20 September 2026