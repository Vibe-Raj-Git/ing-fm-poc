#### Let's write a standalone, clean Python script using single quotes for SQL string literals to pull the exact top-ranked clients.

Run this in your terminal:

cat << 'EOF' > /tmp/get_ranks.py
import sys
sys.path.insert(0, "/home/user/ing-fm-poc")
from main import get_db_connection

conn, connector = get_db_connection()
cur = conn.cursor()

query = """
    SELECT DISTINCT ON (c.client_id)
        c.client_id,
        c.client_name,
        COALESCE(o.priority_score, 75) as score,
        COALESCE(o.est_revenue_eur_000, 0) as est_fee,
        COALESCE(o.opportunity_type, 'STRATEGIC FINANCING') as opp_type
    FROM ca.ca_opportunity_scoring o
    JOIN ca.client_master c ON (o.client_id = c.client_id)
    ORDER BY c.client_id, score DESC, est_fee DESC;
"""

cur.execute(query)
rows = cur.fetchall()

# Rank by score DESC, then fee DESC
sorted_rows = sorted(rows, key=lambda x: (int(x[2] or 0), float(x[3] or 0)), reverse=True)

print("\n" + "="*70)
print(f"{'RANK':<6} {'CLIENT ID':<12} {'SCORE':<8} {'EST. FEE':<12} {'CLIENT NAME'}")
print("="*70)
for idx, r in enumerate(sorted_rows, 1):
    cid, cname, score, est_fee, opp_type = r
    fee_val = float(est_fee or 0)
    fee_str = f"€{fee_val/1000:.1f}M" if fee_val >= 1000 else f"€{int(fee_val)}k"
    print(f"#{idx:<5} {cid:<12} {score:<8} {fee_str:<12} {cname}")
print("="*70 + "\n")

if connector:
    connector.close()
EOF
python3 /tmp/get_ranks.py

python3 /tmp/get_ranks.pyd:<12} {score:<8} {fee_str:<12} {cname}")int(fee_val)}k"'}")True)

======================================================================
RANK   CLIENT ID    SCORE    EST. FEE     CLIENT NAME
======================================================================
#1     CLI001       98       €5.5M        Orsted A/S
#2     CLI103       94       €5.8M        BASF SE
#3     CLI003       94       €5.5M        Stellantis N.V.
#4     CLI101       94       €5.5M        Enel S.p.A.
#5     CLI102       94       €5.5M        ASML Holding N.V.
#6     CLI008       85       €640k        A.P. Moller-Maersk A/S
#7     CLI002       82       €850k        ASML Holding N.V.
#8     CLI104       79       €1.2M        Deutsche Lufthansa AG
#9     CLI004       64       €300k        SAP SE
#10    CLI005       60       €550k        Vattenfall AB
#11    CLI007       55       €410k        Heineken N.V.
#12    CLI105       50       €950k        Bayer AG
#13    CLI006       47       €380k        Koninklijke Philips N.V.
======================================================================

user@ing-fm-dev-1:~/ing-fm-poc$ 