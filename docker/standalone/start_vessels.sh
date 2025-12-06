#!/bin/bash
# Vessels startup script - waits for FalkorDB to be ready before starting

set -e

FALKORDB_PORT=${FALKORDB_PORT:-6379}
MAX_ATTEMPTS=60
ATTEMPT=1

echo "=== Vessels Startup Script ==="
echo "Waiting for FalkorDB to be fully loaded..."

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    # Check if redis is responding
    if redis-cli -p $FALKORDB_PORT ping 2>/dev/null | grep -q PONG; then
        # Check if FalkorDB module is loaded
        if redis-cli -p $FALKORDB_PORT MODULE LIST 2>/dev/null | grep -qi "graph\|falkordb"; then
            # Check if not still loading from disk
            if ! redis-cli -p $FALKORDB_PORT INFO persistence 2>/dev/null | grep -q "loading:1"; then
                # Test a graph query
                if redis-cli -p $FALKORDB_PORT GRAPH.QUERY __startup_test__ "RETURN 1" 2>/dev/null | grep -q "1"; then
                    redis-cli -p $FALKORDB_PORT DEL __startup_test__ 2>/dev/null || true
                    echo ""
                    echo "FalkorDB is fully loaded and ready!"
                    echo ""

                    # Print FalkorDB info
                    echo "FalkorDB Status:"
                    redis-cli -p $FALKORDB_PORT INFO server 2>/dev/null | grep -E "(redis_version|uptime)" | head -3 || true
                    echo ""

                    # Start Vessels
                    echo "Starting Vessels Web UI..."
                    cd /vessels
                    exec python run_ui.py
                fi
            fi
        fi
    fi

    echo -n "."
    sleep 1
    ((ATTEMPT++))
done

echo ""
echo "ERROR: FalkorDB did not become ready after $MAX_ATTEMPTS seconds"
echo "Starting Vessels anyway (may have limited functionality)..."
cd /vessels
exec python run_ui.py
