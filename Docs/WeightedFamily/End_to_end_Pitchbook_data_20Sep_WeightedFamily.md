# End-to-End Data Binding — Dashboard to Pitchbook (Flavor 2)

**Version:** 20 September 2026 — Weighted-Family + Adjacencies
**Flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Parallel flavor:** Baseline (Flavor 1) at `Docs/End_to_end_Pitchbook_data.md`
**Branch:** `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3`
**Audience:** Engineers, product stakeholders

---

## 1. Overview

Flavor 2 extends Flavor 1's end-to-end data binding with two synthesis-time capabilities — a validated product family classifier and a grounded adjacent-opportunities paragraph. The core flow is unchanged:
Cloud SQL (ca schema)
│
▼
/api/opportunities (main.py)
• Reads client data, market data, signals, houseviews
• Runs mandate synthesis for whitelisted clients (7-key return)
• Returns a JSON payload per client with two new fields:
family, adjacent_opportunities
│
▼
fetch_pitchbook_bundle(client_id) (pitchbook_builder.py)
• Loads the same data into a context dict
• Reads anchor fields (why_now_nlg, next_best_action)
• Reads market curves and credit spreads
• Reads the family-specific maturity schedule
• Enriched by handle_pitchbook_generation from the synthesis cache:
bundle["family"] ← _MANDATE_SYNTH_CACHE[cid][6]
bundle["adjacent_opportunities"] ← _MANDATE_SYNTH_CACHE[cid][7]
│
▼
detect_product_family(ctx)
• Reads the LLM's proposal from ctx["family"]
• Validates against the weighted anchor score (_FAMILY_KEYWORD_WEIGHTS)
• Decisive override at score ≥ 5 with margin ≥ 3; else trust LLM
│
▼
build_pitchbook(ctx, opp, overrides)
• Renders 11 slides with python-pptx
• Slide 3 has three cards (adds Adjacent Opportunities)
│
▼
Binary .pptx stream

text

---

## 2. Data-Binding Table

Same source chain as Flavor 1, with two new entries marked **[F2]**.

| Card Segment | Source Field | Bundle / Slide Field | Pitchbook Slide |
|---|---|---|---|
| **Client Data** | `ca.ext_company_filings.net_debt_eur_m` (€58,500M for Enel) | `ctx.net_debt_str` | Slide 4 |
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
| **Synthesized Mandate** | LLM synthesis (7-key return) | `ctx.why_now_summary`, `action_summary`, `priority_score` | Slide 2, Slide 3 |
| **Synthesized Mandate [F2]** | LLM synthesis — `family` key | `ctx.family` → `detect_product_family` → deck template selection | Determines slide titles across all family-specific slides |
| **Synthesized Mandate [F2]** | LLM synthesis — `adjacent_opportunities` key | `ctx.adjacent_opportunities` | Slide 3 (third card) |
| **Maturity Schedule** | `ca.debt_maturity_schedule` (per-year rows) | `ctx["maturities"]` | Slide 5 |

**Values shown in parentheses are Enel's current DB state** — for illustration only. Each client's values are resolved from the DB at request time, filtered by `client_id`.

**Note on [F2] fields.** `family` and `adjacent_opportunities` are not persisted to the DB — no column exists on `ca.ca_opportunity_scoring`, and §7.2 forbids DDL. They travel through the 8-tuple synthesis cache, the `/api/opportunities` response, and the pitchbook bundle, all within a single request lifecycle or cache window.

---

## 3. The Four Product Families

The pitchbook template is selected by `detect_product_family(ctx)`, which classifies the opportunity into one of four families.

| Family | Deck theme |
|---|---|
| `FX_HEDGE` | FX & Commodity Risk Advisory |
| `GREEN_ESG` | Sustainable Finance Framework |
| `RATES_HEDGE` | Rate Risk Immunisation |
| `DCM_REFI` | Proactive Capital Structuring |

**Flavor 2 classification.** Two signals are combined:

1. **LLM proposal.** The synthesis prompt returns `family` as the 6th of 7 keys. The prompt instructs the LLM to base the classification on the anchor's `next_best_action`, choose the dominant product (not purpose or feature), and apply a notional tiebreaker when multiple products are present.

