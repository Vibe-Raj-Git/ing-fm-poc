# Database Table Directory

**Version:** 14 September 2026
**Status:** Authoritative
**Supersedes:** Previous `Table_details.md` (pre-14 Sep)
**Audience:** Engineers, Business Analysts

---

## 1. Overview

All tables live in the `ca` schema of the Cloud SQL PostgreSQL 15 instance. The schema
contains **12 tables**, structured across four functional layers:

| Layer | Tables | Purpose |
|---|---|---|
| Core entity & coverage | `client_master`, `coverage_teams`, `dt_client_master`, `cand5_client_master` | Client identity, coverage teams, legacy variants |
| Financial fundamentals & liabilities | `ext_company_filings`, `debt_maturity_schedule` | Balance sheet, debt tranches |
| Market intelligence & deal history | `mkt_rates_curves`, `ext_credit_spreads`, `ext_deals` | Curves, spreads, ING track record |
| Intelligence & vector RAG | `ca_opportunity_scoring`, `digital_twin_signals`, `document_vector_chunks` | Scoring, signals, embeddings |

**Row counts** as of the last audit:

| Table | Rows |
|---|---|
| `ca.client_master` | 13 |
| `ca.ext_company_filings` | 13 |
| `ca.debt_maturity_schedule` | 15 |
| `ca.ca_opportunity_scoring` | 19 |
| `ca.digital_twin_signals` | 44 |
| `ca.document_vector_chunks` | 22 |
| `ca.mkt_rates_curves` | 10 |
| `ca.ext_credit_spreads` | 8 |
| `ca.ext_deals` | 3 |
| `ca.coverage_teams` | 10 |
| `ca.dt_client_master` | 13 (legacy) |
| `ca.cand5_client_master` | 0 (legacy) |

---

## 2. Live Tables

The following nine tables are read by active code paths.

### 2.1 `ca.client_master`

**Purpose:** Golden source of client identity and coverage mapping.

**Primary key:** `client_id`

**Columns:**

| # | Column | Type | Nullable |
|---|---|---|---|
| 1 | `client_id` | varchar | NO |
| 2 | `client_name` | varchar | NO |
| 3 | `group_parent` | varchar | YES |
| 4 | `legal_entity` | varchar | YES |
| 5 | `industry_sector` | varchar | YES |
| 6 | `country` | varchar | YES |
| 7 | `region` | varchar | YES |
| 8 | `ownership_type` | varchar | YES |
| 9 | `tier` | varchar | YES |
| 10 | `hq_country` | varchar | YES |
| 11 | `revenue_eur_m` | numeric | YES |
| 12 | `rm_name` | varchar | YES |
| 13 | `base_ccy` | varchar | YES |

**Referenced by:** All UI segments. `client_id` is the join key for every other table.

**Notes:**
- No `ticker` column exists. Tickers are not stored in the DB.
- `rm_name` is a fallback. The preferred source is `ca.coverage_teams` filtered by
  `role_title ILIKE '%Relationship Manager%'`.

### 2.2 `ca.ext_company_filings`

**Purpose:** Balance sheet metrics from corporate filings.

**Primary key:** `filing_id`

**Columns:**

| # | Column | Type |
|---|---|---|
| 1 | `filing_id` | varchar |
| 2 | `client_id` | varchar |
| 3 | `reporting_period` | varchar |
| 4 | `net_debt_eur_m` | numeric |
| 5 | `liquidity_eur_m` | numeric |
| 6 | `ebitda_eur_m` | numeric |
| 7 | `reported_revenue_eur_m` | numeric |
| 8 | `debt_maturing_24m_eur_m` | numeric |
| 9 | `notes` | text |

**Used by:** Segment 1 (Client Data) of the opportunity card, lineage Tile 1, and the
balance sheet slide of the pitchbook.

