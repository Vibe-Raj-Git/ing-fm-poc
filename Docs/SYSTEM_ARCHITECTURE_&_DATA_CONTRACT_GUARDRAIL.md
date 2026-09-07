Now we have the exact, verified schema straight from PostgreSQL information_schema.columns.

Notice the critical domain nuances:

1.	ca.ext_company_filings stores metrics in millions: net_debt_eur_m (58,500.00), liquidity_eur_m (14,200.00), and debt_maturing_24m_eur_m (3,000.00). This confirms why the pipeline transforms them to €58.5bn and €14.2bn for presentation.
2.	ca.ca_opportunity_scoring provides why_now_nlg (the strategic trigger) and next_best_action (the trade execution proposal).
3.	ca.client_master supplies tier, revenue_eur_m, industry_sector, and legal_entity.
4.	ca.debt_maturity_schedule contains the granular maturity profile broken down by ISIN, instrument, and coupon.

Here is the exact, zero-hardcoding technical architecture prompt locked to your schema:


Markdown
### SYSTEM ARCHITECTURE & DATA CONTRACT GUARDRAIL: ZERO-HARDCODING PIPELINE
**Target Scope:** `App.jsx`, `main.py`, `pitchbook_builder.py`, `test_parity.py`  
**Core Directive:** Maintain 100% data-driven parity across UI Preview, PPTX generation (`python-pptx`), and Copilot LLM prompts. Zero hardcoded financial rates, placeholder text, or synthetic fallbacks.

---

### 1. VERIFIED POSTGRESQL SCHEMA SPECIFICATION (`ca` Schema)

All data must resolve dynamically from these exact tables and columns:

* **`ca.client_master`**
  - Columns: `client_id` (PK, e.g. `'CLI101'`), `client_name`, `group_parent`, `legal_entity`, `industry_sector`, `country`, `region`, `ownership_type`, `tier`, `hq_country`, `revenue_eur_m`, `rm_name`, `base_ccy`.
  - Usage: Client identity, tier resolution, baseline annual revenue.

* **`ca.ext_company_filings`**
  - Columns: `filing_id` (PK), `client_id` (FK), `reporting_period`, `net_debt_eur_m`, `liquidity_eur_m`, `ebitda_eur_m`, `reported_revenue_eur_m`, `debt_maturing_24m_eur_m`, `notes`.
  - Usage: Balance sheet sizing (Net Debt, Liquidity, 24M Maturity Wall, EBITDA).

* **`ca.ca_opportunity_scoring`**
  - Columns: `opportunity_id` (PK), `client_id` (FK), `opportunity_type`, `trigger_source`, `est_revenue_eur_000`, `propensity_score`, `value_score`, `priority_score`, `rank`, `next_best_action`, `why_now_nlg`.
  - Usage: Trade catalysts (`why_now_nlg`), proposed deal execution (`next_best_action`), prioritization ranking.

* **`ca.debt_maturity_schedule`**
  - Columns: `isin` (PK), `client_id` (FK), `instrument_type`, `amount_eur_m`, `maturity_year`, `coupon_rate_pct`, `currency`.
  - Usage: Granular bond tranches and maturity horizon charts.

* **`ca.ext_deals`**
  - Columns: `deal_id` (PK), `client_id` (FK), `deal_type`, `volume_eur_m`, `role`, `deal_date`, `description`.
  - Usage: Historical deals and benchmark issue precedents.

* **`ca.mkt_rates_curves`**
  - Columns: `curve_id` (PK), `curve_date`, `currency`, `tenor` (`'1Y'` through `'30Y'`), `swap_rate_pct`, `govt_yield_pct`, `category`.
  - Ground Truth Values: `5Y EUR` swap rate (`swap_rate_pct = 2.62`), `10Y EUR` govt yield (`govt_yield_pct = 2.61`).

* **`ca.ext_credit_spreads`**
  - Columns: `spread_id` (PK), `quote_date`, `issuer_or_rating`, `sector`, `tenor`, `spread_bps`, `all_in_yield_pct`, `source`.
  - Ground Truth Values (Enel): `5Y` spread (`spread_bps = 78.00`, `all_in_yield_pct = 3.400`), `10Y` spread (`spread_bps = 80.00`, `all_in_yield_pct = 3.600`).

---

### 2. SLIDE-BY-SLIDE DYNAMIC RESOLUTION CONTRACT

