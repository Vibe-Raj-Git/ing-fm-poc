# ING Financial Markets Deal Intelligence Platform

**Current branch:** `feat/bfs-ai-lab-brand-toggle`
**Base flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Date:** 21 September 2026
**Status:** Both services deployed and verified

Internal use only. This repository contains environment-specific identifiers (GCP project, Secret Manager names) intended for internal use.

This branch ships a **runtime brand toggle** on top of Flavor 2. The same codebase — one branch, one Docker image, one PostgreSQL database — deploys as two independent Cloud Run services that render different brands. Brand selection is an environment variable, not a code fork, not a UI control, not a separate database.

| Service | Env var | Renders |
|---|---|---|
| `ing-fm-poc-service` | `BRAND=ING` | ING branding — orange accent, ING logos, "ING Copilot" |
| `bfs-ai-lab-service` | `BRAND=BFS_AI_LAB` | BFS AI Lab branding — turquoise accent, Cognizant BFS AI Lab logos, "BFS AI Lab Copilot" |

Both services read the same `ca.*` tables. Brand-specific text is substituted at read time on the way out of the API. No database content is neutralised or duplicated.

The branding feature is documented in full at `Docs/WeightedFamily/Brand_Toggle_Implementation.md`. The design brief that preceded implementation lives at `Docs/Prompt_Branding_Work_Continuation.md` — the two differ in several places, catalogued in §10 of the implementation record.

---

## 1. Two Brands, One Image

### The toggle

A single environment variable — `BRAND` — selects the active profile at service startup.

- Unset → defaults to ING. The ING service renders identically to its pre-toggle state.
- `BRAND=ING` → the ING profile.
- `BRAND=BFS_AI_LAB` → the BFS AI Lab profile.
- Unrecognized value → logs a warning naming the invalid value and the valid options, then falls back to ING.

The warning is deliberate — silent fallbacks hide errors. This is a lesson carried over from a past bug where a `NameError` inside a `try/except` masked a broken code path for sessions.

### What the profile controls

Each brand profile is a flat dict in `main.py` (`BRAND_PROFILES`). Twenty-eight keys covering:

- **Display strings** — name, full name, Copilot name, footer, attribution, API title
- **Logos** — white-background and orange-background filenames, render height in inches
- **Houseview fallbacks** — chip label, empty-state body, RSS fallback URL
- **Colors** — accent, accent hover, accent hover alt, accent light, accent tint, navy, navy hover, badge
- **Prompt personas** — five LLM persona strings (synthesis, proposal ref, compliance, Copilot prefix, adjacent phrase)
- **Filename prefixes** — long and short forms

Full key list and both profile values in `Docs/WeightedFamily/Brand_Toggle_Implementation.md` §3.

### Two shell aliases

Both defined in `~/.bashrc`. Same underlying `gcloud run deploy --source .` — the only differences are the service name and the `BRAND` value.

```bash
deploy-poc    # ing-fm-poc-service    with BRAND=ING
deploy-bfs    # bfs-ai-lab-service    with BRAND=BFS_AI_LAB
```

Each runs the full two-stage Docker build (Node → Python), pushes to Cloud Run, and routes 100% of traffic to the new revision.

---

## 2. Deployment

### Deploy both services

```bash
deploy-poc && deploy-bfs
```

Each deploy takes 3-5 minutes. The second reuses the Cloud Build cache from the first. Either service can be deployed independently.

### Public access on the BFS service

New Cloud Run services default to **private**. The ING service was granted `allUsers` invoker access earlier. The BFS service needs the same grant to be reachable from a browser:

```bash
gcloud run services add-iam-policy-binding bfs-ai-lab-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --member="allUsers" \
    --role="roles/run.invoker"
```

### Make the BFS service private again

```bash
gcloud run services remove-iam-policy-binding bfs-ai-lab-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --member="allUsers" \
    --role="roles/run.invoker"
```

### Pause a service without deleting it

