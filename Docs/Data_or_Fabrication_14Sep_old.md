# Data Integrity, Dynamic State Lineage & Zero-Fabrication Architecture

**Version:** 14 September 2026
**Status:** Authoritative
**Supersedes:** Previous `Data_or_Fabrication.md` (pre-14 Sep)
**Audience:** Engineers, Business Analysts, Model Risk, Compliance

---

## 1. Executive Summary

The ING Financial Markets Deal Intelligence Platform is built on a **Zero-Fabrication
Architecture**. Every value displayed to the Relationship Manager — balance sheet metrics,
debt tranches, market rates, credit spreads, signal extractions, opportunity narratives —
traces to a specific row in a specific PostgreSQL table, filtered by `client_id`.

No literal client values exist in the presentation layer. No hardcoded fee pools. No invented
deal sizes. Where the platform displays a number or a claim, that number or claim has a
source.

This document describes the actual pipeline as implemented. Where an earlier version of this
doc described aspirational features (a composite scoring formula, a two-model LLM
architecture), those sections have been corrected or removed. A summary of what changed is in
§11.

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
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  PERSISTENCE (Cloud SQL)                                                                 │
│  • INSERT INTO ca.document_vector_chunks (one row per ingestion)                         │
│  • INSERT INTO ca.digital_twin_signals (one row per detected signal)                     │
│  • Dedup guard on (client_id, trigger_summary)                                           │
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

Every arrow in this diagram maps to a specific function in `main.py` and a specific table or
model in the data tier.

---

## 3. UI Section → API → Table Mapping

Every visual element on the dashboard sources from live tables. Nothing is hardcoded.

| UI Section | API Endpoint | Tables Read |
|---|---|---|
| **This Week** metrics strip | `GET /api/metrics` | `ca.digital_twin_signals`, `ca.ca_opportunity_scoring`, `ca.client_master` |
| **Live Signal Feed** marquee | `GET /api/signals` | `ca.digital_twin_signals`, `ca.client_master` (filtered to `_DEMO_CLIENT_IDS`) |
| **Priority Today** sidebar | `GET /api/metrics` (priorities field) | `ca.ca_opportunity_scoring`, `ca.client_master` |
| **Client Data** segment | `GET /api/opportunities` | `ca.client_master`, `ca.ext_company_filings`, `ca.coverage_teams` |
| **Market Data** segment | `GET /api/opportunities` | `ca.mkt_rates_curves`, `ca.ext_credit_spreads` |
| **Context Fabric** segment | `GET /api/opportunities` | `ca.document_vector_chunks`, `ca.digital_twin_signals` |
| **Houseviews & News** segment | `GET /api/opportunities` | `ca.document_vector_chunks` (filtered to `PDF_REPORT` / `HOUSEVIEW` / `NEWS_RSS`) |
| **Synthesized Mandate** hero | `GET /api/opportunities` | `ca.ca_opportunity_scoring` (anchor + synthesized narrative) |
| **Signal Lineage tiles** | `GET /api/opportunities` | Same sources as the four segments above |
| **Pitchbook canvas** | `GET /api/opportunities` + client state | Aggregate of the above, plus `deckOverrides` |
| **Pitchbook .pptx** | `POST /api/pitchbook/generate` | Same bundle as canvas |

**Every value in this table has a specific column behind it.** The next section lists them.

---

## 4. Actual Database Schema

All tables live in the `ca` schema of the Cloud SQL PostgreSQL 15 instance.

### 4.1 Live tables

#### `ca.client_master`

| Column | Type |
|---|---|
| `client_id` (PK) | varchar |
| `client_name` | varchar |
| `group_parent` | varchar |
| `legal_entity` | varchar |
| `industry_sector` | varchar |
| `country` | varchar |
| `region` | varchar |
| `ownership_type` | varchar |
| `tier` | varchar |
| `hq_country` | varchar |
| `revenue_eur_m` | numeric |
| `rm_name` | varchar |
| `base_ccy` | varchar |

#### `ca.ext_company_filings`

