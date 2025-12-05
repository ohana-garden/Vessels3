#!/bin/bash
# Wait for FalkorDB to be fully loaded
# Usage: ./wait-for-db.sh [host] [port] [timeout]

HOST="${1:-localhost}"
PORT="${2:-6379}"
TIMEOUT="${3:-60}"

echo "Waiting for FalkorDB at $HOST:$PORT (timeout: ${TIMEOUT}s)..."

START_TIME=$(date +%s)

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo "Timeout: FalkorDB not ready after ${TIMEOUT}s"
        exit 1
    fi

    # Check if we can ping
    if redis-cli -h "$HOST" -p "$PORT" ping 2>/dev/null | grep -q PONG; then
        # Check if module is loaded
        if redis-cli -h "$HOST" -p "$PORT" MODULE LIST 2>/dev/null | grep -qi "graph\|falkordb"; then
            # Check if loading is done
            if ! redis-cli -h "$HOST" -p "$PORT" INFO persistence 2>/dev/null | grep -q "loading:1"; then
                echo "FalkorDB is ready! (${ELAPSED}s elapsed)"
                exit 0
            fi
        fi
    fi

    sleep 1
done
