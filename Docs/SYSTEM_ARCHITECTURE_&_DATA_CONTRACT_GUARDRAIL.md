# System Architecture & Data Contract Guardrail: Zero-Hardcoding Pipeline

**Version:** 14 September 2026
**Status:** Authoritative
**Supersedes:** Previous version (pre-14 Sep)
**Target Scope:** `App.jsx`, `main.py`, `pitchbook_builder.py`, `test_parity.py`

**Core Directive:** Maintain 100% data-driven parity across the UI preview, the PPTX
generation (`python-pptx`), and the Copilot LLM prompts. No hardcoded financial rates, no
placeholder text, no synthetic fallbacks — with one documented exception (§5).

---

## 1. Verified PostgreSQL Schema

All data resolves dynamically from these tables in the `ca` schema. Column lists are
verified against `information_schema.columns` as of 14 Sep 2026.

### `ca.client_master`

- `client_id` (varchar, PK) — e.g., `CLI101`
- `client_name`, `group_parent`, `legal_entity`
- `industry_sector`, `country`, `region`, `ownership_type`
- `tier`, `hq_country`
- `revenue_eur_m` (numeric, millions EUR)
- `rm_name`, `base_ccy`

**Usage:** Client identity, tier, coverage name, base currency.

### `ca.ext_company_filings`

- `filing_id` (varchar, PK)
- `client_id` (varchar)
- `reporting_period` (varchar)
- `net_debt_eur_m`, `liquidity_eur_m`, `ebitda_eur_m`, `reported_revenue_eur_m` (numeric, millions)
- `debt_maturing_24m_eur_m` (numeric, millions)
- `notes` (text)

**Usage:** Balance sheet sizing, liquidity, EBITDA, 24-month maturity wall.
**Presentation transform:** Values ≥ 1000 are formatted as `€{X.XX}bn`; below that as `€{X}M`.
For Enel: `net_debt_eur_m = 58500` → `€58.5bn`; `debt_maturing_24m_eur_m = 10127` → `€10.13bn`.

### `ca.debt_maturity_schedule`

- `isin` (varchar, PK)
- `client_id` (varchar)
- `instrument_type`, `currency` (varchar)
- `amount_eur_m` (numeric)
- `maturity_year` (integer)
- `coupon_rate_pct` (numeric)

**Usage:** Per-tranche maturity ladder.

### `ca.ca_opportunity_scoring`

- `opportunity_id` (varchar, PK)
- `client_id` (varchar)
- `opportunity_type`, `trigger_source` (free text)
- `est_revenue_eur_000` (numeric, thousands)
- `propensity_score`, `value_score`, `priority_score`, `rank` (integer)
- `next_best_action` (text) — **anchor field**
- `why_now_nlg` (text) — **anchor field**

**Usage:** Trade catalyst, proposed execution, priority ranking.
**Note:** `priority_score` is an LLM-derived estimate, not a formula. See
`Data_or_Fabrication.md` §6.

### `ca.ext_credit_spreads`

- `spread_id` (integer, PK)
- `quote_date` (date)
- `issuer_or_rating` (varchar)
- `sector`, `tenor` (varchar)
- `spread_bps` (numeric)
- `all_in_yield_pct` (numeric)
- `source` (varchar)

**Ground truth (Enel `CLI101`):**

| Tenor | spread_bps | all_in_yield_pct |
|---|---|---|
| 5Y | 78.0 | 3.40 |
| 10Y | 80.0 | 3.41 |

### `ca.mkt_rates_curves`

- `curve_id` (integer, PK)
- `curve_date` (date)
- `currency`, `tenor`, `category` (varchar)
- `swap_rate_pct`, `govt_yield_pct` (numeric)

**Ground truth (EUR):**

| Tenor | swap_rate_pct | govt_yield_pct |
|---|---|---|
| 5Y | 2.62 | 2.38 |
| 10Y | 2.88 | 2.61 |

**Note:** The 10Y Bund (`govt_yield_pct = 2.61`) is on the 10Y row, not the 5Y row. The
doc's earlier claim that both were on 5Y was mislabeled.

