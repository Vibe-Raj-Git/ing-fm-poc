# Weighted-Family + Adjacencies — Flavor 2 Documentation

**Flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Branch:** `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3`
**Date:** 20 September 2026
**Parallel flavor:** Baseline (Flavor 1) at `feat/dulcet-reset-pristine-semantic-dedup-all-UI-RM-HV-Slide2_LLM_Summary_Slide3_WhyNow_Action_17-Sep`

This folder holds the complete documentation set for **Flavor 2** of the ING Financial Markets Deal Intelligence Platform. Flavor 2 extends Flavor 1 (Baseline) with two synthesis-time capabilities and a Slide 3 layout rework.

## What Flavor 2 Adds

Flavor 2 changes three layers of the platform:

**1. Synthesis layer — two new prompt keys.**

The mandate synthesis prompt now returns **seven keys** instead of five:

- `family` — the product family the LLM classifies the opportunity into: `FX_HEDGE`, `GREEN_ESG`, `RATES_HEDGE`, or `DCM_REFI`
- `adjacent_opportunities` — an 80–140 word business-English paragraph identifying up to 3 grounded cross-sell angles supported by the signal corpus

Both travel through the 8-tuple synthesis cache to the API response and the pitchbook bundle. Neither is persisted to the database — §7.2 forbids DDL, and no `family` or `adjacent_opportunities` column exists on `ca.ca_opportunity_scoring`.

**2. Pitchbook layer — weighted family classification + Slide 3 rework.**

- **Product family classifier.** The LLM's `family` proposal is validated by `_FAMILY_KEYWORD_WEIGHTS`, a weighted vocabulary that encodes the ING product taxonomy. Strong product signals (weight 5: `green bond`, `slb`, `emtn`, `irs pre-hedge`, `fx collar`) dominate weak context words (weight 1–2: `refinancing`, `maturity wall`, `dual-tranche`). When the anchor's weighted score is decisive (≥ 5 with margin ≥ 3), the weights override the LLM. Otherwise the LLM is trusted. When both are silent, a narrative keyword fallback fires.
- **Slide 3 layout.** The four pillars moved from the right column into the left orange panel. The right column now holds three stacked full-width cards: Catalyst Rationale, Proposed Execution, and **Adjacent Opportunities** (new).
- **Frontend hardcode removed.** The pre-20Sep frontend keyword branches on `opportunity_type` and client name are gone. The frontend reads `activeClient.family` from the API.

**3. Copilot layer — conditional fourth section + encoding fix.**

- The Copilot's `slide_3` payload now carries both `family` and `adjacent_opportunities`.
- The mandatory three-section response structure gains a conditional fourth section — **Adjacent Opportunities** — that appears only when the field is non-empty.
- `json.dumps(..., ensure_ascii=False)` in the Copilot prompt serialization so real `€` characters reach the LLM. Prior to this fix, the Copilot occasionally echoed `\u20ac` in replies for Slide 3 while Slide 2 rendered `€`.
- The prompt now requires bolding monetary amounts, percentages, and tenors in the "Key Mechanics & Deal Metrics" section.

## What Is Common With Flavor 1

Data architecture, ingestion pipeline, database schema, reset-to-pristine mechanism, defensive fallbacks, `priority_score` semantics, cache/DB consistency invariant, credit rating dict (`_CREDIT_RATINGS`), demo narratives, compliance architecture, deployment topology. All unchanged.

## Documentation In This Folder

