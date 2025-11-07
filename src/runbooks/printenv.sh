#!/bin/bash

# Print environment variables containing AKS or MONITOR
printenv | grep -E "AKS|MONITOR"

sleep 60
