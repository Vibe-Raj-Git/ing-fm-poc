Here is the full updated document. Save it as `Docs/Data_or_Fabrication.md`, replacing the current version.

---

# Data Integrity, Dynamic State Lineage & Zero-Fabrication Architecture

**Version:** 17 September 2026
**Status:** Authoritative
**Supersedes:** `Data_or_Fabrication.md` (14 Sep 2026)
**Audience:** Engineers, Business Analysts, Model Risk, Compliance

---

## 1. Executive Summary

The ING Financial Markets Deal Intelligence Platform is built on a **Zero-Fabrication Architecture**. Every value displayed to the Relationship Manager — balance sheet metrics, debt tranches, market rates, credit spreads, signal extractions, opportunity narratives — traces to a specific row in a specific PostgreSQL table, filtered by `client_id`.

No literal client values exist in the presentation layer. No hardcoded fee pools. No invented deal sizes. Where the platform displays a number or a claim, that number or claim has a source.

This document describes the actual pipeline as implemented, including the reset-to-pristine mechanism that lets a demo environment be restored to a curated baseline on demand without destroying user-ingested content. Where an earlier version of this doc described aspirational features (a composite scoring formula, a two-model LLM architecture), those sections have been corrected or removed. A summary of what changed is in §12.

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
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  SYNTHESIS (Read-time, whitelisted clients only)                                         │
│  • Read anchor from ca.ca_opportunity_scoring                                            │
│  • Check TTL cache (300s, keyed by client_id)                                            │
│  • On cache miss and client in _DEMO_CLIENT_IDS:                                         │
│      – Fetch 20 most recent signals                                                      │
│      – Call gemini-2.5-flash with the anchor first                                       │
│      – Apply drift guard                                                                 │
│      – Write to cache and back to ca.ca_opportunity_scoring                              │
│  • On cache hit or non-whitelisted client: use DB row directly                           │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  RENDERING                                                                               │
│  • React preview canvas                                                                  │
│  • python-pptx export                                                                    │
│  • Both consume the same deckOverrides payload                                           │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Every arrow in this diagram maps to a specific function in `main.py` and a specific table or model in the data tier.

The **reset-to-pristine** mechanism (§8) is a separate, non-destructive path that restores curated baseline content from `baseline_snapshots.json`. It does not remove user-ingested rows; it refreshes the pristine rows' timestamps so they win the `created_at DESC` sort.

---

## 3. UI Section → API → Table Mapping

Every visual element on the dashboard sources from live tables. Nothing is hardcoded.

| UI Section | API Endpoint | Tables Read | Channel Filters |
|---|---|---|---|
| **This Week** metrics strip | `GET /api/metrics` | `ca.digital_twin_signals`, `ca.ca_opportunity_scoring`, `ca.client_master` | — |
| **Live Signal Feed** marquee | `GET /api/signals` | `ca.digital_twin_signals`, `ca.client_master` | Filtered to `_DEMO_CLIENT_IDS` |
| **Priority Today** sidebar | `GET /api/metrics` (priorities field) | `ca.ca_opportunity_scoring`, `ca.client_master` | — |
| **Client Data** segment | `GET /api/opportunities` | `ca.client_master`, `ca.ext_company_filings`, `ca.coverage_teams` | — |
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

**Two important multi-channel details:**

1. **Context Fabric chips accept five channel names.** `ANALYST_NOTE`, `CONTEXT_FABRIC`, and `MEMO` are standardized to `WORKFABRIC_MEMO` at display time. This means the analyst note channel merges into the WorkFabric chip rather than producing a separate chip.
2. **Live Verified News accepts four channel aliases.** `NEWS_RSS`, `LIVE_RSS_NEWS`, `LIVE RSS News`, and `News RSS` are all queried, sorted together by `created_at DESC, chunk_id DESC`. The current ingestion pipeline writes `LIVE_RSS_NEWS`; the other three are legacy aliases retained for compatibility.

---

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
| `priority_score` | integer | Displayed as `<Label> · <Score>`. See §6. |
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

- **CLI101 (Enel)** — carries the original curated demo content (42 signals, ~13 chunks)
- **CLI103 (BASF)** — carries the newer curated demo content plus user-ingestion test content

The remaining 11 clients have baseline data in `client_master`, `ext_company_filings`, `ca_opportunity_scoring`, and `debt_maturity_schedule` (for a subset), but minimal signal and chunk history. This is intentional — the demo whitelists one client at a time via `_DEMO_CLIENT_IDS` and `ACTIVE_UI_CLIENT_IDS`.

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

---

## 6. Priority Score — What It Actually Is

