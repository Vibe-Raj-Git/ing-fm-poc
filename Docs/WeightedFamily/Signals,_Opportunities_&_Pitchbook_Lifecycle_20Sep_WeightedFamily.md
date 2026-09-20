# Financial Markets Deal Origination Engine: Signals, Opportunities & Pitchbook Lifecycle

**Version:** 20 September 2026 — Weighted-Family + Adjacencies
**Flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Parallel flavor:** Baseline (Flavor 1) at `Docs/Signals,_Opportunities_&_Pitchbook_Lifecycle.md`
**Branch:** `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3`
**Audience:** Engineers, Business Analysts

---

## 1. Executive Summary & Architectural Overview

Modern Wholesale Banking and Financial Markets origination requires continuous monitoring of corporate balance sheets, dynamic macro market curves, and real-time qualitative touchpoints. This platform employs a **two-stage hybrid architecture** combining deterministic financial logic with large language model semantic intelligence.

┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        HYBRID INGESTION & ORIGINATION ENGINE                           │
├────────────────────────────────────────────────────┬───────────────────────────────────┤
│            UNSTRUCTURED DATA SOURCES               │      STRUCTURED DATA SOURCES      │
│  • Google News RSS Feeds                           │  • Core Client Master             │
│  • Treasury Emails & Inbound Inquiries             │  • Balance Sheet & Debt Schedules │
│  • MS Teams Coverage Transcripts                   │  • Live Market Fixings            │
│  • House Views (PDF / PPTX Research)               │  • Historical Pricing             │
└─────────────────────────┬──────────────────────────┴─────────────────────────┬─────────┘
                          │                                                    │
                          ▼                                                    ▼
             [ LLM Extraction (Vertex AI) ]                     [ Deterministic SQL & Logic ]
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

text

**Current demo scope:** Enel S.p.A. (`CLI101`) is the primary demo client; BASF SE (`CLI103`) is a testable secondary. Both are whitelisted — `_DEMO_CLIENT_IDS = {"CLI101", "CLI103"}` on the backend, mirrored by `ACTIVE_UI_CLIENT_IDS` on the frontend. The DB holds 13 client records; only the whitelisted clients render. For an Enel-primary demo, revert both to `{"CLI101"}`.

**Values shown in this document reflect Enel's current DB state** — for illustration only. Each client's values are resolved from the DB at request time, filtered by `client_id`.

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

**Current canonical `source_channel` values** written by the pipeline: `PDF_REPORT`, `NEWS_RSS`, `CLIENT_EMAIL`, `TEAMS_CHAT`, `WORKFABRIC_MEMO`. Historical aliases from earlier ingestion eras (`LIVE_RSS_NEWS`, `TREASURY_EMAIL`, `ANALYST_NOTE`, `CONTEXT_FABRIC`, etc.) also exist in the DB and are readable by the read paths.

### 2.2 Semantic Extraction & Parameterization

Unstructured inputs are processed by **`gemini-2.5-flash`** on Vertex AI under a strict JSON extraction schema.

**Multi-signal extraction:** A single ingestion produces **N signals**, not one. A PDF with six sections produces six rows in `ca.digital_twin_signals`.

The model extracts per signal:

- `catalog_family` — `Financing/Capital Markets`, `Interest Rate`, `Foreign Exchange`, `Sustainable Finance`, `Commodities`, `Credit`, `Cross-Asset & Discovery`
- `signal_type` — free text (e.g., `SUSTAINABLE FUNDING`, `BOARD_AUTHORIZATION`, `REFINANCING`)
- `urgency` — `High` / `Medium` / `Low`
- `metric_identified` — short headline / metric
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

Two-layer deduplication:

Layer 1 — Signal dedup on (client_id, trigger_summary). If a signal with the same trigger summary already exists for the client, the insert is skipped.

Layer 2 — Channel-scoped semantic dedup on text content. Before inserting a chunk, the pipeline checks for existing chunks in the same source_channel with similar text content. On a semantic match, the write is suppressed and the existing chunk_id is returned.

Document chunk storage: Each ingestion also writes one row to ca.document_vector_chunks with the raw text, source metadata, and structured metadata (containing the full detected_signals array).

