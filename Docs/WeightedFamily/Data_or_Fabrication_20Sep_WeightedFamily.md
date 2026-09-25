# Data Integrity, Dynamic State Lineage & Zero-Fabrication Architecture

**Version:** 20 September 2026 — Weighted-Family + Adjacencies
**Status:** Authoritative
**Flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Parallel flavor:** Baseline (Flavor 1) at `Docs/Data_or_Fabrication.md`
**Branch:** feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3
**Audience:** Engineers, Business Analysts, Model Risk, Compliance

---

## 1. Executive Summary

The ING Financial Markets Deal Intelligence Platform is built on a **Zero-Fabrication Architecture**. Every value displayed to the Relationship Manager — balance sheet metrics, debt tranches, market rates, credit spreads, signal extractions, opportunity narratives — traces to a specific row in a specific PostgreSQL table, filtered by `client_id`.

No literal client values exist in the presentation layer. No hardcoded fee pools. No invented deal sizes. Where the platform displays a number or a claim, that number or claim has a source.

This document describes the actual pipeline as implemented, including the reset-to-pristine mechanism that lets a demo environment be restored to a curated baseline on demand without destroying user-ingested content. Where an earlier version of this doc described aspirational features (a composite scoring formula, a two-model LLM architecture), those sections have been corrected or removed. A summary of what changed is in §13.

**Corrections in the 20 Sep version** reflect the 19-20 Sep session, which changed the `priority_score` lifecycle (§6.2) and added code-level curated exceptions for credit ratings (§11.7) and frontend fallbacks (§11.8).

---

## 2. The Zero-Fabrication Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  UNSTRUCTURED INPUTS                                                                     │
│  • Microsoft Teams chats            • PDF / PPTX houseview uploads                       │
│  • Treasury / client emails         • WorkFabric memos                                   │
│  • Market RSS feeds                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ /api/ingest/text  or  /api/ingest/file
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  LLM EXTRACTION (gemini-2.5-flash)                                                       │
│  • Reads source text                                                                     │
│  • Returns { "detected_signals": [ { signal_type, catalog_family, metric_identified,     │
│    trigger_summary, metric_value, description, confidence_pct, urgency } ] }             │
│  • One document → N signals                                                              │
│  • Semantic dedup guard suppresses duplicate content within a channel                    │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  PERSISTENCE (Cloud SQL)                                                                 │
│  • INSERT INTO ca.document_vector_chunks (one row per ingestion)                         │
│  • INSERT INTO ca.digital_twin_signals (one row per detected signal)                     │
│  • Dedup guard on (client_id, trigger_summary) and channel-scoped text match             │
│  • Ingestion does NOT write to ca.ca_opportunity_scoring                                 │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ /api/opportunities
│  SYNTHESIS (Read-time, whitelisted clients only)                                         │
│  • Read anchor from ca.ca_opportunity_scoring                                            │
│  • Check TTL cache (900s, keyed by client_id, 10-tuple entry)                             │
│  • On cache miss and client in _DEMO_CLIENT_IDS:                                         │
│      – Fetch 20 most recent signals                                                      │
│      – Call gemini-2.5-flash with the anchor first; 7-key JSON return                    │
│      – Apply drift guard                                                                 │
│      – UPDATE ca.ca_opportunity_scoring.priority_score, then commit                      │
│      – Populate _MANDATE_SYNTH_CACHE only after commit succeeds                          │
│  • On cache hit or non-whitelisted client: use DB row directly                           │
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  RENDERING                                                                               │
│  • React preview canvas                                                                  │
│  • python-pptx export                                                                    │
│  • Both consume the same deckOverrides payload; slides 4, 5, 6 verified 1:1 on 20 Sep     │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Every arrow in this diagram maps to a specific function in `main.py` and a specific table or model in the data tier.

The **reset-to-pristine** mechanism (§8) is a separate, non-destructive path that restores curated baseline content from `baseline_snapshots.json`. It does not remove user-ingested rows; it refreshes the pristine rows' timestamps so they win the `created_at DESC` sort.

**Note on `priority_score`:** the synthesis step produces `priority_score` as one of **eight keys** — the Flavor 2 additions are `family` and `adjacent_opportunities`, and the branding-branch addition is `primary_trigger`. `priority_score` is written back to the anchor table on every cache miss for whitelisted clients. See §6.2.

---

## 3. UI Section → API → Table Mapping

Every visual element on the dashboard sources from live tables. Nothing is hardcoded (with two documented code-level exceptions: the credit rating dict in §11.7 and the frontend `default*` fallbacks in §11.8).

| UI Section | API Endpoint | Tables Read | Channel Filters |
|---|---|---|---|
| **This Week** — Clients with signals | `GET /api/metrics` | `ca.digital_twin_signals` | Whitelist-scoped |
| **This Week** — Active signals | `GET /api/metrics` | `ca.digital_twin_signals` | Whitelist-scoped; value = all-time, change = 7-day |
| **This Week** — High-priority clients | `GET /api/metrics` | `ca.ca_opportunity_scoring` | Whitelist-scoped; `priority_score >= 85` |
| **This Week** — Clients in database | `GET /api/metrics` | `ca.client_master` | Full book (not whitelist-scoped) |
| **Live Signal Feed** marquee | `GET /api/signals` | `ca.digital_twin_signals`, `ca.client_master` | Filtered to `_DEMO_CLIENT_IDS` |
| **Priority Today** sidebar | `GET /api/metrics` (priorities field) | `ca.ca_opportunity_scoring`, `ca.client_master` | — |
| **Client Data** segment | `GET /api/opportunities` | `ca.client_master`, `ca.ext_company_filings`, `ca.coverage_teams`, `_CREDIT_RATINGS` (dict) | — |
| **Market Data** segment | `GET /api/opportunities` | `ca.mkt_rates_curves`, `ca.ext_credit_spreads` | — |
| **Context Fabric** segment (chips) | `GET /api/opportunities` | `ca.document_vector_chunks` | `source_channel IN ('WORKFABRIC_MEMO', 'CONTEXT_FABRIC', 'ANALYST_NOTE', 'TEAMS_CHAT', 'CLIENT_EMAIL')` |
| **Context Fabric** segment (Desk Signal) | `GET /api/opportunities` | `ca.document_vector_chunks` | `source_channel = 'WORKFABRIC_MEMO'` |
| **Context Fabric** segment (Latent list) | `GET /api/opportunities` | `ca.digital_twin_signals` | `signal_type = 'LATENT_OPPORTUNITY'` |
| **Houseviews & News** — Houseview | `GET /api/opportunities` | `ca.document_vector_chunks` | `source_channel IN ('PDF_REPORT', 'HOUSEVIEW')` |
| **Houseviews & News** — Live Verified News | `GET /api/opportunities` | `ca.document_vector_chunks` | `source_channel IN ('NEWS_RSS', 'LIVE_RSS_NEWS', 'LIVE RSS News', 'News RSS')` |
| **Synthesized Mandate** hero | `GET /api/opportunities` | `ca.ca_opportunity_scoring` (anchor + synthesized narrative) | — |
| **Signal Lineage tiles** | `GET /api/opportunities` | Same sources as the four segments above | — |
| **Pitchbook canvas** | `GET /api/opportunities` + client state | Aggregate of the above, plus `deckOverrides` | — |
| **Pitchbook .pptx** | `POST /api/pitchbook/generate` | Same bundle as canvas | — |
| **Reset-to-pristine** | `POST /api/system/reset-baseline` | `baseline_snapshots.json` → upserts into 8 client-scoped tables | Whitelist via request body |

**Three notes on multi-channel and code-level sources:**

1. **Context Fabric chips accept five channel names.** `ANALYST_NOTE`, `CONTEXT_FABRIC`, and `MEMO` are standardized to `WORKFABRIC_MEMO` at display time. The analyst note channel merges into the WorkFabric chip rather than producing a separate chip.
2. **Live Verified News accepts four channel aliases.** `NEWS_RSS`, `LIVE_RSS_NEWS`, `LIVE RSS News`, and `News RSS` are all queried, sorted together by `created_at DESC, chunk_id DESC`. The current ingestion pipeline writes `LIVE_RSS_NEWS`; the other three are legacy aliases retained for compatibility.
3. **The Client Data segment's rating field is a code-level curated exception.** `credit_rating` is read from `_CREDIT_RATINGS` in `main.py:89` (and mirrored in `pitchbook_builder.py:6`), not from a DB column. `ca.client_master` has no `credit_rating` column. See §11.7.

**The `This Week` tiles were replaced in the 20 Sep session** (commit `f9f8eeb`). The prior "Avg. time to first draft" tile was hardcoded and unmeasurable; the prior three tiles (`Active drafts`, `Deals pending review`, `Cohort matches`) all rendered a frontend render count with no backend source. All four now read whitelist-scoped SQL values via `/api/metrics`.

## 4. Actual Database Schema

