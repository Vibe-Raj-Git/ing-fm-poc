# Per-Brand JSON Records

This folder holds the canonical per-brand record for each onboarded
runtime brand, written by `tools/onboard_brand.py`.

Files: `<KEY>.json` — one per brand (e.g. `ACME_FINANCIAL.json`).

Each file is consumed by `--resume-from-json`, which lets you
re-generate or re-prompt a brand without re-entering all values.

Currently empty. Populated as brands are onboarded via the utility.