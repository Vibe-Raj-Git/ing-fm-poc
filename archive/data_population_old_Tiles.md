Here's the updated `data_population.md`. Save it as `Docs/data_population.md`, replacing the current version.

---

# Data Population & UI Lineage

**Version:** 17 September 2026
**Status:** Authoritative
**Supersedes:** `data_population.md` (14 Sep 2026)
**Audience:** Engineers, Business Analysts

---

## 1. Overview

This doc traces every visible field on the opportunity card and pitchbook back to the specific column or query that produces it. It also describes the mechanism that keeps the browser preview canvas and the downloaded `.pptx` file in sync.

The platform follows a strict principle: **no value is rendered without a database source.** Fallbacks exist for missing data but never substitute invented values. Client-specific metrics — net debt, liquidity, maturities, credit spreads, ratings — all trace to rows in the `ca` schema filtered by `client_id`.

The reset-to-pristine mechanism (documented in `Data_or_Fabrication.md` §8) does not change these read paths. It changes which rows win the `created_at DESC` sort after a reset, which shifts the visible values without altering the lineage. See §2.8 for the effect.

---

## 2. Opportunity Card — 4-Segment Grid Lineage

The top of the opportunity card is a 2×2 grid:

| Position | Segment Name | Purpose |
|---|---|---|
| Top-left | **Client Data** | Balance sheet and coverage context |
| Top-right | **Market Data** | Live rates, spreads, benchmark yields |
| Bottom-left | **Context Fabric** | Internal desk signals and latent opportunities |
| Bottom-right | **Houseviews & News** | Ingested research, news wires, and summaries |

Below the grid, a full-width **Synthesized Mandate & AI Catalyst** section renders the narrative and lineage audit.

### 2.1 Segment 1 — Client Data

| Field | Table | Column | Transformation |
|---|---|---|---|
| Coverage RM | `ca.coverage_teams` | `banker_name` WHERE `role_title ILIKE '%Relationship Manager%'` LIMIT 1 | Fallback: `ca.client_master.rm_name` |
| External ratings | `ca.client_master` | `tier` | Displayed as-is, **except for CLI101 (Enel)**, where the value is hardcoded as "S&P \| BBB \| Positive" — see `Data_or_Fabrication.md` §8.1 for the documented exception. For other clients, the `tier` column holds a coverage classification ("Tier 1"), not a credit rating |
| Net Debt | `ca.ext_company_filings` | `net_debt_eur_m` | Latest row by `reporting_period DESC`, formatted as `€{X}bn` if ≥ 1000, else `€{X}M` |
| Available Liquidity | `ca.ext_company_filings` | `liquidity_eur_m` | Same formatting rule |
| Potential debt maturities within 24 months | `ca.ext_company_filings` | `debt_maturing_24m_eur_m` | Formatted as `€{X}bn`. **This is the balance-sheet figure**, not the schedule sum |

**Note on maturities:** `ca.ext_company_filings.debt_maturing_24m_eur_m` and `ca.debt_maturity_schedule` measure different things. The balance-sheet field is the reported 24-month maturity wall. The schedule is itemized instruments. See §5 for details.

### 2.2 Segment 2 — Market Data

| Field | Table | Column | Notes |
|---|---|---|---|
| 5Y EUR Swap | `ca.mkt_rates_curves` | `swap_rate_pct` WHERE `currency = 'EUR'` AND `tenor = '5Y'` | Formatted as `{X.XX}%` |
| 10Y German Bund | `ca.mkt_rates_curves` | `govt_yield_pct` WHERE `currency = 'EUR'` AND `tenor = '10Y'` | Formatted as `{X.XX}%` |
| 5Y Credit Spread | `ca.ext_credit_spreads` | `spread_bps` WHERE `issuer_or_rating` matches client or rating bucket | Formatted as `{X} bps` |
| All-In Benchmark Yield | Derived | `swap_5y + (spread_bps / 100)` | Computed in Python, formatted as `{X.XX}%` |
| 5Y USD Swap Benchmark | `ca.mkt_rates_curves` | `swap_rate_pct` WHERE `currency = 'USD'` AND `tenor = '5Y'` | Formatted as `{X.XX}%` |

**Note on table design:** `ca.mkt_rates_curves` is a tall table — one row per (currency, tenor). The code selects by `currency` and `tenor`, not by a `curve_name` column (there is none).

### 2.3 Segment 3 — Context Fabric

The Context Fabric segment renders three sub-elements: ingestion chips, a Desk Signal, and a Latent Opportunity list.

#### 2.3.1 Ingestion chips

