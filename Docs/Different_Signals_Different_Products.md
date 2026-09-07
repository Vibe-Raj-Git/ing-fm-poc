Yes, that is exactly how the platform is architected to behave.

When you ingest signals or latent opportunities spanning different product families (e.g., **FX Risk / Hedging** alongside **Refinancing / Liquidity**), the system handles it dynamically through product archetype routing.

---

### Core Behavioral Flow

```
           [ Ingested Signals / Context Fabric ]
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
   [ Debt / Liquidity Signal ]        [ FX / Rates Exposure Signal ]
             │                                 │
             ▼                                 ▼
  Opportunity #1: Enel S.p.A.        Opportunity #2: Enel S.p.A.
  Type: REFINANCING | LIQUIDITY      Type: FX RISK | CAPEX HEDGING
             │                                 │
             ▼                                 ▼
   Template: DCM / EMTN Deck          Template: FX Derivative / Collar Deck

```

---

### 1. Distinct Opportunity Cards per Product Mandate

In wholesale banking, an RM does not combine an unrelated FX Collar pitch into a Debt Capital Markets (DCM) bond refinancing pitch. The platform generates **two distinct opportunity cards** for Enel:

* **Card 1: Enel S.p.A. — `OPPORTUNITY: REFINANCING | LIQUIDITY**`
* **Catalyst:** €10.1B 24M debt maturity wall, Yankee bond issuance.
* **Grounding Data:** 5Y EUR Swap (2.62%), 10Y Bund (2.61%), credit spread (78 bps).
* **Pitchbook Engine:** Routes to the **DCM / Green EMTN Issuance & Liquidity Template**.


* **Card 2: Enel S.p.A. — `OPPORTUNITY: FX RISK | HEDGING**`
* **Catalyst:** Cross-border USD revenue stream / US CapEx currency exposure without active overlay.
* **Grounding Data:** EUR/USD forward curve, 1Y–3Y implied volatility, basis swap spreads.
* **Pitchbook Engine:** Routes to the **FX Risk Advisory & Derivative Collar Template**.



---

### 2. Archetype-Driven Pitchbook Generation

When the RM clicks **"Open draft pitchbook"** on the FX card:

* The frontend passes the specific opportunity context: `{ client_id: "CLI101", opportunity_type: "FX_HEDGE" }`.
* The backend (`pitchbook_builder.py` / copilot engine) selects the **FX Pitchbook Template**, replacing DCM debt maturity schedules and bond comps with:
* Currency exposure breakdowns
* Hedging scenario payoff diagrams
* Term sheets for FX forwards, cross-currency swaps, or zero-cost collars



---

### 3. How the UI Stays Clean

* **Cohort Header:** Displays **`2 opportunities surfaced`**.
* **Filter Whitelist:** Because `ACTIVE_UI_CLIENT_IDS = ["CLI101"]`, both Enel opportunities automatically appear while keeping other clients hidden until whitelisted.