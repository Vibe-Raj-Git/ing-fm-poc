# Architecture Decision — Hybrid (LLM + Code) vs. LLM-Only Discovery

**Status:** Decided — Hybrid
**Date:** 14 September 2026
**Audience:** Engineering leadership, product stakeholders, model risk

---

## 1. Context

A design question was raised: should the platform discover opportunities entirely through the
LLM, using signals, the ING service catalog, and contextual data as inputs? Or should it
continue with the current hybrid model, where an LLM handles extraction and synthesis while
deterministic code governs storage, ranking, and drift prevention?

The recommendation is to keep the hybrid model. This document records why.

---

## 2. The Two Architectures

### 2.1 LLM-only discovery

```
Signals + ING Service Catalog + Client context
                    │
                    ▼
        ┌───────────────────────┐
        │   LLM (Gemini)        │
        │                       │
        │ • Reads signals       │
        │ • Maps to catalog     │
        │ • Scores priority     │
        │ • Produces narrative  │
        └───────────────────────┘
                    │
                    ▼
             Opportunity record
```

The LLM is the entire discovery engine. Any structured data it needs is passed in the
prompt. Ranking, sizing, and narrative are all LLM outputs.

### 2.2 Hybrid (current)

```
Signals
    │
    ▼
┌───────────────────────┐
│  LLM (Stage 1)        │   ← Semantic extraction only
│  • Multi-signal       │
│    extraction         │
└───────────────────────┘
    │
    ▼
┌───────────────────────┐
│  DB Persistence       │   ← Deterministic writes, dedup
└───────────────────────┘
    │
    ▼
┌───────────────────────┐
│  LLM (Stage 2)        │   ← Narrative synthesis, anchored
│  • Anchored synthesis │
│  • Drift guard        │
└───────────────────────┘
    │
    ▼
┌───────────────────────┐
│  Code Governance      │   ← Deterministic checks
│  • Whitelist          │
│  • TTL cache          │
│  • Score thresholds   │
│  • Product templates  │
└───────────────────────┘
    │
    ▼
Opportunity record + pitchbook
```

The LLM is one component in a pipeline that also includes deterministic code.

---

## 3. Where Each Approach Excels

### 3.1 LLM strengths

- **Semantic extraction:** reads unstructured text and identifies relevant signals.
- **Cross-domain reasoning:** maps a signal to a candidate service without a rigid rule.
- **Narrative synthesis:** drafts a client-appropriate `why_now` and `action`.
- **Contextual awareness:** adapts language to the deal type (FX vs. Green vs. Rates).

These are all places where the current hybrid model uses the LLM heavily.

### 3.2 Code strengths

- **Arithmetic:** debt schedules, spread calculations, fee pools.
- **Deterministic ranking:** the same inputs produce the same outputs every time.
- **Constraint enforcement:** whitelist, drift guard, TTL cache.
- **Auditability:** every display value traces to a specific query.

These are all places where the current hybrid model uses deterministic code.

---

## 4. The Case Against LLM-Only Discovery

Four specific failure modes make LLM-only discovery inappropriate for wholesale banking.

### 4.1 Arithmetic and sizing

LLMs are probabilistic text generators. They handle decimal arithmetic unreliably. When asked
to size a deal, they produce values that look plausible but don't respect market convention
(benchmark tranches are €500M, €750M, €1.0B — not €437M or €1.23B).

**Observed in testing:** mandate synthesis without an anchor drifted to "€600m 8Y Green +
€400m 12Y SLB" while the curated mandate specified "€600m 7Y Green + €400m 10Y SLB". The
sizing matched convention; the tenors did not. A CFO reviewing the deck would notice.

### 4.2 Reproducibility

An LLM returns different outputs across runs for the same input. With temperature > 0, the
same signals can rank differently on successive requests. This breaks cohort consistency: an
RM and a coverage head refreshing the dashboard a minute apart would see different orderings.