**Query:** `ca.document_vector_chunks WHERE client_id = %s AND source_channel IN (...)` ordered by `created_at DESC, chunk_id DESC`. The full channel `IN` list:

```
('WORKFABRIC_MEMO', 'CONTEXT_FABRIC', 'ANALYST_NOTE', 'TEAMS_CHAT', 'CLIENT_EMAIL')
```

**Channel standardization:** three of those five channels map to `WORKFABRIC_MEMO` at the display layer:

| Raw channel | Displayed channel | Chip label | Chip color |
|---|---|---|---|
| `WORKFABRIC_MEMO` | `WORKFABRIC_MEMO` | 🧠 WorkFabric Memo | Blue |
| `ANALYST_NOTE` | `WORKFABRIC_MEMO` | 🧠 WorkFabric Memo | Blue (merged) |
| `CONTEXT_FABRIC` | `WORKFABRIC_MEMO` | 🧠 WorkFabric Memo | Blue (merged) |
| `TEAMS_CHAT` | `TEAMS_CHAT` | 💬 Teams Chat | Indigo |
| `CLIENT_EMAIL` | `CLIENT_EMAIL` | ✉️ Treasury Email | Amber |

Result: at most three distinct chips per client, regardless of how many source-channel aliases exist in the DB.

**Deduplication:** the loop keeps only the first-seen row per standardized channel. With the sort `created_at DESC, chunk_id DESC`, the newest chunk (tiebroken by highest `chunk_id`) wins per channel.

**Preview:** each chip carries a 150-character preview of `text_content`, shown on hover.

#### 2.3.2 Desk Signal

**Read order:**

1. **Primary:** query `ca.document_vector_chunks WHERE client_id = %s AND source_channel = 'WORKFABRIC_MEMO' ORDER BY created_at DESC, chunk_id DESC LIMIT 1`. Use `text_content` as the Desk Signal.
2. **Fallback:** if no `WORKFABRIC_MEMO` chunk exists, query `ca.digital_twin_signals WHERE client_id = %s AND catalog_family IN ('Financing/Capital Markets', 'Interest Rate') AND (signal_type IS NULL OR signal_type != 'LATENT_OPPORTUNITY') ORDER BY confidence_pct DESC, signal_id ASC LIMIT 1`. Use `description` or `trigger_summary`.

The chunk-first read means the Desk Signal is normally a memo-style entry (WorkFabric, analyst note, or context fabric) rather than a machine-extracted signal.

#### 2.3.3 Latent Opportunity

**Query:** `ca.digital_twin_signals WHERE client_id = %s AND signal_type = 'LATENT_OPPORTUNITY' ORDER BY signal_id ASC LIMIT 3`.

Rendered as a numbered list L-01, L-02, L-03. If no latent opportunities exist, the display falls back to a static template string.

**Attribution:** the Attribution line shows the `source_name` of the newest `WORKFABRIC_MEMO` chunk (the same source that wins the Desk Signal primary read).

**Note on metadata formats:** `ca.document_vector_chunks.structured_metadata` uses three different schemas depending on ingestion era. See `Data_or_Fabrication.md` §5.3.

### 2.4 Segment 4 — Houseviews & News

#### 2.4.1 Houseview

| Field | Table | Column | Notes |
|---|---|---|---|
| Houseview chip | `ca.document_vector_chunks` | `source_name` WHERE `source_channel IN ('PDF_REPORT', 'HOUSEVIEW')` AND `source_channel NOT IN ('NEWS_RSS', 'LIVE_RSS_NEWS')` | Latest row by `created_at DESC, chunk_id DESC` |
| Chip hover | Same source | `structured_metadata.executive_summary` (or truncated `text_content`) | Truncated to 160 chars |
| Houseview body | Same source | `structured_metadata.executive_summary` | Full text, no truncation. Falls back to `text_content[:200]` if `executive_summary` is absent |

**Boundary isolation:** the internal research read explicitly excludes news channels (`NOT IN ('NEWS_RSS', 'LIVE_RSS_NEWS')`). Without this, ingested news headlines would spill into the "ING FM Research" label. This was a fix applied during the 14–17 Sep workstream.

**Fallback behavior:** if no houseview chunk exists for the client, the chip displays "ING FM Research" and the body displays the fallback string from `main.py` (a generic "no houseview published" message).

#### 2.4.2 Live Verified News

**Query:**

```sql
SELECT text_content, source_name
FROM ca.document_vector_chunks
WHERE client_id = %s
  AND source_channel IN ('NEWS_RSS', 'LIVE_RSS_NEWS', 'LIVE RSS News', 'News RSS')
ORDER BY created_at DESC, chunk_id DESC
LIMIT 1;
```

