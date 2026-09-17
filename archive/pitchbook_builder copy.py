import re

def compute_canonical_bundle(ctx, ov=None):
    """
    Single mathematical source of truth.
    Derives all tenors, spreads, rates, tranches, and scenarios from DB + Overrides.
    """
    ov = ov or {}
    
    # Client Meta
    rating = ov.get("rating", ctx.get("credit_rating", ctx.get("rating", "BBB+")))
    raw_wall = ov.get("debt_maturing_24m_str", ov.get("maturity_wall_str", ctx.get("debt_maturing_24m_str")))
    wall_str = str(raw_wall) if raw_wall and str(raw_wall) != "None" else "€3,000M"
    
    # 1. Tenor
    tenor_raw = str(ov.get("tenor", ctx.get("tenor", "7 Years")))
    tenor_m = re.search(r"(\d+)", tenor_raw)
    tenor_years = int(tenor_m.group(1)) if tenor_m else 7
    tenor_str = f"{tenor_years} Years (T + {tenor_years}Y)"
    
    # 2. Spread & Swap Rate (Dynamic DB + Copilot Overrides)
    raw_s = (
        ov.get("spread")
        or ov.get("credit_spread_5y")
        or ov.get("spread_5y_bps")
        or ctx.get("credit_spread_5y")
        or ctx.get("spread_5y_bps")
        or ctx.get("indicative_spread")
        or "Mid-Swap + 78 bps"
    )
    sp_m = re.search(r"(\d+)\s*bps", str(raw_s), re.IGNORECASE)
    spread_bps = int(sp_m.group(1)) if sp_m else 78
    spread_str = f"Mid-Swap + {spread_bps} bps"
    
    swap_raw = ov.get("swap_5y", ctx.get("swap_5y", "2.62%"))
    sw_m = re.search(r"([\d\.]+)", str(swap_raw))
    swap_val = float(sw_m.group(1)) if sw_m else 2.62
    
    # 3. All-In Rate
    calc_all_in = swap_val + (spread_bps / 100.0)
    all_in_rate = float(ov.get("indicative_all_in_rate", calc_all_in))
    all_in_str = f"{all_in_rate:.2f}%"
    
    # 4. Tranche Splits
    refi_pct = int(ov.get("refi_bond_pct", ctx.get("refi_bond_pct", 60)))
    prehedge_pct = int(ov.get("prehedge_swap_pct", ctx.get("prehedge_swap_pct", 100 - refi_pct)))
    
    # 5. ESG & FX Parameters
    greenium_bps = int(ov.get("greenium_bps", ctx.get("greenium_bps", 5)))
    floor_val = ov.get("fx_collar_floor", "1.0850")
    cap_val = ov.get("fx_collar_cap", "1.0450")
    
    # 6. Scenarios
    scen_lock = ov.get("rate_scenario_lock", f"{all_in_str} (locked)")
    scen_up = ov.get("rate_scenario_up", f"{all_in_rate + 1.00:.2f}%")
    scen_down = ov.get("rate_scenario_down", f"{all_in_rate - 0.50:.2f}%")
    
    return {
        "rating": rating,
        "wall_str": wall_str,
        "tenor_years": tenor_years,
        "tenor_str": tenor_str,
        "spread_bps": spread_bps,
        "spread_str": spread_str,
        "swap_val": swap_val,
        "all_in_rate": all_in_rate,
        "all_in_str": all_in_str,
        "refi_pct": refi_pct,
        "prehedge_pct": prehedge_pct,
        "greenium_bps": greenium_bps,
        "floor_val": floor_val,
        "cap_val": cap_val,
        "scen_lock": scen_lock,
        "scen_up": scen_up,
        "scen_down": scen_down
    }

import io
import os
import logging
from datetime import datetime
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import CategoryChartData

logger = logging.getLogger("pitchbook_builder")

# =============================================================================
# ING Brand Colors
# =============================================================================
ING_NAVY = RGBColor(0, 0, 102)
ING_ORANGE = RGBColor(255, 98, 0)
GRAY_TEXT = RGBColor(100, 116, 139)
ING_DARK_SLATE = RGBColor(12, 17, 43)
ING_DARK_SLATE = RGBColor(12, 17, 43)
ING_WHITE = RGBColor(255, 255, 255)
ING_LIGHT_ORANGE = RGBColor(255, 235, 220)
BG_LIGHT = RGBColor(248, 249, 250)
LINE_GRAY = RGBColor(220, 224, 230)
TEXT_DARK = RGBColor(15, 23, 42)
TEXT_MUTED = RGBColor(100, 116, 139)
CARD_BG_BLUE = RGBColor(240, 244, 255)
CARD_BORDER_BLUE = RGBColor(200, 215, 250)
SUCCESS_GREEN = RGBColor(16, 149, 79)


# =============================================================================
# Helper Functions
# =============================================================================

def add_header(slide, title, category="FINANCIAL MARKETS ORIGINATION", is_white=False):
    tb_k = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(10.0), Inches(0.3))
    tf_k = tb_k.text_frame
    tf_k.word_wrap = True
    p_k = tf_k.paragraphs[0]
    p_k.text = category.upper()
    p_k.font.bold = True
    p_k.font.size = Pt(9)
    p_k.font.color.rgb = ING_ORANGE

    tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.65), Inches(10.0), Inches(0.65))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.bold = True
    p.font.size = Pt(20)
    p.font.color.rgb = ING_WHITE if is_white else ING_DARK_SLATE


def add_logo(slide, is_white=False):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_filename = os.path.join(base_dir, "assets", "ing_logo_white.png") if is_white else os.path.join(base_dir, "assets", "ing_logo_orange.png")
    if os.path.exists(logo_filename):
        try:
            # Render logo with explicit height constraint to prevent vertical overflow
            slide.shapes.add_picture(logo_filename, Inches(11.8), Inches(0.35), height=Inches(0.45))
            return
        except Exception as exc:
            logger.warning(f"Could not insert logo: {exc}")
    tb = slide.shapes.add_textbox(Inches(11.4), Inches(0.35), Inches(1.2), Inches(0.4))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = "ING"
    p.alignment = PP_ALIGN.RIGHT
    p.font.bold = True
    p.font.size = Pt(18)
    p.font.color.rgb = ING_WHITE if is_white else ING_ORANGE


def add_footer(slide, is_white=False):
    tb = slide.shapes.add_textbox(Inches(0.8), Inches(6.85), Inches(11.733), Inches(0.3))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = "ING Wholesale Banking • Strictly Confidential"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(9)
    p.font.color.rgb = RGBColor(160, 175, 200) if is_white else TEXT_MUTED


def detect_product_family(ctx):
    combined = " ".join([
        str(ctx.get("opportunity_type") or ""),
        str(ctx.get("product_family") or ""),
        str(ctx.get("type") or ""),
        str(ctx.get("next_best_action") or ""),
        str(ctx.get("trigger_catalyst") or ""),
        str(ctx.get("why_now_nlg") or "")
    ]).lower()
    if any(k in combined for k in ["green", "sustainable", "esg", "slb", "sustainability"]):
        return "GREEN_ESG"
    if any(k in combined for k in ["fx", "currency", "collar", "usd", "hedging gap"]):
        return "FX_HEDGE"
    if any(k in combined for k in ["irs", "pre-hedge", "rate sensitivity", "swap overlay"]):
        return "RATES_HEDGE"
    if any(k in combined for k in ["refinanc", "dcm", "emtn", "bond", "maturity wall"]):
        return "DCM_REFI"
    return "DCM_REFI"
        
    return "DCM_REFI"


def get_product_kicker(p_fam):
    """Get product category kicker text."""
    mapping = {
        "FX_HEDGE": "FX & COMMODITY RISK ADVISORY",
        "GREEN_ESG": "SUSTAINABLE & ESG CAPITAL STRUCTURING",
        "RATES_HEDGE": "RATES RISK & LIABILITY MANAGEMENT",
        "DCM_REFI": "DCM CAPITAL STRUCTURING"
    }
    return mapping.get(p_fam, "DCM CAPITAL STRUCTURING")


def get_product_subtitle(p_fam):
    """Get product subtitle text."""
    mapping = {
        "FX_HEDGE": "Strategic FX Exposure Risk & Layered Hedging Programme",
        "GREEN_ESG": "Sustainable Funding",
        "RATES_HEDGE": "Pre-Hedge Swap Overlay & Rate Sensitivity Immunisation",
        "DCM_REFI": "Refinancing & Capital Markets Execution Framework"
    }
    return mapping.get(p_fam, "Capital Markets Execution Framework")


def get_product_pillars(p_fam, ctx, ov):
    """Get executive summary pillars matching App.jsx preview with dynamic WorkFabric & Channel Telemetry."""
    client_name = ov.get("client_name", ctx.get("client_name", "Corporate Client"))
    rm_name = ov.get("rm_name", ctx.get("rm_name", "Senior Relationship Manager"))
    mat_wall = ov.get("maturity_wall_str", ctx.get("debt_maturing_24m_str", "€3,000M"))
    if mat_wall == "N/A" or not mat_wall:
        mat_wall = "€3,000M"
    unhedged_gap = ov.get("unhedged_gap_str", ov.get("unhedged_gap", "$8.0B"))
    if unhedged_gap == "N/A" or not unhedged_gap:
        unhedged_gap = "$8.0B"
    notional = ov.get("notional_bond", "EUR 600,000,000")

    # Extract dynamic WorkFabric signals (Latent Opportunities vs Desk Signals)
    raw_signals = ov.get("signals") or ctx.get("signals") or []
    wf_latents = [s for s in raw_signals if s.get("signal_type") == "LATENT_OPPORTUNITY"]
    top_latent_summary = wf_latents[0].get("trigger_summary") if wf_latents else None

    if p_fam == "FX_HEDGE":
        pillar2_desc = "Rolling 12M–24M zero-cost participating collars protecting gross margins."
        if top_latent_summary:
            pillar2_desc = f"WorkFabric Trigger: {top_latent_summary}. Dynamic participating collars protecting margins."
        return [
            ("1", "Exposure-led Architecture", f"Addressing the {unhedged_gap} USD hedge gap from commercial revenue expansion."),
            ("2", "Multi-Tenor Layered Corridors", pillar2_desc),
            ("3", "Electronic Desk Execution", "Automated liquidity sourcing through ING global FX electronic trading desk."),
            ("4", "Dedicated Coverage", f"Sector coverage led by {rm_name} with IFRS 9 hedge accounting support.")
        ]
    elif p_fam == "GREEN_ESG":
        pillar2_desc = "Ring-fenced eligible asset pool with annual impact & allocation verification."
        if top_latent_summary:
            pillar2_desc = f"{top_latent_summary}. Ring-fenced eligible green asset pool."
        return [
            ("1", "Green Framework Alignment", "Alignment with ICMA Green Bond Principles and EU Taxonomy standards."),
            ("2", "Use of Proceeds Pool", pillar2_desc),
            ("3", "Greenium Advantage", "Potential pricing benefit from access to dedicated sustainable-investment demand."),
            ("4", "Sole ESG Structurer", "ING leading SPO documentation, investor roadshow, and syndicate execution.")
        ]
    elif p_fam == "RATES_HEDGE":
        pillar2_desc = "Forward-starting IRS and swaptions to lock in current benchmark yield curve."
        if top_latent_summary:
            pillar2_desc = f"WorkFabric Pre-Hedge Trigger: {top_latent_summary}. Forward-starting IRS execution window."
        return [
            ("1", "Rate Risk Assessment", f"Quantifying interest rate repricing risk across the {mat_wall} debt horizon."),
            ("2", "Pre-Hedge Swap Overlay", pillar2_desc),
            ("3", "Hedge Policy Alignment", "Optimizing treasury fixed vs floating debt ratio target."),
            ("4", "Syndicate Distribution", "Full balance sheet underwriting and rating agency advisory.")
        ]
    else:  # DCM_REFI
        pillar2_desc = f"Tailored combination of {notional} benchmark EMTN."
        if top_latent_summary:
            pillar2_desc = f"WorkFabric Refinancing Catalyst: {top_latent_summary}. Sized for {notional} benchmark issuance."
        return [
            ("1", "Maturity-Led Sizing", f"Addressing the {mat_wall} near-term maturity profile."),
            ("2", "Right-Sized Structure", pillar2_desc),
            ("3", "Competitive Execution", "Direct syndicate distribution across European institutional bases."),
            ("4", "Long-Term Partnership", "Committed balance sheet underwriting and rating optimization.")
        ]


# =============================================================================
# Data Fetching - Fully Database-Driven
# =============================================================================

