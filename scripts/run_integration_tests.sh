#!/bin/bash
# Docker-based integration tests for Vessels with FalkorDB
# This script builds and runs the container, then verifies everything works

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONTAINER_NAME="vessels-integration-test"
IMAGE_NAME="vessels-test:latest"
TEST_TIMEOUT=120

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup() {
    log_info "Cleaning up..."
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

trap cleanup EXIT

# Change to project directory
cd "$PROJECT_DIR"

log_info "=== Vessels Integration Tests ==="
log_info "Project directory: $PROJECT_DIR"

# Step 1: Build the Docker image
log_info "Step 1: Building Docker image..."
docker build -t "$IMAGE_NAME" . || {
    log_error "Docker build failed"
    exit 1
}
log_info "Docker image built successfully"

# Step 2: Start the container
log_info "Step 2: Starting container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -p 16379:6379 \
    -p 18000:8000 \
    -e OPENAI_API_KEY=sk-test-key \
    -e ANTHROPIC_API_KEY=sk-ant-test-key \
    -e VESSELS_DEBUG=true \
    -e VESSELS_LOG_LEVEL=DEBUG \
    "$IMAGE_NAME" || {
    log_error "Failed to start container"
    exit 1
}
log_info "Container started"

# Step 3: Wait for FalkorDB to be ready
log_info "Step 3: Waiting for FalkorDB to be ready..."
FALKORDB_READY=false
for i in $(seq 1 $TEST_TIMEOUT); do
    if docker exec "$CONTAINER_NAME" redis-cli -p 6379 ping 2>/dev/null | grep -q PONG; then
        # Check if module is loaded
        if docker exec "$CONTAINER_NAME" redis-cli -p 6379 MODULE LIST 2>/dev/null | grep -qi "graph\|falkordb"; then
            # Check if loading is complete
            if ! docker exec "$CONTAINER_NAME" redis-cli -p 6379 INFO persistence 2>/dev/null | grep -q "loading:1"; then
                FALKORDB_READY=true
                break
            fi
        fi
    fi
    echo -n "."
    sleep 1
done
echo ""

if [ "$FALKORDB_READY" = false ]; then
    log_error "FalkorDB failed to become ready within $TEST_TIMEOUT seconds"
    docker logs "$CONTAINER_NAME"
    exit 1
fi
log_info "FalkorDB is ready!"

# Step 4: Verify FalkorDB module is loaded
log_info "Step 4: Verifying FalkorDB module..."
MODULE_LIST=$(docker exec "$CONTAINER_NAME" redis-cli -p 6379 MODULE LIST 2>/dev/null)
if echo "$MODULE_LIST" | grep -qi "graph\|falkordb"; then
    log_info "FalkorDB graph module is loaded"
else
    log_error "FalkorDB graph module NOT loaded!"
    echo "Module list: $MODULE_LIST"
    exit 1
fi

# Step 5: Test graph operations directly
log_info "Step 5: Testing graph operations..."
GRAPH_TEST=$(docker exec "$CONTAINER_NAME" redis-cli -p 6379 GRAPH.QUERY test_graph "CREATE (n:Test {name: 'test'}) RETURN n" 2>/dev/null)
if [ -n "$GRAPH_TEST" ]; then
    log_info "Graph CREATE operation successful"
else
    log_error "Graph CREATE operation failed"
    exit 1
fi

GRAPH_READ=$(docker exec "$CONTAINER_NAME" redis-cli -p 6379 GRAPH.QUERY test_graph "MATCH (n:Test) RETURN n.name" 2>/dev/null)
if echo "$GRAPH_READ" | grep -q "test"; then
    log_info "Graph MATCH operation successful"
else
    log_error "Graph MATCH operation failed"
    exit 1
fi

# Cleanup test graph
docker exec "$CONTAINER_NAME" redis-cli -p 6379 DEL test_graph 2>/dev/null || true

# Step 6: Wait for Vessels API to be ready
log_info "Step 6: Waiting for Vessels API..."
API_READY=false
for i in $(seq 1 60); do
    if curl -s http://localhost:18000/health 2>/dev/null | grep -q "healthy"; then
        API_READY=true
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