Scale to zero — service stays deployed, URL stays valid, no compute cost when idle. Cold start on next request (~5-6 seconds).

```bash
gcloud run services update bfs-ai-lab-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --min-instances 0
```

Restore warm instance before a demo:

```bash
gcloud run services update bfs-ai-lab-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --min-instances 1
```

Same pattern applies to `ing-fm-poc-service`.

### Database impact

**No schema change. No DB mutation.** Both services read the same `ca.*` tables. The brand substitution happens in Python after the row is fetched — no `UPDATE`, no `INSERT`, no `DELETE`. The `reset-baseline` endpoint is unaffected.

### Environment variables

The full env var set on each service (identical apart from `BRAND`):

```
INSTANCE_CONNECTION_NAME=dulcet-radar-508218-c5:europe-west1:ing-postgres-db
DB_USER=postgres
DB_NAME=postgres
GCP_PROJECT=dulcet-radar-508218-c5
REGION=europe-west1
BRAND=<ING or BFS_AI_LAB>
```

DB password is mounted from Secret Manager (`db-postgres-pass:latest`).

---

## 3. Flavor 2 — What This Branch Adds Over Flavor 1

The platform has two parallel flavors, each originally on its own feature branch. They share the data tier, ingestion pipeline, database schema, and reset mechanism. They differ in the synthesis and pitchbook layers. **This branch is Flavor 2 plus branding.**

| Flavor | What it is |
|---|---|
| **Baseline (Flavor 1)** | Slide 2 summaries, Slide 3 two-card narrative, reset-to-pristine, dedup, all common infrastructure. Frontend hardcodes the product family by keyword. |
| **Weighted-Family + Adjacencies (Flavor 2)** | Everything in Baseline, plus: LLM-returned product family validated by weighted keyword scoring; grounded adjacent-opportunities paragraph; three-card Slide 3 with pillars moved to the orange panel; Copilot conditional fourth response section; `ensure_ascii=False` fix for `€`. |

### Three layers changed by Flavor 2

**Synthesis layer — two new prompt keys.**

The mandate synthesis prompt returns **seven keys** instead of five:

- `family` — the product family the LLM classifies the opportunity into: `FX_HEDGE`, `GREEN_ESG`, `RATES_HEDGE`, or `DCM_REFI`
- `adjacent_opportunities` — an 80-140 word business-English paragraph identifying up to 3 grounded cross-sell angles supported by the signal corpus

Both travel through the 8-tuple synthesis cache to the API response and the pitchbook bundle. Neither is persisted — no `family` or `adjacent_opportunities` column exists on `ca.ca_opportunity_scoring`.

**Pitchbook layer — weighted family classification + Slide 3 rework.**

- **Product family classifier.** The LLM's `family` proposal is validated by `_FAMILY_KEYWORD_WEIGHTS`, a weighted vocabulary that encodes the ING product taxonomy. Strong product signals (weight 5: `green bond`, `slb`, `emtn`, `irs pre-hedge`, `fx collar`) dominate weak context words (weight 1-2: `refinancing`, `maturity wall`, `dual-tranche`). When the anchor's weighted score is decisive (≥ 5 with margin ≥ 3), the weights override the LLM. Otherwise the LLM is trusted. When both are silent, a narrative keyword fallback fires.
- **Slide 3 layout.** The four pillars moved from the right column into the left orange panel. The right column now holds three stacked full-width cards: Catalyst Rationale, Proposed Execution, and **Adjacent Opportunities**.
- **Frontend hardcode removed.** The pre-20Sep frontend keyword branches on `opportunity_type` and client name are gone. The frontend reads `activeClient.family` from the API.

**Copilot layer — conditional fourth section + encoding fix.**