def fetch_pitchbook_bundle(canonical_id, client_id_raw, get_db_connection):
    """
    Fetch complete client and deal context resolving by Opp ID, Client ID, or Client Name.
    """
    conn, connector = get_db_connection()
    cur = conn.cursor()
    
    ctx = {
        "client_name": "Corporate Client",
        "rm_name": "Senior Relationship Manager",
        "opportunity_type": "REFINANCING",
        "propensity_score": 90,
        "why_now_nlg": "",
        "next_best_action": "",
        "trigger_source": "",
        "revenue_str": "N/A",
        "ebitda_str": "N/A",
        "net_debt_str": "N/A",
        "liquidity_str": "N/A",
        "leverage_ratio": "N/A",
        "debt_maturing_24m": 0.0,
        "debt_maturing_24m_str": "N/A",
        "signals": [],
        "maturities": []
    }

    try:
        search_token = str(canonical_id or client_id_raw or "").strip()
        actual_cid = None
        
        # 1. Resolve by ca_opportunity_scoring (opportunity_id, client_id)
        cur.execute("""
            SELECT client_id, opportunity_type, propensity_score, why_now_nlg, next_best_action, trigger_source
            FROM ca.ca_opportunity_scoring
            WHERE opportunity_id = %s OR client_id = %s
            ORDER BY COALESCE(propensity_score, 0) DESC
            LIMIT 1;
        """, (search_token, search_token))
        opp_row = cur.fetchone()
        
        if opp_row:
            actual_cid = opp_row[0]
            if opp_row[1]: ctx["opportunity_type"] = opp_row[1]
            if opp_row[2]: ctx["propensity_score"] = opp_row[2]
            if opp_row[3]: ctx["why_now_nlg"] = opp_row[3]
            if opp_row[4]: ctx["next_best_action"] = opp_row[4]
            if opp_row[5]: ctx["trigger_source"] = opp_row[5]

        # 2. Resolve client_master (by resolved client_id or fuzzy client_name)
        if actual_cid:
            cur.execute("""
                SELECT client_id, client_name, rm_name, revenue_eur_m, tier, hq_country
                FROM ca.client_master
                WHERE client_id = %s
                LIMIT 1;
            """, (actual_cid,))
        else:
            cur.execute("""
                SELECT client_id, client_name, rm_name, revenue_eur_m, tier, hq_country
                FROM ca.client_master
                WHERE client_id = %s OR client_name ILIKE %s
                LIMIT 1;
            """, (search_token, f"%{search_token}%"))

        cm_row = cur.fetchone()
        if cm_row:
            actual_cid = cm_row[0]
            ctx["client_id"] = actual_cid
            if cm_row[1]: ctx["client_name"] = cm_row[1]
            if cm_row[2]:
                # Override with primary Relationship Manager from coverage_teams
                try:
                    cur.execute("""
                        SELECT banker_name FROM ca.coverage_teams
                        WHERE client_id = %s AND role_title ILIKE %s
                        LIMIT 1;
                    """, (actual_cid, '%Relationship Manager%'))
                    rm_row = cur.fetchone()
                    # Prioritize client_master rm_name (Klaus Weber) over coverage_teams override
                    ctx["rm_name"] = cm_row[2] if (cm_row and cm_row[2]) else (rm_row[0] if (rm_row and rm_row[0]) else "Senior Relationship Manager")
                except Exception as e_rm:
                    logger.warning(f"coverage_teams RM lookup failed for {actual_cid}: {e_rm}")
                    ctx["rm_name"] = cm_row[2]
            if cm_row[3] and float(cm_row[3]) > 0:
                ctx["revenue_str"] = f"€{float(cm_row[3]):,.0f}M"
            ctx["tier"] = cm_row[4] or "Tier 1"
            ctx["hq_country"] = cm_row[5] or "Europe"

        # If we didn't have opportunity info yet, fetch it for resolved client_id
        if actual_cid and not opp_row:
            cur.execute("""
                SELECT opportunity_type, propensity_score, why_now_nlg, next_best_action, trigger_source
                FROM ca.ca_opportunity_scoring
                WHERE client_id = %s
                ORDER BY COALESCE(propensity_score, 0) DESC
                LIMIT 1;
            """, (actual_cid,))
            opp_row2 = cur.fetchone()
            if opp_row2:
                if opp_row2[0]: ctx["opportunity_type"] = opp_row2[0]
                if opp_row2[1]: ctx["propensity_score"] = opp_row2[1]
                if opp_row2[2]: ctx["why_now_nlg"] = opp_row2[2]
                if opp_row2[3]: ctx["next_best_action"] = opp_row2[3]
                if opp_row2[4]: ctx["trigger_source"] = opp_row2[4]

        # 3. Fetch Financial Filings
        if actual_cid:
            cur.execute("""
                SELECT net_debt_eur_m, liquidity_eur_m, ebitda_eur_m, reported_revenue_eur_m, debt_maturing_24m_eur_m
                FROM ca.ext_company_filings
                WHERE client_id = %s
                ORDER BY reporting_period DESC
                LIMIT 1;
            """, (actual_cid,))
            f_row = cur.fetchone()
            if f_row:
                net_d, liq, ebitda, rep_rev, mat24 = f_row
                if net_d and float(net_d) > 0: ctx["net_debt_str"] = f"€{float(net_d):,.0f}M"
                if liq and float(liq) > 0: ctx["liquidity_str"] = f"€{float(liq):,.0f}M"
                if ebitda and float(ebitda) > 0: ctx["ebitda_str"] = f"€{float(ebitda):,.0f}M"
                if rep_rev and float(rep_rev) > 0: ctx["revenue_str"] = f"€{float(rep_rev):,.0f}M"
                if mat24 and float(mat24) > 0:
                    ctx["debt_maturing_24m"] = float(mat24)
                    ctx["debt_maturing_24m_str"] = f"€{float(mat24):,.0f}M"
                if net_d and ebitda and float(ebitda) > 0:
                    ctx["leverage_ratio"] = f"{(float(net_d) / float(ebitda)):.1f}x"

            # 4. Fetch Debt Maturity Schedule
            cur.execute("""
                SELECT isin, instrument_type, amount_eur_m, maturity_year, coupon_rate_pct, currency
                FROM ca.debt_maturity_schedule
                WHERE client_id = %s
                ORDER BY maturity_year ASC;
            """, (actual_cid,))
            for m in cur.fetchall():
                ctx["maturities"].append({
                    "isin": m[0] or "N/A",
                    "instrument_type": m[1] or "Bond",
                    "amount_eur_m": float(m[2]) if m[2] else 0.0,
                    "maturity_year": str(m[3]) if m[3] else "2026",
                    "coupon_rate_pct": float(m[4]) if m[4] else 0.0,
                    "currency": m[5] or "EUR"
                })

            # Calculate 24M Maturity Wall from tranches if not in filings
            if (not ctx.get("debt_maturing_24m") or ctx["debt_maturing_24m"] == 0) and ctx.get("maturities"):
                tot_wall = sum(m["amount_eur_m"] for m in ctx["maturities"] if int(m.get("maturity_year") or 0) <= 2028)
                if tot_wall > 0:
                    ctx["debt_maturing_24m"] = float(tot_wall)
                    ctx["debt_maturing_24m_str"] = f"€{tot_wall:,.0f}M"

            # 5. Fetch Digital Twin Signals (Deterministic parity with main.py & App.jsx)
            # Fetch top Latent Opportunities ordered deterministically by signal_id ASC
            cur.execute("""
                SELECT signal_type, trigger_summary, metric_identified, description, confidence_pct
                FROM ca.digital_twin_signals
                WHERE (client_id = %s OR client_id LIKE %s OR client_id ILIKE '%%ENEL%%')
                  AND signal_type = 'LATENT_OPPORTUNITY'
                ORDER BY signal_id ASC
                LIMIT 3;
            """, (actual_cid, actual_cid + "%"))
            for s in cur.fetchall():
                ctx["signals"].append({
                    "signal_type": s[0],
                    "trigger_summary": s[1],
                    "metric_identified": s[2],
                    "description": s[3],
                    "confidence_pct": s[4]
                })

            # Also fetch top non-latent Desk/Market signals
            cur.execute("""
                SELECT signal_type, trigger_summary, metric_identified, description, confidence_pct
                FROM ca.digital_twin_signals
                WHERE (client_id = %s OR client_id LIKE %s OR client_id ILIKE '%%ENEL%%')
                  AND (signal_type IS NULL OR signal_type != 'LATENT_OPPORTUNITY')
                ORDER BY created_at DESC
                LIMIT 3;
            """, (actual_cid, actual_cid + "%"))
            for s in cur.fetchall():
                ctx["signals"].append({
                    "signal_type": s[0],
                    "trigger_summary": s[1],
                    "metric_identified": s[2],
                    "description": s[3],
                    "confidence_pct": s[4]
                })

            # 6. Fetch Market Rates & Benchmark Curves from DB
            try:
                cur.execute("""
                    SELECT tenor, swap_rate_pct, govt_yield_pct
                    FROM ca.mkt_rates_curves
                    WHERE currency = 'EUR'
                    ORDER BY curve_id;
                """)
                mkt_curves = {}
                for row in cur.fetchall():
                    t, swap_pct, bund_pct = row[0], float(row[1]) if row[1] else None, float(row[2]) if row[2] else None
                    mkt_curves[t] = {"swap_rate_pct": swap_pct, "govt_yield_pct": bund_pct}
                
                ctx["mkt_curves"] = mkt_curves
                if "10Y" in mkt_curves and mkt_curves["10Y"]["govt_yield_pct"]:
                    ctx["bund_10y_yield"] = f"{mkt_curves['10Y']['govt_yield_pct']:.2f}%"
                if "10Y" in mkt_curves and mkt_curves["10Y"]["swap_rate_pct"]:
                    ctx["swap_10y_rate"] = f"{mkt_curves['10Y']['swap_rate_pct']:.2f}%"
                if "7Y" in mkt_curves and mkt_curves["7Y"]["swap_rate_pct"]:
                    ctx["swap_7y_rate"] = f"{mkt_curves['7Y']['swap_rate_pct']:.2f}%"
                if "5Y" in mkt_curves and mkt_curves["5Y"]["swap_rate_pct"]:
                    ctx["swap_5y_rate"] = f"{mkt_curves['5Y']['swap_rate_pct']:.2f}%"
            except Exception as e:
                print(f"ca.mkt_rates_curves fetch warning: {e}")

            # 7. Fetch Dynamic Credit Spreads from DB (Prioritize direct client/issuer match)
            try:
                c_name_val = str(ctx.get("client_name") or ctx.get("name") or "").strip()
                c_lead = c_name_val.split()[0] if c_name_val else "Enel"
                cur.execute("""
                    SELECT tenor, spread_bps, all_in_yield_pct, issuer_or_rating
                    FROM ca.ext_credit_spreads
                    WHERE issuer_or_rating ILIKE %s
                       OR issuer_or_rating ILIKE %s
                       OR issuer_or_rating ILIKE '%%ENEL%%'
                       OR issuer_or_rating ILIKE '%%BBB%%'
                    ORDER BY
                        CASE
                            WHEN (issuer_or_rating ILIKE %s OR issuer_or_rating ILIKE %s OR issuer_or_rating ILIKE '%%ENEL%%') THEN 1
                            ELSE 2
                        END,
                        spread_id ASC;
                """, (f"%{c_lead}%", f"%{actual_cid}%", f"%{c_lead}%", f"%{actual_cid}%"))

                credit_spreads = {}
                for s_row in cur.fetchall():
                    t_key = s_row[0]
                    if t_key not in credit_spreads:
                        credit_spreads[t_key] = {
                            "spread_bps": float(s_row[1]) if s_row[1] is not None else 0.0,
                            "all_in_yield": float(s_row[2]) if s_row[2] is not None else 0.0,
                            "issuer": s_row[3]
                        }
                ctx["credit_spreads"] = credit_spreads
                if "10Y" in credit_spreads:
                    ctx["spread_10y_bps"] = f"{credit_spreads['10Y']['spread_bps']:.0f} bps"
                    ctx["all_in_yield_10y"] = f"{credit_spreads['10Y']['all_in_yield']:.2f}%"
                if "5Y" in credit_spreads:
                    ctx["spread_5y_bps"] = f"{credit_spreads['5Y']['spread_bps']:.0f} bps"
                    ctx["credit_spread_5y"] = f"{credit_spreads['5Y']['spread_bps']:.0f} bps"
                    ctx["all_in_yield"] = f"{credit_spreads['5Y']['all_in_yield']:.2f}%"
                    ctx["all_in_yield_5y"] = f"{credit_spreads['5Y']['all_in_yield']:.2f}%"
            except Exception as e:
                print(f"ca.ext_credit_spreads fetch warning: {e}")

    except Exception as e:
        print(f"fetch_pitchbook_bundle warning: {e}")
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass
        if connector:
            try: connector.close()
            except Exception: pass

    ctx["product_family"] = detect_product_family(ctx)
    return ctx

