# Financial Markets Deal Origination Engine: Signals, Opportunities & Pitchbook Lifecycle

**Version:** 14 September 2026
**Status:** Authoritative
**Supersedes:** Previous version (pre-14 Sep)
**Audience:** Engineers, Business Analysts

---

## 1. Executive Summary & Architectural Overview

Modern Wholesale Banking and Financial Markets origination requires continuous monitoring of
corporate balance sheets, dynamic macro market curves, and real-time qualitative touchpoints.
This platform employs a **two-stage hybrid architecture** combining deterministic financial
logic with large language model semantic intelligence.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                       HYBRID INGESTION & ORIGINATION ENGINE            │
├────────────────────────────────────────────────────┬───────────────────────────────────┤
│          UNSTRUCTURED DATA SOURCES                 │              STRUCTURED DATA SOURCES│
│  • Google News RSS Feeds                           │  • Core Client Master              │
│  • Treasury Emails & Inbound Inquiries             │  • Balance Sheet & Debt Schedules  │
│  • MS Teams Coverage Transcripts                   │  • Live Market Fixings             │
│  • House Views (PDF / PPTX Research)               │  • Historical Pricing              │
└─────────────────────────┬──────────────────────────┴─────────────────────────┬──────────┘
                          │                                                    │
                          ▼                                                    ▼
             [ LLM Extraction (Vertex AI) ]                      [ Deterministic SQL & Logic ]
                          │                                                    │
                          └─────────────────────────┬──────────────────────────┘
                                                    │
                                                    ▼
                                  [ PostgreSQL Storage & Calibration ]
                                  • ca.digital_twin_signals
                                  • ca.document_vector_chunks
                                  • ca.ca_opportunity_scoring
                                                    │
                                                    ▼
                             ┌──────────────────────────────────────────────┐
                             │       DOWNSTREAM PRESENTATION LAYER          │
                             ├──────────────────────────────────────────────┤
                             │ 1. Live Horizontal Signal Feed               │
                             │ 2. Priority Today Flight-Deck                │
                             │ 3. Whitelisted Opportunity Cards             │
                             │ 4. Pitchbook Engine (Preview & PPTX)         │
                             └──────────────────────────────────────────────┘
