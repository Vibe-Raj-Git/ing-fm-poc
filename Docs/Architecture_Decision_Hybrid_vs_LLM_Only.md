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

The hybrid model avoids this: the priority score is fixed in the DB, the mandate narrative
is cached for 5 minutes, and the ranking is deterministic.

### 4.3 Auditability

**Question:** "Why is Enel ranked #1 with a score of 94?"

**LLM-only answer:** "Because the model decided so."

**Hybrid answer:** "Because `ca_opportunity_scoring.priority_score = 94`, which exceeds the
`≥85 = High` threshold. The value was written during the last ingestion that populated the
opportunity row."

The hybrid answer is auditable. It cites a specific column, a specific value, and a specific
rule. That's the standard that internal audit and model risk management expect.

### 4.4 Constraint awareness

An LLM prompted with signals and a catalog lacks awareness of:
- The client's existing credit facility headroom
- KYC / ISDA status
- Existing derivative positions
- Regulatory constraints on product suitability

Recommending a product the client is not eligible for, or that exceeds their credit capacity,
is a commercial and compliance failure. Deterministic pre-checks in code prevent this. The
LLM prompt alone cannot.

---

## 5. The Current Hybrid Realization

The current architecture implements the hybrid model as follows:

| Layer | LLM responsibility | Code responsibility |
|---|---|---|
| Ingestion | Extract `detected_signals[]` from source text | Persist signals, dedup by `(client_id, trigger_summary)` |
| Scoring | Provide a priority estimate during extraction (legacy path) | Threshold classification (`≥85 → High`) |
| Synthesis | Produce `why_now` and `action`, anchored to the DB row | Drift guard, TTL cache, whitelist scoping, DB write-back |
| Pitchbook | None | Template rendering, product-family branching, 1:1 PPTX parity |
| Copilot | Natural-language reasoning over hydrated slides | Prompt structure, JSON contract, state mutation reducer |
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

1. **Introduce a real priority formula.** Replace the LLM-estimated `priority_score` with
   a computation over the accumulated signal corpus plus balance-sheet data. This would make
   the score auditable and reproducible, satisfying model risk requirements.

2. **Extend anchored synthesis to all clients.** Move from a whitelist to per-client anchors
   in `ca_opportunity_scoring`. Then every client gets coherent, anchored synthesis.

3. **Add a validation layer** for LLM-proposed opportunities. Before adding a candidate
   opportunity to the display, check it against client eligibility and credit constraints.

4. **Normalise the `signal_type` enum at ingestion.** Currently free text. A canonical set
   would allow catalog-driven mapping rather than keyword matching.

5. **Persist the synthesis cache in a shared store.** Currently in-memory, which requires
   `max-instances=1`. Moving to Redis or a DB-backed cache allows horizontal scaling.

None of these block the current demo. They represent the natural next layer of investment.

---

*End of document.*