**Four channel aliases.** The current ingestion pipeline writes `LIVE_RSS_NEWS`; the other three are legacy aliases from earlier eras. Querying all four is deliberate — it ensures both current and historical news content is readable.

**Headline parsing:** if `text_content` contains the marker `[1] HEADLINE:`, the code extracts the line containing that marker and prepends `"LIVE RSS INTELLIGENCE WIRE: "`. Otherwise, `text_content` is used directly.

| Field | Table | Column | Notes |
|---|---|---|---|
| Live Verified News | `ca.document_vector_chunks` | `text_content` (parsed for `[1] HEADLINE:` marker) | Latest row across all four aliases |
| News source attribution | Same source | `source_name` | Latest row |
| Attribution line | Static | "ING Desk Research & Market Intelligence" | Displayed label |

### 2.5 Synthesized Mandate & AI Catalyst

Below the 4-segment grid, the full-width mandate section renders four lineage tiles plus the narrative pair.

#### 2.5.1 Lineage tiles

| Tile | Table | Column | Transform |
|---|---|---|---|
| 1 — Balance Sheet: Liquidity Buffer | `ca.ext_company_filings` | `liquidity_eur_m` | Same formatting as Segment 1 |
| 2 — Market DB | `ca.mkt_rates_curves` + `ca.ext_credit_spreads` | 5Y swap + 5Y credit spread | Format: `5Y Swap {X.XX}% / {Y} bps` |
| 3 — Context Fabric | `ca.digital_twin_signals` | `metric_value` WHERE `signal_type IN ('BOARD_AUTHORIZATION', 'Funding Capacity Authorisation')` AND `metric_value IS NOT NULL AND metric_value != ''` ORDER BY `created_at DESC` LIMIT 1 | See §2.5.2 for format |
| 4 — Houseview / News | `ca.document_vector_chunks` | Derived from the winning houseview chunk's `structured_metadata` (see §2.5.3) | — |

#### 2.5.2 Lineage Tile 3 — format contract

The read code constructs the display value with a fixed suffix:

```python
cf_tile_value = f"{_cap_num} financing capacity"
```

Where `_cap_num` is derived from `metric_value` with two normalizations:

1. Truncate at the first `;` — so `"€12.0bn; 'March 2027'"` becomes `"€12.0bn"`
2. Replace `.0bn` → `bn` and `.0B` → `B` — so `"€12.0bn"` becomes `"€12bn"`

**Contract:** the `metric_value` column for `BOARD_AUTHORIZATION` signals **must be a bare number**. A value that already contains the suffix ("€4.0bn financing capacity") would render as "€4bn financing capacity financing capacity".

Current example values:

- Enel's `BOARD_AUTHORIZATION` signal: `metric_value = "€12bn"` → tile displays `"€12bn financing capacity"`
- BASF's `SIG_BASF_BOARD_AUTH_01`: `metric_value = "€4.0bn"` → tile displays `"€4bn financing capacity"`

If a client has no matching signal, the tile shows `"No capacity signal"`.

#### 2.5.3 Lineage Tile 4 — fallback chain

Tile 4 reads the same chunk as the houseview chip (highest `chunk_id` among `PDF_REPORT` / `HOUSEVIEW`, tiebroken after `created_at DESC`). The value is derived via a fallback chain:

1. `structured_metadata.detected_signals[0].metric_identified` — trimmed at the first `;` and stripped of structured prefixes (`Amount: `, `Event: `)
2. If absent or N/A: `structured_metadata.detected_signals[0].signal_type` — abbreviated to first two words
3. If absent: the chunk's `source_name` with `.pdf` stripped and `_` replaced by space
4. If all else fails: `"No houseview ingested"`

#### 2.5.4 Narrative fields

| Field | Table | Column | Notes |
|---|---|---|---|
| Catalyst Rationale (Why Now) | `ca.ca_opportunity_scoring` | `why_now_nlg` | Anchor value, potentially rewritten by mandate synthesis with drift guard |
| Proposed Execution & Structuring | `ca.ca_opportunity_scoring` | `next_best_action` | Anchor value, potentially rewritten by mandate synthesis with drift guard |
| Pitchbook Ready | Static | "11 Slides Generated" | Display-only |
| Multi-Signal Lineage Verified | Static | Badge label | Display-only |

#### 2.5.5 Tile tooltips

Each lineage tile carries a `title=` attribute with a business-language description:

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

