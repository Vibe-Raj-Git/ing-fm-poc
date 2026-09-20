# The Client Opportunity Card — Section Walkthrough

**Version:** 20 September 2026 — Weighted-Family + Adjacencies
**Flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Parallel flavor:** Baseline (Flavor 1) at `Docs/Explain_Left_Client_Section.md`
**Branch:** `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3`
**Audience:** Coverage leadership, product stakeholders

---

## 1. The Card At A Glance

The **Client Opportunity Card** is the primary origination surface of the platform. It sits on the left side of the workspace and combines three inputs into a single pitchable view:

1. **Internal client data** — balance sheet and coverage context from Cloud SQL
2. **Live market data** — benchmark rates, spreads, and yields from the same DB
3. **Synthesized mandate** — an LLM-generated catalyst narrative anchored to a curated DB row

The result: an RM opens the workspace, sees a specific opportunity for a specific client, and can open a client-ready pitchbook in one click.

**Demo state:** Enel S.p.A. (`CLI101`), `SUSTAINABLE FUNDING`, match confidence `High · 91–94`. All values shown in this document reflect Enel's current DB state.

---

## 2. Header Band

| Element | Source | Example |
|---|---|---|
| Opportunity classification chip | `ca.ca_opportunity_scoring.opportunity_type` | `SUSTAINABLE FUNDING` |
| Client name | `ca.client_master.client_name` | `Enel S.p.A.` |
| Tier + sector | `ca.client_master.tier`, `.industry_sector` | `Tier 1 (Electric Utilities)` |
| Match confidence | `_effective_score` — fresh synthesis score, else DB `priority_score` | `High · 94` |

**Match confidence bands** (fixed thresholds): `≥ 85 → High`, `70–84 → Medium`, `< 70 → Low`.

The score is **LLM-computed on every synthesis run** (18 Sep change, commit `13721ca`). It is not a static value. See `Data_or_Fabrication.md` §6.2 for the rubric and non-determinism characteristics.

---

## 3. The 2×2 Grid

The card renders four segments in a two-by-two grid. Each segment is fed by a specific set of DB queries.

### 3.1 Segment 1 — Client Data (Top-Left)

| Field | Source | Enel's current value |
|---|---|---|
| Coverage RM | `ca.coverage_teams.banker_name` (filtered to Relationship Manager) | Marco Bianchi |
| External ratings | `_CREDIT_RATINGS` dict (`main.py:89`) | `S&P \| BBB \| Positive` |
| Net Debt | `ca.ext_company_filings.net_debt_eur_m` | €58.5bn |
| Available Liquidity | `ca.ext_company_filings.liquidity_eur_m` | €14.2bn |
| Potential debt maturities within 24 months | `ca.ext_company_filings.debt_maturing_24m_eur_m` (formatted as `debt_maturing_24m_bn`) | €10.13bn |

**Note on the rating.** `ca.client_master` has no `credit_rating` column. The rating is a curated string from `_CREDIT_RATINGS` — a §8.1 exception documented in `Data_or_Fabrication.md` §11.7.

### 3.2 Segment 2 — Market Data (Top-Right)

| Field | Source | Enel's current value |
|---|---|---|
| 5Y EUR Swap | `ca.mkt_rates_curves.swap_rate_pct` WHERE `currency='EUR'` AND `tenor='5Y'` | 2.62% |
| 10Y German Bund | `ca.mkt_rates_curves.govt_yield_pct` WHERE `currency='EUR'` AND `tenor='10Y'` | 2.61% |
| 5Y Credit Spread | `ca.ext_credit_spreads.spread_bps` | 78 bps |
| All-In Benchmark Yield | Derived — `swap_5y + spread_bps / 100` | 3.40% |
| 5Y USD Swap Benchmark | `ca.mkt_rates_curves.swap_rate_pct` WHERE `currency='USD'` AND `tenor='5Y'` | 3.92% |

