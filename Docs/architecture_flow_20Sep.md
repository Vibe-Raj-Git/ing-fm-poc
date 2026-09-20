# ING Financial Markets Deal Intelligence & Origination Platform

## Architecture & Technical Reference — 20 September 2026

**Status:** Authoritative
**Supersedes:** `architecture_flow_14Sep.md`, `architecture_flow_28Aug.md`, `architecture_flow_19Aug (1).md`, `architecture_flow (2).md`
**Audience:** Engineers, Business Analysts, Technical Architects working on the codebase and product

---

## 1. Executive Summary

The ING Financial Markets Deal Intelligence Platform ingests unstructured corporate and market
signals, identifies actionable origination opportunities, generates a curated mandate narrative,
and produces client-ready pitchbooks across four product families (FX, Green/ESG, Rates, DCM).

The current architecture is a three-tier application:

- **Frontend:** React 18 + Vite + Tailwind, single-page workspace
- **Backend:** FastAPI (Python 3.11) with async endpoints
- **Data + AI:** PostgreSQL 15 (Cloud SQL, with `pgvector`), Vertex AI (`gemini-2.5-flash`, `text-embedding-004`)

Everything the platform displays is sourced from the database or from an LLM extraction grounded
in database content. There are no hardcoded client values, no fabricated metrics, and no
placeholder strings in the presentation layer.

**Current demo scope:** Enel S.p.A. (`CLI101`) is the primary demo client. BASF SE
(`CLI103`) is a testable secondary client — whitelisted alongside Enel as of 20 Sep 2026 to
exercise the multi-client display paths. Both are controlled by the whitelist below.

`_DEMO_CLIENT_IDS = {"CLI101", "CLI103"}` on the backend and
`ACTIVE_UI_CLIENT_IDS = ["CLI101", "CLI103"]` on the frontend.

For an Enel-primary demo, revert both whitelists to `{"CLI101"}` / `["CLI101"]` before the
presentation. See `master_persona_20Sep.md` §2.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       ING FM Deal Intelligence Platform                         │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  FRONTEND (React 18 + Vite + Tailwind)                                    │  │
│  │                                                                           │  │
│  │  • Live Signal Marquee (Enel-only, deduplicated, filtered by whitelist)   │  │
│  │  • Opportunity Cards (Client Data | Market Data | Context | Houseviews)   │  │
│  │  • 11-Slide Pitchbook Canvas (React preview, 1:1 PPTX parity)             │  │
│  │  • ING Copilot Sidebar (context-grounded LLM, state mutation)             │  │
│  │  • Score Tooltip (LLM-estimate provenance note)                           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                  │  REST / Binary stream                        │
│                                  ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  BACKEND (FastAPI / Uvicorn)                                              │  │
│  │                                                                           │  │
│  │  Ingestion         Read API              LLM / Copilot      Pitchbook     │  │
│  │  ─────────         ────────              ─────────────      ─────────     │  │
│  │  /api/ingest/text  /api/opportunities    /api/copilot/chat  /api/pitchbook│  │
│  │  /api/ingest/file  /api/signals          /api/chat          /generate     │  │
│  │  /api/rss/feed     /api/metrics          /api/check-        /api/pitchbook│  │
│  │                    /api/client/{id}/     compliance         /download     │  │
│  │                    maturities                                             │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                  │                                              │
│                                  ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  DATA + AI TIER                                                           │  │
│  │                                                                           │  │
│  │  Cloud SQL (PostgreSQL 15 + pgvector)   Vertex AI                         │  │
│  │  • ca.client_master                     • gemini-2.5-flash                │  │
│  │  • ca.ext_company_filings                 (signal extraction,             │  │
│  │  • ca.debt_maturity_schedule              mandate synthesis,              │  │
│  │  • ca.mkt_rates_curves                    copilot, compliance)            │  │
│  │  • ca.ext_credit_spreads                • text-embedding-004              │  │
│  │  • ca.ca_opportunity_scoring              (768-dim chunks)                │  │
│  │  • ca.digital_twin_signals                                                │  │
│  │  • ca.document_vector_chunks                                              │  │
│  │  • ca.coverage_teams                                                      │  │
│  │  • ca.ext_deals                                                           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Deployment:** Cloud Run (`europe-west1`), 1 vCPU / 512 MiB, `min-instances=1`,
`max-instances=1`. Single warm instance keeps the in-memory mandate synthesis cache shared
across requests.

---

## 3. Omni-Channel Ingestion & Signal Extraction

The platform ingests unstructured content from five channels:

| Channel | Endpoint | Typical use |
|---|---|---|
| PDF / PPTX upload | `/api/ingest/file` | Houseviews, client filings |
| RSS news | `/api/ingest/text` (from `/api/rss/feed`) | Live market news |
| Treasury email | `/api/ingest/text` | Inbound client correspondence |
| Microsoft Teams | `/api/ingest/text` | Internal deal channels |
| WorkFabric memo | `/api/ingest/text` | Internal desk notes, latent opportunities |

