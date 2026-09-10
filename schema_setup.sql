CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS ca;

CREATE TABLE IF NOT EXISTS ca.client_master (
    client_id VARCHAR(50) PRIMARY KEY,
    client_name VARCHAR(255),
    group_parent VARCHAR(255),
    legal_entity VARCHAR(255),
    industry_sector VARCHAR(100),
    country VARCHAR(100),
    region VARCHAR(100),
    ownership_type VARCHAR(100),
    tier VARCHAR(50),
    hq_country VARCHAR(100),
    revenue_eur_m NUMERIC,
    rm_name VARCHAR(255),
    base_ccy VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS ca.debt_maturity_schedule (
    isin VARCHAR(50),
    client_id VARCHAR(50),
    instrument_type VARCHAR(100),
    amount_eur_m NUMERIC,
    maturity_year INTEGER,
    coupon_rate_pct NUMERIC,
    currency VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS ca.cand5_client_master (
    client_id VARCHAR(50),
    client_name VARCHAR(255),
    group_parent VARCHAR(255),
    legal_entity VARCHAR(255),
    industry_sector VARCHAR(100),
    country VARCHAR(100),
    region VARCHAR(100),
    ownership_type VARCHAR(100),
    client_tier VARCHAR(50),
    base_ccy VARCHAR(10),
    maps_to_original_id VARCHAR(50),
    approach_overall_assessment TEXT
);

CREATE TABLE IF NOT EXISTS ca.dt_client_master (
    client_id VARCHAR(50),
    client_name VARCHAR(255),
    group_parent VARCHAR(255),
    legal_entity VARCHAR(255),
    industry_sector VARCHAR(100),
    country VARCHAR(100),
    region VARCHAR(100),
    ownership_type VARCHAR(100),
    client_tier VARCHAR(50),
    base_ccy VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS ca.ext_deals (
    deal_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50),
    deal_type VARCHAR(100),
    volume_eur_m NUMERIC,
    role VARCHAR(100),
    deal_date DATE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS ca.ext_company_filings (
    filing_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50),
    reporting_period VARCHAR(50),
    net_debt_eur_m NUMERIC,
    liquidity_eur_m NUMERIC,
    ebitda_eur_m NUMERIC,
    reported_revenue_eur_m NUMERIC,
    debt_maturing_24m_eur_m NUMERIC,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS ca.mkt_rates_curves (
    curve_id SERIAL PRIMARY KEY,
    curve_date DATE,
    currency VARCHAR(10),
    tenor VARCHAR(20),
    swap_rate_pct NUMERIC,
    govt_yield_pct NUMERIC,
    category VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS ca.ext_credit_spreads (
    spread_id SERIAL PRIMARY KEY,
    quote_date DATE,
    issuer_or_rating VARCHAR(100),
    sector VARCHAR(100),
    tenor VARCHAR(20),
    spread_bps NUMERIC,
    all_in_yield_pct NUMERIC,
    source VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS ca.coverage_teams (
    team_id SERIAL PRIMARY KEY,
    client_id VARCHAR(50),
    rm_name VARCHAR(255),
    role VARCHAR(100),
    email VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS ca.digital_twin_signals (
    signal_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50),
    catalog_family VARCHAR(100),
    signal_type VARCHAR(100),
    metric_identified TEXT,
    trigger_summary TEXT,
    metric_value VARCHAR(255),
    description TEXT,
    confidence_pct INTEGER,
    urgency VARCHAR(50),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ca.document_vector_chunks (
    chunk_id BIGSERIAL PRIMARY KEY,
    client_id VARCHAR(50),
    source_channel VARCHAR(100),
    source_name VARCHAR(255),
    text_content TEXT,
    structured_metadata JSONB,
    embedding vector(768),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ca.ca_opportunity_scoring (
    opportunity_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50),
    opportunity_type VARCHAR(100),
    trigger_source TEXT,
    est_revenue_eur_000 NUMERIC,
    propensity_score INTEGER,
    value_score INTEGER,
    priority_score INTEGER,
    rank INTEGER,
    next_best_action TEXT,
    why_now_nlg TEXT
);

CREATE TABLE IF NOT EXISTS ca.ca_opportunity_scoring_backup AS 
SELECT * FROM ca.ca_opportunity_scoring WITH NO DATA;