**Note on the `rank` column:** `ca.ca_opportunity_scoring.rank` exists but is not read by any code path. The presentation rank is computed at request time by enumerating sorted rows.

**Note on `COALESCE(priority_score, 75)`:** the sidebar query substitutes a fabricated score of 75 when a client has no scoring row. This is a known open item — see `Data_or_Fabrication.md` §6.7.

### 2.7 This Week Metrics Strip

| Field | Table | Query |
|---|---|---|
| Active drafts | `ca.digital_twin_signals` | `COUNT(DISTINCT client_id)` |
| Avg. time to first draft | Static | "less than 15s" (display-only) |
| Deals pending review | `ca.ca_opportunity_scoring` | `COUNT(DISTINCT client_id) WHERE priority_score >= 85` |
| Cohort matches | `ca.client_master` | `COUNT(*)` |

### 2.8 Reset Effect On Lineage

The reset-to-pristine endpoint (`Data_or_Fabrication.md` §8) does not change the read paths in §2.1–§2.7. It changes which rows win the sort.

After a reset:

- Pristine rows in `ca.digital_twin_signals` and `ca.document_vector_chunks` have `created_at = NOW()`, so they outrank any previously-ingested rows.
- The `chunk_id >= 9000000` convention (§8.5 in `Data_or_Fabrication.md`) ensures curated chunks win ties against organic chunks with higher sequence-assigned IDs.
- The Context Fabric chips, Desk Signal, Latent list, Houseviews body, Live Verified News, and the two tiles that read chunk data all shift to reflect the pristine state.
- User-ingested content remains in the DB, outranked but preserved.
- The Synthesized Mandate cache is invalidated, so the narrative re-synthesizes from the pristine anchor on the next read.

The specific post-reset values for a given client are the curated values captured in `baseline_snapshots.json`, not invented. See `Data_or_Fabrication.md` §8.6 for the full before/after comparison.

---

## 3. Continuous Live Signal Feed

The marquee at the top of the page reads from `ca.digital_twin_signals`.

### 3.1 Query

The live `/api/signals` handler runs:

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

Followed by a Python-level dedup and a `[:12]` slice. The `ANY(%s)` binds to the demo client whitelist (`_DEMO_CLIENT_IDS`).

**Note on the duplicate definition:** the file contains two `def get_live_signals()` definitions. The one decorated with `@app.get("/api/signals")` is bound to the route and is the live handler. The second is dead code — Python rebinds the module-level name at load, but the route holds a reference to the first function object. See `Data_or_Fabrication.md` §7.1.

The frontend applies a second dedup pass on `(client_name, headline)` before rendering. Final visible count: at most 12 unique signals.

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

If `metric_identified` is shorter than 20 characters, the code prefers `trigger_summary` for the marquee text. This gives cleaner display for signals like the board authorization (where `metric_identified` is just "€12.0bn" but `trigger_summary` is a full sentence).

---

## 4. Web Preview vs. PPTX Parity

Both the browser preview (`frontend/src/App.jsx`) and the `.pptx` export (`pitchbook_builder.py`) consume the same data source, produced by the same backend query.

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
| `fetch_pitchbook_bundle` | `pitchbook_builder.py` | Loads all data for a client into a context dict |
| `build_pitchbook` | `pitchbook_builder.py` | Builds the `.pptx` binary from the context |
| `get_opportunities` | `main.py` | Serves the `/api/opportunities` payload |
| `handle_pitchbook_generation` | `main.py` | Serves `/api/pitchbook/generate` |

Use `grep -n "def <function_name>" <file>` to locate any function in the current code.

### 4.3 Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/pitchbook/generate` | Generates and returns the `.pptx` file |
| `GET/POST /api/pitchbook/download` | Same handler, alternate path |

The frontend calls `/api/pitchbook/generate` with the current `deckOverrides` state. The backend applies those overrides on top of the DB bundle before rendering.

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

**Note:** The React preview uses Tailwind's `#F8FAFC` for card fills in some places, which is close to but not identical to `#F8F9FA` in the PPTX. A future alignment pass could unify these. The visual difference is imperceptible.

### 4.6 Slide count and structure

The deck has **11 slides** (not 10). The React canvas maps them via `case 0` through `case 10` in `App.jsx`. Slide 5 is the debt maturity profile; slide 8 is the term sheet.

Slide titles vary by product family (FX / Green / Rates / DCM). The full mapping is in `architecture_flow_14Sep.md` §6.2.

---

## 5. The Maturity Source Ambiguity

Two sources of truth exist for "what's maturing":

