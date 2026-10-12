# Caching Service

A high-performance FastAPI microservice that generates, deduplicates, and caches string transformation payloads, backed by PostgreSQL / SQLite. Includes a CLI tool (`cache-cli`) for programmatic load generation and testing.

## Features
- **String-Level Caching**: Transforms strings through a simulated external service and caches results individually in the database.
- **Payload Deduplication**: Deterministically hashes input payloads to reuse existing payload records without recomputation.
- **Interleaving Transformation**: Interleaves transformed strings from two lists of equal length.
- **Async Database Layer**: Built on top of SQLModel / SQLAlchemy 2.0 async engine supporting PostgreSQL and SQLite.
- **CLI Utility**: CLI tool using Pydantic Settings for sanitizing inputs and sending requests.
- **Dockerized**: Multi-container Docker Compose setup for API service and PostgreSQL.