### `ca.ext_deals`

- `deal_id` (varchar, PK)
- `client_id` (varchar)
- `deal_type`, `role` (varchar)
- `volume_eur_m` (numeric)
- `deal_date` (date)
- `description` (text)

**Usage:** Currently unused. Candidate for the "Why Execute With Us" slide.

### `ca.coverage_teams`

- `client_id` (varchar)
- `role_title` (varchar)
- `banker_name` (varchar)
- `location` (varchar)

**Usage:** Preferred source for RM name. Filter `role_title ILIKE '%Relationship Manager%'`.

### `ca.digital_twin_signals`

- `signal_id` (varchar, PK)
- `client_id` (varchar)
- `catalog_family`, `signal_type`, `metric_value`, `urgency` (varchar)
- `metric_identified`, `trigger_summary`, `description` (text)
- `confidence_pct` (integer)
- `created_at` (timestamp)

**Usage:** Signal marquee, mandate synthesis context, Context Fabric segment.

### `ca.document_vector_chunks`

- `chunk_id` (bigint, PK)
- `client_id` (varchar)
- `source_channel`, `source_name` (varchar)
- `text_content` (text)
- `structured_metadata` (jsonb)
- `embedding` (vector(768))
- `created_at` (timestamp)

**Usage:** Houseview retrieval, Context Fabric chips, lineage Tile 4.

### Legacy tables

- `ca.dt_client_master` (13 rows) — reduced-column version of `client_master`
- `ca.cand5_client_master` (0 rows) — deprecated candidate staging

---

## 2. Slide-by-Slide Dynamic Resolution Contract

The pitchbook has **11 slides**. Slide titles vary by product family (FX / Green / Rates /
DCM). Full mapping is in `architecture_flow_14Sep.md` §6.2.