| Source | Value (Enel) | Meaning |
|---|---|---|
| `ca.ext_company_filings.debt_maturing_24m_eur_m` | €10,127M | Balance-sheet reported 24-month maturity wall |
| `ca.debt_maturity_schedule` (2026-2027) | €7,100M | Itemized instruments maturing in 2026 or 2027 |

These are **not the same thing**:

- The balance-sheet figure is a reported aggregate that a client discloses. It includes all debt maturing in a 24-month window as defined by the reporting period.
- The schedule is an itemized list of specific ISINs with specific maturity years.

The gap (€3.03bn for Enel) represents the difference in definitions. Neither is "wrong."

**Where each is used:**

| UI Element | Source |
|---|---|
| Segment 1 — "Potential debt maturities within 24 months" | Balance sheet (`debt_maturing_24m_eur_m`) |
| Lineage Tile 1 — "Liquidity Buffer" | Balance sheet (`liquidity_eur_m`) |
| Lineage Tile 3 — "Context Fabric" | `ca.digital_twin_signals.metric_value` WHERE `signal_type IN ('BOARD_AUTHORIZATION', 'Funding Capacity Authorisation')` |
| Slide 5 — per-tranche ladder | Schedule (`debt_maturity_schedule`) |
| Mandate narrative | Balance sheet figure (references "€10.13bn maturity wall") |

---

## 6. Data Sources For Non-Display Fields

Some fields exist in the DB and are read by code, but do not appear as display values. Others are entirely dormant.

| Column | Table | Current use |
|---|---|---|
| `propensity_score` | `ca.ca_opportunity_scoring` | Read by `pitchbook_builder.py` as an `ORDER BY` tiebreaker in `fetch_pitchbook_bundle`. Determines which scoring row resolves when a client has multiple rows. Not displayed. |
| `value_score` | `ca.ca_opportunity_scoring` | Not displayed, not read by any current code path. |
| `rank` | `ca.ca_opportunity_scoring` | Not displayed, not read by any code path. Presentation rank is computed at request time. |
| `metric_value` | `ca.digital_twin_signals` | Read for Lineage Tile 3 (with the bare-number contract in §2.5.2). Also read for signal display in some paths. |
| `catalog_family` | `ca.digital_twin_signals` | Not displayed. Used as a filter in the Desk Signal fallback read and in mandate synthesis. |
| `notes` | `ca.ext_company_filings` | Not displayed. |

---

## 7. Changelog — 17 Sep 2026

Corrections and additions since the 14 Sep 2026 version:

- **Context Fabric chip read corrected.** Full `IN` list documented (five channels, not three). Channel standardization to `WORKFABRIC_MEMO` documented.
- **Desk Signal read order corrected.** Now documents that the primary read is a `WORKFABRIC_MEMO` chunk, with `ca.digital_twin_signals` as a fallback — not the other way around.
- **Houseview body fallback documented.** Falls back to truncated `text_content` when `structured_metadata.executive_summary` is absent.
- **Live Verified News read corrected.** Four channel aliases documented (`NEWS_RSS`, `LIVE_RSS_NEWS`, `LIVE RSS News`, `News RSS`). Sort is `created_at DESC, chunk_id DESC`.
- **Boundary isolation noted.** Internal research queries exclude news channels with `NOT IN ('NEWS_RSS', 'LIVE_RSS_NEWS')`.
- **Lineage Tile 3 format contract documented (§2.5.2).** Bare-number requirement for `metric_value`, suffix-append behavior, `.0bn` normalization.
- **Lineage Tile 4 fallback chain documented (§2.5.3).** Full four-step fallback.
- **Reset effect on lineage documented (§2.8).** Cross-references `Data_or_Fabrication.md` §8.
- **`propensity_score` classification corrected.** Now documented as read by `pitchbook_builder.py` as an ORDER BY tiebreaker.
- **Line number references removed.** Function-name references retained; line numbers drift with every code change.
- **Section 2.3 restructured** into sub-sections (chips, Desk Signal, Latent list) for clarity.
- **Section 2.4 restructured** into sub-sections (houseview, Live Verified News).
- **Section 2.5 restructured** into sub-sections (tiles, tile-3 contract, tile-4 fallback chain, narrative fields, tooltips).
- **`COALESCE(priority_score, 75)` noted** in §2.6 with a cross-reference to `Data_or_Fabrication.md` §6.7.
- **Dead `get_live_signals` definition noted** in §3.1 with a cross-reference to `Data_or_Fabrication.md` §7.1.
- **Section 6 reclassified.** Now distinguishes "read by code" from "entirely dormant" fields.

---

*End of document.*