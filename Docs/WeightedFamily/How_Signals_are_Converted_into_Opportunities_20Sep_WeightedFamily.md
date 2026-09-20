# How Signals Are Converted into Opportunities

**Version:** 20 September 2026 — Weighted-Family + Adjacencies
**Flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Parallel flavor:** Baseline (Flavor 1) at `Docs/How_Signals_are_Converted_into_Opportunities.md`
**Branch:** `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3`
**Audience:** Engineers, Business Analysts

---

## 1. Overview

The platform converts unstructured content (emails, Teams messages, RSS news, PDF houseviews) into structured signals, then into an actionable opportunity narrative for the Relationship Manager.

This is a **hybrid pipeline**: an LLM does semantic extraction and narrative synthesis, and deterministic code governs storage, ranking, caching, and drift prevention. Neither stage works without the other.

---

## 2. The Pipeline — End to End
┌──────────────────────────────────────────────────────────────────────────────┐
│ SOURCE │
│ • PDF / PPTX upload • RSS news • Treasury email │
│ • Microsoft Teams • WorkFabric memo │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1 — MULTI-SIGNAL EXTRACTION (LLM) │
│ │
│ Endpoint: POST /api/ingest/text or POST /api/ingest/file │
│ Model: gemini-2.5-flash │
│ │
│ The LLM receives the raw text and returns a JSON object with a │
│ "detected_signals" array. Each element has: │
│ │
│ • signal_type (e.g. "Debt Refinancing Requirements") │
│ • catalog_family (e.g. "Financing/Capital Markets") │
│ • metric_identified (short label) │
│ • trigger_summary (1-sentence description) │
│ • metric_value (key value or spread) │
│ • description (2-sentence detail) │
│ • confidence_pct (integer) │
│ • urgency ("High" / "Medium" / "Low") │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2 — PERSISTENCE │
│ │
│ • INSERT INTO ca.document_vector_chunks │
│ One row per ingestion. Raw text, source metadata, structured_metadata │
│ JSONB with the full detected_signals array. │
│ │
│ • INSERT INTO ca.digital_twin_signals │
│ One row per detected signal (N rows for N signals). │
│ Two-layer dedup guard: │
│ Layer 1 — signal-level on (client_id, trigger_summary) │
│ Layer 2 — channel-scoped semantic on text content │
│ │
│ Ingestion does NOT write to ca.ca_opportunity_scoring. │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3 — SYNTHESIS (LLM, TRIGGERED ON READ) │
│ │
│ Endpoint: GET /api/opportunities │
│ │
│ For clients in _DEMO_CLIENT_IDS only: │
│ 1. Read anchor from ca.ca_opportunity_scoring │
│ (why_now_nlg + next_best_action) │
│ 2. Check in-memory TTL cache keyed by client_id │
│ 3. On cache miss: │
│ a. Fetch the 20 most recent signals for the client │
│ b. Call synthesize_mandate_catalyst() with the anchor first │
│ c. Receive JSON with seven keys:                                       │
│      {"why_now", "action", "why_now_summary", "action_summary",          │
│      "priority_score", "family", "adjacent_opportunities"}              │
│ d. Drift guard: replace with anchor verbatim on tenor conflict         │
│ e. UPDATE ca.ca_opportunity_scoring.priority_score                     │
│ f. Populate the cache ONLY after the DB commit succeeds                │
└──────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4 — READ │
│ │
│ • Opportunity card renders why_now + action + client data + market data │
│ • Pitchbook preview and PPTX read the same values │
│ • Copilot reads the same values │
│ • All consumers see the same narrative │
└──────────────────────────────────────────────────────────────────────────────┘

text

---

## 3. Stage 1 — Multi-Signal Extraction

**File:** `main.py`
**Function:** `ingest_text_signal`

The LLM is asked to extract **all distinct signals** from the source text, not just one. A treasury email that mentions (a) an upcoming maturity, (b) a board authorization, and (c) an FX exposure produces three signal rows.

**Why multi-signal:** prior to 14 Sep 2026, ingestion produced a single signal per source. That under-represented multi-topic documents.

**Example — Enel houseview PDF:**

The uploaded `ENEL_Capital_Markets_Filing_2026_Test.pdf` contains 6 sections. The LLM returns 6 signals, written as 6 rows:

| # | signal_type | metric_identified |
|---|---|---|
| 0 | Debt Refinancing Requirements | €10.13bn debt maturing; 'late 2026 and 2027' |
| 1 | Funding Capacity Authorisation | €12.0bn; 'March 2027' |
| 2 | Interest Rate Risk Exposure & Pre-hedging Opportunity | Legacy coupon ~1.20%; Indicative refinancing yields 4.5%-5.0% |
| 3 | Foreign Exchange Exposure Review | USD-linked procurement; USD vs EUR exchange rate risk |
| 4 | Commodity Price Volatility Impact | N/A |
| 5 | Cross-Asset Risk Coordination Assessment | N/A |

---

## 4. Stage 2 — Persistence & Deduplication

Ingestion applies a **two-layer dedup guard:**

**Layer 1 — Signal dedup on `(client_id, trigger_summary)`.** If a signal with the same trigger summary already exists, the insert is skipped.

**Layer 2 — Channel-scoped semantic dedup on text content.** Before inserting a chunk, the pipeline checks for existing chunks in the same `source_channel` with similar text content. If a semantic match is found, the write is suppressed and the existing `chunk_id` is returned.

Verified behavior: an identical ingestion submitted twice returns `{"status": "duplicate_skipped", ...}` on the second call.

---

## 5. Stage 3 — Synthesis on Read

**File:** `main.py`
**Function:** `get_opportunities` (the `/api/opportunities` handler)

Synthesis does not run during ingestion. It runs when the frontend requests the opportunity list.

### 5.1 Read the anchor

For each client, the query reads:

- `ca.ca_opportunity_scoring.why_now_nlg` — the curated catalyst rationale
- `ca.ca_opportunity_scoring.next_best_action` — the curated mandate action

These two fields together are **the anchor**.

**Why the anchor exists:** the signals describe evidence and context, but they don't contain a specific deal structure. Left to synthesize freely, the LLM will invent a plausible structure that may not match ING's actual advisory proposal.

**Example of drift the anchor prevents:** during the 14 Sep session, synthesis without an anchor drifted to "€600m 8Y Green + €400m 12Y SLB" while the curated mandate said "€600m 7Y Green + €400m 10Y SLB."

### 5.2 Check the TTL cache

`_MANDATE_SYNTH_CACHE` is a module-level dictionary:

```python
_MANDATE_SYNTH_CACHE = {}
_MANDATE_SYNTH_CACHE_TTL = 300  # seconds
Cache key is `client_id`. Entry value is an **8-tuple**: `(expiry_epoch, why_now, action, why_now_summary, action_summary, priority_score, family, adjacent_opportunities)`. Cache hit returns the stored values without an LLM call.

Cache/DB consistency invariant (18 Sep, commit 9cfeb42): the cache is populated only after conn.commit() succeeds. On persist failure, the entry is popped. This prevents the failure mode where the UI served a cached value the DB did not hold.

Deployment dependency: because the cache is in-memory, the service must run with max-instances=1.

5.3 Synthesize (only if client is whitelisted)
The whitelist:

python
_DEMO_CLIENT_IDS = {"CLI101", "CLI103"}
Clients not in this set skip the LLM call entirely and use the DB row's why_now_nlg and next_best_action values as-is.

For whitelisted clients on cache miss, synthesize_mandate_catalyst() runs:

Fetch the 20 most recent signals for the client

Build a prompt with:

Client name, product family

The anchor (why_now_nlg + next_best_action) placed first, labeled as authoritative

Grounded input signals (balance sheet, market data, context, news)

Accumulated signals

   - Instructions to return **seven keys**: `why_now`, `action`, `why_now_summary`, `action_summary`, `priority_score`, `family`, `adjacent_opportunities`

Call gemini-2.5-flash at temperature=0.0

Parse the JSON response

5.4 Drift guard
After the LLM returns, a deterministic check runs:

python
if "7Y" in anchor and "8Y" in output:
    output = anchor
if "10Y" in anchor and "12Y" in output:
    output = anchor
This is a safety net. The prompt asks the LLM to preserve the anchor's structure. If it doesn't, the guard catches the tenor conflict and substitutes the anchor.

5.5 Persist
The anchor narratives are protected. Fresh synthesis writes back only priority_score:

python
UPDATE ca.ca_opportunity_scoring
SET priority_score = %s
WHERE client_id = %s
What is not written: why_now_nlg and next_best_action are curated fields and are not overwritten by the LLM. The prompt treats them as fixed inputs; the write-back intentionally excludes them. Rationale: if synthesis rewrote the anchor on every cache miss, the prompt would drift on each run — and temperature=0.0 could not guarantee a stable score, because the input would not be stable.

The priority_score write-back happens inside a try block; the cache entry is populated only after conn.commit() succeeds. On persist failure, the cache entry is popped.

### 5.6 Product family classification

The synthesis LLM returns `family` as one of the seven keys — `FX_HEDGE`, `GREEN_ESG`, `RATES_HEDGE`, or `DCM_REFI`. The prompt instructs the LLM to base the classification on the anchor's `next_best_action`, choose the dominant product (not purpose or feature), and apply a notional tiebreaker.

**Validation.** `detect_product_family(ctx)` in `pitchbook_builder.py` validates the LLM's proposal against a weighted anchor score:

1. Score `why_now_nlg + " " + next_best_action` against `_FAMILY_KEYWORD_WEIGHTS` — strong product signals weight 5 (`green bond`, `slb`, `emtn`, `irs pre-hedge`, `fx collar`); weak context words weight 1–2 (`refinancing`, `maturity wall`, `dual-tranche`, `senior unsecured`).
2. If the top family's weighted score is **≥ 5 with a margin ≥ 3** over the runner-up → the weights **override** the LLM. Deterministic.
3. Otherwise → trust the LLM's proposal.
4. If both are silent → narrative keyword fallback.

**Observed:**

| Client | Anchor score | Margin | Outcome |
|---|---|---|---|
| Enel (`CLI101`) | 15 GREEN_ESG vs 5 DCM_REFI | 10 | Decisive — guaranteed `GREEN_ESG` |
| BASF (`CLI103`) | 8 DCM_REFI vs 5 RATES_HEDGE | 3 | At threshold — LLM decides |

The `family` value is not persisted to the DB — no column exists on `ca.ca_opportunity_scoring`. It travels via the 8-tuple cache, the `/api/opportunities` response as `family`, and the pitchbook bundle. See `Data_or_Fabrication_20Sep_WeightedFamily.md` §6.8.

### 5.7 Adjacent opportunities

The synthesis LLM returns `adjacent_opportunities` as the seventh key — an 80–140 word business-English paragraph identifying up to 3 grounded cross-sell angles beyond the primary mandate.

**Prompt rules:**

- Each adjacency must cite a specific signal from the corpus.
- No invention — empty string if no adjacencies are supported.
- No repetition of the primary mandate.
- Maximum 3 adjacencies, prioritised by notional or urgency.
- No marketing language.

**Lifecycle:**

1. Produced by synthesis on a cache miss; stored at element 7 of the cache tuple.
2. Exposed in `/api/opportunities` as `adjacent_opportunities`.
3. Rendered on Slide 3 as the third card.
4. Included in the Copilot `slide_3` payload.
5. Read by `handle_pitchbook_generation` from `_MANDATE_SYNTH_CACHE[cid][7]` and set on the pitchbook bundle before `build_pitchbook`.

**Non-determinism.** Like `priority_score`, the paragraph varies across runs. Multiple grounded variants have been observed for Enel, all citing rate, FX, and DCM angles in different phrasings. See `Data_or_Fabrication_20Sep_WeightedFamily.md` §6.9.

6. The Three Scores on ca.ca_opportunity_scoring
Column	Type	Current use
priority_score	integer	Displayed on the card as <Label> · <Score> (e.g., High · 94)
propensity_score	integer	Read by pitchbook_builder.py as an ORDER BY tiebreaker when a client has multiple scoring rows. Not displayed.
value_score	integer	Not read by any code path
6.1 What priority_score actually is
priority_score is an LLM-derived estimate, produced during synthesis (not ingestion). Since commit 13721ca (18 Sep 2026), the synthesis prompt returns priority_score as one of five keys, computed against an explicit weighted rubric:

Signal strength — 40%

Balance-sheet pressure — 30%

Market window — 30%

The value is written back to ca.ca_opportunity_scoring.priority_score on every cache miss for whitelisted clients.

Non-determinism. Even at temperature=0.0, gemini-2.5-flash produces slightly different scores across synthesis runs. Observed values for CLI101 across a single session:

Run	Score
1	85
2	88
3	91
4	93
5	94
This is a property of the model, not a bug. If a stable score is required for a demo, pin priority_score to the anchor's curated value — the same treatment the narratives receive.

6.2 Threshold classification
The card label is derived from the effective score by a fixed rule in /api/opportunities:

python
_effective_score = int(final_priority_score) if final_priority_score is not None else int(score_num)
score_level = "High" if _effective_score >= 85 else ("Medium" if _effective_score >= 70 else "Low")
score_val = f"{score_level} · {_effective_score}"
Score range	Label
≥ 85	High
70 – 84	Medium
< 70	Low
_effective_score prefers the fresh synthesis value when present; falls back to the DB value on cache hit or non-whitelisted client.

6.3 No composite formula
There is no weighted combination of the three scores in the code. Earlier documentation described a 0.35 × propensity + 0.25 × value + ... formula. It was aspirational, never implemented.

6.4 What the score is NOT
Not a compliance or risk score

Not a formula over code-level fields

Not static — refreshes on every synthesis cache miss

7. Worked Example — Enel S.p.A. (CLI101)
Values below reflect the current DB state.

7.1 Ingestion
A PDF (ENEL_Capital_Markets_Filing_2026_Test.pdf) was uploaded. The LLM extracted 6 signals, all written to ca.digital_twin_signals under client_id = 'CLI101'.

7.2 Accumulated signals
Enel's signal corpus spans multiple ingestion channels: PDF houseviews, treasury emails, Teams exchanges, RSS news, WorkFabric memos. Example signals:

signal_id	signal_type	trigger_summary
SIG-3B377DD4	SUSTAINABLE FUNDING	Enel is entering a treasury planning window requiring a comprehensive review of funding, rates, sustainable finance readiness...
SIG-069AF8DA	SUSTAINABLE FUNDING	CaixaBank CIB acted as Joint Active Bookrunner for Enel's €2.5 billion dual-tranche senior bond issuance.
SIG-68A1FD24	SUSTAINABLE FUNDING	Enel faces a €10.13bn debt maturity wall in 2026-2027 with significantly higher refinancing costs...
The current count is ~46 signals. It drifts with every ingestion.

7.3 The anchor
ca.ca_opportunity_scoring for CLI101 has:

why_now_nlg: "Enel faces a critical €10.13bn debt maturity wall in 2026-2027, necessitating proactive refinancing despite its robust €14.2bn liquidity buffer..."

next_best_action: "We propose a €1.0bn dual-tranche senior unsecured issuance, strategically leveraging Enel's €3.5bn green asset pool through a €600m 7Y Green bond priced at Mid-swap + 73 bps (net of -5 bps greenium), complemented by a €400m 10Y Sustainability-Linked Bond..."

7.4 Synthesis
Since CLI101 is in _DEMO_CLIENT_IDS:

1. Anchor is read from the DB row
2. Cache is checked (miss on cold start)
3. Signal corpus is fetched (20 most recent)
4. Gemini is called with the anchor at the top of the prompt
5. Response includes why_now, action, why_now_summary, action_summary, priority_score, family, adjacent_opportunities
6. Drift guard runs (no conflict for Enel — the LLM respected the anchor)
7. priority_score is written back to the DB; family and adjacent_opportunities are not persisted
8. The cache is populated after commit

7.5 Read
The opportunity card displays:

Coverage RM: Marco Bianchi (from ca.coverage_teams)

External ratings: S&P | BBB | Positive (from _CREDIT_RATINGS)

Net Debt: €58.5bn

Available Liquidity: €14.2bn

Maturities within 24 months: €10.13bn

- **Match confidence:** High · 91–94 (from _effective_score)
- **Catalyst Rationale (Why Now):** the synthesized narrative
- **Proposed Execution & Structuring:** the synthesized narrative
- **Family:** GREEN_ESG (drives the deck template)
- **Adjacent Opportunities:** the grounded cross-sell paragraph (rendered on Slide 3)

All values sourced from the DB or from LLM extraction grounded in DB content.

8. What Happens for a Non-Whitelisted Client
If a client is not in _DEMO_CLIENT_IDS:

Ingestion works the same — signals are written to ca.digital_twin_signals with dedup

Signals appear in /api/signals only if the client is in the whitelist

In /api/opportunities, the client's row is processed but the synthesis block is skipped

The card displays why_now_nlg and next_best_action from the DB row directly

No LLM call is made

This is intentional — see Architecture_Decision_Hybrid_vs_LLM_Only.md.

9. Summary
LLM extracts N signals per ingestion

Code persists signals with two-layer dedup, and stores the full chunk with metadata

Synthesis (on read) uses the accumulated signals, anchored to the curated DB row

Drift guard prevents the LLM from changing the mandate structure

TTL cache (5 minutes) eliminates repeat synthesis calls; populated only after DB commit

Whitelist scopes synthesis to demo clients

Every value displayed traces to a database row or to an LLM output grounded in DB content.

10. Cross-References
Document	Relevant sections
master_persona_20Sep.md	§4 Component Map, §6 Pipeline Behavior, §7 Data Integrity
architecture_flow_20Sep.md	§3 Ingestion, §5 Mandate Synthesis
Data_or_Fabrication.md	§2 Data Flow, §6 Priority Score, §7 Fallbacks
Explain_Left_Client_Section.md	The client card that renders the output

End of document.