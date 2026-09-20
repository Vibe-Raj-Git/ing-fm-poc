Markdown
## Database Operations Runbook

> **Prerequisite:** Before running any section below on a workstation instance, ensure your environment variables and Cloud SQL Auth Proxy daemon are running:
> ```bash
> cd ~/ing-fm-poc
> source ./session-init.sh
> ```

---

# 1. Full Audit (Inspect All Tables & Counts)
Review all document vector chunks, the top 10 digital twin signals, and opportunity scoring records for Enel (`CLI101`):

```bash
cd ~/ing-fm-poc

python3 - << 'EOF'
import main

print("=" * 85)
print(" 🔎 COMPREHENSIVE DB AUDIT: ENEL S.P.A. (CLI101)")
print("=" * 85)

conn, connector = main.get_db_connection()
if conn:
    cur = conn.cursor()
    
    # 1. Document Vector Chunks
    print("--- [1/3] ca.document_vector_chunks ---")
    cur.execute("""
        SELECT chunk_id, client_id, source_channel, source_name, created_at, text_content
        FROM ca.document_vector_chunks
        WHERE client_id = 'CLI101' OR client_id LIKE '%ENEL%'
        ORDER BY created_at DESC, chunk_id DESC;
    """)
    chunks = cur.fetchall()
    print(f"Total Chunks: {len(chunks)}")
    for r in chunks:
        cid, cl_id, chan, src, ctime, txt = r
        print(f"  • ID #{cid:<4} | {chan:<16} | {str(src)[:30]:<30} | {ctime}")
        print(f"    Preview: {txt[:80]}...")
    
    # 2. Digital Twin Signals
    print("\n--- [2/3] ca.digital_twin_signals ---")
    cur.execute("""
        SELECT signal_id, catalog_family, signal_type, metric_identified, created_at
        FROM ca.digital_twin_signals
        WHERE client_id = 'CLI101' OR client_id LIKE '%ENEL%'
        ORDER BY created_at DESC;
    """)
    sigs = cur.fetchall()
    print(f"Total Signals: {len(sigs)}")
    for r in sigs[:10]:
        sid, cat, stype, metric, ctime = r
        print(f"  • {sid:<16} | {str(cat):<25} | {str(metric)[:30]:<30} | {ctime}")
    if len(sigs) > 10:
        print(f"    ... and {len(sigs) - 10} earlier baseline signals.")

    # 3. Opportunity Scoring
    print("\n--- [3/3] ca.ca_opportunity_scoring ---")
    cur.execute("""
        SELECT client_id, opportunity_type, priority_score, est_revenue_eur_000, next_best_action, why_now_nlg
        FROM ca.ca_opportunity_scoring
        WHERE client_id = 'CLI101' OR client_id LIKE '%ENEL%';
    """)
    opps = cur.fetchall()
    print(f"Total Opportunity Rows: {len(opps)}")
    for r in opps:
        cl_id, otype, score, rev, nba, why = r
        print(f"  • Client: {cl_id} | Score: {score} | Revenue: €{rev:,.0f}k | Type: {otype}")
        print(f"    Action : {nba}")
        print(f"    Why Now: {str(why)[:80]}...")

    cur.close()
    conn.close()
    if connector:
        connector.close()
print("=" * 85)
EOF
2. Quick Top-Record Checker (Post-Ingestion / Post-Deletion)
Verify what currently sits at the top of ca.document_vector_chunks and ca.digital_twin_signals:

Bash
cd ~/ing-fm-poc

python3 - << 'EOF'
import main

conn, connector = main.get_db_connection()
if conn:
    cur = conn.cursor()
    print("=" * 85)
    print(" 🔎 TOP ACTIVE RECORDS (ENEL S.P.A.)")
    print("=" * 85)
    
    # Check top chunk
    cur.execute("""
        SELECT chunk_id, source_channel, source_name, created_at, text_content 
        FROM ca.document_vector_chunks 
        WHERE client_id = 'CLI101' OR client_id LIKE '%ENEL%' 
        ORDER BY created_at DESC, chunk_id DESC LIMIT 1;
    """)
    top_chunk = cur.fetchone()
    if top_chunk:
        print(f"Top Chunk  : #{top_chunk[0]} [{top_chunk[1]}] by {top_chunk[2]} ({top_chunk[3]})")
        print(f"Preview    : {top_chunk[4][:85]}...")
    else:
        print("Top Chunk  : None found.")
    
    # Check top signal
    cur.execute("""
        SELECT signal_id, metric_identified, created_at 
        FROM ca.digital_twin_signals 
        WHERE client_id = 'CLI101' OR client_id LIKE '%ENEL%' 
        ORDER BY created_at DESC LIMIT 1;
    """)
    top_sig = cur.fetchone()
    if top_sig:
        print(f"Top Signal : {top_sig[0]} - {top_sig[1]} ({top_sig[2]})")
    else:
        print("Top Signal : None found.")
        
    print("=" * 85)
    cur.close()
    conn.close()
    if connector:
        connector.close()
EOF

## 3. Rollback / Reset — Use The Reset Endpoint

### 3.1 Why the old manual DELETEs are retired

Earlier versions of this runbook included `DELETE` statements to "remove test touchpoints" and `UPDATE` statements to revert `ca_opportunity_scoring` to a hardcoded baseline narrative. Those predate the reset-to-pristine endpoint and are **no longer safe**:

- **Signal DELETEs have no reliable filter.** BASF's signals — curated and organic — share a single `created_at` timestamp after the enrichment run (`2026-09-16 19:49:25.215347`). `ORDER BY created_at DESC LIMIT 1` returns an arbitrary row. There is no column that reliably distinguishes test-ingested signals from pristine ones.
- **Chunk DELETEs cannot distinguish test from pristine after a reset.** After a reset, pristine chunks also hold `created_at = NOW()`. The top of the sort is arbitrary between test and pristine content.
- **The narrative UPDATE writes stale content.** The hardcoded strings ("Execute EMTN Benchmark with Pre-Hedge Swap Overlay", "Enel successfully issued a US$4.5 billion Yankee bond...") are from a pre-14Sep era. They contradict the curated baseline in `baseline_snapshots.json`. Writing them would break the demo narrative.
- **Hardcoded `priority_score = 95` fights the current architecture.** The score is recomputed on every synthesis run (commit `13721ca`) and written back to `ca_opportunity_scoring`. A manual override is overwritten on the next cache miss and provides no durable state.

**The correct mechanism is the reset-to-pristine endpoint** (`POST /api/system/reset-baseline`). It is non-destructive, idempotent, and reads the curated values from the snapshot rather than from hardcoded strings. See `Data_or_Fabrication.md` §8 for the full mechanism.

### 3.2 Reset BASF (`CLI103`)

BASF is the safe test target. Run this to restore the curated baseline without touching Enel.

```bash
cd ~/ing-fm-poc

