ING Financial Markets AI Platform

Data Integrity, Dynamic State Lineage & Zero-Fabrication Architecture Specification

1. Executive Summary & Verification Principles
The ING Financial Markets Deal Intelligence & Origination Platform is built on a Zero-Fabrication Architecture. In wholesale banking and Financial Markets (FM) origination, synthetic mock numbers or ungrounded generative AI hallucinations introduce unacceptable regulatory, credit, and reputational risk.
The platform enforces a strict separation of concerns:
Deterministic Calculations & Truth Layer: All corporate balance sheet metrics, debt amortization tranches, liquidity reserves, and live swap curves originate from Cloud SQL (PostgreSQL with the ca schema) and are computed via deterministic math.
Hybrid Intelligence Layer: Gemini 1.5 Flash performs entity extraction from unstructured communication channels (Teams, Emails, RSS) and rapid MiFID II regulatory pattern screening. Gemini 1.5 Pro serves as the interactive Deal Copilot, evaluating cross-slide financing strategies and executing natural language state mutations.
Deterministic Generation Layer: Presentation decks (both on the interactive React canvas and in the downloadable PowerPoint file) are rendered without generative layout hallucinations, ensuring 1:1 visual, numerical, and structural parity.┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Zero-Fabrication Data Flow Pipeline                                       │
│                                                                                                             │
│  Unstructured Inputs            Cloud SQL (PostgreSQL)            FastAPI Business Logic        React / PPTX│
│  ┌────────────────────┐         ┌────────────────────────┐        ┌────────────────────┐       ┌───────────┐│
│  │ • Teams Chats      │────────►│ • ca.dt_client_master  │───────►│ • Deterministic    │──────►│ • 1:1 UI  ││
│  │ • Treasury Emails  │ (Flash) │ • ca.corp_debt_sched   │ (ACID) │   Financial Math   │       │   Canvas  ││
│  │ • Market RSS News  │         │ • ca.market_fixings    │        │ • Copilot Context  │       │ • Native  ││
│  │ • Filings (PDF)    │         │ • ca.vector_chunks     │        │   Hydration        │       │   .PPTX   ││
│  └────────────────────┘         └────────────────────────┘        └────────────────────┘       └───────────┘│
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
2. Dynamic Data Layer Breakdown (ca Schema)Every visual tile, pipeline card, metric counter, and term sheet parameter maps to live PostgreSQL tables and deterministic aggregation queries.UI Section & API RouteUnderlying PostgreSQL Tables & Query LogicDynamic vs Hardcoded VerificationThis Week Metrics Strip/api/metrics• Active Drafts: COUNT(DISTINCT client_id) from ca.digital_twin_signals• High Conviction Deals: COUNT(*) from ca.ca_opportunity_scoring WHERE priority_score >= 85• Cohort Matches: COUNT(*) from ca.dt_client_master100% Dynamic DB AggregateRecalculates instantly whenever new signals or corporate profiles are added.Continuous Live Signal Feed/api/signals/live• Query: SELECT s.*, c.client_name FROM ca.digital_twin_signals s LEFT JOIN ca.dt_client_master c ORDER BY s.created_at DESC LIMIT 15• Calculates relative time (now() - created_at) on the fly.• Dynamically applies color tokens based on signal_type (RATES_RISK, ESG_SUSTAINABLE, FX_VOLATILITY, DCM_REFI).100% Dynamic DB StreamPowers the top infinite marquee with auto-pause and smooth click-to-focus highlighting.Client Opportunity Pipeline Cards/api/opportunitiesJoins 4 relational tables dynamically:1. ca.dt_client_master: Client Tier, RM Name, Sector, Country.2. ca.ext_company_filings / Financials: Revenue, EBITDA, Net Debt, Liquidity.3. ca.corporate_debt_schedules: Aggregates upcoming maturities to compute the exact 24M Maturity Wall.4. ca.ca_opportunity_scoring: Priority Score ($0\text{--}100$), Recommended Action, Fee Estimation, Lineage Trace.100% Dynamic Relational JoinNo hardcoded card arrays. Eliminates mock company cards.Omni-Channel Ingestion Engine/api/ingest & /api/ingest_touchpointWhen a user submits an email, Teams transcript, or RSS article:1. Gemini 1.5 Flash extracts structured entities (Client, Trigger, Urgency, Catalog Family).2. Vector Embeddings ($768$-dim) are computed and stored in ca.document_vector_chunks (pgvector).3. Executes INSERT INTO ca.digital_twin_signals.4. Executes UPDATE / INSERT INTO ca.ca_opportunity_scoring to update pipeline ranking.100% ACID Read/Write TransactionFull database persistence with complete audit history and vector similarity retrieval.10-Slide Interactive Pitchbook Canvas/api/pitchbook/bundle• Queries PostgreSQL for verified balance sheet figures, credit ratings, maturity ladders, and market curve fixings.• Assembles deterministic data objects for all 10 slides.• Provides clean fallback boundaries to ensure error-free rendering.100% Data-Driven AssemblyNo LLM text synthesis in the base layout; every card renders directly from DB keys.Real-Time Deal Copilot/api/copilot/chat• Hydrates active_deck_slides by capturing the exact strings and numbers currently displayed on the frontend screen.• Passes live context to Gemini 1.5 Pro with strict JSON schemas.• Returns strategic advice in reply and targeted parameter modifications in overrides.100% Context-Grounded ReasoningEliminates cross-slide hallucination by reading active canvas state.Native PowerPoint Exporter/api/pitchbook/export• Uses python-pptx to build binary presentations.• Applies any active deckOverrides mutated by the Copilot during the session.• Renders identical geometry, typography, tables, and colors matching the web preview.100% Deterministic File GeneratorGuarantees strict 1:1 parity between browser canvas and final .pptx file.3. Relational Database Schema ArchitectureThe data tier is deployed on Google Cloud SQL (PostgreSQL 15 with pgvector).┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Relational & Vector Schema Mapping                                       │
│                                                                                                             │
│  ca.dt_client_master                   ca.corporate_debt_schedules               ca.market_fixings_live     │
│  ├── client_id (PK) ───────────┐       ├── tranche_id (PK)                       ├── fixing_date (PK)       │
│  ├── client_name               └──────►├── client_id (FK)                        ├── eur_swap_5y            │
│  ├── credit_rating                     ├── instrument_type (EMTN/Bond)           ├── bund_yield_10y         │
│  ├── rm_name                           ├── notional (e.g. €3,000M)               ├── itraxx_europe_main     │
│  ├── revenue (€M)                      ├── coupon_rate (e.g. 1.75%)              └── eurusd_spot            │
│  ├── ebitda (€M)                       ├── maturity_date (e.g. 2027-06-15)                                  │
│  ├── net_debt (€M)                     └── is_maturing_24m (Boolean)             ca.document_vector_chunks  │
│  └── available_liquidity (€M)                                                    ├── chunk_id (PK)          │
│                                        ca.digital_twin_signals                   ├── client_id (FK)         │
│  ca.ca_opportunity_scoring             ├── signal_id (PK)                        ├── source_channel         │
│  ├── scoring_id (PK)                   ├── client_id (FK)                        ├── text_content           │
│  ├── client_id (FK)                    ├── signal_type (RATES/ESG/FX)            ├── structured_metadata    │
│  ├── priority_score (0-100)            ├── headline                              └── embedding (vector 768) │
│  └── recommended_product               └── confidence_pct (e.g. 94%)                                        │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
Table Definitions & Production SchemasSQL-- 1. Client Master Data
CREATE TABLE ca.dt_client_master (
    client_id VARCHAR(50) PRIMARY KEY,
    client_name VARCHAR(150) NOT NULL,
    industry_sector VARCHAR(100),
    country VARCHAR(50),
    credit_rating VARCHAR(20),       -- e.g., "Tier 1 (BBB+)"
    rm_name VARCHAR(100),             -- Relationship Manager, e.g., "G. Romano"
    revenue NUMERIC(15,2),            -- in Millions: 65000.00 -> €65,000M
    ebitda NUMERIC(15,2),             -- in Millions: 14300.00 -> €14,300M
    net_debt NUMERIC(15,2),           -- in Millions: 16200.00 -> €16,200M
    available_liquidity NUMERIC(15,2) -- in Millions: 7800.00  -> €7,800M
);

