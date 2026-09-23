#!/usr/bin/env python3
"""
load_baseline.py - Load a baseline snapshot into a Cloud SQL instance.

Prerequisites:
    - The `ca` schema and all tables already exist (schema_setup.sql).
    - Env vars set (run: source ./session-init.sh)
    - baseline_snapshots.json present in the repo root.

Usage:
    python3 load_baseline.py                    # normal load
    python3 load_baseline.py --dry-run          # report only, no writes
    python3 load_baseline.py --snapshot PATH    # override snapshot path
    python3 load_baseline.py --client CLI101    # load only one client

Idempotent: PK'd tables use ON CONFLICT DO NOTHING; PK-less tables are
cleared per client_id then re-inserted. Safe to re-run.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from main import get_db_connection


# ---------------------------------------------------------------------
# Table map
# ---------------------------------------------------------------------
# Client-scoped tables, in topological order (parents before children).
# (table_name, pk_col_or_None, serial_col_to_skip_or_None)
CLIENT_TABLES = [
    ("client_master",            "client_id",      None),
    ("cand5_client_master",      None,             None),
    ("dt_client_master",         None,             None),
    ("debt_maturity_schedule",   None,             None),
    ("ext_deals",                "deal_id",        None),
    ("ext_company_filings",      "filing_id",      None),
    ("digital_twin_signals",     "signal_id",      None),
    ("document_vector_chunks",   "chunk_id",       None),
    ("ca_opportunity_scoring",   "opportunity_id", None),
    ("coverage_teams",           None,             None),
]

# Global tables (not client-scoped). Fetched once.
GLOBAL_TABLES = [
    ("mkt_rates_curves",         "curve_id",       None),
    ("ext_credit_spreads",       "spread_id",      None),
]

# Tables with no reliable unique constraint. Cleared per client_id
# before insert to guarantee idempotent re-runs.
PKLESS_TABLES = {
    "cand5_client_master",
    "dt_client_master",
    "debt_maturity_schedule",
    "coverage_teams",
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def quote_ident(name):
    return '"' + name.replace('"', '""') + '"'


def build_insert_sql(table, columns, pk_col):
    """Parameterised INSERT. Uses %s (DB-API style) for SQLAlchemy-pg8000."""
    cols_sql = ", ".join(quote_ident(c) for c in columns)
    params_sql = ", ".join(["%s"] * len(columns))
    if pk_col:
        conflict = f" ON CONFLICT ({quote_ident(pk_col)}) DO NOTHING"
    else:
        conflict = ""
    return f"INSERT INTO ca.{quote_ident(table)} ({cols_sql}) VALUES ({params_sql}){conflict}"


def row_to_tuple(row_dict, columns):
    return tuple(row_dict.get(c) for c in columns)


def insert_rows(cur, table, pk_col, serial_col, rows, dry_run=False):
    if not rows:
        return 0, 0
    columns = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k == serial_col:
                continue
            if k not in seen:
                seen.add(k)
                columns.append(k)
    sql = build_insert_sql(table, columns, pk_col)
    inserted = 0
    skipped = 0
    for r in rows:
        params = row_to_tuple(r, columns)
        if dry_run:
            inserted += 1
            continue
        try:
            cur.execute(sql, params)
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            skipped += 1
            print(f"    [warn] {table}: {type(e).__name__}: {e}")
    return inserted, skipped


def clear_client_rows(cur, table, cid, dry_run=False):
    if dry_run:
        return
    try:
        cur.execute(f"DELETE FROM ca.{quote_ident(table)} WHERE client_id = %s", (cid,))
    except Exception as e:
        print(f"    [warn] clear {table} for {cid}: {type(e).__name__}: {e}")


def setval_sequence(conn, cur, table, serial_col, dry_run=False):
    if dry_run:
        return
    try:
        cur.execute(f"SELECT COALESCE(MAX({quote_ident(serial_col)}), 1) FROM ca.{quote_ident(table)}")
        max_id = cur.fetchone()[0]
        seq_name = f"ca.{table}_{serial_col}_seq"
        cur.execute("SELECT setval(%s, %s, true)", (seq_name, max_id))
    except Exception as e:
        print(f"    [warn] setval {table}.{serial_col}: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="baseline_snapshots.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--client", default=None)
    args = ap.parse_args()

    snap_path = Path(args.snapshot)
    if not snap_path.is_file():
        print(f"ERROR: snapshot not found: {snap_path}")
        sys.exit(1)

    with open(snap_path) as f:
        snap = json.load(f)

    clients = snap.get("clients", {})
    globals_ = snap.get("global", {})

    if args.client:
        if args.client not in clients:
            print(f"ERROR: client {args.client} not in snapshot")
            sys.exit(1)
        clients = {args.client: clients[args.client]}

    print(f"Snapshot: {snap_path}")
    print(f"Clients:  {len(clients)} ({', '.join(sorted(clients.keys()))})")
    print(f"Global tables: {list(globals_.keys())}")
    print(f"Mode: {'DRY-RUN (no writes)' if args.dry_run else 'LIVE'}")
    print()

    conn, _ = get_db_connection()
    if not conn:
        print("ERROR: database connection failed")
        sys.exit(1)
    cur = conn.cursor()
    total_inserted = 0

    # --- Global tables ---
    print("--- Global tables ---")
    for table, pk_col, serial_col in GLOBAL_TABLES:
        rows = globals_.get(table, [])
        if not rows:
            print(f"  ca.{table}: 0 rows in snapshot, skipped")
            continue
        ins, skip = insert_rows(cur, table, pk_col, serial_col, rows, args.dry_run)
        print(f"  ca.{table}: {ins} inserted, {skip} skipped ({len(rows)} in snapshot)")
        total_inserted += ins
        if serial_col:
            setval_sequence(conn, cur, table, serial_col, args.dry_run)

    # --- Client-scoped tables ---
    for cid, client_data in sorted(clients.items()):
        print(f"\n--- Client {cid} ---")
        for table, pk_col, serial_col in CLIENT_TABLES:
            rows = client_data.get(table, [])
            if not rows:
                continue
            # PK-less tables: clear first, then insert
            if table in PKLESS_TABLES:
                clear_client_rows(cur, table, cid, args.dry_run)
            ins, skip = insert_rows(cur, table, pk_col, serial_col, rows, args.dry_run)
            print(f"  ca.{table}: {ins} inserted, {skip} skipped ({len(rows)} in snapshot)")
            total_inserted += ins
            if serial_col:
                setval_sequence(conn, cur, table, serial_col, args.dry_run)

    # --- Commit ---
    if not args.dry_run:
        conn.commit()
        print(f"\n✓ Committed. Total rows inserted: {total_inserted}")
    else:
        print(f"\n✓ Dry-run complete. Would insert: {total_inserted}")

    # --- Parity report ---
    print("\n--- Parity check (target row counts) ---")
    all_tables = [t[0] for t in GLOBAL_TABLES] + [t[0] for t in CLIENT_TABLES]
    for table in dict.fromkeys(all_tables):
        try:
            cur.execute(f"SELECT COUNT(*) FROM ca.{quote_ident(table)}")
            print(f"  ca.{table}: {cur.fetchone()[0]}")
        except Exception as e:
            print(f"  ca.{table}: ERROR {type(e).__name__}: {e}")

    conn.close()


if __name__ == "__main__":
    main()