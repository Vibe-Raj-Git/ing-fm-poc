### Query to inspect Live Signals Feed
cd ~/ing-fm-poc

cat << 'EOF' > inspect_signals_marquee.py
import os, pg8000.native
conn = pg8000.native.Connection(
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASS", ""),
    host="127.0.0.1", port=5432,
    database=os.environ.get("DB_NAME", "postgres")
)

print("=== signal_type values and their frequency ===")
rows = conn.run("""
    SELECT signal_type, COUNT(*) as n
    FROM ca.digital_twin_signals
    GROUP BY signal_type
    ORDER BY n DESC;
""")
for r in rows:
    print(f"  {repr(r[0]):<40} | count={r[1]}")

print()
print("=== All signals for CLI101 (Enel) with display fields ===")
rows = conn.run("""
    SELECT signal_id, signal_type, metric_identified, trigger_summary, created_at
    FROM ca.digital_twin_signals
    WHERE client_id IN ('CLI101', 'CLI009_ENEL')
    ORDER BY created_at DESC
    LIMIT 20;
""")
for r in rows:
    print(f"ID: {r[0]}")
    print(f"  signal_type      : {repr(r[1])}")
    print(f"  metric_identified: {repr(r[2])}")
    print(f"  trigger_summary  : {repr((r[3] or '')[:100])}")
    print(f"  created_at       : {r[4]}")
    print()

conn.close()
EOF

export DB_PASS=$(gcloud secrets versions access latest --secret=db-postgres-pass --project=dulcet-radar-508218-c5)
python3 inspect_signals_marquee.py
rm inspect_signals_marquee.py
unset DB_PASS

### Query Output

cat << 'EOF' > inspect_signals_marquee.py
import os, pg8000.native
conn = pg8000.native.Connection(
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASS", ""),
    host="127.0.0.1", port=5432,
    database=os.environ.get("DB_NAME", "postgres")
)

print("=== signal_type values and their frequency ===")
rows = conn.run("""
    SELECT signal_type, COUNT(*) as n
unset DB_PASSgnals_marquee.pyee.pyrsions access latest --secret=db-postgres-pass --project=dulcet-radar-508218-c5)
=== signal_type values and their frequency ===
  'SUSTAINABLE FUNDING'                    | count=10
  'LATENT_OPPORTUNITY'                     | count=3
  'REFINANCING'                            | count=3
  'Bond Issuance'                          | count=2
  'CLIENT_VALIDATION'                      | count=1
  'Debt Analysis Mention'                  | count=1
  'Mandate Status'                         | count=1
  'Credit Risk Concern'                    | count=1
  'Conditional Sustainable Financing Opportunity' | count=1
  'ENERGY_PRICE_VOLATILITY'                | count=1
  'Potential Funding Requirement'          | count=1
  'New Financing Facility'                 | count=1
  'Refinancing Requirement Status'         | count=1
  'Refinancing Difficulty / Credit Risk'   | count=1
  'REFINANCING | HEDGING'                  | count=1
  'Corporate Strategy / Previous Engagement' | count=1
  'M&A'                                    | count=1
  'Sustainable Finance Engagement'         | count=1
  'Commodity Price Volatility Exposure'    | count=1
  'DEBT_MATURITY_SCHEDULE'                 | count=1
  'Recent Bond Issuance'                   | count=1
  'Interest Rate Risk Exposure & Pre-hedging Opportunity' | count=1
  'Debt Management / Corporate Finance Strategy' | count=1
  'Investment Program'                     | count=1
  'Financing Authorization/Availability'   | count=1
  'Commodity Price Volatility Impact'      | count=1
  'Confirmation of Recent Public Issuance' | count=1
  'Data Gap / Validation Required - Maturity Ladder Impact' | count=1
  'REFINANCING | LIQUIDITY | HEDGING'      | count=1
  'BOARD_AUTHORIZATION'                    | count=1
  'Conditional Interest Rate Hedging Opportunity' | count=1
  'RATE_HEDGE_ROLLOFF'                     | count=1
  'Internal Plan for Treasury Engagement'  | count=1
  'TREASURY_SCENARIO_REVIEW'               | count=1
  'Debt Origination / Acquisition Financing' | count=1
  'Need for Funding Requirement Reconciliation' | count=1
  'Foreign Exchange Exposure Review'       | count=1
  'Interest Rate Risk Management'          | count=1
  'Refinancing Blocked / Credit Risk'      | count=1
  'Internal Focus on Residual Funding Sequencing' | count=1
  'Debt Refinancing Requirements'          | count=1
  'Potential Future Funding Assessment'    | count=1
  'Cross-Asset Risk Coordination Assessment' | count=1
  'Green Project Eligibility Status'       | count=1
  'Debt Increase'                          | count=1
  'PUBLIC_ISSUANCE_COMPLETED'              | count=1
  'Funding Capacity Authorisation'         | count=1

=== All signals for CLI101 (Enel) with display fields ===
ID: SIG-3B377DD4
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: 'Enel Treasury Planning & Risk Review'
  trigger_summary  : 'Enel is entering a treasury planning window requiring a comprehensive review of funding, rates, sust'
  created_at       : 2026-09-09 06:46:49.854360

ID: SIG-069AF8DA
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: "Enel's €2.5B Dual-Tranche Senior Bond Issuance"
  trigger_summary  : "CaixaBank CIB acted as Joint Active Bookrunner for Enel's €2.5 billion dual-tranche senior bond issu"
  created_at       : 2026-09-07 13:22:23.052809

ID: SIG_CLI101_LATENT_03
  signal_type      : 'LATENT_OPPORTUNITY'
  metric_identified: None
  trigger_summary  : 'Potential future refinancing-cost and interest-rate-risk assessment'
  created_at       : 2026-09-07 06:36:30.783568

ID: SIG_CLI101_LATENT_01
  signal_type      : 'LATENT_OPPORTUNITY'
  metric_identified: None
  trigger_summary  : 'Potential residual funding-calendar and funding-mix review'
  created_at       : 2026-09-07 06:36:30.783568

ID: SIG_CLI101_LATENT_02
  signal_type      : 'LATENT_OPPORTUNITY'
  metric_identified: None
  trigger_summary  : 'Potential sustainable funding-format assessment'
  created_at       : 2026-09-07 06:36:30.783568

ID: SIG-63FC8944
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: '€1.0B Dual-Tranche Green & SLB Issuance'
  trigger_summary  : '€1.0B Dual-Tranche Green & SLB Issuance (€3.5B Pool / €10.13bn Debt Wall)'
  created_at       : 2026-09-02 01:30:54.133831

ID: SIG-5315C7AB
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: '€1.0B Dual-Tranche Green & SLB Issuance'
  trigger_summary  : '€1.0B Dual-Tranche Green & SLB Issuance (€3.5B Pool / €10.13bn Debt Wall)'
  created_at       : 2026-09-01 16:43:27.172558

ID: SIG-9FD91A1F
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: '€1.0B Dual-Tranche Green & SLB Issuance'
  trigger_summary  : '€1.0B Dual-Tranche Green & SLB Issuance (€3.5B Pool / €10.13bn Debt Wall)'
  created_at       : 2026-09-01 16:41:29.543463

ID: SIG-68A1FD24
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: '€10.13bn debt maturity wall & rising refinancing costs'
  trigger_summary  : 'Enel faces a €10.13bn debt maturity wall in 2026-2027 with significantly higher refinancing costs an'
  created_at       : 2026-08-31 04:32:56.798357

ID: SIG-2243E208
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: '€1.0B Dual-Tranche Green & SLB Issuance'
  trigger_summary  : '€1.0B Dual-Tranche Green & SLB Issuance (€3.5B Pool / €10.13bn Debt Wall)'
  created_at       : 2026-08-27 19:07:59.579283

ID: SIG-409F55E1
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: '€1.0B Dual-Tranche Green & SLB Issuance'
  trigger_summary  : '€1.0B Dual-Tranche Green & SLB Issuance (€3.5B Pool / €10.13bn Debt Wall)'
  created_at       : 2026-08-27 17:02:08.114512

ID: SIG-65634B7B
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: '€1.0B Dual-Tranche Green & SLB Issuance'
  trigger_summary  : '€1.0B Dual-Tranche Green & SLB Issuance (€3.5B Pool / €10.13bn Debt Wall)'
  created_at       : 2026-08-27 15:52:13.666790

ID: SIG-CC616165
  signal_type      : 'SUSTAINABLE FUNDING'
  metric_identified: 'Enel plans €4.0B hybrid green bond for capex & debt buybacks'
  trigger_summary  : 'Enel Finance International N.V. received board authorization to issue up to €4.0B in hybrid green bo'
  created_at       : 2026-08-23 16:48:13.001536

ID: SIG_EXT_12_5
  signal_type      : 'Corporate Strategy / Previous Engagement'
  metric_identified: 'N/A'
  trigger_summary  : 'Enel Group has engaged in Sustainability-Linked Finance activities.'
  created_at       : 2026-08-21 08:59:20.916391

ID: SIG_EXT_12_2
  signal_type      : 'Debt Increase'
  metric_identified: 'Event: Debt increase; Entity: Enel Américas; Period: Q2 2026; Date reported: 29 Jul 2026'
  trigger_summary  : 'Enel Américas, a subsidiary of Enel S.p.A., reported an increase in debt during Q2 2026.'
  created_at       : 2026-08-21 08:59:20.916391

ID: SIG_EXT_12_3
  signal_type      : 'Financing Authorization/Availability'
  metric_identified: 'Amount: €12 billion; Type: Financing; Entity: Enel; Date reported: 23 Feb 2026'
  trigger_summary  : 'Enel has opened €12 billion in financing.'
  created_at       : 2026-08-21 08:59:20.916391

ID: SIG_EXT_12_1
  signal_type      : 'Bond Issuance'
  metric_identified: 'Amount: €2.5 billion; Instrument: Bond; Issuer: Enel; Date reported: 12 Jul 2026'
  trigger_summary  : 'Enel executed a €2.5 billion bond sale.'
  created_at       : 2026-08-21 08:59:20.916391

ID: SIG_EXT_12_4
  signal_type      : 'Refinancing Blocked / Credit Risk'
  metric_identified: 'Event: Refinancing blocked; Reason: High debt risk; Entity: Enel Rio; Date reported: 22 Oct 2025'
  trigger_summary  : "A regulator blocked Enel Rio's refinancing due to high debt risk."
  created_at       : 2026-08-21 08:59:20.916391

ID: SIG_EXT_11_7
  signal_type      : 'Mandate Status'
  metric_identified: 'N/A'
  trigger_summary  : 'The current engagement with Enel is internally assessed as an opportunity hypothesis, not a DCM mand'
  created_at       : 2026-08-21 04:58:08.520945

ID: SIG_EXT_11_6
  signal_type      : 'Green Project Eligibility Status'
  metric_identified: 'N/A'
  trigger_summary  : 'There is a need to validate whether eligible green projects remain available for Enel.'
  created_at       : 2026-08-21 04:58:08.520945

### How to query the Signals which are actually running on the LIVE SIGNAL FEED
## Step 1: Run below command:-
SVC_URL=$(gcloud run services describe ing-fm-poc-service \
  --region europe-west1 \
  --project dulcet-radar-508218-c5 \
  --format "value(status.url)")

echo "Service URL: $SVC_URL"
## Output:-
user@ing-fm-dev-1:~/ing-fm-poc$ SVC_URL=$(gcloud run services describe ing-fm-poc-service \
  --region europe-west1 \
  --project dulcet-radar-508218-c5 \
  --format "value(status.url)")

echo "Service URL: $SVC_URL"
Service URL: https://ing-fm-poc-service-pjlcvlic6a-ew.a.run.app

## Step 2: Then run below Verification command:-
curl -s "$SVC_URL/api/signals" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Total signals: {len(data)}')
print()
seen = set()
for s in data:
    cid = s.get('client_id', '?')
    seen.add(cid)
    marker = '✓' if cid == 'CLI101' else '✗'
    stype = s.get('type', '?')
    headline = (s.get('headline') or '')[:70]
    print(f'  {marker} {cid:<10} | {stype:<26} | {headline}')
print()
print(f'Distinct client_ids: {sorted(seen)}')
"
## Output:-
user@ing-fm-dev-1:~/ing-fm-poc$ curl -s "$SVC_URL/api/signals" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Total signals: {len(data)}')
print()
seen = set()
for s in data:
    cid = s.get('client_id', '?')
    seen.add(cid)
    marker = '✓' if cid == 'CLI101' else '✗'
    stype = s.get('type', '?')
    headline = (s.get('headline') or '')[:70]
    print(f'  {marker} {cid:<10} | {stype:<26} | {headline}')
print()
"rint(f'Distinct client_ids: {sorted(seen)}')
Total signals: 12

  ✓ CLI101     | SUSTAINABLE FUNDING        | Enel's €2.5B Dual-Tranche Senior Bond Issuance
  ✓ CLI101     | SUSTAINABLE FUNDING        | Enel Treasury Planning & Risk Review
  ✓ CLI101     | SUSTAINABLE FUNDING        | €1.0B Dual-Tranche Green & SLB Issuance
  ✓ CLI101     | SUSTAINABLE FUNDING        | €10.13bn debt maturity wall & rising refinancing costs
  ✓ CLI101     | SUSTAINABLE FUNDING        | Enel plans €4.0B hybrid green bond for capex & debt buybacks
  ✓ CLI101     | BOARD AUTHORIZATION        | Board authorized up to €12bn of bond and bank financing through March 
  ✓ CLI101     | CLIENT VALIDATION          | Treasury confirmed active refinancing sequencing and liability managem
  ✓ CLI101     | DEBT MATURITY SCHEDULE     | Residual funding sequencing and liability management review required.
  ✓ CLI101     | PUBLIC ISSUANCE COMPLETED  | Completed USD issuance leaves residual EUR maturity wall.
  ✓ CLI101     | LATENT OPPORTUNITY         | Potential residual funding-calendar and funding-mix review
  ✓ CLI101     | LATENT OPPORTUNITY         | Potential sustainable funding-format assessment
  ✓ CLI101     | LATENT OPPORTUNITY         | Potential future refinancing-cost and interest-rate-risk assessment

Distinct client_ids: ['CLI101']