### 3.1 Pipeline

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 1 — TEXT EXTRACTION                                                    │
│  • PDF: pypdf reads all pages                                                │
│  • PPTX: python-pptx reads all shapes with text frames                       │
│  • Plain text: passed through                                                │
│  • Truncated to 4,000 characters before further processing                   │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 2 — GEMINI MULTI-SIGNAL EXTRACTION                                     │
│  • Model: gemini-2.5-flash                                                   │
│  • Prompt asks for a JSON object with a "detected_signals" array             │
│  • Each signal has: signal_type, catalog_family, metric_identified,          │
│    trigger_summary, metric_value, description, confidence_pct, urgency       │
│  • One document → N signals (typically 5–7 for a houseview PDF)              │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 3 — PERSISTENCE                                                        │
│  • INSERT INTO ca.document_vector_chunks (one row per ingestion)             │
│  • INSERT INTO ca.digital_twin_signals (one row per detected signal)         │
│  • Dedup guard: skip if (client_id, trigger_summary) already exists          │
│  • Ingestion does NOT write to ca.ca_opportunity_scoring                     │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 4 — CACHE INVALIDATION                                                 │
│  • New signal advances MAX(created_at) in digital_twin_signals               │
│  • Next /api/opportunities call is a synthesis cache miss                    │
│  • Fresh mandate narrative is generated for whitelisted clients              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Multi-Signal Extraction (why it matters)

A single PDF may contain several distinct signals — a refinancing trigger, a funding
authorisation, an FX exposure, an interest-rate sensitivity. Each is captured as a separate
row in `ca.digital_twin_signals`, so downstream components (marquee, mandate synthesis,
pitchbook) can reason over them individually.

Prior to 14 Sep 2026, ingestion wrote a single row per source. This under-represented
multi-topic documents and inflated the mandate card with whatever the LLM chose as the top
signal.

### 3.3 Deduplication

The dedup guard checks for an existing signal with the same `(client_id, trigger_summary)`
pair. If found, the new ingestion is skipped. This prevents table growth when the same
document is re-uploaded or when overlapping news articles cover the same fact.

### 3.4 Source Channel Normalisation

Ingested content is classified into one of these `source_channel` values:

| Channel value | Source |
|---|---|
| `PDF_REPORT` | PDF / PPTX uploads |
| `NEWS_RSS` | Google News RSS |
| `CLIENT_EMAIL` | Treasury / client email |
| `TEAMS_CHAT` | Microsoft Teams |
| `WORKFABRIC_MEMO` | Internal memos, latent opportunities |

---

## 4. Database Schema

All tables live in the `ca` schema of the Cloud SQL PostgreSQL instance.

### 4.1 Live Tables (referenced by code)

#### `ca.client_master`

Client master data. Resolved once per opportunity card.

| Column | Type | Notes |
|---|---|---|
| `client_id` | varchar (PK) | e.g. `CLI101` |
| `client_name` | varchar | e.g. `Enel S.p.A.` |
| `group_parent` | varchar | |
| `legal_entity` | varchar | |
| `industry_sector` | varchar | |
| `country` | varchar | |
| `region` | varchar | |
| `ownership_type` | varchar | |
| `tier` | varchar | e.g. `Tier 1` |
| `hq_country` | varchar | |
| `revenue_eur_m` | numeric | Millions EUR |
| `rm_name` | varchar | Fallback if no coverage_teams row |
| `base_ccy` | varchar | |

#### `ca.ext_company_filings`

Balance sheet and liquidity, one row per reporting period.

| Column | Type | Notes |
|---|---|---|
| `filing_id` | varchar (PK) | |
| `client_id` | varchar | |
| `reporting_period` | varchar | e.g. `FY2024 / Q2 2026` |
| `net_debt_eur_m` | numeric | Millions |
| `liquidity_eur_m` | numeric | Millions |
| `ebitda_eur_m` | numeric | Millions |
| `reported_revenue_eur_m` | numeric | Millions |
| `debt_maturing_24m_eur_m` | numeric | Millions |
| `notes` | text | |

#### `ca.debt_maturity_schedule`

Individual debt instruments. Used by the maturity ladder and slide 5 of the pitchbook.

| Column | Type |
|---|---|
| `isin` | varchar |
| `client_id` | varchar |
| `instrument_type` | varchar |
| `amount_eur_m` | numeric |
| `maturity_year` | integer |
| `coupon_rate_pct` | numeric |
| `currency` | varchar |

#### `ca.mkt_rates_curves`

Market rates by currency and tenor. Refreshed periodically.

| Column | Type |
|---|---|
| `curve_id` | integer (PK) |
| `curve_date` | date |
| `currency` | varchar |
| `tenor` | varchar |
| `swap_rate_pct` | numeric |
| `govt_yield_pct` | numeric |
| `category` | varchar |

#### `ca.ext_credit_spreads`

Issuer and rating-bucket credit spreads.

| Column | Type |
|---|---|
| `spread_id` | integer (PK) |
| `quote_date` | date |
| `issuer_or_rating` | varchar |
| `sector` | varchar |
| `tenor` | varchar |
| `spread_bps` | numeric |
| `all_in_yield_pct` | numeric |
| `source` | varchar |

#### `ca.ca_opportunity_scoring`

The curated opportunity record. Holds the anchor narrative used by mandate synthesis.

