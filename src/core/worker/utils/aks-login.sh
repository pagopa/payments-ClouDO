# shell
#!/bin/bash
set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 <resource-group> <cluster-name> <namespace>"
  exit 1
fi

RESOURCE_GROUP=$1
CLUSTER_NAME=$2
NAMESPACE=$3
TOKEN_TTL=600  # token valid for 10 minutes

log() { echo "[aks-login] $*"; }

# Azure login (Managed Identity, non-interactive)
log "Azure login with Managed Identity..."
if [[ -n "${AZURE_CLIENT_ID:-}" ]]; then
  az login --identity --client-id "$AZURE_CLIENT_ID" 1>/dev/null
else
  az login --identity 1>/dev/null
fi

# Optional subscription
if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" ]]; then
  log "Setting subscription: ${AZURE_SUBSCRIPTION_ID}"
  az account set --subscription "$AZURE_SUBSCRIPTION_ID"
fi

# Fetch kubeconfig
log "Fetching AKS credentials for ${CLUSTER_NAME}..."
az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$CLUSTER_NAME" --overwrite-existing

# Convert kubeconfig to MSI with token TTL 10 minutes
log "Converting kubeconfig to MSI via kubelogin (force, token ${TOKEN_TTL}s)..."
if [[ -n "${AZURE_CLIENT_ID:-}" ]]; then
  kubelogin convert-kubeconfig -l msi --client-id "$AZURE_CLIENT_ID" --token-expiry "$TOKEN_TTL" --force
else
  kubelogin convert-kubeconfig -l msi --token-expiry "$TOKEN_TTL" --force
fi

# Limit context to the target namespace
kubectl config set-context --current --namespace="$NAMESPACE"

# Probe non-interactive access
set +e
kubectl get --raw=/readyz 1>/dev/null 2>&1
READY_RC=$?
set -e

if [[ $READY_RC -ne 0 ]]; then
  log "Probe failed; applying exec-plugin fallback with token ${TOKEN_TTL}s..."

  USER_NAME="msi-${CLUSTER_NAME}"

  if [[ -n "${AZURE_CLIENT_ID:-}" ]]; then
    kubectl config set-credentials "$USER_NAME" \
      --exec-command=kubelogin \
      --exec-api-version=client.authentication.k8s.io/v1beta1 \
      --exec-arg=get-token \
      --exec-arg=--login \
      --exec-arg=msi \
      --exec-arg=--client-id \
      --exec-arg="$AZURE_CLIENT_ID" \
      --exec-arg=--token-expiry \
      --exec-arg="$TOKEN_TTL"
  else
    kubectl config set-credentials "$USER_NAME" \
      --exec-command=kubelogin \
      --exec-api-version=client.authentication.k8s.io/v1beta1 \
      --exec-arg=get-token \
      --exec-arg=--login \
      --exec-arg=msi \
      --exec-arg=--token-expiry \
      --exec-arg="$TOKEN_TTL"
  fi

  CURRENT_CONTEXT="$(kubectl config current-context)"
  kubectl config set-context "$CURRENT_CONTEXT" --user="$USER_NAME" --namespace="$NAMESPACE"

  set +e
  kubectl get --raw=/readyz 1>/dev/null 2>&1
  READY_RC=$?
  set -e

  if [[ $READY_RC -ne 0 ]]; then
    log "Still failing to authenticate non-interactively. Check RBAC/permissions."
    exit 1
  fi
fi

log "AKS login completed (non-interactive, token valid 10 minutes) for namespace: $NAMESPACE"
