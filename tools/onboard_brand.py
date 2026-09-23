#!/usr/bin/env python3
"""
onboard_brand.py - Interactive utility to onboard a new runtime brand
onto the ING Financial Markets Deal Intelligence Platform.

Given a logo PNG and two base colours, this utility:
  1. Derives hover / light / tint colour variants from the base hexes
  2. Crops + resizes the logo into the 400x218 bounding box (aspect-preserved)
  3. Writes the processed logos to assets/ and frontend/public/assets/
  4. Interactively collects the 5 prompt-persona strings (ING template pre-filled)
  5. Builds the 27-key BRAND_PROFILES entry
  6. Patches main.py to insert the new profile
  7. Appends a deploy-<key> shell alias to ~/.bashrc
  8. Writes brands/<KEY>.json as the canonical per-brand record
  9. Verifies with ast.parse + grep

Design contract (see Docs/WeightedFamily/Brand_Toggle_Implementation.md):
    Adding a brand is a DATA-ONLY change: one BRAND_PROFILES entry,
    two logo files, one deploy alias. No logic changes anywhere.

Usage:
    python3 tools/onboard_brand.py \\
        --key NORTHWIND \\
        --name "Northwind Capital" \\
        --stage-from ~/Downloads/gemini_logo.png \\
        --accent "#701C36" \\
        --navy "#3A0E1D" \\
        --prefix-short "NW" \\
        --dry-run
"""
import argparse
import colorsys
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------
BT = chr(96)       # backtick
BS = chr(92)       # backslash
Q = chr(0x22)      # double quote (for building literals inside f-strings)

DEFAULT_LOGO_HEIGHT = 0.45
TARGET_LOGO_BOX = (400, 218)   # width, height; aspect preserved inside

# Derived-colour formulas: (source_key, target_key, lightness_delta, sat_delta)
# lightness_delta is signed (positive = lighter, negative = darker)
COLOR_DERIVATIONS = [
    ("accent_color", "accent_color_hover",     -0.08,  0.00),
    ("accent_color", "accent_color_hover_alt", -0.12,  0.00),
    ("accent_color", "accent_color_light",     +0.42, -0.30),
    ("accent_color", "accent_color_tint",      +0.42, -0.30),
    ("navy_color",   "navy_color_hover",       +0.10,  0.00),
    ("accent_color", "badge_color",             0.00,  0.00),  # default: accent
]

# The five prompt keys, ING template as starting point
PROMPT_KEYS = [
    ("prompt_capital_markets_persona",
     "You are an Executive Director in {NAME} Capital Markets & Advisory."),
    ("prompt_proposal_ref",
     "The following is {NAME}'s current proposal."),
    ("prompt_compliance_persona",
     "You are the Senior Executive Director of EU Financial Regulatory Compliance at {NAME}."),
    ("prompt_copilot_persona_prefix",
     "You are the senior {NAME} Financial Markets Origination, Structuring & Regulatory Compliance Copilot for"),
    ("prompt_adjacent_phrase",
     "{NAME} has identified"),
]

# The exact 27-key schema every brand in BRAND_PROFILES must satisfy
PROFILE_SCHEMA = [
    "name", "full_name", "copilot_name",
    "logo_white", "logo_orange",
    "footer", "attribution", "api_title",
    "download_prefix", "download_prefix_short",
    "houseview_default_source", "houseview_fallback", "rss_fallback_url",
    "logo_height_inches",
    "accent_color", "accent_color_hover", "accent_color_hover_alt",
    "accent_color_light", "accent_color_tint",
    "navy_color", "navy_color_hover", "badge_color",
    "prompt_capital_markets_persona", "prompt_proposal_ref",
    "prompt_compliance_persona", "prompt_copilot_persona_prefix",
    "prompt_adjacent_phrase",
]

# Fallback RSS — same for every brand; the ING research feed is shared
RSS_FALLBACK = "https://think.ing.com"


# ---------------------------------------------------------------------
# Repo root detection
# ---------------------------------------------------------------------
def find_repo_root():
    """Walk up from this script's location until .git is found."""
    here = Path(__file__).resolve().parent
    for candidate in [here] + list(here.parents):
        if (candidate / ".git").is_dir():
            return candidate
    raise RuntimeError("Could not locate repo root (.git not found)")


REPO_ROOT = find_repo_root()


