import os, pg8000.native
conn = pg8000.native.Connection(
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASS", ""),
    host="127.0.0.1", port=5432,
    database=os.environ.get("DB_NAME", "postgres")
)

# Fetch ALL signals for CLI101 (and legacy CLI009_ENEL) that contain any tenor or notional
rows = conn.run("""
    SELECT signal_id, signal_type, catalog_family,
           COALESCE(metric_identified, '') AS metric,
           COALESCE(trigger_summary, '') AS trig,
           COALESCE(metric_value, '') AS mval,
           created_at
    FROM ca.digital_twin_signals
    WHERE client_id IN ('CLI101', 'CLI009_ENEL')
      AND (
        metric_identified ~ '\\y(7|8|10|12)Y\\y'
        OR trigger_summary ~ '\\y(7|8|10|12)Y\\y'
        OR metric_value ~ '\\y(7|8|10|12)Y\\y'
        OR trigger_summary ILIKE '%7 Years%'
        OR trigger_summary ILIKE '%8 Years%'
        OR trigger_summary ILIKE '%10 Years%'
        OR trigger_summary ILIKE '%12 Years%'
        OR trigger_summary ILIKE '%€750M%'
        OR trigger_summary ILIKE '%€600M%'
        OR trigger_summary ILIKE '%€400M%'
        OR metric_identified ILIKE '%€750M%'
        OR metric_identified ILIKE '%€600M%'
        OR metric_identified ILIKE '%€400M%'
      )
    ORDER BY created_at DESC;
""")

print(f"=== {len(rows)} signals match tenor/notional pattern ===")
print()
for r in rows:
    print(f"ID: {r[0]}  |  created: {r[6]}")
    print(f"  type: {r[1]}  |  family: {r[2]}")
    print(f"  metric_identified: {r[3]}")
    print(f"  trigger_summary:   {r[4]}")
    print(f"  metric_value:      {r[5]}")
    print("-" * 90)

conn.close()
