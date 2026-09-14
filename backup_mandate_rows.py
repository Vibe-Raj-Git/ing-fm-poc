import os, json, pg8000.native
conn = pg8000.native.Connection(
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASS", ""),
    host="127.0.0.1", port=5432,
    database=os.environ.get("DB_NAME", "postgres")
)
rows = conn.run("""
    SELECT opportunity_id, why_now_nlg, next_best_action
    FROM ca.ca_opportunity_scoring WHERE client_id = 'CLI101'
    ORDER BY opportunity_id;
""")
backup = [{"opportunity_id": r[0], "why_now_nlg": r[1], "next_best_action": r[2]} for r in rows]
with open("/tmp/mandate_backup_cli101.json", "w") as f:
    json.dump(backup, f, indent=2)
print(f"Backed up {len(backup)} rows to /tmp/mandate_backup_cli101.json")
conn.close()