### 6.1 Not a formula

An earlier version of this document described a four-factor weighted composite score:

```
Priority Score = w_mat · S_mat + w_curve · S_curve + w_lev · S_lev + w_sig · S_sig
```

**That formula does not exist in the code.** It was documented aspirationally but never implemented. A code search for the weights (0.35, 0.25, 0.20, 0.20) returns nothing.

### 6.2 What the score actually is

`ca.ca_opportunity_scoring.priority_score` is a **single LLM-derived estimate**, produced during ingestion. When the ingestion extraction ran under an earlier prompt schema, Gemini included a `priority_score` value in its structured output. That value was written to the row.

**Current state:** the ingestion pipeline was refactored on 14 Sep 2026 to extract `detected_signals[]` arrays. The new prompt schema no longer includes `priority_score`. That means the score in the DB is now a **legacy value** from the last time the old single-signal pipeline ran.

For Enel, `priority_score = 94`. For BASF, `priority_score = 94`. These values will not change until either:

- The score is manually set, or
- A future scoring mechanism is introduced

### 6.3 Threshold classification

The card label is derived from `priority_score` by a fixed rule in `/api/opportunities`:

```python
score_level = "High" if int(score_num) >= 85 else ("Medium" if int(score_num) >= 70 else "Low")
score_val = f"{score_level} · {score_num}"
```

| Score range | Label |
|---|---|
| ≥ 85 | High |
| 70 – 84 | Medium |
| < 70 | Low |

### 6.4 The other two scores

`ca.ca_opportunity_scoring` also has `propensity_score` and `value_score` columns. Both are LLM outputs from earlier ingestion runs.

- `propensity_score` is read by `pitchbook_builder.py` as an **ORDER BY tiebreaker** in `fetch_pitchbook_bundle` (lines 307, 365). It does not affect the display value, but it does determine which row resolves when a client has multiple scoring rows.
- `value_score` is not read by any current code path.

### 6.5 Display provenance

The card shows a tooltip on hover:

> *LLM-generated priority estimate (0–100). High ≥ 85 · Medium 70–84 · Low < 70.*

This is honest — it states the score is an LLM estimate, not a computed metric.

### 6.6 What the score is NOT

- Not a compliance score
- Not a risk score
- Not derived from a formula
- Not updated per request
- Not the sum of weighted dimensions

### 6.7 Known open item — `COALESCE(priority_score, 75)` fallback

Two live read sites substitute a fabricated score when the DB has no value:

- `main.py:214` — `/api/metrics` priorities query
- `main.py:666` — `/api/opportunities` client rows

Both use the pattern `COALESCE(priority_score, 75)`. This **violates the zero-fabrication principle** stated in §1. A client with no scoring row would be displayed with a fake score of 75, which would then be classified as "Medium" by the §6.3 threshold rule.

**Currently dormant:** all 13 clients in the DB have a scoring row, so the fallback never fires.

**Recommended fix (backlog):** replace `COALESCE(priority_score, 75)` with a null-preserving read, filter out unscored clients from the rank table, or render them with an explicit "Unscored" label. The design decision (filter vs. display) should be made before implementation. This is a read-path change only — no schema change required.

---

## 7. Defensive Fallback Architecture

### 7.1 Where fallbacks live

`main.py` contains two `def get_live_signals()` definitions. The first is the live one — it is bound to the FastAPI route via `@app.get("/api/signals")` at decoration time. The second is dead code: Python rebinds the module-level name on load, but the route table already holds a reference to the first function object.

**Which one is live, precisely:**

- **First definition** (whichever line number it currently sits at) — carries `_DEMO_CLIENT_IDS` filter, client-name normalization, `LIMIT 40` SQL, `[:12]` Python slice, `(client_name, headline)` dedup
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

`/api/rss/feed` returns two synthetic articles per client when Google News returns no rows (see `main.py:~1248` for the BASF branch, and the analogous Enel branch above it). These articles are returned to the Ingestion Engine modal only. They are **never persisted** to the DB and **never surface** on the opportunity card.

The purpose is graceful degradation: the modal has something to show rather than an empty list. This is not a zero-fabrication concern because these articles never become display data — they are inputs the user may choose to ingest. If ingested, the regular pipeline processes them, and any resulting signals or chunks are subject to the normal dedup and validation guards.

**Caveat:** the synthetic articles look identical to real ones. There is no visual marker distinguishing a synthetic fallback article from a real Google News result. A future improvement would be to label fallback articles in the modal UI (e.g., "[Sample] ..."), but this is not a correctness issue.

---

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

