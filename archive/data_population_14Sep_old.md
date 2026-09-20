# Data Population & UI Lineage

**Version:** 14 September 2026
**Status:** Authoritative
**Supersedes:** Previous `data_population.md` (pre-14 Sep)
**Audience:** Engineers, Business Analysts

---

## 1. Overview

This doc traces every visible field on the opportunity card and pitchbook back to the specific
column or query that produces it. It also describes the mechanism that keeps the browser
preview canvas and the downloaded `.pptx` file in sync.

The platform follows a strict principle: **no value is rendered without a database source.**
Fallbacks exist for missing data but never substitute invented values. Client-specific
metrics — net debt, liquidity, maturities, credit spreads, ratings — all trace to rows in the
`ca` schema filtered by `client_id`.

---

## 2. Opportunity Card — 4-Segment Grid Lineage

The top of the opportunity card is a 2×2 grid:

| Position | Segment Name | Purpose |
|---|---|---|
| Top-left | **Client Data** | Balance sheet and coverage context |
| Top-right | **Market Data** | Live rates, spreads, benchmark yields |
| Bottom-left | **Context Fabric** | Internal desk signals and latent opportunities |
| Bottom-right | **Houseviews & News** | Ingested research, news wires, and summaries |

Below the grid, a full-width **Synthesized Mandate & AI Catalyst** section renders the
narrative and lineage audit.

### 2.1 Segment 1 — Client Data

| Field | Table | Column | Transformation |
|---|---|---|---|
| Coverage RM | `ca.coverage_teams` | `banker_name` WHERE `role_title ILIKE '%Relationship Manager%'` | Fallback: `ca.client_master.rm_name` |
| External ratings | `ca.client_master` | `tier` | Displayed as-is. For CLI101, shown as "S&P \| BBB \| Positive" (client-specific) |
| Net Debt | `ca.ext_company_filings` | `net_debt_eur_m` | Latest row by `reporting_period DESC`, formatted as `€{X}bn` if ≥ 1000, else `€{X}M` |
| Available Liquidity | `ca.ext_company_filings` | `liquidity_eur_m` | Same formatting rule |
| Potential debt maturities within 24 months | `ca.ext_company_filings` | `debt_maturing_24m_eur_m` | Formatted as `€{X}bn`. Note: **this is the balance-sheet figure**, not the schedule sum |

**Note on maturities:** `ca.ext_company_filings.debt_maturing_24m_eur_m` and
`ca.debt_maturity_schedule` measure different things. The balance-sheet field is the reported
24-month maturity wall. The schedule is itemized instruments. See §5 for details.

### 2.2 Segment 2 — Market Data

| Field | Table | Column | Notes |
|---|---|---|---|
| 5Y EUR Swap | `ca.mkt_rates_curves` | `swap_rate_pct` WHERE `currency = 'EUR'` AND `tenor = '5Y'` | Formatted as `{X.XX}%` |
| 10Y German Bund | `ca.mkt_rates_curves` | `govt_yield_pct` WHERE `currency = 'EUR'` AND `tenor = '10Y'` | Formatted as `{X.XX}%` |
| 5Y Credit Spread | `ca.ext_credit_spreads` | `spread_bps` WHERE `issuer_or_rating` matches client or rating bucket | Formatted as `{X} bps` |
| All-In Benchmark Yield | Derived | `swap_5y + (spread_bps / 100)` | Computed in Python, formatted as `{X.XX}%` |
| 5Y USD Swap Benchmark | `ca.mkt_rates_curves` | `swap_rate_pct` WHERE `currency = 'USD'` AND `tenor = '5Y'` | Formatted as `{X.XX}%` |

**Note on table design:** `ca.mkt_rates_curves` is a tall table — one row per
(currency, tenor). The code selects by `currency` and `tenor`, not by a curve_name
column (there is none).

### 2.3 Segment 3 — Context Fabric

| Field | Table | Column | Notes |
|---|---|---|---|
| Ingestion chips | `ca.document_vector_chunks` | `source_channel`, `source_name` | Grouped by channel: `WORKFABRIC_MEMO`, `CLIENT_EMAIL`, `TEAMS_CHAT` |
| Desk Signal | `ca.digital_twin_signals` | `description` (or `trigger_summary`) | The most recent high-confidence signal for the client |
| Latent Opportunity | `ca.digital_twin_signals` | `trigger_summary` WHERE `signal_type = 'LATENT_OPPORTUNITY'` | Numbered list L-01, L-02, L-03 |
| Attribution | `ca.document_vector_chunks` | `source_name` for the latest memo | e.g., "WorkFabric Context Engine (Enel S.p.A.)" |