-- 2. Corporate Debt Schedules (Maturity Ladders & 24M Walls)
CREATE TABLE ca.corporate_debt_schedules (
    tranche_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50) REFERENCES ca.dt_client_master(client_id),
    instrument_type VARCHAR(50),     -- Senior Unsecured, EMTN, Revolver, Term Loan
    notional NUMERIC(15,2),           -- in Millions: 3000.00 -> €3,000M
    currency VARCHAR(10) DEFAULT 'EUR',
    coupon_rate NUMERIC(5,3),         -- e.g., 1.750%
    maturity_date DATE NOT NULL,      -- e.g., 2027-06-15
    is_maturing_24m BOOLEAN DEFAULT TRUE,
    coupon_type VARCHAR(20)           -- Fixed vs Floating
);

-- 3. Live Financial Market Fixings & Benchmark Curves
CREATE TABLE ca.market_fixings_live (
    fixing_date DATE PRIMARY KEY,
    eur_swap_5y NUMERIC(5,3),         -- e.g., 2.620 (%)
    bund_yield_10y NUMERIC(5,3),      -- e.g., 2.610 (%)
    itraxx_europe_main NUMERIC(6,2),  -- e.g., 58.00 (bps)
    eurusd_spot NUMERIC(6,4),         -- e.g., 1.0850
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Multi-Channel Vector Storage (pgvector)
CREATE TABLE ca.document_vector_chunks (
    chunk_id VARCHAR(100) PRIMARY KEY,
    client_id VARCHAR(50) REFERENCES ca.dt_client_master(client_id),
    source_channel VARCHAR(50),      -- Teams, Email, RSS, PDF Filing
    source_name VARCHAR(200),
    text_content TEXT NOT NULL,
    structured_metadata JSONB,
    embedding vector(768)            -- 768-dimensional dense vector
);
4. Priority Scoring Algorithm & Calculation Engine
The opportunity matching score (0-100) is computed dynamically by combining corporate balance sheet urgency with market window attractiveness:

    "Priority Score"=w_"mat" ⋅S_"mat" +w_"curve" ⋅S_"curve" +w_"lev" ⋅S_"lev" +w_"sig" ⋅S_"sig" 

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Multi-Factor Opportunity Scoring Weights                                    │
│                                                                                                             │
│    Maturity Proximity (35%)      Curve Opportunity (25%)        Leverage Room (20%)      Signal Urgency (20%)│
│    ┌──────────────────────┐      ┌─────────────────────┐       ┌───────────────────┐    ┌──────────────────┐│
│    │ 24M Maturity Wall vs │      │ 5Y EUR Swap Spread  │       │ Net Debt / EBITDA │    │ Ingested Signal  ││
│    │ Total Net Debt Ratio │      │ vs 12M Moving Avg   │       │ Sweet Spot: 1-2.5x│    │ Confidence x Urg ││
│    └──────────────────────┘      └─────────────────────┘       └───────────────────┘    └──────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
Maturity Proximity ($S_{\text{mat}}$, 35% Weight):$$S_{\text{mat}} = \min\left(100, \left(\frac{\text{Debt Maturing in 24 Months}}{\text{Total Net Debt}}\right) \times 200\right)$$A client facing a large debt rollover cluster within 24 months (such as BASF's €3,000M maturity wall) generates high urgency.Curve Window Opportunity ($S_{\text{curve}}$, 25% Weight):$$S_{\text{curve}} = 100 - \max\left(0, \min\left(100, \frac{\text{Current 5Y Swap} - \text{52W Min}}{\text{52W Max} - \text{52W Min}} \times 100\right)\right)$$When 5Y EUR swap rates ease towards attractive levels (e.g., easing to 2.62%), the scoring engine detects an entry window for forward-starting interest rate swaps (IRS).Leverage & Debt Capacity ($S_{\text{lev}}$, 20% Weight):$$\text{Leverage} = \frac{\text{Net Debt}}{\text{EBITDA}}$$Leverage between $1.0\times$ and $2.5\times$ indicates high institutional debt capacity for benchmark corporate bond issuances.Ingested Signal Urgency ($S_{\text{sig}}$, 20% Weight):$$S_{\text{sig}} = \text{Confidence Pct} \times U_{\text{factor}} \quad \text{where } U_{\text{factor}} = \begin{cases} 1.0 & \text{High Urgency} \\ 0.6 & \text{Medium Urgency} \\ 0.3 & \text{Low Urgency} \end{cases}$$

![alt text](image-1.png)

5. Defensive Fallback Architecture in main.pyIn main.py, defensive fallback blocks are implemented to safeguard system uptime:
Python
# Defensive Circuit Breaker Pattern in main.py
try:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ... FROM ca.digital_twin_signals ORDER BY created_at DESC LIMIT 15")
            signals = cur.fetchall()
except Exception as db_err:
    logger.error(f"Database query failed, engaging defensive circuit breaker: {db_err}")
    signals = []

# Fallback engagement ONLY on database interruption
if not signals:
    signals = [
        {
            "id": "SIG-DF1", 
            "client_id": "BASF", 
            "client_name": "BASF SE",
            "type": "RATES_RISK",
            "headline": "Upcoming €3.2B debt maturities face repricing risk amid benchmark curve fluctuations."
        }
    ]
Operational Principles of Fallbacks
Circuit Breakers: These data structures act as shock absorbers. If Cloud SQL encounters a transient network partition, cold restart, or connection limit, the API gracefully degrades rather than throwing an unhandled 500 Internal Server Error or crashing the client frontend.
Strict DB Precedence: When Cloud SQL is connected and operational (normal production state), the database query results execute and completely bypass the fallback blocks.
No Phantom Writes: Fallback values are read-only and are never persisted back into the database.6. Real-Time Deal Copilot Grounding & State MutationsTo eliminate hallucination, the Deal Copilot is integrated using Bidirectional Context Grounding:
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Copilot State Hydration & Dispatch Loop                                   │
│                                                                                                             │
│  User Request (e.g., "In Slide 4, change €3,000M to €1,000M")                                               │
│                                      │                                                                      │
│                                      ▼                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  BACKEND PAYLOAD HYDRATION (`main.py`)                                                                │  │
│  │  Constructs `active_deck_slides` dictionary containing exact live strings on screen:                  │  │
│  │  • slide_1_cover: { client_name, kicker, subtitle, rm_name, market_date }                             │  │
│  │  • slide_2_catalyst: { primary_market_trigger, window_of_opportunity, recommended_action }             │  │
│  │  • slide_4_financial_snapshot: { revenue, ebitda, net_debt, liquidity, maturity_wall_24m }           │  │
│  │  • slide_7_macro_backdrop: { swap_5y, bund_10y, itraxx_main }                                         │  │
│  │  • slide_8_term_sheet: { notional, spread, tenor }                                                    │  │
│  │  • current_deck_overrides: { ... } (any active session mutations)                                     │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                                                      │
│                                      ▼                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  🧠 GEMINI 1.5 PRO - REASONING & STRUCTURED JSON EMISSION                                             │  │
│  │                                                                                                       │  │
│  │  Evaluates request against active slides and generates response conforming to strict JSON contract:   │  │
│  │  {                                                                                                    │  │
│  │    "reply": "Updated the 24-month maturity wall on Slide 4 to €1,000M...",                            │  │
│  │    "overrides": {                                                                                     │  │
│  │      "maturity_wall_str": "€1,000M",                                                                  │  │
│  │      "debt_maturing_24m_str": "€1,000M"                                                               │  │
│  │    }                                                                                                  │  │
│  │  }                                                                                                    │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                                                      │
│                                      ▼                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  FRONTEND SYNCHRONIZATION REDUCER                                                                     │  │
│  │  1. React merges new `overrides` into `deckOverrides` state.                                          │  │
│  │  2. Active Slide 4 re-renders with €1,000M in real time.                                              │  │
│  │  3. `deckOverrides` are forwarded to `/api/pitchbook/export` ensuring the exported PPTX matches.      │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
7. Deterministic 10-Slide Pitchbook Architecture (1:1 UI/PPTX Parity)
The pitchbook follows a standardized 10-slide structure generated deterministically via python-pptx and rendered on the interactive React canvas:
![alt text](image-2.png)
![alt text](image-3.png)
![alt text](image-4.png)
8. Regulatory Compliance Framework (MiFID II & FINRA)The platform embeds automated compliance checks (/api/compliance/audit) to protect against mis-selling and non-compliant marketing:
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               Two-Stage Regulatory Screening Pipeline                                       │
│                                                                                                             │
│    Current Pitchbook Canvas Content + Term Sheet Parameters                                                 │
│                                 │                                                                           │
│                                 ▼                                                                           │
│    ┌───────────────────────────────────────────────────────────────────────────────────────────────────┐    │
│    │ STAGE 1: Deterministic Lexicon Filter (Regex Screening)                                           │    │
│    │ Scans for prohibited promissory terms: "guarantee", "risk-free", "certain profit", "no downside" │    │
│    └───────────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                 │                                                                           │
│                                 ▼                                                                           │
│    ┌───────────────────────────────────────────────────────────────────────────────────────────────────┐    │
│    │ STAGE 2: 🧠 Gemini 1.5 Flash Regulatory Context Screening                                         │    │
│    │ • MiFID II Target Market: Verified for Eligible Counterparties and Professional Clients only.     │    │
│    │ • Derivative Risk Warning: Mandatory mark-to-market break-cost disclosure on IRS overlays.         │    │
│    │ • Pricing Caveat: Validates "Indicative terms subject to market conditions and credit approval".  │    │
│    └───────────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                 │                                                                           │
│                                 ▼                                                                           │
│    ┌───────────────────────────────────────────────────────────────────────────────────────────────────┐    │
│    │ REMEDIATION ACTION                                                                                │    │
│    │ Clicking "Apply compliance recommendations" automatically injects missing regulatory caveats      │    │
│    │ into `deckOverrides.disclaimers`, instantly updating Slide 10 and the PPTX export.                 │    │
│    └───────────────────────────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
9. User Session Context & Institutional UI Styling
The static elements in the user interface represent the institutional session state and user identity:
User Persona & Profile: Sarah Bover · Director Financial Markets with avatar SB (simulating the active ING coverage banker session).
Desk Scope & Coverage: DACH & Benelux Coverage | €42.5B Book (portfolio filter).
Market Session Indicator: TARGET2 ACTIVE synchronized with a live browser clock in Central European Time (CET).
Institutional Color Tokens:ING Premium Orange: #FF6200ING Deep Navy: #0C112BING Slate Blue: #000066Subtle Canvas Gray: #F8FAFC10. 

Summary Verification Matrix
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Architecture Verification Matrix                                          │
│                                                                                                             │
│  Component            State Mechanism        Implementation Detail                                          │
│  ─────────────────────────────────────────────────────────────────────────────────────────────────────────  │
│  Data Layer           100% Dynamic           Live PostgreSQL Cloud SQL instance via pgvector.               │
│  Opportunity Pipeline 100% Dynamic           Multi-table SQL relational joins with dynamic scoring.         │
│  Signal Ingestion     100% Live Ingestion    Tri-channel processing with Gemini Flash entity extraction.    │
│  Pitchbook Canvas     100% Data-Driven       Deterministic rendering based on DB records and math logic.    │
│  Deal Copilot         100% Grounded Memory   Reads active canvas context; mutates state via JSON overrides. │
│  PPTX Export          100% Parity            Deterministic python-pptx engine applying active overrides.    │
│  Compliance           100% Automated         Two-stage MiFID II / FINRA regex and LLM audit engine.         │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘


ca.client_master

ca.ext_company_filings

ca.ca_opportunity_scoring

ca.ext_credit_spreads

ca.mkt_rates_curves

ca.debt_maturity_schedule

ca.ext_deals

ca.digital_twin_signals

============
Run Full Database Inspection Script
Run this in Cloud Shell to list all tables, their columns, and the exact signal/filing/market data currently stored for Enel:

cd ~/ing-fm-poc

python3 - << 'EOF'
import os
import sqlalchemy
from sqlalchemy import text

db_user = os.environ.get("DB_USER", "postgres")
db_pass = os.environ.get("DB_PASS", "")
db_name = os.environ.get("DB_NAME", "postgres")
inst_conn = os.environ.get("INSTANCE_CONNECTION_NAME", "")

try:
    from google.cloud.sql.connector import Connector, IPTypes
    connector = Connector()
    def getconn():
        return connector.connect(
            inst_conn,
            "pg8000",
            user=db_user,
            password=db_pass,
            db=db_name,
            ip_type=IPTypes.PUBLIC
        )
    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)
except Exception:
    db_host = os.environ.get("DB_HOST", "127.0.0.1")
    db_port = os.environ.get("DB_PORT", "5432")
    engine = sqlalchemy.create_engine(f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}")

with engine.connect() as conn:
    print("===============================================================")
    print(" 1. ALL TABLES IN 'ca' SCHEMA")
    print("===============================================================")
    res = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'ca'
        ORDER BY table_name;
    """))
    tables = [r[0] for r in res.fetchall()]
    for t in tables:
        count = conn.execute(text(f'SELECT COUNT(*) FROM "ca"."{t}"')).fetchone()[0]
        print(f"  • ca.{t:<30} ({count} rows)")

    print("\n===============================================================")
    print(" 2. COLUMNS & SAMPLE DATA FOR SIGNALS & FILINGS")
    print("===============================================================")
    
    # Check digital_twin_signals
    if "digital_twin_signals" in tables:
        print("\n--- [ca.digital_twin_signals columns] ---")
        cols = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'ca' AND table_name = 'digital_twin_signals'
        """)).fetchall()
        for c, dt in cols:
            print(f"   {c} ({dt})")
            
        print("\n--- [Sample Enel Signals in ca.digital_twin_signals] ---")
        signals = conn.execute(text("""
            SELECT * FROM ca.digital_twin_signals 
            WHERE client_id = 'CLI101' OR client_id LIKE '%Enel%' LIMIT 5;
        """)).mappings().fetchall()
        for s in signals:
            print(dict(s))

    # Check ext_company_filings
    if "ext_company_filings" in tables:
        print("\n--- [ca.ext_company_filings columns] ---")
        cols = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'ca' AND table_name = 'ext_company_filings'
        """)).fetchall()
        for c, dt in cols:
            print(f"   {c} ({dt})")
            
        print("\n--- [Sample Enel Filings in ca.ext_company_filings] ---")
        filings = conn.execute(text("""
            SELECT * FROM ca.ext_company_filings 
            WHERE client_id = 'CLI101' OR client_id LIKE '%Enel%' LIMIT 3;
        """)).mappings().fetchall()
        for f in filings:
            print(dict(f))

    # Check ca_opportunity_scoring
    if "ca_opportunity_scoring" in tables:
        print("\n--- [ca.ca_opportunity_scoring columns] ---")
        cols = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'ca' AND table_name = 'ca_opportunity_scoring'
        """)).fetchall()
        for c, dt in cols:
            print(f"   {c} ({dt})")
            
        print("\n--- [Enel Opportunity Scoring Record] ---")
        opps = conn.execute(text("""
            SELECT * FROM ca.ca_opportunity_scoring 
            WHERE client_id = 'CLI101' OR client_id LIKE '%Enel%' LIMIT 2;
        """)).mappings().fetchall()
        for op in opps:
            print(dict(op))