# ---------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(
        prog="onboard_brand.py",
        description="Onboard a new runtime brand onto the deal-intelligence platform.",
    )
    p.add_argument("--key", required=True,
                   help="Uppercase brand key, e.g. NORTHWIND. [A-Z0-9_] only.")
    p.add_argument("--name", required=True,
                   help="Display name, e.g. 'Northwind Capital'.")
    p.add_argument("--stage-from", default=None,
                   help="Path to a raw logo file. Copies it into "
                        "assets/<key>_logo_raw.png and uses it as both "
                        "the white and orange logo source.")
    p.add_argument("--logo-white", default=None,
                   help="Path to the white-bg logo (omit if --stage-from used).")
    p.add_argument("--logo-orange", default=None,
                   help="Path to the light-bg logo (omit if --stage-from used).")
    p.add_argument("--accent", required=True,
                   help="Primary accent colour, e.g. '#701C36'.")
    p.add_argument("--navy", required=True,
                   help="Dark/navy colour, e.g. '#3A0E1D'.")
    p.add_argument("--prefix-short", required=True,
                   help="Short download prefix, e.g. 'NW'. [A-Z0-9_] only.")
    p.add_argument("--logo-height", type=float, default=DEFAULT_LOGO_HEIGHT,
                   help="Deck logo height in inches (default: 0.45).")
    p.add_argument("--dry-run", action="store_true",
                   help="Print everything, write nothing to main.py or ~/.bashrc.")
    p.add_argument("--apply", action="store_true",
                   help="Actually patch main.py and ~/.bashrc. "
                        "Without this, only the logos + JSON are written.")
    p.add_argument("--save-json", action="store_true",
                   help="Write brands/<KEY>.json with the accepted profile.")
    p.add_argument("--resume-from-json", default=None,
                   help="Read brands/<KEY>.json and skip interactive prompts.")
    return p.parse_args()


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def validate_args(args):
    errors = []
    if not KEY_RE.match(args.key):
        errors.append(f"--key must match [A-Z][A-Z0-9_]* (got: {args.key!r})")
    if not PREFIX_RE.match(args.prefix_short):
        errors.append(f"--prefix-short must match [A-Z][A-Z0-9_]* (got: {args.prefix_short!r})")
    if not HEX_RE.match(args.accent):
        errors.append(f"--accent must be #RRGGBB (got: {args.accent!r})")
    if not HEX_RE.match(args.navy):
        errors.append(f"--navy must be #RRGGBB (got: {args.navy!r})")
    if not args.name.strip():
        errors.append("--name must not be empty")
    if args.stage_from is None and (args.logo_white is None or args.logo_orange is None):
        errors.append("Provide either --stage-from OR both --logo-white and --logo-orange")
    if args.stage_from and (args.logo_white or args.logo_orange):
        errors.append("--stage-from is mutually exclusive with --logo-white / --logo-orange")
    if args.apply and args.dry_run:
        errors.append("--apply and --dry-run are mutually exclusive")
    if errors:
        print("ERROR: validation failed:")
        for e in errors:
            print("  - " + e)
        sys.exit(1)
    print("Validation: OK")


# ---------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def shift_lightness(hex_str, lightness_delta, sat_delta):
    """Convert to HLS, shift lightness/saturation, convert back."""
    r, g, b = hex_to_rgb(hex_str)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    l = max(0.0, min(1.0, l + lightness_delta))
    s = max(0.0, min(1.0, s + sat_delta))
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return rgb_to_hex((r2 * 255, g2 * 255, b2 * 255))


def derive_color_defaults(base_map):
    """base_map has 'accent_color' and 'navy_color'. Returns a dict of 6 defaults."""
    out = {}
    for src_key, tgt_key, l_delta, s_delta in COLOR_DERIVATIONS:
        src_hex = base_map.get(src_key)
        if src_hex is None:
            out[tgt_key] = "#000000"
            continue
        out[tgt_key] = shift_lightness(src_hex, l_delta, s_delta)
    return out


# ---------------------------------------------------------------------
# Colour prompt (interactive)
# ---------------------------------------------------------------------
COLOR_PROMPT_LABELS = {
    "accent_color_hover":     "Accent hover (buttons, links)",
    "accent_color_hover_alt": "Accent hover variant (secondary)",
    "accent_color_light":     "Accent light (deck tints)",
    "accent_color_tint":      "Accent tint (frontend tints)",
    "navy_color_hover":       "Navy hover",
    "badge_color":            "Badge background (header chip)",
}