| Column | Type | Notes |
|---|---|---|
| `opportunity_id` | varchar (PK) | |
| `client_id` | varchar | |
| `opportunity_type` | varchar | Free text (business label) |
| `trigger_source` | text | |
| `est_revenue_eur_000` | numeric | Fee estimate in thousands |
| `propensity_score` | integer | LLM-derived estimate, unused in display |
| `value_score` | integer | LLM-derived estimate, unused in display |
| `priority_score` | integer | LLM-derived; drives card ranking |
| `rank` | integer | Unused by current code |
| `next_best_action` | text | **Anchor: curated mandate action** |
| `why_now_nlg` | text | **Anchor: curated catalyst rationale** |

#### `ca.digital_twin_signals`

Extracted signals from all ingestion sources.

| Column | Type |
|---|---|
| `signal_id` | varchar (PK) |
| `client_id` | varchar |
| `catalog_family` | varchar |
| `signal_type` | varchar |
| `metric_identified` | text |
| `trigger_summary` | text |
| `metric_value` | varchar |
| `description` | text |
| `confidence_pct` | integer |
| `urgency` | varchar |
| `created_at` | timestamp |

#### `ca.document_vector_chunks`

Ingestion chunks with optional embeddings and structured metadata.

| Column | Type | Notes |
|---|---|---|
| `chunk_id` | bigint (PK) | |
| `client_id` | varchar | |
| `source_channel` | varchar | See §3.4 |
| `source_name` | varchar | Filename or source label |
| `text_content` | text | Extracted text |
| `structured_metadata` | jsonb | Contains `detected_signals[]`, `executive_summary` |
| `embedding` | vector(768) | `pgvector` dense vector |
| `created_at` | timestamp | |

#### `ca.coverage_teams`

Relationship managers and coverage team members.

| Column | Type |
|---|---|
| `client_id` | varchar |
| `role_title` | varchar |
| `banker_name` | varchar |
| `location` | varchar |

### 4.2 Legacy Tables (not referenced by current code)

**Orphan tables** — exist in the schema but are not read by any live code path:

- `ca.dt_client_master` — earlier reduced-column version of `ca.client_master`
- `ca.ca_opportunity_scoring_backup` — snapshot table
- `ca.cand5_client_master` — candidate/deprecated schema (empty)

**Data tables not currently surfaced** — populated but not read by any endpoint:

- `ca.ext_deals` — ING track record and credentials. Contains 3 rows (2 for Enel,
  1 for BASF). Client IDs are canonical after the 14 Sep 2026 cleanup. Candidate
  for the "Why Execute With Us" slide, which currently renders generic capability
  cards instead of client-specific credentials.

Current contents:

  | Deal ID | Client | Type | Volume | Role | Date |
  |---|---|---|---|---|---|
  | `DEAL_ENEL_01` | `CLI101` | Sustainability-Linked Bond | €1,500M | Joint Active Bookrunner | 2025-06-15 |
  | `DEAL_ENEL_02` | `CLI101` | Multi-Currency RCF Refinancing | €3,000M | Mandated Lead Arranger & Bookrunner | 2024-11-20 |
  | `DEAL_BASF_01` | `CLI103` | Green Bond Issuance | €1,000M | Joint Bookrunner | 2025-03-10 |

### 4.3 Data Lineage — Which API reads which table

| Endpoint | Tables read |
|---|---|
| `/api/opportunities` | `client_master`, `ext_company_filings`, `debt_maturity_schedule`, `mkt_rates_curves`, `ext_credit_spreads`, `ca_opportunity_scoring`, `digital_twin_signals`, `document_vector_chunks`, `coverage_teams` |
| `/api/signals` | `digital_twin_signals`, `client_master` |
| `/api/metrics` | `ca_opportunity_scoring`, `client_master`, `digital_twin_signals` — returns `clients_with_signals`, `active_signals`, `high_priority_clients`, `clients_in_database` (all whitelist-scoped except the last) |
| `/api/client/{id}/maturities` | `debt_maturity_schedule` |
| `/api/copilot/chat` | Reads via `fetch_pitchbook_bundle` — same set as opportunities |
| `/api/check-compliance` | Same bundle as copilot |
| `/api/pitchbook/generate` | Same bundle as copilot |
| `/api/ingest/*` | Writes only |

### 4.4 Client ID Consistency

All tables use canonical client IDs (`CLI001`, `CLI002`, ... `CLI105`). Legacy
IDs (`CLI009_ENEL`, `CLI010_BASF`) were migrated to canonical forms on
14 Sep 2026:

| Legacy ID | Canonical ID | Tables affected |
|---|---|---|
| `CLI009_ENEL` | `CLI101` | `ca.digital_twin_signals`, `ca.ext_deals` |
| `CLI010_BASF` | `CLI103` | `ca.digital_twin_signals`, `ca.document_vector_chunks`, `ca.ext_deals` |

Any new ingestion or data load must use the canonical ID. The backend normalises
legacy forms defensively in a few places (e.g., `_format_signal_type`) but
storing canonical IDs at write time is the correct approach.
---

## 5. Opportunity Scoring & Mandate Synthesis

### 5.1 What `priority_score` actually is

The `priority_score` column on `ca.ca_opportunity_scoring` is an **LLM-derived estimate**,
produced during mandate synthesis. It is not calculated by a formula.

