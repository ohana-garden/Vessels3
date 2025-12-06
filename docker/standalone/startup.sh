#!/bin/bash
set -e

echo "=== Vessels All-in-One Container ==="
echo "Starting services..."

# Create data directories if they don't exist
mkdir -p /data/falkordb /data/tigerbeetle /vessels/work_dir /var/log/supervisor

# ============================================
# Write API Keys to .env file
# ============================================
write_env_file() {
    ENV_FILE="/vessels/.env"
    echo "# Vessels Configuration (Auto-generated at startup)" > "$ENV_FILE"
    echo "# Generated: $(date -Iseconds)" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # FalkorDB Configuration
    echo "# FalkorDB Configuration" >> "$ENV_FILE"
    echo "FALKORDB_HOST=${FALKORDB_HOST:-localhost}" >> "$ENV_FILE"
    echo "FALKORDB_PORT=${FALKORDB_PORT:-6379}" >> "$ENV_FILE"
    echo "FALKORDB_DATABASE=${FALKORDB_DATABASE:-vessels}" >> "$ENV_FILE"
    [ -n "$FALKORDB_USERNAME" ] && echo "FALKORDB_USERNAME=${FALKORDB_USERNAME}" >> "$ENV_FILE"
    [ -n "$FALKORDB_PASSWORD" ] && echo "FALKORDB_PASSWORD=${FALKORDB_PASSWORD}" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # TigerBeetle Configuration
    echo "# TigerBeetle Configuration" >> "$ENV_FILE"
    echo "TIGERBEETLE_HOST=${TIGERBEETLE_HOST:-localhost}" >> "$ENV_FILE"
    echo "TIGERBEETLE_PORT=${TIGERBEETLE_PORT:-3000}" >> "$ENV_FILE"
    echo "TIGERBEETLE_CLUSTER_ID=${TIGERBEETLE_CLUSTER_ID:-0}" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Graphiti Configuration
    echo "# Graphiti (Knowledge Graph)" >> "$ENV_FILE"
    echo "GRAPHITI_LLM_PROVIDER=${GRAPHITI_LLM_PROVIDER:-openai}" >> "$ENV_FILE"
    echo "GRAPHITI_LLM_MODEL=${GRAPHITI_LLM_MODEL:-gpt-4o-mini}" >> "$ENV_FILE"
    echo "GRAPHITI_EMBEDDING_MODEL=${GRAPHITI_EMBEDDING_MODEL:-text-embedding-3-small}" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # API Keys
    echo "# LLM API Keys" >> "$ENV_FILE"
    if [ -n "$OPENAI_API_KEY" ]; then
        echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >> "$ENV_FILE"
        echo "  [OK] OPENAI_API_KEY configured"
    fi
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" >> "$ENV_FILE"
        echo "  [OK] ANTHROPIC_API_KEY configured"
    fi
    if [ -n "$HUME_API_KEY" ]; then
        echo "HUME_API_KEY=${HUME_API_KEY}" >> "$ENV_FILE"
        echo "HUME_SECRET_KEY=${HUME_SECRET_KEY}" >> "$ENV_FILE"
        echo "  [OK] HUME keys configured"
    fi

    echo ""
    echo ".env file written to $ENV_FILE"
}

# ============================================
# Initialize TigerBeetle
# ============================================
init_tigerbeetle() {
    if [ ! -f /data/tigerbeetle/0_0.tigerbeetle ]; then
        echo "Initializing TigerBeetle data file..."
        /usr/local/bin/tigerbeetle format \
            --cluster=0 \
            --replica=0 \
            --replica-count=1 \
            /data/tigerbeetle/0_0.tigerbeetle
        echo "TigerBeetle initialized."
    else
        echo "TigerBeetle data file exists."
    fi
}

# ============================================
# Main Startup
# ============================================

# Check if FalkorDB module exists
if [ ! -f /opt/falkordb/falkordb.so ]; then
    echo "WARNING: FalkorDB module not found at /opt/falkordb/falkordb.so"
    echo "Graph features may not work correctly."
fi

# Write environment configuration
echo ""
echo "=== Writing Environment Configuration ==="
write_env_file

# Initialize TigerBeetle
echo ""
echo "=== Initializing TigerBeetle ==="
init_tigerbeetle

# Set environment variables for the application
export FALKORDB_HOST=${FALKORDB_HOST:-localhost}
export FALKORDB_PORT=${FALKORDB_PORT:-6379}
export FALKORDB_DATABASE=${FALKORDB_DATABASE:-vessels}
export TIGERBEETLE_HOST=${TIGERBEETLE_HOST:-localhost}
export TIGERBEETLE_PORT=${TIGERBEETLE_PORT:-3000}
export TIGERBEETLE_CLUSTER_ID=${TIGERBEETLE_CLUSTER_ID:-0}

echo ""
echo "=== Configuration ==="
echo "  FalkorDB: ${FALKORDB_HOST}:${FALKORDB_PORT}/${FALKORDB_DATABASE}"
echo "  TigerBeetle: ${TIGERBEETLE_HOST}:${TIGERBEETLE_PORT}"
echo "  Web UI: ${WEB_UI_HOST:-0.0.0.0}:${WEB_UI_PORT:-80}"
echo ""

# Start supervisor (manages all processes)
echo "=== Starting Supervisord ==="
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