- The Copilot's `slide_3` payload now carries both `family` and `adjacent_opportunities`.
- The mandatory three-section response structure gains a conditional fourth section — **Adjacent Opportunities** — that appears only when the field is non-empty.
- `json.dumps(..., ensure_ascii=False)` in the Copilot prompt serialization so real `€` characters reach the LLM. Prior to this fix the Copilot occasionally echoed `\u20ac` in replies for Slide 3 while Slide 2 rendered `€`.
- The prompt requires bolding monetary amounts, percentages, and tenors in the "Key Mechanics & Deal Metrics" section.

### What is common with Flavor 1

Data architecture, ingestion pipeline, database schema, reset-to-pristine mechanism, defensive fallbacks, `priority_score` semantics, cache/DB consistency invariant, credit rating dict (`_CREDIT_RATINGS`), demo narratives, compliance architecture, deployment topology. All unchanged — and the branding toggle applies to both without modifying any of them.

---

## 4. Architecture

### Three-tier application

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND — React 18 + Vite + Tailwind (frontend/)                          │
│  · /api/brand fetch on mount sets seven CSS custom properties + tab title   │
│  · 130 hex values → var(--accent), var(--navy), etc.                        │
│  · 35 hardcoded ING strings → brand.* reads                                 │
│  · Loading gate blocks render until brand resolves (no flash of wrong brand)│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │  REST / binary stream
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  BACKEND — FastAPI + Python 3.11 (main.py)                                  │
│  · BRAND_PROFILES dict (ING + BFS_AI_LAB), ACTIVE_BRAND selected at startup │
│  · GET /api/brand returns the profile (excludes prompt_* and download_prefix)│
│  · GET /api/opportunities applies _brand_substitute to 10 text fields       │
│  · handle_pitchbook_generation calls _set_active_brand before build         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATA + AI TIER                                                             │
│  · Cloud SQL PostgreSQL 15 with pgvector — 12 tables in schema ca           │
│  · Vertex AI — gemini-2.5-flash (extraction, synthesis, copilot, compliance)│
│  · Vertex AI — text-embedding-004 (768-dim document chunks)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Deck builder brand access

`pitchbook_builder.py` holds a module-level slot rather than a `BRAND_PROFILES` copy:

```python
_ACTIVE_BRAND = None

def _set_active_brand(brand):
    global _ACTIVE_BRAND
    _ACTIVE_BRAND = brand

def _brand():
    if _ACTIVE_BRAND is not None:
        return _ACTIVE_BRAND
    return { ... minimal ING fallback ... }
```

`main.py` calls `pitchbook_builder._set_active_brand(ACTIVE_BRAND)` immediately before each `build_pitchbook()`. The deck builder reads its colors, logo path, footer, pillar bodies, and logo height from that slot.

**Brand is not in the `overrides` payload.** Overrides carry user-mutable session state. Brand is deployment configuration — it doesn't belong in user-mutable state.

### Colour reassignment at build time

At the top of `build_pitchbook()`:

```python
global ING_ORANGE, ING_NAVY, ING_LIGHT_ORANGE
_b = _brand()
ING_ORANGE = RGBColor(*_hex_to_rgb(_b.get("accent_color", "#FF6200")))
ING_NAVY = RGBColor(*_hex_to_rgb(_b.get("navy_color", "#000066")))
ING_LIGHT_ORANGE = RGBColor(*_hex_to_rgb(_b.get("accent_color_light", "#FFEBDC")))
```

All 29 existing usages of `ING_ORANGE`, `ING_NAVY`, `ING_LIGHT_ORANGE` keep working — they read the reassigned values. The `ING_*` names stay; they're internal identifiers, not user-visible strings.

### Read-path substitution scope

Ten text fields in `/api/opportunities` are wrapped in `_brand_substitute` at the point they enter the response dict:

| Field | Source |
|---|---|
| `why_now`, `action` | LLM synthesis — full narratives, Slide 3 |
| `why_now_summary`, `action_summary` | LLM synthesis — max 160 chars, Slide 2 |
| `adjacent_opportunities` | LLM synthesis — 80-140 word paragraph, Slide 3 |
| `cf_description`, `cf_latent` | DB — Desk Signal, Latent opportunity |
| `hv_doc_title`, `hv_doc_summary` | DB — Houseview chip, body |
| `news_headline` | DB — Live Verified News |