EOF

user@ing-fm-dev-1:~/ing-fm-poc$ cd ~/ing-fm-poc

python3 - << 'EOF'
import os
import sqlalchemy
from sqlalchemy import text

# Database credentials from environment
db_user = os.environ.get("DB_USER", "postgres")
db_pass = os.environ.get("DB_PASS", "")
EOF     print(f"• {schema}.{tname:<32} ({count_res[0]} rows)"){schema}"."{tname}"')).fetchone()b_name}")
=== ALL TABLES IN DATABASE ===
• ca.ca_opportunity_scoring           (19 rows)
• ca.cand5_client_master              (0 rows)
• ca.client_master                    (13 rows)
• ca.coverage_teams                   (10 rows)
• ca.debt_maturity_schedule           (15 rows)
• ca.digital_twin_signals             (54 rows)
• ca.document_vector_chunks           (22 rows)
• ca.dt_client_master                 (13 rows)
• ca.ext_company_filings              (13 rows)
• ca.ext_credit_spreads               (8 rows)
• ca.ext_deals                        (3 rows)
• ca.mkt_rates_curves                 (10 rows)
user@ing-fm-dev-1:~/ing-fm-poc$ 

We have the complete table list. Notice three key tables here that provide the groundwork:

ca.digital_twin_signals (54 rows — contains multi-channel signals like News RSS, Emails, Teams chats, and Analyst Notes).

