#!/bin/bash

# Print environment variables containing AKS or MONITOR
printenv | grep -E "AKS|MONITOR"

kubectl get pods -n $AKS_NAMESPACE