def prompt_colors(base_map):
    """Interactively collect the 6 derived colour values."""
    defaults = derive_color_defaults(base_map)
    accepted = {}
    print()
    print("=== Colour derivation ===")
    print("Derived defaults shown below. Press Enter to accept, or type a")
    print("new #RRGGBB value.")
    print()
    for key in ["accent_color_hover", "accent_color_hover_alt",
                "accent_color_light", "accent_color_tint",
                "navy_color_hover", "badge_color"]:
        label = COLOR_PROMPT_LABELS[key]
        default = defaults[key]
        while True:
            raw = input(f"  {label} [{default}]: ").strip()
            if not raw:
                accepted[key] = default
                break
            if HEX_RE.match(raw):
                accepted[key] = raw.upper()
                break
            print("    Invalid hex. Use #RRGGBB.")
    return accepted


# ---------------------------------------------------------------------
# END OF MESSAGE 1 - main() installed in Message 4
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Logo processing
# ---------------------------------------------------------------------
def stage_logo(args):
    """If --stage-from was used, copy the source into assets/<key>_logo_raw.png
    and return the two source paths (white, orange) — both pointing at the
    staged file. Otherwise return (args.logo_white, args.logo_orange)."""
    if args.stage_from is None:
        return args.logo_white, args.logo_orange

    src = Path(args.stage_from).expanduser().resolve()
    if not src.is_file():
        print(f"ERROR: --stage-from file does not exist: {src}")
        sys.exit(1)

    stage_name = f"{args.key.lower()}_logo_raw.png"
    stage_path = REPO_ROOT / "assets" / stage_name

    if not args.dry_run and not args.apply:
        # Write the staged file even in the "safe" default mode; it's an input
        # artifact, not a repo mutation. Skipped only under --dry-run.
        pass
    if args.dry_run:
        print(f"[dry-run] would copy {src} -> {stage_path}")
        return str(stage_path), str(stage_path)

    shutil.copy2(src, stage_path)
    print(f"Staged: {src} -> {stage_path}")
    return str(stage_path), str(stage_path)


def _crop_whitespace(img, padding=6):
    """Crop uniform near-white margins. Falls back to original if fully white."""
    rgb = img.convert("RGB")
    bg = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = Image.new("L", rgb.size, 0)
    # Manual diff since ImageChops may not be imported
    w, h = rgb.size
    px_src = rgb.load()
    px_bg = bg.load()
    px_out = diff.load()
    for y in range(h):
        for x in range(w):
            r1, g1, b1 = px_src[x, y]
            r2, g2, b2 = px_bg[x, y]
            px_out[x, y] = max(abs(r1 - r2), abs(g1 - g2), abs(b1 - b2))
    bbox = diff.point(lambda v: 255 if v > 10 else 0).getbbox()
    if bbox is None:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(w, x1 + padding)
    y1 = min(h, y1 + padding)
    return img.crop((x0, y0, x1, y1))


def process_logo(src_path, dest_path, box=TARGET_LOGO_BOX):
    """Crop whitespace, thumbnail into box preserving aspect, save as PNG."""
    src = Path(src_path).expanduser().resolve()
    if not src.is_file():
        print(f"ERROR: logo source does not exist: {src}")
        sys.exit(1)

    img = Image.open(src).convert("RGBA")
    img = _crop_whitespace(img)

    # thumbnail() preserves aspect; use the largest dimension
    img.thumbnail(box, Image.LANCZOS)

    # Pad to exact box with transparency so all brands share canvas dims
    canvas = Image.new("RGBA", box, (255, 255, 255, 0))
    x = (box[0] - img.size[0]) // 2
    y = (box[1] - img.size[1]) // 2
    canvas.paste(img, (x, y), img)

    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, "PNG", optimize=True)
    return dest


def write_logos(args, white_src, orange_src):
    """Write both logo variants to assets/ and frontend/public/assets/."""
    key_lower = args.key.lower()
    names = {
        "white":  f"{key_lower}_logo_white.png",
        "orange": f"{key_lower}_logo_orange.png",
    }
    outputs = []
    for variant, src in (("white", white_src), ("orange", orange_src)):
        for base in (REPO_ROOT / "assets",
                     REPO_ROOT / "frontend" / "public" / "assets"):
            dest = base / names[variant]
            if args.dry_run:
                print(f"[dry-run] would write {dest}")
                continue
            process_logo(src, dest)
            print(f"Wrote: {dest}")
            outputs.append(dest)
    return outputs