### 3.3 Segment 3 — Context Fabric (Bottom-Left)

Three sub-elements render here:

**Ingestion chips** — one chip per channel present for the client. The channel set is `WORKFABRIC_MEMO`, `TEAMS_CHAT`, `CLIENT_EMAIL`, and merge-aliases.

**Desk Signal** — reads the newest `WORKFABRIC_MEMO` chunk's `text_content`. This is the internal desk note that grounds the "why this client, why now."

**Latent Opportunity** — lists up to 3 `LATENT_OPPORTUNITY` signals from `ca.digital_twin_signals`, ordered by `signal_id ASC`. Rendered as L-01, L-02, L-03.

### 3.4 Segment 4 — Houseviews & News (Bottom-Right)

**Houseview chip** — reads the newest `PDF_REPORT` or `HOUSEVIEW` chunk's `source_name` and `structured_metadata.executive_summary`.

**Live Verified News** — reads the newest news-alias chunk's `text_content`; the headline is extracted from the `[1] HEADLINE:` marker if present.

---

## 4. Synthesized Mandate & AI Catalyst (Below The Grid)

Below the 2×2 grid, a full-width section renders the mandate narrative and its lineage.

### 4.1 Lineage Tiles

Four tiles show the provenance chain:

| Tile | Source |
|---|---|
| 1. Balance Sheet: Liquidity Buffer | `liquidity_eur_m` formatted as `€14.2bn` |
| 2. Market DB | `5Y Swap 2.62% / 78 bps` |
| 3. Context Fabric | `ca.digital_twin_signals.metric_value` — Enel: `€12bn financing capacity` |
| 4. Houseview / News | Derived from the winning houseview chunk's `structured_metadata` |

### 4.2 Narrative Cards

Two cards render the mandate:

- **🎯 Catalyst Rationale (Why Now)** — `why_now_nlg` from `ca.ca_opportunity_scoring`, potentially rewritten by LLM synthesis with the drift guard applied
- **💼 Proposed Execution & Structuring** — `next_best_action`, same treatment

**Enel's current narrative:**

- **Why now:** *"Enel faces a critical €10.13bn debt maturity wall in 2026-2027, necessitating proactive refinancing despite its robust €14.2bn liquidity buffer…"*
- **Action:** *"We propose a €1.0bn dual-tranche senior unsecured issuance, strategically leveraging Enel's €3.5bn green asset pool through a €600m 7Y Green bond priced at Mid-swap + 73 bps (net of -5 bps greenium), complemented by a €400m 10Y Sustainability-Linked Bond…"*

---

## 5. Priority Today Sidebar (Right Rail)

The sidebar ranks clients by `_effective_score DESC`. Each entry shows the badge (opportunity type + rank + score), the client name, the fee estimate, and the first sentence of `why_now_nlg`.

**Whitelist guarantee (18 Sep, `13721ca`).** After the top-4 slice, the endpoint appends any whitelisted client not already present. This ensures the demo client always renders even if its score drops below the slice threshold.

---

## 6. Action Bar

Two buttons at the bottom of the card:

| Button | Purpose |
|---|---|
| **Ingestion Engine** | Opens the modal to paste text, upload PDF/PPTX, or trigger an RSS fetch. New content recalibrates the Digital Twin. |
| **Open draft pitchbook ↗** | Opens the 11-slide preview canvas with the pitchbook deck, compliance checker, and `.pptx` export. |

The `handleDownloadDeck` path sends the current overrides (including `why_now`, `action`, `why_now_summary`, `action_summary`) to the backend.

---

## 7. Family Selection (Flavor 2)

When the RM opens the draft pitchbook, the deck template is chosen by `detect_product_family(ctx)` in `pitchbook_builder.py`. In Flavor 2, the classification combines two signals:

1. **LLM proposal.** The synthesis prompt returns `family` as the 6th of 7 keys — one of `FX_HEDGE`, `GREEN_ESG`, `RATES_HEDGE`, `DCM_REFI`. The LLM bases this on the anchor's `next_best_action`, choosing the dominant product (not purpose or feature) with a notional tiebreaker.

