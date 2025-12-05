#!/bin/bash
set -e

# Vessels Container Entrypoint
# Handles API key injection and startup modes

ENV_FILE="/app/.env"
SCRIPTS_DIR="/app/scripts"

echo "=== Vessels Container Starting ==="
echo "Mode: ${1:-supervisor}"

# Function to write API keys to .env file
write_env_file() {
    echo "# Vessels Configuration (Auto-generated)" > "$ENV_FILE"
    echo "# Generated at: $(date -Iseconds)" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # FalkorDB Configuration
    echo "# FalkorDB Configuration" >> "$ENV_FILE"
    echo "FALKORDB_HOST=${FALKORDB_HOST:-localhost}" >> "$ENV_FILE"
    echo "FALKORDB_PORT=${FALKORDB_PORT:-6379}" >> "$ENV_FILE"
    if [ -n "$FALKORDB_PASSWORD" ]; then
        echo "FALKORDB_PASSWORD=${FALKORDB_PASSWORD}" >> "$ENV_FILE"
    fi
    echo "FALKORDB_DATA_DIR=${FALKORDB_DATA_DIR:-/data/falkordb}" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # API Keys
    echo "# API Keys" >> "$ENV_FILE"
    if [ -n "$OPENAI_API_KEY" ]; then
        echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >> "$ENV_FILE"
        echo "Found: OPENAI_API_KEY"
    fi
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" >> "$ENV_FILE"
        echo "Found: ANTHROPIC_API_KEY"
    fi
    echo "" >> "$ENV_FILE"

    # Application Settings
    echo "# Application Settings" >> "$ENV_FILE"
    echo "VESSELS_DEBUG=${VESSELS_DEBUG:-false}" >> "$ENV_FILE"
    echo "VESSELS_LOG_LEVEL=${VESSELS_LOG_LEVEL:-INFO}" >> "$ENV_FILE"
    echo "VESSELS_GRAPH_NAME=${VESSELS_GRAPH_NAME:-vessels}" >> "$ENV_FILE"

    echo ".env file written to $ENV_FILE"
}

# Function to validate API keys
validate_api_keys() {
    local has_keys=false

    if [ -n "$OPENAI_API_KEY" ]; then
        if [[ "$OPENAI_API_KEY" == sk-* ]]; then
            echo "OPENAI_API_KEY: Valid format"
            has_keys=true
        else
            echo "WARNING: OPENAI_API_KEY does not match expected format (sk-*)"
        fi
    fi

    if [ -n "$ANTHROPIC_API_KEY" ]; then
        if [[ "$ANTHROPIC_API_KEY" == sk-ant-* ]]; then
            echo "ANTHROPIC_API_KEY: Valid format"
            has_keys=true
        else
            echo "WARNING: ANTHROPIC_API_KEY does not match expected format (sk-ant-*)"
        fi
    fi

    if [ "$has_keys" = false ]; then
        echo "WARNING: No API keys configured. Some features may be unavailable."
    fi
}

# Function to wait for FalkorDB
wait_for_falkordb() {
    local max_attempts=${1:-60}
    local attempt=1

    echo "Waiting for FalkorDB to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if redis-cli -h localhost -p ${FALKORDB_PORT:-6379} ping 2>/dev/null | grep -q PONG; then
            # Check if graph module is loaded
            if redis-cli -h localhost -p ${FALKORDB_PORT:-6379} MODULE LIST 2>/dev/null | grep -qi "graph\|falkordb"; then
                # Check if loading is complete
                if ! redis-cli -h localhost -p ${FALKORDB_PORT:-6379} INFO persistence 2>/dev/null | grep -q "loading:1"; then
                    echo "FalkorDB is ready! (attempt $attempt)"
                    return 0
                fi
            fi
        fi

        echo "Waiting for FalkorDB... (attempt $attempt/$max_attempts)"
        sleep 1
        ((attempt++))
    done

    echo "ERROR: FalkorDB failed to become ready after $max_attempts attempts"
    return 1
}

# Write environment configuration
echo "=== Writing Environment Configuration ==="
write_env_file

# Validate API keys
echo "=== Validating API Keys ==="
validate_api_keys

# Ensure data directory exists and has correct permissions
mkdir -p "${FALKORDB_DATA_DIR:-/data/falkordb}"

# Handle different startup modes
case "${1:-supervisor}" in
    supervisor)
        echo "=== Starting Supervisor (FalkorDB + Vessels) ==="
        exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
        ;;

    falkordb-only)
        echo "=== Starting FalkorDB Only ==="
        exec /usr/local/bin/redis-server /etc/redis/redis.conf
        ;;

    vessels-only)
        echo "=== Starting Vessels Only (External FalkorDB) ==="
        wait_for_falkordb 30
        exec python -m uvicorn vessels.api.app:app --host 0.0.0.0 --port 8000
        ;;

    test)
        echo "=== Running Tests ==="
        # Start FalkorDB in background
        /usr/local/bin/redis-server /etc/redis/redis.conf &
        wait_for_falkordb 30
        exec python -m pytest /app/tests -v
        ;;

    shell)
        echo "=== Starting Shell ==="
        exec /bin/bash
        ;;

    *)
        echo "=== Running Custom Command ==="
        exec "$@"
        ;;
esac
