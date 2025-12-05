#!/bin/bash
# Supervisor event listener for startup verification

read line
echo "READY"

while read line; do
    # Parse the event
    if echo "$line" | grep -q "SUPERVISOR_STATE_CHANGE_RUNNING"; then
        echo "Supervisor is running, all services should be starting..."
    fi
    echo "RESULT 2"
    echo "OK"
done
