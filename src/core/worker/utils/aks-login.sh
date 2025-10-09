#!/bin/bash
set -euo pipefail

# Script to login into AKS with dedicated service account
# Required parameters:
# - Resource group name
# - AKS cluster name
# - Namespace

# Check if required parameters are provided
if [ $# -ne 3 ]; then
  echo "Usage: $0 <resource-group> <cluster-name> <namespace>"
  exit 1
fi

RESOURCE_GROUP=$1
CLUSTER_NAME=$2
NAMESPACE=$3

# Login to Azure using Managed Identity (non-interactive)
if [[ -n "${AZURE_CLIENT_ID:-}" ]]; then
  az login --identity --client-id "$AZURE_CLIENT_ID"
else
  az login --identity
fi

# Optionally set the Azure subscription if provided
if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" ]]; then
  az account set --subscription "$AZURE_SUBSCRIPTION_ID"
fi

# Retrieve AKS kubeconfig for the specified cluster
az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$CLUSTER_NAME" --overwrite-existing

# Convert kubeconfig to use MSI with kubelogin to avoid interactive prompts
if [[ -n "${AZURE_CLIENT_ID:-}" ]]; then
  kubelogin convert-kubeconfig -l msi --client-id "$AZURE_CLIENT_ID"
else
  kubelogin convert-kubeconfig -l msi
fi

# Restrict current context to the requested namespace (no user changes, no resources created)
kubectl config set-context --current --namespace="$NAMESPACE"

echo "AKS login ready for namespace: $NAMESPACE"