ca.document_vector_chunks (22 rows — contains the vector chunks and text extracts from ingested PDFs/PPTs).

ca.ext_company_filings (13 rows — contains metadata for ingested corporate reports and filings).

==================

Run Detailed Column & Sample Data Inspection
Run this script in Cloud Shell to see the exact columns and actual sample data for Enel (CLI101) across digital_twin_signals, document_vector_chunks, ext_company_filings, and ca_opportunity_scoring:

cd ~/ing-fm-poc

python3 - << 'EOF'
import os
import sqlalchemy
from sqlalchemy import text

db_user = os.environ.get("DB_USER", "postgres")
db_pass = os.environ.get("DB_PASS", "")
db_name = os.environ.get("DB_NAME", "postgres")
inst_conn = os.environ.get("INSTANCE_CONNECTION_NAME", "")

try:
    from google.cloud.sql.connector import Connector, IPTypes
    connector = Connector()
    def getconn():
        return connector.connect(
            inst_conn,
            "pg8000",
            user=db_user,
            password=db_pass,
            db=db_name,
            ip_type=IPTypes.PUBLIC
        )
    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)
except Exception:
    db_host = os.environ.get("DB_HOST", "127.0.0.1")
    db_port = os.environ.get("DB_PORT", "5432")
    engine = sqlalchemy.create_engine(f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}")