**Analogous convention for signals:** curated signals should use IDs in the form `SIG_BASF_*` (or client-specific prefixes) so they are visibly distinguishable from ingestion-generated `SIG-<uuid>` IDs.

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

---

## 11. Known Data Inconsistencies

### 11.1 Two maturity sources for the same client

| Source | Value (Enel) | Meaning |
|---|---|---|
| `ca.ext_company_filings.debt_maturing_24m_eur_m` | €10,127M | Balance-sheet reported 24-month maturity wall |
| `ca.debt_maturity_schedule` (2026-2027) | €7,100M | Itemized instruments maturing in 2026 or 2027 |

These are not the same thing:

- The balance-sheet figure is what the pitchbook references as "24-month maturity wall" (headline statements)
- The schedule is what appears in slide 5's per-tranche ladder (line-item breakdowns)

Both are accurate for their own definition. The gap (€3.03bn for Enel) is a definitional difference, not a bug.

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

---

## 12. Changelog — 17 Sep 2026

Changes since the 14 Sep 2026 version:

- **Reset-to-pristine mechanism documented (§8).** New top-level section covering the endpoint, the `baseline_snapshots.json` snapshot, the `chunk_id >= 9000000` convention, and the effect on the UI. Previously absent.
- **Two live read sites with `COALESCE(priority_score, 75)` fallbacks flagged (§6.7).** Dormant but a violation of the zero-fabrication principle. Backlog item.
- **`propensity_score` read at `pitchbook_builder.py:307, 365`** — corrected from "not read by any current code path" to "used as ORDER BY tiebreaker in the pitchbook bundle read."
- **Primary-key absence on `debt_maturity_schedule` and `coverage_teams` documented (§11.4).** Explains the reset endpoint's delete-by-client pattern for those tables.
- **Client ID distribution (§4.3) reframed.** Specific counts removed in favor of a pattern statement, since counts drift with each ingestion.
- **Channel classification (§5.1) expanded.** Historical channel aliases documented. Read paths now explicitly noted as querying a superset of the current pipeline's output.
- **Multi-channel reads in §3 updated.** Context Fabric chips and Live Verified News now show their full channel `IN` lists.
- **RSS synthetic fallback documented (§7.5).** Notes that `/api/rss/feed` returns synthetic articles when Google News fails, and that these are never persisted or surfaced on the opportunity card.
- **Dedup layered into two guards (§5.4).** Signal-level `(client_id, trigger_summary)` and chunk-level semantic. The semantic guard is channel-scoped.
- **`metric_value` contract documented (§8.5).** For `BOARD_AUTHORIZATION` signals, the value must be a bare number; the read path appends `" financing capacity"` at display time.
- **`ca.ext_deals` promoted to §4.4** with its schema.
- **Section numbers shifted.** The 14 Sep version's §8 Copilot State Grounding, §9 Compliance, and §10 Known Data Inconsistencies are now §9, §10, §11 respectively.

---

*End of document.*

---

## Where To Save It

```bash
cd ~/ing-fm-poc

# Back up the current version
cp Docs/Data_or_Fabrication.md Docs/Data_or_Fabrication.md.bak.$(date +%s)

# Save the new content as Docs/Data_or_Fabrication.md
```

## Verification After Saving

```bash
cd ~/ing-fm-poc

echo "=== Verify header and key sections ==="
grep -n "^# \|^## " Docs/Data_or_Fabrication.md | head -30

echo ""
echo "=== Verify the new §8 is present ==="
grep -c "Reset-to-Pristine Baseline" Docs/Data_or_Fabrication.md

echo ""
echo "=== Verify §6.7 is present ==="
grep -c "Known open item" Docs/Data_or_Fabrication.md

echo ""
echo "=== Verify changelog mentions 17 Sep ==="
grep -c "17 Sep 2026" Docs/Data_or_Fabrication.md
```

Expected:

- Header shows the new §8, §9, §10, §11, §12 numbering
- "Reset-to-Pristine Baseline" appears **≥ 1** time
- "Known open item" appears **≥ 1** time
- "17 Sep 2026" appears **≥ 1** time

## What's Next

After this doc lands, the remaining documentation work:

1. **`Reset_Baseline.md`** — I'd argue this is now optional given the depth of §8. Unless you want a standalone spec, the coverage in `Data_or_Fabrication.md` should suffice.
2. **`data_population.md`** — update §2.4 for the four-channel news read.
3. **`Table_details.md`** — add the `chunk_id >= 9000000` convention and PK-absence notes.
4. **`Ranks.md`** — still a transcript; needs a rewrite.

Say the word on which one next.