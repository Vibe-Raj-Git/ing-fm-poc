# Refresh Button Behavior

**Version:** 15 September 2026
**Status:** Authoritative
**Supersedes:** Previous `Refresh_button.md`

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

**Tables read:** `ca.ca_opportunity_scoring`, `ca.client_master`.

**Note:** the doc's earlier claim that this endpoint reads `ca.digital_twin_signals` is incorrect. It reads only the two tables above.

**What it returns:**

- Active drafts count
- Average time to first draft (static display value)
- Deals pending review count (`priority_score >= 85`)
- Cohort matches count (`ca.client_master` row count)
- Priorities list (top 4 by score, sorted descending)

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
| Cold container (rare, requires `min-instances=0`) | ~12s+ |

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

## 7. Changelog — 15 Sep 2026

Corrected from the previous version:

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