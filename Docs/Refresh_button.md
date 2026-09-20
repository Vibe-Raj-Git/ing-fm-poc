# Refresh Button Behavior

**Version:** 20 September 2026 — Baseline (Flavor 1)
**Flavor:** Baseline (Flavor 1)
**Status:** Authoritative
**Audience:** Engineers, Business Analysts

The refresh button and its three endpoints are identical on Flavor 2 (Weighted-Family + Adjacencies). The only difference on Flavor 2 is that `/api/opportunities` returns two additional fields (`family`, `adjacent_opportunities`) — a refresh that triggers synthesis picks up both.

---

## 1. What The Button Does

The refresh icon **[⟳]** in the top-right of the dashboard header triggers
`fetchDashboardData()` in `frontend/src/App.jsx` (line 220).

### 1.1 Frontend sequence

```jsx
const fetchDashboardData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
        const [oppRes, signalsRes, metricsRes] = await Promise.all([
            fetch("/api/opportunities"),
            fetch("/api/signals"),
            fetch("/api/metrics")
        ]);
        
        if (!oppRes.ok) throw new Error("Failed to fetch opportunities");
        if (!signalsRes.ok) throw new Error("Failed to fetch signals");
        if (!metricsRes.ok) throw new Error("Failed to fetch metrics");
        
        const oppData = await oppRes.json();
        const signalsData = await signalsRes.json();
        const metricsData = await metricsRes.json();
        
        setOpportunities(oppData);
        // ...frontend dedup and normalize signals...
        setSignals(uniqueSignals);
        setMetrics(metricsData);
    } catch (err) {
        setError(err.message);
    } finally {
        setIsLoading(false);
    }
}, []);
```

**What happens when the button is clicked:**

1. `isLoading = true` — the icon spins and the button is disabled (`disabled={isLoading}`)
2. Three API calls fire in parallel via `Promise.all`:
   - `GET /api/opportunities`
   - `GET /api/signals`
   - `GET /api/metrics`
3. The three responses are parsed
4. `setOpportunities`, `setSignals`, `setMetrics` update React state
5. `isLoading = false` — the icon stops spinning

No full page reload. The dashboard re-renders in place.

---

## 2. What Each Endpoint Queries

### 2.1 `GET /api/opportunities`

**Tables read:** nine, not four.

| Table | Purpose |
|---|---|
| `ca.client_master` | Client identity, tier, RM fallback |
| `ca.ext_company_filings` | Balance sheet: net debt, liquidity, EBITDA, maturities |
| `ca.debt_maturity_schedule` | Per-tranche maturity ladder |
| `ca.mkt_rates_curves` | Swap rates, government yields |
| `ca.ext_credit_spreads` | Issuer and rating-bucket spreads |
| `ca.ca_opportunity_scoring` | Priority score, mandate anchor (`why_now_nlg`, `next_best_action`) |
| `ca.digital_twin_signals` | Signal corpus for mandate synthesis |
| `ca.document_vector_chunks` | Houseview and news retrieval |
| `ca.coverage_teams` | Primary RM lookup |

**Additional behavior:**

- Runs mandate synthesis for whitelisted clients (see §4)
- Loads the anchor from `ca.ca_opportunity_scoring.why_now_nlg` and `.next_best_action`
- Checks the TTL cache before calling Gemini

### 2.2 `GET /api/signals`

**Tables read:** `ca.digital_twin_signals`, `ca.client_master`.

**Query:**

```sql
SELECT DISTINCT ON (s.signal_id)
    s.signal_id, s.client_id, ...
FROM ca.digital_twin_signals s
LEFT JOIN ca.client_master c ON (s.client_id = c.client_id)
WHERE s.client_id = ANY(%s)
ORDER BY s.signal_id, s.created_at DESC
LIMIT 40;
```

**Post-processing:**

- Python dedups by `(client_name, headline)`
- Returns `deduped_signals[:12]` — maximum 12 signals
- Frontend applies a second dedup pass by `(client_name, headline)`

**Result:** the marquee shows at most 12 unique signals, filtered to `_DEMO_CLIENT_IDS`.

### 2.3 `GET /api/metrics`

**Tables read:** `ca.digital_twin_signals`, `ca.ca_opportunity_scoring`, `ca.client_master`.

**What it returns — the four "This Week" tiles (rewritten 20 Sep, commit `f9f8eeb`):**

