import os
import sys
from google.cloud.sql.connector import Connector
import pg8000

INSTANCE = os.getenv("INSTANCE_CONNECTION_NAME")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "postgres")

if not INSTANCE:
    print("ERROR: INSTANCE_CONNECTION_NAME is not set.")
    sys.exit(1)
if not DB_PASS:
    print("ERROR: DB_PASS is not set.")
    sys.exit(1)

connector = Connector()

def getconn():
    return connector.connect(
        INSTANCE, "pg8000",
        user=DB_USER, password=DB_PASS, db=DB_NAME,
    )

try:
    conn = getconn()
    cur = conn.cursor()

    print("=" * 80)
    print("ca.ca_opportunity_scoring — rows for CLI101")
    print("=" * 80)

    cur.execute("""
        SELECT opportunity_id, client_id, opportunity_type,
               priority_score, next_best_action
        FROM ca.ca_opportunity_scoring
        WHERE client_id = 'CLI101'
        ORDER BY priority_score DESC;
    """)

    rows = cur.fetchall()
    if not rows:
        print("No rows found for CLI101.")
    else:
        for r in rows:
            opp_id, cid, opp_type, score, nba = r
            print()
            print("opportunity_id  :", opp_id)
            print("client_id       :", cid)
            print("opportunity_type:", opp_type)
            print("priority_score  :", score)
            print("next_best_action:")
            print(" ", nba)
            print("-" * 80)
            if nba:
                print("Substring checks:")
                print("  '€600m 8Y Green bond'                  :", '€600m 8Y Green bond' in nba)
                print("  '€400m 12Y Sustainability-Linked Bond' :", '€400m 12Y Sustainability-Linked Bond' in nba)
                print("  '€600m 7Y Green bond'                  :", '€600m 7Y Green bond' in nba)
                print("  '€400m 10Y Sustainability-Linked Bond' :", '€400m 10Y Sustainability-Linked Bond' in nba)

    cur.close()
    conn.close()

finally:
    try:
        connector.close()
    except Exception:
        pass
