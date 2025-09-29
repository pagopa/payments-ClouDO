#!/bin/bash

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

# Login to Azure and get AKS credentials
echo "Logging into Azure and connecting to AKS cluster..."
# Log in using managed identity
echo "Logging in with managed identity..."
if [[ -n "${AZURE_CLIENT_ID:-}" ]]; then
  if ! az login --identity --client-id "$AZURE_CLIENT_ID"; then
    echo "1 Failed to login with managed identity"
    exit 1
  fi
else
  if ! az login --identity; then
    echo "2 Failed to login with managed identity"
    exit 1
  fi
fi
# Optionally set the subscription if provided
if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" ]]; then
  echo "Setting subscription..."
  if ! az account set --subscription "$AZURE_SUBSCRIPTION_ID"; then
    echo "Failed to set subscription"
    exit 1
  fi
fi

az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME --overwrite-existing
kubelogin convert-kubeconfig -l azurecli

# Get TOKENNAME from aks cluster
TOKENNAME=`kubectl -n $NAMESPACE get serviceaccount/default -o jsonpath='{.secrets[0].name}'`

# Decode TOKENNAME
TOKEN=`kubectl -n $NAMESPACE get secret $TOKENNAME -o jsonpath='{.data.token}'| base64 --decode`

# Configure credential to user default service account for selected namespace
kubectl config set-credentials default --token=$TOKEN
kubectl config set-context --current --user=default
