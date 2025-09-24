#!/bin/bash

# Script to log into AKS and perform a deployment rollout
# Required parameters:
# - Resource group name
# - AKS cluster name
# - Namespace
# - Deployment name

# Check if required parameters are provided
if [ $# -ne 4 ]; then
    echo "Usage: $0 <resource-group> <cluster-name> <namespace> <deployment-name>"
    exit 1
fi

RESOURCE_GROUP=$1
CLUSTER_NAME=$2
NAMESPACE=$3
DEPLOYMENT_NAME=$4

# Login to Azure and get AKS credentials
echo "Logging into Azure and connecting to AKS cluster..."
az login
az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME --overwrite-existing

# Perform deployment rollout
echo "Performing rollout for deployment $DEPLOYMENT_NAME in namespace $NAMESPACE..."
kubectl rollout restart deployment/$DEPLOYMENT_NAME -n $NAMESPACE

# Check rollout status
echo "Checking rollout status..."
kubectl rollout status deployment/$DEPLOYMENT_NAME -n $NAMESPACE
