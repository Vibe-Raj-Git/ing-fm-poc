import os
import sys
import io
from main import get_db_connection, get_opportunities
from pitchbook_builder import fetch_pitchbook_bundle, build_pitchbook

def run_parity_audit():
    print("=" * 72)
    print("  ING FINANCIAL MARKETS POC — 13-GATE DYNAMIC PARITY AUDIT")
    print("=" * 72)

    passed_gates = 0
    total_gates = 13

    # -------------------------------------------------------------
    # Gate 1: DB Connection
    # -------------------------------------------------------------
    conn, connector = get_db_connection()
    if conn:
        print("✅ Gate 01: PostgreSQL connection established via get_db_connection")
        passed_gates += 1
    else:
        print("❌ Gate 01: Failed to connect to PostgreSQL")
        return

    cur = conn.cursor()

    # -------------------------------------------------------------
    # Gate 2: ca.mkt_rates_curves Grounding
    # -------------------------------------------------------------
    cur.execute("SELECT tenor, swap_rate_pct, govt_yield_pct FROM ca.mkt_rates_curves WHERE currency = 'EUR';")
    curves = {r[0]: {"swap": float(r[1]) if r[1] else 0.0, "bund": float(r[2]) if r[2] else 0.0} for r in cur.fetchall()}
    if curves.get("5Y", {}).get("swap") == 2.62 and curves.get("10Y", {}).get("bund") == 2.61:
        print(f"✅ Gate 02: ca.mkt_rates_curves verified (5Y Swap: {curves['5Y']['swap']}%, 10Y Bund: {curves['10Y']['bund']}%)")
        passed_gates += 1
    else:
        print(f"❌ Gate 02: Unexpected rates in ca.mkt_rates_curves: {curves}")

    # -------------------------------------------------------------
    # Gate 3: ca.ext_credit_spreads Grounding (Enel Benchmark)
    # -------------------------------------------------------------
    cur.execute("""
        SELECT tenor, spread_bps, all_in_yield_pct 
        FROM ca.ext_credit_spreads 
        WHERE issuer_or_rating ILIKE '%ENEL%'
        ORDER BY tenor;
    """)
    enel_spreads = {r[0]: {"spread": float(r[1]), "all_in": float(r[2])} for r in cur.fetchall()}
    if enel_spreads.get("5Y", {}).get("spread") == 78.0 and enel_spreads.get("10Y", {}).get("spread") == 80.0:
        print(f"✅ Gate 03: ca.ext_credit_spreads verified (5Y: {enel_spreads['5Y']['spread']} bps, 10Y: {enel_spreads['10Y']['spread']} bps)")
        passed_gates += 1
    else:
        print(f"❌ Gate 03: Unexpected spreads in ca.ext_credit_spreads: {enel_spreads}")

    # -------------------------------------------------------------
    # Gate 4: API /api/opportunities Enel Retrieval
    # -------------------------------------------------------------
    opps = get_opportunities()
    enel_opp = next((o for o in opps if "ENEL" in o["id"].upper() or o["id"] == "CLI101"), None)
    if enel_opp:
        print(f"✅ Gate 04: /api/opportunities returns client ({enel_opp.get('name')})")
        passed_gates += 1
    else:
        print("❌ Gate 04: Enel not found in /api/opportunities")
        return

    # -------------------------------------------------------------
    # Gate 5: API Opportunity Market Curve Payload
    # -------------------------------------------------------------
    if enel_opp.get("eur_10y_bund") == "2.61%" and enel_opp.get("eur_5y_swap") == "2.62%":
        print(f"✅ Gate 05: /api/opportunities rates mapped (10Y Bund: {enel_opp.get('eur_10y_bund')}, 5Y Swap: {enel_opp.get('eur_5y_swap')})")
        passed_gates += 1
    else:
        print(f"❌ Gate 05: Bad rates in /api/opportunities: Bund={enel_opp.get('eur_10y_bund')}, Swap={enel_opp.get('eur_5y_swap')}")

    # -------------------------------------------------------------
    # Gate 6: API Opportunity Credit Spread Payload
    # -------------------------------------------------------------
    if enel_opp.get("credit_spread_5y_bps") == "78 bps" and enel_opp.get("credit_spread_10y_bps") == "80 bps":
        print(f"✅ Gate 06: /api/opportunities spreads mapped (5Y: {enel_opp.get('credit_spread_5y_bps')}, 10Y: {enel_opp.get('credit_spread_10y_bps')})")
        passed_gates += 1
    else:
        print(f"❌ Gate 06: Bad spreads in /api/opportunities: 5Y={enel_opp.get('credit_spread_5y_bps')}, 10Y={enel_opp.get('credit_spread_10y_bps')}")

    # -------------------------------------------------------------
    # Gate 7: fetch_pitchbook_bundle Grounding
    # -------------------------------------------------------------
    bundle = fetch_pitchbook_bundle("CLI101", "CLI101", get_db_connection)
    if bundle and bundle.get("client_name"):
        print(f"✅ Gate 07: fetch_pitchbook_bundle loaded for {bundle.get('client_name')}")
        passed_gates += 1
    else:
        print("❌ Gate 07: fetch_pitchbook_bundle failed to resolve client")
        return

    # -------------------------------------------------------------
    # Gate 8: PPTX Bundle Curve Parity
    # -------------------------------------------------------------
    if bundle.get("bund_10y_yield") == "2.61%" and bundle.get("swap_5y_rate") == "2.62%":
        print(f"✅ Gate 08: Bundle curves aligned (Bund: {bundle.get('bund_10y_yield')}, Swap: {bundle.get('swap_5y_rate')})")
        passed_gates += 1
    else:
        print(f"❌ Gate 08: Bundle curves misaligned: Bund={bundle.get('bund_10y_yield')}, Swap={bundle.get('swap_5y_rate')}")

    # -------------------------------------------------------------
    # Gate 9: PPTX Bundle Credit Spread Parity
    # -------------------------------------------------------------
    if bundle.get("credit_spread_5y") == "78 bps" and bundle.get("spread_10y_bps") == "80 bps":
        print(f"✅ Gate 09: Bundle spreads aligned (5Y: {bundle.get('credit_spread_5y')}, 10Y: {bundle.get('spread_10y_bps')})")
        passed_gates += 1
    else:
        print(f"❌ Gate 09: Bundle spreads misaligned: 5Y={bundle.get('credit_spread_5y')}, 10Y={bundle.get('spread_10y_bps')}")

    # -------------------------------------------------------------
    # Gate 10: PPTX Bundle All-In Yield Parity
    # -------------------------------------------------------------
    if bundle.get("all_in_yield") == "3.40%":
        print(f"✅ Gate 10: Bundle all-in yield aligned ({bundle.get('all_in_yield')})")
        passed_gates += 1
    else:
        print(f"❌ Gate 10: Bundle all-in yield misaligned: {bundle.get('all_in_yield')}")

    # -------------------------------------------------------------
    # Gate 11: Base Pitchbook PPTX Generation via build_pitchbook
    # -------------------------------------------------------------
    try:
        prs_buf = build_pitchbook(bundle, enel_opp, compliance_bullets=[], overrides={})
        byte_len = prs_buf.getbuffer().nbytes if hasattr(prs_buf, "getbuffer") else len(prs_buf)
        if byte_len > 10000:
            print(f"✅ Gate 11: Base PPTX generated cleanly ({byte_len:,} bytes)")
            passed_gates += 1
        else:
            print(f"❌ Gate 11: Base PPTX generated buffer too small ({byte_len} bytes)")
    except Exception as e_gen:
        print(f"❌ Gate 11: PPTX generation crashed: {e_gen}")

    # -------------------------------------------------------------
    # Gate 12: Override Layering (Copilot Simulation Test)
    # -------------------------------------------------------------
    try:
        simulated_ov = {
            "credit_spread_5y": "65 bps",
            "all_in_yield": "3.27%",
            "swap_5y": "2.55%"
        }
        prs_ov_buf = build_pitchbook(bundle, enel_opp, compliance_bullets=[], overrides=simulated_ov)
        byte_len_ov = prs_ov_buf.getbuffer().nbytes if hasattr(prs_ov_buf, "getbuffer") else len(prs_ov_buf)
        if byte_len_ov > 10000:
            print(f"✅ Gate 12: Copilot scenario override generated cleanly ({byte_len_ov:,} bytes)")
            passed_gates += 1
        else:
            print(f"❌ Gate 12: Override PPTX buffer too small ({byte_len_ov} bytes)")
    except Exception as e_ov:
        print(f"❌ Gate 12: Override PPTX generation crashed: {e_ov}")

    # -------------------------------------------------------------
    # Gate 13: Non-Destructive Invariance
    # -------------------------------------------------------------
    cur.execute("SELECT spread_bps FROM ca.ext_credit_spreads WHERE issuer_or_rating ILIKE '%ENEL%' AND tenor = '5Y';")
    base_check = cur.fetchone()
    if base_check and float(base_check[0]) == 78.0:
        print("✅ Gate 13: Non-destructive invariance confirmed (DB base record preserved at 78.0 bps)")
        passed_gates += 1
    else:
        print(f"❌ Gate 13: Base DB was mutated by scenario run: {base_check}")

    cur.close()
    conn.close()
    if connector:
        connector.close()

    print("=" * 72)
    print(f"  AUDIT SUMMARY: {passed_gates}/{total_gates} GATES PASSED")
    print("=" * 72)

    if passed_gates == total_gates:
        print("🚀 ALL 13 GATES PASSED. FULL PLATFORM PARITY ACHIEVED!")
    else:
        print("⚠️ Some gates failed. Review diagnostic lines above.")

if __name__ == "__main__":
    run_parity_audit()