**The substitution is a word-boundary regex:** `re.sub(r'\bING\b', ACTIVE_BRAND["name"], text)`. It matches `ING` as a standalone token, not `DOING`, `USING`, `INGESTED`. **No-op when the brand is ING** — the ING path is byte-identical to its pre-toggle behaviour.

**Emails are intentionally not substituted.** `@ing.com` stays `@ing.com` under BFS. An email address is a factual reference to a person at ING, not brand chrome.

**The substitution is applied in Python after the row is fetched** — never in SQL. Both services read the same rows and transform on the way out. No `UPDATE`, no DB mutation.

### Interactive fetch flow

```
Browser → /api/brand            → brand profile (colors, names, logos, title)
Browser → /api/opportunities    → client records; 10 text fields substituted
Browser → /api/pitchbook/generate → main.py sets deck brand, builds deck
```

No frontend needs to know the toggle exists. It fetches once and renders with what it receives.

---

## 5. Repository Structure

```
.
├── main.py                          # FastAPI backend — BRAND_PROFILES, /api/brand, read-path substitution
├── pitchbook_builder.py             # PPTX generation — _brand() accessor, dynamic colours/logo/positions
├── frontend/                        # React source
│   ├── src/App.jsx                  # Brand fetch, CSS variables, 35 string replacements
│   ├── index.html                   # Neutral <title> placeholder (React sets the real title)
│   └── public/assets/
│       ├── ing_logo_white.png       # ING logo — 15 KB
│       ├── ing_logo_orange.png      # ING logo — 15 KB
│       ├── bfs_ai_lab_logo_white.png   # BFS AI Lab logo — 76 KB (optimized)
│       └── bfs_ai_lab_logo_orange.png  # BFS AI Lab logo — 76 KB (optimized)
├── assets/                          # Deck-side logos (same files as frontend/public/assets)
│   ├── ing_logo_white.png
│   ├── ing_logo_orange.png
│   ├── bfs_ai_lab_logo_white.png
│   └── bfs_ai_lab_logo_orange.png
├── Docs/                            # Architecture documentation
│   ├── Prompt_Branding_Work_Continuation.md    # Design brief (pre-implementation)
│   └── WeightedFamily/              # Flavor 2 + branding documentation
│       ├── README_WeightedFamily.md
│       ├── Brand_Toggle_Implementation.md      # Branding implementation record
│       ├── master_persona_20Sep_WeightedFamily.md
│       ├── architecture_flow_20Sep_WeightedFamily.md
│       ├── Data_or_Fabrication_20Sep_WeightedFamily.md
│       ├── data_population_20Sep_WeightedFamily.md
│       ├── Different_Signals_Different_Products_20Sep_WeightedFamily.md
│       ├── End_to_end_Pitchbook_data_20Sep_WeightedFamily.md
│       ├── Explain_Left_Client_Section_20Sep_WeightedFamily.md
│       ├── How_Signals_are_Converted_into_Opportunities_20Sep_WeightedFamily.md
│       ├── Signals,_Opportunities_&_Pitchbook_Lifecycle_20Sep_WeightedFamily.md
│       └── SYSTEM_ARCHITECTURE_&_DATA_CONTRACT_GUARDRAIL_20Sep_WeightedFamily.md
├── baseline_snapshots.json          # Reset-to-pristine snapshot
├── dump_baseline.py                 # Snapshot generator
├── enrich_basf_baseline.py          # Curated baseline content utility (CLI103)
├── test_parity.py                   # 13-gate parity audit — run before every deploy
├── Dockerfile                       # Two-stage build (node:20-alpine → python:3.11-slim)
├── requirements.txt                 # Python dependencies
├── archive/                         # Historical variants (git-ignored)
└── README_Flavor2.md                # Original README for the demo branch (kept for reference)
```