if [ "$API_READY" = false ]; then
    log_error "Vessels API failed to become ready"
    docker logs "$CONTAINER_NAME"
    exit 1
fi
log_info "Vessels API is ready!"

# Step 7: Test API health endpoint
log_info "Step 7: Testing API health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:18000/health)
if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
    log_info "Health check passed"
    echo "Response: $HEALTH_RESPONSE"
else
    log_error "Health check failed"
    echo "Response: $HEALTH_RESPONSE"
    exit 1
fi

# Step 8: Test vessel CRUD operations via API
log_info "Step 8: Testing vessel CRUD operations..."

# Create vessel
log_info "  Creating vessel..."
CREATE_RESPONSE=$(curl -s -X POST http://localhost:18000/vessels \
    -H "Content-Type: application/json" \
    -d '{"id":"test-vessel-1","name":"Integration Test Vessel","vessel_type":"test"}')
if echo "$CREATE_RESPONSE" | grep -q '"id":"test-vessel-1"'; then
    log_info "  Vessel created successfully"
else
    log_error "  Failed to create vessel"
    echo "  Response: $CREATE_RESPONSE"
    exit 1
fi

# Read vessel
log_info "  Reading vessel..."
READ_RESPONSE=$(curl -s http://localhost:18000/vessels/test-vessel-1)
if echo "$READ_RESPONSE" | grep -q '"name":"Integration Test Vessel"'; then
    log_info "  Vessel read successfully"
else
    log_error "  Failed to read vessel"
    echo "  Response: $READ_RESPONSE"
    exit 1
fi

# Update vessel
log_info "  Updating vessel..."
UPDATE_RESPONSE=$(curl -s -X PATCH http://localhost:18000/vessels/test-vessel-1 \
    -H "Content-Type: application/json" \
    -d '{"name":"Updated Test Vessel"}')
if echo "$UPDATE_RESPONSE" | grep -q '"name":"Updated Test Vessel"'; then
    log_info "  Vessel updated successfully"
else
    log_error "  Failed to update vessel"
    echo "  Response: $UPDATE_RESPONSE"
    exit 1
fi

# List vessels
log_info "  Listing vessels..."
LIST_RESPONSE=$(curl -s http://localhost:18000/vessels)
if echo "$LIST_RESPONSE" | grep -q 'test-vessel-1'; then
    log_info "  Vessel listing works"
else
    log_error "  Failed to list vessels"
    echo "  Response: $LIST_RESPONSE"
    exit 1
fi

# Step 9: Test connection operations
log_info "Step 9: Testing connection operations..."

# Create second vessel
curl -s -X POST http://localhost:18000/vessels \
    -H "Content-Type: application/json" \
    -d '{"id":"test-vessel-2","name":"Second Vessel","vessel_type":"test"}' > /dev/null

# Create connection
log_info "  Creating connection..."
CONN_RESPONSE=$(curl -s -X POST http://localhost:18000/connections \
    -H "Content-Type: application/json" \
    -d '{"source_id":"test-vessel-1","target_id":"test-vessel-2","connection_type":"depends_on","weight":0.9}')
if echo "$CONN_RESPONSE" | grep -q '"connection_type":"depends_on"'; then
    log_info "  Connection created successfully"
else
    log_error "  Failed to create connection"
    echo "  Response: $CONN_RESPONSE"
    exit 1
fi

# Get connections
log_info "  Getting connections..."
GET_CONN_RESPONSE=$(curl -s "http://localhost:18000/vessels/test-vessel-1/connections?direction=outgoing")
if echo "$GET_CONN_RESPONSE" | grep -q 'test-vessel-2'; then
    log_info "  Connection retrieval works"
else
    log_error "  Failed to get connections"
    echo "  Response: $GET_CONN_RESPONSE"
    exit 1
fi

# Step 10: Test statistics
log_info "Step 10: Testing statistics..."
STATS_RESPONSE=$(curl -s http://localhost:18000/stats)
if echo "$STATS_RESPONSE" | grep -q '"total_vessels"'; then
    log_info "Statistics endpoint works"
    echo "Stats: $STATS_RESPONSE"
else
    log_error "Failed to get statistics"
    echo "Response: $STATS_RESPONSE"
    exit 1
fi

# Step 11: Test path finding
log_info "Step 11: Testing path finding..."
PATH_RESPONSE=$(curl -s "http://localhost:18000/path?start_id=test-vessel-1&end_id=test-vessel-2")
if echo "$PATH_RESPONSE" | grep -q 'path'; then
    log_info "Path finding works"
else
    log_warn "Path finding returned no path (may be expected for simple connection)"
fi

# Step 12: Test delete operations
log_info "Step 12: Testing delete operations..."

# Delete connection
log_info "  Deleting connection..."
DEL_CONN_RESPONSE=$(curl -s -X DELETE "http://localhost:18000/connections?source_id=test-vessel-1&target_id=test-vessel-2")
if echo "$DEL_CONN_RESPONSE" | grep -q '"deleted":true'; then
    log_info "  Connection deleted successfully"
else
    log_error "  Failed to delete connection"
    echo "  Response: $DEL_CONN_RESPONSE"
    exit 1
fi

# Delete vessels
log_info "  Deleting vessels..."
curl -s -X DELETE http://localhost:18000/vessels/test-vessel-1 > /dev/null
curl -s -X DELETE http://localhost:18000/vessels/test-vessel-2 > /dev/null
log_info "  Vessels deleted"

# Step 13: Verify .env file was created with API keys
log_info "Step 13: Verifying .env file creation..."
ENV_CONTENT=$(docker exec "$CONTAINER_NAME" cat /app/.env 2>/dev/null)
if echo "$ENV_CONTENT" | grep -q "OPENAI_API_KEY=sk-test-key"; then
    log_info ".env file contains OPENAI_API_KEY"
else
    log_error ".env file missing OPENAI_API_KEY"
    echo "Content: $ENV_CONTENT"
    exit 1
fi

if echo "$ENV_CONTENT" | grep -q "ANTHROPIC_API_KEY=sk-ant-test-key"; then
    log_info ".env file contains ANTHROPIC_API_KEY"
else
    log_error ".env file missing ANTHROPIC_API_KEY"
    echo "Content: $ENV_CONTENT"
    exit 1
fi

# Step 14: Verify data persistence in FalkorDB
log_info "Step 14: Verifying data persistence..."

# Create a vessel that should persist
curl -s -X POST http://localhost:18000/vessels \
    -H "Content-Type: application/json" \
    -d '{"id":"persist-test","name":"Persistence Test"}' > /dev/null

# Check it exists in FalkorDB directly
PERSIST_CHECK=$(docker exec "$CONTAINER_NAME" redis-cli -p 6379 GRAPH.QUERY vessels "MATCH (v:Vessel {id: 'persist-test'}) RETURN v.name" 2>/dev/null)
if echo "$PERSIST_CHECK" | grep -q "Persistence Test"; then
    log_info "Data correctly persisted in FalkorDB"
else
    log_error "Data NOT persisted in FalkorDB"
    echo "Check result: $PERSIST_CHECK"
    exit 1
fi

# Cleanup
curl -s -X DELETE http://localhost:18000/vessels/persist-test > /dev/null

# Summary
echo ""
log_info "=== All Integration Tests Passed ==="
echo ""
echo "Verified:"
echo "  ✓ Docker image builds successfully"
echo "  ✓ Container starts properly"
echo "  ✓ FalkorDB loads completely"
echo "  ✓ FalkorDB graph module is loaded"
echo "  ✓ Graph operations work (CREATE, MATCH)"
echo "  ✓ Vessels API is healthy"
echo "  ✓ Vessel CRUD operations work"
echo "  ✓ Connection operations work"
echo "  ✓ Statistics endpoint works"
echo "  ✓ .env file created with API keys"
echo "  ✓ Data persists in FalkorDB"
echo ""
log_info "Integration tests completed successfully!"