The hybrid model reduces this: the priority score is recomputed only on synthesis runs
(cache misses), then cached for 5 minutes and written to a traceable column. Within a cache
window, every viewer is served the same score. Across windows, the score can drift — observed
values for CLI101 across a single session were 85, 88, 91, 93, 94 — because the underlying
LLM is non-deterministic even at temperature=0.0.

The audit trail is deterministic; the value is not. This is the correct trade-off for a demo.
If reproducibility is required, pin priority_score to the anchor's curated value, the same
treatment the narratives receive. That would make both the score and the ranking fully
deterministic, at the cost of not refreshing the score against new signals.

### 4.3 Auditability

**Question:** "Why is Enel ranked #1 with a score of 94?"

**LLM-only answer:** "Because the model decided so."

**Hybrid answer:** "Because `ca_opportunity_scoring.priority_score = 94`, written by the
synthesis run that produced this display, and exceeding the `≥85 = High` threshold. The
synthesis prompt returns priority_score as one of five keys; the value is persisted with
the write-back to ca_opportunity_scoring."

The hybrid answer cites a specific column, a specific value, and a specific rule — the audit
standard that internal audit and model risk management expect. Note: the value is not static.
Synthesis reruns on cache misses (TTL 300s), and the LLM is non-deterministic even at
temperature=0.0. An audit that revisits the row an hour later may see a different score.
The audit trail is the write-back history, not a fixed number.

The point of the hybrid model is not that the value never changes — it's that any value has a
traceable source and a deterministic rule applied to it. That's the difference from LLM-only,
where the answer is "the model decided."

### 4.4 Constraint awareness

An LLM prompted with signals and a catalog lacks awareness of:
- The client's existing credit facility headroom
- KYC / ISDA status
- Existing derivative positions
- Regulatory constraints on product suitability

Recommending a product the client is not eligible for, or that exceeds their credit capacity,
is a commercial and compliance failure. Deterministic pre-checks in code prevent this. The
LLM prompt alone cannot.

**The family classifier is a second, subtler case of the same principle.** A narrative
that mentions "greenium" and "green tranche" alongside "EMTN" and "IRS pre-hedge" gives a
naive keyword classifier two conflicting signals — is the deal Green/ESG or DCM/Rates? The
LLM reads the full narrative and proposes a family; the weighted vocabulary
(`_FAMILY_KEYWORD_WEIGHTS`) enforces the taxonomy hierarchy — what's the *product*, not
what's the *feature* or *purpose*. Without the deterministic validation, the LLM's proposal
could vary run to run; with it, the demo client's classification is deterministic while
other clients still benefit from the LLM's reasoning. This is the hybrid pattern applied to
classification.

---

## 5. The Current Hybrid Realization

The current architecture implements the hybrid model as follows:

| Layer | LLM responsibility | Code responsibility |
|---|---|---|
| Ingestion | Extract `detected_signals[]` from source text | Persist signals, dedup by `(client_id, trigger_summary)` |
| Scoring | Return `priority_score` from synthesis with a weighted rubric (signal strength 40% / balance-sheet pressure 30% / market window 30%) | Threshold classification (`≥85 → High`), write-back to `ca_opportunity_scoring`, cache populated only after commit |
| Family classification | Propose the product family (`family` synthesis key: `FX_HEDGE` / `GREEN_ESG` / `RATES_HEDGE` / `DCM_REFI`) based on the anchor's primary product | Validate the proposal against the weighted anchor score (`_FAMILY_KEYWORD_WEIGHTS`); decisive override at score ≥ 5 and margin ≥ 3; narrative keyword fallback |
| Adjacent opportunities | Write the 80–140 word cross-sell paragraph grounded in the signal corpus | Enforce the prompt rules (no invention, no repetition of the primary, max 3 angles); render the paragraph on Slide 3; expose it to the Copilot |
| Synthesis | Produce `why_now` and `action`, anchored to the DB row | Drift guard, TTL cache, whitelist scoping, DB write-back |
| Pitchbook | None | Template rendering, product-family branching (using the validated family), 1:1 PPTX parity |
| Copilot | Natural-language reasoning over hydrated slides | Prompt structure, JSON contract, state mutation reducer; conditional fourth response section (Adjacent Opportunities) |
| Compliance | Full-deck audit against MiFID II / MAR / EuGB | Alias endpoints, remediation path |