```

**Current demo scope:** The UI whitelists to Enel S.p.A. (`CLI101`). The DB holds 13 client
records; only the whitelisted client renders. See §3.4 for details.

---

## 2. Signal Identification Pipeline

### 2.1 Multi-Channel Ingestion Gateways

Unstructured corporate touchpoints flow into a single unified entry point:

| Channel | Endpoint | Source |
|---|---|---|
| Live Google News RSS | `/api/rss/feed` → `/api/ingest/text` | Google News |
| Coverage transcripts | `/api/ingest/text` | MS Teams, internal notes |
| Treasury direct inbound | `/api/ingest/text` | Client emails |
| House views | `/api/ingest/file` | PDF / PPTX uploads |
| WorkFabric memos | `/api/ingest/text` | Internal desk notes |

### 2.2 Semantic Extraction & Parameterization

Unstructured inputs are processed by **`gemini-2.5-flash`** on Vertex AI under a strict JSON
extraction schema.

**Multi-signal extraction:** A single ingestion produces **N signals**, not one. A PDF with six
sections produces six rows in `ca.digital_twin_signals`.

The model extracts per signal:

- `catalog_family` — `Financing/Capital Markets`, `Interest Rate`, `Foreign Exchange`,
  `Sustainable Finance`, `Commodities`, `Credit`, `Cross-Asset & Discovery`
- `signal_type` — free text (e.g., `SUSTAINABLE FUNDING`, `BOARD_AUTHORIZATION`, `REFINANCING`)
- `urgency` — `High` / `Medium` / `Low`
- `metric_identified` — short headline / metric (max 100 chars)
- `trigger_summary` — 1-sentence description
- `metric_value` — key value or spread
- `description` — 2-sentence detail
- `confidence_pct` — integer

### 2.3 Database Persistence

Extracted signals are committed to `ca.digital_twin_signals`:

```sql
INSERT INTO ca.digital_twin_signals (
    signal_id, client_id, catalog_family, signal_type,
    metric_identified, trigger_summary, metric_value,
    description, confidence_pct, urgency, created_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
```

**Deduplication:** Before inserting, the pipeline checks whether `(client_id, trigger_summary)`
already exists. If so, the insert is skipped.

**Document chunk storage:** Each ingestion also writes one row to
`ca.document_vector_chunks` with the raw text, source metadata, and structured metadata
(containing the full `detected_signals` array).

**Ingestion does NOT write to `ca.ca_opportunity_scoring`.** That table is populated or
updated only by the mandate synthesis step. See §3.3.

---

## 3. Opportunity Discovery & Prioritization Engine

### 3.1 The Hybrid Discovery Method

Opportunity formulation combines LLM-derived signals with deterministic SQL logic:

| Dimension | LLM Functionality | Deterministic Code / DB Functionality |
|---|---|---|
| **Data Ingestion** | Extracts triggers from unstructured text | Stores signals with dedup; stores document chunks |
| **Catalog Mapping** | Synthesizes deal narrative into "Why Now" rationale | Uses product-family templates and slide structure |
| **Financial Math** | *Bypassed to prevent hallucinations* | Computes maturity walls, liquidity ratios, and savings math |
| **Model Risk Governance** | Generates institutional text summaries | Threshold classification, cache, drift guard |

### 3.2 Priority Score — Actual Implementation

**Important:** The Priority Score is not computed from a weighted formula. This was
documented aspirationally in earlier versions of the platform docs but was never implemented
in the code.

**What the score actually is:** `ca.ca_opportunity_scoring.priority_score` is a **single
LLM-derived estimate**, produced during ingestion. When the old single-signal ingestion
pipeline ran, Gemini returned a `priority_score` value in its structured output, and that
value was written to the row.

**Current state:** the ingestion pipeline was refactored on 14 Sep 2026 to extract
`detected_signals[]` arrays. The new prompt schema no longer includes `priority_score`. The
values in the DB today are **legacy values** from the last time the old pipeline ran.

**Example — Enel (`CLI101`):**

| Field | Value |
|---|---|
| `opportunity_id` | `OPPCA104_CLI101` |
| `priority_score` | 94 |
| `est_revenue_eur_000` | 5500.0 (i.e., €5.5M) |
| `next_best_action` | "We recommend a €1.0bn dual-tranche senior unsecured issuance, comprising a €600m 7Y Green bond at Mid-swap + 73 bps (net of -5 bps greenium) and a €400m 10Y Sustainability-Linked Bond..." |

**The other two scores:**

| Column | Status |
|---|---|
| `propensity_score` | LLM output from earlier ingestion. Not read by any code path. |
| `value_score` | Same. |

Both are retained for a potential future ranking model.

### 3.3 Mandate Synthesis (the anchor pattern)

`/api/opportunities` runs a synthesis step anchored to the curated DB row.

**Purpose:** the signals in `ca.digital_twin_signals` describe evidence and context, but they
don't contain a specific deal structure. Left to synthesize freely, an LLM will invent a
plausible structure that may not match ING's actual advisory proposal. The anchor prevents
that.

**Flow:**

1. Read `why_now_nlg` and `next_best_action` from `ca.ca_opportunity_scoring` (the anchor)
2. Check the TTL cache (`_MANDATE_SYNTH_CACHE`, 300-second expiry, keyed by `client_id`)
3. On cache miss and client in `_DEMO_CLIENT_IDS`:
   - Fetch the 20 most recent signals for the client
   - Call `gemini-2.5-flash` with the anchor placed first in the prompt
   - Apply the drift guard (tenor conflict check)
   - Write the result to the cache and back to `ca.ca_opportunity_scoring`
4. On cache hit or non-whitelisted client: use the DB row directly

Full detail in `How_Signals_are_Converted_into_Opportunities.md` §5.

### 3.4 Score Calibration & Priority Today Ranking

**Threshold classification** (in `/api/opportunities`):

```python
score_level = "High" if int(score_num) >= 85 else ("Medium" if int(score_num) >= 70 else "Low")
```

| Range | Label |
|---|---|
| ≥ 85 | High |
| 70 – 84 | Medium |
| < 70 | Low |

**Current cohort scores:**

| Client | Score | Fee |
|---|---|---|
| Enel S.p.A. (`CLI101`) | 94 | €5.5M |
| BASF SE (`CLI103`) | 94 | €5.8M |
| Ørsted A/S (`CLI001`) | 98 | — |
| Stellantis N.V. (`CLI003`) | 94 | — |

**Priority Today ranking:**

The `/api/metrics` endpoint sorts all clients by priority score descending and takes the top 4:

```python
sorted_rows = sorted(rows, key=lambda x: (int(x[2]), float(x[4])), reverse=True)[:4]
```

**Frontend whitelist:** the Priority Today sidebar in `App.jsx` filters the result to
`ACTIVE_UI_CLIENT_IDS = ["CLI101"]`. Only Enel renders, even though the API returns four
priorities. To render multiple clients in the demo, update both `ACTIVE_UI_CLIENT_IDS` and
`_DEMO_CLIENT_IDS`.

---

## 4. Pitchbook Creation: UI Preview & Document Generation

### 4.1 The 11-Slide Deck

The pitchbook has **11 slides**. Slide titles vary by product family (FX / Green / Rates /
DCM). The table below shows the Green/ESG variant (Enel's deck).

| # | Green / ESG | Primary Data Source |
|---|---|---|
| 1 | Cover Slide | `ca.client_master.client_name` |
| 2 | Decarbonization Catalyst | `ca.ca_opportunity_scoring.trigger_source` |
| 3 | Executive Summary | `get_product_pillars()` + signals |
| 4 | ESG Balance Sheet | `ca.ext_company_filings` |
| 5 | Use of Proceeds Pool | Synthesis context + framework data |
| 6 | Greenium Sensitivity | `ca.ext_credit_spreads` + greenium override |
| 7 | ESG Market Backdrop | `ca.mkt_rates_curves` + `ca.ext_credit_spreads` |
| 8 | Green Bond Term Sheet | Deal proposal + canonical calculation |
| 9 | Why Execute With Us | Static capability cards (candidate for `ca.ext_deals`) |
| 10 | SPO & Syndicate Plan | Template (SPO, roadmap) |
| 11 | ICMA Disclosures | `ca.regulatory_notices` (in progress) |

Full mapping of all four families in `architecture_flow_14Sep.md` §6.2.

### 4.2 Synthesis of Structured & Unstructured Data

**Structured grounding** — slide 4 and slide 5 render exact metrics from
`ca.ext_company_filings` and `ca.debt_maturity_schedule`:

| Metric | Value | Source |
|---|---|---|
| Net Debt | €58.5bn | `net_debt_eur_m = 58500` |
| Available Liquidity | €14.2bn | `liquidity_eur_m = 14200` |
| 24M Maturity Wall | €10.13bn | `debt_maturing_24m_eur_m = 10127` |

**Unstructured grounding** — slides 1, 2, and 3 translate signal text into deal themes
(e.g., from the Enel houseview: "Inaugural Green Bond with SPO verification, capturing 3-7
bps greenium").

**Sensitivity & term sheet** — slide 6 computes cost savings:

| Tranche | Notional | Greenium | Annual Savings |
|---|---|---|---|
| Green Bond | €600M | -5 bps | €300,000 |
| SLB | €400M | -2 bps | €80,000 |
| **Total** | €1.0bn | — | **€380,000** |

Slide 8 renders the two-leg term sheet with all notionals, tenors, and spreads sourced from
`compute_canonical_bundle()` and any active overrides.

### 4.3 Interactive UI Preview

Clicking **Open draft pitchbook** launches the workspace:

1. **Slide Navigation** — 11 structured slides with live previews
2. **Origination Deal Copilot** — LLM assistant for restructuring tranches, updating spread
   assumptions, and regenerating slide text
3. **Compliance Audit** — inspects deck against MiFID II, MAR Art. 11, and (for green-family
   decks) the EU Green Bond Standard / EU Taxonomy

### 4.4 Production `.PPTX` Generation

Clicking **Download .PPTX Deck** executes `/api/pitchbook/generate`:

- Fetches the bundle via `fetch_pitchbook_bundle()`
- Applies overrides via `build_pitchbook()`
- Renders 11 slides with corporate styling (`python-pptx`)
- Returns a binary `.pptx` stream

The preview canvas and PPTX consume the same underlying bundle, ensuring 1:1 parity.

---

## 5. Compliance Checkpoints

### 5.1 Where Compliance Runs

Compliance is evaluated at two points in the lifecycle:

| Point | Endpoint | What it does |
|---|---|---|
| On-demand audit | `POST /api/check-compliance` (alias: `/api/compliance/audit`) | Full-deck inspection |
| During download | Implicit in `build_pitchbook` if overrides contain `disclaimers` | Applies active disclaimers |

### 5.2 Regulatory Regimes

The compliance check is **LLM-driven** today. The endpoint sends the full deck to Gemini
with a system prompt that evaluates against:

- **MiFID II** (Art. 24/54) — professional clients, non-binding pricing caveats
- **MAR Art. 11** — market sounding safe harbour
- **EU Green Bond Standard / EU Taxonomy** — for green-family decks
- **EMIR** — derivative classification (NFC+ for pre-hedges)

**Note:** A regex list (`PROMISSORY_PATTERNS`) exists in `main.py` but is not called. All
screening is LLM-driven. See `Data_or_Fabrication.md` §9.3 for the post-demo improvement.

### 5.3 Remediation

If the user clicks **Apply Compliance Remediations**, the endpoint returns an `overrides`
object containing `pricing_caveat`, `emir_notice`, `compliance_status`, and any additional
disclaimers. These merge into `deckOverrides` and apply to both preview and export.

---

## 6. Lifecycle In One View

```
Stage 1: Signal Arrival
    Ingestion → Gemini extraction → N signals written to DB
    Endpoint: /api/ingest/text or /api/ingest/file
    ↓
Stage 2: Signal Accumulation
    Signals deduped by (client_id, trigger_summary)
    Query: SELECT * FROM ca.digital_twin_signals WHERE client_id = ?
    ↓
Stage 3: Opportunity Discovery
    /api/opportunities joins client + filings + markets + signals
    Synthesis (whitelisted clients) anchors to ca_opportunity_scoring
    ↓
Stage 4: Priority Ranking
    /api/metrics sorts by priority_score, takes top 4
    Frontend filters to ACTIVE_UI_CLIENT_IDS
    ↓
Stage 5: Pitchbook Preview
    11-slide canvas rendered from same bundle
    Copilot state mutations via /api/copilot/chat
    ↓
Stage 6: PPTX Export
    /api/pitchbook/generate rebuilds from the same bundle + overrides
    1:1 parity with preview
    ↓
Stage 7: Compliance Audit (on-demand)
    /api/check-compliance evaluates the full deck
    Remediations apply to preview and export
```

---

## 7. Current Constraints

Three constraints shape the current behavior:

### 7.1 Whitelist scoping

Only clients in `_DEMO_CLIENT_IDS` (backend) and `ACTIVE_UI_CLIENT_IDS` (frontend) go through
LLM synthesis and render in the UI. Currently scoped to Enel (`CLI101`).

The DB holds 13 clients. The whitelist is a demo-scoped decision, not an architectural limit.

### 7.2 Single-instance deployment

The mandate synthesis cache is in-memory. It requires `max-instances=1` on Cloud Run. If the
service ever scales horizontally, the cache would need to move to a shared store.

### 7.3 LLM-derived scores

`priority_score` is not computed by a formula. It reflects the last ingestion that wrote it.
A post-demo improvement is to compute it deterministically from the accumulated signal corpus
plus balance-sheet data.

---

## 8. Changelog — 14 Sep 2026

Corrected from the pre-14-Sep version:

- **Priority Score formula removed.** The doc previously described a three-factor weighted
  formula. That formula does not exist in the code. §3.2 rewritten to describe the actual
  mechanism.
- **Score values corrected.** BASF is 94, not 92. All clients now show accurate current
  values.
- **Slide count corrected.** 10 → 11 slides throughout.
- **Enel savings corrected.** The doc previously cited €375,000/year on €750M. Actual current
  mandate is €600M Green (€300k/yr) + €400M SLB (€80k/yr) = €380k/yr total.
- **Maturity format corrected.** The card and pitchbook show `€10.13bn`, not `€10,127M`.
  Both refer to the same underlying value.
- **Compliance regime clarified.** The active regimes are MiFID II, MAR, and EU Green Bond
  Standard. FINRA is mentioned in code but is not the primary checks. The regex pre-filter is
  dormant.
- **Client cohort corrected.** The UI whitelists to Enel only. The 13-client cohort lives in
  the DB but only the whitelisted client renders.
- **§6 Lifecycle In One View added.**
- **§7 Current Constraints added.**

---

*End of document.*