**Note on metadata formats:** `ca.document_vector_chunks.structured_metadata` uses three
different schemas depending on ingestion era. See `Data_or_Fabrication.md` §5.3.

### 2.4 Segment 4 — Houseviews & News

| Field | Table | Column | Notes |
|---|---|---|---|
| Houseview chip | `ca.document_vector_chunks` | `source_name` WHERE `source_channel IN ('PDF_REPORT', 'HOUSEVIEW')` | Latest row by `created_at DESC` |
| Chip hover | Same source | `structured_metadata.executive_summary` (or truncated `text_content`) | Truncated to 160 chars |
| Houseview body | Same source | `structured_metadata.executive_summary` | Full text, no truncation |
| RSS chip | `ca.document_vector_chunks` | `source_name` WHERE `source_channel = 'NEWS_RSS'` | Latest row |
| Live Verified News | Same source | `text_content` (parsed for `[1] HEADLINE:`) | Latest row |
| Attribution | Static | "ING Desk Research & Market Intelligence" | Displayed label |

**Fallback behavior:** If no houseview chunk exists for the client, the chip displays
"ING FM Research" and the body displays "No ING houseview published for this client in the
current reporting cycle."

### 2.5 Synthesized Mandate & AI Catalyst

Below the 4-segment grid, the full-width mandate section renders:

| Field | Table | Column | Notes |
|---|---|---|---|
| Lineage Tile 1 — Balance Sheet: Liquidity Buffer | `ca.ext_company_filings` | `liquidity_eur_m` | Same formatting as Segment 1 |
| Lineage Tile 2 — Market DB | `ca.mkt_rates_curves` + `ca.ext_credit_spreads` | 5Y swap + credit spread | Format: `5Y Swap {X.XX}% / {Y} bps` |
| Lineage Tile 3 — Context Fabric | `ca.digital_twin_signals` | `metric_value` WHERE `signal_type IN ('BOARD_AUTHORIZATION', 'Funding Capacity Authorisation')` | Format: `{X} financing capacity` |
| Lineage Tile 4 — Houseview / News | `ca.document_vector_chunks` | `structured_metadata.detected_signals[0].metric_identified` | Trimmed at first semicolon |
| Catalyst Rationale (Why Now) | `ca.ca_opportunity_scoring` | `why_now_nlg` | Anchor or synthesized narrative |
| Proposed Execution & Structuring | `ca.ca_opportunity_scoring` | `next_best_action` | Anchor or synthesized narrative |
| Pitchbook Ready | Static | "11 Slides Generated" | Confirmed by slide count in the app |
| Multi-Signal Lineage Verified | Static | Badge label | Display-only |

**Tile tooltips:** Each lineage tile carries a `title=` attribute with a business-language
description:

| Tile | Tooltip |
|---|---|
| 1 | `Source: Company filings — reported liquidity position` |
| 2 | `Source: Live market data feed — swap rates and credit spreads` |
| 3 | `Source: Debt maturity schedule and twin signals` |
| 4 | `Source: Ingested houseviews and news` |

No schema names appear in any user-visible tooltip.

### 2.6 Priority Today Sidebar

| Field | Table | Column | Notes |
|---|---|---|---|
| Rank badge | Computed | Enumerate index over priorities sorted by `priority_score DESC` | "RANK #1 (SCORE 94)" |
| Client name | `ca.client_master` | `client_name` | |
| Description | `ca.ca_opportunity_scoring` | `why_now_nlg` | Truncated |
| Action | `ca.ca_opportunity_scoring` | `next_best_action` | Truncated |
| Fee estimate | `ca.ca_opportunity_scoring` | `est_revenue_eur_000` | Formatted as `€{X.X}M` or `€{X}k` |

**Note on the "rank" column:** `ca.ca_opportunity_scoring.rank` exists but is not read by
any code path. The presentation rank is computed at request time by enumerating sorted rows.

### 2.7 This Week Metrics Strip

| Field | Table | Query |
|---|---|---|
| Active drafts | `ca.digital_twin_signals` | `COUNT(DISTINCT client_id)` |
| Avg. time to first draft | Static | "less than 15s" (display-only) |
| Deals pending review | `ca.ca_opportunity_scoring` | `COUNT(DISTINCT client_id) WHERE priority_score >= 85` |
| Cohort matches | `ca.client_master` | `COUNT(*)` |

