#!/bin/bash

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

# Verify login by listing subscriptions
echo "Verifying login by listing subscriptions..."
if ! az account list --query "[].name" -o tsv; then
  echo "Failed to list subscriptions"
  exit 1
fi

az group list --query "[].{Name:name, Location:location}" -o table
echo "Login successful and verified"