**Updated 20 Sep 2026 (commit `13721ca`):** the synthesis prompt now returns `priority_score`
as a fifth key, alongside `why_now`, `action`, `why_now_summary`, `action_summary`. The
weighted rubric is: signal strength 40% / balance-sheet pressure 30% / market window 30%.
The LLM's value is written back to `ca.ca_opportunity_scoring.priority_score` on every
synthesis run (i.e. every cache miss for a whitelisted client). The prior approach — a
frozen value from an earlier pipeline era — is superseded.

The card label `High · 94` is derived from `priority_score` by a fixed threshold:

| Score | Label |
|---|---|
| ≥ 85 | High |
| 70–84 | Medium |
| < 70 | Low |

**Non-determinism:** even at `temperature=0.0`, `gemini-2.5-flash` produces slightly
different scores across synthesis runs. Observed values for `CLI101` across a single session:
85, 88, 91, 93, 94. This is a property of the model, not a bug. If a stable score is required
for a demo, pin `priority_score` to the anchor's curated value, the same treatment the
narratives receive.

**Cache/DB consistency (commit `9cfeb42`):** the `_MANDATE_SYNTH_CACHE` is populated **only
after** `conn.commit()` succeeds. On persist failure, the cache entry is popped. This
prevents the failure mode where the UI served a cached score the DB did not hold. See §5.5.

The related columns `propensity_score` and `value_score` are also LLM outputs. They are
retained for potential future ranking models but are not read by any current code path.

### 5.2 Mandate Synthesis — the Anchor Pattern

`/api/opportunities` does not simply return the mandate text from the database. It runs a
synthesis step, anchored to the curated DB row.

**Purpose:** the signals in `digital_twin_signals` describe evidence and context, but they do
not contain a specific deal structure. Left to synthesize freely, an LLM will invent a
plausible structure that may not match ING's actual advisory proposal. The anchor prevents
that.

**Flow:**

```
┌────────────────────────────────────────────────────────────────────────────┐
│  1. Read anchor from ca.ca_opportunity_scoring                             │
│     • why_now_nlg  (curated catalyst rationale)                            │
│     • next_best_action  (curated deal structure)                           │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  2. Check TTL cache, keyed by client_id                                    │
│     • _MANDATE_SYNTH_CACHE[client_id] = (expiry_ts, why_now, action,       │
│       why_now_summary, action_summary, priority_score)                     │
│     • TTL = 300 seconds                                                    │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
│  3. Cache miss AND client in _DEMO_CLIENT_IDS:                             │
│     a. Fetch 20 most recent signals for the client                         │
│     b. Call synthesize_mandate_catalyst() with the anchor as the first     │
│        instruction in the prompt                                           │
│     c. Receive JSON with five keys:                                        │
│        {"why_now", "action", "why_now_summary", "action_summary",          │
│         "priority_score"}                                                  │
│     d. Drift guard: if the output introduces conflicting tenors or         │
│        notionals, replace with the anchor verbatim                         │
│     e. UPDATE ca.ca_opportunity_scoring.priority_score, then commit        │
│     f. Populate _MANDATE_SYNTH_CACHE ONLY AFTER the commit succeeds        │
│        (on failure, the cache entry is popped). See §5.5.                  │
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  4. Cache hit OR client not in _DEMO_CLIENT_IDS:                           │
│     • Use the DB row value directly                                        │
│     • No LLM call                                                          │
└────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 The Whitelist

`_DEMO_CLIENT_IDS` in `main.py` scopes LLM synthesis to the current demo client(s).
Clients not in the set skip the Gemini call and read their DB row directly.

Current value (20 Sep 2026): `_DEMO_CLIENT_IDS = {"CLI101", "CLI103"}` — Enel and BASF.

**Why:** before the whitelist, every client in the loop triggered a synthesis call on cold
cache. With 13 clients × 3–5 seconds each, cold load was 40–65 seconds. The whitelist brings
that down to one call per whitelisted client (two today).

**Sync requirement:** the frontend mirrors this with ACTIVE_UI_CLIENT_IDS in App.jsx
(currently ["CLI101", "CLI103"]). When adding a client to the demo, update both lists.
Mismatch between the two produces a display inconsistency: the backend synthesizes for a
client the frontend doesn't render, or vice versa.

### 5.4 The Drift Guard

After the LLM returns its synthesized text, a deterministic check runs:

```python
if anchor_has_7Y and output_has_8Y:
    output = anchor
if anchor_has_10Y and output_has_12Y:
    output = anchor
