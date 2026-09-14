# Copilot Test Suite

**Version:** 14 September 2026
**Purpose:** Validation prompts for the ING FM Copilot against the pitchbook preview canvas
**Audience:** QA, Engineers, Product

---

## 1. Purpose & Scope

This doc is a **test suite** for the ING FM Copilot. It lists prompts to run against the
copilot and the expected behavior for each.

**In scope:**
- Read-side tests (copilot describes slide content accurately)
- Mutation tests (copilot returns overrides that change the deck state)
- Compliance tests (copilot runs MiFID II / MAR / EuGB audits)
- Structuring tests (copilot reasons across slides)

**Out of scope:**
- LLM prompt engineering (see `Copilot_Chatbot_Prompt.md` for the pattern)
- Model tuning
- Deployment configuration

---

## 2. Prerequisites

Before running any test:

- Deployed service is current (matches the branch's HEAD)
- `min-instances=1` is set on Cloud Run
- Cache has been warmed: `curl $SVC_URL/api/opportunities > /dev/null`
- Client under test is whitelisted for the demo (`_DEMO_CLIENT_IDS`)

**Current whitelist:** `{"CLI101"}` — Enel S.p.A. only.

Non-whitelisted clients (e.g., BASF `CLI103`) still work in the copilot but skip the
synthesis step. Their narrative comes from the raw DB row. Behavior may differ.

---

## 3. Expected Response Contract

Every copilot response is a JSON object with two fields:

```json
{
  "reply": "Natural-language explanation",
  "overrides": { "key": "value", ... }
}
```

- For **read-only questions**, `overrides` is empty (`{}`).
- For **mutation requests**, `overrides` contains one or more canonical keys.
- For **compliance audits**, `overrides` may contain remediation values.

**Canonical override keys** (the only keys the copilot must return):

| Key | Type | Example value |
|---|---|---|
| `notional_bond` | string | `"EUR 800,000,000"` |
| `notional_swap` | string | `"EUR 400,000,000"` |
| `tenor` | string | `"10 Years (T + 10Y)"` |
| `tenor_leg2` | string | `"12 Years (T + 12Y)"` |
| `spread` | string | `"Mid-swap + 75 bps"` |
| `spread_leg2` | string | `"Mid-swap + 80 bps (-2 bps vs baseline)"` |
| `greenium_bps` | integer | `7` |
| `eur_green_spread` | string | `"Mid-swap + 71 bps"` |
| `itraxx_main` | string | `"60 bps"` |
| `ecb_rate` | string | `"2.50%"` |
| `bund_10y` | string | `"2.65%"` |
| `pricing_caveat` | string | (MiFID II notice) |
| `emir_notice` | string | (EMIR NFC+ notice) |
| `disclaimers` | list of strings | (Regulatory disclosures) |

Any key not in this list should be treated as a test failure — the copilot is inventing
non-canonical keys.

---

## 4. Category 1 — Slide Content Awareness

**Purpose:** Verify the copilot reads from the hydrated deck state, not from memory.

**Method:** Ask a question about a specific slide. Compare the copilot's answer to what's
visible on the preview canvas.

### Test 1.1 — Enel Slide 4 balance sheet

**Prompt:**
```
What are the key balance sheet numbers on Slide 4?
```

**Expected behavior:**
- Copilot reply cites: net debt `€58.5bn`, liquidity `€14.2bn`, maturities within 24 months `€10.13bn`, revenue `€95,000M`, EBITDA `€20,900M`
- These values match what's rendered on slide 4
- `overrides` is `{}`

### Test 1.2 — Enel Slide 7 market backdrop

**Prompt:**
```
Explain Slide 7 and tell me what the 5Y swap rate is.
```

**Expected behavior:**
- Copilot identifies 5Y EUR swap rate as `2.62%`
- Copilot identifies 10Y Bund as `2.61%`, iTraxx Main as `58 bps`, ECB rate as `2.25%`
- Values match `ca.mkt_rates_curves` and slide 7's rendering

### Test 1.3 — Enel Slide 8 term sheet

**Prompt:**
```
Summarize the pricing and tenor from the Slide 8 term sheet.
```

**Expected behavior:**
- Copilot cites Green tranche: `€600m 7Y` at `Mid-swap + 78 bps` with `-5 bps greenium`
- Copilot cites SLB tranche: `€400m 10Y` at `Mid-swap + 80 bps`
- **No 8Y or 12Y tenors** — the anchored structure must be preserved

### Test 1.4 — Cross-slide synthesis

**Prompt:**
```
How do Slide 2's catalyst and Slide 8's term sheet tie together?
```

**Expected behavior:**
- Copilot connects the maturity wall (Slide 2 catalyst) to the specific tranches (Slide 8)
- No invented values

---

## 5. Category 2 — Live Parameter Mutations

**Purpose:** Verify the copilot returns canonical overrides that change the deck.

**Method:** Issue a mutation prompt. Verify three things:
1. `reply` acknowledges the change
2. `overrides` contains the correct canonical key with the correct value
3. The preview canvas re-renders with the new value

### Test 2.1 — Notional mutation

**Prompt:**
```
In Slide 8, adjust bond sizing to EUR 800,000,000
```

**Expected:**
- `overrides.notional_bond = "EUR 800,000,000"`
- Slide 8 notional cell for Leg 1 shows `EUR 800,000,000`
- Green tranche N (from greenium savings on Slide 6) re-renders if applicable

### Test 2.2 — Tenor mutation

**Prompt:**
```
In Slide 8, extend the tenor to 10 Years
```

**Expected:**
- `overrides.tenor = "10 Years (T + 10Y)"`
- Slide 8 tenor cell for Leg 1 shows `10 Years (T + 10Y)`
- Reference benchmark cell updates to `10Y EUR mid-swap` if the backend maps it

### Test 2.3 — Spread mutation

**Prompt:**
```
In Slide 8, change spread to Mid-Swap + 75 bps
```

**Expected:**
- `overrides.spread = "Mid-Swap + 75 bps"`
- Slide 8 spread cell for Leg 1 shows the new value
- Greenium indicator updates if the greenium is derived from the spread

### Test 2.4 — Greenium mutation

**Prompt:**
```
In Slide 6, adjust the greenium concession to 7 bps
```

**Expected:**
- `overrides.greenium_bps = 7`
- `overrides.greenium_concession = "-7 bps"` (derived)
- `overrides.eur_green_spread` updates so that `78 - 7 = 71 bps` shows on slide 6
- Slide 6 shows the new greenium and the recalculated savings (`€600M × 7 bps / 10000 = €420k/year`)

### Test 2.5 — Market index mutation

**Prompt:**
```
In Slide 7, update iTraxx Main to 60 bps
```

**Expected:**
- `overrides.itraxx_main = "60 bps"`
- Slide 7's iTraxx card re-renders with the new value

### Test 2.6 — Multi-key mutation

**Prompt:**
```
Update Slide 7: set iTraxx Main to 60 bps, ECB refi rate to 2.50%, and Bund 10Y yield to 2.65%.
```

**Expected:**
- `overrides` contains three keys: `itraxx_main`, `ecb_rate`, `bund_10y`
- Slide 7 shows all three updated cards

### Test 2.7 — Revert to baseline

**Prompt:**
```
Revert Slide 7 back to institutional baseline terms
```

**Expected:**
- Copilot reads the pristine baseline from `baseline_deck_slides`
- `overrides.itraxx_main = "58 bps"` (the baseline value)
- `overrides.ecb_rate = "2.25%"` (baseline)
- `overrides.bund_10y = "2.61%"` (baseline)
- Slide 7 re-renders with the original values

**This is the critical test.** It verifies the copilot respects the pristine baseline rather
than assuming the current active state is the baseline.

### Test 2.8 — Multi-variant override

**Prompt:**
```
Update Slide 8: set Green Bond notional to EUR 900M and Sustainability Overlay notional to EUR 500M.
```

**Expected:**
- `overrides.notional_bond = "EUR 900,000,000"`
- `overrides.notional_swap = "EUR 500,000,000"`
- Slide 8 shows both legs updated

### Test 2.9 — Post-revert sequential mutation

**Prompt sequence:**
1. `Revert Slide 8 back to baseline`
2. `Then update the Green Bond tenor to 8 Years`

**Expected after step 1:**
- Slide 8 reverts to baseline (7Y / 10Y, €600M / €400M)

**Expected after step 2:**
- `overrides.tenor = "8 Years (T + 8Y)"`
- Slide 8 Leg 1 shows `8 Years (T + 8Y)`

**Note:** This test exercises the drift guard. Since the anchor says 7Y, the drift guard
may refuse to apply 8Y and revert to 7Y. If the copilot applies 8Y, the drift guard has
a bug. If the copilot refuses, the drift guard is working as designed.

---

## 6. Category 3 — Compliance

### Test 3.1 — Full audit

**Prompt:**
```
Run a full MiFID II compliance check across this deck.
```

**Expected:**
- `overrides` contains `pricing_caveat`, `emir_notice`, `compliance_status`
- Reply describes the flagged slides and rules

### Test 3.2 — Targeted audit

**Prompt:**
```
Are there any missing disclaimers or target market disclosures on Slide 8 and Slide 10?
```

**Expected:**
- Reply references the specific slides
- If missing content is detected, `overrides` proposes the additions

### Test 3.3 — Remediation

**Prompt:**
```
Apply all recommended compliance remediations to the deck.
```

**Expected:**
- `overrides` includes updated disclaimers, `emir_notice`, and any other regulatory text
- Slide 11 (Disclosures) re-renders with the new content

---

## 7. Category 4 — Structuring Advisory

**Purpose:** Verify cross-slide reasoning without state mutation.

### Test 4.1 — Structuring rationale

**Prompt:**
```
Why should the client consider an IRS pre-hedge instead of waiting until issuance?
```

**Expected:**
- Copilot reasons over Slide 6 (sensitivity) and Slide 8 (term sheet)
- Reply discusses rate-lock rationale grounded in the current swap curve
- `overrides` is `{}`

### Test 4.2 — Rate sensitivity

**Prompt:**
```
What happens to our debt servicing costs if EUR swap rates rise by 50 bps?
```

**Expected:**
- Copilot uses the notional from Slide 8 and the swap rate from Slide 7
- Calculates the impact (e.g., `€600M × 50 bps = €3,000,000/yr`)
- No invented notionals or rates

### Test 4.3 — Execution roadmap

**Prompt:**
```
What are the critical execution milestones on Slide 10?
```

**Expected:**
- Copilot describes the four milestones from the deck
- No mutation

---

## 8. Known Constraints

### 8.1 Non-whitelisted clients

Clients not in `_DEMO_CLIENT_IDS` do not run synthesis. Their card narrative comes from the
DB row directly, and their signal marquee entries do not appear. When testing with a
non-whitelisted client (e.g., BASF `CLI103`), expect:

- Read-side tests to pass (the copilot still reads the deck)
- Mutation tests to pass (overrides work regardless of whitelist)
- Compliance tests to pass
- Synthesis-dependent tests to reflect the raw DB row, not a synthesized narrative

### 8.2 The drift guard

The copilot's override for `tenor` is post-validated by the drift guard. If the override
conflicts with the anchor's tenor, the guard replaces the LLM output with the anchor. This
means:

- Tenor mutations that match the anchor apply cleanly
- Tenor mutations that conflict with the anchor may be silently reverted to the anchor

This is by design (see `architecture_flow_14Sep.md` §5.4). Test 2.9 exercises this.

### 8.3 The maturity figure has two sources

Two sources of truth exist for Enel's maturities:

| Source | Value | Meaning |
|---|---|---|
| `ca.ext_company_filings.debt_maturing_24m_eur_m` | €10,127M | Balance-sheet reported 24-month maturity wall |
| `ca.debt_maturity_schedule` (2026-2027 window) | €7,100M | Individual instruments maturing in 2026 or 2027 |

These are not the same thing:

- The balance-sheet figure is what the pitchbook references as "24-month maturity wall"
- The schedule figure is what appears in slide 5's per-tranche ladder

Both are accurate for their own definition. Tests should reference the right source for the
right slide. **Do not treat the difference as a bug.**

### 8.4 The signal marquee shows only whitelisted clients

`/api/signals` is filtered to `_DEMO_CLIENT_IDS`. The marquee does not display signals for
non-whitelisted clients, even if their signals exist in the DB.

---

## 9. Test Execution Checklist

Before committing any code change, run the following:

- [ ] Category 1 (read) — all four tests pass
- [ ] Category 2 (mutation) — all nine tests pass
- [ ] Category 3 (compliance) — all three tests pass
- [ ] Category 4 (structuring) — all three tests pass
- [ ] Post-mutation state verified in preview canvas
- [ ] No non-canonical override keys returned by any test
- [ ] Drift guard behavior matches expectation (Test 2.9)

---

## 10. Changelog

### 14 September 2026

- Rewritten from the original `Copilot_Prompts.md`
- Corrected Enel tenors (7Y, not 8Y)
- Separated schedule-view maturities (€7.1bn) from balance-sheet maturities (€10.13bn)
- Added canonical override key contract
- Added drift guard notes
- Added non-whitelisted client behavior
- Converted literal expected responses to behavior-based tests
- Added BASF/baseline distinction

---

*End of document.*