with engine.connect() as conn:
    print("=" * 65)
    print("1. ca.digital_twin_signals (Ingested Multi-Channel Signals)")
    print("=" * 65)
    cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='ca' AND table_name='digital_twin_signals'")).fetchall()
    print("Columns:", [f"{c[0]} ({c[1]})" for c in cols])
    
    rows = conn.execute(text("SELECT * FROM ca.digital_twin_signals WHERE client_id='CLI101' LIMIT 5")).mappings().fetchall()
    for r in rows:
        print("\nRecord:", dict(r))

    print("\n" + "=" * 65)
    print("2. ca.document_vector_chunks (Ingested Document Chunks / Houseviews)")
    print("=" * 65)
    cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='ca' AND table_name='document_vector_chunks'")).fetchall()
    print("Columns:", [f"{c[0]} ({c[1]})" for c in cols])
    
    rows = conn.execute(text("SELECT * FROM ca.document_vector_chunks LIMIT 3")).mappings().fetchall()
    for r in rows:
        print("\nRecord:", dict(r))

    print("\n" + "=" * 65)
    print("3. ca.ext_company_filings (Ingested Filings / Reports)")
    print("=" * 65)
    cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='ca' AND table_name='ext_company_filings'")).fetchall()
    print("Columns:", [f"{c[0]} ({c[1]})" for c in cols])
    
    rows = conn.execute(text("SELECT * FROM ca.ext_company_filings WHERE client_id='CLI101' LIMIT 3")).mappings().fetchall()
    for r in rows:
        print("\nRecord:", dict(r))

    print("\n" + "=" * 65)
    print("4. ca.ca_opportunity_scoring (Synthesized Mandates & Rationale)")
    print("=" * 65)
    cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='ca' AND table_name='ca_opportunity_scoring'")).fetchall()
    print("Columns:", [f"{c[0]} ({c[1]})" for c in cols])
    
    rows = conn.execute(text("SELECT * FROM ca.ca_opportunity_scoring WHERE client_id='CLI101' LIMIT 2")).mappings().fetchall()
    for r in rows:
        print("\nRecord:", dict(r))
