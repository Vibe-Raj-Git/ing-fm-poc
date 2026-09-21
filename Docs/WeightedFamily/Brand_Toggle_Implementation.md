# Brand Toggle — Implementation Record

**Version:** 21 September 2026
**Status:** Delivered and verified
**Flavor:** Weighted-Family + Adjacencies (Flavor 2)
**Branch:** `feat/bfs-ai-lab-brand-toggle`
**Tags:** `ing-baseline-pre-branding`, `branding-working-pre-color`, `branding-complete-enel-only`
**Predecessor:** `Docs/Prompt_Branding_Work_Continuation.md` — the design brief from before implementation

This document records what was built. The predecessor described what we intended; this describes what shipped, with the actual values, key names, and known deviations from the original design.

---

## 1. What Was Delivered

A **runtime brand toggle** for the ING Financial Markets Deal Intelligence Platform. The same codebase — one branch, one Docker image, one PostgreSQL database — deploys as two independent Cloud Run services that render different brands. The toggle is an environment variable, not a UI control, not a code fork.

| Service | URL | Env var | Renders |
|---|---|---|---|
| `ing-fm-poc-service` | `ing-fm-poc-service-482846129838.europe-west1.run.app` | `BRAND=ING` | ING branding — orange accent, ING logos, "ING Copilot" |
| `bfs-ai-lab-service` | `bfs-ai-lab-service-482846129838.europe-west1.run.app` | `BRAND=BFS_AI_LAB` | BFS AI Lab branding — turquoise accent, Cognizant BFS AI Lab logos, "BFS AI Lab Copilot" |

Both services share the same Cloud SQL instance and read the same rows. Brand-specific text is substituted at read time on the way out of the API — the DB content is never neutralised or duplicated.

**Verification status:** both services deployed, visually verified in browser, deck generation confirmed end-to-end on both, `test_parity.py` passes 13/13 with `BRAND` unset (the ING path is byte-identical in behaviour to before the toggle was added).

**Default safety:** when `BRAND` is unset, the code selects the ING profile. Redeploying the existing ING service without any env var change produces zero visible difference.

---

## 2. Architecture

```
                 ┌──────────────────────────────────────────────┐
                 │  Single codebase · single Docker image       │
                 │  Brand selected at startup via BRAND env var │
                 └────────────────────┬─────────────────────────┘
                                      │
              ┌───────────────────────┴────────────────────────┐
              │                                                │
              ▼                                                ▼
   ┌────────────────────────┐                   ┌──────────────────────────┐
   │  ing-fm-poc-service    │                   │  bfs-ai-lab-service      │
   │  BRAND=ING (default)   │                   │  BRAND=BFS_AI_LAB        │
   │  revision 00099+       │                   │  revision 00001+         │
   └───────────┬────────────┘                   └───────────┬──────────────┘
               │                                            │
               │      same Cloud SQL instance               │
               │      same ca.* tables                      │
               └────────────────────┬───────────────────────┘
                                    ▼
                 ┌──────────────────────────────────────────────┐
                 │  Cloud SQL (PostgreSQL 15 + pgvector)        │
                 │  Content NOT neutralised                     │
                 │  Brand substitution applied on the read path │
                 └──────────────────────────────────────────────┘
```

### Request-time flow

```
Browser → /api/brand           → returns active brand profile (colors, names, logos, title)
Browser → /api/opportunities   → reads DB, applies _brand_substitute to 10 text fields,
                                  returns client records (no brand field in the response)
Browser → /api/pitchbook/*     → main.py calls pitchbook_builder._set_active_brand(ACTIVE_BRAND)
                                  before build_pitchbook; deck renders with active brand colors,
                                  logo, footer, pillar text, and dynamic cover-slide positions
```

### Two shell aliases, one image

```bash
deploy-poc   → ing-fm-poc-service    with BRAND=ING
deploy-bfs   → bfs-ai-lab-service    with BRAND=BFS_AI_LAB
```

Both run the same `gcloud run deploy --source .` — same Dockerfile, same Cloud Build, same output image. The only differences are the service name and the `BRAND` value in `--set-env-vars`.

### Related documentation

| Doc | Purpose |
|---|---|
| `Docs/Prompt_Branding_Work_Continuation.md` | The original design brief — what we intended |
| `Docs/WeightedFamily/master_persona_20Sep_WeightedFamily.md` | Full architectural context; §2.1 Flavor Differential |
| `Docs/WeightedFamily/SYSTEM_ARCHITECTURE_&_DATA_CONTRACT_GUARDRAIL_20Sep_WeightedFamily.md` | Schema, slide contract, 3-tier resolution, exceptions |

---

## 3. Brand Profile

Both brands are described by a single `BRAND_PROFILES` dict in `main.py`, defined immediately after the module logger. Each profile is a flat dict with the same key set.

### 3.1 Full key list

