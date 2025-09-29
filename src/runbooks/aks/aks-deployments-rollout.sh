#!/bin/bash

# Script to log into AKS and perform a deployment rollout
# Required parameters:
# - Resource group name
# - AKS cluster name
# - Namespace
# - Deployment name

echo $#

# Check if required parameters are provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <namespace> <deployment-name>"
    exit 1
fi

NAMESPACE=$1
DEPLOYMENT_NAME=$2

# Perform deployment rollout
echo "Performing rollout for deployment $DEPLOYMENT_NAME in namespace $NAMESPACE..."
kubectl rollout restart deployment/$DEPLOYMENT_NAME -n $NAMESPACE

# Check rollout status
echo "Checking rollout status..."
kubectl rollout status deployment/$DEPLOYMENT_NAME -n $NAMESPACE
