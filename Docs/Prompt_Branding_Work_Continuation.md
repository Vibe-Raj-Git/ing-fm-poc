## Branding Work Continuation Prompt

**Copy everything below the line into a new session.**

---

**Context:** I'm continuing work on the ING Financial Markets Deal Intelligence Platform. In a previous session, we designed a **runtime brand toggle** so the same codebase deploys as two Cloud Run services — one ING-branded, one BFS AI Lab-branded. No code fork. No separate database. Same Docker image, different environment variable.

## Orientation Checklist (Read In This Order)

1. `Docs/master_persona_18Sep.md` — full architectural context
2. `README.md` (repo root) — branch structure and checkout procedure
3. `main.py`, `pitchbook_builder.py`, `frontend/src/App.jsx` — the three files to modify
4. This prompt — the branding work design and constraints

Once oriented, run the preflight greps and wait for user confirmation before writing any code.

**Current state of the codebase:**

| Attribute | Value |
|---|---|
| Branch | `feat/dulcet-reset-pristine-semantic-dedup-all-UI-RM-HV-Slide2_LLM_Summary_Slide3_WhyNow_Action_17-Sep` |
| Latest commit | `a74a4ad` (master persona 18Sep + archive 14Sep) |
| Working tree | clean |
| Repository location | `~/ing-fm-poc` |
| GitHub | `Vibe-Raj-Git/ing-fm-poc` |
| `main` branch | intentionally stale at Aug 30 state — historical reference only, do not update |
| Docs | `Docs/` — start with `master_persona_18Sep.md` |
| README | repo root — documents clone-and-checkout procedure for a fresh clone |

**Architecture of the branding feature:**

```
                 ┌──────────────────────────────────────────┐
                 │  Shared codebase (one branch, one image) │
                 │  Reads BRAND env var at runtime          │
                 └────────────────┬─────────────────────────┘
                                  │
              ┌───────────────────┴───────────────────────┐
              │                                           │
              ▼                                           ▼
   ┌──────────────────────┐                  ┌────────────────────────┐
   │  ing-fm-poc-service  │                  │  bfs-ai-lab-service    │
   │  BRAND=ING (default) │                  │  BRAND=BFS_AI_LAB      │
   │  (existing, live)    │                  │  (new)                 │
   └──────────┬───────────┘                  └──────────┬─────────────┘
              │                                         │
              └────────────────┬────────────────────────┘
                               ▼
                 ┌─────────────────────────────────┐
                 │  Cloud SQL (shared DB)          │
                 │  Content NOT neutralized        │
                 │  Substituted at read time       │
                 └─────────────────────────────────┘
```

**Design decisions already made:**

1. **Brand config lives in `main.py`** — a `BRAND_PROFILES` dict with entries for `"ING"` and `"BFS_AI_LAB"`. Each profile contains:

   - `name` — short name (e.g., "ING", "BFS AI Lab")
   - `full_name` — full display (e.g., "ING Wholesale Banking", "BFS AI Lab")
   - `copilot_name` — chat panel header (e.g., "ING Copilot", "BFS AI Lab Copilot")
   - `logo_white` — filename for dark backgrounds
   - `logo_orange` — filename for light backgrounds
   - `footer` — slide footer text
   - `prompt_org` — organization name injected into LLM personas (server-side only, not exposed)
   - `download_prefix` — filename prefix for downloaded decks (server-side only)
   - `houseview_default_source` — fallback chip label for houseview
   - `houseview_fallback` — fallback text when no houseview exists
   - `attribution` — "X Desk Research & Market Intelligence" string
   - `pillar_fx` — FX pillar text
   - `pillar_spo` — SPO pillar text

   A module-level `ACTIVE_BRAND = os.getenv("BRAND", "ING").upper()` selects the profile. If the value is unrecognized, **log a warning** and fall back to ING — do not fail silently. See the note about the `ctx` bug below for why logging matters.

2. **A new `GET /api/brand` endpoint** returns the active brand's profile for the frontend to consume. It excludes `prompt_org` and `download_prefix` — those are server-side only and should not leak to the browser.

3. **Frontend fetches the brand on mount** and threads it through React state (React Context or simple state at the top level of the app). All hardcoded ING strings in `App.jsx` get replaced with values from the brand object. Until the fetch completes, render nothing or a minimal placeholder — do not show ING-branded content and then swap it.

4. **`pitchbook_builder.py` reads the brand from the overrides payload**, passed by `POST /api/pitchbook/generate`. The frontend already fetches the brand; `handleDownloadDeck` includes it in the `overrides` object; the PPTX builder reads `ov.get("brand", {...fallback to ING...})`. Then `add_logo()`, `add_footer()`, and the pillar texts read from that brand profile.

