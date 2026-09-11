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
3. Single-Touchpoint Rollback (Delete Last Inserted & Reset Scoring)
Remove test touchpoints and revert opportunity scoring to the baseline benchmark:

Bash
cd ~/ing-fm-poc

python3 - << 'EOF'
import main

print("=" * 85)
print(" 🧹 ROLLING BACK LAST INSERTED TOUCHPOINT & REVERTING SCORING")
print("=" * 85)

conn, connector = main.get_db_connection()
if conn:
    try:
        cur = conn.cursor()
        
        # 1. Delete the latest document vector chunk
        cur.execute("""
            DELETE FROM ca.document_vector_chunks
            WHERE chunk_id = (
                SELECT chunk_id 
                FROM ca.document_vector_chunks 
                WHERE client_id = 'CLI101' OR client_id LIKE '%ENEL%'
                ORDER BY created_at DESC, chunk_id DESC 
                LIMIT 1
            )
            RETURNING chunk_id, source_channel, source_name;
        """)
        deleted_chunk = cur.fetchone()
        if deleted_chunk:
            print(f"✓ Deleted latest Chunk #{deleted_chunk[0]} [{deleted_chunk[1]} - {deleted_chunk[2]}]")
        else:
            print("• No chunks found to delete.")

        # 2. Delete the latest digital twin signal
        cur.execute("""
            DELETE FROM ca.digital_twin_signals
            WHERE signal_id = (
                SELECT signal_id 
                FROM ca.digital_twin_signals 
                WHERE client_id = 'CLI101' OR client_id LIKE '%ENEL%'
                ORDER BY created_at DESC 
                LIMIT 1
            )
            RETURNING signal_id, metric_identified;
        """)
        deleted_sig = cur.fetchone()
        if deleted_sig:
            print(f"✓ Deleted latest Signal {deleted_sig[0]} ({deleted_sig[1]})")
        else:
            print("• No signals found to delete.")

        # 3. Reset Opportunity Scoring for CLI101 back to baseline
        cur.execute("""
            UPDATE ca.ca_opportunity_scoring
            SET next_best_action = 'Execute EMTN Benchmark with Pre-Hedge Swap Overlay',
                why_now_nlg = 'Enel successfully issued a US$4.5 billion Yankee bond, advised by White & Case.',
                est_revenue_eur_000 = 5000,
                priority_score = 95,
                opportunity_type = 'REFINANCING | LIQUIDITY'
            WHERE client_id = 'CLI101' OR client_id LIKE '%ENEL%';
        """)
        print("✓ Reset ca.ca_opportunity_scoring back to baseline benchmark.")

        conn.commit()
        cur.close()
        conn.close()
        if connector:
            connector.close()
        print("✓ Rollback complete — database synchronized.")
    except Exception as e:
        print(f"❌ Error during rollback: {e}")
print("=" * 85)
EOF