Ingestion does NOT write to ca.ca_opportunity_scoring. That table is populated or updated only by the mandate synthesis step. See §3.3.

## 3. Opportunity Discovery & Prioritization Engine
### 3.1 The Hybrid Discovery Method
Opportunity formulation combines LLM-derived signals with deterministic SQL logic:

Dimension	LLM Functionality	Deterministic Code / DB Functionality
Data Ingestion	Extracts triggers from unstructured text	Stores signals with two-layer dedup; stores document chunks
Catalog Mapping	Synthesizes deal narrative into "Why Now" rationale	Uses product-family templates and slide structure
Financial Math	Bypassed to prevent hallucinations	Computes maturity walls, liquidity ratios, and savings math
Model Risk Governance	Generates institutional text summaries	Threshold classification, cache, drift guard
### 3.2 Priority Score — Actual Implementation
The Priority Score is computed by the synthesis LLM against an explicit weighted rubric. It is not a formula in code, but it is not a frozen value either.

Rubric:

Signal strength — 40%

Balance-sheet pressure — 30%

Market window — 30%

History. An earlier version of this document stated the score was a legacy value from the pre-14-Sep single-signal ingestion pipeline and would not change. That was accurate at the time of writing but is superseded by commit 13721ca (18 Sep 2026). The synthesis prompt now returns priority_score as one of its keys; the value is written back to ca.ca_opportunity_scoring.priority_score on every synthesis cache miss for whitelisted clients.

Example — Enel (CLI101):

Field	Current value
opportunity_id	OPPCA104_CLI101
priority_score	Recomputed on synthesis; observed values 85, 88, 91, 93, 94 across a session
est_revenue_eur_000	5500.0 (i.e., €5.5M)
next_best_action	"We propose a €1.0bn dual-tranche senior unsecured issuance, strategically leveraging Enel's €3.5bn green asset pool through a €600m 7Y Green bond priced at Mid-swap + 73 bps (net of -5 bps greenium), complemented by a €400m 10Y Sustainability-Linked Bond..."
The other two scores:

Column	Current use
propensity_score	Read by pitchbook_builder.py as an ORDER BY tiebreaker in fetch_pitchbook_bundle when a client has multiple scoring rows. Not displayed.
value_score	Not read by any code path.
Non-determinism. Even at temperature=0.0, gemini-2.5-flash produces slightly different scores across synthesis runs. This is a property of the model. If a stable score is required for a demo, pin priority_score to the anchor's curated value — the same treatment the narratives receive.

### 3.3 Mandate Synthesis (the anchor pattern)
/api/opportunities runs a synthesis step anchored to the curated DB row.

Purpose: the signals in ca.digital_twin_signals describe evidence and context, but they don't contain a specific deal structure. Left to synthesize freely, an LLM will invent a plausible structure that may not match ING's actual advisory proposal. The anchor prevents that.

Flow:

1. Read why_now_nlg and next_best_action from ca.ca_opportunity_scoring (the anchor)
2. Check the TTL cache (`_MANDATE_SYNTH_CACHE`, 300-second expiry, keyed by `client_id`). In Flavor 2, entries are **8-tuples**: `(expiry, why_now, action, why_now_summary, action_summary, priority_score, family, adjacent_opportunities)`.
3. On cache miss and client in `_DEMO_CLIENT_IDS`:
   - Fetch the 20 most recent signals for the client
   - Call `gemini-2.5-flash` with the anchor placed first in the prompt
   - Receive JSON with seven keys: `why_now`, `action`, `why_now_summary`, `action_summary`, `priority_score`, `family`, `adjacent_opportunities`
   - Apply the drift guard (tenor conflict check)
   - UPDATE `ca.ca_opportunity_scoring.priority_score` — only the score is written back; `family` and `adjacent_opportunities` are not persisted (no columns exist)
   - Populate the cache only after `conn.commit()` succeeds; on failure, pop the cache entry

On cache hit or non-whitelisted client: use the DB row directly

Full detail in How_Signals_are_Converted_into_Opportunities.md §5.

### 3.4 Score Calibration & Priority Today Ranking
Threshold classification (in /api/opportunities, using the effective score):