### Key files at a glance

| File | Purpose |
|---|---|
| `main.py` | FastAPI backend — `BRAND_PROFILES`, `ACTIVE_BRAND`, `_brand_substitute`, `/api/brand`, read-path substitution |
| `pitchbook_builder.py` | PPTX generation — `_set_active_brand`, `_brand`, dynamic colour/logo/position reads |
| `frontend/src/App.jsx` | Brand fetch, CSS custom properties, `document.title`, 35 string replacements, loading gate |
| `frontend/index.html` | Neutral `<title>` placeholder — React replaces it after the brand resolves |
| `test_parity.py` | 13-gate audit — must pass 13/13 before every deploy |

---

## 6. Documentation

The `Docs/WeightedFamily/` folder holds the complete documentation set for this branch. The branding doc is new; the Flavor 2 docs predate it and remain accurate.

| Document | Purpose |
|---|---|
| **`Brand_Toggle_Implementation.md`** | **What was built for the runtime brand toggle.** Architecture, profile keys, backend, deck builder, frontend, deploy, verification, recovery points, and nine deviations from the original design brief. |
| `master_persona_20Sep_WeightedFamily.md` | Persona and architectural context. §2.1 has the full Flavor Differential table. §7.11, §8.7, §13 are Flavor 2-specific. |
| `architecture_flow_20Sep_WeightedFamily.md` | Complete architecture reference. §5.6 (product family classification), §5.7 (adjacent opportunities), §6.5 (Slide 3 layout), §7.2 (Copilot additions), §11 (principles 11-13). |
| `Data_or_Fabrication_20Sep_WeightedFamily.md` | Zero-fabrication spec. §6.2 (7-key prompt), §6.8 (product family), §6.9 (adjacent opportunities), §9 (Copilot additions), §11.10 (`_FAMILY_KEYWORD_WEIGHTS` sync). |
| `data_population_20Sep_WeightedFamily.md` | Field-by-field UI lineage. §2.1 (family-derived predicates), §4.6 (Slide 3 update). |
| `Different_Signals_Different_Products_20Sep_WeightedFamily.md` | How Flavor 2 classifies multi-signal clients. Dominant family + adjacency paragraph. Multi-card architecture noted as a future option. |
| `End_to_end_Pitchbook_data_20Sep_WeightedFamily.md` | End-to-end data binding from the dashboard to the pitchbook. Corrected slide count (11), four real families, known exceptions, Flavor 2-specific additions. |
| `Explain_Left_Client_Section_20Sep_WeightedFamily.md` | Section walkthrough of the Client Opportunity Card — the 2×2 grid, the Synthesized Mandate section, the Priority Today sidebar, the Action Bar, and the family classifier. Includes a 30-second executive pitch. |
| `How_Signals_are_Converted_into_Opportunities_20Sep_WeightedFamily.md` | Signal-to-opportunity pipeline. End-to-end stages, two-layer dedup, anchor pattern, the 7-key synthesis prompt, drift guard, family classification, adjacent opportunities. |
| `Signals,_Opportunities_&_Pitchbook_Lifecycle_20Sep_WeightedFamily.md` | End-to-end lifecycle: signal arrival → accumulation → discovery → ranking → preview → PPTX → compliance. Includes the Flavor 2 classification and adjacent-opportunities additions. |
| `SYSTEM_ARCHITECTURE_&_DATA_CONTRACT_GUARDRAIL_20Sep_WeightedFamily.md` | Verified schema (12 tables), slide-by-slide resolution contract, 3-tier hierarchy, invariance rules, 13-gate parity audit, exception catalog (5.1-5.8). |
| `README_WeightedFamily.md` | Folder index — Flavor 2 overview and demo talking points (pre-branding). |

### Design brief

`Docs/Prompt_Branding_Work_Continuation.md` records the intended design as of 18 September 2026, before any branding code was written. **This is not a spec — it's a historical artifact.** Where it diverges from the implementation, the implementation record is authoritative. The nine deviations are catalogued in `Brand_Toggle_Implementation.md` §10.

