#!/bin/bash

end=$((SECONDS + 5))

printenv | grep -E "AKS|MONITOR"
while [ $SECONDS -lt $end ]; do
    # Print environment variables containing AKS or MONITOR
    echo "Test message at second: $SECONDS"
    sleep 1
done