python
_effective_score = int(final_priority_score) if final_priority_score is not None else int(score_num)
score_level = "High" if _effective_score >= 85 else ("Medium" if _effective_score >= 70 else "Low")
Range	Label
≥ 85	High
70 – 84	Medium
< 70	Low
_effective_score prefers the fresh synthesis value when present; falls back to the DB value on cache hit or non-whitelisted client.

Priority Today ranking:

The /api/metrics endpoint sorts all clients by priority score descending and takes the top 4, then appends any whitelisted client not already present (the whitelist guarantee, commit 13721ca):

python
sorted_rows = sorted(rows, key=lambda x: (int(x[2]), float(x[4])), reverse=True)[:4]
# then append missing whitelist clients
Frontend whitelist. The Priority Today sidebar in App.jsx filters to ACTIVE_UI_CLIENT_IDS (currently ["CLI101", "CLI103"]). Only whitelisted clients render, even though the API returns more priorities.

### 3.5 The Four Tiles on /api/metrics
The "This Week" section renders four tiles, all rewritten in commit f9f8eeb:

Tile	Backend key	Query	Scope
Clients with signals	clients_with_signals	COUNT(DISTINCT client_id) in ca.digital_twin_signals	Whitelist-scoped
Active signals	active_signals	COUNT(*) in ca.digital_twin_signals (all-time); change line shows 7-day count	Whitelist-scoped
High-priority clients	high_priority_clients	COUNT(DISTINCT client_id) in ca.ca_opportunity_scoring WHERE priority_score >= 85	Whitelist-scoped
Clients in database	clients_in_database	COUNT(*) in ca.client_master	Full book (not whitelist-scoped)
The prior "Avg. time to first draft" tile — which displayed < 15s / ▼ 99% vs manual — was hardcoded with no underlying measurement. It was removed; the platform does not record draft generation. Its replacement is "Active signals."

### 3.6 Product family classification (Flavor 2)

The synthesis LLM returns `family` as one of the seven keys. `detect_product_family(ctx)` in `pitchbook_builder.py` validates the proposal against a weighted anchor score computed from `_FAMILY_KEYWORD_WEIGHTS`.

- Strong product signals weight 5 (`green bond`, `slb`, `emtn`, `irs pre-hedge`, `fx collar`).
- Weak context words weight 1–2 (`refinancing`, `maturity wall`, `dual-tranche`, `senior unsecured`).
- If the weighted score is ≥ 5 with a margin ≥ 3 over the runner-up → weights override. Deterministic.
- Otherwise → trust the LLM.
- If both are silent → narrative keyword fallback.

**Observed:**

| Client | Anchor score | Margin | Outcome |
|---|---|---|---|
| Enel (`CLI101`) | 15 GREEN_ESG vs 5 DCM_REFI | 10 | Decisive — guaranteed `GREEN_ESG` |
| BASF (`CLI103`) | 8 DCM_REFI vs 5 RATES_HEDGE | 3 | At threshold — LLM decides |

The `family` field is not persisted. It travels via the 8-tuple cache, the `/api/opportunities` response, and the pitchbook bundle. See `Data_or_Fabrication_20Sep_WeightedFamily.md` §6.8.

### 3.7 Adjacent opportunities (Flavor 2)

The synthesis LLM returns `adjacent_opportunities` as the seventh key — an 80–140 word paragraph identifying up to 3 grounded cross-sell angles beyond the primary mandate. The prompt enforces: each adjacency cites a specific signal; no invention; no repetition of the primary; max 3 angles; no marketing language.

**Lifecycle:** produced on a cache miss; exposed in `/api/opportunities`; rendered on Slide 3 as the third card; included in the Copilot `slide_3` payload; read by `handle_pitchbook_generation` from `_MANDATE_SYNTH_CACHE[cid][7]` and set on the bundle before `build_pitchbook`.

**Non-determinism:** like `priority_score`, the paragraph varies across runs. Multiple grounded variants observed for Enel, all citing rate, FX, and DCM angles in different phrasings. See `Data_or_Fabrication_20Sep_WeightedFamily.md` §6.9.