### Related docs outside this folder

`README_Flavor2.md` at repo root is the original landing doc for the demo branch. It predates branding and describes the platform without the toggle. Kept for reference.

### Demo talking points

**Primary pitch.** The dominant opportunity — for Enel, the €1.0bn dual-tranche green issuance refinancing the €10.13bn maturity wall. Flavor 2's classifier selects the Green/ESG deck template deterministically (Enel's anchor scores 15 GREEN_ESG vs 5 DCM_REFI, a margin of 10 — decisive).

**Supplementary section — Adjacent Opportunities.** The platform has processed every ingested signal, not just the primary drivers. Slide 3's third card surfaces what else the bank can pitch. For Enel, the paragraph cites a rate pre-hedge, a USD FX exposure review, and liability-management structuring.

**Branding angle.** The same codebase, same database, same 11-slide deck structure — just a different `BRAND` env var and the presentation follows. Two audiences, two Cloud Run services, zero code fork.

**Voiceover guidance.** The RM presents the primary recommendation first, then points at the third card: *"Beyond the primary issuance, we've processed the full signal corpus and identified adjacent angles worth a conversation — a pre-hedge ahead of pricing, an FX review of the USD-linked procurement flows, and possible liability management. These aren't part of the primary proposal, but they're on the table if you'd like to explore them."*

---

## 7. Verification

### 7.1 The parity gate — run before every deploy

```bash
cd ~/ing-fm-poc
python3 test_parity.py
```

Expected: `13/13 GATES PASSED`. The audit verifies PostgreSQL connectivity via `get_db_connection`, `ca.mkt_rates_curves` ground truth (5Y EUR swap 2.62%, 10Y Bund 2.61%), `ca.ext_credit_spreads` ground truth (Enel 5Y 78 bps, 10Y 80 bps), `/api/opportunities` integrity, bundle consistency, base PPTX generation, Copilot override generation, and non-destructive invariance.

**The audit does not exercise the deck-generation HTTP path.** It calls `build_pitchbook()` directly. The `_set_active_brand` call from `handle_pitchbook_generation` is only tested by hitting the API endpoint (see §7.3).

### 7.2 Local development test

```bash
# Start with default (ING) brand
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080

# Or with BFS AI Lab
BRAND=BFS_AI_LAB python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
```

In a second terminal:

```bash
curl -s http://localhost:8080/api/brand | python3 -m json.tool
curl -s http://localhost:8080/api/opportunities | python3 -c "
import sys, json
d = json.load(sys.stdin)
for o in d:
    if o.get('id') == 'CLI101':
        print(o.get('id'), '| family:', o.get('family'), '| adj present:', bool(o.get('adjacent_opportunities')))
"
```

### 7.3 Post-deploy — both services

```bash
SVC_URL=$(gcloud run services describe ing-fm-poc-service --region europe-west1 --project dulcet-radar-508218-c5 --format "value(status.url)")
BFS_URL=$(gcloud run services describe bfs-ai-lab-service --region europe-west1 --project dulcet-radar-508218-c5 --format "value(status.url)")

echo "ING: $SVC_URL"
echo "BFS: $BFS_URL"

curl -s "$SVC_URL/api/brand" | python3 -m json.tool | head -3
curl -s "$BFS_URL/api/brand" | python3 -m json.tool | head -3
```

Expected: `"name": "ING"` from the first, `"name": "BFS AI Lab"` from the second.

**Deck filename check:**

```bash
curl -s -X POST "$BFS_URL/api/pitchbook/generate" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"CLI101"}' \
  -D /tmp/bfs_headers.txt \
  -o /tmp/bfs_test.pptx

grep -i "content-disposition" /tmp/bfs_headers.txt
ls -la /tmp/bfs_test.pptx
```

Expected: `filename="BFS_AI_LAB_Enel_S.p.A._Pitchbook.pptx"` and a file around 800 KB.

