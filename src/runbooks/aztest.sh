#!/bin/bash

kubectl -h

# Log in using managed identity
#echo "Logging in with managed identity..."
#if ! az login --identity; then
#    echo "Failed to login with managed identity"
#    exit 1
#fi
#
## Verify login by listing subscriptions
#echo "Verifying login by listing subscriptions..."
#if ! az account list --query "[].name" -o tsv; then
#    echo "Failed to list subscriptions"
#    exit 1
#fi
#
#echo "Login successful and verified"
