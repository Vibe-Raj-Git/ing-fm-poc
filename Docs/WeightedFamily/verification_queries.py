#!/usr/bin/env python3
"""Verification queries for the ING FM Deal Intelligence platform.

Read-only inspection script. Runs 14 SQL queries against the ca schema to
demonstrate the platform's data architecture, ingestion state, dedup logic,
reset mechanism, and runtime brand toggle.

Usage:
  python3 verification_queries.py           # menu mode — pick a query
  python3 verification_queries.py --all     # run all queries
  python3 verification_queries.py --summary # one-line-per-query health check
  python3 verification_queries.py 5         # run query 5 only

Architect & Developer: Rajarshi Pathak (rajarshi.pathak@cognizant.com)
"""
import sys
import json
from pathlib import Path

# Path to the repo root — adjust if running from elsewhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from main import get_db_connection, ACTIVE_BRAND, BRAND_PROFILES, \
    _DEMO_CLIENT_IDS, _CREDIT_RATINGS, _FAMILY_KEYWORD_WEIGHTS

BASELINE_PATH = Path(__file__).resolve().parent.parent.parent / "baseline_snapshots.json"


def _connect():
    return get_db_connection()


def _close(conn, connector, cur=None):
    if cur is not None:
        cur.close()
    conn.close()
    if connector:
        connector.close()


def _hdr(n, title):
    print()
    print("=" * 78)
    print(f"  Q{n:>2}  {title}")
    print("=" * 78)


# ═══════════════════════════════════════════════════════════════════════════
def q01_schema_inventory():
    _hdr(1, "Schema inventory — tables in ca")
    conn, connector = _connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'ca' ORDER BY table_name
    """)
    rows = cur.fetchall()
    print(f"  Tables in schema ca: {len(rows)}")
    for r in rows:
        print(f"    {r[0]}")
    _close(conn, connector, cur)


def q02_client_scope():
    _hdr(2, "Client scope — the demo book")
    conn, connector = _connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT client_id, client_name, industry_sector, tier, hq_country
        FROM ca.client_master ORDER BY client_id
    """)
    print(f"  {'client_id':10s} {'client_name':32s} {'sector':32s} {'tier':8s}")
    print("  " + "-" * 84)
    for r in cur.fetchall():
        print(f"  {r[0]:10s} {(r[1] or ''):32s} {(r[2] or ''):32s} {(r[3] or ''):8s}")
    _close(conn, connector, cur)


def q03_opportunity_anchor():
    _hdr(3, "Opportunity anchor — curated narratives")
    conn, connector = _connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT opportunity_id, client_id, opportunity_type, priority_score,
               LEFT(trigger_source, 100), LEFT(why_now_nlg, 100),
               LEFT(next_best_action, 100)
        FROM ca.ca_opportunity_scoring
        WHERE client_id IN ('CLI101', 'CLI103')
        ORDER BY client_id
    """)
    for r in cur.fetchall():
        print(f"  === {r[0]} | {r[1]} | {r[2]} ===")
        print(f"    priority_score:    {r[3]}")
        print(f"    trigger_source:    {r[4]}...")
        print(f"    why_now_nlg:       {r[5]}...")
        print(f"    next_best_action:  {r[6]}...")
        print()
    _close(conn, connector, cur)


def q04_balance_sheet():
    _hdr(4, "Balance sheet truth (with NULL-row mitigation)")
    conn, connector = _connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT client_id, reporting_period, net_debt_eur_m, liquidity_eur_m,
               debt_maturing_24m_eur_m, reported_revenue_eur_m, ebitda_eur_m
        FROM ca.ext_company_filings
        WHERE client_id IN ('CLI101', 'CLI103')
          AND reported_revenue_eur_m IS NOT NULL
        ORDER BY client_id
    """)
    for r in cur.fetchall():
        print(f"  {r[0]} | {r[1]}")
        print(f"    net_debt:           \u20ac{r[2]}M")
        print(f"    liquidity:          \u20ac{r[3]}M")
        print(f"    24M maturity wall:  \u20ac{r[4]}M")
        print(f"    revenue:            \u20ac{r[5]}M")
        print(f"    ebitda:             \u20ac{r[6]}M")
        print()
    _close(conn, connector, cur)


def q05_market_ground_truth():
    _hdr(5, "Market data ground truth")
    conn, connector = _connect()
    cur = conn.cursor()
    print("  === ca.mkt_rates_curves (EUR) ===")
    cur.execute("""
        SELECT tenor, swap_rate_pct, govt_yield_pct
        FROM ca.mkt_rates_curves WHERE currency = 'EUR' ORDER BY tenor
    """)
    for r in cur.fetchall():
        print(f"    {r[0]} | swap: {r[1]}% | govt: {r[2]}%")
    print()
    print("  === ca.ext_credit_spreads (Enel) ===")
    cur.execute("""
        SELECT tenor, spread_bps, all_in_yield_pct
        FROM ca.ext_credit_spreads WHERE issuer_or_rating ILIKE %s ORDER BY tenor
    """, ('%Enel%',))
    for r in cur.fetchall():
        print(f"    {r[0]} | {r[1]} bps | all-in {r[2]}%")
    _close(conn, connector, cur)