# ---------------------------------------------------------------------
# Logo-height prompt
# ---------------------------------------------------------------------
def prompt_logo_height(default):
    print()
    print("=== Logo render height (inches) ===")
    print("The deck places the logo at this height. ING and Acme use 0.45.")
    print("BFS AI Lab uses 0.60 because its mark has more internal whitespace.")
    while True:
        raw = input(f"  logo_height_inches [{default}]: ").strip()
        if not raw:
            return default
        try:
            val = float(raw)
            if 0.20 <= val <= 1.20:
                return val
            print("    Out of range. Use 0.20 - 1.20.")
        except ValueError:
            print("    Not a number.")

# ---------------------------------------------------------------------
# Prompt-strings session
# ---------------------------------------------------------------------
def prompt_strings(brand_name, prefill=None):
    """Interactively collect the 5 prompt-persona strings.
    prefill (optional dict) overrides the ING template for any key."""
    prefill = prefill or {}
    accepted = {}
    print()
    print("=== Prompt-persona strings ===")
    print("These 5 strings set the voice of the synthesis, compliance,")
    print("and Copilot LLMs. ING template shown pre-filled; edit in place")
    print("or press Enter to accept. See Brand_Toggle_Implementation.md")
    print("section 4.5 for why grammar differs per brand.")
    print()
    for key, template in PROMPT_KEYS:
        suggested = prefill.get(key) or template.replace("{NAME}", brand_name)
        print(f"  [{key}]")
        print(f"    Suggested: {suggested}")
        raw = input("    Edit, or Enter to accept: ").rstrip("\n")
        accepted[key] = raw if raw.strip() else suggested
    return accepted


# ---------------------------------------------------------------------
# Profile-dict builder
# ---------------------------------------------------------------------
def build_profile(args, colors, logo_height, prompt_strings_map):
    """Assemble the 27-key profile dict from the collected inputs."""
    key_lower = args.key.lower()
    display = args.name.strip()
    profile = {
        "name": display,
        "full_name": display,
        "copilot_name": f"{display} Copilot",
        "logo_white":  f"{key_lower}_logo_white.png",
        "logo_orange": f"{key_lower}_logo_orange.png",
        "footer": f"{display} {chr(0x2022)} Strictly Confidential",
        "attribution": f"{display} Desk Research & Market Intelligence",
        "api_title": f"{display} FM Insights API",
        "download_prefix": args.prefix_short + "_FM",
        "download_prefix_short": args.prefix_short,
        "houseview_default_source": f"{display} Research",
        "houseview_fallback": f"No {display} houseview published for this client in the current reporting cycle.",
        "rss_fallback_url": RSS_FALLBACK,
        "logo_height_inches": logo_height,
        "accent_color": args.accent.upper(),
        "accent_color_hover": colors["accent_color_hover"],
        "accent_color_hover_alt": colors["accent_color_hover_alt"],
        "accent_color_light": colors["accent_color_light"],
        "accent_color_tint": colors["accent_color_tint"],
        "navy_color": args.navy.upper(),
        "navy_color_hover": colors["navy_color_hover"],
        "badge_color": colors["badge_color"],
    }
    for key, _ in PROMPT_KEYS:
        profile[key] = prompt_strings_map[key]

    # Schema conformance check
    missing = [k for k in PROFILE_SCHEMA if k not in profile]
    extra = [k for k in profile if k not in PROFILE_SCHEMA]
    if missing or extra:
        print(f"ERROR: profile schema mismatch. missing={missing} extra={extra}")
        sys.exit(1)
    if len(profile) != len(PROFILE_SCHEMA):
        print(f"ERROR: profile has {len(profile)} keys, expected {len(PROFILE_SCHEMA)}")
        sys.exit(1)
    return profile


