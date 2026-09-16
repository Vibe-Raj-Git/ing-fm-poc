# dump_baseline.py
#
# Reads the current pristine state from Cloud SQL and writes a complete
# snapshot to baseline_snapshots.json.
#
# Coverage:
#   - All clients in ca.client_master (no whitelist filter)
#   - Every client-scoped table, all columns read by any code path
#   - Global market tables (mkt_rates_curves, ext_credit_spreads) once, at top level
#   - ext_deals (ING track record) for future use
#
# Read-only. Safe to run at any time. Re-running produces an equivalent
# snapshot (modulo created_at timestamps and sequence-driven IDs).

import sys
import json
from datetime import datetime, date
from decimal import Decimal

sys.path.insert(0, "/home/user/ing-fm-poc")
from main import get_db_connection


def _serialize(value):
    """Convert DB types to JSON-safe values."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def fetch(cur, sql, params=None):
    cur.execute(sql, params or ())
    cols = [d[0] for d in cur.description]
    return [
        {col: _serialize(val) for col, val in zip(cols, row)}
        for row in cur.fetchall()
    ]


def main():
    conn, connector = get_db_connection()
    if not conn:
        raise SystemExit("DB connection failed")

    cur = conn.cursor()

    # --- 1. Enumerate all clients ---
    cur.execute("SELECT client_id FROM ca.client_master ORDER BY client_id")
    client_ids = [row[0] for row in cur.fetchall()]
    print(f"Dumping snapshot for {len(client_ids)} clients: {client_ids}")

    # --- 2. Read all client-scoped tables (no whitelist) ---

    client_master_rows = fetch(cur, """
        SELECT client_id, client_name, group_parent, legal_entity,
               industry_sector, country, region, ownership_type,
               tier, hq_country, revenue_eur_m, rm_name, base_ccy
        FROM ca.client_master
        ORDER BY client_id
    """)

    filings_rows = fetch(cur, """
        SELECT filing_id, client_id, reporting_period, net_debt_eur_m,
               liquidity_eur_m, ebitda_eur_m, reported_revenue_eur_m,
               debt_maturing_24m_eur_m, notes
        FROM ca.ext_company_filings
        ORDER BY client_id, reporting_period DESC
    """)

    scoring_rows = fetch(cur, """
        SELECT opportunity_id, client_id, opportunity_type, trigger_source,
               est_revenue_eur_000, propensity_score, value_score,
               priority_score, rank, next_best_action, why_now_nlg
        FROM ca.ca_opportunity_scoring
        ORDER BY client_id, opportunity_id
    """)

    signals_rows = fetch(cur, """
        SELECT signal_id, client_id, catalog_family, signal_type,
               metric_identified, trigger_summary, metric_value,
               description, confidence_pct, urgency, created_at
        FROM ca.digital_twin_signals
        ORDER BY client_id, signal_id
    """)

    chunks_rows = fetch(cur, """
        SELECT chunk_id, client_id, source_channel, source_name,
               text_content, structured_metadata, created_at
        FROM ca.document_vector_chunks
        ORDER BY client_id, chunk_id
    """)

    maturities_rows = fetch(cur, """
        SELECT isin, client_id, instrument_type, amount_eur_m,
               maturity_year, coupon_rate_pct, currency
        FROM ca.debt_maturity_schedule
        ORDER BY client_id, maturity_year, isin
    """)

    coverage_rows = fetch(cur, """
        SELECT client_id, role_title, banker_name, location
        FROM ca.coverage_teams
        ORDER BY client_id, role_title
    """)

    deals_rows = fetch(cur, """
        SELECT deal_id, client_id, deal_type, volume_eur_m,
               role, deal_date
        FROM ca.ext_deals
        ORDER BY client_id, deal_id
    """)

    # --- 3. Read global market tables once (not per-client) ---

    mkt_rates_rows = fetch(cur, """
        SELECT curve_id, curve_date, currency, tenor,
               swap_rate_pct, govt_yield_pct, category
        FROM ca.mkt_rates_curves
        ORDER BY currency, curve_id
    """)

    credit_spreads_rows = fetch(cur, """
        SELECT spread_id, quote_date, issuer_or_rating, sector,
               tenor, spread_bps, all_in_yield_pct, source
        FROM ca.ext_credit_spreads
        ORDER BY issuer_or_rating, tenor, spread_id
    """)

    # --- 4. Group client-scoped rows per client ---

    def group_by_client(rows):
        out = {}
        for r in rows:
            cid = r["client_id"]
            out.setdefault(cid, []).append(r)
        return out

    cm_by_cid   = group_by_client(client_master_rows)
    fl_by_cid   = group_by_client(filings_rows)
    os_by_cid   = group_by_client(scoring_rows)
    sig_by_cid  = group_by_client(signals_rows)
    ch_by_cid   = group_by_client(chunks_rows)
    mat_by_cid  = group_by_client(maturities_rows)
    cov_by_cid  = group_by_client(coverage_rows)
    dl_by_cid   = group_by_client(deals_rows)

    # --- 5. Assemble ---

    snapshot = {
        "_meta": {
            "version": "1.0",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "client_count": len(client_ids),
            "note": (
                "Complete snapshot of client-scoped and global tables. "
                "Client-scoped tables are keyed by client_id under 'clients'. "
                "Global tables are at top level and are NOT reset per-client."
            ),
        },
        "clients": {},
        "global": {
            "mkt_rates_curves": mkt_rates_rows,
            "ext_credit_spreads": credit_spreads_rows,
        },
    }

    for cid in client_ids:
        snapshot["clients"][cid] = {
            "client_master":          cm_by_cid.get(cid, []),
            "ext_company_filings":    fl_by_cid.get(cid, []),
            "ca_opportunity_scoring": os_by_cid.get(cid, []),
            "digital_twin_signals":   sig_by_cid.get(cid, []),
            "document_vector_chunks": ch_by_cid.get(cid, []),
            "debt_maturity_schedule": mat_by_cid.get(cid, []),
            "coverage_teams":         cov_by_cid.get(cid, []),
            "ext_deals":              dl_by_cid.get(cid, []),
        }

    # --- 6. Write ---

    out_path = "baseline_snapshots.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, default=str)

    # --- 7. Summary ---

    print(f"\nWritten: {out_path}")
    print(f"  Global: mkt_rates_curves={len(mkt_rates_rows)}, ext_credit_spreads={len(credit_spreads_rows)}")
    print()
    print("  Per-client row counts:")
    for cid in client_ids:
        c = snapshot["clients"][cid]
        counts = ", ".join(f"{k}={len(v)}" for k, v in c.items())
        print(f"    {cid}: {counts}")

    cur.close()
    conn.close()
    if connector:
        connector.close()


if __name__ == "__main__":
    main()