import sys
import os

# Ensure we can import from main.py
sys.path.insert(0, os.path.dirname(__file__))

from main import get_db_connection

def insert_surgical_test_signal():
    conn, connector = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            insert_query = """
            INSERT INTO ca.digital_twin_signals (
                signal_id, client_id, catalog_family, signal_type, 
                metric_identified, trigger_summary, metric_value, 
                description, confidence_pct, urgency, created_at
            ) VALUES (
                'SIG_BASF_TEST_103', 'CLI103', 'Financing/Capital Markets', 'TEST_INJECTION',
                '€500M Surgical Test', 'BASF test insertion for Master Reset validation', '€500M',
                'Verifying that reset clears UI state while preserving table rows.', 95, 'High', NOW()
            )
            ON CONFLICT (signal_id) DO NOTHING;
            """
            cur.execute(insert_query)
            conn.commit()
            print("Successfully inserted surgical test signal for BASF (CLI103).")
            cur.close()
            conn.close()
            if connector:
                connector.close()
        except Exception as e:
            print(f"Database insertion failed: {e}")
    else:
        print("Failed to obtain database connection.")

if __name__ == "__main__":
    insert_surgical_test_signal()