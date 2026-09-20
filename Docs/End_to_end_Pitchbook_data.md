# End-to-End Data Binding — Dashboard to Pitchbook

**Version:** 20 September 2026 — Baseline (Flavor 1)
**Flavor:** Baseline (Flavor 1)
**Parallel flavor:** Weighted-Family + Adjacencies (Flavor 2) at `Docs/WeightedFamily/End_to_end_Pitchbook_data_20Sep_WeightedFamily.md`
**Branch:** `feat/dulcet-reset-pristine-semantic-dedup-all-UI-RM-HV-Slide2_LLM_Summary_Slide3_WhyNow_Action_17-Sep`
**Audience:** Engineers, product stakeholders

---

## 1. Overview

Every value rendered in the pitchbook traces to a specific source: a database row, a family-specific template, or a computed value derived from a source. There are no invented numbers.

The flow is:
Cloud SQL (ca schema)
│
▼
/api/opportunities (main.py)
• Reads client data, market data, signals, houseviews
• Runs mandate synthesis for whitelisted clients
• Returns a JSON payload per client
│
▼
fetch_pitchbook_bundle(client_id) (pitchbook_builder.py)
• Loads the same data into a context dict
• Reads anchor fields (why_now_nlg, next_best_action)
• Reads market curves and credit spreads
• Reads the family-specific maturity schedule
│
▼
detect_product_family(ctx)
• Selects one of FX_HEDGE / GREEN_ESG / RATES_HEDGE / DCM_REFI
• Flavor 1: uses keyword branches in the combined narrative
│
▼
build_pitchbook(ctx, opp, overrides)
• Renders 11 slides with python-pptx
• Each slide reads specific fields from the bundle
│
▼
Binary .pptx stream

text

The React preview canvas follows the same shape — it reads `activeClient` from the `/api/opportunities` response, applies the same `deckOverrides`, and renders the same 11 slides.

---

## 2. Data-Binding Table

The opportunity card's 4-segment grid feeds the bundle; the bundle feeds the slides. The chain is:

**DB row → opportunity card segment → bundle field → slide.**

| Card Segment | Source Field | Bundle / Slide Field | Pitchbook Slide |
|---|---|---|---|
| **Client Data** | `ca.ext_company_filings.net_debt_eur_m` (€58,500M for Enel) | `ctx.net_debt_str` | Slide 4 — Balance Sheet |
| **Client Data** | `ca.ext_company_filings.liquidity_eur_m` (€14,200M for Enel) | `ctx.liquidity_str` | Slide 4 |
| **Client Data** | `ca.ext_company_filings.debt_maturing_24m_eur_m` (€10,127M for Enel) | `ctx.debt_maturing_24m_bn` | Slide 4, Slide 5 |
| **Client Data** | `_CREDIT_RATINGS` dict (`"S&P \| BBB \| Positive"` for CLI101) | `ctx.credit_rating` | Slide 4 |
| **Client Data** | `ca.coverage_teams.banker_name` (Marco Bianchi for Enel) | `ctx.rm_name` | Slide 1 (Cover) |
| **Market Data** | `ca.mkt_rates_curves.swap_rate_pct` (5Y EUR swap 2.62% for Enel) | `ctx.swap_5y` | Slide 6, Slide 7 |
| **Market Data** | `ca.mkt_rates_curves.govt_yield_pct` (10Y Bund 2.61% for Enel) | `ctx.bund_10y` | Slide 7 |
| **Market Data** | `ca.ext_credit_spreads.spread_bps` (78 bps for Enel) | `ctx.credit_spread_5y` | Slide 6, Slide 7 |
| **Market Data** | Derived — `swap_5y + spread_bps/100` (3.40% for Enel) | `ctx.all_in_yield` | Slide 6, Slide 8 |
| **Context Fabric** | `ca.document_vector_chunks.text_content` WHERE `source_channel = 'WORKFABRIC_MEMO'` | `ctx.trigger_source` | Slide 2, Slide 3 |
| **Context Fabric** | `ca.digital_twin_signals.description` WHERE `signal_type = 'LATENT_OPPORTUNITY'` | `ctx.latent_opps` | Slide 3 (pillars) |
| **Houseviews & News** | `ca.document_vector_chunks.text_content` WHERE `source_channel IN ('PDF_REPORT', 'HOUSEVIEW')` | `ctx.houseview_summary` | Slide 3 (lineage tile 4) |
| **Houseviews & News** | `ca.document_vector_chunks.text_content` WHERE `source_channel IN ('NEWS_RSS', 'LIVE_RSS_NEWS', ...)` | `ctx.news_headline` | Slide 2, Slide 3 |
| **Synthesized Mandate** | `ca.ca_opportunity_scoring.why_now_nlg` | `ctx.why_now_nlg` | Slide 2, Slide 3 |
| **Synthesized Mandate** | `ca.ca_opportunity_scoring.next_best_action` | `ctx.next_best_action` | Slide 3, Slide 8 |
| **Synthesized Mandate** | LLM synthesis (5-key return) | `ctx.why_now_summary`, `action_summary`, `priority_score` | Slide 2, Slide 3 |
| **Maturity Schedule** | `ca.debt_maturity_schedule` (per-year rows) | `ctx["maturities"]` | Slide 5 |

**Values shown in parentheses are Enel's current DB state** — for illustration only. Each client's values are resolved from the DB at request time, filtered by `client_id`.

---

## 3. The Four Product Families

The pitchbook template is selected by `detect_product_family(ctx)`, which classifies the opportunity into one of four families. Slide titles and categories vary by family.

