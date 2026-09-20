# Different Signals, Different Products — How Flavor 2 Classifies Multi-Family Clients

**Version:** 20 September 2026 — Weighted-Family + Adjacencies
**Flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Parallel flavor:** Baseline (Flavor 1) at `Docs/Different_Signals_Different_Products.md`
**Branch:** `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3`
**Audience:** Product stakeholders, engineers, coverage leadership

---

## 1. The Problem

A client's ingested signals rarely fit neatly into one product family. Enel's corpus, for example, spans:

- **Green/ESG** — the €600m 7Y Green bond and €400m 10Y SLB in the curated mandate
- **Rates** — the €1.20% legacy coupon refinancing risk and the swap-rate backdrop
- **FX** — USD-linked procurement and cross-currency exposure noted in the latent signals
- **DCM** — the €10.13bn maturity wall concentrated in 2026–2027

BASF's corpus spans DCM (the €4.0B 6Y EMTN refinancing), Rates (the €1.2B 6Y IRS pre-hedge), and M&A financing (the Coatings carve-out).

**A coverage RM does not want to see one card per product family.** The RM's meeting with the client's treasurer is a single conversation. The pitchbook is one document. If the platform shows four cards for Enel, the RM faces a decision the platform should have already made: which deck do I open?

**Flavor 2 answers the question with a specific architecture:**

1. **One opportunity per client.** The platform produces a single opportunity card and a single pitchbook, regardless of how many product families the signal corpus touches.
2. **One dominant family drives the deck.** The classification is made by the synthesis LLM and validated by a weighted vocabulary.
3. **The other families surface as an adjacency paragraph.** A grounded 80–140 word section on Slide 3 identifies up to three cross-sell angles — the "what else we see" layer of the pitch.

---

## 2. The Core Behavioral Flow
[ Ingested Signals / Context Fabric ]
│
▼
┌─────────────────────────────────────────┐
│ Synthesis: LLM proposes dominant family │
│ Reads anchor + full signal corpus │
└─────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────┐
│ Validation: weighted anchor scoring │
│ _FAMILY_KEYWORD_WEIGHTS │
│ Decisive override or trust LLM │
└─────────────────────────────────────────┘
│
┌───────────────┴───────────────┐
▼ ▼
One opportunity card One adjacency paragraph
Enel S.p.A. — GREEN_ESG "Pre-hedge, FX review,
Deck: Green / ESG Template liability management"
Slide 3 shows the primary Grounded in the signals
recommendation Rendered as Card 3 on Slide 3

text

**The client sees one deck with the primary pitch and a supplementary cross-sell section.** No family is lost — every signal feeds either the primary classification or the adjacency paragraph.

---

## 3. How The Family Is Chosen

The synthesis LLM returns `family` as one of seven keys — `FX_HEDGE`, `GREEN_ESG`, `RATES_HEDGE`, or `DCM_REFI`. The prompt instructs the LLM to base the classification on the anchor's `next_best_action`, choose the dominant *product* (not purpose or feature), and apply a notional tiebreaker when multiple products are present.

**The LLM's proposal is validated by `detect_product_family` in `pitchbook_builder.py`:**

1. **Weighted anchor scoring.** For each family, sum `_FAMILY_KEYWORD_WEIGHTS[fam]` for every keyword present in the concatenation of `why_now_nlg + " " + next_best_action`. Strong product signals weight 5 (`green bond`, `slb`, `emtn`, `irs pre-hedge`, `fx collar`); weak context words weight 1–2 (`refinancing`, `maturity wall`, `dual-tranche`, `senior unsecured`).
2. **Decision:**
   - If the top family's weighted score is **≥ 5 with a margin ≥ 3** over the runner-up → the weights **override** the LLM. Deterministic.
   - Otherwise → trust the LLM's proposal.
   - If both LLM and weights are silent → fall back to narrative keyword classification.

**Why the weighted validation matters.** A naive keyword classifier fails on narratives that legitimately contain vocabulary from multiple families. BASF's anchor mentions "EMTN" and "greenium" — the word "green" would trip a green-first keyword order and misclassify the deal. The weighted hierarchy encodes the taxonomy: the *product* dominates the *purpose* or *feature*. The LLM reads the full anchor; the weights enforce the hierarchy.

**Observed classifications:**

| Client | Anchor score | Margin | Outcome |
|---|---|---|---|
| Enel (`CLI101`) | 15 GREEN_ESG vs 5 DCM_REFI | 10 | Decisive — guaranteed `GREEN_ESG` |
| BASF (`CLI103`) | 8 DCM_REFI vs 5 RATES_HEDGE | 3 | At threshold — LLM decides; either family coherent |

For Enel, the classification is deterministic: the demo client's family does not vary across synthesis runs. For BASF, the LLM's semantic reasoning picks between two defensible families.

---

## 4. How The Adjacency Paragraph Captures The Other Families

The synthesis LLM also returns `adjacent_opportunities` — a single 80–140 word business-English paragraph identifying up to three cross-sell angles beyond the primary mandate.

**The prompt enforces:**