```

This is a safety net. The prompt asks the LLM to preserve the anchor's structure, but if it
doesn't, the guard catches the specific case of conflicting tenors and replaces the LLM
output with the anchor verbatim.

### 5.5 The TTL Cache

`_MANDATE_SYNTH_CACHE` is a module-level dictionary:

```python
_MANDATE_SYNTH_CACHE = {}
_MANDATE_SYNTH_CACHE_TTL = 300  # 5 minutes
```

Cache entries are keyed by `client_id` and expire after 5 minutes. Each entry is a
6-tuple: `(expiry_epoch, why_now, action, why_now_summary, action_summary, priority_score)`. 
This eliminates repeat Gemini calls for the same client within a demo session.

Cache/DB consistency invariant (added 20 Sep, commit 9cfeb42): the cache is populated
only after `conn.commit()` succeeds. On persist failure, the cache entry is popped in
the except block. This prevents the failure mode where the UI serves a cached score the
DB does not hold — observed in the 19 Sep review as a UI-vs-DB mismatch window lasting until
cache TTL expiry.

Because the cache is in-memory, it requires `max-instances=1` on Cloud Run — otherwise
requests land on different instances and each has its own empty cache.

---

## 6. Pitchbook Generation

### 6.1 Slide Count

**11 slides.** The React preview canvas (`App.jsx`) uses `case 0` through `case 10`, and the
PPTX builder generates the same 11 slides.

### 6.2 Slide Names by Product Family

Slide titles vary by product family. The backend detects the family and selects the
appropriate template:

| # | FX Hedge | Green / ESG | Rates Hedge | DCM Refi |
|---|---|---|---|---|
| 01 | Cover Slide | Cover Slide | Cover Slide | Cover Slide |
| 02 | Strategic Catalyst | Decarbonization Catalyst | Rate Risk Catalyst | Strategic Catalyst |
| 03 | Executive Summary | Executive Summary | Executive Summary | Executive Summary |
| 04 | Balance Sheet & Inflows | ESG Balance Sheet | Capital Structure Snapshot | Balance Sheet Foundation |
| 05 | FX Sizing & Hedge Gap | Use of Proceeds Pool | Debt & Swap Horizon | Debt Maturity Profile |
| 06 | Collar Payoff Matrix | Greenium Sensitivity | Rate Shift Sensitivity | Refinancing Sensitivity |
| 07 | Forward Points & Rates | ESG Market Backdrop | Swap Curve Backdrop | Credit Spread Backdrop |
| 08 | FX Advisory Term Sheet | Green Bond Term Sheet | Pre-Hedge Term Sheet | EMTN Term Sheet |
| 09 | Why Execute With Us | Why Execute With Us | Why Execute With Us | Why Execute With Us |
| 10 | Layered Roll Schedule | SPO & Syndicate Plan | Execution Roadmap | Syndicate Timeline |
| 11 | EMIR Disclosures | ICMA Disclosures | Regulatory Disclosures | Regulatory Disclosures |

### 6.3 Preview / PPTX Parity

The React preview canvas and the python-pptx generator produce the same content. Both read
from the same `deckOverrides` payload, both consume the same field names, both render the
same values — after the 19-20 Sep fixes.

**Observed divergence (19-20 Sep 2026):** the two paths computed several values
independently and drifted on slides 4, 5, and 6 for BASF:

Slide 4 maturity wall — preview read `opp.debt_maturing_24m_bn (billions);` generated
read `ctx["debt_maturing_24m_str"] (millions).` Fixed: both `read _bn`.

Slide 4 credit rating — preview had its own `CLI101 ? "S&P | BBB | Positive" : tier`
branch; generated read the anchor. Fixed: both read `_CREDIT_RATINGS` / API `credit_rating`.

Slide 5 tranche table — preview read `clientMaturities` from `/api/client/{id}/maturities`;
generated had three hardcoded rows. Fixed: both read `ctx["maturities"]` and the sum.

Slide 6 narrative — preview had hardcoded rating and wall strings; generated used
`compute_canonical_bundle` fallbacks. Fixed: both read dynamic values.

**Remaining divergence risks (backlog):**

Frontend default* constants in `App.jsx (defaultRevenue, defaultEbitda, defaultNetDebt, defaultLiquidity)` — coincidence-correct for the current two clients, but hardcoded. Full fix requires exposing these four fields in `/api/opportunities`.

`pitchbook_builder.py` line 1045 retains a hardcoded revenue/EBITDA fallback when
`revenue_str` is "N/A". Dormant.

`main.py:602` retains a swap pre-hedge fallback string. Dormant.

See `master_persona_20Sep.md` §8.4-8.6 and §13.

### 6.4 Generation Flow

```
POST /api/pitchbook/generate
    ↓
fetch_pitchbook_bundle(client_id)
    ↓
Detect product family (detect_product_family)
    ↓
Build slide meta (get_slide_meta)
    ↓
For each of 11 slides, populate from DB values + overrides
    ↓