| Family | Deck theme |
|---|---|
| `FX_HEDGE` | FX & Commodity Risk Advisory |
| `GREEN_ESG` | Sustainable Finance Framework |
| `RATES_HEDGE` | Rate Risk Immunisation |
| `DCM_REFI` | Proactive Capital Structuring |

**Flavor 1 classification.** The family is determined by keyword matching in the concatenation of `opportunity_type`, `product_family`, `type`, `next_best_action`, `trigger_catalyst`, and `why_now_nlg`. The check order is:

1. `green`, `sustainable`, `esg`, `slb`, `sustainability` → `GREEN_ESG`
2. `fx`, `currency`, `collar`, `usd`, `hedging gap` → `FX_HEDGE`
3. `irs`, `pre-hedge`, `rate sensitivity`, `swap overlay` → `RATES_HEDGE`
4. `refinanc`, `dcm`, `emtn`, `bond`, `maturity wall` → `DCM_REFI`
5. Default → `DCM_REFI`

**The frontend mirrors this classification** in `App.jsx` (lines 627–629) with its own keyword branches, and passes the result as `product_family` in the deck generation request.

**For Enel, the family is `GREEN_ESG`.** The deck renders the Green / ESG template — slides "Decarbonization Catalyst", "ESG Balance Sheet", "Use of Proceeds Pool", "Greenium Sensitivity", "Green Bond Term Sheet".

---

## 4. Canonical Computation — `compute_canonical_bundle`

`compute_canonical_bundle(ctx, ov)` derives single-source-of-truth values used across multiple slides:

- **Tenor** — from overrides or the bundle's `tenor` field
- **Spread** — from `ca.ext_credit_spreads.spread_bps` or an override, formatted as `Mid-Swap + N bps`
- **Swap rate** — from `ca.mkt_rates_curves.swap_rate_pct` at the relevant tenor
- **All-in yield** — spread + benchmark rate
- **Tranches** — for term sheet slides (8), split into legs with notional, tenor, spread per tranche

**What it does not derive:** rate sensitivity scenarios. Those are computed at slide 6 and slide 8 render time, from the canonical bundle's values plus hardcoded scenario deltas (e.g. ±100 bps for the rate table).

---

## 5. Slide Binding Summary

All 11 slides populate from the bundle. The general pattern:

| # | Slide | Primary source |
|---|---|---|
| 01 | Cover Slide | `ca.client_master.client_name`, `_CREDIT_RATINGS`, `ca.coverage_teams.banker_name` |
| 02 | Family-specific Catalyst | `ctx.trigger_source`, `why_now_summary`, `action_summary` |
| 03 | Executive Summary | `why_now`, `action`, `get_product_pillars()` |
| 04 | Family-specific Balance Sheet | `net_debt_str`, `liquidity_str`, `debt_maturing_24m_bn`, `_CREDIT_RATINGS`, `revenue_str`, `ebitda_str` |
| 05 | Family-specific Maturity / Use of Proceeds / Exposure | `ctx["maturities"]` for maturity families; family template for others |
| 06 | Family-specific Sensitivity | `compute_canonical_bundle` output + scenario deltas |
| 07 | Family-specific Market Backdrop | `ca.mkt_rates_curves` + `ca.ext_credit_spreads` |
| 08 | Family-specific Term Sheet | `compute_canonical_bundle` + overrides |
| 09 | Why Execute With Us | Static capability cards |
| 10 | Family-specific Roadmap | Family-branched template |
| 11 | Family-specific Disclosures | `overrides.disclaimers` + family fallback |

**Slide count: 11.** Not 10.

---

## 6. Known Non-Deterministic / Fallback Cases

The flow is grounded, but not every value is deterministic. Known exceptions:

**Frontend `default*` constants.** `App.jsx` defines `defaultNetDebt`, `defaultLiquidity`, `defaultRevenue`, `defaultEbitda` per family. They fire when the API response doesn't supply a value. `/api/opportunities` currently does **not** expose `revenue_str` or `ebitda_str` for the client card — so the preview slide 4 falls back to the constants. For the current two clients, the constants are coincidence-correct. See `Data_or_Fabrication.md` §11.8.

**`pitchbook_builder.py:1045`.** A hardcoded `"€65,000M"` / `"€14,300M"` fallback fires if `revenue_str` or `ebitda_str` resolve to `"N/A"`. Dormant with the current bundle.

**`main.py:602`.** A hardcoded swap pre-hedge string fires only when `current_action` is empty for a `GREEN_ESG` client. Dormant for Enel (the curated narrative is populated).

**LLM synthesis non-determinism.** The mandate narrative (`why_now`, `action`) and `priority_score` vary across synthesis runs. The output is anchored (cannot invent tenors, spreads, or notionals that conflict with the anchor), but the phrasing and score are non-deterministic. See `Data_or_Fabrication.md` §6.2.

**What is *not* non-deterministic:** market rates, credit spreads, debt maturities, balance sheet metrics, credit rating, RM name. These trace to specific rows and do not change across requests unless the DB changes.

---

## 7. Cross-References

| Document | Relevant sections |
|---|---|
| `master_persona_20Sep.md` | §4 Component Map, §5 Slide Library, §6 Pipeline Behavior |
| `architecture_flow_20Sep.md` | §6 Pitchbook Generation |
| `Data_or_Fabrication.md` | §6 Priority Score, §11.7–11.9 Known Data Inconsistencies |
| `data_population.md` | Field-by-field lineage of every UI element |

---

*End of document.*