def render_profile_dict(profile, indent="    "):
    """Render the profile as a Python dict literal suitable for main.py."""
    lines = ["{"]
    for key in PROFILE_SCHEMA:
        val = profile[key]
        if isinstance(val, str):
            # Escape any embedded double quotes for a valid Python string
            v = val.replace(BS, BS + BS).replace(Q, BS + Q)
            lines.append(f'{indent}{Q}{key}{Q}: {Q}{v}{Q},')
        elif isinstance(val, float):
            lines.append(f'{indent}{Q}{key}{Q}: {val},')
        else:
            lines.append(f'{indent}{Q}{key}{Q}: {val!r},')
    lines.append(indent[:-4] + "}")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# JSON sidecar
# ---------------------------------------------------------------------
def write_brand_json(args, profile):
    """Write brands/<KEY>.json as the canonical per-brand record."""
    dest = REPO_ROOT / "brands" / f"{args.key}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": "Canonical per-brand record. Consumed by --resume-from-json.",
        "_schema_version": 1,
        "key": args.key,
        "profile": profile,
    }
    if args.dry_run:
        print(f"[dry-run] would write {dest}")
        return dest
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Wrote: {dest}")
    return dest


def load_brand_json(path):
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["profile"]

# ---------------------------------------------------------------------
# main.py patch
# ---------------------------------------------------------------------
def _format_profile_block(key, profile):
    """Render the profile as a properly-indented Python dict literal,
    suitable for insertion into BRAND_PROFILES."""
    inner = "        "
    lines = [f'    {Q}{key}{Q}: {{']
    for k in PROFILE_SCHEMA:
        val = profile[k]
        if isinstance(val, str):
            v = val.replace(BS, BS + BS).replace(Q, BS + Q)
            lines.append(f'{inner}{Q}{k}{Q}: {Q}{v}{Q},')
        elif isinstance(val, float):
            lines.append(f'{inner}{Q}{k}{Q}: {val},')
        else:
            lines.append(f'{inner}{Q}{k}{Q}: {val!r},')
    lines.append("    },")
    return "\n".join(lines)


def patch_main_py(key, profile, args):
    """Insert the new brand profile into BRAND_PROFILES in main.py.
    Surgical str.replace() with count verification (never regex)."""
    main_path = REPO_ROOT / "main.py"
    src = main_path.read_text(encoding="utf-8")

    # Anchor: the closing brace of the last existing profile.
    # Match: '        "prompt_adjacent_phrase": "...",\n    },\n}'
    # which is the end of the last brand entry + the dict close.
    anchor_pat = (
        '        "prompt_adjacent_phrase": "'
    )
    count = src.count(anchor_pat)
    if count == 0:
        print("ERROR: could not find prompt_adjacent_phrase anchor in main.py")
        sys.exit(1)
    if count > 4:
        print(f"ERROR: found {count} anchor candidates — expected <=3 (ING, BFS, Acme)")
        print("       Refusing to patch to avoid ambiguity.")
        sys.exit(1)

    # Find the last occurrence and its enclosing dict close.
    last_idx = src.rfind(anchor_pat)
    # Walk forward to the end of that line, then to the '    },\n}'
    line_end = src.find("\n", last_idx)
    tail = src[line_end:]

    # The next two meaningful lines after that should be '    },' and '}'
    close_anchor = '    },\n}\n'
    close_idx = tail.find(close_anchor)
    if close_idx == -1:
        print("ERROR: could not find BRAND_PROFILES closing '    },\\n}'")
        sys.exit(1)

    # Position where the new entry should be inserted:
    #   - after the last '    },' (which closes the previous entry)
    #   - before the '}' that closes the BRAND_PROFILES dict
    insert_at = line_end + close_idx + len('    },\n')

    # Idempotency: refuse if the key is already present
    if f'{Q}{key}{Q}:' in src:
        print(f"ERROR: {Q}{key}{Q} already present in main.py. Refusing to double-insert.")
        sys.exit(1)

    # Dry-run: show what would change
    block = _format_profile_block(key, profile) + "\n"
    if args.dry_run:
        print()
        print("=== main.py patch (dry-run) ===")
        print(f"Would insert {len(block.splitlines())} lines at byte offset {insert_at}:")
        print(block)
        return False

    if not args.apply:
        print()
        print("=== main.py patch (SKIPPED — pass --apply to write) ===")
        return False

    # Backup
    backup_path = main_path.with_suffix(".py.onboard.bak")
    backup_path.write_text(src, encoding="utf-8")
    print(f"Backup written: {backup_path}")

    # Insert
    new_src = src[:insert_at] + block + src[insert_at:]
    main_path.write_text(new_src, encoding="utf-8")
    print(f"Patched: {main_path}")
    return True