| Tile | Backend key | Query | Scope |
|---|---|---|---|
| Clients with signals | `clients_with_signals` | `COUNT(DISTINCT client_id)` in `ca.digital_twin_signals` | Whitelist-scoped |
| Active signals | `active_signals` | `COUNT(*)` in `ca.digital_twin_signals` (all-time); change line shows the 7-day count | Whitelist-scoped |
| High-priority clients | `high_priority_clients` | `COUNT(DISTINCT client_id)` in `ca.ca_opportunity_scoring` WHERE `priority_score >= 85` | Whitelist-scoped |
| Clients in database | `clients_in_database` | `COUNT(*)` in `ca.client_master` | Full book (not whitelist-scoped) |

**Response shape per tile:** `{"value": "<count>", "change": "<trend line>", "label": "<human-readable label>"}`. Fallbacks are `"0"`.

**Plus:** the `priorities` list — top 4 by score, sorted descending, with the whitelist guarantee (any whitelisted client not already present is appended).

**What was removed:** the prior "Avg. time to first draft" tile was hardcoded (`< 15s / ▼ 99% vs manual`) with no underlying measurement. It was removed in `f9f8eeb` because the platform does not record draft generation — the metric was uncomputable without a schema change. Its replacement is the "Active signals" tile. The prior "Active drafts", "Deals pending review", and "Cohort matches" tiles were also fabricated — they all rendered a frontend render count. They were relabeled to "Clients with signals", "High-priority clients", and "Clients in database" respectively.

---

## 3. When To Use The Button

Three scenarios where the refresh is useful.

### 3.1 After ingesting a client touchpoint

When a new signal is ingested (email, Teams chat, RSS, PDF), the backend writes rows to
`ca.digital_twin_signals`. If the client is whitelisted, the next `/api/opportunities` call
will re-run mandate synthesis (cache miss).

Clicking **[⟳]**:

- Pulls the new signal into the marquee
- Recomputes opportunity scores
- Triggers fresh synthesis if the cache has expired

### 3.2 To update freshness timestamps

Relative timestamps in the marquee ("Just now", "12m ago") are computed against
`datetime.now()` at query time. Clicking refresh updates them without a page reload.

### 3.3 Multi-user and background updates

If another RM, an automated scraper, or a scheduled job writes to Cloud SQL, the current
user's dashboard does not see those rows until they refresh. Clicking **[⟳]** syncs the
local UI with the latest DB state.

---

## 4. What The Button Does Not Do

These are worth stating explicitly to prevent expectation mismatch.

### 4.1 It does not force mandate re-synthesis if the cache is warm

`_MANDATE_SYNTH_CACHE` has a 300-second TTL. If a synthesis ran less than 5 minutes ago, the
next refresh returns the cached values. The narrative will not change until the TTL expires
or the cache is cleared (by a container restart).

**To force re-synthesis:** either wait for the TTL, or trigger a new revision (any
`deploy-poc` restart clears the in-memory cache).

### 4.2 It does not close open modals

The pitchbook preview modal and ingestion modal are React state, not part of the fetched
data. Refreshing the dashboard data does not close them. This is by design — an RM who has
the preview open while a background job ingests a new signal can refresh the dashboard
without losing their place.

### 4.3 It does not reset session-scoped overrides

`deckOverrides` (spread adjustments, tenor changes, and any copilot mutations) live in
separate React state. Refresh does not reset them.

### 4.4 It does not re-fetch pitchbook bundles

`/api/pitchbook/generate` is only called when the user clicks **Download .PPTX Deck**. The
refresh button does not trigger deck regeneration.

### 4.5 It does not reload the page

The browser tab stays on the same URL. No browser cache is cleared.

---

## 5. Performance Characteristics

| Scenario | Expected time |
|---|---|
| Warm container, warm cache | ~1s |
| Warm container, cold cache (first synthesis) | ~5-6s |
| Cold container | Not reachable — Cloud Run is configured with `min-instances=1` |

**Why warm is ~1s:** the `/api/opportunities` endpoint runs the mandate synthesis only on
cache miss. On cache hit, it returns DB values directly. The other two endpoints
(`/api/signals`, `/api/metrics`) execute fast DB queries with no LLM involvement.