The table below documents the Green/ESG family (Enel's deck). Other families follow the same
column sources with different slide names.

### Slide 1 — Cover

- `ca.client_master.client_name`, `legal_entity`
- Product family via `detect_product_family()`
- RM name: `ca.coverage_teams.banker_name` where `role_title ILIKE '%Relationship Manager%'`
- Fallback: `ca.client_master.rm_name`

### Slide 2 — Strategic Catalyst

- **Primary Market Trigger:** `ca.ca_opportunity_scoring.trigger_source` (or synthesized narrative)
- **Window of Opportunity:** synthesis output
- **Recommended Action:** `ca.ca_opportunity_scoring.next_best_action`

### Slide 3 — Executive Summary

- Numbered pillars from `get_product_pillars(p_fam, ctx, ov)` in `pitchbook_builder.py`
- Pillars blend: `ca.digital_twin_signals` (WorkFabric latent opportunities) +
  `ca.ca_opportunity_scoring.next_best_action` + family-specific template content

### Slide 4 — Balance Sheet Foundation

| Card | Source | Format |
|---|---|---|
| Net Debt | `ca.ext_company_filings.net_debt_eur_m` | `€{X.X}bn` if ≥1000, else `€{X}M` |
| Available Liquidity | `ca.ext_company_filings.liquidity_eur_m` | Same |
| 24M Maturity Wall | `ca.ext_company_filings.debt_maturing_24m_eur_m` | Same (shows `€10.13bn` for Enel) |
| Credit Rating | **Hardcoded override** for Enel | See §5 |
| Revenue | `ca.ext_company_filings.reported_revenue_eur_m` | `€{X}M` |
| EBITDA | `ca.ext_company_filings.ebitda_eur_m` | `€{X}M` |

### Slide 5 — Use of Proceeds Pool (Green family)

- Green pool breakdown comes from the synthesis context, not a DB table.
- **Future improvement:** add a `ca.sustainability_frameworks` table to source the pool
  breakdown deterministically.

### Slide 6 — Greenium Sensitivity (Green family)

- Green spread: `ca.ext_credit_spreads.spread_bps` for the client's 5Y row
- Greenium: `ca.ca_opportunity_scoring.why_now_nlg` or synthesis override
- Savings: computed as `notional × greenium_bps / 10000`

### Slide 7 — ESG Market Backdrop

- 5Y EUR Swap: `ca.mkt_rates_curves.swap_rate_pct` WHERE `tenor = '5Y'`
- 10Y Bund: `ca.mkt_rates_curves.govt_yield_pct` WHERE `tenor = '10Y'`
- 5Y Credit Spread: `ca.ext_credit_spreads.spread_bps` WHERE `tenor = '5Y'`
- All-In Yield: computed or from `ca.ext_credit_spreads.all_in_yield_pct`
- Copilot context strings build reference curves with dynamic f-strings, not literals

### Slide 8 — Proposal Features (Term Sheet)

- Notional Leg 1: `ov.get("notional_bond")` or bundle default
- Notional Leg 2: `ov.get("notional_swap")` or bundle default
- Tenor: `ov.get("tenor")` or `compute_canonical_bundle()`
- **Spread cell:** `s8_tbl.cell(5, 1)` and `s8_tbl.cell(5, 2)` — row index 5 is the
  Spread/rate row. Copilot mutations (e.g., `78 bps` → `60 bps`) propagate here.
- Documentation: `ov.get("disclaimers")` or fallback list

### Slide 9 — Why Execute With Us

- Currently renders six generic franchise capability cards.
- **Future improvement:** wire to `ca.ext_deals` for client-specific credentials.

### Slide 10 — Execution Roadmap (or SPO & Syndicate Plan for Green)

- Milestones from template in `pitchbook_builder.py`
- Product family changes the specific milestone wording

### Slide 11 — Regulatory Disclosures

- Disclaimers from `ov.get("disclaimers")` or product-family fallback
- Regulatory regime injection: ICMA GBP, EU Taxonomy, MiFID II, EMIR Refit

---

## 3. The 3-Tier Resolution Hierarchy

Whenever a value is queried, computed, or formatted, enforce this order:

### Tier 1 — Active Session Overrides (`current_ov` / `ov`)

Runtime mutations from the RM or Copilot. Example: `{'credit_spread_5y': '60 bps'}`.
These take precedence over everything.

### Tier 2 — Canonical Database Context (`bundle` / `opp` / `calc` / `ctx`)

Live values from `ca` tables via `fetch_pitchbook_bundle()` and
`compute_canonical_bundle()`.

### Tier 3 — Fail-Safe Non-Breaking Fallback

Strictly for type safety if a database field returns `None`. **Never embed static business
rates or bypass the canonical calculation.** Fallbacks return `"N/A"`, `"—"`, or an empty
string — not invented numbers.

---

## 4. Invariance & Verification Rules

### Non-destructive invariance

Copilot prompt mutations are session-only. **NEVER** run `UPDATE` or `INSERT` queries
against `ca.ext_credit_spreads` or `ca.mkt_rates_curves` during chat or deck builds. The
only exception is the mandate synthesis write-back to `ca.ca_opportunity_scoring`
(`why_now_nlg` and `next_best_action`), which is intentional and audited.

### Table cell text access (python-pptx)

Table cell contents must be inspected via `cell.text_frame.text`, never `shape.text`.
`shape.text` does not exist on table shapes and will raise `AttributeError`.

### Clean string escapes

Use raw Python strings (`r"..."`) or properly escaped regex tokens (`\\d+`) to avoid
`SyntaxWarning` issues when embedding patterns in f-strings.

### Audit gate requirement

`test_parity.py` runs a 13-gate dynamic parity audit. It validates:

- PostgreSQL connection
- `ca.mkt_rates_curves` ground truth (5Y swap 2.62%, 10Y Bund 2.61%)
- `ca.ext_credit_spreads` ground truth (Enel 5Y = 78 bps, 10Y = 80 bps)
- `/api/opportunities` Enel retrieval
- Database bundle integrity
- Plus 8 additional gates covering the pipeline, PPTX generation, and preview consistency

**Any proposed code change must maintain 13/13 passing gates.** Run:

```bash
cd ~/ing-fm-poc
python3 test_parity.py
```

Expected output ends with all 13 gates printed as `✅` and a summary like `13/13 gates passed`.

`test_parity.py` is not a pytest suite — it's an inline audit script. Run it directly.

---

## 5. Known Exceptions To Zero-Hardcoding

The platform aims for 100% data-driven values. Two exceptions exist today, both documented
for future cleanup.

### Exception 1 — Enel credit rating string

**Location:**

- `main.py:1663` — `db_rating = "External ratings: S&P | BBB | Positive"`
- `pitchbook_builder.py:912` — `tier_str = "S&P | BBB | Positive"`

**What it is:** A hardcoded literal for client `CLI101` (Enel). The DB's
`ca.client_master.tier` field does not contain this string.

**Why it exists:** The `tier` column contains a coverage classification ("Tier 1", "Tier
2"), not a credit rating. The proper source would be a `credit_rating` column, which does
not exist.

**Future fix (post-demo):** Add a `credit_rating` column to `ca.client_master` and remove
the hardcoded override. This requires a schema change, which is out of scope for the
current phase.

**Impact:** The rating string is correct for Enel. For any other client, the code falls
back to the generic `tier` value. No user-facing inaccuracy today, but the pattern is
fragile.

### Exception 2 — WorkFabric latent opportunities in the pillars

**Location:** `pitchbook_builder.py` — `get_product_pillars()` function.

**What it is:** When the client's `ca.digital_twin_signals` table has no
`LATENT_OPPORTUNITY` rows, the function uses a template paragraph for pillar 2.

**Why it exists:** Ensures the pillars render with a coherent narrative even when the
signal corpus is sparse.

**Impact:** Only fires when no latent opportunities exist. For Enel, three latent
opportunities are present, and the pillar renders the actual signal content.

---

## 6. Changelog — 14 Sep 2026

Corrected from the pre-14-Sep version:

- **Slide count corrected.** 10 → 11 slides. All slide references renumbered.
- **Slide 4 formatting corrected.** `€X,XXXM` → `€{X.XX}bn` for values ≥ 1000.
- **Enel rating string disclosed as hardcoded.** The doc previously claimed it was
  "derived dynamically." It is not. Now documented as a known exception in §5.
- **Enel 10Y all-in corrected.** `3.600%` → `3.41%`.
- **`ca.mkt_rates_curves` ground truth clarified.** The 10Y Bund value is on the 10Y row,
  not the 5Y row.
- **Slide 5-6 identified as Green-family specific.** The doc previously described them
  without noting the family variant.
- **`test_parity.py` reference verified.** The file exists, is an inline audit script,
  and runs 13 gates.
- **§5 Known Exceptions added.**
- **Slide 3, 9, 10 descriptions expanded.**

---

## 7. Reference

For the full 11-slide product-family mapping, see `architecture_flow_14Sep.md` §6.2.

For the actual mandate synthesis anchor pattern, see
`How_Signals_are_Converted_into_Opportunities.md` §5.

For the scoring mechanism, see `Data_or_Fabrication.md` §6.

---

*End of document.*


## To find out how many Tables are in my Cloud SQL PostgreSQL DB:-

Let's query PostgreSQL's information_schema.tables directly from your environment so we capture the exact, ground-truth table names and schemas:

cd ~/ing-fm-poc

python3 - << 'EOF'
from main import get_db_connection

conn, connector = get_db_connection()
cur = conn.cursor()

cur.execute("""
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY table_schema, table_name;
""")

rows = cur.fetchall()
print("--- Actual Database Tables in Environment ---")
for schema, table in rows:
    print(f"{schema}.{table}")

cur.close()
conn.close()
if connector:
    connector.close()
EOF

# Output:-
--- Actual Database Tables in Environment ---
ca.ca_opportunity_scoring
ca.cand5_client_master
ca.client_master
ca.coverage_teams
ca.debt_maturity_schedule
ca.digital_twin_signals
ca.document_vector_chunks
ca.dt_client_master
ca.ext_company_filings
ca.ext_credit_spreads
ca.ext_deals
ca.mkt_rates_curves

Now we have the real database catalog. Notice the exact table names:
•	ca.client_master
•	ca.debt_maturity_schedule (where the 24M maturity wall / debt profile lives)
•	ca.ext_deals (deal pipeline / opportunities)
•	ca.ca_opportunity_scoring (opportunity ranking & signals)
•	ca.ext_company_filings (balance sheet, financials, liquidity, Net Debt)
•	ca.ext_credit_spreads (issuer spreads & all-in yields)
•	ca.mkt_rates_curves (EUR/USD swap and benchmark curves)
•	ca.digital_twin_signals, ca.coverage_teams, ca.cand5_client_master, ca.dt_client_master, ca.document_vector_chunks

## Let's do a quick column inspection on the core 6 tables so we document the exact schema columns with 100% accuracy:

cd ~/ing-fm-poc

python3 - << 'EOF'
from main import get_db_connection

conn, connector = get_db_connection()
cur = conn.cursor()

tables = [
    'client_master',
    'ext_deals',
    'debt_maturity_schedule',
    'ext_company_filings',
    'mkt_rates_curves',
    'ext_credit_spreads',
    'ca_opportunity_scoring'
]

print("=" * 70)
for t in tables:
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'ca' AND table_name = '{t}'
        ORDER BY ordinal_position;
    """)
    cols = cur.fetchall()
    print(f"TABLE: ca.{t}")
    for col, dt in cols:
        print(f"  - {col} ({dt})")
    print("-" * 70)

cur.close()
conn.close()
if connector:
    connector.close()
EOF

# Output:-
TABLE: ca.client_master
  - client_id (character varying)
  - client_name (character varying)
  - group_parent (character varying)
  - legal_entity (character varying)
  - industry_sector (character varying)
  - country (character varying)
  - region (character varying)
  - ownership_type (character varying)
  - tier (character varying)
  - hq_country (character varying)
  - revenue_eur_m (numeric)
  - rm_name (character varying)
  - base_ccy (character varying)
----------------------------------------------------------------------
TABLE: ca.ext_deals
  - deal_id (character varying)
  - client_id (character varying)
  - deal_type (character varying)
  - volume_eur_m (numeric)
  - role (character varying)
  - deal_date (date)
  - description (text)
----------------------------------------------------------------------
TABLE: ca.debt_maturity_schedule
  - isin (character varying)
  - client_id (character varying)
  - instrument_type (character varying)
  - amount_eur_m (numeric)
  - maturity_year (integer)
  - coupon_rate_pct (numeric)
  - currency (character varying)
----------------------------------------------------------------------
TABLE: ca.ext_company_filings
  - filing_id (character varying)
  - client_id (character varying)
  - reporting_period (character varying)
  - net_debt_eur_m (numeric)
  - liquidity_eur_m (numeric)
  - ebitda_eur_m (numeric)
  - reported_revenue_eur_m (numeric)
  - debt_maturing_24m_eur_m (numeric)
  - notes (text)
----------------------------------------------------------------------
TABLE: ca.mkt_rates_curves
  - curve_id (integer)
  - curve_date (date)
  - currency (character varying)
  - tenor (character varying)
  - swap_rate_pct (numeric)
  - govt_yield_pct (numeric)
  - category (character varying)
----------------------------------------------------------------------
TABLE: ca.ext_credit_spreads
  - spread_id (integer)
  - quote_date (date)
  - issuer_or_rating (character varying)
  - sector (character varying)
  - tenor (character varying)
  - spread_bps (numeric)
  - all_in_yield_pct (numeric)
  - source (character varying)
----------------------------------------------------------------------
TABLE: ca.ca_opportunity_scoring
  - opportunity_id (character varying)
  - client_id (character varying)
  - opportunity_type (character varying)
  - trigger_source (text)
  - est_revenue_eur_000 (numeric)
  - propensity_score (integer)
  - value_score (integer)
  - priority_score (integer)
  - rank (integer)
  - next_best_action (text)
  - why_now_nlg (text)
----------------------------------------------------------------------