- **Grounded** — each adjacency must cite a specific signal that appears in the corpus.
- **No invention** — return an empty string if no adjacencies are supported.
- **No repetition** of the primary mandate.
- **Maximum 3** adjacencies, prioritised by notional or urgency.
- **Business English**, no marketing language.

**Observed Enel output (one synthesis run):**

> "Enel's significant €10.13bn debt maturity wall and potential USD FX exposure indicate a broader multi-channel treasury review is warranted. Given the material increase in financing costs as legacy debt is refinanced at higher indicative yields, ING can offer comprehensive interest rate hedging solutions to mitigate future rate risk. Furthermore, the identified potential USD FX exposure and the need to review currency risk present an opportunity for ING to provide tailored FX hedging strategies. The board's authorization for up to €12bn in financing through March 2027 also suggests further DCM or bank lending opportunities beyond this specific issuance."

This is the Flavor 2 answer to "the corpus has signals in multiple families" — the primary family (Green/ESG) drives the deck, and the other families (Rates, FX, DCM) are surfaced as concrete, grounded cross-sell suggestions.

**Non-determinism.** The paragraph varies across synthesis runs, like `priority_score`. Different runs produce different wordings. This is expected — the LLM reads the corpus and writes a fresh summary each cache miss. Both observed variants are grounded, non-repetitive, and actionable.

---

## 5. What The Demo Looks Like

**One card per client.** For Enel whitelisted alone, the cohort header reads **`1 opportunity surfaced`**. When both Enel and BASF are whitelisted, it reads **`2 opportunities surfaced`** — one per client.

**The primary family drives the deck template.** For Enel, the template is **Green / ESG** (slides: "Decarbonization Catalyst", "ESG Balance Sheet", "Use of Proceeds Pool", "Greenium Sensitivity", "Green Bond Term Sheet"). For BASF, **DCM Refi** (slides: "Strategic Catalyst", "Balance Sheet Foundation", "Debt Maturity Profile", "Refinancing Sensitivity", "EMTN Term Sheet").

**Slide 3 renders the primary and the adjacencies together.** The Executive Summary slide shows three stacked cards:

- 🎯 **Catalyst Rationale (Why Now)** — the primary narrative
- 💼 **Proposed Execution & Structuring** — the primary deal structure
- 🧭 **Adjacent Opportunities** — the cross-sell paragraph

**The Copilot has both.** Asking "explain Slide 3" produces the mandatory three sections plus a conditional fourth section — Adjacent Opportunities. Asking "what adjacent and latent opportunities do we have?" produces two distinct responses: adjacencies from the `adjacent_opportunities` field, latents from the WorkFabric signals.

---

## 6. Why Not Multiple Opportunity Cards

A multi-card architecture — one card per (client, product family) pair — was considered. It is not implemented.

**What it would require:**

- Multiple rows in `ca.ca_opportunity_scoring` per client, one per family
- A read path that iterates scoring rows rather than taking one per client
- Per-family anchor narratives
- Per-family market data slices (FX needs forward points and implied vol; Green needs greenium; Rates needs the swap curve)
- N pitchbooks per client, each with its own template selection
- Frontend rendering of N cards per client, each clickable, each routing to its own deck

**Why it isn't built:**

1. **The demo doesn't need it.** A single deck with a primary pitch and an adjacency section delivers the same client-facing message — "here's the main recommendation, plus what else we see." The RM walks in with one document, not four.
2. **The complexity is not proportional to the value.** Two additional anchors, two additional market-data slices, two additional pitchbooks — for a use case the adjacency paragraph already covers.
3. **The client conversation is one conversation.** A treasurer does not walk through four separate decks in one meeting. The primary pitch leads; the adjacencies are a natural follow-on within the same document.

**If the multi-card architecture is revisited**, the platform already has most of the primitives: `ca_opportunity_scoring` supports multiple rows per client (one-to-many with `client_master`), the four family templates exist, and `detect_product_family` classifies per opportunity. The change would be in the read path, market-data plumbing, frontend rendering, and pitchbook generation. That's a multi-session workstream, not a small extension.

**For now, the dominant-family-plus-adjacencies approach serves the purpose:**

- Every signal in the corpus is captured — either as primary classification input, as adjacency content, or both.
- The client sees a single, coherent pitch.
- The RM's meeting is one conversation with one deck.
- The platform demonstrates that it has read the whole corpus, not just the loudest signals.

---

## 7. Cross-References

Sibling documents in this folder:

| Document | Relevant sections |
|---|---|
| `master_persona_20Sep_WeightedFamily.md` | §2.1 Flavor Differential, §5 Slide 3 Content Sources, §6 Pipeline Behavior |
| `architecture_flow_20Sep_WeightedFamily.md` | §5.6 Product Family Classification, §5.7 Adjacent Opportunities, §6.5 Slide 3 Layout |
| `Data_or_Fabrication_20Sep_WeightedFamily.md` | §6.8 Product family as synthesis output, §6.9 Adjacent opportunities as synthesis output |
| `data_population_20Sep_WeightedFamily.md` | §2.1 Family-derived predicates, §4.6 Slide 3 update |

---

*End of document.*