Each row splits the work between probabilistic (LLM) and deterministic (code) capabilities.

---

## 6. Where The Manager's Intuition Is Correct

The manager's view — that the LLM should drive discovery using signals, catalog, and context
— is directionally right. Two places where it holds:

### 6.1 Discovery creativity

An LLM can propose cross-sell opportunities that a rule engine would miss. Reading a
client's earnings release and connecting it to a specific DCM product requires semantic
reasoning, not pattern matching.

The current pipeline captures this: the LLM extracts signals from unstructured text, and the
synthesis step reasons over the accumulated signal corpus.

### 6.2 Service catalog mapping

Given the ING catalog (Green EMTN, Pre-Hedge IRS, FX Collar, etc.), the LLM can map a
signal to the appropriate product more flexibly than a fixed rule set.

The current pipeline captures this partially: the prompt includes product-family context,
and the synthesis selects language appropriate to the family. Full catalog-driven selection
is a future enhancement.

---

## 7. Where The Manager's Intuition Needs Guardrails

Extending LLM-driven discovery to all 13 clients (not just the whitelisted one) is the right
direction, but requires deterministic validation alongside it.

### 7.1 Proposed extension — LLM discovery with code validation

```
For each client:
    ├── LLM reads signals + client data + catalog
    ├── LLM proposes N candidate opportunities
    └── For each candidate:
            ├── Code checks: is the client eligible?
            ├── Code checks: is the sizing within convention?
            ├── Code checks: does the product match a catalog entry?
            ├── Code checks: does it violate any credit/KYC constraint?
            └── If validated: add to the ranked list
```

This pattern preserves the LLM's creative discovery while enforcing constraints in code.

### 7.2 What this would require

- A `ca.catalog_products` table (or similar) listing ING services with their eligibility rules
- A validation function that checks each candidate against the client's constraints
- A ranking step that combines LLM confidence with code-validated eligibility

None of these are in scope for the demo, but the architecture is designed to accept them.

---

## 8. Decision

**The hybrid model is retained.**

For a wholesale banking platform, the LLM's role is **creative synthesizer**: reading
unstructured content, extracting signals, drafting narratives, and explaining context.

Deterministic code's role is **financial governor**: computing scores, enforcing whitelists,
caching synthesis, guarding against drift, and rendering pitchbooks.

Neither works alone:
- LLM-only has no audit trail and no arithmetic precision
- Code-only cannot parse unstructured text or draft client-appropriate narratives

The current pipeline splits responsibilities accordingly, and the platform's behavior is
traceable to a specific row in a specific table for every displayed value.

---

## 9. Post-Demo Backlog Related To This Decision

1. **Replace the structured LLM estimate with a real formula.** The current `priority_score`
is produced by an LLM with an explicit weighted rubric (signal strength 40% / balance-sheet
pressure 30% / market window 30%). This is an improvement over the prior unfixed estimate,
but the value is still non-deterministic across runs. A fully deterministic formula —
computed in code over the accumulated signal corpus plus balance-sheet data — would
satisfy model risk requirements and make the score reproducible. Requires deciding the
formula.

2. **Extend anchored synthesis to all clients.** Move from a whitelist to per-client anchors
   in `ca_opportunity_scoring`. Then every client gets coherent, anchored synthesis.

3. **Add a validation layer** for LLM-proposed opportunities. Before adding a candidate
   opportunity to the display, check it against client eligibility and credit constraints.