| Document | Purpose |
|---|---|
| `master_persona_20Sep_WeightedFamily.md` | Persona and architectural context. §2.1 has the full Flavor Differential table. §7.11, §8.7, §13 are Flavor 2-specific. |
| `architecture_flow_20Sep_WeightedFamily.md` | Complete architecture reference. §5.6 (product family classification), §5.7 (adjacent opportunities), §6.5 (Slide 3 layout), §7.2 (Copilot additions), §11 (principles 11–13). |
| `Data_or_Fabrication_20Sep_WeightedFamily.md` | Zero-fabrication spec. §6.2 (7-key prompt), §6.8 (product family), §6.9 (adjacent opportunities), §9 (Copilot additions), §11.10 (`_FAMILY_KEYWORD_WEIGHTS` sync). |
| `data_population_20Sep_WeightedFamily.md` | Field-by-field UI lineage. §2.1 (family-derived predicates), §4.6 (Slide 3 update). |
| `Different_Signals_Different_Products_20Sep_WeightedFamily.md` | How Flavor 2 classifies multi-signal clients. Dominant family + adjacency paragraph. Multi-card architecture noted as a future option. |
| `End_to_end_Pitchbook_data_20Sep_WeightedFamily.md` | End-to-end data binding from the dashboard to the pitchbook. Corrected slide count (11), four real families, known exceptions, Flavor 2-specific additions. |
| `Explain_Left_Client_Section_20Sep_WeightedFamily.md` | Section walkthrough of the Client Opportunity Card — the 2×2 grid, the Synthesized Mandate section, the Priority Today sidebar, the Action Bar, and the family classifier. Includes a 30-second executive pitch. |
| `Signals,_Opportunities_&_Pitchbook_Lifecycle_20Sep_WeightedFamily.md` | End-to-end lifecycle: signal arrival → accumulation → discovery → ranking → preview → PPTX → compliance. Includes the Flavor 2 classification and adjacent-opportunities additions. |

## Demo Talking Points

The Flavor 2 demo introduces two ideas to the client. Both are grounded in the ingested signal corpus — nothing is invented.

**Primary pitch.** The dominant opportunity as before — for Enel, the €1.0bn dual-tranche green issuance refinancing the €10.13bn maturity wall. This remains the headline recommendation. Flavor 2's classifier selects the Green/ESG deck template deterministically (Enel's anchor scores 15 GREEN_ESG vs 5 DCM_REFI, a margin of 10 — decisive).

**Supplementary section — Adjacent Opportunities.** The platform has processed every ingested signal, not just the primary drivers. Slide 3's third card surfaces what else ING can pitch. For Enel, the paragraph cites a rate pre-hedge, a USD FX exposure review, and liability-management structuring. For BASF, it cites M&A carve-out financing and derivatives advisory alongside the primary EMTN refinancing.

**Voiceover guidance.** The RM presents the primary recommendation first, then points at the third card: *"Beyond the primary issuance, we've processed the full signal corpus and identified adjacent angles worth a conversation — a pre-hedge ahead of pricing, an FX review of the USD-linked procurement flows, and possible liability management. These aren't part of the primary proposal, but they're on the table if you'd like to explore them."*

The adjacent opportunities are a **supplementary section**, not a substitute for the primary pitch. They demonstrate that the platform is reading the whole corpus, not just the loudest signals.

## Verification

Three checks after deploy:

**1. API returns both new fields:**

```bash
SVC_URL=$(gcloud run services describe ing-fm-poc-service \
  --region europe-west1 --project dulcet-radar-508218-c5 \
  --format "value(status.url)")

curl -s "$SVC_URL/api/opportunities" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for o in d:
    if o.get('id') in ('CLI101', 'CLI103'):
        print(o.get('id'), '| family:', o.get('family'), '| adjacent present:', bool(o.get('adjacent_opportunities')))
"
```

Expected output:

```
CLI101 | family: GREEN_ESG | adjacent present: True
CLI103 | family: DCM_REFI | adjacent present: True
```

**2. Slide 3 preview shows three cards.**

Open the pitchbook preview in the browser, navigate to Slide 3. Verify:

- Four pillars inside the orange panel
- Three stacked cards on the right: Catalyst Rationale, Proposed Execution, Adjacent Opportunities

**3. Copilot answers about adjacencies.**

Load the UI to populate the cache, then ask the Copilot: *"explain Slide 3."*

The reply should include the three mandatory sections plus an **Adjacent Opportunities** section. Verify:

- The euro sign renders as `€`, not `\u20ac`
- Monetary amounts are bolded in the "Key Mechanics & Deal Metrics" section

## Related Commits

| Commit | Content |
|---|---|
| `1a04960` | Flavor 2 feature — LLM family + adjacent opportunities, Slide 3 rework, Copilot additions |
| `f76bdc0` | Flavor 1 HEAD — the branch point |
| `f9f8eeb`, `13721ca`, `9cfeb42` | Common commits from the 18–20 Sep session |

---

*End of document.*