**Notes:**
- One row per reporting period. Latest is selected via `ORDER BY reporting_period DESC LIMIT 1`.
- `debt_maturing_24m_eur_m` is a **reported aggregate**, distinct from the sum of
  `ca.debt_maturity_schedule`. See `data_population.md` §5.

### 2.3 `ca.debt_maturity_schedule`

**Purpose:** Itemized debt instruments per client.

**Primary key:** `isin`

**Columns:**

| # | Column | Type |
|---|---|---|
| 1 | `isin` | varchar |
| 2 | `client_id` | varchar |
| 3 | `instrument_type` | varchar |
| 4 | `amount_eur_m` | numeric |
| 5 | `maturity_year` | integer |
| 6 | `coupon_rate_pct` | numeric |
| 7 | `currency` | varchar |

**Used by:** The debt maturity slide of the pitchbook, and any query that needs a per-tranche
breakdown.

**Notes:**
- `maturity_year` is an integer, not a date.
- `instrument_type` values observed: Bond, Swap, Derivative, Loan, Commodity, Facility.
- **FK not enforced at DB level.** The `client_id` relationship is logical only.

### 2.4 `ca.ca_opportunity_scoring`

**Purpose:** Curated opportunity record. Contains the anchor narrative used by mandate
synthesis.

**Primary key:** `opportunity_id`

**Columns:**

| # | Column | Type | Notes |
|---|---|---|---|
| 1 | `opportunity_id` | varchar | |
| 2 | `client_id` | varchar | |
| 3 | `opportunity_type` | varchar | Free text (e.g., `SUSTAINABLE FUNDING`) |
| 4 | `trigger_source` | text | |
| 5 | `est_revenue_eur_000` | numeric | Fee estimate in thousands |
| 6 | `propensity_score` | integer | LLM-derived, unused in display |
| 7 | `value_score` | integer | LLM-derived, unused in display |
| 8 | `priority_score` | integer | Displayed as `<Label> · <Score>` |
| 9 | `rank` | integer | Unused by code |
| 10 | `next_best_action` | text | **Anchor field** |
| 11 | `why_now_nlg` | text | **Anchor field** |

**Used by:** Priority sidebar, mandate synthesis anchor, opportunity card header.

**Notes:**
- `priority_score` is not computed by a formula. See `Data_or_Fabrication.md` §6.
- `propensity_score` and `value_score` are LLM outputs from earlier ingestion eras. Retained
  but unused.
- `rank` exists but is not read by any code path. Presentation rank is computed at request time.

### 2.5 `ca.digital_twin_signals`

**Purpose:** Real-time signals extracted from all ingestion sources.

**Primary key:** `signal_id`

**Columns:**

| # | Column | Type |
|---|---|---|
| 1 | `signal_id` | varchar |
| 2 | `client_id` | varchar |
| 3 | `catalog_family` | varchar |
| 4 | `signal_type` | varchar |
| 5 | `metric_identified` | text |
| 6 | `trigger_summary` | text |
| 7 | `metric_value` | varchar |
| 8 | `description` | text |
| 9 | `confidence_pct` | integer |
| 10 | `urgency` | varchar |
| 11 | `created_at` | timestamp |

**Used by:** Live signal marquee, mandate synthesis, Context Fabric segment, lineage Tile 3.

**Notes:**
- `signal_type` is free text. Values range from `SUSTAINABLE FUNDING` (with space) to
  `BOARD_AUTHORIZATION` (with underscore). The display layer normalizes via
  `_format_signal_type()`.
- Dedup guard operates on `(client_id, trigger_summary)`.
- No `source` column. The source channel lives in `ca.document_vector_chunks.source_channel`.

### 2.6 `ca.document_vector_chunks`

**Purpose:** Vector chunks for RAG and houseview retrieval.

**Primary key:** `chunk_id` (bigint)

**Columns:**