### 7.4 Visual checks in the browser

**ING service** — hard-refresh (`Ctrl+Shift+R`):

| Element | Expected |
|---|---|
| Header badge | Orange |
| Buttons (Download, Compliance Audit, chat send) | Orange |
| Pillar headings | Navy |
| Copilot name | `ING Copilot` |
| Browser tab | `ING Financial Markets Insights` |
| Download filename | `ING_Enel_S.p.A._Pitchbook.pptx` |

**BFS AI Lab service** — hard-refresh:

| Element | Expected |
|---|---|
| Header badge | Navy (`#0A3168`) |
| Buttons | Turquoise (`#10C4C0`) |
| Pillar headings | BFS navy |
| Copilot name | `BFS AI Lab Copilot` |
| Browser tab | `BFS AI Lab Financial Markets Insights` |
| Download filename | `BFS_AI_LAB_Enel_S.p.A._Pitchbook.pptx` |
| Deck size | ~800 KB |

### 7.5 Demo prep notes

**Warm the cache first.** The mandate synthesis cache (`_MANDATE_SYNTH_CACHE`) is per-service, in-memory. The adjacent-opportunities paragraph and priority score come from the cache on deck generation. If the cache is cold, the adjacent card renders the fallback text: *"Additional origination angles will appear here once the mandate synthesis identifies any."*

**Warm it by loading the dashboard first.** `/api/opportunities` triggers synthesis on cache miss. Then generate the deck.

**Watch Vertex AI quota.** Repeated synthesis calls across many sessions can hit `429 RESOURCE_EXHAUSTED`. The Enel-only whitelist halves the per-cycle call count. For a live demo, warm the cache 5-10 minutes before the call and avoid rapid page reloads.

### 7.6 Pre-deploy checklist

1. **Syntax** — `python3 -c "import ast; ast.parse(open('main.py').read())"`, same for `pitchbook_builder.py`
2. **Frontend brace balance** — approximate JSX structural check
3. **Parity audit** — `python3 test_parity.py`, expected 13/13
4. **Whitelist sync** — confirm `_DEMO_CLIENT_IDS` in `main.py` matches `ACTIVE_UI_CLIENT_IDS` in `App.jsx`
5. **`_CREDIT_RATINGS` sync** — confirm the two copies are aligned
6. **`_FAMILY_KEYWORD_WEIGHTS` sync** — confirm the two copies are byte-identical
7. **Clean working tree** — no `.bak*` or `.prepatch.*` files in the deploy path

---

## 8. Branching Convention

| Branch | Purpose |
|---|---|
| `main` | Historical reference (Aug 2026). Not actively maintained. |
| `feat/dulcet-reset-pristine-...17-Sep` | Flavor 1 (Baseline). Preserved. |
| `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3` | Flavor 2 (Weighted-Family + Adjacencies). The demo branch — no branding code. |
| `feat/bfs-ai-lab-brand-toggle` | **This branch.** Flavor 2 plus the runtime brand toggle. |

**The demo branch is untouched by the branding work.** If you need the Flavor 2 feature set without branding, check out `feat/dulcet-20Sep-demo-...`. If you need both, check out this branch.

To start new work, branch off the branch you're targeting — not off `main`:

```bash
git checkout feat/bfs-ai-lab-brand-toggle
git checkout -b feat/your-new-feature
```

### Demo whitelist

The demo scope is controlled by two synchronized lists:

- `main.py` — `_DEMO_CLIENT_IDS` (currently `{"CLI101"}`)
- `frontend/src/App.jsx` — `ACTIVE_UI_CLIENT_IDS` (currently `["CLI101"]`)

The backend list controls LLM synthesis and the signal feed scope. The frontend list controls rendering. **Both must be updated together.**

**BASF SE (`CLI103`) is currently excluded.** It was used to test the reset-to-pristine shield icon and LLM semantic deduplication in earlier sessions — both now verified. Removing BASF from the whitelist halves Vertex AI quota consumption per cold-cache cycle and prevents the `429 RESOURCE_EXHAUSTED` seen under repeated testing.

