# System Architecture & Data Contract Guardrail: Zero-Hardcoding Pipeline

**Version:** 20 September 2026 — Weighted-Family + Adjacencies
**Flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Parallel flavor:** Baseline (Flavor 1) at `Docs/SYSTEM_ARCHITECTURE_&_DATA_CONTRACT_GUARDRAIL.md`
**Branch:** `feat/dulcet-20Sep-demo-Weighted-LLMProductFamilyIdentification-AdjOppS3`
**Branding branch:** `feat/bfs-ai-lab-brand-toggle` (adds the runtime brand toggle — see §4 read-path invariant and §5.9)
**Target Scope:** `App.jsx`, `main.py`, `pitchbook_builder.py`, `test_parity.py`

**Core Directive:** Maintain 100% data-driven parity across the UI preview, the PPTX generation (`python-pptx`), and the Copilot LLM prompts. No hardcoded financial rates, no placeholder text, no synthetic fallbacks — with the documented exceptions listed in §5.

---

## 1. Verified PostgreSQL Schema

All data resolves dynamically from these tables in the `ca` schema. Column lists verified against `information_schema.columns` on 21 Sep 2026.

The DB contains **12 tables**, all in schema `ca`:

| # | Table |
|---|---|
| 1 | `ca.client_master` |
| 2 | `ca.ext_company_filings` |
| 3 | `ca.debt_maturity_schedule` |
| 4 | `ca.mkt_rates_curves` |
| 5 | `ca.ext_credit_spreads` |
| 6 | `ca.ca_opportunity_scoring` |
| 7 | `ca.digital_twin_signals` |
| 8 | `ca.document_vector_chunks` |
| 9 | `ca.coverage_teams` |
| 10 | `ca.ext_deals` |
| 11 | `ca.dt_client_master` (legacy) |
| 12 | `ca.cand5_client_master` (legacy, empty) |

### `ca.client_master`

| Column | Type | Notes |
|---|---|---|
| `client_id` | varchar | Primary key |
| `client_name` | varchar | |
| `group_parent` | varchar | |
| `legal_entity` | varchar | |
| `industry_sector` | varchar | |
| `country` | varchar | |
| `region` | varchar | |
| `ownership_type` | varchar | |
| `tier` | varchar | Coverage classification ("Tier 1"), **not** a credit rating |
| `hq_country` | varchar | |
| `revenue_eur_m` | numeric | Millions EUR |
| `rm_name` | varchar | Fallback RM if no `coverage_teams` row |
| `base_ccy` | varchar | |

**No `credit_rating` column.** See §5 Exception 1.

### `ca.ext_company_filings`

| Column | Type |
|---|---|
| `filing_id` | varchar (PK) |
| `client_id` | varchar |
| `reporting_period` | varchar |
| `net_debt_eur_m` | numeric (millions) |
| `liquidity_eur_m` | numeric (millions) |
| `ebitda_eur_m` | numeric (millions) |
| `reported_revenue_eur_m` | numeric (millions) |
| `debt_maturing_24m_eur_m` | numeric (millions) |
| `notes` | text |

**Presentation transform:** values ≥ 1000 are formatted as `€{X.XX}bn`; below that as `€{X}M`. For Enel: `net_debt_eur_m = 58500` → `€58.5bn`; `debt_maturing_24m_eur_m = 10127` → `€10.13bn`.

**Multi-row hazard.** The table can contain multiple rows per client with identical `reporting_period` values. Most rows carry NULL for revenue/EBITDA; one row carries the populated values. Reads that pick "the latest row" via `ORDER BY reporting_period DESC LIMIT 1` can land on a NULL row. `fetch_pitchbook_bundle` filters `AND reported_revenue_eur_m IS NOT NULL`. See `Data_or_Fabrication.md` §11.9.

### `ca.debt_maturity_schedule`

| Column | Type |
|---|---|
| `isin` | varchar |
| `client_id` | varchar |
| `instrument_type` | varchar |
| `amount_eur_m` | numeric |
| `maturity_year` | integer |
| `coupon_rate_pct` | numeric |
| `currency` | varchar |

**No primary key on this table.** The reset endpoint uses delete-by-client + insert. See `Data_or_Fabrication.md` §11.4.