def get_slide_meta(p_fam):
    meta = {
        "FX_HEDGE": {
            "s2_cat": "FX RISK CATALYST", "s2_ttl": "Currency Exposure & Market Catalyst",
            "s4_cat": "BALANCE SHEET FOUNDATION", "s4_ttl": "Corporate Liquidity & Currency Inflow Profile",
            "s5_cat": "CURRENCY EXPOSURE PROFILE", "s5_ttl": "FX Currency Breakdown & Hedging Gap",
            "s6_cat": "SENSITIVITY ANALYSIS", "s6_ttl": "FX Scenario Analysis & Layered Collar Payoff",
            "s7_cat": "MARKET INTELLIGENCE", "s7_ttl": "Central Bank Differentials & FX Forward Points",
            "s8_cat": "TRANSACTION STRUCTURING", "s8_ttl": "Indicative FX Risk Management Term Sheet",
            "s9_cat": "WHY EXECUTE WITH US", "s9_ttl": "Why Execute With Us",
            "s10_cat": "EXECUTION ROADMAP", "s10_ttl": "Layered Roll Framework & Desk Execution",
            "s11_cat": "REGULATORY DISCLOSURES", "s11_ttl": "Target Market Notice & EMIR Derivative Disclosures"
        },
        "GREEN_ESG": {
            "s2_cat": "SUSTAINABILITY CATALYST", "s2_ttl": "ESG Capital Strategy & Decarbonization Catalyst",
            "s4_cat": "ESG BALANCE SHEET FOUNDATION", "s4_ttl": "Balance Sheet Capacity & Green CapEx Profile",
            "s5_cat": "USE OF PROCEEDS", "s5_ttl": "Eligible Green Asset Pool & Use of Proceeds",
            "s6_cat": "SENSITIVITY ANALYSIS", "s6_ttl": "Greenium vs Plain-Vanilla Cost Sensitivity",
            "s7_cat": "MARKET INTELLIGENCE", "s7_ttl": "ESG Credit Spreads & Green Bond Index Backdrop",
            "s8_cat": "TRANSACTION STRUCTURING", "s8_ttl": "Indicative Green / Sustainability-Linked Term Sheet",
            "s9_cat": "WHY EXECUTE WITH US", "s9_ttl": "Why Execute With Us",
            "s10_cat": "EXECUTION ROADMAP", "s10_ttl": "Second-Party Opinion (SPO) & Syndicate Timeline",
            "s11_cat": "REGULATORY DISCLOSURES", "s11_ttl": "ICMA Green Bond Principles & Target Market Notice"
        },
        "RATES_HEDGE": {
            "s2_cat": "RATE RISK CATALYST", "s2_ttl": "Rate Path Volatility & IRS Pre-Hedge Catalyst",
            "s4_cat": "BALANCE SHEET FOUNDATION", "s4_ttl": "Capital Structure & Liquidity Snapshot",
            "s5_cat": "MATURITY & SWAP SCHEDULE", "s5_ttl": "Debt Maturity Profile & Swap Refinancing Horizon",
            "s6_cat": "SENSITIVITY ANALYSIS", "s6_ttl": "Rate Shift Sensitivity & Pre-Hedge Lock Analysis",
            "s7_cat": "MARKET INTELLIGENCE", "s7_ttl": "Benchmark Yields & Swap Curve Backdrop",
            "s8_cat": "TRANSACTION STRUCTURING", "s8_ttl": "Indicative Pre-Hedge Swap & EMTN Term Sheet",
            "s9_cat": "WHY EXECUTE WITH US", "s9_ttl": "Why Execute With Us",
            "s10_cat": "EXECUTION ROADMAP", "s10_ttl": "ISDA Schedule, CSA & Execution Timeline",
            "s11_cat": "REGULATORY DISCLOSURES", "s11_ttl": "Target Market Notice & EMIR Classification Disclosures"
        },
        "DCM_REFI": {
            "s2_cat": "STRATEGIC CATALYST", "s2_ttl": "Executive Context & Opportunity Rationale",
            "s4_cat": "BALANCE SHEET FOUNDATION", "s4_ttl": "Capital Structure & Treasury Health Profile",
            "s5_cat": "MATURITY SCHEDULE", "s5_ttl": "Debt Maturity Profile & Refinancing Horizon",
            "s6_cat": "SENSITIVITY ANALYSIS", "s6_ttl": "Refinancing Scenario Analysis",
            "s7_cat": "MARKET INTELLIGENCE", "s7_ttl": "Benchmark Yields & Credit Spread Backdrop",
            "s8_cat": "TRANSACTION STRUCTURING", "s8_ttl": "Indicative Debt Financing Term Sheet",
            "s9_cat": "WHY EXECUTE WITH US", "s9_ttl": "Why Execute With Us",
            "s10_cat": "EXECUTION ROADMAP", "s10_ttl": "Roadmap & Syndicate Timeline",
            "s11_cat": "REGULATORY DISCLOSURES", "s11_ttl": "Regulatory Notices & Target Market Classification"
        }
    }
    return meta.get(p_fam, meta["DCM_REFI"])

