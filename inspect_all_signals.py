import os, pg8000.native
conn = pg8000.native.Connection(
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASS", ""),
    host="127.0.0.1", port=5432,
    database=os.environ.get("DB_NAME", "postgres")
)

# ALL signals for CLI101, unfiltered
rows = conn.run("""
    SELECT signal_id, signal_type, catalog_family,
           COALESCE(metric_identified, '') AS metric,
           COALESCE(trigger_summary, '') AS trig,
           COALESCE(metric_value, '') AS mval,
           created_at
    FROM ca.digital_twin_signals
    WHERE client_id IN ('CLI101', 'CLI009_ENEL')
    ORDER BY created_at DESC
    LIMIT 30;
""")

print(f"=== {len(rows)} total signals for CLI101 ===")
print()
for r in rows:
    print(f"ID: {r[0]}  |  {r[6]}")
    print(f"  type: {r[1]}  |  family: {r[2]}")
    print(f"  metric_identified: {r[3][:90]}")
    print(f"  trigger_summary:   {r[4][:120]}")
    print(f"  metric_value:      {r[5][:80]}")
    print("-" * 90)

conn.close()