All tables live in the `ca` schema of the Cloud SQL PostgreSQL 15 instance.

### 4.1 Live tables

#### `ca.client_master`

| Column | Type | Notes |
|---|---|---|
| `client_id` (PK) | varchar | |
| `client_name` | varchar | |
| `group_parent` | varchar | |
| `legal_entity` | varchar | |
| `industry_sector` | varchar | |
| `country` | varchar | |
| `region` | varchar | |
| `ownership_type` | varchar | |
| `tier` | varchar | Coverage classification (e.g. `Tier 1`), not a credit rating |
| `hq_country` | varchar | |
| `revenue_eur_m` | numeric | |
| `rm_name` | varchar | Fallback RM if no `coverage_teams` row |
| `base_ccy` | varchar | |

**No `credit_rating` column.** The rating shown on the client card and pitchbook cover comes from a code-level dict (`_CREDIT_RATINGS`). See §11.7.

#### `ca.ext_company_filings`

| Column | Type | Notes |
|---|---|---|
| `filing_id` (PK) | varchar | |
| `client_id` | varchar | |
| `reporting_period` | varchar | **Sort key for the latest filing read.** Lexicographic — must sort highest for the pristine filing to win |
| `net_debt_eur_m` | numeric | |
| `liquidity_eur_m` | numeric | |
| `ebitda_eur_m` | numeric | |
| `reported_revenue_eur_m` | numeric | |
| `debt_maturing_24m_eur_m` | numeric | |
| `notes` | text | |

**Multi-row hazard (added 20 Sep, §11.9).** This table can contain multiple rows per client with identical `reporting_period` values. Most rows carry NULL for `reported_revenue_eur_m` and `ebitda_eur_m`; one row carries the populated values. Reads that pick "the latest row" via `ORDER BY reporting_period DESC LIMIT 1` can land on a NULL row. The 20 Sep cleanup deleted 4 NULL-revenue BASF rows, leaving 1 populated row.

#### `ca.debt_maturity_schedule`

| Column | Type | Notes |
|---|---|---|
| `isin` | varchar | **No primary key on this table** |
| `client_id` | varchar | |
| `instrument_type` | varchar | |
| `amount_eur_m` | numeric | |
| `maturity_year` | integer | |
| `coupon_rate_pct` | numeric | |
| `currency` | varchar | |

**No PK** — the reset endpoint handles this table with delete-by-client + insert (§8).

**Feeds slide 5/10.** The tranche ladder and "Total Maturity Profile" sum both read from this table per client. See §11.1.

#### `ca.mkt_rates_curves`

| Column | Type | Notes |
|---|---|---|
| `curve_id` (PK) | integer | |
| `curve_date` | date | |
| `currency` | varchar | |
| `tenor` | varchar | |
| `swap_rate_pct` | numeric | |
| `govt_yield_pct` | numeric | |
| `category` | varchar | |

**Global table** — not client-scoped. Never reset by the per-client reset endpoint.

#### `ca.ext_credit_spreads`

| Column | Type | Notes |
|---|---|---|
| `spread_id` (PK) | integer | |
| `quote_date` | date | |
| `issuer_or_rating` | varchar | |
| `sector` | varchar | |
| `tenor` | varchar | |
| `spread_bps` | numeric | |
| `all_in_yield_pct` | numeric | |
| `source` | varchar | |

**Global table** — not client-scoped. Never reset by the per-client reset endpoint.

#### `ca.ca_opportunity_scoring`

| Column | Type | Notes |
|---|---|---|
| `opportunity_id` (PK) | varchar | |
| `client_id` | varchar | One-to-many with `client_master` — a client may have multiple scoring rows |
| `opportunity_type` | varchar | Free text |
| `trigger_source` | text | |
| `est_revenue_eur_000` | numeric | Fee estimate (thousands EUR) |
| `propensity_score` | integer | LLM-derived; used only as an ORDER BY tiebreaker in the pitchbook bundle read |
| `value_score` | integer | LLM-derived; not read by any current code path |
| `priority_score` | integer | Displayed as `<Label> · <Score>`. **Recomputed on every synthesis run.** See §6. |
| `rank` | integer | **Not read by any code path.** Populated inconsistently. The presentation rank is computed at request time |
| `next_best_action` | text | **Anchor field** |
| `why_now_nlg` | text | **Anchor field** |

#### `ca.digital_twin_signals`

| Column | Type | Notes |
|---|---|---|
| `signal_id` (PK) | varchar | |
| `client_id` | varchar | |
| `catalog_family` | varchar | |
| `signal_type` | varchar | Free text (see §6.6 for why) |
| `metric_identified` | text | Display label for marquee headlines |
| `trigger_summary` | text | Used for dedup and marquee fallback |
| `metric_value` | varchar | For `BOARD_AUTHORIZATION` signals, must be a bare number (see §8.5) |
| `description` | text | Full description; used as Desk Signal fallback when no `WORKFABRIC_MEMO` chunk exists |
| `confidence_pct` | integer | |
| `urgency` | varchar | |
| `created_at` | timestamp | **Sort key for all read paths.** Ordered DESC, tiebroken by `signal_id` |

#### `ca.document_vector_chunks`

| Column | Type | Notes |
|---|---|---|
| `chunk_id` (PK) | bigint | `bigserial` — sequence-assigned. Curated chunks use explicit IDs ≥ 9,000,000 (see §8.5) |
| `client_id` | varchar | |
| `source_channel` | varchar | See §5.1 |
| `source_name` | varchar | Filename or source label |
| `text_content` | text | Extracted text |
| `structured_metadata` | jsonb | Format varies — see §5.3 |
| `embedding` | vector(768) | pgvector |
| `created_at` | timestamp | **Sort key for all read paths.** Ordered DESC, tiebroken by `chunk_id DESC` |

#### `ca.coverage_teams`

| Column | Type | Notes |
|---|---|---|
| `client_id` | varchar | **No primary key on this table** |
| `role_title` | varchar | Read path filters `ILIKE '%Relationship Manager%'` |
| `banker_name` | varchar | |
| `location` | varchar | |

**No PK** — the reset endpoint handles this table with delete-by-client + insert (§8).

### 4.2 Legacy tables

Not read by any live code path:

- `ca.dt_client_master` — earlier reduced-column version of `ca.client_master`
- `ca.ca_opportunity_scoring_backup` — snapshot table
- `ca.cand5_client_master` — candidate/deprecated schema (empty)

### 4.3 Client ID consistency

All live tables use canonical IDs (`CLI001`, `CLI002`, ... `CLI105`). Legacy IDs (`CLI009_ENEL`, `CLI010_BASF`) were migrated on 14 Sep 2026:

| Legacy ID | Canonical ID |
|---|---|
| `CLI009_ENEL` | `CLI101` |
| `CLI010_BASF` | `CLI103` |

**Distribution pattern:** The demo corpus is concentrated on two clients:

- **CLI101 (Enel)** — carries the original curated demo content
- **CLI103 (BASF)** — carries the newer curated demo content plus user-ingestion test content

The remaining 11 clients have baseline data in `client_master`, `ext_company_filings`, `ca_opportunity_scoring`, and `debt_maturity_schedule` (for a subset), but minimal signal and chunk history. This is intentional — the demo whitelists clients via `_DEMO_CLIENT_IDS` and `ACTIVE_UI_CLIENT_IDS`.

**Current whitelist (20 Sep 2026):** `{"CLI101", "CLI103"}` on both backend and frontend. Enel is the primary demo; BASF is a testable secondary. For an Enel-primary demo, revert both to `{"CLI101"}`.

Specific counts are not documented here because they drift with every ingestion. Use the live DB as the source of truth, or regenerate `baseline_snapshots.json` via `dump_baseline.py` (§8.2).

### 4.4 `ca.ext_deals`

Client-scoped ING track record. One row per historical deal. Not read by any current slide — the "Why Execute With Us" slide renders static capability cards. Candidate for future wiring.

| Column | Type |
|---|---|
| `deal_id` (PK) | varchar |
| `client_id` | varchar |
| `deal_type` | varchar |
| `volume_eur_m` | numeric |
| `role` | varchar |
| `deal_date` | date |

Currently 3 rows (2 for `CLI101`, 1 for `CLI103`).

---

## 5. Ingestion Channels — What Actually Gets Stored

### 5.1 Channel classification

Every ingestion is tagged with a `source_channel` value in `ca.document_vector_chunks`.

**Current pipeline produces these five canonical values:**

| Value | Typical source |
|---|---|
| `PDF_REPORT` | PDF / PPTX upload |
| `NEWS_RSS` | Google News RSS |
| `CLIENT_EMAIL` | Treasury / client email |
| `TEAMS_CHAT` | Microsoft Teams |
| `WORKFABRIC_MEMO` | Internal memos |

**Historical aliases coexist in the DB from earlier ingestion eras:**