2. **Weighted anchor validation.** `detect_product_family` scores `why_now_nlg + " " + next_best_action` against `_FAMILY_KEYWORD_WEIGHTS`. Strong product signals weight 5 (`green bond`, `slb`, `emtn`, `irs pre-hedge`, `fx collar`); weak context words weight 1–2 (`refinancing`, `maturity wall`, `dual-tranche`, `senior unsecured`).

**Decision logic:**

- If the top family's weighted score is **≥ 5 with a margin ≥ 3** over the runner-up → the weights **override** the LLM. Deterministic.
- Otherwise → trust the LLM's proposal.
- If both LLM and weights are silent → narrative keyword fallback (the Flavor 1 logic).

**Observed:**

| Client | Anchor score | Margin | Outcome |
|---|---|---|---|
| Enel (`CLI101`) | 15 GREEN_ESG vs 5 DCM_REFI | 10 | Decisive — guaranteed `GREEN_ESG` |
| BASF (`CLI103`) | 8 DCM_REFI vs 5 RATES_HEDGE | 3 | At threshold — LLM decides |

**Why the weighted validation matters.** A naive keyword classifier fails on narratives that legitimately contain vocabulary from multiple families — BASF's EMTN bond references a "greenium" feature, which would trip a green-first keyword order. The weighted hierarchy encodes the taxonomy: what's the *product*, not the *purpose* or *feature*. The LLM reads the full anchor; the weights enforce the hierarchy.

