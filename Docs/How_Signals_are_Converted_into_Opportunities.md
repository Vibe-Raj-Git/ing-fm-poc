# How Signals Are Converted into Opportunities

**Version:** 14 September 2026
**Status:** Authoritative
**Supersedes:** Previous version dated pre-14 Sep 2026
**Audience:** Engineers, Business Analysts

---

## 1. Overview

The platform converts unstructured content (emails, Teams messages, RSS news, PDF
houseviews) into structured signals, then into an actionable opportunity narrative for the
Relationship Manager.

This is a **hybrid pipeline**: an LLM does semantic extraction and narrative synthesis, and
deterministic code governs storage, ranking, caching, and drift prevention. Neither stage
works without the other.

---

## 2. The Pipeline — End to End

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  SOURCE                                                                      │
│  • PDF / PPTX upload                                                         │
│  • RSS news                                                                  │
│  • Treasury email                                                            │
│  • Microsoft Teams chat                                                      │
│  • WorkFabric memo                                                           │
└──────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 1 — MULTI-SIGNAL EXTRACTION (LLM)                                     │
│                                                                              │
│  Endpoint: POST /api/ingest/text  or  POST /api/ingest/file                  │
│  Model: gemini-2.5-flash                                                     │
│                                                                              │
│  The LLM receives the raw text and returns a JSON object with a              │
│  "detected_signals" array. Each element has:                                 │
│                                                                              │
│    • signal_type       (e.g. "Debt Refinancing Requirements")                │
│    • catalog_family    (e.g. "Financing/Capital Markets")                    │
│    • metric_identified (short label, max 100 chars)                          │
│    • trigger_summary   (1-sentence description)                              │
│    • metric_value      (key value or spread)                                 │
│    • description       (2-sentence detail)                                   │
│    • confidence_pct    (integer)                                             │
│    • urgency           ("High" / "Medium" / "Low")                           │
└──────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 2 — PERSISTENCE                                                       │
│                                                                              │
│  • INSERT INTO ca.document_vector_chunks                                     │
│      One row per ingestion. Contains the raw text, source metadata, and a    │
│      structured_metadata JSONB with the full detected_signals array.         │
│                                                                              │
│  • INSERT INTO ca.digital_twin_signals                                       │
│      One row per detected signal (N rows for N signals).                     │
│      Dedup guard: skip if (client_id, trigger_summary) already exists.       │
│                                                                              │
│  Ingestion does NOT write to ca.ca_opportunity_scoring.                      │
└──────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 3 — SYNTHESIS (LLM, TRIGGERED ON READ)                                │
│                                                                              │
│  Endpoint: GET /api/opportunities                                            │
│                                                                              │
│  For clients in _DEMO_CLIENT_IDS only:                                       │
│    1. Read anchor from ca.ca_opportunity_scoring                             │
│       (why_now_nlg + next_best_action)                                       │
│    2. Check in-memory TTL cache keyed by client_id                           │
│    3. On cache miss:                                                         │
│       a. Fetch the 20 most recent signals for the client                     │
│       b. Call synthesize_mandate_catalyst() with the anchor first            │
│       c. Receive JSON {"why_now": "...", "action": "..."}                    │
│       d. Drift guard: replace with anchor verbatim if tenors conflict        │
│       e. Write to cache and back to ca.ca_opportunity_scoring                │
└──────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 4 — READ                                                              │
│                                                                              │
│  • Opportunity card renders why_now + action + client data + market data     │
│  • Pitchbook preview and PPTX read the same values                           │
│  • Copilot reads the same values                                             │
│  • All consumers see the same narrative                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Stage 1 — Multi-Signal Extraction

**File:** `main.py`
**Function:** `ingest_text_signal`

**What happens:**

The LLM is asked to extract **all distinct signals** from the source text, not just one.
A treasury email that mentions (a) an upcoming maturity, (b) a board authorization, and
(c) an FX exposure produces three signal rows.

**Why multi-signal:**

Prior to 14 Sep 2026, ingestion produced a single signal per source. That under-represented
multi-topic documents. A PDF with six sections produced one row, and whichever section the
LLM chose as the "top" signal dominated downstream.

**Example — Enel houseview PDF:**

The uploaded `ENEL_Capital_Markets_Filing_2026_Test.pdf` contains 6 sections. The LLM returns
a `detected_signals` array with 6 elements, and 6 rows are written to
`ca.digital_twin_signals`:

| # | signal_type | metric_identified |
|---|---|---|
| 0 | Debt Refinancing Requirements | €10.13bn debt maturing; 'late 2026 and 2027' |
| 1 | Funding Capacity Authorisation | €12.0bn; 'March 2027' |
| 2 | Interest Rate Risk Exposure & Pre-hedging Opportunity | Legacy coupon ~1.20%; Indicative refinancing yields 4.5%-5.0% |
| 3 | Foreign Exchange Exposure Review | USD-linked procurement; USD vs EUR exchange rate risk |
| 4 | Commodity Price Volatility Impact | N/A |
| 5 | Cross-Asset Risk Coordination Assessment | N/A |

Each of these is a separate signal that downstream components can reason over.

---

## 4. Stage 2 — Persistence & Deduplication

**Dedup guard:** Before inserting a new signal, the code checks whether
`(client_id, trigger_summary)` already exists. If so, the insert is skipped and the log
records `Skipping duplicate signal for {client_id}`.

This prevents table growth when:
- The same document is uploaded twice
- Overlapping news articles cover the same fact
- The same event is mentioned in an email and a Teams message

---

## 5. Stage 3 — Synthesis on Read

**File:** `main.py`
**Function:** `get_opportunities` (the `/api/opportunities` handler)

Synthesis does not run during ingestion. It runs when the frontend requests the opportunity
list. The flow has four stages.

### 5.1 Read the anchor

For each client, the query reads the current values of:

- `ca.ca_opportunity_scoring.why_now_nlg` — the curated catalyst rationale
- `ca.ca_opportunity_scoring.next_best_action` — the curated mandate action

These two fields together are **the anchor**.

**Why the anchor exists:** the signals in `ca.digital_twin_signals` describe evidence and
context, but they don't contain a specific deal structure. Left to synthesize freely, the
LLM will invent a plausible structure — and it may not match ING's actual advisory proposal.
The anchor constrains the structure.

**Example of drift that the anchor prevents:** during the 14 Sep 2026 session, synthesis
without an anchor drifted to "€600m 8Y Green + €400m 12Y SLB" while the curated mandate said
"€600m 7Y Green + €400m 10Y SLB". The anchor (and drift guard) prevents this.

### 5.2 Check the TTL cache

`_MANDATE_SYNTH_CACHE` is a module-level dictionary:

```python
_MANDATE_SYNTH_CACHE = {}
_MANDATE_SYNTH_CACHE_TTL = 300  # seconds
```

Cache key is `client_id`. Entry value is `(expiry_timestamp, why_now, action)`. Cache hit
returns the stored values without an LLM call. Cache miss falls through to synthesis.

**Why the TTL: 300 seconds:** long enough to eliminate repeated calls during a demo session,
short enough that stale narratives expire quickly.

**Deployment dependency:** because the cache is in-memory, the service must run with
`max-instances=1`. If multiple instances served requests, each would have its own empty
cache and the TTL benefit would be lost.

### 5.3 Synthesize (only if client is whitelisted)

The whitelist:

```python
_DEMO_CLIENT_IDS = {"CLI101"}
```

Clients not in this set skip the LLM call entirely and use the DB row's `why_now_nlg` and
`next_best_action` values as-is.

For whitelisted clients on cache miss, `synthesize_mandate_catalyst()` runs:

1. Fetch the 20 most recent signals for the client
2. Build a prompt with:
   - Client name, product family
   - The anchor (why_now + action) placed **first**, labeled as authoritative
   - Grounded input signals (balance sheet, market data, context, news)
   - Accumulated signals for the client
   - Instructions to produce 2-sentence `why_now` and 2-sentence `action`
3. Call `gemini-2.5-flash`
4. Parse the JSON response

### 5.4 Drift guard

After the LLM returns, a deterministic check runs:

```python
if "7Y" in anchor and "8Y" in output:
    output = anchor   # replace LLM output with anchor
if "10Y" in anchor and "12Y" in output:
    output = anchor
```

This is a safety net. The prompt asks the LLM to preserve the anchor's structure. If it
doesn't, the guard catches the specific conflict class and substitutes the anchor.

### 5.5 Persist

Fresh synthesis is written back to `ca.ca_opportunity_scoring`:

```python
UPDATE ca.ca_opportunity_scoring
SET why_now_nlg = %s, next_best_action = %s
WHERE client_id = %s
```

This keeps the DB row aligned with what the frontend displays, so downstream consumers
(copilot, compliance, pitchbook) that read the DB row see the same values.

---

## 6. The Three Scores on `ca.ca_opportunity_scoring`

The table has three score columns. Only one is currently displayed.

| Column | Type | Current use |
|---|---|---|
| `priority_score` | integer | Displayed on the card as `<Label> · <Score>` (e.g., `High · 94`) |
| `propensity_score` | integer | Retained for future use; not read by any code path |
| `value_score` | integer | Retained for future use; not read by any code path |

### 6.1 What `priority_score` actually is

`priority_score` is a **single LLM-derived estimate**, produced during ingestion. It is not
a formula. It is not recalculated as new signals arrive.

**Current state — worth noting:** the ingestion pipeline was refactored on 14 Sep 2026 to
extract `detected_signals[]` arrays. The new prompt no longer asks Gemini to return a
`priority_score`. That means the score in the DB is now a **legacy value** from the last
time the old single-signal pipeline ran.

For Enel, `priority_score = 94`. It has not changed since the pipeline refactor, and it
will not change until either:
- The score is manually set, or
- A new scoring mechanism is introduced

### 6.2 Threshold classification

The card label is derived from `priority_score` by a fixed rule in `/api/opportunities`:

```python
score_level = "High" if int(score_num) >= 85 else ("Medium" if int(score_num) >= 70 else "Low")
score_val = f"{score_level} · {score_num}"
```

| Score range | Label |
|---|---|
| ≥ 85 | High |
| 70 – 84 | Medium |
| < 70 | Low |

### 6.3 Why the three scores are independent

There is no weighted combination of the three scores. No `0.35 × propensity + 0.25 × value +
...` formula exists in the code.

Earlier documentation described such a formula. It was aspirational, not implemented. A
future refinement could introduce a real composite score — for example, weight the propensity
and value dimensions alongside signal urgency — but that requires both a specification and
implementation.

### 6.4 What the score is NOT

To prevent confusion:

- Not a compliance or risk score
- Not derived from a formula
- Not updated per request
- Not the sum of any weighted dimensions

It is a single LLM output, frozen at its last write.

---

## 7. Worked Example — Enel S.p.A. (`CLI101`)

The following traces the current state of Enel through the pipeline.

### 7.1 Ingestion

A PDF (`ENEL_Capital_Markets_Filing_2026_Test.pdf`) was uploaded on 21 Aug 2026. The LLM
extracted 6 signals, all written to `ca.digital_twin_signals` under `client_id = 'CLI101'`.

### 7.2 Accumulated signals

Enel now has 42 signals in `digital_twin_signals`, from the PDF plus multiple emails, Teams
exchanges, RSS news, and WorkFabric memos. Example:

| signal_id | signal_type | trigger_summary |
|---|---|---|
| `SIG-3B377DD4` | SUSTAINABLE FUNDING | Enel is entering a treasury planning window requiring a comprehensive review of funding, rates, sustainable finance readiness... |
| `SIG-069AF8DA` | SUSTAINABLE FUNDING | CaixaBank CIB acted as Joint Active Bookrunner for Enel's €2.5 billion dual-tranche senior bond issuance. |
| `SIG-68A1FD24` | SUSTAINABLE FUNDING | Enel faces a €10.13bn debt maturity wall in 2026-2027 with significantly higher refinancing costs... |

### 7.3 The anchor

`ca.ca_opportunity_scoring` for CLI101 has:

- `why_now_nlg`: "Enel faces a significant €10.13bn debt maturity wall in 2026-2027, necessitating proactive treasury planning amidst a 5Y EUR swap rate of 2.62% and higher refinancing costs..."
- `next_best_action`: "We recommend a €1.0bn dual-tranche senior unsecured issuance, comprising a €600m 7Y Green bond at Mid-swap + 73 bps (net of -5 bps greenium) and a €400m 10Y Sustainability-Linked Bond..."

### 7.4 Synthesis

Since CLI101 is in `_DEMO_CLIENT_IDS`:

1. Anchor is read from the DB row
2. Cache is checked (miss on cold start)
3. Signal corpus is fetched (20 most recent)
4. Gemini is called with the anchor at the top of the prompt
5. Response comes back with `why_now` and `action` consistent with the anchor
6. Drift guard runs (no conflict detected — the LLM respected the anchor)
7. Fresh values written to the cache and back to the DB row

### 7.5 Read

The opportunity card displays:

- **Coverage RM:** Giulia Romano (from `ca.coverage_teams`)
- **Net Debt:** €58.5bn (from `ca.ext_company_filings`)
- **Available Liquidity:** €14.2bn
- **Maturities within 24 months:** €10.13bn
- **Match confidence:** High · 94 (from `ca_opportunity_scoring.priority_score`)
- **Catalyst Rationale (Why Now):** the synthesized narrative
- **Proposed Execution & Structuring:** the synthesized narrative

All values sourced from the DB or from LLM extraction grounded in DB content.

---

## 8. What Happens for a Non-Whitelisted Client

If a client is not in `_DEMO_CLIENT_IDS` (for example, BASF `CLI103`):

1. Ingestion works the same — signals are written to `ca.digital_twin_signals` with dedup
2. Signals appear in `/api/signals` **only if the client is in the whitelist** — currently
   the signal marquee is also filtered, so non-whitelisted clients' signals do not appear
3. In `/api/opportunities`, the client's row is processed but the synthesis block is skipped
4. The card displays `why_now_nlg` and `next_best_action` from the DB row directly
5. No LLM call is made for that client

This is intentional — see the hybrid rationale in `Architecture_Decision_Hybrid_vs_LLM_Only.md`.

---

## 9. Summary

The signal → opportunity pipeline is:

1. **LLM extracts** N signals per ingestion
2. **Code persists** signals with dedup, and stores the full chunk with metadata
3. **Synthesis (on read)** uses the accumulated signals, anchored to the curated DB row
4. **Drift guard** prevents the LLM from changing the mandate structure
5. **TTL cache** eliminates repeat synthesis calls within a 5-minute window
6. **Whitelist** scopes synthesis to demo clients

Every value displayed traces to a database row or to an LLM output grounded in DB content.
No formula, no fabrication, no placeholder strings.

---

*End of document.*