5. **DB content is NOT neutralized.** Instead, the read paths apply a runtime substitution wherever DB-sourced text might contain "ING". The scope:

   - `hv_doc_title` (houseview chip source)
   - `hv_doc_summary` (houseview body)
   - `news_headline` (Live Verified News)
   - `cf_description` (Desk Signal)
   - `cf_latent` / `cf_latent_list` (latent opportunities)
   - any chunk `text_content` that reaches the UI
   
   The substitution is `re.sub(r'\bING\b', BRAND["name"], text)` — word-boundary, so "DOING", "USING", "PROVIDING" aren't touched. For the ING service this is a no-op (`BRAND["name"] == "ING"`). For the BFS AI Lab service, "ING Chemicals Sector Strategy" becomes "BFS AI Lab Chemicals Sector Strategy".
   
   **Do not substitute raw SQL** — do it in Python after the row is fetched, so both services read the same DB rows and transform on the way out. This keeps the DB as the single source of truth and avoids UPDATE statements.
   
   **Email addresses** like `@ing.com` in ingested content need a different treatment because the word-boundary regex would produce `@BFS AI Lab.com` (with a space). Handle these as a separate substitution: `re.sub(r'@ing\.', '@bfsailab.', text)` or leave them alone depending on visibility.

6. **Logging for fallbacks.** If `BRAND` env var is unrecognized → log a warning naming the invalid value and the valid options, then fall back to ING. If a logo file is missing → log a warning before falling back to text rendering.

**Key files that need changes:**

Run the greps to confirm the inventory is current. As of the 18Sep commit:

- **`main.py`** — approximately 8 ING references. Includes: FastAPI title, mandate synthesis prompt persona, compliance prompt persona, Copilot system instruction persona, houseview fallback strings, RSS fallback URLs (`think.ing.com`), download filename prefix. There's also a "status": "INGESTED_AND_EVALUATED" string — leave it alone, it's an API status value, not branding.

- **`pitchbook_builder.py`** — approximately 6 visible ING references: logo file paths in `add_logo()`, fallback text "ING" when the logo is missing, footer string, FX pillar text, SPO pillar text. **The color constants `ING_NAVY`, `ING_ORANGE`, `ING_DARK_SLATE`, `ING_WHITE`, `ING_LIGHT_ORANGE` stay named as-is.** They're internal identifiers and renaming them is out of scope — we did not pursue a code identifier rename.

- **`frontend/src/App.jsx`** — approximately 30 ING references. Logo image `src` and `alt` attributes at many lines, footers at each of the 9 slide positions, header badges, Copilot labels, download filename, loading text, houseview strings, pillar texts, roadmap text, chat greeting.

**BFS AI Lab logo files:**

- `assets/bfs_ai_lab_white.png` — for dark backgrounds (same dimensions as `ing_logo_white.png`)
- `assets/bfs_ai_lab_orange.png` — for light backgrounds (same dimensions as `ing_logo_orange.png`)
- Also add to `frontend/public/assets/` if the frontend serves from there (check with `ls frontend/public/assets/` before Diff 3)
- **Status:** the user will provide these at deployment time. The code references them regardless, and the fallback-to-text path handles their absence with a log warning.

**What we haven't done yet:**

- No code changes for the branding feature have been written or applied
- The DB has not been touched
- The logo files are not yet in place
- The BFS AI Lab Cloud Run service has not been deployed

**What I want to do next:**

Produce the diffs for the branding feature, **one file at a time**, in the same file-based Python patch script pattern we've used successfully before (write to `/tmp/diff_*.py`, verify with `python3 -c "import ast; ast.parse(...)"`, then execute). The order:

1. **Diff 1** — `main.py`: `BRAND_PROFILES` dict + `/api/brand` endpoint + string replacements + read-path substitution in `/api/opportunities`
2. **Diff 2** — `pitchbook_builder.py`: brand reads + logo path + footer + pillar updates
3. **Diff 3** — `App.jsx`: brand fetch + ~30 string replacements
4. **Diff 4** — logo file additions (user provides the files)
5. **Diff 5** — test plan (local with `BRAND=ING` and `BRAND=BFS_AI_LAB`)
6. **Diff 6** — deploy plan (existing `ing-fm-poc-service` explicitly set to `BRAND=ING` for safety; new `bfs-ai-lab-service` created with `BRAND=BFS_AI_LAB`)

**Disciplines to maintain (from master_persona_18Sep.md §1, §9):**

- **Do not modify `main` branch.** Work on the feature branch.
- **Do not fork the project.** Do not create `/home/user/bfs-ai-lab-fm-poc`. This is a runtime toggle, not a code fork.
- **Do not modify DB content unless absolutely necessary.** Prefer read-time substitution.
- **Do not use regex scripts to modify code.** Use the surgical file-based patch pattern (write to `/tmp/`, verify with `ast.parse`, then run). A prior regex-based script corrupted `main.py` and required a full recovery.
- **Every change is verified with grep immediately after applying.**
- **Test between steps.** Never apply two diffs without verifying the first.
- **Commit and push** when a logical unit is complete.