def verify_main_py(key):
    """ast.parse the patched main.py, then grep for the new key."""
    main_path = REPO_ROOT / "main.py"
    try:
        ast_src = main_path.read_text(encoding="utf-8")
        import ast as _ast
        _ast.parse(ast_src)
        print("main.py syntax: OK")
    except SyntaxError as e:
        print(f"ERROR: main.py syntax broken: {e}")
        return False

    matches = ast_src.count(f'{Q}{key}{Q}:')
    if matches < 1:
        print(f"ERROR: {Q}{key}{Q} not found in patched main.py")
        return False
    print(f"main.py contains {Q}{key}{Q}: {matches} match(es)")

    if "prompt_adjacent_phrase" in ast_src:
        print("anchor intact: prompt_adjacent_phrase present")
    return True


# ---------------------------------------------------------------------
# ~/.bashrc alias
# ---------------------------------------------------------------------
def bashrc_alias_line(key):
    """Return the deploy-<key> alias line for ~/.bashrc.
    Inner quotes are escaped with backslash-doublequote to match the
    existing deploy-poc / deploy-bfs / deploy-acme pattern."""
    alias_name = f"deploy-{key.lower().replace(chr(95), chr(45))}"
    brand_env = key.upper()
    svc_name = key.lower().replace(chr(95), chr(45)) + "-service"
    BQ = chr(92) + chr(34)  # backslash + double-quote
    return (
        f'alias {alias_name}="cd ~/ing-fm-poc && gcloud run deploy {svc_name} '
        f'--source . '
        f'--project={BQ}dulcet-radar-508218-c5{BQ} '
        f'--region={BQ}europe-west1{BQ} '
        f'--set-env-vars={BQ}INSTANCE_CONNECTION_NAME=dulcet-radar-508218-c5:europe-west1:ing-postgres-db,'
        f'DB_USER=postgres,DB_NAME=postgres,GCP_PROJECT=dulcet-radar-508218-c5,'
        f'REGION=europe-west1,BRAND={brand_env}{BQ} '
        f'--set-secrets={BQ}DB_PASS=db-postgres-pass:latest{BQ} '
        f'--quiet"'
    )

def patch_bashrc(key, args):
    """Append the deploy alias to ~/.bashrc. Idempotent."""
    bashrc = Path.home() / ".bashrc"
    alias_name = f"deploy-{key.lower().replace(chr(95), chr(45))}"
    line = bashrc_alias_line(key)

    if not bashrc.is_file():
        print(f"ERROR: {bashrc} not found")
        sys.exit(1)

    contents = bashrc.read_text(encoding="utf-8")

    if f"alias {alias_name}=" in contents:
        print(f"{alias_name} already present in ~/.bashrc — skipping (idempotent)")
        return False

    if args.dry_run:
        print()
        print("=== ~/.bashrc patch (dry-run) ===")
        print(f"Would append to {bashrc}:")
        print()
        print(line)
        return False

    if not args.apply:
        print()
        print("=== ~/.bashrc patch (SKIPPED — pass --apply to write) ===")
        return False

    # Backup
    backup_path = bashrc.with_suffix(".bashrc.onboard.bak")
    shutil.copy2(bashrc, backup_path)
    print(f"Backup written: {backup_path}")

    with open(bashrc, "a", encoding="utf-8") as f:
        f.write("\n" + line + "\n")
    print(f"Appended alias to {bashrc}")
    print(f"Reload with: source <(grep '^alias deploy-' ~/.bashrc)")
    return True


