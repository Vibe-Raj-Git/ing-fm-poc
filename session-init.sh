#!/bin/bash

set -u

PROJECT_ID="dulcet-radar-508218-c5"
REGION_ID="${REGION:-europe-west1}"
SQL_INSTANCE_ID="${SQL_INSTANCE:-ing-postgres-db}"
CLOUD_RUN_SERVICE="${CLOUD_RUN_SERVICE:-ing-fm-poc-service}"

echo
echo "============================================================"
echo " ING Financial Markets AI Agentic Platform"
echo " Workstation Session Initialization"
echo "============================================================"
echo

# 1. GCP Authentication
echo "[1/6] Checking GCP authentication..."
if ! gcloud auth print-access-token >/dev/null 2>&1; then
    gcloud auth login
fi

# 2. Set Project & Region
echo "[2/6] Configuring GCP project and region..."
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud config set run/region "$REGION_ID" >/dev/null

export GCP_PROJECT="$PROJECT_ID"
export REGION="$REGION_ID"
export SQL_INSTANCE="$SQL_INSTANCE_ID"
export DB_USER="postgres"
export DB_NAME="postgres"

# 3. Auto-Retrieve DB Password from Secret Manager
echo "[3/6] Loading database credentials..."
RETRIEVED_PASS="$(gcloud secrets versions access latest --secret="db-postgres-pass" --project="$PROJECT_ID" 2>/dev/null)"

if [ -n "$RETRIEVED_PASS" ]; then
    export DB_PASS="$RETRIEVED_PASS"
    echo "  ✓ DB_PASS auto-loaded from Secret Manager."
elif [ -z "${DB_PASS:-}" ]; then
    read -rsp "Enter DB_PASS: " DB_PASS
    echo
    export DB_PASS
fi

# 4. Retrieve Cloud SQL Connection Name
echo "[4/6] Retrieving Cloud SQL connection string..."
INSTANCE_CONN_RESULT="$(gcloud sql instances describe "$SQL_INSTANCE" --project="$GCP_PROJECT" --format="value(connectionName)" 2>/dev/null)"

export INSTANCE_CONN="$INSTANCE_CONN_RESULT"
export INSTANCE_CONNECTION_NAME="$INSTANCE_CONN_RESULT"
export SQL_CONN="$INSTANCE_CONN_RESULT"

# 5. Auto-Start Cloud SQL Auth Proxy Daemon on Port 5432
echo "[5/6] Checking local Cloud SQL Auth Proxy daemon..."
mkdir -p "$HOME/bin"
if [ ! -f "$HOME/bin/cloud-sql-proxy" ]; then
    echo "  Downloading cloud-sql-proxy..."
    curl -s -o "$HOME/bin/cloud-sql-proxy" https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.0/cloud-sql-proxy.linux.amd64
    chmod +x "$HOME/bin/cloud-sql-proxy"
fi

if ! pgrep -f "cloud-sql-proxy" >/dev/null 2>&1; then
    if [ -n "$INSTANCE_CONN" ]; then
        "$HOME/bin/cloud-sql-proxy" --port 5432 "$INSTANCE_CONN" > /tmp/proxy.log 2>&1 &
        sleep 2
        echo "  ✓ Cloud SQL Auth Proxy started on 127.0.0.1:5432 (PID: $!)."
    fi
else
    echo "  ✓ Cloud SQL Auth Proxy is already active."
fi

# 6. Database Connectivity Verification
echo "[6/6] Verifying database connectivity..."
python3 - << 'PYEOF' 2>/dev/null
import os, pg8000.native
try:
    conn = pg8000.native.Connection(
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASS", ""),
        host="127.0.0.1",
        port=5432,
        database=os.environ.get("DB_NAME", "postgres")
    )
    print("  ✓ Database connection test: SUCCESSFUL")
    conn.close()
except Exception as e:
    print(f"  ✗ Database connection test failed: {e}")
PYEOF

# Check Cloud Run URL dynamically if deployed
SERVICE_URL_RESULT="$(gcloud run services describe "$CLOUD_RUN_SERVICE" --project="$GCP_PROJECT" --region="$REGION" --format="value(status.url)" 2>/dev/null)"
export SERVICE_URL="${SERVICE_URL_RESULT:-NOT DEPLOYED YET}"

echo
echo "============================================================"
echo " Project      : $GCP_PROJECT"
echo " SQL Conn     : $INSTANCE_CONN"
echo " Cloud Run URL: $SERVICE_URL"
echo "============================================================"
echo "✓ POC Environment Initialized | Ready to run deploy-poc"
echo "============================================================"