| Key | Type | Purpose | Server-only? |
|---|---|---|---|
| `name` | str | Short display name ("ING", "BFS AI Lab") | No |
| `full_name` | str | Full display name ("ING Wholesale Banking", "BFS AI Lab") | No |
| `copilot_name` | str | Copilot panel header ("ING Copilot", "BFS AI Lab Copilot") | No |
| `logo_white` | str | Logo filename for dark backgrounds | No |
| `logo_orange` | str | Logo filename for light backgrounds | No |
| `footer` | str | Slide footer text | No |
| `attribution` | str | "X Desk Research & Market Intelligence" | No |
| `api_title` | str | FastAPI `title=` metadata | No |
| `download_prefix` | str | Long prefix (unused in final implementation) | Yes |
| `download_prefix_short` | str | Deck filename prefix ("ING", "BFS_AI_LAB") | Yes |
| `houseview_default_source` | str | Houseview chip label fallback | No |
| `houseview_fallback` | str | Houseview body fallback | No |
| `rss_fallback_url` | str | RSS fallback link | No |
| `logo_height_inches` | float | Deck logo render height (0.45 / 0.60) | No |
| `accent_color` | hex str | Primary accent (badges, buttons, spinners) | No |
| `accent_color_hover` | hex str | Accent hover state | No |
| `accent_color_hover_alt` | hex str | Secondary hover variant | No |
| `accent_color_light` | hex str | Deck-side light tint | No |
| `accent_color_tint` | hex str | Frontend-side light tint | No |
| `navy_color` | hex str | Dark background / heading color | No |
| `navy_color_hover` | hex str | Navy hover state | No |
| `badge_color` | hex str | Header badge background | No |
| `prompt_capital_markets_persona` | str | Synthesis LLM persona line | Yes |
| `prompt_proposal_ref` | str | Synthesis prompt proposal reference | Yes |
| `prompt_compliance_persona` | str | Compliance LLM persona line | Yes |
| `prompt_copilot_persona_prefix` | str | Copilot system instruction prefix (ends at "for") | Yes |
| `prompt_adjacent_phrase` | str | Mid-clause in the Copilot adjacent prompt | Yes |

**Server-only keys** are filtered out of the `/api/brand` response. They never reach the browser.

### 3.2 ING profile

```python
"ING": {
    "name": "ING",
    "full_name": "ING Wholesale Banking",
    "copilot_name": "ING Copilot",
    "logo_white": "ing_logo_white.png",
    "logo_orange": "ing_logo_orange.png",
    "footer": "ING Wholesale Banking • Strictly Confidential",
    "attribution": "ING Desk Research & Market Intelligence",
    "api_title": "ING FM Insights API",
    "download_prefix": "ING_FM",
    "download_prefix_short": "ING",
    "houseview_default_source": "ING FM Research",
    "houseview_fallback": "No ING houseview published for this client in the current reporting cycle.",
    "rss_fallback_url": "https://think.ing.com",
    "logo_height_inches": 0.45,
    "accent_color": "#FF6200",
    "accent_color_hover": "#E05500",
    "accent_color_hover_alt": "#E55800",
    "accent_color_light": "#FFF0E6",
    "accent_color_tint": "#FFF0E6",
    "navy_color": "#000066",
    "navy_color_hover": "#1A224D",
    "badge_color": "#FF6200",
    "prompt_capital_markets_persona": "You are an Executive Director in ING Wholesale Banking Capital Markets & Advisory.",
    "prompt_proposal_ref": "The following is ING's current proposal.",
    "prompt_compliance_persona": "You are the Senior Executive Director of EU Financial Regulatory Compliance at ING Wholesale Banking.",
    "prompt_copilot_persona_prefix": "You are the senior ING Financial Markets Origination, Structuring & Regulatory Compliance Copilot for",
    "prompt_adjacent_phrase": "ING has identified",
}
```

### 3.3 BFS AI Lab profile

```python
"BFS_AI_LAB": {
    "name": "BFS AI Lab",
    "full_name": "BFS AI Lab",
    "copilot_name": "BFS AI Lab Copilot",
    "logo_white": "bfs_ai_lab_logo_white.png",
    "logo_orange": "bfs_ai_lab_logo_orange.png",
    "footer": "BFS AI Lab • Strictly Confidential",
    "attribution": "BFS AI Lab Desk Research & Market Intelligence",
    "api_title": "BFS AI Lab FM Insights API",
    "download_prefix": "BFS_AI_LAB",
    "download_prefix_short": "BFS_AI_LAB",
    "houseview_default_source": "BFS AI Lab Research",
    "houseview_fallback": "No BFS AI Lab houseview published for this client in the current reporting cycle.",
    "rss_fallback_url": "https://think.ing.com",
    "logo_height_inches": 0.60,
    "accent_color": "#10C4C0",
    "accent_color_hover": "#0BA8A4",
    "accent_color_hover_alt": "#0D9E9A",
    "accent_color_light": "#DCF5F4",
    "accent_color_tint": "#DCF5F4",
    "navy_color": "#0A3168",
    "navy_color_hover": "#153F7A",
    "badge_color": "#0A3168",
    "prompt_capital_markets_persona": "You are an Executive Director in Capital Markets & Advisory.",
    "prompt_proposal_ref": "The following is the current proposal.",
    "prompt_compliance_persona": "You are the Senior Executive Director of EU Financial Regulatory Compliance.",
    "prompt_copilot_persona_prefix": "You are the senior Financial Markets Origination, Structuring & Regulatory Compliance Copilot for",
    "prompt_adjacent_phrase": "identified",
}
```

### 3.4 Color provenance

The BFS AI Lab turquoise and navy were **extracted from the logo PNG** on 21 September 2026 by counting non-white opaque pixels. Top colors by pixel frequency:

| Color | Cluster | Role |
|---|---|---|
| `#093268` / `#0A3168` | Navy — the Cognizant wordmark and network strokes | `navy_color`, `badge_color` |
| `#10C3BF` / `#10C4C0` | Turquoise — the arrow, the mark's distinctive element | `accent_color` |

Hover and light variants were hand-derived:
- `accent_color_hover` = `#0BA8A4` (darker turquoise)
- `accent_color_hover_alt` = `#0D9E9A` (slightly darker still)
- `accent_color_light` / `accent_color_tint` = `#DCF5F4` (pale turquoise tint)
- `navy_color_hover` = `#153F7A` (lighter BFS navy)

**The badge uses `badge_color`, not `accent_color`.** Reason: turquoise + white text has low contrast. `badge_color` is `#0A3168` for BFS (navy, good contrast) and `#FF6200` for ING (orange, same as accent — ING's badge was always orange). This is a deliberate per-brand override, not a global rule.

### 3.5 Profile selection

```python
_raw_brand = os.getenv("BRAND", "ING").upper()
if _raw_brand not in BRAND_PROFILES:
    logger.warning(
        "Unrecognized BRAND='%s' — valid options: %s. Falling back to ING.",
        _raw_brand, list(BRAND_PROFILES.keys())
    )
    _raw_brand = "ING"
ACTIVE_BRAND = BRAND_PROFILES[_raw_brand]
logger.info("Active brand: %s", ACTIVE_BRAND["name"])
```

**Unrecognized `BRAND` values warn, then fall back to ING.** This is the lesson from the `ctx` bug (see §10) — silent fallbacks hide errors. Every brand-lookup failure logs.

## 4. Backend — `main.py`

### 4.1 Brand profile and selection

See §3. The dict and the selection logic live in `main.py` immediately after the module logger.

### 4.2 The `_brand_substitute` helper

```python
def _brand_substitute(text):
    """Word-boundary substitution of 'ING' with the active brand's display name.
    No-op when brand is ING. Email addresses (@ing.) are intentionally not touched."""
    if text is None or not isinstance(text, str):
        return text
    if ACTIVE_BRAND["name"] == "ING":
        return text
    return re.sub(r'\bING\b', ACTIVE_BRAND["name"], text)
```

**Three properties to note:**

1. **Early-returns for `None` and non-strings.** Protects against `NoneType` in the DB-read path (some columns can be NULL).
2. **Early-returns for ING.** No regex runs when the brand is ING — the ING path is byte-identical to pre-toggle behaviour. Zero risk of corruption.
3. **`\bING\b` word boundary.** Matches `ING` as a standalone token — not `DOING`, `USING`, `PROVIDING`, `INGESTED`. This is what makes the substitution safe on arbitrary DB text.

**Emails are intentionally not substituted.** `@ing.com` stays `@ing.com` under BFS. Rationale: an email address is a factual reference to a person at ING, not brand chrome. Substituting it would produce `@BFS AI Lab.com` (the word-boundary regex) or fabricate an email address that doesn't exist.

### 4.3 The `/api/brand` endpoint

```python
@app.get("/api/brand")
def get_brand():
    """Return the active brand profile for the frontend.
    Excludes server-side-only keys: prompt_* and download_prefix."""
    return {k: v for k, v in ACTIVE_BRAND.items() if not k.startswith("prompt_") and k != "download_prefix"}
```

Filters out:
- Any key starting with `prompt_` — the LLM persona strings
- `download_prefix` — the long form (the short form `download_prefix_short` **is** exposed; the frontend uses it for the download filename)

Everything else goes to the browser. The response is the single source of brand truth for the React app.

### 4.4 Read-path substitution in `/api/opportunities`

Ten text fields in the response dict are wrapped in `_brand_substitute` at the point they enter the `opps.append({...})` call:

| Field | Source | Notes |
|---|---|---|
| `why_now` | LLM synthesis (`final_why_now`) | Full narrative, slide 3 |
| `action` | LLM synthesis (`final_action`) | Full narrative, slide 3 |
| `why_now_summary` | LLM synthesis | Max 160 chars, slide 2 |
| `action_summary` | LLM synthesis | Max 160 chars, slide 2 |
| `adjacent_opportunities` | LLM synthesis (7th key) | 80-140 word paragraph, slide 3 |
| `cf_description` | DB (`cf_desc`) | Desk Signal from WorkFabric |
| `cf_latent` | DB (`cf_latent`) | Latent opportunity summary |
| `hv_doc_title` | DB (`hv_doc_title`) | Houseview chip |
| `hv_doc_summary` | DB (`hv_doc_summary`) | Houseview body |
| `news_headline` | DB (`news_headline`) | Live Verified News |

**The substitution happens in Python after the row is fetched.** Not in SQL. Both services read the same rows and transform on the way out. No `UPDATE` statements. No DB mutation.

**Fields that are NOT substituted:** numeric fields, IDs, dates, structured metadata, `family`, `score`. Those are brand-neutral by construction.

### 4.5 Prompt persona selection

Five persona strings are read from `ACTIVE_BRAND`, not hardcoded:

| Prompt site | Key | Usage |
|---|---|---|
| Mandate synthesis opening | `prompt_capital_markets_persona` | First line of the synthesis prompt |
| Mandate synthesis proposal reference | `prompt_proposal_ref` | "The following is X's current proposal" line |
| Compliance system prompt | `prompt_compliance_persona` | First line of the compliance audit prompt |
| Copilot system instruction | `prompt_copilot_persona_prefix` | The `You are the senior ... Copilot for` prefix — the f-string appends `{client_name} ({p_family})` |
| Copilot adjacent prompt | `prompt_adjacent_phrase` | Mid-clause inside the response architecture section |

**Why five separate keys, not one `prompt_org`?** Because the grammar doesn't survive a simple substitution. `"...at ING Wholesale Banking."` becomes `"...at BFS AI Lab."` — but `"...in ING Wholesale Banking Capital Markets & Advisory."` becomes `"...in BFS AI Lab Capital Markets & Advisory."` which reads awkwardly. The BFS grammar is `"...in Capital Markets & Advisory."` — the org name is dropped entirely, not replaced. Hand-written per-brand persona strings preserve natural phrasing.

### 4.6 Download filename

```python
clean_filename = f"{ACTIVE_BRAND['download_prefix_short']}_{str(client_name).replace(' ', '_')}_Pitchbook.pptx"
```

- ING service: `ING_Enel_S.p.A._Pitchbook.pptx` (unchanged from pre-toggle)
- BFS service: `BFS_AI_LAB_Enel_S.p.A._Pitchbook.pptx`

`download_prefix_short` exists separately from `download_prefix` so ING's filename format is preserved exactly — no `_FM` was injected.

### 4.7 Deck brand setter call

In `handle_pitchbook_generation`, immediately before `build_pitchbook`:

```python
import pitchbook_builder as _pb_brand
_pb_brand._set_active_brand(ACTIVE_BRAND)
pptx_buf = build_pitchbook(bundle, opp_meta, compliance_bullets=compliance_bullets, overrides=overrides)
```

This hands the active profile to the deck builder — see §5.

---

## 5. Deck Builder — `pitchbook_builder.py`

### 5.1 Module-level brand slot

```python
_ACTIVE_BRAND = None

def _set_active_brand(brand):
    """Called by main.py before build_pitchbook()."""
    global _ACTIVE_BRAND
    _ACTIVE_BRAND = brand

def _brand():
    """Return the active brand dict, or a minimal ING fallback if never set."""
    if _ACTIVE_BRAND is not None:
        return _ACTIVE_BRAND
    return {
        "name": "ING",
        "full_name": "ING Wholesale Banking",
        "logo_white": "ing_logo_white.png",
        "logo_orange": "ing_logo_orange.png",
        "footer": "ING Wholesale Banking • Strictly Confidential",
    }
```

**Why module-level state instead of threading `brand` through every function?**

`pitchbook_builder.py` is a library, not an app. Its public entry is `build_pitchbook()`. The brand is global to a single deck-build invocation — no scenario exists where one deck is half-ING, half-BFS. Module-level state matches that reality and avoids threading `brand` through 11 slide functions.

**Why no `BRAND_PROFILES` duplicate in `pitchbook_builder.py`?**

`main.py` is the single source of truth. `pitchbook_builder.py` holds a slot that `main.py` fills, not a copy of the dict. This avoids a third sync invariant alongside `_CREDIT_RATINGS` and `_FAMILY_KEYWORD_WEIGHTS`.

**Brand is NOT in the `overrides` payload.** Overrides carry user-mutable session state. Brand is deployment config — it doesn't belong in user-mutable state.

### 5.2 Color reassignment at build time

At the top of `build_pitchbook`:

```python
def _hex_to_rgb(hex_str):
    """Convert '#RRGGBB' to an (R, G, B) tuple."""
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def build_pitchbook(ctx, opp, compliance_bullets=None, overrides=None):
    global ING_ORANGE, ING_NAVY, ING_LIGHT_ORANGE
    _b = _brand()
    ING_ORANGE = RGBColor(*_hex_to_rgb(_b.get("accent_color", "#FF6200")))
    ING_NAVY = RGBColor(*_hex_to_rgb(_b.get("navy_color", "#000066")))
    ING_LIGHT_ORANGE = RGBColor(*_hex_to_rgb(_b.get("accent_color_light", "#FFEBDC")))
    ...
```

**What this does:** reassigns three module-level constants from the active brand's hex values at the start of every deck build. **All 29 existing usages of `ING_ORANGE`, `ING_NAVY`, and `ING_LIGHT_ORANGE` keep working** — they read the reassigned values without any call-site change.

**The `ING_*` names stay.** They're internal identifiers, not user-visible strings. Renaming them would touch 68+ lines and introduce zero visible change. Out of scope.

**`ING_WHITE`, `ING_DARK_SLATE`, `ING_LIGHT_ORANGE`** — the first two are neutral (white, near-black slate), not brand-specific. They're left alone. Only the three brand-tinted constants are reassigned.

### 5.3 Logo path, fallback text, footer, pillars

Four sites read from `_brand()` at draw time:

```python
# add_logo() — logo path
_b = _brand()
_logo_name = _b["logo_white"] if is_white else _b["logo_orange"]
logo_filename = os.path.join(base_dir, "assets", _logo_name)

# add_logo() — text fallback when the logo file is missing
p.text = _brand()["name"]

# add_footer() — footer text
p.text = _brand()["footer"]

# get_product_pillars() — FX pillar 3 body
f"Automated liquidity sourcing through {_brand()['name']} global FX electronic trading desk."

# get_product_pillars() — Green pillar 4 body
f"{_brand()['name']} leading SPO documentation, investor roadshow, and syndicate execution."
```

### 5.4 Dynamic logo height

```python
slide.shapes.add_picture(logo_filename, Inches(11.8), Inches(0.35), height=Inches(_brand().get("logo_height_inches", 0.45)))
```

- ING: 0.45" — same as pre-toggle
- BFS: 0.60" — larger, so the mark is legible given the logo file has more internal whitespace

### 5.5 Dynamic cover-slide text position

```python
add_logo(s1, is_white=True)
_logo_bottom = 0.35 + _brand().get("logo_height_inches", 0.45)
_desk_y = _logo_bottom + 0.05
tb_desk = s1.shapes.add_textbox(Inches(8.5), Inches(_desk_y), Inches(4.0), Inches(0.35))
```

The `Financial Markets Origination` label is positioned **below the logo bottom plus a 0.05" clearance**. ING: 0.85" (unchanged). BFS: 1.00" (moved down 0.15"). No overlap on either brand.

---

## 6. Frontend — `frontend/src/App.jsx`

### 6.1 Brand state and fetch

A `brand` state variable is declared alongside the other global state:

```jsx
const [brand, setBrand] = useState(null);
```

A fetch runs on mount:

```jsx
useEffect(() => {
  let cancelled = false;
  fetch("/api/brand")
    .then((r) => r.json())
    .then((data) => {
      if (!cancelled) {
        setBrand(data);
        document.documentElement.style.setProperty('--accent', data.accent_color);
        document.documentElement.style.setProperty('--accent-hover', data.accent_color_hover);
        document.documentElement.style.setProperty('--accent-hover-alt', data.accent_color_hover_alt);
        document.documentElement.style.setProperty('--accent-light', data.accent_color_tint);
        document.documentElement.style.setProperty('--navy', data.navy_color);
        document.documentElement.style.setProperty('--navy-hover', data.navy_color_hover);
        document.documentElement.style.setProperty('--badge', data.badge_color);
        document.title = `${data.name} Financial Markets Insights`;
      }
    })
    .catch((err) => {
      console.warn("Brand fetch failed, using ING fallback:", err);
      if (!cancelled) {
        setBrand(ING_FALLBACK);
        /* ...same seven setProperty calls with ING_FALLBACK values... */
        document.title = `${ING_FALLBACK.name} Financial Markets Insights`;
      }
    });
  return () => { cancelled = true; };
}, []);
```

**The seven CSS custom properties are set on `document.documentElement`** — the `<html>` element. Every Tailwind arbitrary-value class like `bg-[var(--accent)]` resolves through them.

**On fetch failure**, the frontend falls back to `ING_FALLBACK` — a hardcoded ING-shaped object with the same keys — and logs a warning. The app remains functional.

### 6.2 Loading gate

The app renders nothing until the brand fetch resolves:

```jsx
if (!brand || isLoading) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F8F9FA]">
      <div className="text-center">
        <div className="w-16 h-16 border-4 border-[var(--accent)] border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-gray-600 font-medium">Loading platform...</p>
      </div>
    </div>
  );
}
```

**Two things to note:**

1. **The gate checks `!brand` as well as `isLoading`** — the app waits for both.
2. **The loading text is brand-neutral** (`"Loading platform..."`) — this prevents a flash of ING-branded text before the BFS brand is known.

### 6.3 CSS variables and color replacements

Seven CSS variables set from the brand profile:

| Variable | ING value | BFS value |
|---|---|---|
| `--accent` | `#FF6200` | `#10C4C0` |
| `--accent-hover` | `#E05500` | `#0BA8A4` |
| `--accent-hover-alt` | `#E55800` | `#0D9E9A` |
| `--accent-light` | `#FFF0E6` | `#DCF5F4` |
| `--navy` | `#000066` | `#0A3168` |
| `--navy-hover` | `#1A224D` | `#153F7A` |
| `--badge` | `#FF6200` | `#0A3168` |

**130 hardcoded hex values across `App.jsx` were replaced with `var(--...)` references** via count-verified `str.replace()`:

| Original hex | Replacement | Count |
|---|---|---|
| `#FF6200` | `var(--accent)` | 71 |
| `#E05500` | `var(--accent-hover)` | 2 |
| `#E55800` | `var(--accent-hover-alt)` | 2 |
| `#FFF0E6` | `var(--accent-light)` | 4 |
| `#FFF9F5` | `var(--accent-light)` | 1 |
| `#FFE0CC` | `var(--accent-light)` | 1 |
| `#000066` | `var(--navy)` | 42 |
| `#1A224D` | `var(--navy-hover)` | 7 |

**Colors left alone:** `#0C112B` (7 uses — deck cover dark slate), all neutral grays (`#F8F9FA`, `#F8FAFC`, etc.), and `#4A154B` (Slack purple on a channel chip). These aren't brand-specific.

**The badge override.** After the global replace, the header badge used `bg-[var(--accent)]` (which resolves to turquoise under BFS). A targeted post-replace swapped it to `bg-[var(--badge)]` — navy under BFS, orange under ING — for white-text contrast.

### 6.4 String replacements

35 hardcoded ING strings replaced with `brand.*` reads:

| Group | Count | Example replacement |
|---|---|---|
| Logo `<img>` tags | 11 | `src="/assets/ing_logo_orange.png"` → `` src={`/assets/${brand.logo_orange}`} `` |
| Slide footers | 9 | `ING Wholesale Banking • Strictly Confidential` → `{brand.footer}` |
| Copilot names | 3 | `ING Copilot` → `{brand.copilot_name}` |
| Houseview labels | 5 | `ING FM Research` → `{brand.houseview_default_source}` |
| Pillar bodies | 2 | `"through ING global FX..."` → `` `through ${brand.name} global FX...` `` |
| Timeline | 1 | `"via ING FX desk"` → `` `via ${brand.name} FX desk` `` |
| Slide 11 heading | 1 | `ING` → `{brand.name}` |
| Badge | 1 | `ING` → `{brand.name}` |
| Slide 3 tooltip | 1 | `title="ING Wholesale Banking Research Desk..."` → `` title={`${brand.full_name} Research Desk...`} `` |
| Attribution | 1 | `📊 ING Desk Research & Market Intelligence` → `📊 {brand.attribution}` |

### 6.5 `ING_FALLBACK` constant

Defined at the top of `App.jsx`, after the imports. Mirrors the ING profile from `main.py` so the frontend can render ING-branded content even when `/api/brand` is unreachable. Contains: name, full_name, copilot_name, logo_white, logo_orange, footer, attribution, api_title, houseview_default_source, houseview_fallback, rss_fallback_url, download_prefix, download_prefix_short, seven color keys, logo_height_inches.

### 6.6 Download filename

```jsx
a.download = `${brand.download_prefix_short}_${clientId}_Pitchbook.pptx`;
```

The frontend **overrides** the server's `Content-Disposition` header — the browser uses the `download` attribute on the anchor element. Without this line, the browser would name the file per the server header (which is correct), but the frontend attribute always wins if present.

---

## 7. Deploy

### 7.1 Two shell aliases

Both defined in `~/.bashrc`. Same underlying `gcloud run deploy --source .` — the only differences are the service name and the `BRAND` value.

```bash
# ING service — deploy-poc
alias deploy-poc="cd ~/ing-fm-poc && gcloud run deploy ing-fm-poc-service \
  --source . \
  --project=\"dulcet-radar-508218-c5\" \
  --region=\"europe-west1\" \
  --set-env-vars=\"INSTANCE_CONNECTION_NAME=dulcet-radar-508218-c5:europe-west1:ing-postgres-db,DB_USER=postgres,DB_NAME=postgres,GCP_PROJECT=dulcet-radar-508218-c5,REGION=europe-west1,BRAND=ING\" \
  --set-secrets=\"DB_PASS=db-postgres-pass:latest\" \
  --quiet"

# BFS AI Lab service — deploy-bfs
alias deploy-bfs="cd ~/ing-fm-poc && gcloud run deploy bfs-ai-lab-service \
  --source . \
  --project=\"dulcet-radar-508218-c5\" \
  --region=\"europe-west1\" \
  --set-env-vars=\"INSTANCE_CONNECTION_NAME=dulcet-radar-508218-c5:europe-west1:ing-postgres-db,DB_USER=postgres,DB_NAME=postgres,GCP_PROJECT=dulcet-radar-508218-c5,REGION=europe-west1,BRAND=BFS_AI_LAB\" \
  --set-secrets=\"DB_PASS=db-postgres-pass:latest\" \
  --quiet"
```

**`BRAND=ING` is set explicitly on the ING service, not left to the default.** Reason: the intent is recorded in the Cloud Run service definition. If the default in code were ever changed, the ING service wouldn't silently shift brand.

### 7.2 Deploy order

Either service can be deployed independently. The two are decoupled — same image, different config.

```bash
deploy-poc && deploy-bfs    # both in one go
```

Each deploy takes 3-5 minutes. The image is built once per `gcloud run deploy --source .` invocation — the second deploy reuses the Cloud Build cache from the first, so it's usually faster.

### 7.3 Public access on the BFS service

**New Cloud Run services default to private.** The ING service was granted `allUsers` invoker access earlier. The BFS service needs the same grant to be reachable from a browser:

```bash
gcloud run services add-iam-policy-binding bfs-ai-lab-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --member="allUsers" \
    --role="roles/run.invoker"
```

**Remove the binding to make the BFS service private again:**

```bash
gcloud run services remove-iam-policy-binding bfs-ai-lab-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --member="allUsers" \
    --role="roles/run.invoker"
```

Both commands are recorded in `Docs/runbook (1).md`.

### 7.4 Pausing one service without deleting it

**Scale to zero** — service stays deployed, URL stays valid, no compute cost when idle. Cold start on next request (~5-6s):

```bash
gcloud run services update bfs-ai-lab-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --min-instances 0
```

**Restore warm instance before a demo:**

```bash
gcloud run services update bfs-ai-lab-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --min-instances 1
```

Same pattern applies to `ing-fm-poc-service`.

### 7.5 Database impact

**No schema change. No DB mutation.** Both services read the same `ca.*` tables. Brand substitution happens in Python after the row is fetched — no `UPDATE`, no `INSERT`, no `DELETE`.

The `reset-baseline` endpoint is unaffected: it writes to the DB and doesn't read the transformed API output.

---

## 8. Verification

### 8.1 Automated — `test_parity.py`

13-gate dynamic parity audit. Run before every deploy.

```bash
cd ~/ing-fm-poc
python3 test_parity.py
```

Expected: `13/13 GATES PASSED`. Verifies PostgreSQL connection, market data ground truth, `/api/opportunities` integrity, bundle consistency, PPTX generation, and non-destructive invariance.

**The parity audit does not exercise the deck-generation HTTP path** — it calls `build_pitchbook()` directly. To test the full API path (`handle_pitchbook_generation` → `_set_active_brand` → `build_pitchbook`), use the POST endpoint directly (see §8.2).

### 8.2 Manual — endpoint checks

**Local uvicorn (before deploy):**

```bash
cd ~/ing-fm-poc
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
```

Then in another terminal:

```bash
curl -s http://localhost:8080/api/brand | python3 -m json.tool
curl -s http://localhost:8080/api/opportunities | python3 -c "
import sys, json
d = json.load(sys.stdin)
for o in d:
    if o.get('id') in ('CLI101', 'CLI103'):
        print(o.get('id'), '| family:', o.get('family'), '| adj present:', bool(o.get('adjacent_opportunities')))
"
```

**Toggle local brand** by running the same server with the env var:

```bash
BRAND=BFS_AI_LAB python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
```

Then `/api/brand` returns the BFS profile.

### 8.3 Post-deploy — both services

```bash
SVC_URL=$(gcloud run services describe ing-fm-poc-service --region europe-west1 --project dulcet-radar-508218-c5 --format "value(status.url)")
BFS_URL=$(gcloud run services describe bfs-ai-lab-service --region europe-west1 --project dulcet-radar-508218-c5 --format "value(status.url)")

echo "ING: $SVC_URL"
echo "BFS: $BFS_URL"

curl -s "$SVC_URL/api/brand" | python3 -m json.tool | head -3
curl -s "$BFS_URL/api/brand" | python3 -m json.tool | head -3
```

Expected:
- ING: `"name": "ING"`
- BFS: `"name": "BFS AI Lab"`

**Deck content-disposition test:**

```bash
curl -s -X POST "$BFS_URL/api/pitchbook/generate" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"CLI101"}' \
  -D /tmp/bfs_headers.txt \
  -o /tmp/bfs_test.pptx

grep -i "content-disposition" /tmp/bfs_headers.txt
ls -la /tmp/bfs_test.pptx
```

Expected: `filename="BFS_AI_LAB_Enel_S.p.A._Pitchbook.pptx"` and a file around 800 KB.

### 8.4 Visual checks in browser

**ING service — hard-refresh (`Ctrl+Shift+R`):**

| Element | Expected |
|---|---|
| Header badge | Orange |
| Buttons (`Download`, `Compliance Audit`, chat send) | Orange |
| Pillar headings | Navy |
| Card light-tint backgrounds | Pale orange |
| Copilot name | `ING Copilot` |
| Browser tab | `ING Financial Markets Insights` |
| Download filename | `ING_Enel_S.p.A._Pitchbook.pptx` |

**BFS service — hard-refresh:**

| Element | Expected |
|---|---|
| Header badge | Navy (`#0A3168`) |
| Buttons | Turquoise (`#10C4C0`) |
| Pillar headings | BFS navy |
| Card light-tint backgrounds | Pale turquoise |
| Copilot name | `BFS AI Lab Copilot` |
| Browser tab | `BFS AI Lab Financial Markets Insights` |
| Download filename | `BFS_AI_LAB_Enel_S.p.A._Pitchbook.pptx` |
| Deck size | ~800 KB |
| Cover slide text | `Financial Markets Origination` clears the logo (moved to y=1.00") |

### 8.5 Known polish backlog

Two cosmetic items, deferred — not blocking:

1. **Slide 1 generated deck** — the `Financial Markets Origination` text box's right edge doesn't exactly match the BFS logo's right edge. The BFS logo is wider (aspect ratio ~1.83:1), extending to x≈12.90", while the text box right edge sits at 12.50". ~0.40" offset. Preview is unaffected (CSS flex handles alignment).
2. **Slide 3 generated deck** — the BFS logo (bottom edge at y=0.95") slightly overlaps the Catalyst card (top edge at y=0.85"). ~0.10" overlap. Preview is unaffected.

Both fixable later via per-brand logo aspect ratio (new profile key) plus card position offsets. Neither affects content, functionality, or legibility materially.

### 8.6 Demo prep note — cache warm

The mandate synthesis cache (`_MANDATE_SYNTH_CACHE`) is per-service and in-memory. **The adjacent opportunities paragraph and priority score come from the cache on deck generation.** If the cache is cold when the deck is generated, the adjacent card renders the fallback text (`"Additional origination angles will appear here once the mandate synthesis identifies any."`).

**Warm the cache before a demo** by loading the dashboard first (`/api/opportunities` triggers synthesis on cache miss). Then generate the deck.

**Also note:** Vertex AI quota. Repeated synthesis calls across many sessions can hit `429 RESOURCE_EXHAUSTED`. The Enel-only whitelist (§10) halves the per-cycle call count. For a live demo, warm the cache 5-10 minutes before the call and avoid rapid page reloads.

---

## 9. Recovery Points

Three annotated tags on the branding branch, pushed to GitHub.

| Tag | Commit | State |
|---|---|---|
| `ing-baseline-pre-branding` | `3d1bb16` | BFS logos committed, no branding code yet — pure ING behaviour |
| `branding-working-pre-color` | `565d8e3` | Toggle working end-to-end, both services deployed, before the color rebrand |
| `branding-complete-enel-only` | `82d75d0` | Full feature — colors, dynamic filename, logo optimization, Enel-only whitelist |

**Restore a single file from a tag:**

```bash
git checkout branding-working-pre-color -- main.py
```

**Restore everything to a tag:**

```bash
git reset --hard branding-working-pre-color
```

**Local file backups** (outside the repo, at `~/ing-fm-poc-backups/`):

| Timestamp | Contents |
|---|---|
| `20260921_042605` | `main.py`, `pitchbook_builder.py`, `App.jsx` — before Diff 1 |
| `20260921_054602_shellrc` | `~/.bashrc` — before the alias edits |
| `20260921_064930_pre_color_rebrand` | `main.py`, `pitchbook_builder.py`, `App.jsx`, `index.html` — before the color rebrand |
| `*_pre_logo_resize` | BFS logos at original 3.26 MB resolution |

**The original design brief** lives at `Docs/Prompt_Branding_Work_Continuation.md`. It documents the *intended* design — this record documents what shipped, and the two differ in several places (§10).

---

## 10. Changelog — Deviations From the Design Brief

`Docs/Prompt_Branding_Work_Continuation.md` describes the design as of 18 September 2026, before any code was written. Implementation revealed that several planned decisions needed to change. This section records the deltas.

### 10.1 Profile shape

| Planned | Implemented | Why |
|---|---|---|
| Single `prompt_org` key | Five separate `prompt_*` keys | Grammar: `"...in ING Wholesale Banking Capital Markets..."` → `"...in Capital Markets..."` (drop the org), not a word swap |
| `pillar_fx` / `pillar_spo` with full pillar sentences | Dropped | Pillar bodies use `_brand()["name"]` inline — the sentence is the same, only the name changes |
| `download_prefix` | Added `download_prefix_short` alongside | ING's existing `ING_` filename must be preserved exactly, not changed to `ING_FM_` |
| No color keys | Six color keys per brand | Full color rebrand was added mid-implementation |
| No `logo_height_inches` | Added | BFS logo needs a taller render (0.60" vs 0.45") for legibility |

### 10.2 Deck builder brand access

| Planned | Implemented | Why |
|---|---|---|
| Brand in `overrides` payload | Module-level `_set_active_brand()` setter | Brand is deployment config, not user-mutable state — it doesn't belong in overrides |
| `pitchbook_builder.py` holds a `BRAND_PROFILES` copy | `main.py` is the sole source; `pitchbook_builder.py` holds a slot | Avoids a third sync invariant (alongside `_CREDIT_RATINGS` and `_FAMILY_KEYWORD_WEIGHTS`) |
| Logo paths hardcoded per brand | `add_logo()` reads `_brand()["logo_white"]` / `["logo_orange"]` | Single code path, brand picks the file |

### 10.3 Read-path substitution scope

| Planned | Implemented | Why |
|---|---|---|
| Include `cf_latent_list` (plural) | Included `cf_latent` (singular) | The response dict has `cf_latent`, not `cf_latent_list` — inventory error in the brief |
| Email substitution `@ing.` → `@bfsailab.` | **Dropped** — emails untouched | An email address is factual content, not brand chrome. Substituting it would fabricate a BFS email that doesn't exist |
| Not specified | Added `adjacent_opportunities`, `why_now`, `action`, `why_now_summary`, `action_summary` | Flavor 2 LLM-generated fields are also brand-sensitive |
| 6 fields | 10 fields | See §4.4 for the full list |

### 10.4 Logo files

| Planned | Implemented | Why |
|---|---|---|
| `bfs_ai_lab_white.png` / `bfs_ai_lab_orange.png` | `bfs_ai_lab_logo_white.png` / `bfs_ai_lab_logo_orange.png` | Naming consistency with `ing_logo_white.png` — the uploaded files used the `_logo_` convention |
| Original resolution (2816×1536, 3.26 MB each) | Cropped and resized to 400×218 (76 KB each) | Original files inflated the generated deck from 75 KB to 3.2 MB. Deck now ~800 KB |

### 10.5 Frontend color mechanism

| Planned | Implemented | Why |
|---|---|---|
| Not specified | CSS custom properties on `document.documentElement` | Single source of truth; 130 replacements compile cleanly with Tailwind 3.4.1 arbitrary-value syntax `bg-[var(--accent)]` |
| Not specified | `document.title` set from `brand.name` | Browser tab matches the active brand |
| Not specified | `ING_FALLBACK` constant in `App.jsx` | Frontend renders ING if the `/api/brand` fetch fails |

### 10.6 The `ctx` bug lesson

The original brief flags a prior bug: `synthesize_mandate_catalyst` referenced `ctx.get('opportunity_type', '')` where `ctx` was not a parameter. The `NameError` was silently caught by a `try/except`, so the code fell back to static text and synthesis never ran. The bug was invisible for sessions because nothing logged the failure.

**The branding implementation applies the lesson:** every brand-lookup failure logs a warning.
- Unrecognized `BRAND` value → `logger.warning(...)` naming the invalid value and valid options, then fall back to ING
- Frontend brand fetch failure → `console.warn(...)` before falling back to `ING_FALLBACK`
- The `_brand()` accessor returns a minimal ING fallback if `_set_active_brand` was never called — but it's the fallback for a **legitimate** "never set" case (e.g. the deck builder used as a standalone library), not for an error path

### 10.7 Whitelist scope change

| Planned | Implemented | Why |
|---|---|---|
| Not addressed in the brief | Whitelist reduced to `{"CLI101"}` (Enel only) | BASF was used to test the reset-to-pristine shield and LLM semantic deduplication in earlier sessions — both now verified. Enel is the primary demo. Removing BASF halves Vertex AI quota consumption per cold-cache cycle and prevents `429 RESOURCE_EXHAUSTED` seen under repeated testing |

**To re-enable BASF for destructive testing**, change two lines:
- `main.py`: `_DEMO_CLIENT_IDS = {"CLI101", "CLI103"}`
- `frontend/src/App.jsx`: `const ACTIVE_UI_CLIENT_IDS = ["CLI101", "CLI103"];`

### 10.8 Branch and deploy changes

| Planned | Implemented | Why |
|---|---|---|
| Work on the demo branch | Separate branch `feat/bfs-ai-lab-brand-toggle` | Demo branch stays ING-only and unchanged. Branding work is isolated |
| Deploy commands inline | Two shell aliases: `deploy-poc`, `deploy-bfs` | Ergonomic — one command per service, no risk of forgetting the `BRAND` env var |
| Not addressed | IAM binding for BFS public access | New Cloud Run services default to private; the `allUsers` invoker binding is required for browser access |

### 10.9 Commit history

| Commit | Content |
|---|---|
| `3d1bb16` | BFS logos added, archive backups, pre-branding baseline |
| `565d8e3` | Toggle + 35 string replacements + 130 color replacements + whitelist change — the branding feature itself |
| `82d75d0` | Color rebrand (turquoise/navy for BFS), dynamic filename, dynamic logo height, dynamic cover-slide text, logo optimization |
| `08723ed` | Runbook update — BFS Cloud Run IAM toggle commands |

Committed on `feat/bfs-ai-lab-brand-toggle`. Never merged to the demo branch.

---

*End of document.*
```