Return binary .pptx stream
```

---

## 7. Copilot Architecture

### 7.1 Context Hydration

`/api/copilot/chat` constructs two dicts before calling the LLM:

- **`baseline_deck_slides`** — the pristine (unmutated) deck content, from the DB
- **`active_deck_slides`** — the current deck state with any applied overrides

Both are serialized into the system instruction so the LLM reasons over exactly what the RM
sees on screen.

### 7.2 Prompt Structure

The system instruction has these sections, in order:

1. Client name and product family
2. Ingested multi-stream signals (WorkFabric + telemetry)
3. Pristine database baseline
4. Current active slides (with overrides applied)
5. Active overrides state
6. Response architecture (three-part explanation structure for slide queries)
7. Regulatory compliance handling
8. Parameter mutations and canonical key contract
9. Dynamic revert handling
10. Output format (`{"reply": "...", "overrides": {...}}`)

### 7.3 State Mutation

When the user asks the copilot to change a value ("update Slide 7 iTraxx to 60 bps"), the
LLM returns an `overrides` object with the new value. The frontend merges it into
`deckOverrides` state, and the preview re-renders.

### 7.4 Model

`gemini-2.5-flash` for all copilot calls. The doc originally referenced "Gemini 1.5 Pro" and
"Gemini 1.5 Flash" for different roles — this is no longer accurate. A single model handles
signal extraction, mandate synthesis, copilot, and compliance.

---

## 8. Compliance Architecture

### 8.1 Endpoints

- `POST /api/check-compliance`
- `POST /api/compliance/audit` (alias)

### 8.2 Mechanism

The compliance check is **LLM-driven**, not regex-driven. A Gemini call evaluates the deck
against:

- **MiFID II** (Art. 24/54) — professional clients, non-binding pricing caveats
- **MAR Art. 11** — market sounding safe harbour
- **EU Green Bond Standard / EU Taxonomy** — for green-family decks
- **EMIR** — derivative classification (NFC+ for pre-hedges)

The response includes `flags[]` with `slide_number`, `rule`, `issue`, and
`recommended_overrides`.

### 8.3 Note on Dormant Code

`PROMISSORY_PATTERNS` (a regex list for detecting promissory language like `guarantee`,
`risk-free`) exists in `main.py` but is **not called** by any endpoint. Compliance is entirely
handled by the LLM. This is a candidate for a future improvement — running the regex
pre-filter before the LLM audit would make the check deterministic for a subset of patterns.

### 8.4 Remediation

If the user clicks "Apply Compliance Remediations", the endpoint returns an `overrides`
object containing `pricing_caveat`, `emir_notice`, `compliance_status`, and any additional
disclaimers. These are merged into `deckOverrides` and applied to both preview and export.

---

## 9. API Reference

All endpoints served from the FastAPI application. Base URL is the Cloud Run service URL.

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness check. Note: returns 404 when accessed via Cloud Run (intercepted path); prefer `/api/opportunities` for reachability checks. |
| GET | `/api/metrics` | Dashboard metrics: `clients_with_signals`, `active_signals`, `high_priority_clients`, `clients_in_database`, `priorities` (all whitelist-scoped except the last) |
| GET | `/api/signals` | Live signal marquee feed. Filtered to `_DEMO_CLIENT_IDS`. |
| GET | `/api/opportunities` | Opportunity cards with mandate synthesis |
| GET | `/api/client/{client_id}/maturities` | Debt maturity ladder for one client |
| GET | `/api/rss/feed?client_id=...` | Live Google News RSS for a client |
| POST | `/api/ingest/text` | Ingest text from any channel |
| POST | `/api/ingest/file` | Ingest a PDF or PPTX |
| POST | `/api/check-compliance` | Full-deck compliance audit |
| POST | `/api/compliance/audit` | Same as above (alias) |
| POST | `/api/copilot/chat` | Copilot chat |
| POST | `/api/chat` | Same as above (alias) |
| POST | `/api/pitchbook/generate` | Generate PPTX |
| GET/POST | `/api/pitchbook/download` | Same handler as generate |
| POST | `/api/system/reset-baseline` | Restore pristine state from `baseline_snapshots.json`. Non-destructive — pristine rows get `created_at = NOW()` so they win the ordering sort; user content stays in the DB, outranked. |
| GET | `/{full_path:path}` | React SPA catch-all |

**Static assets:** mounted at `/assets`.

---

## 10. Deployment

### 10.1 Cloud Run

| Setting | Value |
|---|---|
| Service | `ing-fm-poc-service` |
| Region | `europe-west1` |
| CPU | 1000m (1 vCPU) |
| Memory | 512 MiB |
| Min instances | 1 |
| Max instances | 1 |
| Container port | 8080 |
| Ingress | Public (allUsers granted `roles/run.invoker`) |

**Why min/max = 1:** The mandate synthesis cache (`_MANDATE_SYNTH_CACHE`) is in-memory.
Multiple instances would each have their own empty cache, defeating the TTL caching strategy.
For a demo workload with one active viewer, single instance is correct. For production, the
cache would need to move to a shared store (Redis or a DB-backed cache).

### 10.2 Cloud SQL

| Setting | Value |
|---|---|
| Instance | `ing-postgres-db` |
| Region | `europe-west1` |
| Engine | PostgreSQL 15 |
| Extensions | `pgvector` |
| Connection | Cloud SQL Connector (`pg8000`) via `INSTANCE_CONNECTION_NAME` |

### 10.3 Vertex AI

| Model | Purpose |
|---|---|
| `gemini-2.5-flash` | All LLM calls (extraction, synthesis, copilot, compliance) |
| `text-embedding-004` | 768-dim embeddings for document chunks |

### 10.4 Environment Variables

Set on the Cloud Run service:

```
INSTANCE_CONNECTION_NAME=dulcet-radar-508218-c5:europe-west1:ing-postgres-db
DB_USER=postgres
DB_NAME=postgres
GCP_PROJECT=dulcet-radar-508218-c5
REGION=europe-west1
```

DB password is mounted from Secret Manager (`db-postgres-pass`).

### 10.5 Deployment Command

```
deploy-poc
```

This is a shell alias for:

```
gcloud run deploy ing-fm-poc-service \
  --source . \
  --project=dulcet-radar-508218-c5 \
  --region=europe-west1 \
  --set-env-vars=INSTANCE_CONNECTION_NAME=...,DB_USER=...,DB_NAME=...,GCP_PROJECT=...,REGION=... \
  --set-secrets=DB_PASS=db-postgres-pass:latest \
  --quiet