### `ca.mkt_rates_curves`

| Column | Type |
|---|---|
| `curve_id` | integer (PK) |
| `curve_date` | date |
| `currency` | varchar |
| `tenor` | varchar |
| `swap_rate_pct` | numeric |
| `govt_yield_pct` | numeric |
| `category` | varchar |

**Ground truth (EUR):**

| Tenor | swap_rate_pct | govt_yield_pct |
|---|---|---|
| 5Y | 2.62 | 2.38 |
| 10Y | 2.88 | 2.61 |

**Note:** the 10Y Bund value (`govt_yield_pct = 2.61`) is on the 10Y row, not the 5Y row.

### `ca.ext_credit_spreads`

| Column | Type |
|---|---|
| `spread_id` | integer (PK) |
| `quote_date` | date |
| `issuer_or_rating` | varchar |
| `sector` | varchar |
| `tenor` | varchar |
| `spread_bps` | numeric |
| `all_in_yield_pct` | numeric |
| `source` | varchar |

**Ground truth (Enel `CLI101`):**

| Tenor | spread_bps | all_in_yield_pct |
|---|---|---|
| 5Y | 78.0 | 3.40 |
| 10Y | 80.0 | 3.41 |

### `ca.ca_opportunity_scoring`

| Column | Type | Notes |
|---|---|---|
| `opportunity_id` | varchar | Primary key |
| `client_id` | varchar | |
| `opportunity_type` | varchar | Free text |
| `trigger_source` | text | |
| `est_revenue_eur_000` | numeric | Thousands EUR |
| `propensity_score` | integer | Read as ORDER BY tiebreaker in `fetch_pitchbook_bundle` |
| `value_score` | integer | Not read by any code path |
| `priority_score` | integer | LLM-computed; refreshed on every synthesis cache miss |
| `rank` | integer | Not read by any code path |
| `next_best_action` | text | **Anchor field** — protected from LLM overwrite |
| `why_now_nlg` | text | **Anchor field** — protected from LLM overwrite |

**Note:** `priority_score` is LLM-computed against a weighted rubric on every synthesis run (commit `13721ca`). See `Data_or_Fabrication.md` §6.

### `ca.digital_twin_signals`

| Column | Type |
|---|---|
| `signal_id` | varchar (PK) |
| `client_id` | varchar |
| `catalog_family` | varchar |
| `signal_type` | varchar |
| `metric_value` | varchar |
| `metric_identified` | text |
| `trigger_summary` | text |
| `description` | text |
| `confidence_pct` | integer |
| `urgency` | varchar |
| `created_at` | timestamp |

### `ca.document_vector_chunks`

| Column | Type |
|---|---|
| `chunk_id` | bigint (PK) |
| `client_id` | varchar |
| `source_channel` | varchar |
| `source_name` | varchar |
| `text_content` | text |
| `structured_metadata` | jsonb |
| `embedding` | vector(768) |
| `created_at` | timestamp |

### `ca.coverage_teams`

| Column | Type |
|---|---|
| `client_id` | varchar |
| `role_title` | varchar |
| `banker_name` | varchar |
| `location` | varchar |

**No primary key on this table.** The reset endpoint uses delete-by-client + insert. Filter read path: `role_title ILIKE '%Relationship Manager%'`.

### `ca.ext_deals`

| Column | Type |
|---|---|
| `deal_id` | varchar (PK) |
| `client_id` | varchar |
| `deal_type` | varchar |
| `volume_eur_m` | numeric |
| `role` | varchar |
| `deal_date` | date |
| `description` | text |

**Usage:** currently unused. Candidate for the "Why Execute With Us" slide.

### Legacy tables

- `ca.dt_client_master` (13 rows) — reduced-column version of `client_master`
- `ca.cand5_client_master` (0 rows) — deprecated candidate staging

---

## 2. Slide-by-Slide Dynamic Resolution Contract

The pitchbook has **11 slides**. Slide titles vary by product family (FX / Green / Rates / DCM). Full mapping is in `architecture_flow_20Sep.md` §6.2.

