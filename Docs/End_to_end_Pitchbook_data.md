End-to-End Data Binding & Template Pipeline
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ING FINANCIAL MARKETS DATA-TO-PITCHBOOK FLOW                    │
├──────────────────────────┬─────────────────────────────┬───────────────────────────────┤
│ Dashboard Segment        │ Source Database Field       │ Pitchbook Output Slide        │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 1. Client Fundamentals   │ `net_debt_eur_m` (€58,500M) │ Slide 4: Balance Sheet &      │
│                          │ `debt_maturing_24m_eur_m`   │ Maturity Wall Analysis        │
│                          │ (€10,127M)                  │                               │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 2. Live Market Curves    │ `swap_rate_pct` (5Y: 2.62%) │ Slide 6 & 7: Market Dynamics, │
│                          │ `spread_bps` (78 bps)       │ Curve & Benchmark Yields      │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 3. Context Fabric        │ `WORKFABRIC_MEMO` /         │ Slide 3 & 5: Catalyst Trigger │
│                          │ `TEAMS_CHAT` / Email        │ & Green Asset Framework       │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 4. Houseviews & News     │ `NEWS_RSS` / `HOUSEVIEWS`   │ Slide 3: Intelligence &       │
│                          │ (Strategy extract)          │ Verified Wire Validation      │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 5. Synthesized Mandate   │ `why_now_nlg` &             │ Slide 2 & 8: Executive Mandate│
│                          │ `next_best_action`          │ Summary & Structuring Terms   │
└──────────────────────────┴─────────────────────────────┴───────────────────────────────┘

This confirms the end-to-end binding architecture. The dynamic pipeline from the database to the pitchbook functions as follows:

Mandate & Opportunity Synthesis: The composite processing in ca.ca_opportunity_scoring identifies the product_family (e.g., DCM_REFI, GREEN_HYBRID, LIABILITY_MGMT).

Template & Metadata Resolution: get_slide_meta(p_fam) resolves the dynamic structure, titles, and layout for that specific product family.

Canonical Calculation (compute_canonical_bundle): Derives single-source-of-truth values for tenor, spreads, all-in rates, tranches, and rate sensitivity scenarios across all slides.

Slide Binding (build_pitchbook): Maps the grounded client data, live market curves, internal signals, and compliance rules directly into the 10-slide deck with zero hardcoded defaults.