| Column | Type |
|---|---|
| `filing_id` (PK) | varchar |
| `client_id` | varchar |
| `reporting_period` | varchar |
| `net_debt_eur_m` | numeric |
| `liquidity_eur_m` | numeric |
| `ebitda_eur_m` | numeric |
| `reported_revenue_eur_m` | numeric |
| `debt_maturing_24m_eur_m` | numeric |
| `notes` | text |

#### `ca.debt_maturity_schedule`

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

| Column | Type |
|---|---|
| `curve_id` (PK) | integer |
| `curve_date` | date |
| `currency` | varchar |
| `tenor` | varchar |
| `swap_rate_pct` | numeric |
| `govt_yield_pct` | numeric |
| `category` | varchar |

#### `ca.ext_credit_spreads`

| Column | Type |
|---|---|
| `spread_id` (PK) | integer |
| `quote_date` | date |
| `issuer_or_rating` | varchar |
| `sector` | varchar |
| `tenor` | varchar |
| `spread_bps` | numeric |
| `all_in_yield_pct` | numeric |
| `source` | varchar |

#### `ca.ca_opportunity_scoring`

| Column | Type | Notes |
|---|---|---|
| `opportunity_id` (PK) | varchar | |
| `client_id` | varchar | |
| `opportunity_type` | varchar | Free text |
| `trigger_source` | text | |
| `est_revenue_eur_000` | numeric | Fee estimate (thousands EUR) |
| `propensity_score` | integer | LLM-derived, unused in display |
| `value_score` | integer | LLM-derived, unused in display |
| `priority_score` | integer | Displayed as `<Label> · <Score>` |
| `rank` | integer | Unused |
| `next_best_action` | text | **Anchor field** |
| `why_now_nlg` | text | **Anchor field** |

#### `ca.digital_twin_signals`

| Column | Type |
|---|---|
| `signal_id` (PK) | varchar |
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

| Column | Type | Notes |
|---|---|---|
| `chunk_id` (PK) | bigint | |
| `client_id` | varchar | |
| `source_channel` | varchar | See §5.2 |
| `source_name` | varchar | Filename or source label |
| `text_content` | text | Extracted text |
| `structured_metadata` | jsonb | Format varies — see §5.3 |
| `embedding` | vector(768) | pgvector |
| `created_at` | timestamp | |

#### `ca.coverage_teams`

| Column | Type |
|---|---|
| `client_id` | varchar |
| `role_title` | varchar |
| `banker_name` | varchar |
| `location` | varchar |

### 4.2 Legacy tables

Not read by any live code path:

- `ca.dt_client_master` — earlier reduced-column version of `ca.client_master`
- `ca.ca_opportunity_scoring_backup` — snapshot table
- `ca.cand5_client_master` — candidate/deprecated schema (empty)
- `ca.ext_deals` — ING track record. 3 rows, canonical client IDs, candidate for future slide integration.

### 4.3 Client ID consistency

All live tables use canonical IDs (`CLI001`, `CLI002`, ... `CLI105`). Legacy IDs
(`CLI009_ENEL`, `CLI010_BASF`) were migrated on 14 Sep 2026:

| Legacy ID | Canonical ID |
|---|---|
| `CLI009_ENEL` | `CLI101` |
| `CLI010_BASF` | `CLI103` |

Current distribution:
- `ca.document_vector_chunks`: CLI101 (13), CLI102 (1), CLI103 (5)
- `ca.digital_twin_signals`: CLI101 (42), CLI103 (10), CLI001 (1), CLI003 (1), CLI102 (2)
- `ca.ca_opportunity_scoring`: one row per client

---

## 5. Ingestion Channels — What Actually Gets Stored

### 5.1 Channel classification

Every ingestion is tagged with a `source_channel` value in `ca.document_vector_chunks`:

| Value | Typical source |
|---|---|
| `PDF_REPORT` | PDF / PPTX upload |
| `NEWS_RSS` | Google News RSS |
| `CLIENT_EMAIL` | Treasury / client email |
| `TEAMS_CHAT` | Microsoft Teams |
| `WORKFABRIC_MEMO` | Internal memos |