The table below documents the Green/ESG family (Enel's deck). Other families follow the same column sources with different slide names.

### Slide 1 — Cover

- `ca.client_master.client_name`, `legal_entity`
- Product family via `detect_product_family()`
- RM name: `ca.coverage_teams.banker_name` where `role_title ILIKE '%Relationship Manager%'`
- Fallback: `ca.client_master.rm_name`
- Credit rating: `_CREDIT_RATINGS` dict (see §5 Exception 1)

### Slide 2 — Strategic Catalyst

- **Primary Market Trigger:** `ca.ca_opportunity_scoring.trigger_source` or synthesized narrative
- **Window of Opportunity:** synthesis output
- **Recommended Action:** `ca.ca_opportunity_scoring.next_best_action` or synthesis output

### Slide 3 — Executive Summary

- Numbered pillars from `get_product_pillars(p_fam, ctx, ov)` in `pitchbook_builder.py`
- Pillars blend `ca.digital_twin_signals` (WorkFabric latent opportunities) + `ca.ca_opportunity_scoring.next_best_action` + family template content

### Slide 4 — Balance Sheet Foundation

| Card | Source | Format |
|---|---|---|
| Net Debt | `ca.ext_company_filings.net_debt_eur_m` | `€{X.X}bn` if ≥ 1000, else `€{X}M` |
| Available Liquidity | `ca.ext_company_filings.liquidity_eur_m` | Same |
| 24M Maturity Wall | `debt_maturing_24m_bn` (billions-formatted) | `€10.13bn` for Enel |
| Credit Rating | `_CREDIT_RATINGS` dict per client | See §5 Exception 1 |
| Revenue | `ca.ext_company_filings.reported_revenue_eur_m` | `€{X}M` |
| EBITDA | `ca.ext_company_filings.ebitda_eur_m` | `€{X}M` |

### Slide 5 — Use of Proceeds Pool (Green family)

- Green pool breakdown from synthesis context, not a DB table.
- **Future improvement:** add a `ca.sustainability_frameworks` table to source the pool breakdown deterministically.

### Slide 6 — Greenium Sensitivity (Green family)

- Green spread: `ca.ext_credit_spreads.spread_bps` for the client's 5Y row
- Greenium: `ca.ca_opportunity_scoring.why_now_nlg` or synthesis override
- Savings: computed as `notional × greenium_bps / 10000`

### Slide 7 — ESG Market Backdrop

- 5Y EUR Swap: `ca.mkt_rates_curves.swap_rate_pct` WHERE `tenor = '5Y'`
- 10Y Bund: `ca.mkt_rates_curves.govt_yield_pct` WHERE `tenor = '10Y'`
- 5Y Credit Spread: `ca.ext_credit_spreads.spread_bps` WHERE `tenor = '5Y'`
- All-In Yield: computed or from `ca.ext_credit_spreads.all_in_yield_pct`
- Copilot context strings build reference curves with dynamic f-strings, not literals

### Slide 8 — Proposal Features (Term Sheet)

- Notional Leg 1: `ov.get("notional_bond")` or bundle default
- Notional Leg 2: `ov.get("notional_swap")` or bundle default
- Tenor: `ov.get("tenor")` or `compute_canonical_bundle()`
- Spread cell: mutations from Copilot propagate to the spread row
- Documentation: `ov.get("disclaimers")` or family fallback list

### Slide 9 — Why Execute With Us

- Currently renders generic franchise capability cards.
- **Future improvement:** wire to `ca.ext_deals` for client-specific credentials.

### Slide 10 — Execution Roadmap (or SPO & Syndicate Plan for Green)

- Milestones from template in `pitchbook_builder.py`
- Product family changes the specific milestone wording

### Slide 11 — Regulatory Disclosures

- Disclaimers from `ov.get("disclaimers")` or product-family fallback
- Regulatory regime injection: ICMA GBP, EU Taxonomy, MiFID II, EMIR Refit

---

## 3. The 3-Tier Resolution Hierarchy

Whenever a value is queried, computed, or formatted, enforce this order:

### Tier 1 — Active Session Overrides (`current_ov` / `ov`)

Runtime mutations from the RM or Copilot. Example: `{'credit_spread_5y': '60 bps'}`. These take precedence over everything.

### Tier 2 — Canonical Database Context (`bundle` / `opp` / `calc` / `ctx`)

Live values from `ca` tables via `fetch_pitchbook_bundle()` and `compute_canonical_bundle()`. Plus, for whitelisted clients, values from the synthesis cache (`_MANDATE_SYNTH_CACHE`, **8-tuple in Flavor 2**) — specifically `why_now`, `action`, `why_now_summary`, `action_summary`, `priority_score`, **`family`**, **`adjacent_opportunities`**.

### Tier 3 — Fail-Safe Non-Breaking Fallback

Strictly for type safety if a database field returns `None`. **Never embed static business rates or bypass the canonical calculation.** Fallbacks return `"N/A"`, `"—"`, or an empty string — not invented numbers.

---

## 4. Invariance & Verification Rules

### Non-destructive invariance

Copilot prompt mutations are session-only. **Never** run `UPDATE` or `INSERT` queries against `ca.ext_credit_spreads` or `ca.mkt_rates_curves` during chat or deck builds. The only permitted write-back is the mandate synthesis to `ca.ca_opportunity_scoring.priority_score` — and only the score. The anchor narratives (`why_now_nlg`, `next_best_action`) are **protected from LLM overwrite**. `family` and `adjacent_opportunities` are not persisted to the DB (no columns exist). See §5 for exceptions.

### Read-path brand substitution (branding branch)

`_brand_substitute` applies a word-boundary `\bING\b` → active brand name substitution to 10 DB- and LLM-sourced text fields in `/api/opportunities`: `why_now`, `action`, `why_now_summary`, `action_summary`, `adjacent_opportunities`, `cf_description`, `cf_latent`, `hv_doc_title`, `hv_doc_summary`, `news_headline`.

**Rules:**

- Applied in Python after the row is fetched — never in SQL. Both services read the same rows and transform on the way out.
- No DB mutation. No `UPDATE`, no `INSERT`.
- No-op when the active brand is ING — the ING path is byte-identical to its pre-toggle behaviour.
- Email addresses (`@ing.`) are intentionally not substituted. An email address is a factual reference, not brand chrome.
- Numeric fields, IDs, dates, and structured metadata are not substituted.

Full specification: `Brand_Toggle_Implementation.md` §4.4.

### Cache/DB consistency invariant

The `_MANDATE_SYNTH_CACHE` is populated **only after** `conn.commit()` succeeds. On persist failure, the cache entry is popped. This prevents the UI from serving a cached value the DB does not hold. See `Data_or_Fabrication.md` §7.8.

### Table cell text access (python-pptx)

Table cell contents must be inspected via `cell.text_frame.text`, never `shape.text`. `shape.text` does not exist on table shapes and will raise `AttributeError`.

### Clean string escapes

Use raw Python strings (`r"..."`) or properly escaped regex tokens (`\\d+`) to avoid `SyntaxWarning` issues when embedding patterns in f-strings.

### Audit gate requirement

`test_parity.py` runs a 13-gate dynamic parity audit. It validates:

- PostgreSQL connection
- `ca.mkt_rates_curves` ground truth (5Y swap 2.62%, 10Y Bund 2.61%)
- `ca.ext_credit_spreads` ground truth (Enel 5Y = 78 bps, 10Y = 80 bps)
- `/api/opportunities` Enel retrieval
- Database bundle integrity
- Plus 8 additional gates covering the pipeline, PPTX generation, and preview consistency

**Any proposed code change must maintain 13/13 passing gates.** Run:

```bash
cd ~/ing-fm-poc
python3 test_parity.py
```
Expected output ends with all 13 gates printed as ✅ and a summary like 13/13 gates passed.

`test_parity.py` is not a pytest suite — it's an inline audit script. Run it directly.

## 5. Known Exceptions To Zero-Hardcoding
The platform aims for 100% data-driven values. Nine exceptions exist today, documented for future cleanup. The source of truth for each is the referenced section of the persona.

### 5.1 — Credit rating dict (_CREDIT_RATINGS)
**Location:** ``main.py` near `BRAND_PROFILES``, ``pitchbook_builder.py` near the module logger`.

**What it is:** a curated dict mapping `client_id` to a rating display string. `ca.client_master` has no credit_rating column.
```python
_CREDIT_RATINGS = {
    "CLI101": "S&P | BBB | Positive",   # Enel S.p.A.
    "CLI103": "S&P | A- | Stable",      # BASF SE
}
```
**Why it exists:** the tier column holds a coverage classification, not a credit rating. §7.2 forbids DDL — no `credit_rating` column can be added in the current phase.

Adding a client requires adding its rating to both dicts.

**Future fix:** add a `credit_rating` column to `ca.client_master` when DDL is unlocked.

### 5.2 — WorkFabric latent opportunities in pillars
**Location:** `pitchbook_builder.py` — `get_product_pillars()`.

**What it is:** when a client's `ca.digital_twin_signals` corpus has no `LATENT_OPPORTUNITY` rows, the function uses a template paragraph for pillar 2.

**Impact:** fires only when the signal corpus is sparse. For Enel, three latent opportunities exist and the pillar renders real content.

### 5.3 — COALESCE(priority_score, 75) fallback
**Location:** `main.py:337` (the /api/metrics priorities query), `main.py:848` (the main /api/opportunities query).

**What it is:** a fabricated score of 75 substitutes when a client has no scoring row.

**Currently dormant:** all 13 clients have scoring rows.

**Future fix:** replace with a null-preserving read; handle score_num = None downstream in _effective_score (line 935) and the response construction (line 936).

### 5.4 — Frontend default* constants
**Location:** `frontend/src/App.jsx`.

**What it is:** per-family hardcoded fallbacks for net debt, liquidity, revenue, and EBITDA. Fires when `/api/opportunities` doesn't supply the corresponding field. For the current two clients, the constants are coincidence-correct.

**Future fix:** expose `revenue_str`, `ebitda_str`, `net_debt_str`, `liquidity_str` in the API response; remove the constants.

### 5.5 — `pitchbook_builder.py:1163` revenue/EBITDA fallback
**What it is:** a hardcoded '€65,000M' / '€14,300M' pair that fires if `revenue_str` or `ebitda_str` resolve to 'N/A'.

**Currently dormant:** the bundle returns populated values.

### 5.6 — `main.py:714` swap pre-hedge fallback
**What it is:** a hardcoded action string mentioning "paired with a €500M swap pre-hedge overlay" for the GREEN_ESG family. Fires only when current_action is empty.

**Currently dormant:** Enel's curated narrative is populated.

### 5.7 — `_FAMILY_KEYWORD_WEIGHTS` (Flavor 2)

**Location:** ``main.py` near `BRAND_PROFILES`` (near `_CREDIT_RATINGS`), ``pitchbook_builder.py` near the module logger`.

**What it is:** a weighted vocabulary for product family classification. **This is a taxonomy definition, not a per-client exception** — it scales to new clients without modification.

**Sync invariant:** the two copies must remain byte-identical. See `master_persona_20Sep_WeightedFamily.md` §7.11.

### 5.8 — `ensure_ascii=False` in Copilot serialization (Flavor 2)

**Location:** `main.py` `copilot_chat_endpoint`.

**What it is:** the two `json.dumps` calls that serialize `baseline_deck_slides` and `active_deck_slides` into the Copilot prompt use `ensure_ascii=False`. This is a deliberate override of Python's default ASCII-safe serialization so that UTF-8 characters (notably `€`) reach the LLM as real characters rather than JSON escapes. Without it, the Copilot occasionally echoed `\u20ac` in replies for Slide 3.

### 5.9 — `BRAND_PROFILES` dict (branding branch)

**Location:** `main.py` (after the module logger, before the FastAPI app).

**What it is:** a curated dict of **27 keys per brand**, one entry per deployment target (`ING`, `BFS_AI_LAB`, `ACME_FINANCIAL`). Keys cover display strings, logo filenames and heights, footer and attribution text, houseview fallbacks, RSS URL, colour palette (accent, hover, light, navy, badge), five LLM persona strings, and download filename prefixes.

**Why it exists:** the platform renders under three brands from a single codebase. The profile is the single source of brand truth.

**Sync consideration:** `BRAND_PROFILES` lives only in `main.py`. `pitchbook_builder.py` holds a module-level slot (`_ACTIVE_BRAND`) that `main.py` fills via `_set_active_brand()` immediately before each `build_pitchbook()` call. There is no duplicate dict to keep in sync — unlike `_CREDIT_RATINGS` (§5.1) and `_FAMILY_KEYWORD_WEIGHTS` (§5.7).

**Key parity invariant (23 Sep 2026):** all three brands in `BRAND_PROFILES` must carry the **identical 27-key set**. This is verified programmatically as part of the pre-deploy checklist. Adding a brand via `tools/onboard_brand.py` guarantees parity — the utility refuses to patch if the produced entry diverges from the schema.

**Selection:** `os.getenv("BRAND", "ING").upper()`. Unrecognized values log a warning and fall back to ING.

**Onboarding:** adding a fourth brand is a one-command operation. See `BRAND_ONBOARDING_GUIDE.md`.

Full specification: `Brand_Toggle_Implementation.md` §3 and §11.


### 5.10 — `ADJACENT_OPPORTUNITY_FALLBACKS` (23 Sep 2026)

**Location:** `main.py` near `PRIMARY_TRIGGER_FALLBACKS` (both defined together, near `_FAMILY_KEYWORD_WEIGHTS`).

**What it is:** a curated dict of fallback paragraphs for the `adjacent_opportunities` synthesis output. Keyed by client ID and by family. Consulted only when the validator rejects the LLM output.

**Keys:**

- `CLI101` — Enel S.p.A. curated paragraph (EUR 12bn authorization window, interest-rate risk review, USD FX exposure)
- `CLI103` — BASF SE curated paragraph (fixed-coverage trajectory, refinancing calendar, green-feature evaluation)
- `_GREEN_ESG`, `_DCM_REFI`, `_RATES_HEDGE`, `_FX_HEDGE` — generic per-family paragraphs
- `_FALLBACK` — last-resort paragraph used when neither client nor family matches

**Why it exists:** the LLM occasionally returned an empty `adjacent_opportunities` string despite the prompt asking for 80-140 words. Prior behaviour cached the empty value for the full 900s TTL, silently degrading Slide 3 and the Copilot's conditional fourth section. The validator runs before the cache write so the cache never holds an empty value.

**Not fabrication:** the fallback is a human-written, defensible, deterministic substitute — same class of exception as `PRIMARY_TRIGGER_FALLBACKS` (§5.10 in `MASTER_PERSONA_23Sep2026.md`, if separately numbered). Not an invented value from the LLM. No DB write.

**Future:** if the desk wants per-client curated adjacent paragraphs as part of the anchor, a `ca_opportunity_scoring.adjacent_opportunities_nlg` column could be added (requires unlocking DDL). Until then, the fallback dict is the canonical substitute.

Full specification: `MASTER_PERSONA_23Sep2026.md` §5 and §13; `Brand_Toggle_Implementation.md` §11.7.

## 6. Changelog — 20 Sep 2026 (Flavor 2 — Weighted-Family + Adjacencies)

Changes since the Flavor 1 (Baseline) version. Flavor 1 is documented separately at `Docs/SYSTEM_ARCHITECTURE_&_DATA_CONTRACT_GUARDRAIL.md`.

### Added

- **§3 Tier 2 updated** — cache is 8-tuple; the two new fields (`family`, `adjacent_opportunities`) travel through the cache.
- **§4 write-back rule clarified** — `family` and `adjacent_opportunities` are not persisted to the DB.
- **§5.7 expanded** — `_FAMILY_KEYWORD_WEIGHTS` sync invariant.
- **§5.8 added** — `ensure_ascii=False` exception in Copilot serialization.

### Common with Flavor 1

Everything else: schema, slide contract, 3-tier resolution, parity audit, exceptions 5.1–5.6.

---

## 6a. Changelog — 21 Sep 2026 (Runtime Brand Toggle)

Changes on the `feat/bfs-ai-lab-brand-toggle` branch. The Flavor 2 demo branch does not carry these changes.

### Added

- **§4 read-path brand substitution invariant** — `_brand_substitute` scope, word boundary, no-op for ING, emails untouched
- **§5.9 `BRAND_PROFILES` dict** — the branding exception, its 28-key profile, and the module-level slot design that avoids a third sync invariant
- **Header** — branding branch reference

### Updated

- **§5 preamble** — "Seven exceptions" → "Eight exceptions"
- **Line-number references** — `_CREDIT_RATINGS` and `_FAMILY_KEYWORD_WEIGHTS` now use function anchors; other references refreshed after the branding patch shifted code positions

### No change to

- Database schema (§1) — no new columns, no DDL
- Slide-by-slide contract (§2)
- 3-tier resolution hierarchy (§3)
- Cache/DB consistency invariant (§4)
- Exceptions 5.1–5.8
- 13-gate parity audit

---

## 6b. Changelog — 23 Sep 2026 (Three-brand + Adjacent Validator)

Changes on the working line `feat/adjacent-opportunities-fallback` (formerly `feat/complete-working-acme-financial`, formerly `feat/bfs-ai-lab-brand-toggle`). Both Flavor 2 demo branch and the branding branch are ancestors; this section records the state as of 23 September 2026.

### Added

- **§5.10 `ADJACENT_OPPORTUNITY_FALLBACKS`** — a curated dict of fallback paragraphs for the `adjacent_opportunities` field, mirroring the `primary_trigger` fallback pattern. Per-client (`CLI101` Enel, `CLI103` BASF), per-family (prefixed `_GREEN_ESG`, `_DCM_REFI`, `_RATES_HEDGE`, `_FX_HEDGE`), plus `_FALLBACK` last-resort. Consulted only when the validator rejects the LLM output.
- **`_validate_adjacent_opportunities()`** — deterministic three-rule check: non-empty, ≥ 100 chars, ≥ 40 words. Returns `(is_valid, reason)`.
- **`_resolve_adjacent_opportunities()`** — applies the validator; substitutes the fallback on rejection; logs the failed rule. Returns `(final_text, source)` where `source` is `"llm"` or `"fallback"`.
- **New API response field `adjacent_opportunities_source`** — one of `"llm"`, `"fallback"`, or `"error"`. Metadata only; no UI or deck consumer yet. Enables observability of how often the fallback fires.

### Updated

- **§3 Tier 2 cache shape** — `_MANDATE_SYNTH_CACHE` extended from **9 elements to 10**. The new tenth element carries `adjacent_opportunities_source`. Old cached entries remain readable via the existing `len() > 9` guard, which defaults the source to `"fallback"`. Rolling deploys do not break in-flight cached entries.
- **§4 `adjacent_opportunities` invariant** — the value that enters the cache is now guaranteed non-empty. The validator runs in `synthesize_mandate_catalyst` **before** the cache write, so cached values are always the resolved value (LLM output that passed, or a curated fallback).
- **§5 preamble** — "Eight exceptions" → **"Nine exceptions"** (adds §5.10).
- **§5.9 `BRAND_PROFILES`** — key count corrected from **28 to 27**; extended from **two brands to three** (`ING`, `BFS_AI_LAB`, `ACME_FINANCIAL`); key parity invariant added (all three brands must carry the identical 27-key set, verified programmatically at `MASTER_PERSONA_23Sep2026.md` §10 step 7).
- **§2 Slide 3 contract** — the Adjacent Opportunities card is now guaranteed populated. Prior behaviour: on a cold cache or an empty LLM return, Slide 3 rendered the placeholder string *"Additional origination angles will appear here once the mandate synthesis identifies any."* New behaviour: `_resolve_adjacent_opportunities` substitutes the per-client or per-family fallback before caching, so the card always shows a substantive paragraph.

### Bug fix (same commit, same code path)

- **`_client_id_for_fallback` was set to `str(client_name)`** — a display name like `"Enel S.p.A."` — rather than the client ID. Since `PRIMARY_TRIGGER_FALLBACKS` and `ADJACENT_OPPORTUNITY_FALLBACKS` are keyed by `CLI101` / `CLI103`, the per-client branch never fired; the code always fell through to the per-family entry. Corrected to use `client_id`, passed through from the call site as `cid_str`.

### Cross-references

- Full fix details: `MASTER_PERSONA_23Sep2026.md` §13 (changelog) and §5 (component map)
- Brand extension record: `Brand_Toggle_Implementation.md` §11
- Onboarding utility: `BRAND_ONBOARDING_GUIDE.md`

---

*End of document.*