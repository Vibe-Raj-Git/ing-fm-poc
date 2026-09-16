# enrich_basf_baseline.py
#
# Idempotent utility: inserts the curated BASF (CLI103) baseline rows into
# ca.digital_twin_signals and ca.document_vector_chunks.
#
# Safe to re-run:
#   - Signals use ON CONFLICT (signal_id) DO UPDATE
#   - Chunks check for existing (client_id, source_channel, source_name) before inserting
#
# Scope: CLI103 only. Does not touch any other client.
# Read-only against ca.ca_opportunity_scoring, ca.ext_company_filings, etc.
#
# Run with: python3 enrich_basf_baseline.py

import sys
import json
from datetime import datetime

sys.path.insert(0, "/home/user/ing-fm-poc")
from main import get_db_connection


CLIENT_ID = "CLI103"


SIGNALS = [
    {
        "signal_id": "SIG_BASF_BOARD_AUTH_01",
        "catalog_family": "Financing/Capital Markets",
        "signal_type": "BOARD_AUTHORIZATION",
        "metric_identified": "€4.0bn FY26/27 financing capacity",
        "metric_value": "€4.0bn",
        "trigger_summary": "Board approved accelerated debt rollover programme up to €4.0bn through March 2027",
        "description": "Executive Committee authorisation covers €4.0B Senior EMTN benchmark issuance and €1.2B IRS pre-hedge.",
        "confidence_pct": 96,
        "urgency": "High",
    },
    {
        "signal_id": "SIG_BASF_LATENT_01",
        "catalog_family": "Interest Rate",
        "signal_type": "LATENT_OPPORTUNITY",
        "metric_identified": "Pre-hedge IRS window",
        "metric_value": "€1.2B 6Y IRS",
        "trigger_summary": "Lock pre-hedge swap before ECB policy revision",
        "description": "Pre-hedge interest rate swap window and bond issuance advisory.",
        "confidence_pct": 92,
        "urgency": "High",
    },
    {
        "signal_id": "SIG_BASF_LATENT_02",
        "catalog_family": "Financing/Capital Markets",
        "signal_type": "LATENT_OPPORTUNITY",
        "metric_identified": "EMTN issuance timing",
        "metric_value": "€4.0B EMTN",
        "trigger_summary": "Benchmark issuance timing ahead of 2027 maturity wall",
        "description": "Refinancing window aligned with €3.0bn 2027 maturity and €5.5bn 2028 syndicated loan.",
        "confidence_pct": 88,
        "urgency": "Medium",
    },
    {
        "signal_id": "SIG_BASF_LATENT_03",
        "catalog_family": "Sustainable Finance",
        "signal_type": "LATENT_OPPORTUNITY",
        "metric_identified": "Greenium opportunity",
        "metric_value": "-5 bps greenium",
        "trigger_summary": "First BASF green tranche eligible for pricing concession",
        "description": "Coatings carve-out proceeds enable green tranche alignment with ICMA Green Bond Principles.",
        "confidence_pct": 85,
        "urgency": "Medium",
    },
]


CHUNKS = [
    {
        "chunk_id": 9000001,
        "source_channel": "WORKFABRIC_MEMO",
        "source_name": "Luca Moretti (DCM Origination)",
        "text_content": (
            "WORKFABRIC DCM MEMO: BASF SE — treasury has authorised accelerated "
            "rollover. Recommend immediate €4.0B 6Y EMTN + €1.2B 6Y IRS pre-hedge "
            "overlay before ECB policy revision. Coatings carve-out proceeds "
            "provide optionality for green tranche structure."
        ),
        "structured_metadata": None,
    },
    {
        "chunk_id": 9000002,
        "source_channel": "HOUSEVIEW",
        "source_name": "ING Chemicals Sector Strategy — Q3 2026",
        "text_content": (
            "ING Research view: European chemicals sector funding conditions "
            "have stabilised around 5Y EUR Swap 2.62% with BBB-rated issuers "
            "trading at 118-122 bps. BASF's fixed coverage decline from 68% to "
            "46% against 60% policy target requires immediate liability "
            "management. The Carlyle-led €7.7bn Coatings carve-out creates a "
            "natural window for benchmark issuance with potential -5 bps "
            "greenium on inaugural green tranche."
        ),
        "structured_metadata": {
            "company_name": "BASF SE",
            "executive_summary": (
                "Chemicals sector funding stabilised; BASF coverage policy "
                "breach requires immediate refinancing."
            ),
            "detected_signals": [
                {
                    "signal_type": "Refinancing Window",
                    "catalog_family": "Financing/Capital Markets",
                    "metric_identified": "€4.0B EMTN benchmark",
                    "confidence_pct": 92,
                }
            ],
        },
    },
    {
        "chunk_id": 9000003,
        "source_channel": "CLIENT_EMAIL",
        "source_name": "BASF Group Treasury (Claudia Meier)",
        "text_content": (
            "Subject: 2026/2027 Rollover Coordination — Following Executive "
            "Committee approval, we are initiating a €4.0B Senior EMTN "
            "benchmark issuance process. Request ING proposal for dual-tranche "
            "structure including an inaugural green tranche. Targeting pricing "
            "window aligned with 5Y EUR Swap at 2.62% and current 120 bps "
            "credit spread."
        ),
        "structured_metadata": None,
    },
    {
        "chunk_id": 9000004,
        "source_channel": "TEAMS_CHAT",
        "source_name": "European Chemicals Coverage (#deal-coverage-basf)",
        "text_content": (
            "MS TEAMS TRANSCRIPT: [10:14] Anna Keller (RM): Treasury flagged the "
            "fixed coverage decline 68%% to 46%% against 60%% policy target. "
            "[10:15] Luca Moretti (DCM): Recommend immediate EMTN issuance timing. "
            "[10:16] Roman Weiss (Rates): Structure 6Y pre-hedge IRS overlay."
        ),
        "structured_metadata": None,
    },
]