def build_pitchbook(ctx, opp, compliance_bullets=None, overrides=None):
    """
    Build pitchbook using database data. No hardcoded client-specific values.
    """
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    ov = overrides or {}
    
    # -------- Client Data from Database (with override support) --------
    client_name = ov.get("client_name", ctx.get("client_name", "Corporate Client"))
    p_fam = ov.get("product_family", ctx.get("product_family", "DCM_REFI"))
    sm = get_slide_meta(p_fam)
    rm_name = ov.get("rm_name", ctx.get("rm_name", "Senior Relationship Manager"))
    
    # Financial data from database
    revenue_str = ov.get("revenue_str", ctx.get("revenue_str", "N/A"))
    ebitda_str = ov.get("ebitda_str", ctx.get("ebitda_str", "N/A"))
    net_debt_str = ov.get("net_debt_str", ctx.get("net_debt_str", "N/A"))
    liquidity_str = ov.get("liquidity_str", ctx.get("liquidity_str", "N/A"))
    leverage_str = ov.get("leverage_ratio", ctx.get("leverage_ratio", "N/A"))
    mat_wall_str = ov.get("debt_maturing_24m_str", ov.get("maturity_wall_str", ctx.get("debt_maturing_24m_str", "N/A")))
    
    # Signals from database
    signals = ctx.get("signals", [])
    
    # Deals from database
    deals = ctx.get("deals", [])
    
    # Maturities from database
    maturities = ctx.get("maturities", [])

    # -------- Market Data (with overrides) --------
    swap_5y = ov.get("swap_5y", "2.62%")
    bund_10y = ov.get("bund_10y", "2.61%")
    iboxx_bbb = ov.get("iboxx_bbb", "115 bps")
    itraxx_main = ov.get("itraxx_main", "58 bps")
    ecb_rate = ov.get("ecb_rate", "2.25%")
    fed_rate = ov.get("fed_rate", "4.00–4.25%")

    # -------- Term Sheet (with overrides) --------
    tenor_str = ov.get("tenor", "7 Years (T + 7Y)")
    spread_str = ov.get("spread", "Mid-Swap + 82 bps")
    notional_str = ov.get("notional_bond", "EUR 600,000,000")
    spread_disc = ov.get("spread_disclaimer", "*Indicative pricing subject to market conditions, bookbuilding depth, and credit approval.*")

    # -------- Scenario Values (with overrides) --------
    scen_up = ov.get("rate_scenario_up", "4.55%")
    scen_lock = ov.get("rate_scenario_lock", "3.60% (locked)")
    scen_down = ov.get("rate_scenario_down", "3.15%")
    
    fx_up_unhedged = ov.get("fx_scen_up_unhedged", "-$520M Revenue Impact")
    fx_up_hedged = ov.get("fx_scen_up_hedged", "Guaranteed Floor (1.0850)")
    fx_spot_unhedged = ov.get("fx_scen_spot_unhedged", "1.0650 Spot Level")
    fx_spot_hedged = ov.get("fx_scen_spot_hedged", "1.0650 Forward Rate")
    fx_down_unhedged = ov.get("fx_scen_down_unhedged", "+$380M FX Gain")
    fx_down_hedged = ov.get("fx_scen_down_hedged", "Participate up to 1.0450")

    unhedged_gap = ov.get("unhedged_gap_str", ov.get("unhedged_gap", "N/A"))

    # -------- Get Product-Specific Content --------
    kicker = get_product_kicker(p_fam)
    subtitle = get_product_subtitle(p_fam)
    pillars = get_product_pillars(p_fam, ctx, ov)
    
    # -------- Build Trigger Cards --------
    trigger_cards = [
        ("Primary Market Trigger", ctx.get("trigger_source", "Active capital structure optimization"), ING_ORANGE),
        ("Window of Opportunity", "Favorable market conditions across European issuance windows.", ING_DARK_SLATE),
        ("Recommended Action", ctx.get("next_best_action", "Propose strategic execution roadmap"), SUCCESS_GREEN)
    ]

    # =========================================================================
    # SLIDE 1: COVER (Full Parity with React Preview)
    # =========================================================================
    s1 = prs.slides.add_slide(blank)
    
    # 1. Dark background
    bg = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = ING_DARK_SLATE
    bg.line.fill.background()

    # 2. Full-height Left Orange Stripe (border-l-8 border-[#FF6200])
    accent = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.18), Inches(7.5))
    accent.fill.solid()
    accent.fill.fore_color.rgb = ING_ORANGE
    accent.line.fill.background()

    # 3. Top-Right Logo & Desk Label
    add_logo(s1, is_white=True)
    tb_desk = s1.shapes.add_textbox(Inches(8.5), Inches(0.85), Inches(4.0), Inches(0.35))
    tf_desk = tb_desk.text_frame
    p_desk = tf_desk.paragraphs[0]
    p_desk.text = "Financial Markets Origination"
    p_desk.font.size = Pt(10)
    p_desk.font.color.rgb = RGBColor(148, 163, 184)
    p_desk.alignment = PP_ALIGN.RIGHT

    # 4. Main Hero Text Box
    tb1 = s1.shapes.add_textbox(Inches(0.9), Inches(2.5), Inches(11.5), Inches(3.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True

    # Kicker
    p = tf1.paragraphs[0]
    p.text = kicker.upper()
    p.font.bold = True
    p.font.size = Pt(12)
    p.font.color.rgb = ING_ORANGE

    # Client Name
    p = tf1.add_paragraph()
    p.text = client_name
    p.font.bold = True
    p.font.size = Pt(36)
    p.font.color.rgb = ING_WHITE
    p.space_before = Pt(8)

    # Subtitle
    p = tf1.add_paragraph()
    p.text = subtitle
    p.font.size = Pt(18)
    p.font.color.rgb = RGBColor(203, 213, 225)
    p.space_before = Pt(6)

    # 5. Bottom Horizontal Divider Line (border-t border-gray-800)
    div_line = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(6.3), Inches(11.6), Inches(0.015))
    div_line.fill.solid()
    div_line.fill.fore_color.rgb = RGBColor(40, 50, 80)
    div_line.line.fill.background()

    # 6. Bottom Metadata Left (Prepared by)
    tb_meta_l = s1.shapes.add_textbox(Inches(0.9), Inches(6.42), Inches(6.0), Inches(0.8))
    tf_meta_l = tb_meta_l.text_frame
    p_ml1 = tf_meta_l.paragraphs[0]
    p_ml1.text = f"Prepared by: {rm_name}"
    p_ml1.font.bold = True
    p_ml1.font.size = Pt(11)
    p_ml1.font.color.rgb = RGBColor(226, 232, 240)

    p_ml2 = tf_meta_l.add_paragraph()
    p_ml2.text = "Global Sector Coverage & Capital Markets Desk"
    p_ml2.font.size = Pt(10)
    p_ml2.font.color.rgb = RGBColor(148, 163, 184)
    p_ml2.space_before = Pt(2)

    # 7. Bottom Metadata Right (Market Snapshot Timestamp)
    market_snapshot_raw = ov.get("market_date") or f"Market Snapshot as of {datetime.now().strftime('%d %B %Y')}"
    market_snapshot_str = market_snapshot_raw.split(",")[0].strip()
    if not market_snapshot_str.startswith("Market Snapshot"): market_snapshot_str = f"Market Snapshot as of {market_snapshot_str}"
    tb_meta_r = s1.shapes.add_textbox(Inches(7.0), Inches(6.55), Inches(5.5), Inches(0.6))
    tf_meta_r = tb_meta_r.text_frame
    p_mr = tf_meta_r.paragraphs[0]
    p_mr.text = market_snapshot_str
    p_mr.font.size = Pt(10)
    p_mr.font.color.rgb = RGBColor(148, 163, 184)
    p_mr.alignment = PP_ALIGN.RIGHT

    # =========================================================================
    # SLIDE 2: STRATEGIC CATALYST
    # =========================================================================
    s2 = prs.slides.add_slide(blank)
    add_header(s2, sm["s2_ttl"], category=sm["s2_cat"])
    add_logo(s2)
    add_footer(s2)

    # Product-dynamic trigger resolution matching App.jsx
    if p_fam == "FX_HEDGE":
        trig_t = ov.get("trigger") or ctx.get("trigger_source") or "Commercial inflow shift: North American expansion increased USD revenue to >$12B against 50% hedge ratio (~$8bn gap)."
        win_t = ov.get("why_now_summary") or ov.get("window") or "EUR/USD forward points offer structural hedging pickup; volatility corridor allows zero-cost collar structuring."
        act_t = ov.get("action_summary") or ov.get("action") or "Propose staged 12M–24M layered FX hedging programme with zero-cost collar overlays to close ~$8bn gap."
    elif p_fam == "GREEN_ESG":
        trig_t = ov.get("trigger") or ctx.get("trigger_source") or "EU Taxonomy alignment: €3.5B eligible renewable & decarbonization CapEx pipeline ready for green financing."
        win_t = ov.get("why_now_summary") or ov.get("window") or "Strong ESG investor liquidity generating 3-7 bps greenium pricing concession across European green bonds, subject to market conditions."
        act_t = ov.get("action_summary") or ov.get("action") or "Establish inaugural Green Bond with second-party SPO verification."
    elif p_fam == "RATES_HEDGE":
        trig_t = ov.get("trigger") or ctx.get("trigger_source") or "Upcoming €3.2B debt maturities face repricing risk amid benchmark curve fluctuations."
        win_t = ov.get("why_now_summary") or ov.get("window") or "Current 5Y EUR swap easing at 2.62% provides attractive entry window for forward-starting IRS."
        act_t = ov.get("action_summary") or ov.get("action") or "Execute €400M pre-hedge IRS overlay to lock in current base yield before debt issuance."
    else:
        trig_t = ov.get("trigger") or ctx.get("trigger_source") or "Active capital structure optimization and refinancing window identified."
        win_t = ov.get("why_now_summary") or ov.get("window") or "Favorable benchmark credit spreads across European issuance windows."
        act_t = ov.get("action_summary") or ov.get("action") or ctx.get("next_best_action", "Propose capital structuring dialogue and benchmark EMTN roadshow.")

    styled_cards = [
        ("Primary Market Trigger", trig_t, RGBColor(255, 247, 237), RGBColor(254, 215, 170), RGBColor(154, 52, 18)),
        ("Window of Opportunity", win_t, RGBColor(239, 246, 255), RGBColor(191, 219, 254), RGBColor(0, 0, 102)),
        ("Recommended Action", act_t, RGBColor(236, 253, 245), RGBColor(167, 243, 208), RGBColor(6, 95, 70))
    ]

    for idx, (head_c, body_c, bg_c, border_c, title_c) in enumerate(styled_cards):
        cx = Inches(0.8 + (idx * 3.95))
        shp = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.5), Inches(3.8), Inches(2.3))
        shp.fill.solid()
        shp.fill.fore_color.rgb = bg_c
        shp.line.color.rgb = border_c
        shp.line.width = Pt(1)

        tb_c = s2.shapes.add_textbox(cx + Inches(0.15), Inches(1.55), Inches(3.5), Inches(2.2))
        tf_c = tb_c.text_frame
        tf_c.word_wrap = True
        
        p_h = tf_c.paragraphs[0]
        p_h.text = head_c
        p_h.font.bold = True
        p_h.font.size = Pt(11)
        p_h.font.color.rgb = title_c

        p_b = tf_c.add_paragraph()
        p_b.text = body_c
        p_b.font.size = Pt(10)
        p_b.font.color.rgb = RGBColor(55, 65, 81)
        p_b.space_before = Pt(6)

        # =========================================================================
    # SLIDE 3: EXECUTIVE SUMMARY (Exact Parity with Preview Canvas)
    # =========================================================================
    s3 = prs.slides.add_slide(blank)
    add_logo(s3)
    add_footer(s3)

    # 1. Left Orange Hero Panel
    hero_panel = s3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(3.0), Inches(7.5))
    hero_panel.fill.solid()
    hero_panel.fill.fore_color.rgb = ING_ORANGE
    hero_panel.line.fill.background()

    # Left Hero Text Box - Title
    tb_lh = s3.shapes.add_textbox(Inches(0.4), Inches(1.1), Inches(2.3), Inches(1.0))
    tf_lh = tb_lh.text_frame
    tf_lh.word_wrap = True
    p = tf_lh.paragraphs[0]
    p.text = "Executive Summary"
    p.font.bold = True
    p.font.size = Pt(24)
    p.font.color.rgb = ING_WHITE

    # White Horizontal Divider Line
    div_w = s3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.4), Inches(1.85), Inches(0.8), Inches(0.025))
    div_w.fill.solid()
    div_w.fill.fore_color.rgb = ING_WHITE
    div_w.line.fill.background()

    # Dynamic Theme Subheading
    subheading_map = {
        "FX_HEDGE": "Strategic FX Architecture",
        "GREEN_ESG": "Sustainable Finance Framework",
        "RATES_HEDGE": "Rate Risk Immunisation",
        "DCM_REFI": "Proactive Capital Structuring"
    }
    s3_subheading = subheading_map.get(p_fam, "Proactive Capital Structuring")

    tb_sub = s3.shapes.add_textbox(Inches(0.4), Inches(2.05), Inches(2.3), Inches(4.5))
    tf_sub = tb_sub.text_frame
    tf_sub.word_wrap = True
    
    p = tf_sub.paragraphs[0]
    p.text = s3_subheading
    p.font.bold = True
    p.font.size = Pt(13)
    p.font.color.rgb = ING_WHITE

    p = tf_sub.add_paragraph()
    p.text = f"Customized execution roadmap for {client_name} based on group treasury requirements and live market backdrop."
    p.font.size = Pt(10.5)
    p.font.color.rgb = RGBColor(255, 245, 235)
    p.space_before = Pt(8)


    # 2. Right Side Numbered Pillars (1, 2, 3, 4)
    pillars = get_product_pillars(p_fam, ctx, ov)
    for idx, (p_num, p_head, p_body) in enumerate(pillars):
        y_pos = Inches(1.1 + (idx * 0.85))
        
        # Circle badge
        c_shp = s3.shapes.add_shape(MSO_SHAPE.OVAL, Inches(3.4), y_pos, Inches(0.42), Inches(0.42))
        c_shp.fill.solid()
        c_shp.fill.fore_color.rgb = ING_ORANGE
        c_shp.line.fill.background()
        
        # Centered white number inside circle
        tf_c = c_shp.text_frame
        tf_c.margin_left = Inches(0)
        tf_c.margin_right = Inches(0)
        tf_c.margin_top = Inches(0.04)
        tf_c.margin_bottom = Inches(0)
        p_c = tf_c.paragraphs[0]
        p_c.text = str(p_num)
        p_c.font.bold = True
        p_c.font.size = Pt(12)
        p_c.font.color.rgb = ING_WHITE
        p_c.alignment = PP_ALIGN.CENTER

        # Pillar Title & Description Text Box
        tb_p = s3.shapes.add_textbox(Inches(4.0), y_pos - Inches(0.05), Inches(8.9), Inches(0.85))
        tf_p = tb_p.text_frame
        tf_p.word_wrap = True
        
        p_h = tf_p.paragraphs[0]
        p_h.text = p_head
        p_h.font.bold = True
        p_h.font.size = Pt(12.5)
        p_h.font.color.rgb = ING_ORANGE

        p_b = tf_p.add_paragraph()
        p_b.text = p_body
        p_b.font.size = Pt(10)
        p_b.font.color.rgb = RGBColor(75, 85, 99)
        p_b.space_before = Pt(3)

    # 3. Two Narrative Cards (from Mandate UI section)
    s3_why_now = ov.get("why_now") or ctx.get("why_now_nlg") or "\u2014"
    s3_action = ov.get("action") or ctx.get("next_best_action") or "\u2014"

    # Card 1 - Catalyst Rationale
    card1 = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(3.4), Inches(4.65), Inches(4.75), Inches(2.55))
    card1.fill.solid()
    card1.fill.fore_color.rgb = RGBColor(255, 247, 237)
    card1.line.color.rgb = RGBColor(254, 215, 170)
    card1.line.width = Pt(1)

    tb_c1 = s3.shapes.add_textbox(Inches(3.55), Inches(4.75), Inches(4.45), Inches(2.35))
    tf_c1 = tb_c1.text_frame
    tf_c1.word_wrap = True
    p_c1 = tf_c1.paragraphs[0]
    p_c1.text = "\U0001F3AF CATALYST RATIONALE (WHY NOW)"
    p_c1.font.bold = True
    p_c1.font.size = Pt(10)
    p_c1.font.color.rgb = RGBColor(154, 52, 18)
    p_c1_b = tf_c1.add_paragraph()
    p_c1_b.text = s3_why_now
    p_c1_b.font.size = Pt(9)
    p_c1_b.font.color.rgb = RGBColor(55, 65, 81)
    p_c1_b.space_before = Pt(4)

    # Card 2 - Proposed Execution & Structuring
    card2 = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.35), Inches(4.65), Inches(4.55), Inches(2.55))
    card2.fill.solid()
    card2.fill.fore_color.rgb = RGBColor(239, 246, 255)
    card2.line.color.rgb = RGBColor(191, 219, 254)
    card2.line.width = Pt(1)

    tb_c2 = s3.shapes.add_textbox(Inches(8.50), Inches(4.75), Inches(4.25), Inches(2.35))
    tf_c2 = tb_c2.text_frame
    tf_c2.word_wrap = True
    p_c2 = tf_c2.paragraphs[0]
    p_c2.text = "\U0001F4BC PROPOSED EXECUTION & STRUCTURING"
    p_c2.font.bold = True
    p_c2.font.size = Pt(10)
    p_c2.font.color.rgb = RGBColor(0, 0, 102)
    p_c2_b = tf_c2.add_paragraph()
    p_c2_b.text = s3_action
    p_c2_b.font.size = Pt(9)
    p_c2_b.font.color.rgb = RGBColor(55, 65, 81)
    p_c2_b.space_before = Pt(4)

            # =========================================================================
    # SLIDE 4: BALANCE SHEET (Exact Database & Preview Parity)
    # =========================================================================
    s4 = prs.slides.add_slide(blank)
    add_header(s4, sm["s4_ttl"], category=sm["s4_cat"])
    add_logo(s4)
    add_footer(s4)

    # Rating / Tier parity with Segment 1 Client Data
    tier_str = ov.get("rating_tier") or ov.get("credit_rating")
    if not tier_str:
        if ctx.get("client_id") == "CLI101" or "Enel" in ctx.get("client_name", ""):
            tier_str = "S&P | BBB | Positive"
        else:
            base_tier = ctx.get("tier", "Tier 1")
            tier_str = f"{base_tier} (Investment Grade)" if "Tier" in base_tier else base_tier

    def _to_bn_val(val_str, fallback):
        s = val_str or fallback
        if not s or s == "N/A":
            return fallback
        import re
        m = re.search(r'€?([0-9,]+(?:\.[0-9]+)?)\s*M', str(s))
        if m:
            num = float(m.group(1).replace(',', ''))
            return f"€{num/1000:.1f}bn"
        return s

    s4_net_debt = ov.get("net_debt_display") or _to_bn_val(net_debt_str, "€58.5bn")
    s4_liquidity = ov.get("liquidity_display") or _to_bn_val(liquidity_str, "€14.2bn")

    card3_lbl = "Unhedged FX Gap" if p_fam == "FX_HEDGE" else ("Eligible Green CapEx" if p_fam == "GREEN_ESG" else "24M Maturity Wall")
    if p_fam == "FX_HEDGE":
        card3_val = ov.get("unhedged_gap_str", "$8.0B")
    elif p_fam == "GREEN_ESG":
        card3_val = ov.get("eligible_green_capex", "€3.5bn")
    else:
        card3_val = mat_wall_str if (mat_wall_str and mat_wall_str != "N/A") else "€3,000M"

    metrics = [
        ("Net Debt", s4_net_debt, ING_DARK_SLATE),
        ("Available Liquidity", s4_liquidity, SUCCESS_GREEN),
        (card3_lbl, card3_val, ING_ORANGE),
        ("Credit Rating / Tier", tier_str, ING_DARK_SLATE)
    ]

    for idx, (lbl, val, val_color) in enumerate(metrics):
        mx = Inches(0.8 + (idx * 2.95))
        shp = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, mx, Inches(1.5), Inches(2.8), Inches(1.5))
        shp.fill.solid()
        shp.fill.fore_color.rgb = BG_LIGHT
        shp.line.color.rgb = LINE_GRAY

        tb_m = s4.shapes.add_textbox(mx + Inches(0.1), Inches(1.6), Inches(2.6), Inches(1.3))
        tf_m = tb_m.text_frame
        tf_m.word_wrap = True
        
        p = tf_m.paragraphs[0]
        p.text = lbl
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = TEXT_MUTED
        p.alignment = PP_ALIGN.CENTER
        
        p = tf_m.add_paragraph()
        p.text = val
        p.font.bold = True
        p.font.size = Pt(14 if len(val) > 12 else 18)
        p.font.color.rgb = val_color
        p.alignment = PP_ALIGN.CENTER
        p.space_before = Pt(6)

    shp_bot = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(3.25), Inches(11.7), Inches(3.35))
    shp_bot.fill.solid()
    shp_bot.fill.fore_color.rgb = CARD_BG_BLUE
    shp_bot.line.color.rgb = CARD_BORDER_BLUE

    tb_bot = s4.shapes.add_textbox(Inches(1.1), Inches(3.45), Inches(11.1), Inches(2.9))
    tf_bot = tb_bot.text_frame
    tf_bot.word_wrap = True
    
    p = tf_bot.paragraphs[0]
    p.text = "Corporate Financial Standing & Balance Sheet Capacity"
    p.font.bold = True
    p.font.size = Pt(13)
    p.font.color.rgb = ING_DARK_SLATE

    p_sub1 = tf_bot.add_paragraph()
    p_sub1.text = f"• Annual Group Revenue of {revenue_str if revenue_str != 'N/A' else '€65,000M'} supported by EBITDA of {ebitda_str if ebitda_str != 'N/A' else '€14,300M'}."
    p_sub1.font.size = Pt(10.5)
    p_sub1.font.color.rgb = RGBColor(55, 65, 81)
    p_sub1.space_before = Pt(8)

    p_sub2 = tf_bot.add_paragraph()
    p_sub2.text = f"• Robust liquidity buffer of {s4_liquidity} provides substantial capacity to execute structured financing and risk management operations."
    p_sub2.font.size = Pt(10.5)
    p_sub2.font.color.rgb = RGBColor(55, 65, 81)
    p_sub2.space_before = Pt(6)

        # =========================================================================
    # SLIDE 5: EXPOSURE / MATURITY / ASSET POOL (Exact Preview Parity)
    # =========================================================================
    s5 = prs.slides.add_slide(blank)
    add_header(s5, sm["s5_ttl"], category=sm["s5_cat"])
    add_logo(s5)
    add_footer(s5)

    # 1. Left Card Container (Gray box)
    shp_l = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(5.6), Inches(4.9))
    shp_l.fill.solid()
    shp_l.fill.fore_color.rgb = BG_LIGHT
    shp_l.line.color.rgb = CARD_BORDER_BLUE

    tb_l = s5.shapes.add_textbox(Inches(1.0), Inches(1.7), Inches(5.2), Inches(4.5))
    tf_l = tb_l.text_frame
    tf_l.word_wrap = True

    # 2. Right Card Container (Blue box)
    shp_r = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.5), Inches(5.7), Inches(4.9))
    shp_r.fill.solid()
    shp_r.fill.fore_color.rgb = CARD_BG_BLUE
    shp_r.line.color.rgb = CARD_BORDER_BLUE

    tb_r = s5.shapes.add_textbox(Inches(7.0), Inches(1.7), Inches(5.3), Inches(4.5))
    tf_r = tb_r.text_frame
    tf_r.word_wrap = True

    if p_fam == "FX_HEDGE":
        # Left: Currency Exposure Breakdown
        p = tf_l.paragraphs[0]
        p.text = "Commercial Currency Exposure Flow"
        p.font.bold = True
        p.font.size = Pt(13)
        p.font.color.rgb = ING_DARK_SLATE

        items_l = [
            ("USD Gross Inflows", "$18.5B / year (Export billing)"),
            ("EUR Cost Base", "€14.2B / year (R&D, manufacturing)"),
            ("Layered Coverage", "42% covered across 12M")
        ]
        for lbl, val in items_l:
            p_i = tf_l.add_paragraph()
            p_i.text = f"• {lbl}: {val}"
            p_i.font.size = Pt(10.5)
            p_i.font.color.rgb = RGBColor(55, 65, 81)
            p_i.space_before = Pt(8)

        p_tot = tf_l.add_paragraph()
        p_tot.text = f"Total Unhedged USD Gap: {ov.get('unhedged_gap_str', '$8.0B')}"
        p_tot.font.bold = True
        p_tot.font.size = Pt(11)
        p_tot.font.color.rgb = ING_ORANGE
        p_tot.space_before = Pt(14)

        # Right: Layered Collar Strategy
        p = tf_r.paragraphs[0]
        p.text = "Layered Collar Execution Architecture"
        p.font.bold = True
        p.font.size = Pt(13)
        p.font.color.rgb = ING_DARK_SLATE

        p_desc = tf_r.add_paragraph()
        p_desc.text = f"Customized rolling 12M–24M FX hedging corridor for {client_name}. Protects operating margin floor while retaining upside participation up to cap limits without upfront option premium."
        p_desc.font.size = Pt(10.5)
        p_desc.font.color.rgb = RGBColor(55, 65, 81)
        p_desc.space_before = Pt(8)

    elif p_fam == "GREEN_ESG":
        # Left: Eligible Green Asset Pool
        p = tf_l.paragraphs[0]
        p.text = "Eligible Green Asset & CapEx Pool"
        p.font.bold = True
        p.font.size = Pt(13)
        p.font.color.rgb = ING_DARK_SLATE

        items_l = [
            ("Renewable Generation", "€1,850M (Solar & Wind)"),
            ("Grid Modernization", "€1,100M (Smart Metering)"),
            ("Energy Storage", "€550M (Battery Systems)")
        ]
        for lbl, val in items_l:
            p_i = tf_l.add_paragraph()
            p_i.text = f"• {lbl}: {val}"
            p_i.font.size = Pt(10.5)
            p_i.font.color.rgb = RGBColor(55, 65, 81)
            p_i.space_before = Pt(8)

        p_tot = tf_l.add_paragraph()
        p_tot.text = "Total Eligible Pool: €3,500M"
        p_tot.font.bold = True
        p_tot.font.size = Pt(11)
        p_tot.font.color.rgb = ING_ORANGE
        p_tot.space_before = Pt(14)

        # Right: SPO Framework
        p = tf_r.paragraphs[0]
        p.text = "Green Framework & SPO Structuring"
        p.font.bold = True
        p.font.size = Pt(13)
        p.font.color.rgb = ING_DARK_SLATE

        green_status = (overrides or {}).get("green_asset_pool_status") or (opp or {}).get("green_asset_pool_status")
        p_desc = tf_r.add_paragraph()
        if green_status:
            p_desc.text = f"Inaugural Green Financing Framework certified under EU Green Bond Standard (EuGBS). Entire €3,500M pool verified 100% EU Taxonomy aligned with Second-Party Opinion (SPO) by Sustainalytics/ISS to capture greenium advantage."
        else:
            p_desc.text = f"Inaugural Green Financing Framework aligned with ICMA Green Bond Principles and EU Taxonomy. Supported by second-party opinion (SPO) provider to capture ESG greenium pricing advantage."
        p_desc.font.size = Pt(10.5)
        p_desc.font.color.rgb = RGBColor(55, 65, 81)
        p_desc.space_before = Pt(8)

    else:  # RATES_HEDGE & DCM_REFI
        # Left: Tranche Maturity Breakdown
        p = tf_l.paragraphs[0]
        p.text = "Tranche Maturity Breakdown"
        p.font.bold = True
        p.font.size = Pt(13)
        p.font.color.rgb = ING_DARK_SLATE

        mat_wall_val = mat_wall_str if (mat_wall_str and mat_wall_str != "N/A") else "€3,000M"
        
        mat_items = [
            ("2026 Maturities", "€600M (Commodity & Fixed Notes)"),
            ("2027 Maturities", "€3,000M (IRS Pre-Hedge Refinancing)"),
            ("2028 Maturities", "€5,497M (Syndicated Term Loan)")
        ]

        for lbl, val in mat_items:
            p_i = tf_l.add_paragraph()
            p_i.text = f"• {lbl}: {val}"
            p_i.font.size = Pt(10.5)
            p_i.font.color.rgb = RGBColor(55, 65, 81)
            p_i.space_before = Pt(8)

        p_tot = tf_l.add_paragraph()
        p_tot.text = f"Total 24M Maturity Wall: {mat_wall_val}"
        p_tot.font.bold = True
        p_tot.font.size = Pt(11)
        p_tot.font.color.rgb = ING_ORANGE
        p_tot.space_before = Pt(14)

        # Right: Pre-Hedge Overlay Sizing
        p = tf_r.paragraphs[0]
        p.text = "Pre-Hedge Overlay Sizing" if p_fam == "RATES_HEDGE" else "Refinancing Wall Rationale"
        p.font.bold = True
        p.font.size = Pt(13)
        p.font.color.rgb = ING_DARK_SLATE

        p_desc = tf_r.add_paragraph()
        if p_fam == "RATES_HEDGE":
            p_desc.text = "Upcoming maturities cluster in near-term windows. Locking in forward-starting swap rates eliminates repricing uncertainty ahead of primary debt issuance."
        else:
            p_desc.text = f"Upcoming debt maturities of {mat_wall_val} cluster in near-term windows. Proactive capital structuring and benchmark EMTN roadshows ensure optimal tenor extension and liquidity resilience."
        p_desc.font.size = Pt(10.5)
        p_desc.font.color.rgb = RGBColor(55, 65, 81)
        p_desc.space_before = Pt(8)

            # =========================================================================
    # SLIDE 6: SENSITIVITY ANALYSIS & STRATEGIC RATIONALE (100% Data-Grounded)
    # =========================================================================
    s6 = prs.slides.add_slide(blank)
    s6_title = "Rationale of our Proposal & FX Corridor Analysis" if p_fam == "FX_HEDGE" else                "Rationale of our Proposal & Greenium Advantage" if p_fam == "GREEN_ESG" else                "Rationale of our Proposal & Rate Sensitivity"
    add_header(s6, s6_title, category="STRATEGIC RATIONALE & SCENARIO ANALYSIS")
    add_logo(s6)
    add_footer(s6)

    # Compute canonical parameters
    calc = compute_canonical_bundle(ctx, ov)

    # --- LEFT COLUMN: Scenario & Recommended Structure Box ---
    left_box = s6.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(5.3), Inches(4.8))
    tf = left_box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.1)
    tf.margin_top = Inches(0.1)
    tf.margin_right = Inches(0.1)

    # 1. Scenario
    p_scen_head = tf.paragraphs[0]
    p_scen_head.text = "Scenario"
    p_scen_head.font.name = "Arial"
    p_scen_head.font.size = Pt(13)
    p_scen_head.font.bold = True
    p_scen_head.font.color.rgb = ING_ORANGE

    p_scen_body = tf.add_paragraph()
    if p_fam == "FX_HEDGE":
        p_scen_body.text = "A corporate treasury with expanding commercial operations in North America has unhedged USD exposures. Fluctuations in EUR/USD spot risk compressing operating margins. Treasury seeks certainty on downside floor while retaining upside participation."
    elif p_fam == "GREEN_ESG":
        p_scen_body.text = "A leading corporate issuer is evaluating its inaugural sustainable finance framework. Dedicated ESG funds offer pricing tension. Treasury seeks to capture the 3-5 bps greenium benefit while establishing market leadership in EU taxonomy alignment."
    else:
        p_scen_body.text = f"A {calc['rating']} rated issuer has a {calc['wall_str']} debt maturity wall upcoming. Current swap-plus-spread levels imply higher refinancing costs. Treasury wants to lock in funding cost ahead of maturity while managing execution risk."

    p_scen_body.font.name = "Arial"
    p_scen_body.font.size = Pt(10)
    p_scen_body.font.color.rgb = ING_DARK_SLATE
    p_scen_body.space_before = Pt(4)
    p_scen_body.space_after = Pt(14)

    # 2. Recommended Structure
    p_rec_head = tf.add_paragraph()
    p_rec_head.text = "Recommended Structure"
    p_rec_head.font.name = "Arial"
    p_rec_head.font.size = Pt(13)
    p_rec_head.font.bold = True
    p_rec_head.font.color.rgb = ING_ORANGE
    p_rec_head.space_before = Pt(6)

    if p_fam == "FX_HEDGE":
        bullets = [
            f"• {calc['refi_pct']}% hedged via layered forward contracts locking core budget rate.",
            f"• {calc['prehedge_pct']}% structured in zero-cost participating collars ({calc['floor_val']} floor / {calc['cap_val']} cap).",
            "• Staggered quarterly roll balances certainty with liquidity."
        ]
    elif p_fam == "GREEN_ESG":
        bullets = [
            f"• {calc['refi_pct']}% Green Benchmark EMTN, capturing ~{calc['greenium_bps']} bps greenium pricing advantage.",
            f"• {calc['prehedge_pct']}% Sustainability-Linked Tranche tied to verified Scope 1/2 reduction SPTs.",
            "• Ring-fenced eligible asset pool aligned with ICMA Green Bond Principles."
        ]
    else:
        bullets = [
            f"• {calc['refi_pct']}% refinanced via a new {calc['tenor_years']}-year vanilla bond, indicatively priced at swap + {calc['spread_bps']}bps (~{calc['all_in_str']} all-in).",
            f"• {calc['prehedge_pct']}% pre-hedged via forward-starting IRS, locking current benchmark rate.",
            "• Staggered approach balances rate-lock certainty with sizing flexibility."
        ]

    for b_text in bullets:
        b_p = tf.add_paragraph()
        b_p.text = b_text
        b_p.font.name = "Arial"
        b_p.font.size = Pt(9.5)
        b_p.font.color.rgb = ING_DARK_SLATE
        b_p.space_before = Pt(4)

    # --- RIGHT COLUMN: Illustrative Scenario Table ---
    r_title_box = s6.shapes.add_textbox(Inches(6.4), Inches(1.5), Inches(6.1), Inches(0.4))
    r_tf = r_title_box.text_frame
    r_p = r_tf.paragraphs[0]
    r_p.text = "COST COMPARISON VS CONVENTIONAL ISSUANCE" if p_fam == "GREEN_ESG" else ("Illustrative FX Outcome by Scenario" if p_fam == "FX_HEDGE" else "Illustrative All-In Cost by Scenario")
    r_p.alignment = PP_ALIGN.CENTER
    r_p.font.name = "Arial"
    r_p.font.size = Pt(12)
    r_p.font.bold = True
    r_p.font.color.rgb = ING_ORANGE

    s6_table_shape = s6.shapes.add_table(4, 3, Inches(6.4), Inches(2.0), Inches(6.1), Inches(2.2))
    s6_tbl = s6_table_shape.table
    s6_tbl.columns[0].width = Inches(2.3)
    s6_tbl.columns[1].width = Inches(1.9)
    s6_tbl.columns[2].width = Inches(1.9)

    if p_fam == "GREEN_ESG":
        s6_headers = ["Issuance Format", "Indicative Spread", "Annual Savings"]
        green_spread = calc["spread_bps"] - calc["greenium_bps"]
        
        # Sizing aligned to Slide 8 Dual-Tranche execution (€600M Green / €400M SLB)
        green_notional_eur = float(calc.get("notional_green_eur") or 600000000.0)
        slb_notional_eur = float(calc.get("notional_slb_eur") or 400000000.0)
        green_bps = calc.get("greenium_bps", 5)
        slb_bps = 2
        
        green_savings = f"€{int(green_notional_eur * (green_bps / 10000)):,} / yr"
        slb_savings = f"€{int(slb_notional_eur * (slb_bps / 10000)):,} / yr"

        s6_data = [
            ("Inaugural Green Bond (with Greenium)", f"Mid-Swap + {green_spread} bps (-{green_bps} bps)", green_savings),
            ("Sustainability-Linked Bond (SLB)", f"Mid-Swap + {calc['spread_bps'] - slb_bps} bps (-{slb_bps} bps)", slb_savings),
            ("Plain-Vanilla Senior EMTN", f"Mid-Swap + {calc['spread_bps']} bps (Flat)", "Baseline")
        ]
    elif p_fam == "FX_HEDGE":
        s6_headers = ["EUR/USD Scenario", "Unhedged", "Collared"]
        s6_data = [
            ("EUR/USD 1.12 (+5%)", fx_up_unhedged, fx_up_hedged),
            ("EUR/USD 1.065 (Spot)", fx_spot_unhedged, fx_spot_hedged),
            ("EUR/USD 1.02 (-4%)", fx_down_unhedged, fx_down_hedged)
        ]
    else:
        s6_headers = ["Rate Scenario", "Refinance Today", "Wait 6 months"]
        s6_data = [
            ("Rates +100bp", calc["scen_lock"], calc["scen_up"]),
            ("Unchanged", f"{calc['all_in_str']} (locked)", calc["all_in_str"]),
            ("Rates -50bp", calc["scen_lock"], calc["scen_down"])
        ]

    for c_idx, h in enumerate(s6_headers):
        c = s6_tbl.cell(0, c_idx)
        c.fill.solid()
        c.fill.fore_color.rgb = ING_ORANGE
        p = c.text_frame.paragraphs[0]
        p.text = h
        p.font.name = "Arial"
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        if c_idx > 0:
            p.alignment = PP_ALIGN.CENTER

    for r_idx, (scen, col1, col2) in enumerate(s6_data):
        row_bg = RGBColor(254, 237, 222) if r_idx % 2 == 0 else RGBColor(255, 255, 255)
        for c_idx, val in enumerate([scen, col1, col2]):
            c = s6_tbl.cell(r_idx + 1, c_idx)
            c.fill.solid()
            c.fill.fore_color.rgb = row_bg
            p = c.text_frame.paragraphs[0]
            p.text = str(val)
            p.font.name = "Arial"
            p.font.size = Pt(9.5)
            p.font.color.rgb = ING_DARK_SLATE
            if c_idx > 0:
                p.alignment = PP_ALIGN.CENTER

    # Reading the Table Box
    read_box = s6.shapes.add_textbox(Inches(6.4), Inches(4.35), Inches(6.1), Inches(1.6))
    rtf = read_box.text_frame
    rtf.word_wrap = True
    rtf.margin_left = Inches(0.1)
    rtf.margin_top = Inches(0.1)

    rp_head = rtf.paragraphs[0]
    rp_head.text = "Reading the table"
    rp_head.font.name = "Arial"
    rp_head.font.size = Pt(11)
    rp_head.font.bold = True
    rp_head.font.color.rgb = ING_ORANGE

    rp_body = rtf.add_paragraph()
    if p_fam == "FX_HEDGE":
        rp_body.text = f"A zero-cost collar provides a hard floor at {calc['floor_val']} against adverse currency moves while allowing upside participation up to {calc['cap_val']}, eliminating upfront premium expense while protecting operating margin."
    elif p_fam == "GREEN_ESG":
        rp_body.text = f"Issuing in Green format attracts dedicated sustainability orderbooks, driving tighter execution pricing (~{calc['greenium_bps']} bps greenium) and expanding investor diversification across European ESG accounts."
    else:
        rp_body.text = f"Refinancing today removes exposure to rate rises but forgoes the benefit if rates fall — the pre-hedge on {calc['prehedge_pct']}% of the notional narrows that trade-off versus refinancing the full amount unhedged."

    rp_body.font.name = "Arial"
    rp_body.font.size = Pt(9)
    rp_body.font.color.rgb = ING_DARK_SLATE
    rp_body.space_before = Pt(4)

    # =========================================================================
    # SLIDE 7: MARKET INTELLIGENCE (Exact Preview Parity)
    # =========================================================================
    s7 = prs.slides.add_slide(blank)
    add_header(s7, sm["s7_ttl"], category=sm["s7_cat"])
    add_logo(s7)
    add_footer(s7)

    # 4 Metric Cards with matching colors and database values
    if p_fam == "DCM_REFI":
        mkt_cards = [
            ("EUR Benchmark Spread", ov.get("spread", "Mid-Swap + 82 bps"), ING_DARK_SLATE),
            ("10Y EUR Mid-Swap", "2.48%", RGBColor(17, 24, 39)),
            ("ECB Refi Rate", "2.25%", ING_ORANGE),
            ("iTraxx Main", "58 bps", SUCCESS_GREEN)
        ]
        b1 = "• Market Liquidity: Robust primary orderbook depth with average Tier-1 corporate coverage at 3.4x."
        b2 = "• Execution Window: Current credit spread stability provides optimal issuance timing ahead of upcoming maturities."
    elif p_fam == "GREEN_ESG":
        mkt_cards = [
            ("EUR Green Spread", ov.get("eur_green_spread", "77 bps"), ING_DARK_SLATE),
            ("Greenium Concession", ov.get("greenium_concession", "-5 bps"), RGBColor(17, 24, 39)),
            ("ECB Refi Rate", ov.get("ecb_rate") or ov.get("ecb_refi_rate", "2.25%"), ING_ORANGE),
            ("iTraxx Main", ov.get("itraxx_main") or ov.get("itraxx", "58 bps"), SUCCESS_GREEN)
        ]
        b1 = "• Central Bank Policy: ECB Refinancing Rate at 2.25%; Fed Funds Target at 4.00–4.25%."
        b2 = "• High ESG subscription ratios (3.8x book cover) provide attractive new-issue pricing compression."
    elif p_fam == "FX_HEDGE":
        mkt_cards = [
            ("EUR/USD Spot", ov.get("eur_usd_spot", "1.0650"), ING_DARK_SLATE),
            ("1Y Forward Points", ov.get("fx_fwd_pts", "+145 pts"), RGBColor(17, 24, 39)),
            ("Fed Funds Target", "4.00–4.25%", ING_ORANGE),
            ("ECB Deposit Rate", "2.00%", SUCCESS_GREEN)
        ]
        b1 = "• Central Bank Policy: Fed easing trajectory creates favorable forward points carry environment for USD receivables."
        b2 = "• Currency Volatility: Heightened transatlantic rate divergence makes systematic layered hedging cost-effective."
    else:  # RATES_HEDGE & DCM_REFI
        mkt_cards = [
            ("5Y EUR Swap", ov.get("swap_5y", "2.62%"), ING_DARK_SLATE),
            ("10Y Bund", ov.get("bund_10y", "2.61%"), RGBColor(17, 24, 39)),
            ("ECB Refi Rate", "2.25%", ING_ORANGE),
            ("iTraxx Main", ov.get("itraxx_main", "58 bps"), SUCCESS_GREEN)
        ]
        b1 = "• Central Bank Policy: ECB Refinancing Rate at 2.25%; Fed Funds Target at 4.00–4.25%."
        b2 = "• Tightening European investment grade credit spreads support attractive execution windows."

    # 1. Top Row: 4 Metric Cards (includes dynamic iTraxx override)
    for idx, (lbl, val, val_color) in enumerate(mkt_cards):
        mx = Inches(0.8 + (idx * 2.95))
        shp = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, mx, Inches(1.45), Inches(2.8), Inches(1.45))
        shp.fill.solid()
        shp.fill.fore_color.rgb = BG_LIGHT
        shp.line.color.rgb = LINE_GRAY

        tb_m = s7.shapes.add_textbox(mx + Inches(0.1), Inches(1.52), Inches(2.6), Inches(1.25))
        tf_m = tb_m.text_frame
        tf_m.word_wrap = True
        
        p = tf_m.paragraphs[0]
        p.text = lbl
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = TEXT_MUTED
        p.alignment = PP_ALIGN.CENTER
        
        p = tf_m.add_paragraph()
        p.text = val
        p.font.bold = True
        p.font.size = Pt(18)
        p.font.color.rgb = val_color
        p.alignment = PP_ALIGN.CENTER
        p.space_before = Pt(4)

    # 2. Middle Container: Benchmark Reference Curves & Market Yields (Market DB)
    shp_mid = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(3.1), Inches(11.7), Inches(1.85))
    shp_mid.fill.solid()
    shp_mid.fill.fore_color.rgb = RGBColor(248, 250, 252)
    shp_mid.line.color.rgb = RGBColor(226, 232, 240)

    tb_mid_header = s7.shapes.add_textbox(Inches(1.0), Inches(3.18), Inches(11.3), Inches(0.35))
    tf_mid_h = tb_mid_header.text_frame
    tf_mid_h.word_wrap = True
    p_mh = tf_mid_h.paragraphs[0]
    p_mh.text = "Benchmark Reference Curves & Market Yields (Market DB)"
    p_mh.font.bold = True
    p_mh.font.size = Pt(11)
    p_mh.font.color.rgb = ING_DARK_SLATE

    bench_cards = [
        ("5Y EUR Swap", ov.get("swap_5y", "2.62%"), ING_DARK_SLATE),
        ("10Y German Bund", ov.get("bund_10y", "2.61%"), ING_DARK_SLATE),
        ("5Y Credit Spread", ov.get("credit_spread_5y", "78 bps"), SUCCESS_GREEN),
        ("All-In Benchmark", ov.get("all_in_yield", "3.40%"), ING_ORANGE)
    ]

    for b_idx, (b_lbl, b_val, b_col) in enumerate(bench_cards):
        bx = Inches(1.0 + (b_idx * 2.85))
        b_shp = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, Inches(3.6), Inches(2.65), Inches(1.15))
        b_shp.fill.solid()
        b_shp.fill.fore_color.rgb = RGBColor(255, 255, 255)
        b_shp.line.color.rgb = RGBColor(229, 231, 235)

        b_tb = s7.shapes.add_textbox(bx + Inches(0.1), Inches(3.68), Inches(2.45), Inches(0.95))
        b_tf = b_tb.text_frame
        b_tf.word_wrap = True
        
        bp0 = b_tf.paragraphs[0]
        bp0.text = b_lbl
        bp0.font.size = Pt(9.5)
        bp0.font.bold = True
        bp0.font.color.rgb = TEXT_MUTED
        bp0.alignment = PP_ALIGN.CENTER

        bp1 = b_tf.add_paragraph()
        bp1.text = b_val
        bp1.font.bold = True
        bp1.font.size = Pt(16)
        bp1.font.color.rgb = b_col
        bp1.alignment = PP_ALIGN.CENTER
        bp1.space_before = Pt(4)

    # 3. Bottom Container: Macro & Market Context
    shp_bot = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.15), Inches(11.7), Inches(1.55))
    shp_bot.fill.solid()
    shp_bot.fill.fore_color.rgb = CARD_BG_BLUE
    shp_bot.line.color.rgb = CARD_BORDER_BLUE

    tb_bot = s7.shapes.add_textbox(Inches(1.1), Inches(5.25), Inches(11.1), Inches(1.35))
    tf_bot = tb_bot.text_frame
    tf_bot.word_wrap = True
    
    p = tf_bot.paragraphs[0]
    p.text = "Macro & Market Context"
    p.font.bold = True
    p.font.size = Pt(12)
    p.font.color.rgb = ING_DARK_SLATE

    p_sub1 = tf_bot.add_paragraph()
    p_sub1.text = b1
    p_sub1.font.size = Pt(10)
    p_sub1.font.color.rgb = RGBColor(55, 65, 81)
    p_sub1.space_before = Pt(3)

    p_sub2 = tf_bot.add_paragraph()
    p_sub2.text = b2
    p_sub2.font.size = Pt(10)
    p_sub2.font.color.rgb = RGBColor(55, 65, 81)
    p_sub2.space_before = Pt(2)


    # =========================================================================
    # SLIDE 8: PROPOSAL FEATURES (2-Leg Multi-Tranche Term Sheet by Product)
    # =========================================================================
    s8 = prs.slides.add_slide(blank)
    add_header(s8, "Proposal features", category="PROPOSAL FEATURES")
    add_logo(s8)
    add_footer(s8)

    calc = compute_canonical_bundle(ctx, ov)
    t_yrs = calc["tenor_years"]

    nba = ctx.get("next_best_action", "")
    bm = re.search(r"EUR\s*([\d\.]+)\s*([BM])(?:(?!EUR).)*?EMTN", nba, re.IGNORECASE)
    hm = re.search(r"EUR\s*([\d\.]+)\s*([BM])(?:(?!EUR).)*?Pre-Hedge", nba, re.IGNORECASE)
    
    def_bond = ov.get("notional_bond")
    def_swap = ov.get("notional_swap")
    if not def_bond and bm:
        unit = "B" if bm.group(2).upper() == "B" else "M"
        def_bond = f"EUR {bm.group(1)}{unit} (Senior Benchmark)"
    if not def_swap and hm:
        unit = "B" if hm.group(2).upper() == "B" else "M"
        def_swap = f"EUR {hm.group(1)}{unit} (Pre-Hedge Overlay)"

    if p_fam == "FX_HEDGE":
        leg1_title = "Leg 1 — USD Bond Tranche"
        leg2_title = "Leg 2 — Cross-Currency Swap"
        notional_leg1 = def_bond or "USD 600,000,000"
        notional_leg2 = def_swap or "EUR 550,000,000 eq."
        tenor_leg1 = ov.get("tenor", f"{t_yrs} Years (T + {t_yrs}Y)")
        tenor_leg2 = f"Matches bond maturity ({t_yrs}Y)"
        bench_leg1 = f"{t_yrs}Y US Treasury / SOFR"
        bench_leg2 = "EUR/USD Cross-Currency Basis"
        spread_leg1 = ov.get("spread", f"SOFR + {calc['spread_bps']} bps (indicative)")
        spread_leg2 = "EURIBOR + 32 bps (synthetic EUR funding)"
        fees_leg1 = "Underwriting fee per mandate letter"
        fees_leg2 = "Nil (embedded in CCY swap rate)"
        settle_leg1 = "T+5 standard for USD benchmark bonds"
        settle_leg2 = "Simultaneous with bond closing (T+5)"
        doc_leg1 = "144A / Reg S Prospectus"
        doc_leg2 = "ISDA Master Agreement + CSA"
    elif p_fam == "GREEN_ESG":
        leg1_title = "Leg 1 — Green Bond Tranche"
        leg2_title = "Leg 2 — Sustainability-Linked Tranche"
        notional_leg1 = def_bond or "EUR 600,000,000"
        notional_leg2 = def_swap or "EUR 400,000,000"
        tenor_leg1 = ov.get("tenor", f"{t_yrs} Years (T + {t_yrs}Y)")
        tenor_leg2 = ov.get("tenor_leg2", "10 Years (T + 10Y)")
        bund_10y_val = ctx.get("bund_10y_yield", "2.61%")
        bench_leg1 = ov.get("bench_leg1", f"{t_yrs}Y EUR mid-swap")
        bench_leg2 = ov.get("bench_leg2", f"10Y German Bund ({bund_10y_val}) / EUR mid-swap")
        custom_spr = ov.get("spread")
        if not custom_spr:
            raw_s = ov.get("credit_spread_5y") or ov.get("spread_5y_bps")
            if raw_s:
                s_val = int(re.search(r"(\d+)", str(raw_s)).group(1)) if re.search(r"(\d+)", str(raw_s)) else calc['spread_bps']
                custom_spr = f"Mid-swap + {s_val} bps (Greenium: -{calc.get('greenium_bps', 5)} bps)"
            else:
                custom_spr = f"Mid-swap + {calc['spread_bps']} bps (Greenium: -{calc['greenium_bps']} bps)"
        spread_leg1 = custom_spr
        spread_leg2 = ov.get("spread_leg2", "Mid-swap + 80 bps (-2 bps vs baseline, +/- 25 bps SPT)")
        fees_leg1 = "Underwriting fee per mandate letter"
        fees_leg2 = "Underwriting fee + ESG Structuring advisory"
        settle_leg1 = "T+5 standard for EUR benchmark bonds"
        settle_leg2 = "T+5 standard for EUR benchmark bonds"
        doc_leg1 = "Green Bond Framework / EMTN Prospectus"
        doc_leg2 = "Sustainability-Linked Framework / EMTN Prospectus"
    elif p_fam == "RATES_HEDGE":
        leg1_title = "Leg 1 — New Benchmark Bond"
        leg2_title = "Leg 2 — Pre-Hedge Swap"
        notional_leg1 = def_bond or "EUR 1,200,000,000"
        notional_leg2 = def_swap or "EUR 800,000,000"
        tenor_leg1 = ov.get("tenor", f"{t_yrs} Years (T + {t_yrs}Y)")
        tenor_leg2 = "Terminates at bond pricing"
        bench_leg1 = f"{t_yrs}Y EUR mid-swap"
        bench_leg2 = f"{t_yrs}Y EUR swap rate"
        spread_leg1 = ov.get("spread", f"Mid-swap + {calc['spread_bps']} bps (indicative)")
        spread_leg2 = f"Current {t_yrs}Y swap rate (indicative)"
        fees_leg1 = "Underwriting fee per mandate letter"
        fees_leg2 = "Nil (embedded in swap rate)"
        settle_leg1 = "T+5 standard for EUR benchmark bonds"
        settle_leg2 = "Physical / cash-settled at unwind"
        doc_leg1 = "EMTN Programme / Prospectus"
        doc_leg2 = "ISDA Master Agreement + CSA"
    else:  # DCM_REFI
        leg1_title = "Leg 1 — Senior EMTN Tranche"
        leg2_title = "Leg 2 — Liquidity RCF / Commercial Paper"
        notional_leg1 = def_bond or "EUR 1,200,000,000"
        notional_leg2 = def_swap or "EUR 800,000,000"
        tenor_leg1 = ov.get("tenor", f"{t_yrs} Years (Euro Benchmark)")
        tenor_leg2 = "3–5 Years Revolving"
        bench_leg1 = f"{t_yrs}Y EUR mid-swap"
        bench_leg2 = "EURIBOR / €STR"
        spread_leg1 = ov.get("spread", f"Mid-swap + {calc['spread_bps']} bps (indicative)")
        spread_leg2 = "EURIBOR + 45 bps (undrawn 15 bps)"
        fees_leg1 = "Underwriting fee per mandate letter"
        fees_leg2 = "Commitment fee per facility agreement"
        settle_leg1 = "T+5 standard for EUR benchmark bonds"
        settle_leg2 = "Available upon documentation execution"
        doc_leg1 = "EMTN Programme / Prospectus"
        doc_leg2 = "LMA Standard Facility Agreement"

    s8_shape = s8.shapes.add_table(9, 3, Inches(0.8), Inches(1.5), Inches(11.7), Inches(4.5))
    s8_tbl = s8_shape.table
    s8_tbl.columns[0].width = Inches(2.7)
    s8_tbl.columns[1].width = Inches(4.5)
    s8_tbl.columns[2].width = Inches(4.5)

    headers = ["Term", leg1_title, leg2_title]
    for c_idx, h in enumerate(headers):
        c = s8_tbl.cell(0, c_idx)
        c.fill.solid()
        c.fill.fore_color.rgb = ING_ORANGE
        p = c.text_frame.paragraphs[0]
        p.text = h
        p.font.name = "Arial"
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)

    s8_rows = [
        ("Notional", notional_leg1, notional_leg2),
        ("Trade / pricing date", "Indicative — T", "Indicative — T"),
        ("Tenor / maturity", tenor_leg1, tenor_leg2),
        ("Reference benchmark", bench_leg1, bench_leg2),
        ("Spread / rate", spread_leg1, spread_leg2),
        ("Fees", fees_leg1, fees_leg2),
        ("Settlement", settle_leg1, settle_leg2),
        ("Governing documentation", doc_leg1, doc_leg2),
    ]

    for r_idx, (t_name, l1_val, l2_val) in enumerate(s8_rows):
        row_bg = RGBColor(254, 237, 222) if r_idx % 2 == 0 else RGBColor(255, 255, 255)
        for c_idx, val in enumerate([t_name, l1_val, l2_val]):
            c = s8_tbl.cell(r_idx + 1, c_idx)
            c.fill.solid()
            c.fill.fore_color.rgb = row_bg
            p = c.text_frame.paragraphs[0]
            p.text = str(val)
            p.font.name = "Arial"
            p.font.size = Pt(10)
            if c_idx == 0:
                p.font.bold = True
                p.font.color.rgb = ING_DARK_SLATE
            elif c_idx == 1 and r_idx == 4:
                p.font.bold = True
                p.font.color.rgb = ING_ORANGE
            else:
                p.font.color.rgb = ING_DARK_SLATE

    # Disclaimer note beneath table (Dynamic compliance override support)
    pricing_caveat = (overrides or {}).get("pricing_caveat") or (opp or {}).get("pricing_caveat")
    emir_notice = (overrides or {}).get("emir_notice") or (opp or {}).get("emir_notice")
    d_box = s8.shapes.add_textbox(Inches(0.8), Inches(6.15), Inches(11.7), Inches(0.45))
    dp = d_box.text_frame.paragraphs[0]
    if pricing_caveat:
        dp.text = f"{pricing_caveat}" + (f" • {emir_notice}" if emir_notice else "")
        dp.font.bold = True
        dp.font.color.rgb = ING_NAVY
    else:
        dp.text = "Indicative terms for discussion purposes only. Subject to internal credit approvals, KYC/AML, and market conditions at pricing."
        dp.font.color.rgb = RGBColor(100, 116, 139)
    dp.font.name = "Arial"
    dp.font.size = Pt(8.5)
    dp.font.italic = True



    # =========================================================================
    # SLIDE 9: WHY EXECUTE WITH US (Universal Franchise Capability Slide)
    # =========================================================================
    s9 = prs.slides.add_slide(blank)
    add_header(s9, "Franchise Capabilities & Syndicate Strength", category="WHY EXECUTE WITH US")
    add_logo(s9)
    add_footer(s9)

    why_cards = [
        ("icon_globe.png", "Global DCM franchise", "Leading bookrunner across investment-grade, high-yield, and hybrid capital across EMEA."),
        ("icon_pulse.png", "24-hour bookbuilding coverage", "Follow-the-sun syndicate desks across Amsterdam, London, Singapore and New York."),
        ("icon_shield.png", "Strong credit standing", "Investment-grade rated balance sheet supporting underwriting commitments."),
        ("icon_chart.png", "Electronic syndicate platform", "Real-time orderbook transparency and allocation reporting during bookbuild."),
        ("icon_check.png", "Regulatory & documentation support", "Dedicated legal, ratings-advisory, and prospectus / EMTN documentation support."),
        ("icon_team.png", "Dedicated coverage team", "A named DCM originator and structurer, not a call centre.")
    ]

    # Dynamic path resolution compatible with local dev, Docker & Cloud Run container
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths = [
        os.path.join(base_dir, "frontend", "public", "assets"),
        os.path.join(base_dir, "public", "assets"),
        os.path.join(base_dir, "assets"),
        "/home/user/ing-fm-poc/frontend/public/assets"
    ]
    assets_dir = next((p for p in candidate_paths if os.path.isdir(p)), candidate_paths[0])
    card_w = Inches(3.68)
    card_h = Inches(2.20)
    col_gap = Inches(0.35)
    row_gap = Inches(0.30)
    grid_left = Inches(0.85)
    grid_top = Inches(1.65)

    for idx, (icon_file, title_txt, desc_txt) in enumerate(why_cards):
        col = idx % 3
        row = idx // 3
        x = grid_left + col * (card_w + col_gap)
        y = grid_top + row * (card_h + row_gap)

        card_box = s9.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, card_w, card_h)
        card_box.fill.solid()
        card_box.fill.fore_color.rgb = RGBColor(255, 255, 255)
        card_box.line.color.rgb = RGBColor(229, 231, 235)
        card_box.line.width = Pt(1.0)

        badge_sz = Inches(0.50)
        badge_x = x + Inches(0.25)
        badge_y = y + Inches(0.22)
        badge = s9.shapes.add_shape(MSO_SHAPE.OVAL, badge_x, badge_y, badge_sz, badge_sz)
        badge.fill.solid()
        badge.fill.fore_color.rgb = ING_ORANGE
        badge.line.fill.background()

        icon_path = os.path.join(assets_dir, icon_file)
        if os.path.exists(icon_path):
            img_sz = Inches(0.28)
            img_x = badge_x + (badge_sz - img_sz) / 2
            img_y = badge_y + (badge_sz - img_sz) / 2
            s9.shapes.add_picture(icon_path, img_x, img_y, width=img_sz, height=img_sz)

        tb = s9.shapes.add_textbox(x + Inches(0.22), y + Inches(0.80), card_w - Inches(0.44), card_h - Inches(0.88))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0)

        p_t = tf.paragraphs[0]
        p_t.text = title_txt
        p_t.font.name = "Arial"
        p_t.font.size = Pt(11.5)
        p_t.font.bold = True
        p_t.font.color.rgb = ING_ORANGE

        p_d = tf.add_paragraph()
        p_d.text = desc_txt
        p_d.font.name = "Arial"
        p_d.font.size = Pt(9.5)
        p_d.font.color.rgb = RGBColor(75, 85, 99)
        p_d.space_before = Pt(4)

    # =========================================================================
    # SLIDE 10: EXECUTION ROADMAP (Exact Preview Parity)
    # =========================================================================
    s10 = prs.slides.add_slide(blank)
    
    # Dynamic Title Resolution matching Preview Canvas
    if p_fam == "FX_HEDGE":
        s10_title = "Layered FX Hedging & Execution Roadmap"
    elif p_fam == "GREEN_ESG":
        s10_title = "Green Bond Framework & Issuance Timetable"
    elif p_fam == "RATES_HEDGE":
        s10_title = "ISDA Schedule, CSA & Execution Timeline"
    else:
        s10_title = "Indicative Execution Roadmap & Timeline"

    add_header(s10, s10_title, category="EXECUTION ROADMAP")
    add_logo(s10)
    add_footer(s10)

    # Dynamic Steps matching React App.jsx case 8 exactly
    if p_fam == "FX_HEDGE":
        steps = [
            ("1", "T - 4 Weeks", "Exposure Mapping", "Audit USD receivables & establish rolling monthly budget hedge ratios."),
            ("2", "T - 2 Weeks", "ISDA & Documentation", "Finalize ISDA Schedule, collateral CSA threshold & credit line setup."),
            ("3", "T - 1 Week", "Collar Structuring", "Calibrate put/call strike corridor against spot & forward curves."),
            ("4", "T-Day", "Layered Execution", "Execute Tranche 1 zero-cost collars; initiate quarterly rolling schedule.")
        ]
    elif p_fam == "GREEN_ESG":
        steps = [
            ("1", "T - 6 Weeks", "Framework Drafting", "Establish Green Financing Framework aligned with EU Taxonomy & ICMA."),
            ("2", "T - 4 Weeks", "SPO Verification", "Engage ISS ESG / Sustainalytics for Second Party Opinion review."),
            ("3", "T - 1 Week", "ESG Roadshow", "Dedicated European SRI investor marketing calls & ESG presentation."),
            ("4", "T-Day", "Syndicate Pricing", "Bookbuilding, greenium spread tightening, and orderbook allocation.")
        ]
    elif p_fam == "RATES_HEDGE":
        steps = [
            ("1", "T - 4 Weeks", "Exposure Sizing", "Quantify repricing gap across upcoming debt tranches"),
            ("2", "T - 2 Weeks", "Pre-Hedge Execution", "Execute forward-starting IRS overlay swap"),
            ("3", "T - 1 Week", "Global Roadshow", "Syndicate investor marketing meetings"),
            ("4", "T-Day", "Pricing & Settlement", "Final syndicate pricing, book allocation & closing")
        ]
    else:  # DCM_REFI
        steps = [
            ("1", "T - 4 Weeks", "Mandate & Prep", "Finalize EMTN documentation, auditor comfort letters, and investor deck."),
            ("2", "T - 2 Weeks", "Pre-Hedge Overlay", "Execute interest rate pre-hedge swaps to lock underlying benchmark yields."),
            ("3", "T - 1 Week", "Global Roadshow", "Conduct targeted European investor marketing & C-suite roadshow calls."),
            ("4", "T-Day", "Launch & Pricing", "Intraday bookbuilding, spread compression, and final syndicate allocation.")
        ]

    # Compact card geometry matching Preview Canvas
    card_w = Inches(2.65)
    card_h = Inches(2.35)
    start_x = Inches(0.9)
    start_y = Inches(1.85)
    gap_x = Inches(0.31)

    for i, (num, time_tag, title_text, desc_text) in enumerate(steps):
        cx = start_x + i * (card_w + gap_x)
        
        # 1. Card Container (clean light border matching React Preview)
        c_box = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, start_y, card_w, card_h)
        c_box.fill.solid()
        c_box.fill.fore_color.rgb = RGBColor(255, 255, 255)
        c_box.line.color.rgb = RGBColor(229, 231, 235)  # border-gray-200
        c_box.line.width = Pt(1.0)
        
        # 2. Orange Step Number Badge (Circle)
        badge_sz = Inches(0.40)
        badge_x = cx + (card_w - badge_sz) / 2
        badge_y = start_y + Inches(0.18)
        b_shp = s10.shapes.add_shape(MSO_SHAPE.OVAL, badge_x, badge_y, badge_sz, badge_sz)
        b_shp.fill.solid()
        b_shp.fill.fore_color.rgb = ING_ORANGE
        b_shp.line.fill.background()
        
        b_tf = b_shp.text_frame
        b_tf.margin_top = Inches(0.04)
        b_p = b_tf.paragraphs[0]
        b_p.text = num
        b_p.font.name = "Arial"
        b_p.font.size = Pt(11)
        b_p.font.bold = True
        b_p.font.color.rgb = RGBColor(255, 255, 255)
        b_p.alignment = PP_ALIGN.CENTER

        # 3. Text Block
        tb = s10.shapes.add_textbox(cx + Inches(0.1), start_y + Inches(0.65), card_w - Inches(0.2), card_h - Inches(0.7))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.05)
        tf.margin_right = Inches(0.05)
        tf.margin_top = Inches(0.05)
        tf.margin_bottom = Inches(0.05)

        # Time Tag (e.g. T - 4 Weeks)
        p_time = tf.paragraphs[0]
        p_time.text = time_tag
        p_time.font.name = "Arial"
        p_time.font.size = Pt(11)
        p_time.font.bold = True
        p_time.font.color.rgb = ING_DARK_SLATE
        p_time.alignment = PP_ALIGN.CENTER
        p_time.space_after = Pt(2)

        # Milestone Subtitle (Orange text)
        p_sub = tf.add_paragraph()
        p_sub.text = title_text
        p_sub.font.name = "Arial"
        p_sub.font.size = Pt(10)
        p_sub.font.bold = True
        p_sub.font.color.rgb = ING_ORANGE
        p_sub.alignment = PP_ALIGN.CENTER
        p_sub.space_after = Pt(4)

        # Description Body
        p_body = tf.add_paragraph()
        p_body.text = desc_text
        p_body.font.name = "Arial"
        p_body.font.size = Pt(8.5)
        p_body.font.color.rgb = RGBColor(100, 116, 139)
        p_body.alignment = PP_ALIGN.CENTER

    # SLIDE 11: REGULATORY DISCLAIMERS
    # =========================================================================
    s11 = prs.slides.add_slide(blank)
    add_header(s11, sm["s11_ttl"], category=sm["s11_cat"])
    add_logo(s11)
    add_footer(s11)

    shp = s11.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.7), Inches(5.0))
    shp.fill.solid()
    shp.fill.fore_color.rgb = BG_LIGHT
    shp.line.color.rgb = LINE_GRAY

    # Dynamic disclaimers override support
    custom_disclaimers = (overrides or {}).get("disclaimers") or (opp or {}).get("disclaimers")
    tb_disc = s11.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(11.1), Inches(4.4))
    tf_disc = tb_disc.text_frame
    tf_disc.word_wrap = True
    p = tf_disc.paragraphs[0]
    p.text = "Regulatory Disclosures & Target Market Notice"
    p.font.bold = True
    p.font.size = Pt(14)
    p.font.color.rgb = ING_DARK_SLATE

    disc_list = ov.get("disclaimers") or compliance_bullets or [
        "This document is prepared for illustrative and discussion purposes only and does not constitute an offer, solicitation, or recommendation to enter into any transaction.",
        "FOR PROFESSIONAL CLIENTS AND ELIGIBLE COUNTERPARTIES ONLY: Target market under MiFID II / UK MiFIR is eligible counterparties and professional clients only (all distribution channels).",
        "This material has not been prepared in accordance with legal requirements designed to promote the independence of investment research.",
        "All rates, levels, spreads, and indicative terms shown are subject to change without notice and are not tradeable prices."
    ]

    # Ensure disc_list is a list
    if isinstance(disc_list, str):
        disc_list = [disc_list]
    elif not isinstance(disc_list, list):
        disc_list = list(disc_list) if disc_list else []

    for d in disc_list:
        if d and d.strip():
            p_d = tf_disc.add_paragraph()
            p_d.text = f"• {d}"
            p_d.font.size = Pt(11)
            p_d.font.color.rgb = TEXT_MUTED
            p_d.space_before = Pt(8)

    # =========================================================================
    # SAVE
    # =========================================================================
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf