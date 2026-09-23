# Brand Onboarding Guide

**Version:** 23 September 2026
**Audience:** Anyone onboarding a new runtime brand onto the Financial Markets Deal Intelligence Platform
**Scope:** From a brand name and logo file, to a live Cloud Run service serving that brand

---

## 1. Overview

### 1.1 What a brand is

A "brand" in this platform is a **presentation profile** applied at runtime. It controls:

- The colours of the UI (header badge, buttons, pillar headings, card tints)
- The logo that appears on the deck and in the browser tab
- Display strings: brand name, footer text, Copilot name, attribution
- The persona strings sent to the LLM (voice of the synthesis, compliance, and Copilot models)
- The download filename prefix for generated pitchbooks

The codebase itself is brand-agnostic. The same Docker image, the same database, the same pipeline. The only thing that changes is a single entry in a Python dict called `BRAND_PROFILES`, selected at startup by the `BRAND` environment variable.

### 1.2 Why onboarding is a data-only change

Per `Docs/WeightedFamily/Brand_Toggle_Implementation.md` §4.1, the platform was deliberately designed so that adding a brand requires **no code changes**. The evidence:

- `BRAND_PROFILES` is a plain dict. Any new entry with the right 27 keys works.
- `ACTIVE_BRAND = BRAND_PROFILES[os.getenv("BRAND", "ING").upper()]` is brand-agnostic.
- `_brand_substitute` applies a word-boundary regex `\bING\b` -> active brand name. No brand enumeration.
- `/api/brand` returns the active profile. The frontend reads it once on mount.
- The deck builder reads colours, logo, footer, and pillars from the module-level brand slot.

The **onboarding utility** (`tools/onboard_brand.py`) automates producing that data-only change. It writes the profile entry into `main.py`, resizes and stages the logos, and appends the deploy alias ` — all in one command.

### 1.3 What you get when you are done

By the end of this guide you will have:

- A new brand entry in `main.py`'s `BRAND_PROFILES` dict
- Two logo files committed in both `assets/` and `frontend/public/assets/`
- A `brands/<KEY>.json` sidecar documenting every accepted value
- A `deploy-<key>` shell alias in `~/.bashrc`
- A live Cloud Run service with the new brand's `BRAND` env var
- A verified `/api/brand` response confirming the brand is loaded

### 1.4 What you do NOT need to change

To set expectations: onboarding a new brand does **not** require touching `pitchbook_builder.py`, `frontend/src/App.jsx`, `frontend/index.html`, or any other file. Only `main.py` (via the utility) and two logo files.

---

## 2. Prerequisites

### 2.1 Environment

| Requirement | Version / Detail |
|---|---|
| Python | 3.11 (matches the Cloud Run runtime) |
| Pillow | Installed (`pip install Pillow` if missing) |
| gcloud CLI | Authenticated against `dulcet-radar-508218-c5` |
| Git | Checkout of `~/ing-fm-poc` on an appropriate branch |
| VS Code | For safe multi-line pasting (see §2.3) |

### 2.2 Repo state

Before you start, confirm:

```bash
cd ~/ing-fm-poc
git status --short
```

Expect: clean working tree except for files you intend to leave untracked. If there are unrelated modifications, commit or stash them first.

### 2.3 The paste discipline

This guide contains commands and prompts you will paste into a terminal or editor. Three rules:

1. **Prefer `code /tmp/xxx.py` for multi-line content.** Do not paste long blocks directly into the terminal — they mangle.
2. **Verify every paste** with `wc -l` and a targeted `grep` before running.
3. **Commit messages via `code /tmp/msg.txt` then `git commit -F /tmp/msg.txt`.** Never `-m "long text"`.

---

## 3. Step 1 — Generate the logo

### 3.1 The Gemini prompt

Open Gemini, select **Canvas**, paste this prompt. Replace only the brand-name line at the top.

```
Generate a single logo image on a pure white background, sized 1:1 (1024x1024).

BRAND NAME TO RENDER: Northwind Capital

Follow every rule below exactly.

=== LAYOUT ===
- Two text lines, left-aligned within the text block.
- Line 1 (top): the FIRST word only.
- Line 2 (bottom): the SECOND word only.
- Both lines use the same left margin so the left edge of the two
  words aligns vertically.
- The text block occupies roughly the left 65% of the canvas.
- The mark occupies the right 30% of the canvas.
- 5% breathing room on all sides. Nothing touches the canvas edge.

=== TEXT ===
- Typeface: serif, high-contrast, classic financial-house style.
  Think Times New Roman Bold, Baskerville Bold, or a similar
  old-style serif. NOT sans-serif. NOT geometric. NOT a script.