```

The Dockerfile uses a two-stage build: node:20-alpine compiles the React frontend into
`/app/frontend/dist`, then python:3.11-slim installs requirements and copies `main.py`,
`pitchbook_builder.py`, and `assets/`.

---

## 11. Architectural Principles

1. **Zero fabrication.** Every value displayed traces to a specific row in a specific
   database table, filtered by `client_id`. Fallbacks exist for missing data but never
   substitute invented values.

2. **Multi-signal extraction.** A single document with N distinct topics produces N signal
   rows, not one. Downstream components reason over the accumulated corpus.

3. **Anchor pattern for LLM synthesis.** The database row holds the curated narrative.
   The LLM synthesizes against it but cannot drift. A deterministic drift guard enforces
   the constraint if the prompt is ignored.

4. **Whitelist-scoped processing.** `_DEMO_CLIENT_IDS` (backend) and `ACTIVE_UI_CLIENT_IDS`
   (frontend) restrict processing and rendering to the demo client(s). The two lists must
   be kept in sync.

5. **TTL cache for repeated synthesis.** The `_MANDATE_SYNTH_CACHE` avoids repeated LLM
   calls for the same client within a 5-minute window. This depends on single-instance
   deployment.

6. **Deterministic drift guard.** Post-LLM validation catches the specific case of tenor
   conflicts between the anchor and the output, replacing the LLM output with the anchor
   verbatim when they disagree.

7. **Single model, multiple roles.** All LLM work uses `gemini-2.5-flash`, simplifying
   cost, latency, and prompt management.

8. **Product-family branching in templates.** Four families (FX, Green, Rates, DCM) each
   have their own slide titles, term-sheet structures, and disclosure sets. The backend
   detects the family and selects the appropriate template.

9. **Cache/DB consistency.** Caches are populated only after the persistent write
   succeeds. `_MANDATE_SYNTH_CACHE` is written to only after `conn.commit()` returns; on
   failure the entry is popped. This ensures any score the UI displays via the cache is a
   score the DB also holds. Added 20 Sep 2026 (commit `9cfeb42`).

10. **Curated credit ratings as a dict.** No `credit_rating` column exists on
    `ca.client_master` (schema changes are out of scope). Credit ratings are curated in a
    `_CREDIT_RATINGS` dict in both `main.py` and `pitchbook_builder.py`. Adding a new demo
    client requires adding its rating to both dicts. The frontend reads `opp.credit_rating`
    from the API response — no client-side rating logic. See `master_persona_20Sep.md` §8.1
    and §7.9.

---

## 12. Changelog — 20 Sep 2026

Changes since the 14 Sep 2026 version. The 14 Sep changelog is preserved below as a
historical record.

### Cache and synthesis

- **Cache/DB consistency** (commit `9cfeb42`) — `_MANDATE_SYNTH_CACHE` is populated only
  after `conn.commit()` succeeds; on failure the entry is popped. Fixes a UI-vs-DB mismatch
  window where the UI served a cached score the DB did not hold.
- **`priority_score` now recomputed on every synthesis** (commit `13721ca`) — the prompt
  returns a fifth key with a weighted rubric. The LLM's value is written back to
  `ca.ca_opportunity_scoring`. Prior behavior was a frozen value from an earlier pipeline
  era.
- **Cache shape** — 5-tuple → 6-tuple (added `priority_score`).
- **Whitelist guarantee** — whitelisted clients always appear in `/api/metrics` priorities,
  even when their score ranks below the top-4 slice.
- **Temperature** — synthesis runs at `temperature=0.0` for determinism.

### THIS WEEK tiles

- **Removed the fabricated "Avg. time to first draft" tile** — was `< 15s / ▼ 99% vs manual`,
  hardcoded with no underlying measurement. The platform does not record draft generation,
  so the metric is uncomputable without a schema change.
- **Replaced with "Active signals"** — `COUNT(*)` from `ca.digital_twin_signals` scoped to
  `_DEMO_CLIENT_IDS`, with a 7-day count as the change line.
- **Three other tiles relabeled and re-sourced** — "Active drafts", "Deals pending review",
  and "Cohort matches" all rendered `displayedOpportunities.length || 1` (frontend render
  count) with no backend source. New tiles: "Clients with signals", "High-priority clients",
  "Clients in database" — all DB-sourced.
- **All four tiles read `metrics.<key>.value` from the API.** Fallbacks are `'0'`, not `'1'`.

### Client display fabrication

- **Credit ratings** — 'Tier 1' (coverage classification) no longer shown under "External
  ratings" for non-Enel clients. `_CREDIT_RATINGS` dict in both `main.py` and
  `pitchbook_builder.py` (both currently `{"CLI101": "S&P | BBB | Positive", "CLI103":
  "S&P | A- | Stable"}`). Frontend reads `opp.credit_rating` from the API.
- **Maturity wall format** — millions (€3,000M / €10,127M) vs billions (€3.00bn / €10.13bn)
  unified to billions. `debt_maturing_24m_bn` added to the pitchbook bundle; every render
  site reads from it.
- **Slide 5/10 tranche table** — three hardcoded rows replaced with `ctx["maturities"]` from
  `ca.debt_maturity_schedule`. Total line relabeled "Total Maturity Profile" and shows the
  sum of rows (BASF: €9,097M across 2026-2028).
- **Slide 6 narrative** — replaced hardcoded 'A BBB+ rated issuer...' with dynamic rating
  and wall values.
- **Preview / generated parity** — slides 4, 5, and 6 now show identical values in the React
  preview and the downloaded PPTX.

### Data cleanup

- **`ca.ext_company_filings` BASF rows** — 4 NULL-revenue duplicate rows deleted (5 → 1).
  The multi-row pattern was causing the deck to read NULL for revenue/EBITDA, silently
  falling through to `client_master` values. Table is not in `baseline_snapshots.json`, so
  the cleanup is durable across reset.

### Documentation

- `master_persona_20Sep.md` — added, supersedes 18Sep. Documents the cache/DB invariant
  (§7.8), credit rating dict sync (§7.9), filings multi-row hazard (§7.10), frontend
  `default*` exceptions (§8.4), dormant fallbacks (§8.5-8.6), paste discipline (§9.12).
- `README.md` — updated to point at `master_persona_20Sep.md`, document the `_CREDIT_RATINGS`
  pattern, and add a Testing section.
- This doc — version bumped to 20 September 2026.

### Backlog

- `COALESCE(priority_score, 75)` at `main.py:225, 727`
- Frontend `default*` constants in `App.jsx`
- `pitchbook_builder.py:1045` revenue/EBITDA fallback
- `main.py:602` swap pre-hedge fallback
- Ingestion pipeline duplicate-row write to `ca.ext_company_filings`
- LLM `priority_score` non-determinism at `temperature=0.0`
- Archive folder fragmentation (`Docs/archive/` vs `archive/`)

---

## 12a. Changelog — 14 Sep 2026 (archived)

Substantial changes since the 28 Aug 2026 architecture doc:

### Data Layer

- **Multi-signal extraction:** prompt now returns a `detected_signals[]` array. Ingestion
  writes N rows to `digital_twin_signals` per ingestion.
- **Deduplication guard:** identical `(client_id, trigger_summary)` pairs are skipped.
- **Client ID normalisation:** legacy IDs (`CLI009_ENEL`, `CLI010_BASF`) merged into
  canonical IDs (`CLI101`, `CLI103`).
- **Duplicate signal cleanup:** 5 duplicate `€1.0B Dual-Tranche Green & SLB` signals removed.
- **Ingestion no longer writes to `ca_opportunity_scoring`** — that column is now curated
  or populated only by mandate synthesis.

### Pipeline

- **Anchor pattern:** mandate synthesis is anchored to `ca_opportunity_scoring.why_now_nlg`
  and `.next_best_action`. Prompt restructured to place the anchor first.
- **Drift guard:** deterministic post-synthesis check for tenor conflicts.
- **TTL cache:** `_MANDATE_SYNTH_CACHE` replaces the previous timestamp-keyed cache.
- **Whitelist:** `_DEMO_CLIENT_IDS = {"CLI101"}` scopes LLM synthesis to demo clients.
- **Signal feed filter:** `/api/signals` filtered to `_DEMO_CLIENT_IDS`.

### Display

- **Signal type normalisation:** `_format_signal_type()` converts `BOARD_AUTHORIZATION` →
  `BOARD AUTHORIZATION` for display.
- **Headline selection:** prefers `trigger_summary` when `metric_identified` is short or
  structured, giving cleaner marquee text.
- **Houseview label:** shortened from `<type>: <metric>` to just the metric trimmed at the
  first semicolon.
- **Signal lineage tiles:** tile 3 value changed from maturities to `€12bn financing capacity`;
  tile 4 value changed to the cleaned metric.
- **Business-language tooltips:** replaced `title="ca.document_vector_chunks"` etc. with
  `title="Source: Ingested houseviews and news"`.

### Performance

- **Cold load:** 120s → ~5s. Root cause was a `NameError` in the drift guard that silently
  prevented the cache from populating.
- **Warm load:** 120s → ~1s. Requires `min-instances=1` and `max-instances=1`.
- Full diagnostic and fix trail is in `PERFORMANCE_OPTIMIZATION.md`.

### Infrastructure

- **Cloud Run:** set `min-instances=1`, `max-instances=1`, `cpu=1000m`, `memory=512Mi`.
- **Model consolidation:** all LLM calls now use `gemini-2.5-flash`. The 28Aug doc referenced
  Gemini 1.5 Pro / 1.5 Flash for different roles — no longer accurate.

### Documentation

- `PERFORMANCE_OPTIMIZATION.md` (new) — optimization trail
- `Live_Signal_feed.md` (updated) — signal feed mechanics
- This doc supersedes the three previous `architecture_flow_*.md` files

---

*End of document.*