| # | Column | Type |
|---|---|---|
| 1 | `chunk_id` | bigint |
| 2 | `client_id` | varchar |
| 3 | `source_channel` | varchar |
| 4 | `source_name` | varchar |
| 5 | `text_content` | text |
| 6 | `structured_metadata` | jsonb |
| 7 | `embedding` | vector(768) |
| 8 | `created_at` | timestamp |

**Used by:** Houseviews & News segment, Context Fabric chips, lineage Tile 4.

**Notes:**
- `source_channel` values: `PDF_REPORT`, `NEWS_RSS`, `CLIENT_EMAIL`, `TEAMS_CHAT`,
  `WORKFABRIC_MEMO`. Historical values (`TEAMS`, `TREASURY_EMAIL`, `ANALYST_NOTE`,
  `NEWS_ARTICLE`) exist from earlier ingestion eras.
- `structured_metadata` has three formats depending on ingestion era. See
  `Data_or_Fabrication.md` §5.3.
- `embedding` column is `vector(768)` from the pgvector extension.

### 2.7 `ca.coverage_teams`

**Purpose:** Coverage team members per client.

**Composite key:** (`client_id`, `role_title`)

**Columns:**

| # | Column | Type |
|---|---|---|
| 1 | `client_id` | varchar |
| 2 | `role_title` | varchar |
| 3 | `banker_name` | varchar |
| 4 | `location` | varchar |

**Used by:** Segment 1 (Client Data) — the RM name.

**Notes:**
- Filter for RM: `WHERE role_title ILIKE '%Relationship Manager%'`.
- Only Enel, ASML, and BASF have coverage team entries. Other clients fall back to
  `ca.client_master.rm_name`.

### 2.8 `ca.mkt_rates_curves`

**Purpose:** Market rates by currency and tenor.

**Primary key:** `curve_id`

**Columns:**

| # | Column | Type |
|---|---|---|
| 1 | `curve_id` | integer |
| 2 | `curve_date` | date |
| 3 | `currency` | varchar |
| 4 | `tenor` | varchar |
| 5 | `swap_rate_pct` | numeric |
| 6 | `govt_yield_pct` | numeric |
| 7 | `category` | varchar |

**Used by:** Segment 2 (Market Data), lineage Tile 2, market backdrop slide.

**Notes:**
- Tall table — one row per (currency, tenor). Not a wide table with columns per tenor.
- Code selects by `WHERE currency = 'EUR'` and filters by `tenor` in Python.
- No `rate_pct` column. There are two rate columns: `swap_rate_pct` (for swaps) and
  `govt_yield_pct` (for government bonds).

### 2.9 `ca.ext_credit_spreads`

**Purpose:** Credit spreads by issuer or rating bucket.

**Primary key:** `spread_id`

**Columns:**

| # | Column | Type |
|---|---|---|
| 1 | `spread_id` | integer |
| 2 | `quote_date` | date |
| 3 | `issuer_or_rating` | varchar |
| 4 | `sector` | varchar |
| 5 | `tenor` | varchar |
| 6 | `spread_bps` | numeric |
| 7 | `all_in_yield_pct` | numeric |
| 8 | `source` | varchar |

**Used by:** Segment 2 (Market Data) — the credit spread value.

**Notes:**
- `issuer_or_rating` may be an issuer name (e.g., "Enel (BBB+)") or a rating bucket
  (e.g., "BBB rating curve").
- There is no `index_name` column. The current code does ILIKE matching on
  `issuer_or_rating`.

### 2.10 `ca.ext_deals`

**Purpose:** ING track record and credentials per client.

**Primary key:** `deal_id`

**Columns:**

| # | Column | Type |
|---|---|---|
| 1 | `deal_id` | varchar |
| 2 | `client_id` | varchar |
| 3 | `deal_type` | varchar |
| 4 | `volume_eur_m` | numeric |
| 5 | `role` | varchar |
| 6 | `deal_date` | date |
| 7 | `description` | text |

**Used by:** Nothing currently. Candidate for the "Why Execute With Us" slide.