- Weight: bold.
- Case: ALL CAPS.
- Letter-spacing: slightly wide (about 5% of the cap height).
- Colour: a single deep maroon (#701C36).
- Both lines use the same font size unless the two words differ in
  length, in which case scale the shorter word up by up to 15% so
  the two lines read as a balanced block.

=== MARK (right side) ===
- A shield or crest silhouette, drawn in a mid-tone gold (#C9A227).
- Inside the shield, place the brand initials in serif capitals,
  one larger and one smaller, arranged diagonally. For
  NORTHWIND CAPITAL: a large N and a smaller C.
- A curved accent line or arc crosses the shield horizontally.
- The shield has a subtle double outline.
- Above the shield, a small stylised compass point or star centred
  on the vertical axis, drawn in the same gold.

=== PALETTE ===
- Text:       #701C36 (deep maroon)
- Mark:       #C9A227 (mid-tone gold)
- Background: #FFFFFF (pure white, no gradient, no texture)
- Do NOT introduce any other colour.
- Do NOT add drop shadows, glows, or outer strokes on the text.

=== OUTPUT ===
- Export a single flat PNG, 1024x1024.
- No mockups. No business cards. No 3D renders.
- Flat two-dimensional vector-style illustration only.
```

### 3.2 Common adjustments

If Gemini's first output is off:

| Problem | Add this line to the prompt |
|---|---|
| Text too small | Scale the text block up 15% and reduce the mark by 10%. |
| Shield too ornate | Simplify the shield — a single outline, no inner strokes. |
| Wrong serif style | Use Baskerville Bold specifically, not Times. |
| Extra elements | No text other than the two brand-name words. No taglines. |

### 3.3 What to save

Save the PNG anywhere on your machine. You will move it into the repo in §4.

**Note:** Canvas is generative. Two runs of the same prompt will produce different marks. For a family of brands, generate one, then ask Gemini to "change only the text to NORTHWIND / CAPITAL, keep the mark identical."

---

## 4. Step 2 — Stage the logo

### 4.1 The `_raw` naming convention

Place your downloaded PNG in the `assets/` folder with the suffix `_logo_raw.png`:

```bash
mv ~/Downloads/gemini_logo.png ~/ing-fm-poc/assets/northwind_logo_raw.png
```

**Why `_raw`?** The utility produces two processed variants (`_white.png` and `_orange.png`). The `_raw` suffix distinguishes the source file from the outputs. It is also excluded from git by a rule in `.gitignore`: `assets/*_raw.png`.

### 4.1.1 Uploading via Cloud Shell UI

If you are working in Cloud Shell, the simplest way to get the logo
into the repo is the built-in upload button. No `scp`, no
`gcloud compute scp`, no copying through a shared drive.

**Steps:**

1. Click the **⋮** (three dots) menu in the Cloud Shell toolbar.
2. Choose **Upload** → **File**.
3. In the upload dialog, set the destination folder to:
   `/home/user/ing-fm-poc/assets/`
4. Select the PNG from your local machine and upload.

The uploaded file will have whatever name your local machine gave it.
Rename it to match the convention:

```bash
mv ~/ing-fm-poc/assets/uploaded-name.png \
   ~/ing-fm-poc/assets/northwind_logo_raw.png
```
Verify the upload:

```bash
ls -la ~/ing-fm-poc/assets/*_raw.png
The .gitignore rule assets/*_raw.png already excludes it from
git, so no cleanup is needed after the utility processes it.
```
Then run the utility pointing at the staged file:

```bash
python3 tools/onboard_brand.py \
  --key NORTHWIND \
  --name "Northwind Capital" \
  --stage-from assets/northwind_logo_raw.png \
  --accent "#701C36" \
  --navy "#3A0E1D" \
  --prefix-short "NW" \
  --dry-run
```
Note the --stage-from value is a relative path
(assets/northwind_logo_raw.png) rather than an absolute
~/Downloads/... path. Both forms work; the relative form is
shorter and matches the repo layout.

If the upload fails silently (rare, but seen in older Cloud Shell
versions), refresh the browser tab, then re-check with
ls -la ~/ing-fm-poc/assets/. Cloud Shell preserves the home
directory across session restarts, so an upload only needs to
succeed once.

### 4.2 Automatic staging

You can skip the manual `mv` entirely by using the utility's `--stage-from` flag:

```bash
python3 tools/onboard_brand.py \
  --key NORTHWIND \
  --name "Northwind Capital" \
  --stage-from ~/Downloads/gemini_logo.png \
  --accent "#701C36" \
  --navy "#3A0E1D" \
  --prefix-short "NW"
```

The utility copies the file to `assets/northwind_logo_raw.png`, then uses it as both the white and orange logo source.

### 4.3 Why both variants can be the same file

Acme Financial's two logo files are byte-identical — both `acme_logo_white.png` and `acme_logo_orange.png` have the same MD5 hash. This is intentional. If a brand only has one mark, use it for both slots. The filenames exist because the deck has both light-background and dark-background contexts; they simply point at the same asset.

---

## 5. Step 3 — Choose colours

### 5.1 You need two hex values

The utility needs two base colours:

| Argument | Purpose | Example (Northwind) |
|---|---|---|
| `--accent` | Primary accent: buttons, badges, spinners, links | `#701C36` (maroon) |
| `--navy` | Dark colour: pillar headings, navy-tinted chrome | `#3A0E1D` (oxblood) |

### 5.2 Method 1 — Extract from the logo (pixel census)

If the logo already uses brand-appropriate colours, extract them by counting non-white pixels:

```python
from PIL import Image
from collections import Counter

img = Image.open(' + chr(0x22) + 'assets/northwind_logo_raw.png' + chr(0x22) + ').convert(' + chr(0x22) + 'RGB' + chr(0x22) + ')
px = img.load()
w, h = img.size
c = Counter()
for y in range(h):
    for x in range(w):
        r, g, b = px[x, y]
        if r > 240 and g > 240 and b > 240:
            continue  # skip white
        c[(r // 8 * 8, g // 8 * 8, b // 8 * 8)] += 1
for rgb, n in c.most_common(8):
    print(' + chr(0x22) + '#%02X%02X%02X' + chr(0x22) + ' % rgb, n)
```

This is the method used for BFS AI Lab (turquoise `#10C4C0` + navy `#0A3168`) and Acme Financial (maroon `#701C36` + oxblood `#3A0E1D`).

### 5.3 Method 2 — Pick from brand guidelines

If the brand has a style guide, use the primary and secondary brand colours directly. Convert to `#RRGGBB` if needed.

### 5.4 Sanity checks

Before committing the colours, verify two things:

**1. Badge contrast.** The header badge uses white text on the `badge_color` background. Check WCAG contrast:

```python
def rel_lum(hex_str):
    r, g, b = [int(hex_str[i:i+2], 16) / 255 for i in (1, 3, 5)]
    def c(x): return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)

def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

print(' + chr(0x22) + 'badge vs white:' + chr(0x22) + ', contrast(' + chr(0x22) + '#701C36' + chr(0x22) + ', ' + chr(0x22) + '#FFFFFF' + chr(0x22) + '))
```

Target: **4.5:1 or higher** for body text, 3:1 for large text. Acme's maroon `#701C36` against white scores ~7.8:1 — comfortably above the threshold.

**2. Light tint.** The `accent_color_light` derived value should be visibly distinct from white but not overpowering. The utility derives it by shifting lightness +42% and saturation —30%. If the result looks off, you can override it during the interactive session.

---

## 6. Step 4 — Run the utility

### 6.1 Always dry-run first

The utility has three modes:

| Mode | Flags | What it writes |
|---|---|---|
| **Dry-run** | `--dry-run` | Nothing. Prints everything it would do. |
| **Safe** (default) | (no flag) | Only logos + JSON sidecar. No `main.py` or `~/.bashrc` patches. |
| **Apply** | `--apply` | Everything: logos, JSON, `main.py` patch, `~/.bashrc` alias. |

**Always start with `--dry-run`.** It lets you review the profile, the alias line, and the prompt strings without touching anything.

### 6.2 The command

```bash
python3 tools/onboard_brand.py \
  --key NORTHWIND \
  --name "Northwind Capital" \
  --stage-from assets/northwind_logo_raw.png \
  --accent "#701C36" \
  --navy "#3A0E1D" \
  --prefix-short "NW" \
  --dry-run
```

### 6.3 Argument reference

| Argument | Required | Purpose |
|---|---|---|
| `--key` | Yes | Uppercase brand key. `[A-Z][A-Z0-9_]*`. Example: `NORTHWIND`. |
| `--name` | Yes | Display name. Example: "Northwind Capital". |
| `--stage-from` | One of | Raw logo file. Copies it to `assets/<key>_logo_raw.png` and uses it as both logo variants. |
| `--logo-white` | One of | Path to white-background variant (use with `--logo-orange` instead of `--stage-from`). |
| `--logo-orange` | One of | Path to light-background variant. |
| `--accent` | Yes | Primary accent hex. `#RRGGBB`. |
| `--navy` | Yes | Dark/navy hex. |
| `--prefix-short` | Yes | Short download prefix. `[A-Z][A-Z0-9_]*`. Example: `NW`. |
| `--logo-height` | No | Deck logo height in inches. Default `0.45`. BFS uses `0.60` because its mark has more internal whitespace. |
| `--dry-run` | No | Print everything, write nothing. |
| `--apply` | No | Write to `main.py` and `~/.bashrc`. |
| `--save-json` | No | Write `brands/<KEY>.json`. Implied by `--apply`. |
| `--resume-from-json` | No | Read `brands/<KEY>.json` and skip the interactive colour and prompt-string sessions. |

### 6.4 The interactive sequence

After validation, the utility walks through four interactive stages.

**Stage 1 — Colour derivation (6 prompts)**

You'll see derived defaults and can override any of them:

```
=== Colour derivation ===

  Accent hover (buttons, links) [#5A1629]:
  Accent hover variant (secondary) [#48111F]:
  Accent light (deck tints) [#F4E7EB]:
  Accent tint (frontend tints) [#F4E7EB]:
  Navy hover [#4B1326]:
  Badge background (header chip) [#701C36]:
```

Press `Enter` to accept each default, or type a new `#RRGGBB` value. The derived values use HSL lightness/saturation shifts; for most brands they're usable as-is.

**Stage 2 — Logo processing**

No prompt. The utility crops whitespace from each logo, resizes preserving aspect ratio into a 400x218 bounding box with transparent padding, and writes to both `assets/` and `frontend/public/assets/`.

**Stage 3 — Logo height (1 prompt)**

```
  logo_height_inches [0.45]:
```

Press `Enter` for the default, or type a value. The prompt shows the existing precedents: ING and Acme use 0.45, BFS uses 0.60.

**Stage 4 — Prompt-persona strings (5 prompts)**

Each prompt shows the ING template with your brand name substituted. Press `Enter` to accept, or edit in place.

```
  [prompt_capital_markets_persona]
    Suggested: You are an Executive Director in Northwind Capital Capital Markets & Advisory.
    Edit, or Enter to accept:
```

**Note the double "Capital"** — the template hardcodes the division name `Capital Markets & Advisory`. If your brand name also ends in "Capital", "Markets", or "Advisory", you'll want to edit this line. See §7.3 below.

### 6.5 What the dry-run output looks like

A successful dry-run ends with:

```
=== Ready to apply ===
  brand key   : NORTHWIND
  display     : Northwind Capital
  logo height : 0.45
  accent      : #701C36
  navy        : #3A0E1D

Mode: DRY-RUN (no writes to main.py or ~/.bashrc)


=== main.py patch (dry-run) ===
Would insert 29 lines at byte offset <N>:
    "NORTHWIND": {
        "name": "Northwind Capital",
        ...
    },

=== ~/.bashrc patch (dry-run) ===
Would append to /home/user/.bashrc:

alias deploy-northwind="cd ~/ing-fm-poc && gcloud run deploy northwind-service ..."

============================================================
SUMMARY
============================================================
  brand key          : NORTHWIND
  ...
DRY-RUN — nothing was written.
```

**Review this carefully before proceeding.** Especially:

- The 27-key profile block — confirm the prompt strings read naturally for your brand
- The alias line — confirm the service name is what you want

---

## 7. Step 5 — Review the generated profile

### 7.1 The 27-key schema

Every brand profile in `BRAND_PROFILES` must have exactly these 27 keys:

| Key | Type | Purpose | Server-only? |
|---|---|---|---|
| `name` | str | Short display name | No |
| `full_name` | str | Full display name | No |
| `copilot_name` | str | Copilot panel header | No |
| `logo_white` | str | Logo filename for dark backgrounds | No |
| `logo_orange` | str | Logo filename for light backgrounds | No |
| `footer` | str | Slide footer text | No |
| `attribution` | str | "X Desk Research & Market Intelligence" | No |
| `api_title` | str | FastAPI `title=` metadata | No |
| `download_prefix` | str | Long prefix (unused in the API response) | Yes |
| `download_prefix_short` | str | Deck filename prefix | Yes |
| `houseview_default_source` | str | Houseview chip label fallback | No |
| `houseview_fallback` | str | Houseview body fallback | No |
| `rss_fallback_url` | str | RSS fallback link (currently shared across brands) | No |
| `logo_height_inches` | float | Deck logo render height | No |
| `accent_color` | hex | Primary accent | No |
| `accent_color_hover` | hex | Accent hover state | No |
| `accent_color_hover_alt` | hex | Secondary hover | No |
| `accent_color_light` | hex | Deck-side light tint | No |
| `accent_color_tint` | hex | Frontend-side light tint | No |
| `navy_color` | hex | Dark background / heading | No |
| `navy_color_hover` | hex | Navy hover | No |
| `badge_color` | hex | Header badge background | No |
| `prompt_capital_markets_persona` | str | Synthesis persona line | Yes |
| `prompt_proposal_ref` | str | Synthesis proposal reference | Yes |
| `prompt_compliance_persona` | str | Compliance persona line | Yes |
| `prompt_copilot_persona_prefix` | str | Copilot system instruction prefix | Yes |
| `prompt_adjacent_phrase` | str | Copilot adjacent-opportunities phrasing | Yes |

**Server-only** keys are filtered out of the `/api/brand` response. They never reach the browser.

### 7.2 Why 5 separate prompt keys instead of 1

See `Brand_Toggle_Implementation.md` §4.5. In short: grammar. "at ING Wholesale Banking Capital Markets & Advisory" does not grammatically become "at BFS AI Lab Capital Markets & Advisory" — BFS drops the org name entirely and uses "at Capital Markets & Advisory". The five strings are hand-tuned per brand.

### 7.3 The double-name trap

Watch for grammar collisions. Common cases:

| Brand name | Template output | Problem | Fix |
|---|---|---|---|
| Northwind Capital | "in Northwind Capital Capital Markets & Advisory" | Double "Capital" | Drop org name: "in Northwind Capital Markets & Advisory" |
| Meridian Markets | "in Meridian Markets Capital Markets & Advisory" | "Markets...Markets" | Drop org name |
| O'Brien Capital | "O'Brien Capital's current proposal" | "Capital's" reads fine, but watch apostrophes | Usually no fix needed |

The interactive prompt in Stage 4 lets you edit each string in place. **You will not see these collisions until the interactive session** — that's why the utility prompts instead of auto-substituting.

### 7.4 The JSON sidecar

If you run with `--apply` (or `--save-json`), the utility writes `brands/<KEY>.json`:

```json
{
  "_comment": "Canonical per-brand record. Consumed by --resume-from-json.",
  "_schema_version": 1,
  "key": "NORTHWIND",
  "profile": { ... full 27-key dict ... }
}
```

This file is the canonical record. Commit it. If you ever need to re-run the utility against the same brand (e.g. to change a colour), use:

```bash
python3 tools/onboard_brand.py --key NORTHWIND --name "Northwind Capital" \
  --logo-white assets/northwind_logo_white.png \
  --logo-orange assets/northwind_logo_orange.png \
  --accent "#701C36" --navy "#3A0E1D" \
  --prefix-short "NW" \
  --resume-from-json brands/NORTHWIND.json --dry-run
```

The utility will skip the interactive colour and prompt-string sessions, using the JSON values instead. Re-prompting is only needed if you're changing something.

---

## 8. Step 6 — Apply the changes

### 8.1 Pre-apply backups

Before you run `--apply`, back up the two files the utility will modify:

```bash
cp main.py /tmp/main.py.pre-onboard
cp ~/.bashrc /tmp/bashrc.pre-onboard
```

The utility itself also creates `main.py.onboard.bak` and `~/.bashrc.onboard.bak` before patching. But belt-and-braces: a pre-apply backup outside the repo means you have a rollback path even if the utility's backup is deleted.

### 8.2 Run with --apply

```bash
python3 tools/onboard_brand.py \
  --key NORTHWIND \
  --name "Northwind Capital" \
  --stage-from assets/northwind_logo_raw.png \
  --accent "#701C36" \
  --navy "#3A0E1D" \
  --prefix-short "NW" \
  --apply
```

**The interactive sequence is the same as the dry-run.** Answer the six colour prompts, the logo height, and the five prompt strings. Then the utility prints:

```
Backup written: /home/user/ing-fm-poc/main.py.onboard.bak
Patched: /home/user/ing-fm-poc/main.py
Backup written: /home/user/.bashrc.onboard.bak
Appended alias to /home/user/.bashrc

=== Writing JSON sidecar ===
Wrote: /home/user/ing-fm-poc/brands/NORTHWIND.json

=== Verifying main.py ===
main.py syntax: OK
main.py contains "NORTHWIND": 1 match(es)
anchor intact: prompt_adjacent_phrase present
```

If any verification step fails, the utility rolls `main.py` back from its own backup and exits non-zero.

### 8.3 What just changed

| File | Change |
|---|---|
| `main.py` | +29 lines: the `NORTHWIND` entry inserted into `BRAND_PROFILES` |
| `assets/northwind_logo_white.png` | New file, 400x218 cropped + resized |
| `assets/northwind_logo_orange.png` | New file, same content as white (if `--stage-from` used) |
| `frontend/public/assets/northwind_logo_white.png` | Mirror of the above |
| `frontend/public/assets/northwind_logo_orange.png` | Mirror |
| `brands/NORTHWIND.json` | Canonical per-brand record |
| `~/.bashrc` | +1 line: `alias deploy-northwind="..."` |

**Nothing else changed.** No changes to `pitchbook_builder.py`, `App.jsx`, `index.html`, or any other source file.

### 8.4 Verify the patch independently

```bash
python3 -c "import ast; ast.parse(open('main.py').read()); print('OK')"
python3 -c "import main; print(list(main.BRAND_PROFILES.keys()))"
git diff main.py | head -40
```

Expected:

- `OK`
- `['ING', 'BFS_AI_LAB', 'ACME_FINANCIAL', 'NORTHWIND']`
- A single `+29 lines` diff block, no other changes

---

## 9. Step 7 — Commit

### 9.1 Stage the files

```bash
git add main.py \
  assets/northwind_logo_white.png assets/northwind_logo_orange.png \
  frontend/public/assets/northwind_logo_white.png frontend/public/assets/northwind_logo_orange.png \
  brands/NORTHWIND.json
git status --short
```

**Do not** stage `main.py.onboard.bak` or `~/.bashrc.onboard.bak`. They should be excluded by the `*.bak*` rule in `.gitignore`.

### 9.2 Commit message

```bash
code /tmp/msg.txt
```

Content:

```
feat(brand): onboard Northwind Capital

Adds Northwind Capital as a runtime brand via tools/onboard_brand.py.

- main.py: +29-line BRAND_PROFILES entry (27 keys)
- assets/ + frontend/public/assets/: two logo variants
- brands/NORTHWIND.json: canonical per-brand record
- ~/.bashrc (local, not committed): deploy-northwind alias

No logic changes. Brand toggle is a data-only extension.
```

### 9.3 Commit and push

```bash
git commit -F /tmp/msg.txt
git push
```

---

## 10. Step 8 — Deploy

### 10.1 Reload the alias

The new alias was appended to `~/.bashrc` but isn't loaded in the current shell. Reload:

```bash
source ~/.bashrc
```

If `source ~/.bashrc` aborts with a `force_color_prompt: unbound variable` error, the `~/.bashrc` fix described in §13.1 has not been applied. Use the targeted reload instead:

```bash
source <(grep '^alias deploy-' ~/.bashrc)
```

Verify the alias:

```bash
type deploy-northwind
```

### 10.2 Deploy the service

```bash
deploy-northwind
```

The command expands to:

```bash
cd ~/ing-fm-poc && gcloud run deploy northwind-service --source . \
  --project="dulcet-radar-508218-c5" --region="europe-west1" \
  --set-env-vars="INSTANCE_CONNECTION_NAME=...,BRAND=NORTHWIND" \
  --set-secrets="DB_PASS=db-postgres-pass:latest" --quiet
```

Build takes 3–5 minutes. The Cloud Build cache makes this fast on repeat deploys.

### 10.3 Enable public access

**New Cloud Run services default to private.** Grant public access:

```bash
gcloud run services add-iam-policy-binding northwind-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --member="allUsers" \
    --role="roles/run.invoker"
```

To make the service private again:

```bash
gcloud run services remove-iam-policy-binding northwind-service \
    --region=europe-west1 \
    --project=dulcet-radar-508218-c5 \
    --member="allUsers" \
    --role="roles/run.invoker"
```

---

## 11. Step 9 — Verify

### 11.1 The brand endpoint

```bash
NORTHWIND_URL=$(gcloud run services describe northwind-service \
  --region europe-west1 --project dulcet-radar-508218-c5 \
  --format "value(status.url)")
echo "$NORTHWIND_URL"
curl -s "$NORTHWIND_URL/api/brand" | python3 -m json.tool | head -6
```

Expected:

```json
{
    "name": "Northwind Capital",
    "full_name": "Northwind Capital",
    "copilot_name": "Northwind Capital Copilot",
    "logo_white": "northwind_logo_white.png",
    "logo_orange": "northwind_logo_orange.png",
    "footer": "Northwind Capital • Strictly Confidential",
```

**The `name` field proves the entire chain works** — env var → `BRAND_PROFILES` lookup → `/api/brand` response → frontend render.

### 11.2 Browser checks

Open the service URL in a browser. Hard-refresh with `Ctrl+Shift+R` to bypass the cache.

| Element | Expected |
|---|---|
| Header badge | `badge_color` from the profile |
| Buttons (Download, Compliance Audit, chat send) | `accent_color` |
| Pillar headings | `navy_color` |
| Card light-tint backgrounds | `accent_color_tint` |
| Copilot name | "Northwind Capital Copilot" |
| Browser tab | "Northwind Capital Financial Markets Insights" |
| Logo (header) | Your logo, cropped and centred |

### 11.3 Deck checks

```bash
curl -s -X POST "$NORTHWIND_URL/api/pitchbook/generate" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"CLI101"}' \
  -D /tmp/nw_headers.txt \
  -o /tmp/northwind_test.pptx

grep -i "content-disposition" /tmp/nw_headers.txt
ls -la /tmp/northwind_test.pptx
python3 -c "from pptx import Presentation; cp = Presentation('/tmp/northwind_test.pptx').core_properties; print('author:', cp.author); print('title:', cp.title)"
```

Expected:

- `filename="NW_Enel_S.p.A._Pitchbook.pptx"`
- File size ~800 KB
- Author: `Rajarshi Pathak (rajarshi.pathak@cognizant.com)`
- Title: `Enel S.p.A. — Pitchbook`

### 11.4 Parity audit

```bash
python3 test_parity.py 2>&1 | tail -3
```

Expected: `13/13 GATES PASSED`

---

## 12. Rollback

If something went wrong and you need to undo the onboarding:

### 12.1 Undo the code change (before commit)

```bash
cp /tmp/main.py.pre-onboard main.py
python3 -c "import ast; ast.parse(open('main.py').read()); print('OK')"
```

Or, if the pre-apply backup was not made, use the utility's own backup:

```bash
cp main.py.onboard.bak main.py
```

### 12.2 Undo the code change (after commit)

```bash
git revert <commit-sha>
```

Or reset to the previous commit if the onboarding commit is the tip:

```bash
git reset --hard HEAD~1
```

### 12.3 Undo the shell alias

```bash
cp /tmp/bashrc.pre-onboard ~/.bashrc
# Or manually:
# edit ~/.bashrc, remove the 'alias deploy-northwind=' line
unalias deploy-northwind 2>/dev/null
```

### 12.4 Delete the Cloud Run service

```bash
gcloud run services delete northwind-service \
  --region=europe-west1 \
  --project=dulcet-radar-508218-c5 \
  --quiet
```

### 12.5 Delete the artifacts

```bash
rm -f assets/northwind_logo_white.png assets/northwind_logo_orange.png
rm -f frontend/public/assets/northwind_logo_white.png frontend/public/assets/northwind_logo_orange.png
rm -f brands/NORTHWIND.json
rm -f main.py.onboard.bak ~/.bashrc.onboard.bak
```

### 12.6 Verify the rollback

```bash
python3 -c "import main; print(list(main.BRAND_PROFILES.keys()))"
# Expected: ['ING', 'BFS_AI_LAB', 'ACME_FINANCIAL']
git status --short
```

---

## 13. Troubleshooting

### 13.1 source ~/.bashrc fails with force_color_prompt: unbound variable

**Symptom:** `source ~/.bashrc` prints `bash: force_color_prompt: unbound variable` and may abort before loading the deploy aliases.

**Cause:** `~/.bashrc` line 48 has `if [ -n "$force_color_prompt" ]` but the variable is never initialised. Under `nounset`, this errors.

**Fix:** open `~/.bashrc` and change line 48 to:

```bash
if [ -n "${force_color_prompt:-}" ]; then
```

The `:-` operator returns an empty string when the variable is unset, avoiding the error.

**Workaround (if you cannot edit `~/.bashrc`):** reload only the alias lines:

```bash
source <(grep '^alias deploy-' ~/.bashrc)
```

### 13.2 Alias not found after deploy

**Symptom:** `type deploy-northwind` returns `bash: type: deploy-northwind: not found`.

**Cause:** The alias was appended to `~/.bashrc` after the current shell session started. Bash only reads `~/.bashrc` at login.

**Fix:** reload the aliases:

```bash
source ~/.bashrc
# or the targeted reload:
source <(grep '^alias deploy-' ~/.bashrc)
# or, most reliable:
eval "$(grep '^alias deploy-northwind' ~/.bashrc)"
```

### 13.3 main.py syntax error after patch

**Symptom:** `python3 -c "import main"` raises `SyntaxError`.

**Cause:** Very rare. The utility validates with `ast.parse` after patching and rolls back on failure. But if you patched manually and something went wrong:

**Fix:** restore from the utility's backup:

```bash
cp main.py.onboard.bak main.py
python3 -c "import ast; ast.parse(open('main.py').read()); print('OK')"
```

### 13.4 Logo distortion

**Symptom:** The logo appears stretched or squashed on the deck.

**Cause:** The utility preserves aspect ratio, so this is unlikely. If it happens:

**Fix:** Check the source file's dimensions. The utility fits into a 400x218 box with transparent padding. If the source is extremely wide or extremely tall, the rendered logo may look small. Either crop the source to a more moderate aspect ratio first, or adjust `--logo-height`.

### 13.5 Colours look wrong on the UI

**Symptom:** The derived hover or light-tint colours don't look right in the browser.

**Cause:** The HSL derivation formulas are calibrated for BFS and Acme. Some brand palettes fall outside that range.

**Fix:** Re-run the utility with `--resume-from-json` and override the specific colours:

```bash
python3 tools/onboard_brand.py --key NORTHWIND --name "Northwind Capital" \
  --logo-white assets/northwind_logo_white.png \
  --logo-orange assets/northwind_logo_orange.png \
  --accent "#701C36" --navy "#3A0E1D" \
  --prefix-short "NW" \
  --resume-from-json brands/NORTHWIND.json
```

The interactive colour prompt appears with the JSON defaults pre-filled. Edit the specific value that's wrong.

### 13.6 Cloud Run service is private

**Symptom:** The service URL returns `403 Forbidden` in the browser.

**Cause:** New Cloud Run services default to private. Public access requires an explicit IAM binding.

**Fix:** See §10.3.

### 13.7 Adjacent Opportunities card shows fallback text

**Symptom:** Slide 3's Adjacent Opportunities card renders the placeholder "Additional origination angles will appear here once the mandate synthesis identifies any." instead of a real paragraph.

**Cause:** The LLM returned an empty `adjacent_opportunities` string during synthesis, and the cache is holding that empty value for up to 900 seconds.

**Workaround:** Wait 15 minutes for the TTL to expire, then reload the page. A fresh synthesis will likely return a populated value.

**Permanent fix:** Tracked on the `feat/adjacent-opportunities-fallback` branch — a post-synthesis validator with a curated fallback. Deferred.

---

## 14. Reference — Full Gemini prompt

The complete prompt, ready to paste. Replace only the brand name on line 3.

```
Generate a single logo image on a pure white background, sized 1:1 (1024x1024).

BRAND NAME TO RENDER: <BRAND NAME HERE>

Follow every rule below exactly.

=== LAYOUT ===
- Two text lines, left-aligned within the text block.
- Line 1 (top): the FIRST word only.
- Line 2 (bottom): the SECOND word only.
- Both lines use the same left margin so the left edge of the two
  words aligns vertically.
- The text block occupies roughly the left 65% of the canvas.
- The mark occupies the right 30% of the canvas.
- 5% breathing room on all sides. Nothing touches the canvas edge.

=== TEXT ===
- Typeface: serif, high-contrast, classic financial-house style.
  Think Times New Roman Bold, Baskerville Bold, or a similar
  old-style serif. NOT sans-serif. NOT geometric. NOT a script.
- Weight: bold.
- Case: ALL CAPS.
- Letter-spacing: slightly wide (about 5% of the cap height).
- Colour: a single deep maroon (#701C36).
- Both lines use the same font size unless the two words differ in
  length, in which case scale the shorter word up by up to 15% so
  the two lines read as a balanced block.

=== MARK (right side) ===
- A shield or crest silhouette, drawn in a mid-tone gold (#C9A227).
- Inside the shield, place the brand initials in serif capitals,
  one larger and one smaller, arranged diagonally. For
  NORTHWIND CAPITAL: a large N and a smaller C.
- A curved accent line or arc crosses the shield horizontally.
- The shield has a subtle double outline.
- Above the shield, a small stylised compass point or star centred
  on the vertical axis, drawn in the same gold.

=== PALETTE ===
- Text:       #701C36 (deep maroon)
- Mark:       #C9A227 (mid-tone gold)
- Background: #FFFFFF (pure white, no gradient, no texture)
- Do NOT introduce any other colour.
- Do NOT add drop shadows, glows, or outer strokes on the text.

=== OUTPUT ===
- Export a single flat PNG, 1024x1024.
- No mockups. No business cards. No 3D renders.
- Flat two-dimensional vector-style illustration only.
```

For brands with a different palette, replace `#701C36` and `#C9A227` with the desired maroon and gold. For brands without a shield motif, replace the `=== MARK ===` section.

---

## 15. Reference — The 27-key schema

See §7.1 for the full table. Key ordering matters for the utility's schema check, not for the runtime. The `PROFILE_SCHEMA` list in `tools/onboard_brand.py` defines the canonical order.

---

## 16. Reference — Per-brand JSON

See §7.4 for the format. Files live at `brands/<KEY>.json`. They are committed to the repo.

---

*End of guide. For architecture context, see `Docs/WeightedFamily/MASTER_PERSONA_23Sep2026.md`. For the design rationale behind the toggle, see `Docs/WeightedFamily/Brand_Toggle_Implementation.md`.*