2. **Weighted anchor validation.** `detect_product_family` scores `why_now_nlg + " " + next_best_action` against `_FAMILY_KEYWORD_WEIGHTS`. Strong product signals weight 5 (`green bond`, `slb`, `emtn`, `irs pre-hedge`, `fx collar`); weak context words weight 1–2 (`refinancing`, `maturity wall`, `dual-tranche`, `senior unsecured`).

**Decision:**

- Weighted score **≥ 5 with a margin ≥ 3** over the runner-up → weights override. Deterministic.
- Otherwise → trust the LLM's proposal.
- If both are silent → narrative keyword fallback.

**Observed:**

| Client | Anchor score | Margin | Outcome |
|---|---|---|---|
| Enel (`CLI101`) | 15 GREEN_ESG vs 5 DCM_REFI | 10 | Decisive — guaranteed `GREEN_ESG` |
| BASF (`CLI103`) | 8 DCM_REFI vs 5 RATES_HEDGE | 3 | At threshold — LLM decides |

**For Enel, the family is `GREEN_ESG`.** The deck renders the Green/ESG template. The `family` field is exposed in `/api/opportunities`; the frontend reads `activeClient.family` — the pre-20Sep frontend keyword branches (lines 627–629) have been removed.

## 8. The Pitchbook Preview — Flavor 2 Additions

The `Open draft pitchbook ↗` button leads to an 11-slide preview canvas, same as Flavor 1. **Slide 3 (Executive Summary) has a Flavor 2 layout rework:**

- Four pillars relocated into the left orange panel
- Three stacked full-width cards in the right column: Catalyst Rationale, Proposed Execution, and **Adjacent Opportunities** (new)

The Adjacent Opportunities card renders the `adjacent_opportunities` field from the bundle — an LLM-written 80–140 word paragraph identifying up to 3 grounded cross-sell angles. See `master_persona_20Sep_WeightedFamily.md` §5 for the layout, `Data_or_Fabrication_20Sep_WeightedFamily.md` §6.9 for the lifecycle.

## 9. The 30-Second Executive Pitch

> *"This is our Real-Time Client Opportunity Twin. Instead of an RM manually cross-referencing a client's balance sheet, live market rates, and news feeds, this card unifies all three in one view.*
>
> *The Client Data segment shows Enel's €58.5bn net debt and €14.2bn liquidity buffer. The Market Data segment shows the live 5Y EUR swap at 2.62% and the 5Y credit spread at 78 bps. The Synthesized Mandate below gives the headline recommendation: a €1.0bn dual-tranche green issuance refinancing the €10.13bn maturity wall.*
>
> *Behind the scenes, the platform has processed every ingested signal and classified Enel into the Green/ESG product family — validated by a weighted taxonomy, deterministic for the demo. One click on Open draft pitchbook generates an 11-slide deck. Slide 3 shows the primary pitch plus an Adjacent Opportunities card, summarising the cross-sell angles we've identified — a rate pre-hedge, an FX exposure review, possible liability management.*
>
> *Every number on this card traces to a specific row in a specific table, filtered by client_id."*

## 10. Cross-References

| Document | Relevant sections |
|---|---|
| `Docs/WeightedFamily/master_persona_20Sep_WeightedFamily.md` | §2.1 Flavor Differential, §5 Slide 3, §6 Pipeline Behavior |
| `Docs/WeightedFamily/architecture_flow_20Sep_WeightedFamily.md` | §5.6, §5.7, §6.5 |
| `Docs/WeightedFamily/Data_or_Fabrication_20Sep_WeightedFamily.md` | §6.2, §6.8, §6.9, §11.10 |
| `Docs/WeightedFamily/Different_Signals_Different_Products_20Sep_WeightedFamily.md` | Multi-family classification |

---

*End of document.*