def q06_maturity_schedule():
    _hdr(6, "Debt maturity schedule (slides 5/10 source)")
    conn, connector = _connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT client_id, maturity_year, SUM(amount_eur_m), COUNT(*)
        FROM ca.debt_maturity_schedule
        WHERE client_id IN ('CLI101', 'CLI103')
        GROUP BY client_id, maturity_year
        ORDER BY client_id, maturity_year
    """)
    for r in cur.fetchall():
        print(f"  {r[0]} | {r[1]} | \u20ac{r[2]}M | {r[3]} instrument(s)")
    _close(conn, connector, cur)


def q07_ingestion_state():
    _hdr(7, "Ingestion state — signals by client")
    conn, connector = _connect()
    cur = conn.cursor()
    print("  === Signals per client ===")
    cur.execute("""
        SELECT client_id, COUNT(*) FROM ca.digital_twin_signals
        GROUP BY client_id ORDER BY COUNT(*) DESC
    """)
    for r in cur.fetchall():
        print(f"    {r[0]:10s} | {r[1]} signals")
    print()
    print("  === Enel signals by urgency ===")
    cur.execute("""
        SELECT urgency, COUNT(*) FROM ca.digital_twin_signals
        WHERE client_id = 'CLI101' GROUP BY urgency ORDER BY COUNT(*) DESC
    """)
    for r in cur.fetchall():
        print(f"    {(r[0] or 'unknown'):10s} | {r[1]}")
    print()
    print("  === Enel most recent 5 signals ===")
    cur.execute("""
        SELECT signal_id, signal_type, LEFT(trigger_summary, 70), created_at
        FROM ca.digital_twin_signals WHERE client_id = 'CLI101'
        ORDER BY created_at DESC LIMIT 5
    """)
    for r in cur.fetchall():
        print(f"    {r[3]} | {r[0]} | {r[1]}")
        print(f"      {r[2]}")
    _close(conn, connector, cur)


def q08_chunks_by_channel():
    _hdr(8, "Document chunks — channel distribution")
    conn, connector = _connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT source_channel, COUNT(*) FROM ca.document_vector_chunks
        GROUP BY source_channel ORDER BY COUNT(*) DESC
    """)
    print("  === Chunks by source_channel (all clients) ===")
    for r in cur.fetchall():
        print(f"    {(r[0] or 'unknown'):25s} | {r[1]}")
    print()
    cur.execute("""
        SELECT chunk_id, source_name, LEFT(text_content, 60)
        FROM ca.document_vector_chunks
        WHERE client_id = 'CLI101' AND chunk_id >= 9000000
        ORDER BY chunk_id
    """)
    rows = cur.fetchall()
    print(f"  === Enel curated chunks (chunk_id >= 9000000): {len(rows)} ===")
    for r in rows:
        print(f"    #{r[0]} | {r[1]}")
        print(f"      {r[2]}")
    _close(conn, connector, cur)


def q09_dedup_state():
    _hdr(9, "Dedup state — channel history")
    conn, connector = _connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (source_channel)
               source_channel, source_name, chunk_id, created_at
        FROM ca.document_vector_chunks WHERE client_id = 'CLI101'
        ORDER BY source_channel, created_at DESC
    """)
    print("  === Enel channel history (most recent per channel) ===")
    for r in cur.fetchall():
        print(f"    {(r[0] or 'unknown'):20s} | chunk #{r[2]} | {r[1]}")
    print()
    cur.execute("SELECT COUNT(*) FROM ca.digital_twin_signals WHERE client_id = 'CLI101'")
    sigs = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ca.document_vector_chunks WHERE client_id = 'CLI101'")
    chunks = cur.fetchone()[0]
    print(f"  Enel signals: {sigs} | Enel chunks: {chunks}")
    print(f"  Signal-to-chunk ratio: {sigs / chunks:.1f}x (multi-signal extraction)")
    _close(conn, connector, cur)


def q10_coverage_teams():
    _hdr(10, "Coverage teams — RM lookup")
    conn, connector = _connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT client_id, role_title, banker_name, location
        FROM ca.coverage_teams WHERE client_id IN ('CLI101', 'CLI103')
        ORDER BY client_id, role_title
    """)
    for r in cur.fetchall():
        print(f"  {r[0]} | {r[1]:45s} | {r[2]:20s} | {r[3]}")
    _close(conn, connector, cur)