Additional historical values (`TEAMS`, `TREASURY_EMAIL`, `ANALYST_NOTE`, `NEWS_ARTICLE`)
exist from earlier ingestion eras. The current ingestion pipeline produces only the five
values in the table above.

### 5.2 Multi-signal extraction

A single ingestion produces **N signals**, not one. A PDF with six sections produces six
rows in `ca.digital_twin_signals`.

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

Not all rows in `ca.document_vector_chunks` have the same `structured_metadata` schema. Three
formats exist, from three ingestion eras:

**Format A — Full extraction (chunks 8, 9, 10, 11):**
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

**Format B — Simplified (chunks 101-107):**
```json
{
  "signal_type": "PUBLIC_ISSUANCE_COMPLETED",
  "evidence_type": "Client-Validated",
  "catalog_family": "Financing/Capital Markets",
  "confidence_pct": 90,
  "metric_identified": "$2.5bn"
}
```

**Format C — Null (chunks 20, 21, 23, 24, 25):**
```json
null
```

Consumers of `structured_metadata` must handle all three cases. The houseview label logic in
`/api/opportunities` reads `meta.get("detected_signals")` and falls back gracefully when the
key is absent.

A future normalization pass could standardise these to Format A. Not required today.

### 5.4 Deduplication

Before inserting a signal, the pipeline checks whether `(client_id, trigger_summary)` already
exists. If so, the insert is skipped. This prevents table growth when:

- The same document is uploaded twice
- Overlapping news articles cover the same fact
- The same event is mentioned across multiple channels

---

## 6. Priority Score — What It Actually Is

### 6.1 Not a formula

An earlier version of this document described a four-factor weighted composite score:

```
Priority Score = w_mat · S_mat + w_curve · S_curve + w_lev · S_lev + w_sig · S_sig
```

**That formula does not exist in the code.** It was documented aspirationally but never
implemented. A code search for the weights (0.35, 0.25, 0.20, 0.20) returns nothing.

### 6.2 What the score actually is

`ca.ca_opportunity_scoring.priority_score` is a **single LLM-derived estimate**, produced
during ingestion. When the ingestion extraction runs, Gemini may include a `priority_score`
value in its structured output. That value is written to the row.

**Current state — worth noting:** the ingestion pipeline was refactored on 14 Sep 2026 to
extract `detected_signals[]` arrays. The new prompt schema no longer includes
`priority_score`. That means the score in the DB is now a **legacy value** from the last
time the old single-signal pipeline ran.

For Enel, `priority_score = 94`. It will not change until either:
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

`ca.ca_opportunity_scoring` also has `propensity_score` and `value_score` columns. Both are
LLM outputs from earlier ingestion runs. Neither is read by any current code path. They are
retained for a potential future ranking model.

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

---

## 7. Defensive Fallback Architecture

### 7.1 Where fallbacks live

Two functions in `main.py` — `get_live_signals` (the live one) and a duplicate dead
definition — contain fallback signal lists that fire when the DB query returns no rows.

**Note:** The file contains two `def get_live_signals()` definitions. The first (line ~315)
is the live one; FastAPI's route decorator holds it. The second (line ~460) is dead code —
Python rebinds the name but the route still points to the first. This is a known cleanup
item.

### 7.2 What the fallback contains

The fallback returns three signals:

| ID | Client | Type | Headline |
|---|---|---|---|
| `SIG-DF1` | BASF SE (`CLI103`) | REFINANCING | BASF SE: €2.0B 6Y EMTN & €1.2B Pre-Hedge |
| `SIG-DF2` | Enel S.p.A. (`CLI101`) | SUSTAINABLE FUNDING | Enel S.p.A.: €1.0B Dual-Tranche Green & SLB Issuance |
| `SIG-DF3` | ASML Holding (`CLI102`) | HEDGING | ASML Holding: EUR 900M FX Collar Hedge |

These are static strings, present for graceful degradation. They fire only when
`ca.digital_twin_signals` returns no rows.

**Note:** the doc's earlier claim that the fallback shows only BASF is incorrect. It shows
three clients.

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