1. **Slide 1 (Cover):**
   - Derived from `ca.client_master.client_name`, `legal_entity`, and `detect_product_family()`.
2. **Slide 2 (Catalyst):**
   - `why_now_nlg` and `next_best_action` from `ca.ca_opportunity_scoring`.
   - Repricing risk references `ca.ext_company_filings.debt_maturing_24m_eur_m`.
3. **Slide 3 (Executive Summary):**
   - Focus and recommended structure driven by `ca.ca_opportunity_scoring.next_best_action` and `ca.client_master.client_name`.
4. **Slide 4 (Balance Sheet Foundation):**
   - `net_debt_eur_m` formatted as `€X.Xbn` (e.g. `58500` -> `€58.5bn`).
   - `liquidity_eur_m` formatted as `€X.Xbn` (e.g. `14200` -> `€14.2bn`).
   - `debt_maturing_24m_eur_m` formatted as `€X,XXXM` (e.g. `€3,000M`).
   - Rating string derived dynamically as `External ratings: S&P | BBB | Positive` for Enel (`CLI101`), never generic `Tier 1`.
5. **Slide 5 (Green Asset Pool / Sizing):**
   - Pool volume and CapEx pipeline mapped from deal opportunity data and use-of-proceeds allocation.
6. **Slide 6 (Pricing Sensitivity):**
   - Step concessions derived dynamically from `ca.ext_credit_spreads.spread_bps` (e.g., `-5 bps` to `-3 bps` greenium pricing).
7. **Slide 7 (Market Reference Backdrop):**
   - `swap_5y` (`2.62%`) and `bund_10y` (`2.61%`) from `ca.mkt_rates_curves`.
   - `credit_spread_5y` (`78 bps`) and `all_in_yield` (`3.40%`) from `ca.ext_credit_spreads`.
   - Copilot context string in `main.py` MUST build reference curves using dynamic f-strings pulling from live variables.
8. **Slide 8 (Indicative Term Sheet):**
   - Tranche sizing and tenors derived from deal proposal and canonical calculation.
   - Spread cell (`s8_tbl.cell(5, 1)`) must dynamically evaluate `ov.get("spread")`, `ov.get("credit_spread_5y")`, or `calc['spread_bps']`.
   - Copilot mutations (e.g., overriding `78 bps` to `60 bps`) MUST propagate into the generated table cell.
9. **Slide 9 (Execution Roadmap):**
   - Derived from `ca.ca_opportunity_scoring.opportunity_type` and deal syndication tracks.
10. **Slide 10 (Regulatory Disclosures):**
    - Dynamic compliance regime injection (ICMA GBP, EU Taxonomy, MiFID II, EMIR Refit) based on client product family.

---

### 3. THE 3-TIER RESOLUTION HIERARCHY

Whenever querying, computing, or formatting fields in `main.py`, `pitchbook_builder.py`, or `App.jsx`, strictly enforce this order:

1. **Active Session Overrides (`current_ov` / `ov`):**
   - Ingest runtime mutations from the RM or Copilot (e.g., `{'credit_spread_5y': '60 bps'}`).
2. **Canonical Database Context (`bundle` / `opp` / `calc` / `ctx`):**
   - Ingest live values from `ca` tables via `fetch_pitchbook_bundle()` and `compute_canonical_bundle()`.
3. **Fail-Safe Non-Breaking Fallback:**
   - Strictly for type safety if a database field returns `None`. Never embed static business rates or bypass the canonical calculation.

---

### 4. INVARIANCE & VERIFICATION RULES

- **Non-Destructive Invariance:** Copilot prompt mutations are session-only. NEVER run `UPDATE` or `INSERT` queries against `ca.ext_credit_spreads` or `ca.mkt_rates_curves` during chat or deck builds.
- **Table Cell Text Access:** In `python-pptx`, table cell contents must be inspected via `cell.text_frame.text` (never `shape.text`).
- **Clean String Escapes:** Always use raw Python strings (`r"..."`) or properly escaped regex tokens (`\\d+`) to avoid Python `SyntaxWarning` issues.
- **Audit Gate Requirement:** Any proposed code change must maintain 13/13 passing gates in `test_parity.py`.

Keep this prompt in your notes or project docs. Whenever we make changes to App.jsx, main.py, or pitchbook_builder.py, paste it into the chat to lock the system directly to your database schema.


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