def upsert_signals(cur):
    inserted = 0
    for sig in SIGNALS:
        cur.execute("""
            INSERT INTO ca.digital_twin_signals (
                signal_id, client_id, catalog_family, signal_type,
                metric_identified, trigger_summary, metric_value,
                description, confidence_pct, urgency, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (signal_id) DO UPDATE SET
                client_id = EXCLUDED.client_id,
                catalog_family = EXCLUDED.catalog_family,
                signal_type = EXCLUDED.signal_type,
                metric_identified = EXCLUDED.metric_identified,
                trigger_summary = EXCLUDED.trigger_summary,
                metric_value = EXCLUDED.metric_value,
                description = EXCLUDED.description,
                confidence_pct = EXCLUDED.confidence_pct,
                urgency = EXCLUDED.urgency,
                created_at = NOW();
        """, (
            sig["signal_id"], CLIENT_ID,
            sig["catalog_family"], sig["signal_type"],
            sig["metric_identified"], sig["trigger_summary"],
            sig["metric_value"], sig["description"],
            sig["confidence_pct"], sig["urgency"],
        ))
        inserted += 1
    return inserted


def upsert_chunks(cur):
    inserted = 0
    skipped = 0
    for ch in CHUNKS:
        # Idempotency check: has this exact chunk already been created?
        cur.execute("""
            SELECT chunk_id FROM ca.document_vector_chunks
            WHERE client_id = %s
              AND source_channel = %s
              AND source_name = %s
            LIMIT 1
        """, (CLIENT_ID, ch["source_channel"], ch["source_name"]))
        existing = cur.fetchone()

        meta_payload = ch["structured_metadata"]
        if isinstance(meta_payload, (dict, list)):
            meta_payload = json.dumps(meta_payload)

        if existing:
            # Refresh content + timestamp on the existing row so it wins the sort
            cur.execute("""
                UPDATE ca.document_vector_chunks
                SET text_content = %s,
                    structured_metadata = %s,
                    created_at = NOW()
                WHERE chunk_id = %s
            """, (ch["text_content"], meta_payload, existing[0]))
            skipped += 1
        else:
            cur.execute("""
                INSERT INTO ca.document_vector_chunks (
                    client_id, source_channel, source_name,
                    text_content, structured_metadata, created_at
                ) VALUES (%s, %s, %s, %s, %s, NOW())
            """, (
                CLIENT_ID, ch["source_channel"], ch["source_name"],
                ch["text_content"], meta_payload,
            ))
            inserted += 1
    return inserted, skipped


def main():
    conn, connector = get_db_connection()
    if not conn:
        raise SystemExit("DB connection failed")

    try:
        cur = conn.cursor()

        # --- Pre-flight: confirm BASF exists ---
        cur.execute("SELECT client_id, client_name FROM ca.client_master WHERE client_id = %s", (CLIENT_ID,))
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"{CLIENT_ID} not found in ca.client_master")
        print(f"Target client: {row[0]} — {row[1]}")

        # --- Insert signals ---
        sig_count = upsert_signals(cur)
        print(f"Signals upserted: {sig_count}")

        # --- Insert chunks ---
        ins, skip = upsert_chunks(cur)
        print(f"Chunks inserted: {ins}  |  Chunks refreshed: {skip}")

        conn.commit()

        # --- Verification query ---
        print()
        print("=== Verification ===")
        cur.execute("""
            SELECT signal_id, signal_type, metric_value, created_at
            FROM ca.digital_twin_signals
            WHERE client_id = %s
              AND signal_id IN ('SIG_BASF_BOARD_AUTH_01', 'SIG_BASF_LATENT_01',
                                'SIG_BASF_LATENT_02', 'SIG_BASF_LATENT_03')
            ORDER BY signal_id
        """, (CLIENT_ID,))
        for r in cur.fetchall():
            print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]}")

        print()
        cur.execute("""
            SELECT chunk_id, source_channel, source_name, created_at
            FROM ca.document_vector_chunks
            WHERE client_id = %s
              AND source_name IN (
                'Luca Moretti (DCM Origination)',
                'ING Chemicals Sector Strategy — Q3 2026',
                'BASF Group Treasury (Claudia Meier)'
              )
            ORDER BY chunk_id
        """, (CLIENT_ID,))
        for r in cur.fetchall():
            print(f"  chunk_id={r[0]} | {r[1]} | {r[2]} | {r[3]}")

        cur.close()
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        raise
    finally:
        try: conn.close()
        except Exception: pass
        if connector:
            try: connector.close()
            except Exception: pass


if __name__ == "__main__":
    main()