---

## 3. Continuous Live Signal Feed

The marquee at the top of the page reads from `ca.digital_twin_signals`.

### 3.1 Query

```sql
SELECT DISTINCT ON (s.signal_id)
    s.signal_id,
    s.client_id,
    COALESCE(c.client_name, s.client_id) as client_name,
    s.signal_type,
    COALESCE(
        CASE
            WHEN LENGTH(COALESCE(s.metric_identified, '')) < 20 THEN s.trigger_summary
            ELSE s.metric_identified
        END,
        s.metric_identified,
        s.trigger_summary,
        s.description,
        'Market Catalyst'
    ) as headline,
    s.confidence_pct,
    s.urgency,
    s.created_at
FROM ca.digital_twin_signals s
LEFT JOIN ca.client_master c ON (s.client_id = c.client_id)
WHERE s.client_id = ANY(%s)
ORDER BY s.signal_id, s.created_at DESC
LIMIT 40;
```

The `ANY(%s)` binds to the demo client whitelist (`_DEMO_CLIENT_IDS`). Non-whitelisted
clients do not appear in the marquee.

### 3.2 Type normalization

`signal_type` values render with underscores replaced by spaces:

```python
def _format_signal_type(raw_type) -> str:
    if not raw_type:
        return "CATALYST"
    return str(raw_type).replace("_", " ").upper()
```

So `BOARD_AUTHORIZATION` renders as `BOARD AUTHORIZATION`, `SUSTAINABLE FUNDING` as-is, etc.

### 3.3 Headline selection

If `metric_identified` is shorter than 20 characters, the code prefers `trigger_summary` for
the marquee text. This gives cleaner display for signals like the board authorization
(where `metric_identified` is just "€12.0bn" but `trigger_summary` is a full sentence).

---

## 4. Web Preview vs. PPTX Parity

Both the browser preview (`frontend/src/App.jsx`) and the `.pptx` export
(`pitchbook_builder.py`) consume the same data source, produced by the same backend query.

### 4.1 Data flow

```
              ┌──────────────────────────────────────────────────┐
              │   Cloud SQL PostgreSQL (ca schema)               │
              └──────────────────────┬───────────────────────────┘
                                     │
                                     ▼
              ┌──────────────────────────────────────────────────┐
              │   /api/opportunities (main.py)                   │
              │   - Reads all tables                             │
              │   - Runs mandate synthesis (whitelisted clients) │
              │   - Returns JSON payload                         │
              └──────────────────────┬───────────────────────────┘
                                     │
              ┌──────────────────────┴───────────────────────────┐
              │                                                  │
              ▼                                                  ▼
   ┌────────────────────────────┐              ┌────────────────────────────┐
   │  React Preview Canvas      │              │  PPTX Generation           │
   │  (App.jsx)                 │              │  (pitchbook_builder.py)    │
   │                            │              │                            │
   │  • Reads from payload      │              │  • fetch_pitchbook_bundle  │
   │  • Applies deckOverrides   │              │  • build_pitchbook         │
   │  • Renders 16:9 DOM        │              │  • Renders 16:9 PPTX       │
   └────────────────────────────┘              └────────────────────────────┘
```

### 4.2 Key functions

| Function | File | Purpose |
|---|---|---|
| `fetch_pitchbook_bundle(canonical_id, client_id_raw, get_db_connection)` | `pitchbook_builder.py:272` | Loads all data for a client into a context dict |
| `build_pitchbook(ctx, opp, compliance_bullets, overrides)` | `pitchbook_builder.py:587` | Builds the `.pptx` binary from the context |
| `get_opportunities()` | `main.py:647` | Serves the `/api/opportunities` payload |
| `handle_pitchbook_generation(request)` | `main.py:2107` | Serves `/api/pitchbook/generate` |

### 4.3 Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/pitchbook/generate` | Generates and returns the `.pptx` file |
| `GET/POST /api/pitchbook/download` | Same handler, alternate path |

The frontend calls `/api/pitchbook/generate` with the current `deckOverrides` state. The
backend applies those overrides on top of the DB bundle before rendering.

### 4.4 Aspect ratio

Both sides render at 16:9:

- **Preview:** Tailwind `aspect-[16/9]` container
- **PPTX:** `Presentation().slide_width = Inches(13.333)`, `.slide_height = Inches(7.5)`

### 4.5 Color palette

The palette is defined in `pitchbook_builder.py`:

| Name | RGB | Hex | Usage |
|---|---|---|---|
| `ING_NAVY` | `RGBColor(0, 0, 102)` | `#000066` | Primary text on light backgrounds |
| `ING_ORANGE` | `RGBColor(255, 98, 0)` | `#FF6200` | Accent, headers, active elements |
| `ING_DARK_SLATE` | `RGBColor(12, 17, 43)` | `#0C112B` | Cover slide background |
| `BG_LIGHT` | `RGBColor(248, 249, 250)` | `#F8F9FA` | Card fill in PPTX |
| `CARD_BG_BLUE` | `RGBColor(240, 244, 255)` | `#F0F4FF` | Blue card backgrounds |
| `SUCCESS_GREEN` | `RGBColor(16, 149, 79)` | `#10954F` | Positive metrics |

**Note:** The React preview uses Tailwind's `#F8FAFC` for card fills in some places, which is
close to but not identical to `#F8F9FA` in the PPTX. A future alignment pass could unify
these. The visual difference is imperceptible.

### 4.6 Slide count and structure

The deck has **11 slides** (not 10). The React canvas maps them via `case 0` through
`case 10` in `App.jsx`. Slide 5 is the debt maturity profile; slide 8 is the term sheet.

Slide titles vary by product family (FX / Green / Rates / DCM). The full mapping is in
`architecture_flow_14Sep.md` §6.2.

---

## 5. The Maturity Source Ambiguity

Two sources of truth exist for "what's maturing":

| Source | Value (Enel) | Meaning |
|---|---|---|
| `ca.ext_company_filings.debt_maturing_24m_eur_m` | €10,127M | Balance-sheet reported 24-month maturity wall |
| `ca.debt_maturity_schedule` (2026-2027) | €7,100M | Itemized instruments maturing in 2026 or 2027 |

These are **not the same thing**:

- The balance-sheet figure is a reported aggregate that a client discloses. It includes all
  debt maturing in a 24-month window as defined by the reporting period.
- The schedule is an itemized list of specific ISINs with specific maturity years.

The gap (€3.03bn for Enel) represents the difference in definitions. Neither is "wrong."

**Where each is used:**

| UI Element | Source |
|---|---|
| Segment 1 — "Potential debt maturities within 24 months" | Balance sheet (`debt_maturing_24m_eur_m`) |
| Lineage Tile 1 — "Liquidity Buffer" | Balance sheet (`liquidity_eur_m`) |
| Lineage Tile 3 — "Context Fabric (Maturities)" | Balance sheet figure for the "24-month wall" |
| Slide 5 — per-tranche ladder | Schedule (`debt_maturity_schedule`) |
| Mandate narrative | Balance sheet figure (references "€10.13bn maturity wall") |

---

## 6. Data Sources For Non-Display Fields

Some fields exist in the DB but aren't shown:

| Column | Table | Current use |
|---|---|---|
| `propensity_score` | `ca.ca_opportunity_scoring` | Not displayed; retained for future ranking |
| `value_score` | `ca.ca_opportunity_scoring` | Not displayed; retained |
| `rank` | `ca.ca_opportunity_scoring` | Not displayed; presentation rank computed at request time |
| `metric_value` | `ca.digital_twin_signals` | Used for the Context Fabric lineage tile |
| `catalog_family` | `ca.digital_twin_signals` | Not displayed, but used in synthesis |
| `notes` | `ca.ext_company_filings` | Not displayed |

---

## 7. Changelog — 14 Sep 2026

Corrections from the pre-14-Sep version:

- **Column names corrected.** Removed references to non-existent columns
  (`ticker`, `curve_name`, `rate_pct`, `index_name`). Replaced with actual columns.
- **4-segment layout corrected.** Segment 4 is Houseviews & News, not "Mandate & Action."
  The Mandate is a separate full-width section below the grid.
- **Endpoint corrected.** `/api/opportunities/{id}/export-pptx` replaced with
  `/api/pitchbook/generate` and `/api/pitchbook/download`.
- **Function names corrected.** `get_pitchbook_content` replaced with
  `fetch_pitchbook_bundle` + `build_pitchbook`.
- **Slide count corrected.** 10 → 11 slides.
- **Slide numbering corrected.** Debt maturity is slide 5, not slide 3.
- **Color palette corrected.** `#F8FAFC` → `#F8F9FA` (BG_LIGHT), with a note about
  minor Tailwind/preview variance.
- **Maturity source ambiguity documented.** Balance sheet vs. schedule.
- **Data Sources For Non-Display Fields section added.**

---

*End of document.*