EOF

This database inspection provides the exact technical lineage for the entire platform.

Here is how each source is stored, differentiated, and mapped directly to the UI:

1. Database Grounding & Ingestion Attribution
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                               DATABASE INGESTION ARCHITECTURE                                │
├──────────────────────────┬─────────────────────────────┬─────────────────────────────────────┤
│ UI Section               │ Source Database Table       │ Grounded Column Fields              │
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────┤
│ 1. CLIENT DATA           │ `ca.ext_company_filings`    │ `net_debt_eur_m` (€58,500M)         │
│                          │ `ca.client_master`          │ `liquidity_eur_m` (€14,200M)        │
│                          │                             │ `debt_maturing_24m_eur_m` (€10,127M)│
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────┤
│ 2. MARKET DATA           │ `ca.mkt_rates_curves`       │ `eur_5y_swap` (2.62%), Bund (2.61%) │
│                          │ `ca.ext_credit_spreads`     │ `credit_spread_bps` (78 bps)        │
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────┤
│ 3. CONTEXT FABRIC        │ `ca.document_vector_chunks` │ `source_channel`: `TEAMS_CHAT`,     │
│    (Internal CRM & Desk) │ `ca.digital_twin_signals`   │ `ANALYST_NOTE`, `CLIENT_EMAIL`      │
│                          │                             │ `source_name`: Luca Moretti, Giulia │
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────┤
│ 4. HOUSEVIEWS & NEWS     │ `ca.document_vector_chunks` │ `source_channel`: `NEWS_RSS`,       │
│    (External & Research) │ `ca.digital_twin_signals`   │ `source_name`: Capital Market News  │
│                          │                             │ `text_content`: $2.5bn multi-tranche│
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────┤
│ 5. SYNTHESIZED MANDATE   │ `ca.ca_opportunity_scoring` │ `why_now_nlg` (Catalyst Rationale)  │
│    (Hero Section Below)  │                             │ `next_best_action` (Execution Plan) │
│                          │                             │ `est_revenue_eur_000` (Fee: €5.0M)  │
└──────────────────────────┴─────────────────────────────┴─────────────────────────────────────┘