python3 - << 'EOF'
import requests

print("=" * 85)
print(" 🧹 RESET-TO-PRISTINE — CLI103 (BASF SE)")
print("=" * 85)
print()
print("Non-destructive. Refreshes pristine rows' created_at = NOW() so they")
print("outrank any test content. Curated narrative restored from snapshot.")
print()

try:
    resp = requests.post(
        "http://localhost:8080/api/system/reset-baseline",
        json={"client_ids": ["CLI103"]},
        timeout=30,
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status   : {data.get('status')}")
        print(f"  Restored : {data.get('restored_clients')}")
        print(f"  Skipped  : {data.get('skipped_clients')}")
        summary = data.get("summary", {}).get("CLI103", {})
        if summary:
            print(f"  Rows restored per table:")
            for tbl, n in summary.items():
                print(f"    {tbl}: {n}")
    else:
        print(f"❌ Reset failed — HTTP {resp.status_code}")
        print(f"   {resp.text}")
except Exception as e:
    print(f"❌ Reset call failed: {e}")

print()
print("Next: /api/opportunities will regenerate the mandate narrative on read.")
print("=" * 85)
EOF
```

**Expected output:** `status: success`, `restored_clients: ["CLI103"]`, plus per-table row counts matching the snapshot.

### 3.3 Reset both demo clients

If both Enel and BASF are whitelisted and need resetting:

```bash
cd ~/ing-fm-poc

python3 - << 'EOF'
import requests

resp = requests.post(
    "http://localhost:8080/api/system/reset-baseline",
    json={"client_ids": ["CLI101", "CLI103"]},
    timeout=60,
)
print(resp.json())
EOF
```

### 3.4 What the reset does and does not do

| Behavior | Detail |
|---|---|
| ✅ Restores pristine narrative | Reads `why_now_nlg` / `next_best_action` from `baseline_snapshots.json` |
| ✅ Restores pristine signals and chunks | Sets `created_at = NOW()` so they outrank test content |
| ✅ Invalidates synthesis cache | Pops `_MANDATE_SYNTH_CACHE[cid]`, next read re-synthesizes |
| ✅ Idempotent | Running it ten times produces the same DB state as running it once |
| ✅ Transaction-safe | Rolls back on error; response is all-or-nothing |
| ❌ Does not delete test content | Test-ingested rows remain in the DB, outranked but preserved |
| ⚠️ Touches `ca.ext_company_filings` | Included in the snapshot. A reset restores the snapshot's filing rows for the client. After any manual cleanup, re-run `dump_baseline.py` and commit the new snapshot |
| ❌ Does not touch global tables | `ca.mkt_rates_curves`, `ca.ext_credit_spreads` are not client-scoped |

**Full detail:** `Data_or_Fabrication.md` §8.

### 3.5 If you genuinely need to delete test content

The reset endpoint outranks test content but does not remove it. If a demo requires the DB to have no test rows at all (e.g. a data-hygiene check), the correct filter is **snapshot membership**, not `chunk_id` threshold or signal-ID prefix:

```bash
cd ~/ing-fm-poc

python3 - << 'EOF'
import json
import main

# Load pristine snapshot IDs
with open("baseline_snapshots.json") as f:
    snap = json.load(f)
basf = snap.get("clients", {}).get("CLI103", {})
pristine_chunks = {r["chunk_id"] for r in basf.get("document_vector_chunks", [])}
pristine_signals = {r["signal_id"] for r in basf.get("digital_twin_signals", [])}

print(f"Pristine chunks : {len(pristine_chunks)}")
print(f"Pristine signals: {len(pristine_signals)}")

conn, connector = main.get_db_connection()
cur = conn.cursor()

# Preview what would be deleted (dry run)
cur.execute("""
    SELECT chunk_id, source_channel, source_name
    FROM ca.document_vector_chunks
    WHERE client_id = 'CLI103' AND chunk_id != ALL(%s)
    ORDER BY chunk_id ASC;
""", (list(pristine_chunks),))
candidates = cur.fetchall()
print(f"\nNon-pristine chunks for CLI103: {len(candidates)}")
for c in candidates:
    print(f"  #{c[0]} | {c[1]} | {c[2]}")

cur.execute("""
    SELECT signal_id, signal_type, metric_identified
    FROM ca.digital_twin_signals
    WHERE client_id = 'CLI103' AND signal_id != ALL(%s)
    ORDER BY signal_id ASC;
""", (list(pristine_signals),))
sig_candidates = cur.fetchall()
print(f"\nNon-pristine signals for CLI103: {len(sig_candidates)}")
for s in sig_candidates[:10]:
    print(f"  {s[0]} | {s[1]} | {s[2]}")
if len(sig_candidates) > 10:
    print(f"  ... and {len(sig_candidates) - 10} more")

cur.close(); conn.close()
if connector: connector.close()

print("\nDRY RUN — no rows deleted. Review the candidates above.")
print("To delete, uncomment the DELETE statements in a follow-up script.")
EOF
```

**Run this as a dry-run first.** If the candidate lists are empty, there is no test content — the DB is pristine and nothing needs deleting. If the lists show real test ingestions, they can be deleted with an explicit DELETE that filters by snapshot membership.

**Caveat:** `baseline_snapshots.json` includes a `filing_id` filter. If snapshot membership is the only safety filter, and the snapshot itself was regenerated after test ingestions, it would contain the test content. Always verify the snapshot is the intended pristine state before using its membership as the deletion filter.
```

---