**Known constraint:** the current ING service on Cloud Run must not be disturbed by these changes. The backward-compatible default (`BRAND=ING` if unset) ensures this. When we redeploy the ING service after the code change, we should explicitly set `BRAND=ING` in the environment variables, so the intent is recorded in the service definition rather than relying on the default.

**Background from earlier sessions:**

- **The `ctx` bug.** A prior bug existed where `synthesize_mandate_catalyst` referenced `ctx.get('opportunity_type', '')` — but `ctx` was never a parameter of that function. The line was inside a `try/except`, and the `NameError` was silently caught. The code fell back to static text, and the LLM synthesis never ran. The UI showed generic placeholder text even after cache clears. The fix replaced the buggy reference with local variables: `p_fam_upper` and `combined_context`, computed from the function's own parameters `product_family` and `latent_str`. The fix is present in `main.py` around line 587-598.
  
  **Lesson for branding:** any brand lookup that fails (unrecognized `BRAND`, missing logo file) must **log a warning**, not fall back silently. Silent fallbacks hide errors.

- **The reset-to-pristine mechanism.** `POST /api/system/reset-baseline` reads `baseline_snapshots.json` and restores pristine rows non-destructively. The brand changes must not break the reset endpoint. In particular, if the read-path substitution changes what `/api/opportunities` returns, the reset endpoint is unaffected (it only writes to the DB, doesn't read the transformed API output). But verify the reset still works after the branding changes.

- **Slides 2 and 3 have DB-driven content.**
  - Slide 2's "Window of Opportunity" and "Recommended Action" cards read from `why_now_summary` and `action_summary` (LLM-generated, max 160 chars).
  - Slide 2's "Primary Market Trigger" reads `ctx.trigger_source` from the DB.
  - Slide 3 has four pillars plus two narrative cards reading `why_now` and `action` (full 2-sentence narratives).
  
  The branding changes must not break these. If the read-path substitution affects `why_now` / `action` / `why_now_summary` / `action_summary`, verify it doesn't mangle the LLM output. (It shouldn't — those strings rarely contain "ING" as a standalone word, but check anyway.)

- **BASF (CLI103) is a test fixture, not a second demo.** During the 17-18 Sep workstream, BASF was used to verify the reset shield icon and the LLM semantic deduplication — both destructive-looking features. Enel (CLI101) is the primary demo client. When testing the brand toggle, either client works; BASF remains a safe target for destructive testing.

**Before writing any code, I want you to:**

1. **Confirm you've read the three code files and `Docs/master_persona_18Sep.md`.**
2. **Re-run the ING occurrence greps** to verify the inventory is still accurate against the current file contents. Report anything that's changed since the 18Sep commit.
3. **Report the preflight state:** current branch name, latest commit, working tree status, whether the two BFS AI Lab logo files exist in `assets/` and `frontend/public/assets/`.
4. **Wait for my confirmation** that the scope is correct before writing Diff 1.

**Start by orienting, then wait.** Do not write any code until I confirm.

Let me know when you're oriented and ready.

---

## How To Use This Prompt

1. **Start a fresh session** when you're ready to resume the branding work.
2. **Paste the prompt above** as your first message.
3. **Attach or paste** the three files — `main.py`, `pitchbook_builder.py`, `frontend/src/App.jsx`.
4. **Attach or paste** `Docs/master_persona_18Sep.md` — the master context.

The prompt is self-contained. A fresh session reading it will know the state, the design, the constraints, and the exact sequence.

## What Changed From The Earlier Version

| Item | Old | New |
|---|---|---|
| Master doc reference | `master_persona_14Sep.md` | `master_persona_18Sep.md` |
| Latest commit | `e13837c` | `a74a4ad` |
| Working pattern | Implicit | Explicitly referenced from §1 of the master persona |
| `ctx` bug description | Brief | Full explanation with line reference and lesson |
| BASF role | Not mentioned | Explicitly noted as test fixture, not demo |
| Read-path substitution scope | Vague | Enumerated list of fields, with email address exception |
| `INGESTED_AND_EVALUATED` status | Not addressed | Explicitly flagged as "leave alone" |
| Color constant rename | Mentioned as "stay as-is per user decision" | Confirmed out of scope |
| Brand fetch on frontend | "Thread through React state" | Explicit guidance: don't render ING-branded content before the fetch completes |
| Logo file preflight | Implied | Explicit: report whether files exist before Diff 1 |
| Deploy plan | Explicit `BRAND=ING` for the existing service | Same, plus rationale: record the intent in the service definition |

## Session Close

Save the updated prompt alongside the earlier version. When you resume the branding work, paste the updated prompt plus the master persona plus the three code files. The next session will orient correctly and wait for your confirmation before writing any code.

The codebase is committed and pushed at `a74a4ad`. Nothing is pending. Walk away whenever you're ready.