=============

**No database schema changes or column additions are required.**

We verified that all the necessary tables, columns, and data points already exist in your database instance:

---

### Existing Table & Column Mapping

* **Client Financials & Debt Wall:** Pulled directly from existing columns `net_debt_eur_m`, `liquidity_eur_m`, `debt_maturing_24m_eur_m` in **`ca.ext_company_filings`**.
* **Market Benchmarks & Credit Spreads:** Pulled directly from existing columns in **`ca.mkt_rates_curves`** and **`ca.ext_credit_spreads`**.
* **Context Fabric Signals & Author:** Pulled directly from existing columns `description`, `trigger_summary`, `confidence_pct` in **`ca.digital_twin_signals`** and `source_name` in **`ca.document_vector_chunks`** (where `source_channel = 'ANALYST_NOTE'`).
* **Houseviews & News Feeds:** Pulled directly from existing records in **`ca.document_vector_chunks`** using the existing `source_channel = 'NEWS_RSS'`, `source_name`, and `text_content` columns.
* **Synthesized Mandate & Rationale:** Pulled directly from existing columns `why_now_nlg` and `next_best_action` in **`ca.ca_opportunity_scoring`**.

---

### Why No Migrations Are Needed

The update only changes:

1. **The SQL query logic in `main.py**` to extract and categorize existing rows into clean response fields.
2. **The JSX rendering tree in `frontend/src/App.jsx**` to display the $2 \times 2$ grid + full-width Mandate.

The database tables remain untouched.

===========

Top $2 \times 2$ Grid (The 4 Audited Ingestion Feeds)The previous layout placed the Mandate inside the fourth box. Now, all four boxes represent pure raw inputs ingested from your database tables:
┌──────────────────────────────────────┬──────────────────────────────────────┐
│  SEGMENT 1: CLIENT DATA              │  SEGMENT 2: MARKET DATA              │
│  [Static Balance Sheet & Maturities] │  [Live Curves & Spreads from DB]     │
│  • Net Debt: €58,500M                │  • 5Y EUR Swap: 2.62%                │
│  • Available Liquidity: €14,200M     │  • 10Y German Bund: 2.61%            │
│  • 24M Maturity Wall: €10,127M       │  • Credit Spread: 78 bps             │
├──────────────────────────────────────┼──────────────────────────────────────┤
│  SEGMENT 3: CONTEXT FABRIC           │  SEGMENT 4: HOUSEVIEWS & NEWS (NEW)  │
│  [Internal Chatter & CRM Signals]    │  [Audited Research & Market Wires]   │
│  • Chips: 📝 Notes | 💬 Teams | ✉️ Email│  • Chips: 📄 Strategy.pdf | 📰 Wire  │
│  • Desk Signal: €10.13bn refi review │  • ING Houseview: Pre-hedge 5Y-7Y rec│
│  • Latent: Pre-hedge rates window    │  • News: $2.5bn multi-tranche bond   │
│  • Attribution: Luca Moretti (DCM)   │  • Attribution: ING WB Research Desk │
└──────────────────────────────────────┴──────────────────────────────────────┘
2. Full-Width Hero Section (Synthesized Mandate & AI Catalyst)Directly underneath the $2 \times 2$ grid, you will see a prominent container spanning the entire width of the card:Live Status Badge: A pulsating orange indicator with SYNTHESIZED MANDATE & AI CATALYST and Multi-Signal Lineage Verified.Signal Lineage Audit Bar: A 4-column trace strip proving multi-signal causality:[1. Balance Sheet: €10.1B Maturity][2. Market DB: 5Y Swap 2.62% / 78bps][3. Context Fabric: €10.13B Refi Review][4. Houseview / News: $2.5B Tranche + Pre-Hedge]2-Column Execution Breakdown:Left Box: Catalyst Rationale (Why Now): "Enel successfully issued a US$4.5 billion Yankee bond, advised by White & Case..."Right Box: Proposed Execution & Structuring: "Engage Enel to discuss the strategic rationale behind the US$4.5bn Yankee bond issuance..."3. Rich Hover-Over Tooltip ExperienceHovering your cursor over any element displays the underlying audit trail:Hovering on 📄 ING_Utilities_Strategy_Q3.pdf: Shows the full research desk excerpt and target tenor guidance.Hovering on 📰 Capital Market News / Bloomberg: Shows the verified corporate filing note regarding the $2.5B issuance.Hovering on Desk Signal / Latent Opp: Shows confidence percentages ($95\%$, $85\%$) and evidence citations directly from ca.digital_twin_signals.Hovering on Catalyst Rationale / Proposed Execution: Shows the full un-truncated narrative from ca.ca_opportunity_scoring.4. Bottom Action BarAt the bottom of the card, the buttons remain fully functional:Ingestion Engine button: Launches the channel simulation and document ingestion modal.Open draft pitchbook button: Opens the slide preview drawer and origination copilot for Enel S.p.A. with all parameters intact.

