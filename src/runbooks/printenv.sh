#!/bin/bash

end=$((SECONDS + 5))

printenv | grep -E "AKS|MONITOR|CLOUDO"
while [ $SECONDS -lt $end ]; do
    # Print environment variables containing AKS or MONITOR
    echo "Test message at second: $SECONDS"
    sleep 5
done