**Current contents:** 3 rows (2 for Enel, 1 for BASF). Client IDs canonical after the
14 Sep 2026 cleanup.

---

## 3. Legacy Tables

The following tables exist but are not read by any live code path.

### 3.1 `ca.dt_client_master` (13 rows)

**Purpose:** Earlier reduced-column version of `ca.client_master`.

**Difference from `client_master`:**
- Column `tier` renamed to `client_tier`
- Missing: `hq_country`, `revenue_eur_m`, `rm_name`
- Otherwise identical content

**Superseded by:** `ca.client_master`. Retained as historical.

### 3.2 `ca.cand5_client_master` (0 rows)

**Purpose:** Candidate/onboarding staging table. Empty.

**Columns:** 12 columns including `maps_to_original_id`, `approach_overall_assessment`.

**Status:** Deprecated. Safe to drop in a future cleanup, but left in place per project
constraint against DDL.

---

## 4. Relationship Model

Logical relationships between tables (FK constraints are not enforced at the DB level):

```
ca.client_master
    │
    ├── client_id ◄──── ca.ext_company_filings.client_id
    ├── client_id ◄──── ca.debt_maturity_schedule.client_id
    ├── client_id ◄──── ca.ca_opportunity_scoring.client_id
    ├── client_id ◄──── ca.digital_twin_signals.client_id
    ├── client_id ◄──── ca.document_vector_chunks.client_id
    ├── client_id ◄──── ca.coverage_teams.client_id
    └── client_id ◄──── ca.ext_deals.client_id
```

`ca.mkt_rates_curves` and `ca.ext_credit_spreads` are standalone — they are not keyed to
any client.

**Note on referential integrity:** the DB does not enforce these relationships. The
application code enforces them by always filtering on `client_id`. If a row exists in a
child table with a `client_id` that's not in `ca.client_master`, it will be orphaned but
not flagged by the DB.

---

## 5. Data Type Conventions

| Type | Convention |
|---|---|
| Money amounts | `numeric` in millions of EUR, except `est_revenue_eur_000` (thousands) |
| Rates | `numeric` in percentage points (2.62 = 2.62%) |
| Spreads | `numeric` in basis points (78 = 78 bps) |
| Years | `integer` (2026, 2027) |
| Dates | `date` for trading days; `timestamp` for event timestamps |
| Client IDs | `varchar`, format `CLI###` |
| Signal IDs | `varchar`, format `SIG-XXXXXXXX` or `SIG_CLI###_*` |

---

## 6. How To Regenerate This Document

The row counts and column lists above were produced by:

```sql
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;
```

And per-table:

```sql
SELECT ordinal_position, column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_schema = 'ca' AND table_name = '<table_name>'
ORDER BY ordinal_position;
```

Run these after any schema change to refresh this doc.

---

## 7. Changelog — 14 Sep 2026

Corrected from the pre-14-Sep version:

- **Removed fictional columns.** The previous version listed `role`, `name`, `email`,
  `desk`, `source`, `confidence_score`, `rating`, `benchmark_type`, `notional_eur_m`,
  `pricing`, `rate_pct`, `timestamp`, `document_type`, `product` — none of which exist.
  Replaced with actual columns from the schema query.
- **Row counts verified.** All 12 tables confirmed against the live DB.
- **Added `ca.ext_deals`** as a live table (it was missing entirely).
- **Marked `ca.dt_client_master` and `ca.cand5_client_master` as legacy** with the
  specific differences from their counterparts.
- **Removed incorrect FK claims.** The DB does not enforce FKs; relationships are logical.
- **Corrected table-name ambiguities.** Named the two rate columns
  (`swap_rate_pct`, `govt_yield_pct`) explicitly.
- **Added §4 Relationship Model** to show the join graph.
- **Added §5 Data Type Conventions.**
- **Added §6 Regeneration Steps.**

---

*End of document.*