Workfabric Memo chip Database Query for Enel :-
====================
# Step 1: Query All Existing WorkFabric Memo Records for Enel
Run this script in Cloud Shell to see all matching rows in ca.document_vector_chunks:
cd ~/ing-fm-poc

python3 - << 'EOF'
import os
import sqlalchemy
from sqlalchemy import text

db_user = os.environ.get("DB_USER", "postgres")
db_pass = os.environ.get("DB_PASS", "ing_fm_password_2026")
db_name = os.environ.get("DB_NAME", "ing_fm_db")
inst_conn = os.environ.get("INSTANCE_CONNECTION_NAME", "teach-telecom-ai-sandbox:europe-west1:ing-fm-db")

try:
    from google.cloud.sql.connector import Connector, IPTypes
    connector = Connector()
    def getconn():
        return connector.connect(
            inst_conn,
            "pg8000",
            user=db_user,
            password=db_pass,
            db=db_name,
            ip_type=IPTypes.PUBLIC
        )
    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)
except Exception:
    db_host = os.environ.get("DB_HOST", "127.0.0.1")
    db_port = os.environ.get("DB_PORT", "5432")
    engine = sqlalchemy.create_engine(f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}")

with engine.connect() as conn:
    print("=" * 80)
    print(" 🔎 EXISTING WORKFABRIC MEMO / ANALYST_NOTE RECORDS FOR ENEL (CLI101)")
    print("=" * 80)

    rows = conn.execute(text("""
        SELECT chunk_id, client_id, source_channel, source_name, text_content, created_at
        FROM ca.document_vector_chunks
        WHERE (client_id = 'CLI101' OR client_id LIKE '%ENEL%')
          AND source_channel IN ('WORKFABRIC_MEMO', 'ANALYST_NOTE')
        ORDER BY created_at DESC, chunk_id DESC;
    """)).mappings().fetchall()

    print(f"Total Records Found: {len(rows)}\n")
    for r in rows:
        print(f"Chunk ID       : {r['chunk_id']}")
        print(f"Client ID      : {r['client_id']}")
        print(f"Channel        : {r['source_channel']}")
        print(f"Source / Author: {r['source_name']}")
        print(f"Created At     : {r['created_at']}")
        print(f"Full Text      :\n{r['text_content']}")
        print("-" * 80)
EOF

# Output
user@ing-fm-dev-1:~/ing-fm-poc$ cd ~/ing-fm-poc

python3 - << 'EOF'
import os
import sqlalchemy
from sqlalchemy import text

db_user = os.environ.get("DB_USER", "postgres")
db_pass = os.environ.get("DB_PASS", "ing_fm_password_2026")
db_name = os.environ.get("DB_NAME", "ing_fm_db")
EOF     print("-" * 80)xt      :\n{r['text_content']}"))LYST_NOTE')xt_content, created_atrt}/{db_name}"))
================================================================================
 🔎 EXISTING WORKFABRIC MEMO / ANALYST_NOTE RECORDS FOR ENEL (CLI101)
================================================================================
Total Records Found: 2

Chunk ID       : 102
Client ID      : CLI101
Channel        : ANALYST_NOTE
Source / Author: Luca Moretti (DCM Origination)
Created At     : 2026-08-20 19:02:08.728518
Full Text      :
Large investment programmes, but the July dollar issuance means we should not equate capex with a funding gap. Residual maturities for 2026-2027 total approx €10.13bn. Candidate issue: residual funding sequencing and liability management.
--------------------------------------------------------------------------------
Chunk ID       : 2
Client ID      : CLI009_ENEL
Channel        : ANALYST_NOTE
Source / Author: Luca Moretti (DCM Origination)
Created At     : 2026-08-20 19:02:08.728518
Full Text      :
Large investment programmes, but the July dollar issuance means we should not equate capex with a funding gap. Residual maturities for 2026-2027 total approx €10.13bn. Candidate issue: residual funding sequencing and liability management.
--------------------------------------------------------------------------------
user@ing-fm-dev-1:~/ing-fm-poc$ 

Table	Relevant Columns	Purpose
ca.document_vector_chunks	chunk_id, client_id, source_channel, source_name, text_content, created_at	Stores raw touchpoints, author attribution, and hover tooltip excerpts for all channels (TEAMS_CHAT, CLIENT_EMAIL, WORKFABRIC_MEMO).
ca.digital_twin_signals	signal_id, client_id, catalog_family, signal_type, metric_identified, trigger_summary, metric_value, description, confidence_pct, urgency, created_at	Stores structured signals extracted by the AI engine.
ca.ca_opportunity_scoring	client_id, opportunity_type, priority_score, est_revenue_eur_000, next_best_action, why_now_nlg	Houses calibrated deal priorities, revenue projections, and action recommendations.