`EMAIL`, `EMAIL_INGESTION`, `TEAMS`, `CHAT`, `HOUSEVIEW_TEXT`, `NEWS`, `LIVE_RSS_NEWS`, `TREASURY_EMAIL`, `ANALYST_NOTE`, `CONTEXT_FABRIC`.

**Important:** the read paths query a **superset** of what the current pipeline produces. For example, the Live Verified News read queries four aliases (`NEWS_RSS`, `LIVE_RSS_NEWS`, `LIVE RSS News`, `News RSS`). This is deliberate backward compatibility — legacy rows must remain readable even as the pipeline evolves.

**Webhook integrations must send canonical values.** The Context Fabric integration spec (`Context_Fabric_Integration_Production.md`) requires `source_channel="WORKFABRIC_MEMO"`, not the legacy `"CONTEXT_FABRIC"`. New channel eras add read-path complexity; canonical values avoid that.

### 5.2 Multi-signal extraction

A single ingestion produces **N signals**, not one. A PDF with six sections produces six rows in `ca.digital_twin_signals`.

**Example — Enel's `ENEL_Capital_Markets_Filing_2026_Test.pdf`:**

| # | signal_type | metric_identified |
|---|---|---|
| 0 | Debt Refinancing Requirements | €10.13bn debt maturing; 'late 2026 and 2027' |
| 1 | Funding Capacity Authorisation | €12.0bn; 'March 2027' |
| 2 | Interest Rate Risk Exposure & Pre-hedging Opportunity | Legacy coupon ~1.20%; Indicative refinancing yields 4.5%-5.0% |
| 3 | Foreign Exchange Exposure Review | USD-linked procurement; USD vs EUR exchange rate risk |
| 4 | Commodity Price Volatility Impact | N/A |
| 5 | Cross-Asset Risk Coordination Assessment | N/A |

### 5.3 Structured metadata format variance

Not all rows in `ca.document_vector_chunks` have the same `structured_metadata` schema. Three formats exist:

**Format A — Full extraction:**
```json
{
  "company_name": "...",
  "detected_signals": [ { signal_type, catalog_family, confidence_pct,
                          evidence_basis, evidence_status, trigger_summary,
                          metric_identified, urgency } ],
  "executive_summary": "...",
  "overall_evidence_assessment": "..."
}
```

**Format B — Simplified:**
```json
{
  "signal_type": "PUBLIC_ISSUANCE_COMPLETED",
  "evidence_type": "Client-Validated",
  "catalog_family": "Financing/Capital Markets",
  "confidence_pct": 90,
  "metric_identified": "$2.5bn"
}
```

**Format C — Null:**
```json
null
```

Consumers of `structured_metadata` must handle all three cases. The houseview label logic in `/api/opportunities` reads `meta.get("detected_signals")` and falls back gracefully when the key is absent. The reset endpoint preserves `structured_metadata` from the snapshot on upsert.

### 5.4 Deduplication

Ingestion applies a two-layer dedup guard:

**Layer 1 — Signal dedup on `(client_id, trigger_summary)`.** Before inserting a signal, the pipeline checks whether a signal with the same trigger summary already exists for the client. If so, the insert is skipped.

**Layer 2 — Channel-scoped semantic dedup on text content.** Before inserting a chunk, the pipeline checks for existing chunks in the same `source_channel` with similar text content. The comparison is LLM-assisted (semantic, not string-exact). If a match is found, the write is suppressed and the existing `chunk_id` is returned.

**Verified behavior:** an identical ingestion submitted twice returns:

```
Call 1: {"status": "INGESTED_AND_EVALUATED", ...}
Call 2: {"status": "duplicate_skipped", "message": "⚠️ Duplicate signal intercepted: ...", "chunk_id": <existing>}
```

Result: one chunk, zero new signals.

**Operational note:** cleanup queries must search on the extracted `trigger_summary` or `description`, not the raw input text. Gemini may rewrite the trigger summary during extraction, so the raw text may not appear verbatim in the DB.

## 6. Priority Score — What It Actually Is

### 6.1 Not a formula

An earlier version of this document described a four-factor weighted composite score:

```
Priority Score = w_mat · S_mat + w_curve · S_curve + w_lev · S_lev + w_sig · S_sig
```

**That formula does not exist in the code.** It was documented aspirationally but never implemented.

### 6.2 What the score actually is

`ca.ca_opportunity_scoring.priority_score` is an **LLM-derived estimate**, produced during **mandate synthesis** (not ingestion). Two paths have written it over the platform's history:

1. **Legacy path (pre-14-Sep ingestion era).** The old single-signal ingestion prompt included `priority_score` in its structured output. Values from that era are frozen unless overwritten.

2. **Current path (18 Sep 2026, commit `13721ca`; extended 20 Sep 2026, commit `1a04960`; extended 22 Sep 2026, commit `3b99c3c`; extended 23 Sep 2026, commit `79cf56e`).** The synthesis prompt (`synthesize_mandate_catalyst`) returns **eight keys**:

   - `why_now`, `action` — full narratives for slide 3
   - `why_now_summary`, `action_summary` — max 160 chars each, for slide 2
   - `priority_score` — integer 0-100. Weighted rubric: signal strength 40% / balance-sheet pressure 30% / market window 30%
   - `family` — one of `FX_HEDGE`, `GREEN_ESG`, `RATES_HEDGE`, `DCM_REFI`. Selected by the LLM based on the anchor's primary product; see §6.8
   - `adjacent_opportunities` — 80-140 word paragraph identifying up to 3 cross-sell angles grounded in the signal corpus; see §6.9
   - `primary_trigger` — two semicolon-separated datapoint clauses (≤ 180 chars) for Slide 2's Primary Market Trigger card; see §6.10 (new)

   `priority_score` is written back to `ca.ca_opportunity_scoring.priority_score` on every synthesis cache miss for whitelisted clients. `family`, `adjacent_opportunities`, and `primary_trigger` are not persisted to the DB (no column exists — §7.2 forbids DDL); they travel through the 10-tuple cache, the API response, and the pitchbook bundle.

   The cache tuple grew from 6 → 8 (Flavor 2, 20 Sep) → 9 (`primary_trigger`, 22 Sep) → 10 (`adjacent_opportunities_source`, 23 Sep). The `adjacent_opportunities_source` field at index 9 carries `llm` / `fallback` / `error` for observability.

**The current value is not a frozen legacy number.** It reflects the last synthesis run for the client. Because the cache TTL is 300s, the score refreshes at most every 5 minutes per whitelisted client.

**Non-determinism.** Even at `temperature=0.0`, `gemini-2.5-flash` produces slightly different scores across synthesis runs. Observed values for `CLI101` across a single session:

| Run | Score |
|---|---|
| 1 | 85 |
| 2 | 88 |
| 3 | 91 |
| 4 | 93 |
| 5 | 94 |

This is a property of the model, not a bug. If a stable score is required for a demo, pin `priority_score` to the anchor's curated value, the same treatment the narratives receive. That would make the score and the ranking fully deterministic.

### 6.3 Threshold classification

The card label is derived from the score by a fixed rule in `/api/opportunities` (`main.py:812–814`):

```python
_effective_score = int(final_priority_score) if final_priority_score is not None else int(score_num)
score_level = "High" if _effective_score >= 85 else ("Medium" if _effective_score >= 70 else "Low")
score_val = f"{score_level} · {_effective_score}"
```

| Score range | Label |
|---|---|
| ≥ 85 | High |
| 70 – 84 | Medium |
| < 70 | Low |

**Score preference chain.** `_effective_score` prefers the fresh synthesis value (`final_priority_score`) when present, and falls back to the DB value (`score_num`) when synthesis was skipped (cache hit or non-whitelisted client).

This means the score shown in the Priority Today sidebar and the score shown on the client card are the same value — both read through the same `_effective_score` chain.

### 6.4 The other two scores

`ca.ca_opportunity_scoring` also has `propensity_score` and `value_score` columns. Both are LLM outputs from earlier ingestion runs.

- `propensity_score` is read by `pitchbook_builder.py` as an **ORDER BY tiebreaker** in `fetch_pitchbook_bundle`. It does not affect the display value, but it does determine which row resolves when a client has multiple scoring rows.
- `value_score` is not read by any current code path.

### 6.5 Display provenance

The card shows a tooltip on hover:

> *LLM-generated priority estimate (0–100). High ≥ 85 · Medium 70–84 · Low < 70.*

This is honest — it states the score is an LLM estimate, not a computed metric.

### 6.6 What the score is NOT

- Not a compliance score
- Not a risk score
- Not derived from a formula in code
- Not the sum of weighted dimensions
- Not frozen — it refreshes on synthesis runs

### 6.7 Known open item — `COALESCE(priority_score, 75)` fallback

Two live read sites substitute a fabricated score when the DB has no value:

- `main.py` — `/api/metrics` priorities query (`COALESCE(o.priority_score, 75) as score`)
- `main.py` — `/api/opportunities` main query (`COALESCE(os.priority_score, 75)`)