**To re-enable BASF for destructive testing**, change the two lines and redeploy both services.

---

## 9. Recovery Points

Three annotated tags on this branch, pushed to GitHub.

| Tag | Commit | State |
|---|---|---|
| `ing-baseline-pre-branding` | `3d1bb16` | BFS logos committed, no branding code — pure ING behaviour |
| `branding-working-pre-color` | `565d8e3` | Toggle working end-to-end, both services deployed, before the colour rebrand |
| `branding-complete-enel-only` | `82d75d0` | Full feature — colours, dynamic filename, logo optimization, Enel-only whitelist |

**Restore a single file from a tag:**

```bash
git checkout branding-working-pre-color -- main.py
```

**Restore everything to a tag:**

```bash
git reset --hard branding-working-pre-color
```

**Local file backups** (outside the repo, at `~/ing-fm-poc-backups/`):

| Timestamp | Contents |
|---|---|
| `20260921_042605` | `main.py`, `pitchbook_builder.py`, `App.jsx` — before the branding patches |
| `20260921_054602_shellrc` | `~/.bashrc` — before the alias edits |
| `20260921_064930_pre_color_rebrand` | Four files — before the colour rebrand |
| `*_pre_logo_resize` | BFS logos at original 3.26 MB resolution |

---

## 10. Known Backlog

### Polish items (cosmetic, deferred)

Two deck-layout differences between the React preview and the generated PPTX on the BFS service:

1. **Slide 1** — the `Financial Markets Origination` text box's right edge doesn't exactly match the BFS logo's right edge. ~0.40" offset. Preview is unaffected (CSS flex handles alignment). Fixable with a per-brand logo aspect ratio key plus a computed text box position.
2. **Slide 3** — the BFS logo (bottom edge at y=0.95") slightly overlaps the Catalyst card (top edge at y=0.85"). ~0.10" overlap. Preview is unaffected.

Neither affects content, functionality, or legibility materially.

### Dormant fallbacks (documented, not active)

- `COALESCE(priority_score, 75)` at `main.py:225` and `main.py:727` — substitutes a fabricated score when a client has no scoring row. All current clients have scores; the fallback never fires.
- `pitchbook_builder.py:1045` — hardcoded revenue/EBITDA strings that fire if `revenue_str` or `ebitda_str` resolve to `N/A`. Bundle returns populated values.
- `main.py:602` — swap pre-hedge fallback string mentioning the removed €500M overlay. Fires only when `current_action` is empty.

### Sync invariants (must remain aligned)

- `_CREDIT_RATINGS` — `main.py` and `pitchbook_builder.py`
- `_FAMILY_KEYWORD_WEIGHTS` — `main.py` and `pitchbook_builder.py` (byte-identical)
- `_DEMO_CLIENT_IDS` / `ACTIVE_UI_CLIENT_IDS` — `main.py` and `App.jsx`
- `BRAND_PROFILES` — single source in `main.py`; `pitchbook_builder.py` reads from the module-level slot, no copy

### Ingestion pipeline duplicate-row hazard

`ca.ext_company_filings` can contain multiple rows per client with identical `reporting_period`. Reads that pick "the latest row" via `ORDER BY ... LIMIT 1` can land on a NULL-revenue row. Current mitigation: `fetch_pitchbook_bundle` filters `AND reported_revenue_eur_m IS NOT NULL`. Root-cause fix (upsert on ingest) is a backlog item.

---

*AI Architect & Developer: Rajarshi Pathak (rajarshi.pathak@cognizant.com) | Senior Manager | AI Consulting CoE*
*Last updated: 21 September 2026*
*Branch: `feat/bfs-ai-lab-brand-toggle`*
*Brand toggle implementation record: `Docs/WeightedFamily/Brand_Toggle_Implementation.md`*
```
