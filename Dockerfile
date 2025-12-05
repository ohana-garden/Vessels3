# Vessels Dockerfile with FalkorDB
# This container includes everything Vessels needs at runtime:
# - FalkorDB (graph database)
# - Python runtime
# - Vessels application
# - Startup scripts ensuring FalkorDB is fully loaded

FROM falkordb/falkordb:latest as falkordb-base

# Final stage with Python and FalkorDB
FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    supervisor \
    redis-tools \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy FalkorDB from the official image
COPY --from=falkordb-base /usr/lib/redis/modules/falkordb.so /usr/lib/redis/modules/
COPY --from=falkordb-base /usr/local/bin/redis-server /usr/local/bin/
COPY --from=falkordb-base /usr/local/bin/redis-cli /usr/local/bin/

# Create directories
RUN mkdir -p /data/falkordb /app /var/log/supervisor /var/run

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY vessels/ /app/vessels/
COPY scripts/ /app/scripts/

# Make scripts executable
RUN chmod +x /app/scripts/*.sh

# Copy configuration files
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/redis.conf /etc/redis/redis.conf

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables with defaults
ENV FALKORDB_HOST=localhost \
    FALKORDB_PORT=6379 \
    FALKORDB_DATA_DIR=/data/falkordb \
    VESSELS_LOG_LEVEL=INFO \
    VESSELS_GRAPH_NAME=vessels \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose ports
# 6379: FalkorDB (Redis protocol)
# 8000: Vessels API
EXPOSE 6379 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python /app/scripts/healthcheck.py || exit 1

# Volume for data persistence
VOLUME ["/data/falkordb"]

# Entrypoint handles API key injection and startup
ENTRYPOINT ["/entrypoint.sh"]

# Default command starts supervisor (FalkorDB + Vessels)
CMD ["supervisor"]