Both use a fallback of `75`. A client with no scoring row would be displayed with a fake score of 75, classified as "Medium" by the §6.3 threshold rule. This **violates the zero-fabrication principle** stated in §1.

**Currently dormant:** all 13 clients in the DB have a scoring row, so the fallback never fires.

**Mitigation (18 Sep, `13721ca`):** the `/api/metrics` endpoint now guarantees that whitelisted clients appear in the priorities list even when their score ranks below the top-4 slice. This prevents silent dropouts from the sidebar but does not remove the fallback score.

**Backlog fix:** replace `COALESCE(priority_score, 75)` with a null-preserving read. Null-safety handling needed downstream in `_effective_score` and the response construction, both of which currently assume `score_num` is an integer. The design decision — filter unscored clients vs. render them with an "Unscored" label — should be made before implementation. This is a read-path change only; no schema change required.

### 6.8 Product family as a synthesis output (Flavor 2, added 20 Sep)

The synthesis LLM returns `family` as one of the seven keys — one of `FX_HEDGE`, `GREEN_ESG`, `RATES_HEDGE`, `DCM_REFI`. This is the product family classification that drives pitchbook template selection.

**Where it comes from:** the prompt instructs the LLM to base the family on the anchor's `next_best_action` (not its own synthesized action), choose the dominant product, and apply a notional tiebreaker when multiple products are present.

**How it's validated:** `pitchbook_builder.py`'s `detect_product_family(ctx)` reads the LLM proposal from `ctx["family"]` and validates it against a weighted anchor score computed from `_FAMILY_KEYWORD_WEIGHTS`:

- Score `why_now_nlg` + `next_best_action` for each family's keywords.
- Strong product signals weight 5 (`green bond`, `slb`, `emtn`, `irs pre-hedge`, `fx collar`).
- Weak context words weight 1–2 (`refinancing`, `maturity wall`, `dual-tranche`).
- If the top family's score ≥ 5 with margin ≥ 3 over the runner-up → weights override.
- Otherwise → trust the LLM.
- If both silent → narrative keyword fallback (pre-20Sep logic).

**Observed:** Enel anchor scores 15 GREEN_ESG vs 5 DCM_REFI (margin 10, decisive); BASF anchor scores 8 DCM_REFI vs 5 RATES_HEDGE (margin 3, LLM decides).

**Where it goes:** the family is not persisted to `ca_opportunity_scoring` (no column — §7.2). It travels in the 8-tuple cache, the `/api/opportunities` response as `family`, and the pitchbook bundle. The frontend reads `activeClient.family` — the pre-20Sep keyword branches on `opportunity_type` and client name in `App.jsx` have been removed.

**Sync invariant:** `_FAMILY_KEYWORD_WEIGHTS` is defined in both `main.py` and `pitchbook_builder.py`. The two must remain byte-identical. See §11.10.

### 6.9 Adjacent opportunities as a synthesis output (Flavor 2, added 20 Sep)

The synthesis LLM returns `adjacent_opportunities` as the seventh key — an 80-140 word business-English paragraph identifying up to 3 cross-sell angles beyond the primary mandate.

**Prompt rules:**
- Each adjacency must cite a specific signal from the corpus (grounded).
- No invention — empty string if no adjacencies are supported.
- No repetition of the primary mandate.
- Maximum 3 adjacencies, prioritised by notional or urgency.
- No marketing language.

**Lifecycle:**
1. Produced by synthesis on a cache miss; stored at element 7 of the cache tuple.
2. Exposed in `/api/opportunities` as `adjacent_opportunities`.
3. Rendered on Slide 3 as the third card — its own background and heading.
4. Included in the Copilot `slide_3` payload for both `baseline_deck_slides` and `active_deck_slides`.
5. Read by `handle_pitchbook_generation` from `_MANDATE_SYNTH_CACHE[cid][7]` and set on the pitchbook bundle before `build_pitchbook`.

**Fallback (updated 23 Sep, commit `79cf56e`; deck path updated 25 Sep, commit `d7c17d8`).** Empty LLM output is caught by `_validate_adjacent_opportunities` (non-empty, ≥ 100 chars, ≥ 40 words) and replaced with a curated paragraph from `ADJACENT_OPPORTUNITY_FALLBACKS`. The chain is: per-client (`CLI101`, `CLI103`) → per-family (`_GREEN_ESG`, `_DCM_REFI`, `_RATES_HEDGE`, `_FX_HEDGE`) → `_FALLBACK`. Every rejection logs the failed rule.

The API path populates the cache with the resolved value — never an empty string. The API response also carries `adjacent_opportunities_source` (`llm` / `fallback` / `error`) for observability.

The deck builder (`pitchbook_builder.py`) uses the same fallback chain since 25 Sep. When the synthesis cache is cold at deck-generation time — e.g. a deck download without a prior dashboard load — the deck renders the curated per-client paragraph, not a placeholder. The placeholder string `"Additional origination angles will appear here once the mandate synthesis identifies any."` remains in the code as the last-resort literal but is now effectively unreachable through the normal synthesis path.

**Observed in a live demo (24 Sep 2026).** A manager downloaded the CLI101 deck without loading the dashboard first. The cache was cold. Slide 3's adjacent card showed the placeholder instead of a substantive paragraph. The 25 Sep fix closes this path.

**Non-determinism.** Like `priority_score`, the paragraph varies across synthesis runs. Observed Enel outputs across a session: one 105-word paragraph citing rate pre-hedge + FX + liability management; another 105-word paragraph citing rate hedging + FX + DCM. Both grounded, both non-repetitive. This is expected — the LLM reads the corpus and writes a fresh summary each cache miss.

### 6.10 Primary trigger as a synthesis output (added 22 Sep 2026, commit `3b99c3c`)

Slide 2's Primary Market Trigger card is populated by an LLM-generated `primary_trigger` field. The synthesis prompt receives a family-scoped instruction block (`FAMILY_PRIORITY_SIGNALS` + `FAMILY_CONTEXT_SIGNALS`) that steers the LLM toward datapoints most relevant to the resolved product family.

**Format rules.** Two semicolon-separated datapoint clauses, ≤ 180 characters, each clause contains a number and a unit, no marketing adjectives. Good example: `€3.5bn eligible green asset pool; €10.13bn maturity wall across 2026-2027`.

**Validator (`_validate_primary_trigger`).** Five deterministic rules:

1. Non-empty, ≤ 180 chars
2. Exactly one semicolon
3. Both clauses contain at least one digit
4. No marketing words (from the `_MARKETING_WORDS` blocklist)
5. Top family from `_FAMILY_KEYWORD_WEIGHTS` scoring matches the resolved family

**Fallback chain (`_resolve_primary_trigger`).** On rejection, substitutes a curated value in order: per-client entry from `PRIMARY_TRIGGER_FALLBACKS` (`CLI101`, `CLI103`) → per-family entry (prefixed `_`) → literal `"Active capital structure optimization"`. Every rejection logs the rule that failed.

**Read path precedence** in the deck and preview:

1. Session override (`ov["trigger"]` / `deckOverrides.trigger`)
2. `ctx["primary_trigger"]` — LLM-generated from the cache
3. `ctx["trigger_source"]` — curated DB value
4. Family default

**Cold-cache behaviour.** On a cold cache, `primary_trigger` is absent from the bundle. Unlike `adjacent_opportunities`, this field does **not** have a deck-builder gap — the deck reads `ctx["trigger_source"]` as its tier-3 fallback, which is a curated DB value. The literal placeholder only fires if all four tiers are empty. Confirmed 25 Sep 2026 during the deck cold-cache audit.

---

## 7. Defensive Fallback Architecture

### 7.1 Where fallbacks live

`main.py` contains two `def get_live_signals()` definitions. The first is the live one — it is bound to the FastAPI route via `@app.get("/api/signals")` at decoration time. The second is dead code: Python rebinds the module-level name on load, but the route table already holds a reference to the first function object.

**Which one is live, precisely:**

- **First definition** — carries `_DEMO_CLIENT_IDS` filter, client-name normalization, `LIMIT 40` SQL, `[:12]` Python slice, `(client_name, headline)` dedup
- **Second definition** — plain SQL, `LIMIT 15`, no whitelist, no dedup, not connected to any route

The second definition is a maintenance hazard. Deleting the wrong one would restore the whitelist filter (`[:12]`) but remove it from the served endpoint, changing runtime behavior. Cleanup is a backlog item.

### 7.2 What the fallback contains

The live `get_live_signals` returns three signals when `ca.digital_twin_signals` yields no rows:

| ID | Client | Type | Headline |
|---|---|---|---|
| `SIG-DF1` | BASF SE (`CLI103`) | REFINANCING | BASF SE: €2.0B 6Y EMTN & €1.2B Pre-Hedge |
| `SIG-DF2` | Enel S.p.A. (`CLI101`) | SUSTAINABLE FUNDING | Enel S.p.A.: €1.0B Dual-Tranche Green & SLB Issuance |
| `SIG-DF3` | ASML Holding (`CLI102`) | HEDGING | ASML Holding: EUR 900M FX Collar Hedge |

