#!/usr/bin/env bash
set -euo pipefail

CONN_STR="${AZURITE_CONNECTION_STRING:-DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;}"
TABLE_NAME="RunbookSchemas"
WORKER="${1:-worker}"

command -v az >/dev/null 2>&1 || { echo "Error: 'az' not found in PATH"; exit 1; }

echo "Creating table '${TABLE_NAME}' (idempotent)..."
az storage table create \
  --name "${TABLE_NAME}" \
  --connection-string "${CONN_STR}" \
  --only-show-errors >/dev/null

echo "Upserting test entity PK='test' RK='test-0001'..."
az storage entity insert \
  --table-name "${TABLE_NAME}" \
  --entity \
    PartitionKey=test \
    RowKey=test-0001 \
    id="test" \
    name=test-entity \
    description='Hello Test!' \
    runbook=check_sys.sh \
    run_args="-n 5000 --repeats 100" \
    url="http://$WORKER/api/Runbook" \
    oncall=false \
  --if-exists merge \
  --connection-string "${CONN_STR}" \
  --only-show-errors >/dev/null

echo "Upserting test entity PK='test-2' RK='test-0002'..."
az storage entity insert \
  --table-name "${TABLE_NAME}" \
  --entity \
    PartitionKey=test-2 \
    RowKey=test-0002 \
    id="test-2" \
    name=test-entity-2 \
    description='Hello Test 2!' \
    runbook=test.py \
    url="http://$WORKER/api/Runbook" \
    oncall=false \
  --if-exists merge \
  --connection-string "${CONN_STR}" \
  --only-show-errors >/dev/null

echo "Upserting test entity PK='test-3' RK='test-0003'..."
az storage entity insert \
  --table-name "${TABLE_NAME}" \
  --entity \
    PartitionKey=test-3 \
    RowKey=test-0003 \
    id="11111111-2222-3333-4444-555555555555" \
    name=test-entity-3 \
    description='Hello Test 3!' \
    runbook=check_sys.sh \
    url="http://$WORKER/api/Runbook" \
    oncall=false \
  --if-exists merge \
  --connection-string "${CONN_STR}" \
  --only-show-errors >/dev/null

echo "Done."