# ---------------------------------------------------------------------
# Post-run summary
# ---------------------------------------------------------------------
def print_summary(args, wrote_logos, wrote_json, patched_main, patched_bashrc):
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  brand key          : {args.key}")
    print(f"  display name       : {args.name}")
    print(f"  deploy alias       : deploy-{args.key.lower().replace(chr(95), chr(45))}")
    print(f"  logos written      : {len(wrote_logos) if wrote_logos else 0}")
    print(f"  JSON sidecar       : {'written' if wrote_json else 'skipped'}")
    print(f"  main.py patched    : {'yes' if patched_main else 'no'}")
    print(f"  ~/.bashrc patched  : {'yes' if patched_bashrc else 'no'}")
    print()
    if args.dry_run:
        print("DRY-RUN — nothing was written.")
    elif patched_main and patched_bashrc:
        print("NEXT STEPS:")
        print(f"  1. Run: python3 test_parity.py")
        print(f"  2. Verify: git diff main.py")
        print(f"  3. Reload alias: source <(grep '^alias deploy-' ~/.bashrc)")
        print(f"  4. Deploy: deploy-{args.key.lower().replace(chr(95), chr(45))}")
        print(f"  5. Enable public access (see runbook):")
        print(f"       gcloud run services add-iam-policy-binding "
              f"{args.key.lower().replace(chr(95), chr(45))}-service \\")
        print(f"         --region=europe-west1 --project=dulcet-radar-508218-c5 \\")
        print(f"         --member=\"allUsers\" --role=\"roles/run.invoker\"")
        print(f"  6. Verify: curl $(gcloud run services describe "
              f"{args.key.lower().replace(chr(95), chr(45))}-service \\")
        print(f"         --region europe-west1 --project dulcet-radar-508218-c5 \\")
        print(f"         --format 'value(status.url)')/api/brand | python3 -m json.tool | head -3")


# ---------------------------------------------------------------------
# Real main()
# ---------------------------------------------------------------------
def main():
    args = parse_args()
    validate_args(args)

    # 1. Stage logos
    white_src, orange_src = stage_logo(args)

    # 2. Colours (interactive unless resuming)
    prefill_colors = None
    prefill_strings = None
    if args.resume_from_json:
        loaded = load_brand_json(args.resume_from_json)
        prefill_colors = loaded
        prefill_strings = loaded
        print(f"Resuming from {args.resume_from_json}")

    base_map = {"accent_color": args.accent, "navy_color": args.navy}
    if prefill_colors:
        accepted_colors = {
            k: prefill_colors[k] for k in (
                "accent_color_hover", "accent_color_hover_alt",
                "accent_color_light", "accent_color_tint",
                "navy_color_hover", "badge_color",
            )
        }
    else:
        accepted_colors = prompt_colors(base_map)

    # 3. Logos
    print()
    print("=== Writing logos ===")
    wrote_logos = write_logos(args, white_src, orange_src)

    # 4. Logo height
    logo_height = prompt_logo_height(args.logo_height)
    print(f"  logo_height_inches = {logo_height}")

    # 5. Prompt strings
    if prefill_strings:
        prompt_strings_map = {k: prefill_strings[k] for k, _ in PROMPT_KEYS}
    else:
        prompt_strings_map = prompt_strings(args.name, prefill=None)

    # 6. Build profile
    profile = build_profile(args, accepted_colors, logo_height, prompt_strings_map)

    # 7. Confirm before mutating anything
    print()
    print("=== Ready to apply ===")
    print(f"  brand key   : {args.key}")
    print(f"  display     : {args.name}")
    print(f"  logo height : {logo_height}")
    print(f"  accent      : {profile['accent_color']}")
    print(f"  navy        : {profile['navy_color']}")
    print()
    if args.dry_run:
        print("Mode: DRY-RUN (no writes to main.py or ~/.bashrc)")
    elif args.apply:
        print("Mode: APPLY (will write to main.py and ~/.bashrc)")
    else:
        print("Mode: SAFE (writes logos + JSON only; use --apply for code patches)")
    print()

    # 8. Patch main.py
    patched_main = patch_main_py(args.key, profile, args)

    # 9. Patch ~/.bashrc
    patched_bashrc = patch_bashrc(args.key, args)

    # 10. JSON sidecar
    wrote_json = False
    if args.save_json or args.apply:
        print()
        print("=== Writing JSON sidecar ===")
        write_brand_json(args, profile)
        wrote_json = True

    # 11. Verify main.py if patched
    if patched_main:
        print()
        print("=== Verifying main.py ===")
        if not verify_main_py(args.key):
            print("VERIFICATION FAILED — rolling back main.py from backup")
            backup = REPO_ROOT / "main.py.onboard.bak"
            if backup.is_file():
                shutil.copy2(backup, REPO_ROOT / "main.py")
                print("Rolled back. Investigate before retrying.")
            sys.exit(1)

    # 12. Summary
    print_summary(args, wrote_logos, wrote_json, patched_main, patched_bashrc)


if __name__ == "__main__":
    main()