These are static strings, present for graceful degradation. They fire only when the DB query returns no rows.

### 7.3 Circuit breaker pattern

```python
try:
    cur.execute("SELECT ... FROM ca.digital_twin_signals ...")
    raw_signals = cur.fetchall()
except Exception as db_err:
    logger.error(f"Database query failed, engaging defensive circuit breaker: {db_err}")
    raw_signals = []

if not raw_signals:
    raw_signals = [ ... fallback list ... ]
```

The circuit breaker protects against:

- Cloud SQL transient network partitions
- Cold restart connection limits
- Query timeouts

It does NOT fire when the query returns rows successfully. In normal operation, the database query wins.

### 7.4 No phantom writes

Fallback values are read-only. They are never written back to the database. A client displayed via the fallback is a client with no live signal data — the fallback makes that state visible rather than failing silently.

### 7.5 RSS synthetic article fallback

`/api/rss/feed` returns two synthetic articles per client when Google News returns no rows. These articles are returned to the Ingestion Engine modal only. They are **never persisted** to the DB and **never surface** on the opportunity card.

The purpose is graceful degradation: the modal has something to show rather than an empty list. This is not a zero-fabrication concern because these articles never become display data — they are inputs the user may choose to ingest. If ingested, the regular pipeline processes them, and any resulting signals or chunks are subject to the normal dedup and validation guards.

**Caveat:** the synthetic articles look identical to real ones. There is no visual marker distinguishing a synthetic fallback article from a real Google News result. A future improvement would be to label fallback articles in the modal UI (e.g., `[Sample] ...`), but this is not a correctness issue.

### 7.6 Synthesis fallback path

If the synthesis LLM call throws (network error, model unavailable, malformed JSON), `get_opportunities` falls through to a deterministic fallback:

```python
final_why_now = why_now or (f"Active debt refinancing window with maturing debt of €{float(m24):,.0f}M." if float(m24) > 0 else "Active balance sheet review.")
final_action = action or "Proactive capital markets advisory and rate hedging review."
final_why_now_summary = ""
final_action_summary = ""
final_priority_score = None
```

The fallback uses the anchor's `why_now_nlg` / `next_best_action` from the DB (`why_now` and `action` in the code above), or a family-neutral statement if those are empty. `final_priority_score = None` means the response construction falls back to the DB's `score_num` value rather than a fresh synthesis score.

No fabricated deal structure is introduced — the fallback either uses the DB's curated anchor or a generic statement.

## 8. Reset-to-Pristine Baseline

### 8.1 Purpose

The platform is deployed on a publicly accessible Cloud Run URL for demonstration purposes. Over the life of the demo, users will ingest arbitrary content, mutate the deck via the Copilot, and alter the visible state of the UI. The reset feature restores the curated baseline on demand.

**Design constraints:**

1. **Do not delete user-ingested content.** The audit trail of every ingestion must be preserved in the DB.
2. **Restore curated baseline on the UI and pitchbook.** After reset, the RM must see the curated narrative, not whatever users have ingested.
3. **Allow future ingestions to become visible again.** The reset is not a lock — a user who ingests after a reset sees their content.

### 8.2 The baseline snapshot file

`baseline_snapshots.json` is the authoritative pristine state. It is generated by `dump_baseline.py`, a read-only utility that:

- Enumerates all clients from `ca.client_master`
- Reads every client-scoped table with all display-relevant columns
- Reads global tables (`mkt_rates_curves`, `ext_credit_spreads`) once, at top level
- Writes to `baseline_snapshots.json`

**Shape:**

```json
{
  "_meta": {
    "version": "1.0",
    "generated_at": "...",
    "client_count": 13,
    "note": "..."
  },
  "clients": {
    "CLI101": {
      "client_master": [ {...} ],
      "ext_company_filings": [ {...} ],
      "ca_opportunity_scoring": [ {...} ],
      "digital_twin_signals": [ {...} ],
      "document_vector_chunks": [ {...} ],
      "debt_maturity_schedule": [ {...} ],
      "coverage_teams": [ {...} ],
      "ext_deals": [ {...} ]
    }
  },
  "global": {
    "mkt_rates_curves": [ {...} ],
    "ext_credit_spreads": [ {...} ]
  }
}
```

The file ships with the container image via the `Dockerfile`:

```
COPY main.py pitchbook_builder.py baseline_snapshots.json ./
```

Without this line, the endpoint would return `"baseline_snapshots.json not found"` on Cloud Run.

**`ca.ext_company_filings` is included in the snapshot.** Row-level cleanups to that table (e.g. the 20 Sep BASF NULL-row deletion, §11.9) are overwritten by a reset — the snapshot holds whatever state existed when `dump_baseline.py` was last run. After cleaning filings rows, re-run `dump_baseline.py` and commit the new snapshot so the clean state becomes the new pristine baseline.

### 8.3 The reset endpoint

`POST /api/system/reset-baseline` — defined in `main.py` as `reset_baseline`.

**Request:** `{"client_ids": ["CLI103"]}`. If `client_ids` is absent, the endpoint defaults to `_DEMO_CLIENT_IDS`.

**Behavior per client:**

1. Read `snapshots["clients"][cid]`
2. For each table in the snapshot:
   - **PK-bearing tables** — `client_master`, `ext_company_filings`, `ca_opportunity_scoring`, `digital_twin_signals`, `document_vector_chunks`, `ext_deals` — upsert with `ON CONFLICT (pk) DO UPDATE`. The row's full column set is refreshed from the JSON.
   - **PK-less tables** — `debt_maturity_schedule`, `coverage_teams` — delete all rows for the client, then insert the snapshot's rows. Safe because ingestion does not write to these tables, so the delete only removes prior pristine copies.
3. For `digital_twin_signals` and `document_vector_chunks`, set `created_at = NOW()` on both insert and update. This makes the pristine rows newer than any user-ingested rows in the same table, so they win the `ORDER BY created_at DESC` sort.
4. Invalidate `_MANDATE_SYNTH_CACHE[cid]` so the next `/api/opportunities` call regenerates the mandate narrative.

**Transaction safety:** the entire operation is wrapped in a single transaction. On any error, `conn.rollback()` reverts all changes. The response is either fully-applied or fully-rejected.

**Response:**

```json
{
  "status": "success",
  "restored_clients": ["CLI103"],
  "skipped_clients": [],
  "summary": {
    "CLI103": {
      "client_master": 1,
      "ext_company_filings": 5,
      "ca_opportunity_scoring": 1,
      "digital_twin_signals": 42,
      "document_vector_chunks": 29,
      "debt_maturity_schedule": 3,
      "coverage_teams": 3,
      "ext_deals": 1
    }
  },
  "timestamp": "..."
}
```

`summary` reflects what the endpoint read from the JSON, not what was in the DB. If a requested `cid` is absent from the JSON, it is listed in `skipped_clients`.

### 8.4 What the reset does NOT do

- **Does not delete user-ingested signals or chunks.** They remain in the DB. They are simply outranked by the pristine rows.
- **Does not modify user-ingested rows.** No UPDATE touches rows the user created.
- **Does not touch global tables.** `ca.mkt_rates_curves` and `ca.ext_credit_spreads` are not client-scoped and are not reset. They cannot be modified by ingestion, so they remain pristine by default.
- **Does not touch non-whitelisted clients.** Only the client IDs in the request body are reset.
- **Touches ca.ext_company_filings.** Included in the snapshot (see §8.2). A reset restores the snapshot's filing rows for the client.

### 8.5 The `chunk_id` tiebreak convention

Because the reset sets `created_at = NOW()` on all pristine chunks, ties are broken by `chunk_id DESC`. Any chunk with a higher ID wins. Organic chunks naturally get high IDs from the `bigserial` sequence as ingestions accumulate — so a curated chunk with a low ID would lose.

**Convention:** curated chunks use explicit `chunk_id` values in the range **9,000,000 and above**. Because `ON CONFLICT (chunk_id) DO UPDATE` preserves these IDs across resets, curated chunks always win the tiebreak.

Current curated chunks for BASF (`CLI103`):

