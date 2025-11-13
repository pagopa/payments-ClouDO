#!/bin/bash

end=$((SECONDS + 5))

while [ $SECONDS -lt $end ]; do
    # Print environment variables containing AKS or MONITOR
    printenv | grep -E "AKS|MONITOR"
    echo "Test message at second: $SECONDS"
    sleep 1
done