**For Enel, the family is `GREEN_ESG`.** The deck renders the Green / ESG template. **For BASF, the family is `DCM_REFI`** on the current synthesis (LLM's choice between DCM_REFI and RATES_HEDGE, both coherent).

---

## 4. Canonical Computation — `compute_canonical_bundle`

Same as Flavor 1. `compute_canonical_bundle(ctx, ov)` derives:

- **Tenor** — from overrides or the bundle's `tenor` field
- **Spread** — from `ca.ext_credit_spreads.spread_bps` or an override, formatted as `Mid-Swap + N bps`
- **Swap rate** — from `ca.mkt_rates_curves.swap_rate_pct` at the relevant tenor
- **All-in yield** — spread + benchmark rate
- **Tranches** — for term sheet slides (8), split into legs with notional, tenor, spread per tranche

**What it does not derive:** rate sensitivity scenarios. Those are computed at slide 6 and slide 8 render time.

**Flavor 2 does not modify `compute_canonical_bundle`.** The new fields — `family` and `adjacent_opportunities` — bypass the canonical bundle because they are not financial calculations. They flow directly from the synthesis cache to the deck.

---

## 5. Slide Binding Summary

All 11 slides populate from the bundle. Slide 3 differs from Flavor 1.

| # | Slide | Primary source |
|---|---|---|
| 01 | Cover Slide | `ca.client_master.client_name`, `_CREDIT_RATINGS`, `ca.coverage_teams.banker_name` |
| 02 | Family-specific Catalyst | `ctx.trigger_source`, `why_now_summary`, `action_summary` |
| 03 | Executive Summary | `why_now`, `action`, **`adjacent_opportunities` [F2]**, `get_product_pillars()` |
| 04 | Family-specific Balance Sheet | `net_debt_str`, `liquidity_str`, `debt_maturing_24m_bn`, `_CREDIT_RATINGS`, `revenue_str`, `ebitda_str` |
| 05 | Family-specific Maturity / Use of Proceeds / Exposure | `ctx["maturities"]` for maturity families; family template for others |
| 06 | Family-specific Sensitivity | `compute_canonical_bundle` output + scenario deltas |
| 07 | Family-specific Market Backdrop | `ca.mkt_rates_curves` + `ca.ext_credit_spreads` |
| 08 | Family-specific Term Sheet | `compute_canonical_bundle` + overrides |
| 09 | Why Execute With Us | Static capability cards |
| 10 | Family-specific Roadmap | Family-branched template |
| 11 | Family-specific Disclosures | `overrides.disclaimers` + family fallback |

**Slide count: 11.** Not 10.

### Slide 3 — Flavor 2 Layout

Slide 3 is the only slide whose layout differs from Flavor 1.

**Deck:**

- Left orange panel (x=0, w=3.0"): title, divider at y=1.42, subheading, focus text, then four pillars at y=3.55 with 1.0" spacing
- Right column (x=3.2, w=9.8"): three stacked full-width cards
  - Card 1 (Catalyst, orange): y=0.85, h=1.65"
  - Card 2 (Execution, blue): y=2.65, h=2.15"
  - Card 3 (Adjacent, green): y=4.95, h=2.15"

**Preview (`App.jsx`):**

- `col-span-3` orange panel with pillars as a vertical flex
- `col-span-9` right column with three cards using inline flex ratios (28% / 33% / 33%)

---

## 6. Known Non-Deterministic / Fallback Cases

Same as Flavor 1, with one Flavor 2 addition.

**Frontend `default*` constants.** `App.jsx` defines `defaultNetDebt`, `defaultLiquidity`, `defaultRevenue`, `defaultEbitda`. They fire when the API response doesn't supply a value. `/api/opportunities` does not expose `revenue_str` or `ebitda_str` for the client card — so the preview slide 4 falls back to the constants. For the current two clients, the constants are coincidence-correct. See `Data_or_Fabrication.md` §11.8.

**`pitchbook_builder.py:1045`.** A hardcoded `"€65,000M"` / `"€14,300M"` fallback fires if `revenue_str` or `ebitda_str` resolve to `"N/A"`. Dormant.

**`main.py:602`.** A hardcoded swap pre-hedge string fires only when `current_action` is empty for a `GREEN_ESG` client. Dormant.

**LLM synthesis non-determinism.** The mandate narrative, `priority_score`, and `adjacent_opportunities` paragraph vary across synthesis runs. The output is anchored but non-deterministic in phrasing. **Flavor 2:** the `family` key is also LLM-produced, but for the demo client the weighted validation is decisive (Enel → `GREEN_ESG` regardless of the LLM's proposal, because the margin is 10). For BASF the margin is 3 — the LLM decides between two coherent options. See `Data_or_Fabrication.md` §6.8, §6.9.

**What is *not* non-deterministic:** market rates, credit spreads, debt maturities, balance sheet metrics, credit rating, RM name, and — for the demo client — the product family.

---

## 7. What Flavor 2 Adds Over Flavor 1

| Aspect | Flavor 1 | Flavor 2 |
|---|---|---|
| Family selection | Keyword branches on the combined narrative | LLM proposal validated by `_FAMILY_KEYWORD_WEIGHTS` weighted scoring |
| Synthesis keys | 5 | 7 (`family` and `adjacent_opportunities` added) |
| Cache tuple | 6 | 8 |
| Slide 3 | Two cards (Catalyst, Execution) | Three cards (adds Adjacent Opportunities) |
| Slide 3 pillars | Right column | Left orange panel |
| Copilot slide_3 payload | `title`, `focus`, `why_now`, `action` | Adds `family` and `adjacent_opportunities` |
| Copilot response structure | Three sections | Three + conditional fourth (Adjacent Opportunities) |
| Copilot euro rendering | Possible `\u20ac` escape | `ensure_ascii=False` fix |
| Frontend family branch | Hardcoded keyword branches (lines 627–629) | Removed; reads `activeClient.family` |

Common (unchanged): data architecture, ingestion pipeline, DB schema, reset-to-pristine, defensive fallbacks, `priority_score` semantics, cache/DB consistency invariant, credit rating dict, compliance architecture, deployment topology.

---

## 8. Cross-References

| Document | Relevant sections |
|---|---|
| `Docs/WeightedFamily/master_persona_20Sep_WeightedFamily.md` | §2.1 Flavor Differential, §4 Component Map, §5 Slide 3, §6 Pipeline Behavior |
| `Docs/WeightedFamily/architecture_flow_20Sep_WeightedFamily.md` | §5.6 Product Family Classification, §5.7 Adjacent Opportunities, §6.5 Slide 3 Layout |
| `Docs/WeightedFamily/Data_or_Fabrication_20Sep_WeightedFamily.md` | §6.2, §6.8, §6.9, §9, §11.10 |
| `Docs/WeightedFamily/data_population_20Sep_WeightedFamily.md` | §2.1, §4.6 |
| `Docs/WeightedFamily/Different_Signals_Different_Products_20Sep_WeightedFamily.md` | Multi-family classification behavior |

---

*End of document.*