**Why cold is ~5-6s:** the first `/api/opportunities` call after cache expiry triggers one
Gemini synthesis call for the whitelisted client (~3-5 seconds of wall time).

The doc's earlier claim of "under 300 milliseconds" was incorrect — even the fastest warm
path is limited by the DB query work across 13 clients.

---

## 6. Where The Button Is Rendered

There are two buttons in the app that call `fetchDashboardData()`. Same handler, different
contexts.

### 6.1 Primary refresh (header bar)

`frontend/src/App.jsx`, top-right of the dashboard header:

```jsx
<button 
    onClick={fetchDashboardData} 
    className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
    title="Refresh database records"
    disabled={isLoading}
>
    <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
</button>
```

- `RefreshCw` icon spins while `isLoading` is true
- Button is disabled during the fetch to prevent duplicate requests
- Available on the main dashboard view

### 6.2 Retry button (error state)

When the initial data load fails (any of the three API calls returns non-OK, or a network
error occurs), the app switches to an error state showing:

```jsx
<div className="min-h-screen flex items-center justify-center bg-[#F8F9FA] p-6">
    <div className="bg-white rounded-xl border border-red-200 p-8 max-w-md w-full text-center shadow-lg">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="w-8 h-8 text-red-600" />
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Error Loading Data</h2>
        <p className="text-sm text-gray-600 mb-4">{error}</p>
        <button
            onClick={fetchDashboardData}
            className="bg-[#FF6200] text-white px-6 py-2 rounded-lg font-semibold hover:bg-[#E05500] transition"
        >
            Retry
        </button>
    </div>
</div>
```

The **Retry** button calls the same handler. If the DB is back online, the dashboard loads
normally. If the error persists, the error state remains visible.

### 6.3 Difference between the two

| | Header refresh | Error Retry |
|---|---|---|
| Visible when | Always (dashboard loaded) | Only on initial load failure |
| Behaviour | Re-fetches in place | Attempts full dashboard load |
| Icon | `RefreshCw` with spin | "Retry" text button |
| Purpose | On-demand sync | Recovery from failure |

---

## 7. Changelog — 20 Sep 2026 (Flavor 1 — Baseline)

Additions since the 15 Sep version. Reflects the 18–20 Sep session.

### Corrected (this version)

- **§2.3 rewritten.** The four "This Week" tiles were replaced in commit `f9f8eeb`. The prior tiles (`Active drafts`, `Avg. time to first draft`, `Deals pending review`, `Cohort matches`) were fabricated. New tiles: `Clients with signals`, `Active signals`, `High-priority clients`, `Clients in database`. Table list updated to include `ca.digital_twin_signals`.
- **§5 cold-container note.** Cloud Run is configured `min-instances=1` — the cold path is not reachable.
- **Header updated.** Flavor identification and audience added. Note added that the refresh behavior is identical on Flavor 2.

### Corrected in the 15 Sep version (preserved)

- Signal count corrected — SQL fetches up to 40, Python slices to 12 unique signals.
- Table count corrected — `/api/opportunities` reads 9 tables.
- `/api/metrics` sources corrected.
- Timing claim corrected — ~1s warm, ~5-6s cold (with `min-instances=1`).
- UI description corrected — no filters or tabs in the current React UI.
- §4 "What The Button Does Not Do" added.
- §5 Performance Characteristics added.
- §6 expanded — two buttons call `fetchDashboardData()`.

- **Signal count corrected.** "Latest 15 live signals" → SQL fetches up to 40, Python slices
  to 12 unique signals.
- **Table count corrected.** "4-table join" → 9 tables read by `/api/opportunities`.
- **`/api/metrics` sources corrected.** The doc claimed `digital_twin_signals` and
  `ca_opportunity_scoring`. Actual: `ca_opportunity_scoring` and `ca.client_master`.
- **Timing claim corrected.** "Under 300 milliseconds" → ~1s warm, ~5-6s cold.
- **UI description corrected.** Removed references to "open filters" and "selected tabs" —
  the current React UI has no filters or tabs.
- **§4 "What The Button Does Not Do" added.** Cache behavior, modals, overrides, and page
  reload clarifications.
- **§5 Performance Characteristics added.**
- **§6 expanded.** Two buttons call `fetchDashboardData()`: the header refresh and the error
  state retry. Both documented with their JSX references and context.
- **§2 broken into per-endpoint subsections** with actual table lists.

---

*End of document.*