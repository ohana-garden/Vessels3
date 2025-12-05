# Vessels

A graph database application powered by FalkorDB. Vessels manages entities and their relationships with all runtime data persisted in FalkorDB.

## Features

- **FalkorDB Integration**: All data stored in FalkorDB graph database
- **API Keys Management**: Automatic .env file generation from environment variables
- **Docker Support**: Complete containerized deployment with FalkorDB included
- **Health Checks**: Comprehensive startup and runtime health verification
- **REST API**: FastAPI-based HTTP interface for vessel management

## Quick Start

### Using Docker (Recommended)

```bash
# Build and run with docker-compose
docker-compose up -d

# With API keys
OPENAI_API_KEY=sk-your-key ANTHROPIC_API_KEY=sk-ant-your-key docker-compose up -d
```

### API Endpoints

Once running, the API is available at `http://localhost:8000`:

- `GET /health` - Health check
- `GET /stats` - Graph statistics
- `POST /vessels` - Create a vessel
- `GET /vessels` - List vessels
- `GET /vessels/{id}` - Get vessel by ID
- `PATCH /vessels/{id}` - Update vessel
- `DELETE /vessels/{id}` - Delete vessel
- `POST /connections` - Create connection
- `GET /vessels/{id}/connections` - Get vessel connections
- `DELETE /connections` - Delete connection
- `GET /path` - Find path between vessels

### Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FALKORDB_HOST` | localhost | FalkorDB host |
| `FALKORDB_PORT` | 6379 | FalkorDB port |
| `FALKORDB_PASSWORD` | - | FalkorDB password |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | - | Anthropic API key |
| `VESSELS_DEBUG` | false | Enable debug mode |
| `VESSELS_LOG_LEVEL` | INFO | Log level |
| `VESSELS_GRAPH_NAME` | vessels | Graph name in FalkorDB |

## Docker Commands

```bash
# Run with all services (FalkorDB + Vessels)
docker-compose up -d

# Run tests
docker-compose -f docker-compose.test.yml up

# Run with external FalkorDB
docker-compose --profile external-db up -d

# View logs
docker-compose logs -f vessels

# Shell access
docker-compose exec vessels bash
```

## Development

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Start FalkorDB (requires Docker)
docker run -d -p 6379:6379 falkordb/falkordb:latest

# Run application
uvicorn vessels.api.app:app --reload
```

### Project Structure

```
vessels/
├── core/           # Configuration and settings
├── db/             # FalkorDB connection and graph operations
├── api/            # FastAPI application
└── utils/          # Logging and utilities

tests/              # Unit tests
scripts/            # Startup and health check scripts
docker/             # Docker configuration files
```

## Architecture

Vessels runs everything from the FalkorDB database:

1. **Startup**: Container entrypoint writes API keys to `.env`
2. **FalkorDB Boot**: Supervisor starts FalkorDB with graph module
3. **Health Check**: Startup script waits for FalkorDB to be fully loaded
4. **Vessels API**: FastAPI server starts after database is ready
5. **Operations**: All CRUD operations use Cypher queries against FalkorDB

## License

MIT