## 4. Pitchbook Creation: UI Preview & Document Generation
### 4.1 The 11-Slide Deck
The pitchbook has 11 slides. Slide titles vary by product family (FX / Green / Rates / DCM). The table below shows the Green/ESG variant (Enel's deck).

#	Green / ESG	Primary Data Source
1	Cover Slide	ca.client_master.client_name, _CREDIT_RATINGS, ca.coverage_teams
2	Decarbonization Catalyst	ca.ca_opportunity_scoring.trigger_source + LLM summaries
3	Executive Summary	why_now, action, get_product_pillars()
4	ESG Balance Sheet	ca.ext_company_filings + _CREDIT_RATINGS
5	Use of Proceeds Pool	ca.debt_maturity_schedule + synthesis context
6	Greenium Sensitivity	ca.ext_credit_spreads + greenium override
7	ESG Market Backdrop	ca.mkt_rates_curves + ca.ext_credit_spreads
8	Green Bond Term Sheet	compute_canonical_bundle() + overrides
9	Why Execute With Us	Static capability cards (candidate for ca.ext_deals)
10	SPO & Syndicate Plan	Family-branched template
11	ICMA Disclosures	overrides.disclaimers + family fallback
Note: earlier versions of this doc cited ca.regulatory_notices as slide 11's source. That table does not exist. Slide 11 reads overrides and family fallbacks.
**Slide 3 (Executive Summary) — Flavor 2 layout.** The four pillars are rendered inside the left orange panel; the right column holds three stacked full-width cards: Catalyst Rationale, Proposed Execution, and **Adjacent Opportunities** (new). The third card reads `ctx["adjacent_opportunities"]`. Deck and preview layout coordinates in `architecture_flow_20Sep_WeightedFamily.md` §6.5.

Full mapping of all four families in architecture_flow_20Sep.md §6.2.

### 4.2 Synthesis of Structured & Unstructured Data
Structured grounding — slides 4 and 5 render exact metrics from ca.ext_company_filings and ca.debt_maturity_schedule:

Metric	Enel's current value	Source
Net Debt	€58.5bn	net_debt_eur_m = 58500
Available Liquidity	€14.2bn	liquidity_eur_m = 14200
24M Maturity Wall	€10.13bn	debt_maturing_24m_eur_m = 10127
Unstructured grounding — slides 1, 2, and 3 translate signal text into deal themes.

Sensitivity & term sheet — slide 6 computes cost savings, and slide 8 renders the two-leg term sheet from compute_canonical_bundle() and any active overrides.

### 4.3 Interactive UI Preview
Clicking Open draft pitchbook launches the workspace:

Slide Navigation — 11 structured slides with live previews

Origination Deal Copilot — LLM assistant for restructuring tranches, updating spread assumptions, and regenerating slide text

Compliance Audit — inspects the deck against MiFID II, MAR Art. 11, and (for green-family decks) the EU Green Bond Standard / EU Taxonomy

### 4.4 Production .PPTX Generation
Clicking Download .PPTX Deck executes /api/pitchbook/generate:

Fetches the bundle via fetch_pitchbook_bundle()

Applies overrides via build_pitchbook()

Renders 11 slides with corporate styling (python-pptx)

Returns a binary .pptx stream

The preview canvas and PPTX consume the same underlying bundle, ensuring 1:1 parity — verified on slides 4, 5, and 6 during the 19-20 Sep session.

## 5. Compliance Checkpoints
### 5.1 Where Compliance Runs
Compliance is evaluated at two points in the lifecycle:

Point	Endpoint	What it does
On-demand audit	POST /api/check-compliance (alias: /api/compliance/audit)	Full-deck inspection
During download	Implicit in build_pitchbook if overrides contain disclaimers	Applies active disclaimers

### 5.2 Regulatory Regimes
The compliance check is LLM-driven today. The endpoint sends the full deck to Gemini with a system prompt that evaluates against:

MiFID II (Art. 24/54) — professional clients, non-binding pricing caveats

MAR Art. 11 — market sounding safe harbour

EU Green Bond Standard / EU Taxonomy — for green-family decks

EMIR — derivative classification (NFC+ for pre-hedges)

Note: a regex list (PROMISSORY_PATTERNS) exists in main.py but is not called by any endpoint. All screening is LLM-driven. See Data_or_Fabrication.md §10.3 for the post-demo improvement.

### 5.3 Remediation
If the user clicks Apply Compliance Remediations, the endpoint returns an overrides object containing pricing_caveat, emir_notice, compliance_status, and any additional disclaimers. These merge into deckOverrides and apply to both preview and export.

## 6. Lifecycle In One View
Stage 1: Signal Arrival
    Ingestion → Gemini extraction → N signals written to DB
    Endpoint: /api/ingest/text or /api/ingest/file
    Two-layer dedup: (client_id, trigger_summary) + channel-scoped semantic
    ↓
Stage 2: Signal Accumulation
    Signals stored in ca.digital_twin_signals, filtered by client_id
    ↓
Stage 3: Opportunity Discovery
    /api/opportunities joins client + filings + markets + signals
    Synthesis (whitelisted clients) anchors to ca_opportunity_scoring
    Returns 7 keys: why_now, action, why_now_summary, action_summary,
    priority_score, family, adjacent_opportunities
    Only priority_score persisted
    Cache populated only after DB commit
    ↓
Stage 4: Priority Ranking
    /api/metrics sorts by _effective_score, takes top 4, appends
    missing whitelist clients
    Frontend filters to ACTIVE_UI_CLIENT_IDS
    ↓
Stage 5: Pitchbook Preview
    11-slide canvas; Slide 3 has three cards (adds Adjacent Opportunities)
    Copilot state mutations via /api/copilot/chat
    ↓
Stage 6: PPTX Export
    /api/pitchbook/generate rebuilds from the same bundle + overrides
    1:1 parity with preview on slides 4, 5, 6
    ↓
Stage 7: Compliance Audit (on-demand)
    /api/check-compliance evaluates the full deck
    Remediations apply to preview and export

## 7. Current Constraints
### 7.1 Whitelist scoping
Only clients in _DEMO_CLIENT_IDS (backend) and ACTIVE_UI_CLIENT_IDS (frontend) go through LLM synthesis and render in the UI. Currently scoped to {"CLI101", "CLI103"} — Enel and BASF.

The DB holds 13 clients. The whitelist is a demo-scoped decision, not an architectural limit.

### 7.2 Single-instance deployment
The mandate synthesis cache is in-memory. It requires max-instances=1 on Cloud Run. If the service ever scales horizontally, the cache would need to move to a shared store.

### 7.3 LLM-derived scores

`priority_score` is computed by the synthesis LLM against a weighted rubric. **Flavor 2 also has an LLM-classified `family`, validated by a weighted anchor score.** Both the score and the family are non-deterministic across synthesis runs — but for the demo client (Enel) the family is deterministic because the weighted margin is decisive (10). See §3.6.

A post-demo improvement is to replace the score with a fully deterministic formula. A separate backlog item is to refine `_FAMILY_KEYWORD_WEIGHTS` statistically as the platform accumulates classified anchors.

## 8. Changelog — 20 Sep 2026 (Flavor 2 — Weighted-Family + Adjacencies)

Changes since the Flavor 1 (Baseline) version. Flavor 1 is documented separately at `Docs/Signals,_Opportunities_&_Pitchbook_Lifecycle.md`.

### Added

- **§3.3 updated** — cache tuple 6 → 8; prompt returns 7 keys; only `priority_score` persisted.
- **§3.6 added** — product family classification. LLM proposal validated by `_FAMILY_KEYWORD_WEIGHTS`. Decision logic and observed outcomes.
- **§3.7 added** — adjacent opportunities paragraph. Prompt rules, lifecycle, non-determinism.
- **§4.1 slide 3 layout note added.**
- **§6 lifecycle diagram updated** — Stage 3 shows 7-key return and persistence rules; Stage 5 shows three-card Slide 3.
- **§7.3 rewritten** — family classification non-determinism; the statistical refinement backlog item.

### Common with Flavor 1

Data architecture, ingestion pipeline, DB schema, reset-to-pristine, defensive fallbacks, compliance architecture, deployment topology, anchor pattern, drift guard. Unchanged.

---

*End of document.*