4. **Normalise the `signal_type` enum at ingestion.** Currently free text. A canonical set
   would allow catalog-driven mapping rather than keyword matching.

4a. **Refine `_FAMILY_KEYWORD_WEIGHTS` statistically.** The weights are currently hand-curated
    from the ING product taxonomy. As the platform accumulates classified anchors, the
    weights could be learned or tuned against observed outcomes — an evidence-based version
    of the current expert system. Backlog, not blocking.

5. **Persist the synthesis cache in a shared store.** Currently in-memory, which requires
   `max-instances=1`. Moving to Redis or a DB-backed cache allows horizontal scaling.

*None of these block the current demo. They represent the natural next layer of investment.*

---

## 10. Changelog — 20 Sep 2026

Corrections to the reasoning in light of the 19-20 Sep session. The decision (§8) is
unchanged — hybrid over LLM-only.

### §4.2 Reproducibility

- The prior text claimed "the priority score is fixed in the DB" and "the ranking is
  deterministic." Both were inaccurate after commit `13721ca`.
- The score is recomputed on every synthesis run and written back to
  `ca_opportunity_scoring`. It is not fixed.
- Within a cache window (300s), all viewers receive the same score. Across windows, the
  score drifts even at `temperature=0.0`. Observed values for `CLI101` across a single
  session: 85, 88, 91, 93, 94.
- The reproducibility claim is now scoped to the cache window.

### §4.3 Auditability

- The prior example cited "the last ingestion that populated the opportunity row."
- The value is written by the last synthesis run, not ingestion.
- Added a note that the value is not static — the audit trail is the write-back history.

### §5 Current Hybrid Realization

- The Scoring row now reflects that `priority_score` is a synthesis output, not an
  extraction artifact. The rubric is cited. The cache-after-commit invariant is noted.

### §9 Post-Demo Backlog

- Item 1 reframed. The current state is a "structured LLM estimate with a weighted rubric,"
  an intermediate between the prior unfixed estimate and a fully deterministic formula.

### Flavor 2 additions (20 Sep 2026, commit `1a04960`)

The two new features reinforce the hybrid decision with two more instances of the same
pattern — LLM proposes, code validates:

- **Product family classification.** The LLM proposes a family as a synthesis key. The
  weighted vocabulary `_FAMILY_KEYWORD_WEIGHTS` validates the proposal against the anchor.
  Decisive override at score ≥ 5 and margin ≥ 3; otherwise the LLM is trusted. This is the
  hybrid pattern applied to a classification task — the LLM's semantic reasoning plus the
  code's deterministic taxonomy.
- **Adjacent opportunities.** The LLM writes the cross-sell paragraph. The prompt enforces
  the grounding rules — each adjacency must cite a specific signal, no repetition of the
  primary, no marketing language. Code renders the paragraph on Slide 3 and exposes it to
  the Copilot. The LLM produces prose; the constraints around it are deterministic.

Neither changes the decision (§8). Both strengthen the case for hybrid: the LLM is trusted
for the parts it's good at (semantic reasoning, narrative drafting), and code governs the
parts it's good at (taxonomy enforcement, drift prevention, cross-consistency).

### Related session work

- `1a04960` — Flavor 2 feature: product family classification + adjacent opportunities +
  Slide 3 rework + Copilot additions.
- `13721ca` — LLM-computed priority_score with weighted rubric + whitelist guarantee.
- `9cfeb42` — cache populated only after successful DB persist.
- `f9f8eeb` — display consistency fixes across card, preview, generated deck, and Copilot.
- `master_persona_20Sep.md` §7.8, §7.9, §8.1, §13 — full detail on the cache/DB invariant,
  the credit rating dict, and the session changelog.
- `Docs/WeightedFamily/master_persona_20Sep_WeightedFamily.md` §2.1, §7.11, §8.7, §13 —
  Flavor 2 documentation including the family weights sync invariant and the taxonomy as a
  curated expert system.

---

*End of document.*