| chunk_id | source_channel | source_name |
|---|---|---|
| 9000001 | `WORKFABRIC_MEMO` | Luca Moretti (DCM Origination) |
| 9000002 | `HOUSEVIEW` | ING Chemicals Sector Strategy — Q3 2026 |
| 9000003 | `CLIENT_EMAIL` | BASF Group Treasury (Claudia Meier) |
| 9000004 | `TEAMS_CHAT` | European Chemicals Coverage (#deal-coverage-basf) |

**Analogous convention for signals:** curated signals use IDs in the form `SIG_BASF_*` (or client-specific prefixes) so they are visibly distinguishable from ingestion-generated `SIG-<uuid>` IDs.

The curated content is regenerated by `enrich_basf_baseline.py`, an idempotent utility that inserts the curated signals and chunks for BASF. It uses `ON CONFLICT (signal_id) DO UPDATE` for signals and a lookup-then-insert guard for chunks, so re-running it does not produce duplicates.

**Contract for `metric_value` on `BOARD_AUTHORIZATION` signals:** the read path in `/api/opportunities` constructs the "Context Fabric" lineage tile value as `f"{metric_value} financing capacity"`. The `metric_value` column must therefore contain a bare number (e.g., `"€12bn"`, `"€4.0bn"`). A value that already contains the suffix would produce "€4.0bn financing capacity financing capacity". The read path additionally normalizes `.0bn` → `bn` and truncates at the first `;` delimiter.

### 8.6 Effect on the UI after a reset

Because the sort key is `created_at DESC`, and the pristine rows now hold `NOW()`, the effect is:

| UI Element | Before Reset | After Reset |
|---|---|---|
| Context Fabric Desk Signal | Whatever newest `WORKFABRIC_MEMO` chunk the user ingested | Curated `WORKFABRIC_MEMO` chunk (9000001) |
| Context Fabric chips | Chips read from the newest row per channel | Curated chunks (9000001–9000004) win per channel |
| Latent Opportunity list | Whatever `LATENT_OPPORTUNITY` signals exist, ordered by `signal_id ASC` | Curated latents (L-01, L-02, L-03) |
| Houseviews & News body | Newest `PDF_REPORT` or `HOUSEVIEW` chunk | Curated houseview chunk (9000002) |
| Live Verified News | Newest news-alias chunk | Curated or next-newest pristine news chunk |
| Lineage Tile 3 | Whatever `BOARD_AUTHORIZATION` signal is newest | Curated board authorization signal |
| Lineage Tile 4 | Newest houseview chunk's `detected_signals[0].metric_identified` | Curated houseview chunk's metric |
| Synthesized Mandate | Cached narrative from prior synthesis | Cache invalidated; next read re-synthesizes from pristine anchor |

**What remains visible after reset:**

- User-ingested signals and chunks stay in the DB, outranked but present.
- The next user ingestion becomes the newest row again, so the pristine rows lose their precedence — until the next reset.

### 8.7 Idempotency

Clicking the reset ten times produces the same DB state as clicking it once. Because the operation only upserts pristine rows (never inserts new ones beyond what the JSON holds) and only deletes rows matching prior pristine content in PK-less tables, repeated resets do not grow the DB or create duplicates.

---

## 9. Copilot State Grounding

The Deal Copilot reads from two dicts constructed before the LLM call:

- **`baseline_deck_slides`** — pristine values, from the DB
- **`active_deck_slides`** — current values, with any session overrides applied

Both are serialized into the system instruction. The LLM cannot answer from memory; it must read from the payload.

Compliance with this pattern is validated by the test suite in `Copilot_Test_Suite.md`.

**Wall and rating in the Copilot context (20 Sep update).** The Copilot's `db_wall_str` reads `debt_maturing_24m_bn` (billions format) from the bundle, and the rating reads `_CREDIT_RATINGS` via the shared dict. Prior to the 19-20 Sep fixes, the Copilot context computed these independently and drifted from the deck.

**Flavor 2 additions (20 Sep, commit `1a04960`).** Both `baseline_deck_slides["slide_3"]` and `active_deck_slides["slide_3"]` now carry two additional fields:

- `family` — the product family from the synthesis classifier (element 6 of the cache tuple)
- `adjacent_opportunities` — the grounded cross-sell paragraph (element 7 of the cache tuple)

Both are read from `_MANDATE_SYNTH_CACHE[cid]` at request time. Fallback: `None` and `""` when the cache is cold or expired.

**Branding additions (22 Sep).** `baseline_deck_slides["slide_2"]` and `active_deck_slides["slide_2"]` carry the `primary_trigger` field (element 8 of the cache tuple) alongside `trigger_source`. The Copilot can answer questions about the trigger and fall back to the curated value when the cache is cold.

The Copilot prompt's response architecture now includes a conditional fourth section — **Adjacent Opportunities** — which appears only when the `adjacent_opportunities` field is non-empty. The Copilot answers questions about cross-sell angles by reading this field directly, without a separate retrieval step.

**Euro rendering fix.** The two `json.dumps` calls that serialize `baseline_deck_slides` and `active_deck_slides` into the prompt use `ensure_ascii=False`. UTF-8 characters (notably `€`) reach the LLM as real characters rather than JSON escapes. Prior to this fix, the Copilot occasionally echoed `\u20ac` in replies for Slide 3 while Slide 2 rendered `€` — the LLM's behavior was inconsistent given the same payload. Serializing with real UTF-8 removes the ambiguity.

---

## 10. Compliance — LLM-Driven, Not Regex

### 10.1 Two-stage design (documented)

The earlier version of this document described a two-stage compliance engine:

1. **Stage 1:** Deterministic regex filter on promissory terms
2. **Stage 2:** Gemini regulatory context screening

### 10.2 What's actually implemented

Only Stage 2 exists. The compliance audit is entirely LLM-driven. The regex list (`PROMISSORY_PATTERNS`) is defined in `main.py` but **is not called by any endpoint**.

**Current behavior:** `POST /api/check-compliance` sends the full deck to Gemini, which evaluates against MiFID II, MAR, and (for green-family decks) the EU Green Bond Standard. The response includes flags with `slide_number`, `rule`, `issue`, and `recommended_overrides`.

### 10.3 Post-demo improvement

Wiring the regex filter as a pre-filter before the LLM call would:

- Make the check deterministic for a subset of patterns
- Reduce LLM cost for obviously-compliant decks
- Provide a "hard flag" that the LLM cannot override

This is a backlog item, not a current defect.

## 11. Known Data Inconsistencies

### 11.1 Two maturity sources for the same client

Two tables carry "what's maturing" for each client, measuring different things:

**Enel (`CLI101`):**

| Source | Value | Meaning |
|---|---|---|
| `ca.ext_company_filings.debt_maturing_24m_eur_m` | €10,127M | Balance-sheet reported 24-month maturity wall |
| `ca.debt_maturity_schedule` (2026-2028 itemized) | €7,100M (2026+2027 only) | Itemized instruments by year |

**BASF (`CLI103`):**

| Source | Value | Meaning |
|---|---|---|
| `ca.ext_company_filings.debt_maturing_24m_eur_m` | €3,000M | Balance-sheet reported 24-month maturity wall |
| `ca.debt_maturity_schedule` (2026-2028 itemized) | €9,097M | Itemized instruments by year |

These are not the same thing:

- The **balance-sheet figure** is the reported 24-month aggregate. It drives the client card's "24M Maturity Wall" and the mandate narrative.
- The **itemized schedule** is what appears in slide 5/10's per-tranche ladder and sums to "Total Maturity Profile."

**Both are correct for their own definition.** For BASF, the two differ significantly (€3.00bn vs €9,097M) because the itemized schedule extends to 2028 while the aggregate is 24-month scoped. Do not treat the difference as a bug.

**20 Sep fix:** slide 5/10's total line now shows the itemized sum with the "Total Maturity Profile" label (§8.5, slide 5 changes). The card and mandate narrative continue to show the aggregate. Different labels, both honest.

### 11.2 Structured metadata format variance

Covered in §5.3. Three formats coexist. Consumers must handle all three.

### 11.3 Two `get_live_signals` definitions

Covered in §7.1. Dead code duplication, no functional impact, cleanup candidate.

### 11.4 No primary keys on `debt_maturity_schedule` and `coverage_teams`

Both tables lack primary keys and unique constraints. This means:

- `ON CONFLICT` cannot be used on these tables
- The reset endpoint uses delete-by-client + insert
- Any future code that inserts into these tables must guard against duplicates manually

The current ingestion pipeline does not write to either table, so duplicates do not accumulate in normal operation. If a future feature adds client-writable data to these tables, the reset pattern will need to be revisited.

### 11.5 Clients with no `priority_score`

See §6.7. `COALESCE(priority_score, 75)` masks the absence of a score with a fabricated value. Not currently triggered but a known open item.

### 11.6 Duplicate `client_name` values

Two clients share the display name "ASML Holding N.V.":

- `CLI002` — priority_score 82
- `CLI102` — priority_score 94

They are distinct records with distinct IDs. The duplication is a data entry issue, not a code defect. Documented here so future engineers do not treat it as a bug.

### 11.7 Credit rating as a code-level dict (added 20 Sep)

`ca.client_master` has **no `credit_rating` column**. The client card and pitchbook cover display a rating sourced from a curated `_CREDIT_RATINGS` dict:

**`main.py:89`** and **`pitchbook_builder.py:6`**:

```python
_CREDIT_RATINGS = {
    "CLI101": "S&P | BBB | Positive",   # Enel S.p.A.
    "CLI103": "S&P | A- | Stable",      # BASF SE
}
```

The frontend reads `opp.credit_rating` from the API response — no client-side rating logic. Adding a new demo client requires adding its rating to **both** dicts.

**Prior implementation (superseded):** before 20 Sep, the rating was a per-client `if cid == "CLI101"` branch in three places (`main.py`, `pitchbook_builder.py`, and `App.jsx`). For any non-Enel client, the display fell through to `tier` — a coverage classification, not a credit rating. Fixed in commit `f9f8eeb`.

**Why a dict, not a DB column:** §7.2 forbids DDL. If the schema unlocks, a `credit_rating` column on `ca.client_master` is the correct home for this data.

**Sync invariant:** the two `_CREDIT_RATINGS` dicts (`main.py`, `pitchbook_builder.py`) must remain identical. A mismatch produces a card-vs-deck-cover inconsistency. See `master_persona_20Sep.md` §7.9.

### 11.8 Frontend `default*` constants (added 20 Sep)

`App.jsx` defines four per-family hardcoded fallbacks:

```jsx
const defaultNetDebt = isGreen ? "€58,500M" : isRates ? "€16,200M" : "€3,192M";
const defaultLiquidity = isGreen ? "€14,200M" : isRates ? "€7,800M" : "€1,008M";
const defaultRevenue = isGreen ? "€95,000M" : isRates ? "€65,000M" : "€28,300M";
const defaultEbitda = isGreen ? "€20,900M" : isRates ? "€14,300M" : "€6,226M";
```

These fire when the API response doesn't supply the corresponding field. `/api/opportunities` currently does **not** expose `revenue_str`, `ebitda_str`, or `liquidity_str` for the client card — so the pitchbook preview slide 4 reads the `default*` constants.

**For the current two clients the constants are coincidence-correct** — they match the DB values. But they are hardcodes: if the DB values change, the preview will not.

**Full fix (backlog):** extend `/api/opportunities` to expose the four fields (`revenue_str`, `ebitda_str`, `net_debt_str`, `liquidity_str`) and remove the `default*` constants. Requires adding `reported_revenue_eur_m` and `ebitda_eur_m` to the `fl` lateral join in `get_opportunities`. Read-path change only.

**Related dormant fallbacks:**

- `pitchbook_builder.py:1045` — hardcoded `'€65,000M'` / `'€14,300M'` fallback when `revenue_str` / `ebitda_str` resolve to `'N/A'`. Dormant now that the bundle returns populated values.
- `main.py:602` — hardcoded swap pre-hedge fallback string. Fires only when `current_action` is empty for a GREEN_ESG client. Does not fire for Enel (the curated narrative is populated).

### 11.9 `ca.ext_company_filings` multi-row hazard (added 20 Sep)

`ca.ext_company_filings` can contain multiple rows per client with identical `reporting_period` values. Observed for BASF: 5 rows, of which 4 had NULL `reported_revenue_eur_m` and `ebitda_eur_m`, and 1 had populated values.

**Failure mode:** reads that pick "the latest row" via `ORDER BY reporting_period DESC LIMIT 1` can land on a NULL row. The downstream code then silently falls through to `client_master` values, producing a display inconsistency between the preview and the generated deck.

Observed in the 19 Sep review: BASF's generated deck showed `€68,900M` revenue (from `client_master.revenue_eur_m`) while the preview showed `€65,000M` (from `defaultRevenue`). Both were "correct" for their source; neither was the reported filings value.

**Fix applied (20 Sep):** deleted 4 NULL-revenue duplicate rows for `CLI103`, leaving 1 populated row. Additionally, `fetch_pitchbook_bundle` now filters `AND reported_revenue_eur_m IS NOT NULL` so the query only picks populated rows.

**Root cause:** the ingestion pipeline writes duplicate rows to `ca.ext_company_filings` instead of upserting. Fixing the pipeline is a backlog item — until fixed, the pattern can recur.

**Durability:** `ca.ext_company_filings` is included in `baseline_snapshots.json`. Row-level cleanups to this table are overwritten by a reset — the snapshot holds whatever state existed when `dump_baseline.py` was last run. The 20 Sep cleanup was captured by re-dumping the snapshot (commit d5e33f1). After any future cleanup, re-run `dump_baseline.py` and commit.

### 11.10 `_FAMILY_KEYWORD_WEIGHTS` as a code-level curated exception (Flavor 2, added 20 Sep)

`_FAMILY_KEYWORD_WEIGHTS` is a weighted vocabulary for product family classification. Like `_CREDIT_RATINGS`, it is a code-level dict — not a DB column — because the schema change required to persist it is off the table (§7.2).

**Definition:** four families, ~20 keywords with weights 1–5. See §6.8 for the weights.

**Sync invariant:** the dict is defined in **both** `main.py` (near `_CREDIT_RATINGS`) and `pitchbook_builder.py` (near `_CREDIT_RATINGS`). The two must remain **byte-identical**.

- `main.py`'s copy is the canonical definition; it is not consumed by any code path in `main.py` today.
- `pitchbook_builder.py`'s copy is what `detect_product_family` reads.
- If they diverge, the "source of truth" and the "used" version disagree silently — a class of bug that the previous session's audit found repeatedly.

**Adding a family keyword requires editing both files.** Same discipline as `_CREDIT_RATINGS` (§11.7).

**Why this isn't a §11.7-style per-client exception:** the weights are a taxonomy definition, not per-client data. They scale to new clients without modification — the LLM classifies, the weights validate. The `_CREDIT_RATINGS` dict, by contrast, needs a new entry per client.

**Backlog:** as the platform accumulates classified anchors, the weights could be learned or refined statistically. For now, hand-curated is appropriate and defensible.

---

## 12. Cross-References to Other Documents

This document is one of a set. Related documents:

Sibling documents within the Flavor 2 documentation set
(`Docs/WeightedFamily/`):

| Document | Relationship |
|---|---|
| `Docs/WeightedFamily/MASTER_PERSONA_25Sep2026.md` | Current authoritative persona. Supersedes `master_persona_20Sep_WeightedFamily.md`. Covers three-brand toggle, `primary_trigger`, adjacent validator, and the deck cold-cache fallback. |
| `Docs/WeightedFamily/architecture_flow_20Sep_WeightedFamily.md` | Architecture reference. §5.5 (cache invariant), §5.6 (product family classification), §5.7 (adjacent opportunities), §6.3 (preview/PPTX parity), §6.5 (Slide 3 layout), §11 (principles) |
| `Docs/WeightedFamily/data_population_20Sep_WeightedFamily.md` | Field-by-field lineage of every UI element |

Common to both flavors (at `Docs/` root):

| Document | Relationship |
|---|---|
| `Docs/Architecture_Decision_Hybrid_vs_LLM_Only.md` | Decision record. §4.2 (reproducibility), §4.3 (auditability), §10 (20 Sep changelog) |
| `Docs/Context_Fabric_Integration_Production.md` | Webhook ingestion spec. Uses the same canonical client IDs and `WORKFABRIC_MEMO` channel |
| `Docs/Table_details.md` | Database schema catalog — companion reference |

Flavor 1 (Baseline) counterparts at `Docs/` root:

- `Docs/master_persona_20Sep.md` — persona for Flavor 1
- `Docs/architecture_flow_20Sep.md` — architecture reference for Flavor 1
- `Docs/data_population.md` — UI lineage for Flavor 1

---

## 13. Changelog — 20 Sep 2026 (Flavor 2 — Weighted-Family + Adjacencies)

Changes since the Flavor 1 (Baseline) version. Flavor 1 is documented separately at
`Docs/Data_or_Fabrication.md`.

**§2 Data flow diagram updated** — cache tuple 6-tuple → 8-tuple; JSON keys 5 → 7.

**§6.2 rewritten** — the synthesis prompt now returns seven keys. Adds `family` and
`adjacent_opportunities` to the description. Notes both travel via cache and API response
without DB persistence.

**§6.8 added** — "Product family as a synthesis output." The LLM's family proposal,
validated by `_FAMILY_KEYWORD_WEIGHTS` weighted scoring. Decision logic: decisive override
at score ≥ 5 and margin ≥ 3; else LLM trusted; else narrative keyword fallback. Observed
Enel (margin 10) and BASF (margin 3) classifications.

**§6.9 added** — "Adjacent opportunities as a synthesis output." The 80-140 word paragraph,
prompt rules, lifecycle, and non-determinism characteristics.

**§9 updated** — Copilot `slide_3` payloads carry `family` and `adjacent_opportunities`;
response architecture has a conditional fourth section; `json.dumps(..., ensure_ascii=False)`
for real `€`.

**§11.10 added** — `_FAMILY_KEYWORD_WEIGHTS` as a code-level curated exception. Sync
invariant between `main.py` and `pitchbook_builder.py`. Distinguished from per-client
exceptions like `_CREDIT_RATINGS`.

**§12 Cross-References updated** — points at the WeightedFamily sibling docs and the shared
root docs. Lists the Flavor 1 counterparts explicitly.

**What is common with Flavor 1 (unchanged):** data architecture, ingestion pipeline, DB
schema, reset-to-pristine mechanism, defensive fallbacks, `priority_score` semantics,
cache/DB consistency invariant, credit rating dict, demo narratives, compliance
architecture.

**Related commits:**

- `1a04960` — feature commit on `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3`
- `13721ca`, `9cfeb42`, `f9f8eeb` — the common-in-both commits from the 18-20 Sep session

**Backlog confirmed in this version:**

1. `COALESCE(priority_score, 75)` at `main.py:225, 727` (§6.7)
2. Frontend `default*` constants in `App.jsx` (§11.8)
3. `pitchbook_builder.py:1045` revenue/EBITDA fallback (§11.8)
4. `main.py:602` swap pre-hedge fallback (§11.8)
5. Ingestion pipeline duplicate-row write to `ca.ext_company_filings` (§11.9)
6. LLM `priority_score` non-determinism at `temperature=0.0` (§6.2)
7. Two `get_live_signals` definitions (§7.1)
8. Compliance regex pre-filter not wired (§10.3)
9. **Statistical refinement of `_FAMILY_KEYWORD_WEIGHTS`** (§11.10, Flavor 2) — as the platform accumulates classified anchors, learn or tune the weights

---

## 13b. Changelog — 22-25 Sep 2026 (state as of 25 Sep)

Sections §1–§13 above describe the platform as of 20 Sep 2026. Since then, four waves of change:

### 22 Sep 2026 — Synthesis + cache

- **`primary_trigger`** added as the 8th synthesis key (commit `3b99c3c`). Deterministic five-rule validator, curated fallback chain. See new §6.10.
- **Cache TTL extended** from 300s to 900s (commit `d41a837`). RM workflow no longer risks cache expiry mid-session.
- **Cache invalidation on ingestion** — `_MANDATE_SYNTH_CACHE.pop(cid, None)` after every successful ingestion commit (`d41a837`).
- **Ingestion source names client-scoped** — three Enel-era fallbacks replaced (`ce85f57`).
- **Layer-1 dedup condition corrected** — OR → AND (`ce85f57`).
- **`why_now` extended to 3 sentences** (`16890f7`).

### 23 Sep 2026 — Acme + adjacent validator

- **`ADJACENT_OPPORTUNITY_FALLBACKS`** dict + `_validate_adjacent_opportunities()` + `_resolve_adjacent_opportunities()` (commit `79cf56e`). The API path now substitutes a curated paragraph on empty LLM output. Cache tuple grew to 10 elements with `adjacent_opportunities_source`. See updated §6.9.
- **`_client_id_for_fallback` bug fixed** — was `str(client_name)` (display name), so the per-client branch of `PRIMARY_TRIGGER_FALLBACKS` never fired. Now uses `client_id` (folded into `79cf56e`).
- **Acme Financial** added as third runtime brand (commit `7590d23`). Data-only change: +29 lines in `main.py`, 4 PNGs. Three Cloud Run services now serve ING / BFS AI Lab / Acme Financial from the same image. See `Brand_Toggle_Implementation.md` §11.

### 25 Sep 2026 — Deck cold-cache adjacent fallback

- **`pitchbook_builder.py`** deck builder now uses the same curated fallback chain as the API when `ctx["adjacent_opportunities"]` is empty (commit `d7c17d8`). Observed in a live demo: cold cache + deck download without prior dashboard load → placeholder rendered. The fix eliminates the placeholder path. Verified on all three services. See updated §6.9.
- **`primary_trigger` cold-cache audit** — confirmed no equivalent gap. Deck reads `ctx["trigger_source"]` (curated DB value) as tier 3. See §6.10.

### Common with the 20 Sep state

Everything else: schema (unchanged), reset-to-pristine mechanism (unchanged), defensive fallbacks (unchanged except the deck builder addition), compliance architecture (unchanged), `priority_score` semantics (unchanged), the `_CREDIT_RATINGS` and `_FAMILY_KEYWORD_WEIGHTS` sync invariants (unchanged).

**Backlog carried forward and new items:**

- All items 1–9 from §13 (unchanged)
- **Brand onboarding utility** — `tools/onboard_brand.py`, guide at `BRAND_ONBOARDING_GUIDE.md`
- **Migration tooling** — `load_baseline.py`, `schema_setup.sql` (aligned with live DB)
- **Corporate migration in flight** — Service Now ticket pending, company project provisioning in progress

---

## 13a. Changelog — 20 Sep 2026 (Flavor 1 — Baseline)

Changes since the 17 Sep 2026 version. Corrections reflect the 19-20 Sep session, which
changed the `priority_score` lifecycle and added two code-level curated exceptions.

### Corrected

- **§6.2 rewritten.** The 17 Sep version stated `priority_score` was a "legacy frozen value" that would not change. That is false after commit `13721ca` (18 Sep). The synthesis prompt now returns `priority_score` as a fifth key with an explicit weighted rubric, and the value is written back on every synthesis cache miss. Non-determinism at `temperature=0.0` documented (observed 85-94 for `CLI101` in one session).
- **§6.3 updated.** The `_effective_score` preference chain (fresh synthesis over DB value) is now documented. Line numbers corrected to `main.py:812–814`.
- **§6.7 line numbers corrected.** Was `main.py:214` / `main.py:666`; now `main.py:225` / `main.py:727`. Whitelist-guarantee mitigation from `13721ca` documented.
- **§3 UI table refreshed.** "This Week" tiles re-sourced with the four new metrics (`clients_with_signals`, `active_signals`, `high_priority_clients`, `clients_in_database`). Client Data segment notes the `credit_rating` code-level source.
- **§4.1 `ca.client_master`** — noted no `credit_rating` column, cross-referenced to §11.7.
- **§4.1 `ca.ext_company_filings`** — added multi-row hazard note, cross-referenced to §11.9.
- **§4.1 `ca.ca_opportunity_scoring`** — `priority_score` description updated ("recomputed on every synthesis run").
- **§4.1 `ca.debt_maturity_schedule`** — noted it feeds slide 5/10 tranche ladder.
- **§4.3** — whitelist state updated (two clients), Enel-primary framing.
- **§5.1** — added canonical-vs-legacy channel guidance for webhook integrations.
- **§8.2 and §8.4 (17 Sep change)** — the 17 Sep version stated `ca.ext_company_filings` was not in the snapshot and cleanups were durable across reset. This was corrected on 20 Sep (see the next entry).
- **§9** — added 20 Sep update on the Copilot's `db_wall_str` and rating sources.
- **§8.2, §8.4, §11.9 corrected (20 Sep, second pass).** The prior version stated `ca.ext_company_filings` was not in `baseline_snapshots.json` and that cleanups to it were durable across reset. Both statements were wrong — the table is in the snapshot, and the snapshot was re-dumped after the BASF NULL-row cleanup to capture the corrected state (`commit d5e33f1`).

### Added

- **§6.2 non-determinism table** — five observed values for `CLI101`.
- **§7.6 Synthesis fallback path** — the deterministic fallback when the LLM call throws.
- **§11.1** — the two-maturity-sources table now includes BASF alongside Enel, with the definitional difference noted.
- **§11.7 Credit rating as a code-level dict** — the `_CREDIT_RATINGS` mechanism, why a dict, sync invariant.
- **§11.8 Frontend `default*` constants** — the four per-family fallbacks, the full fix path, related dormant fallbacks.
- **§11.9 `ca.ext_company_filings` multi-row hazard** — the observed failure mode, the 20 Sep cleanup, root cause, durability.
- **§12 Cross-References** — a table linking this doc to the other five in the set.
- **§13 Changelog** — this section.

### Related commits

- `13721ca` — LLM-computed `priority_score` with weighted rubric + whitelist guarantee
- `9cfeb42` — cache populated only after successful DB commit
- `f9f8eeb` — THIS WEEK tiles + client display fabrication fixes
- `1c1657b`, `b061c14` — persona 20Sep added and personas consolidated
- `c33c573` — architecture_flow_20Sep
- `bd23131` — decision record amended
- `16e1465` — Context Fabric spec updated

### Backlog confirmed in this version

1. `COALESCE(priority_score, 75)` at `main.py:225, 727` (§6.7)
2. Frontend `default*` constants in `App.jsx` (§11.8)
3. `pitchbook_builder.py:1045` revenue/EBITDA fallback (§11.8)
4. `main.py:602` swap pre-hedge fallback (§11.8)
5. Ingestion pipeline duplicate-row write to `ca.ext_company_filings` (§11.9)
6. LLM `priority_score` non-determinism at `temperature=0.0` (§6.2)
7. Two `get_live_signals` definitions (§7.1)
8. Compliance regex pre-filter not wired (§10.3)

---

*End of document.*