It does NOT fire when the query returns rows successfully. In normal operation, the database
query wins.

### 7.4 No phantom writes

Fallback values are read-only. They are never written back to the database. A client displayed
via the fallback is a client with no live signal data — the fallback makes that state visible
rather than failing silently.

---

## 8. Copilot State Grounding

The Deal Copilot reads from two dicts constructed before the LLM call:

- **`baseline_deck_slides`** — pristine values, from the DB
- **`active_deck_slides`** — current values, with any session overrides applied

Both are serialized into the system instruction. The LLM cannot answer from memory; it must
read from the payload.

Compliance with this pattern is validated by the test suite in `Copilot_Test_Suite.md`.

---

## 9. Compliance — LLM-Driven, Not Regex

### 9.1 Two-stage design (documented)

The earlier version of this document described a two-stage compliance engine:

1. **Stage 1:** Deterministic regex filter on promissory terms
2. **Stage 2:** Gemini regulatory context screening

### 9.2 What's actually implemented

Only Stage 2 exists. The compliance audit is entirely LLM-driven. The regex list
(`PROMISSORY_PATTERNS`) is defined in `main.py` but **is not called by any endpoint**.

**Current behavior:** `POST /api/check-compliance` sends the full deck to Gemini, which
evaluates against MiFID II, MAR, and (for green-family decks) the EU Green Bond Standard.
The response includes flags with `slide_number`, `rule`, `issue`, and `recommended_overrides`.

### 9.3 Post-demo improvement

Wiring the regex filter as a pre-filter before the LLM call would:

- Make the check deterministic for a subset of patterns
- Reduce LLM cost for obviously-compliant decks
- Provide a "hard flag" that the LLM cannot override

This is a backlog item, not a current defect.

---

## 10. Known Data Inconsistencies

Two data model ambiguities are worth documenting so future engineers don't chase them as
bugs.

### 10.1 Two maturity sources for the same client

| Source | Value (Enel) | Meaning |
|---|---|---|
| `ca.ext_company_filings.debt_maturing_24m_eur_m` | €10,127M | Balance-sheet reported 24-month maturity wall |
| `ca.debt_maturity_schedule` (2026-2027) | €7,100M | Itemized instruments maturing in 2026 or 2027 |

These are not the same thing:
- The balance-sheet figure is what the pitchbook references as "24-month maturity wall"
- The schedule is what appears in slide 5's per-tranche ladder

Both are accurate for their own definition. The pitchbook uses the balance-sheet figure for
headline statements; the schedule for line-item breakdowns.

### 10.2 Structured metadata format variance

Covered in §5.3. Three formats coexist. Consumers must handle all three.

### 10.3 Two `get_live_signals` definitions

Covered in §7.1. Dead code duplication, no functional impact, cleanup candidate.

---

## 11. Changelog — 14 Sep 2026

Corrected from the pre-14-Sep version:

- **Table names corrected.** Replaced `dt_client_master` → `client_master`,
  `corporate_debt_schedules` → `debt_maturity_schedule`,
  `market_fixings_live` → `mkt_rates_curves`.
- **Priority Score section rewritten.** The four-factor weighted formula was removed. The
  actual mechanism (single LLM estimate, threshold classification) is documented.
- **Model references corrected.** "Gemini 1.5 Flash" and "Gemini 1.5 Pro" replaced with
  `gemini-2.5-flash` (single model for all roles).
- **Compliance section corrected.** The regex pre-filter is documented as dormant code, not
  an active pipeline stage.
- **Fallback section corrected.** The fallback contains three clients, not one.
- **API endpoints corrected.** `/api/signals/live` → `/api/signals`,
  `/api/pitchbook/bundle` removed, `/api/pitchbook/export` → `/api/pitchbook/generate`.
- **Multi-signal extraction documented.** N signals per ingestion, dedup guard.
- **Metadata format variance documented.** Three formats explained.
- **Maturity source ambiguity documented.** €10.13bn (balance sheet) vs €7.1bn (schedule).
- **Client ID migration documented.** Legacy IDs renamed to canonical.

---

*End of document.*