def q11_audit_trail():
    _hdr(11, "Audit trail — timestamps")
    conn, connector = _connect()
    cur = conn.cursor()
    for table in ('digital_twin_signals', 'document_vector_chunks'):
        cur.execute(
            f"SELECT MIN(created_at), MAX(created_at), COUNT(*) "
            f"FROM ca.{table} WHERE client_id = 'CLI101'"
        )
        r = cur.fetchone()
        print(f"  {table}:")
        print(f"    oldest: {r[0]}")
        print(f"    newest: {r[1]}")
        print(f"    count:  {r[2]}")
    _close(conn, connector, cur)


def q12_baseline_snapshot():
    _hdr(12, "Reset snapshot — pristine baseline contents")
    with open(BASELINE_PATH) as f:
        snap = json.load(f)
    print(f"  Top-level keys: {list(snap.keys())}")
    print(f"  Clients: {len(snap['clients'])}")
    print()
    for cid in ('CLI101', 'CLI103'):
        label = 'Enel' if cid == 'CLI101' else 'BASF'
        print(f"  === {cid} ({label}) pristine counts ===")
        for table, rows in snap['clients'][cid].items():
            print(f"    {table}: {len(rows)} row(s)")
        print()


def q13_brand_profile():
    _hdr(13, "Brand profile — runtime toggle state")
    print(f"  Active brand: {ACTIVE_BRAND['name']}")
    print(f"  Available profiles: {list(BRAND_PROFILES.keys())}")
    print()
    print("  === Active profile (server-side keys excluded) ===")
    for k, v in ACTIVE_BRAND.items():
        if k.startswith('prompt_'):
            continue
        print(f"    {k}: {v}")


def q14_sync_invariants():
    _hdr(14, "Sync invariants — module-level constants")
    print(f"  _DEMO_CLIENT_IDS (backend whitelist): {_DEMO_CLIENT_IDS}")
    print()
    print("  _CREDIT_RATINGS (curated display dict):")
    for cid, rating in _CREDIT_RATINGS.items():
        print(f"    {cid}: {rating}")
    print()
    print("  _FAMILY_KEYWORD_WEIGHTS (taxonomy — weight 5 signals only):")
    for fam, kws in _FAMILY_KEYWORD_WEIGHTS.items():
        top5 = [k for k, v in kws.items() if v == 5]
        print(f"    {fam}: {top5}")


QUERIES = {
    1:  ("Schema inventory", q01_schema_inventory),
    2:  ("Client scope", q02_client_scope),
    3:  ("Opportunity anchor", q03_opportunity_anchor),
    4:  ("Balance sheet truth", q04_balance_sheet),
    5:  ("Market ground truth", q05_market_ground_truth),
    6:  ("Debt maturity schedule", q06_maturity_schedule),
    7:  ("Ingestion state", q07_ingestion_state),
    8:  ("Document chunks by channel", q08_chunks_by_channel),
    9:  ("Dedup state", q09_dedup_state),
    10: ("Coverage teams", q10_coverage_teams),
    11: ("Audit trail", q11_audit_trail),
    12: ("Reset snapshot", q12_baseline_snapshot),
    13: ("Brand profile", q13_brand_profile),
    14: ("Sync invariants", q14_sync_invariants),
}


def _print_menu():
    print()
    print("=" * 78)
    print("  ING FM Deal Intelligence — Verification Queries")
    print("=" * 78)
    for n, (label, _) in QUERIES.items():
        print(f"  {n:>2}.  {label}")
    print()
    print("  a.   Run all queries")
    print("  q.   Quit")
    print()


def main():
    args = sys.argv[1:]

    if '--all' in args:
        for n in sorted(QUERIES):
            QUERIES[n][1]()
        return

    if '--summary' in args:
        print()
        print("=" * 78)
        print("  Verification queries — summary")
        print("=" * 78)
        for n, (label, _) in QUERIES.items():
            print(f"  Q{n:>2}  {label}")
        print()
        print(f"  Active brand: {ACTIVE_BRAND['name']}")
        print(f"  Whitelist:    {_DEMO_CLIENT_IDS}")
        print()
        return

    if args and args[0].isdigit():
        n = int(args[0])
        if n in QUERIES:
            QUERIES[n][1]()
        else:
            print(f"Unknown query number: {n}")
            sys.exit(1)
        return

    # Menu mode
    while True:
        _print_menu()
        choice = input("  Select query: ").strip().lower()
        if choice == 'q':
            break
        if choice == 'a':
            for n in sorted(QUERIES):
                QUERIES[n][1]()
            break
        if choice.isdigit() and int(choice) in QUERIES:
            QUERIES[int(choice)][1]()
        else:
            print(f"  Unknown selection: {choice}")


if __name__ == "__main__":
    main()