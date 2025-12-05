#!/bin/bash
# Start Vessels application after ensuring FalkorDB is ready

set -e

FALKORDB_HOST="${FALKORDB_HOST:-localhost}"
FALKORDB_PORT="${FALKORDB_PORT:-6379}"
MAX_ATTEMPTS=60
ATTEMPT=1

echo "=== Vessels Startup Script ==="
echo "Waiting for FalkorDB at $FALKORDB_HOST:$FALKORDB_PORT..."

# Wait for FalkorDB to be fully loaded
while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    # Check basic connectivity
    if redis-cli -h "$FALKORDB_HOST" -p "$FALKORDB_PORT" ping 2>/dev/null | grep -q PONG; then
        # Check if FalkorDB module is loaded
        MODULE_CHECK=$(redis-cli -h "$FALKORDB_HOST" -p "$FALKORDB_PORT" MODULE LIST 2>/dev/null || echo "")

        if echo "$MODULE_CHECK" | grep -qi "graph\|falkordb"; then
            # Check if database is done loading from disk
            LOADING_CHECK=$(redis-cli -h "$FALKORDB_HOST" -p "$FALKORDB_PORT" INFO persistence 2>/dev/null | grep "loading:" || echo "loading:0")

            if echo "$LOADING_CHECK" | grep -q "loading:0"; then
                echo "FalkorDB is fully loaded and ready!"

                # Run a test query to ensure graph operations work
                TEST_RESULT=$(redis-cli -h "$FALKORDB_HOST" -p "$FALKORDB_PORT" GRAPH.QUERY __startup_test__ "RETURN 1" 2>/dev/null || echo "")

                if [ -n "$TEST_RESULT" ]; then
                    # Clean up test graph
                    redis-cli -h "$FALKORDB_HOST" -p "$FALKORDB_PORT" DEL __startup_test__ 2>/dev/null || true
                    echo "Graph operations verified successfully!"
                    break
                else
                    echo "Graph operations not yet available..."
                fi
            else
                echo "FalkorDB is still loading data from disk..."
            fi
        else
            echo "FalkorDB graph module not yet loaded..."
        fi
    else
        echo "FalkorDB not responding yet..."
    fi

    echo "Attempt $ATTEMPT/$MAX_ATTEMPTS - waiting 1 second..."
    sleep 1
    ((ATTEMPT++))
done

if [ $ATTEMPT -gt $MAX_ATTEMPTS ]; then
    echo "ERROR: FalkorDB failed to become ready after $MAX_ATTEMPTS attempts"
    exit 1
fi

# Print database info
echo ""
echo "=== FalkorDB Status ==="
redis-cli -h "$FALKORDB_HOST" -p "$FALKORDB_PORT" INFO server 2>/dev/null | grep -E "(redis_version|uptime_in_seconds)" || true
redis-cli -h "$FALKORDB_HOST" -p "$FALKORDB_PORT" MODULE LIST 2>/dev/null || true
echo ""

# Start Vessels API
echo "=== Starting Vessels API ==="
cd /app
exec python -m uvicorn vessels.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level "${VESSELS_LOG_LEVEL:-info}" \
    --access-log
