# Caching Service

A high-performance FastAPI microservice that generates, deduplicates, and caches string transformation payloads, backed by PostgreSQL / SQLite. Includes a CLI tool (`cache-cli`) for programmatic load generation and automated testing.

---

## Architecture & Features

- **String-Level Caching (`TransformCache`)**: 
  The transformer function simulates an expensive external service. Transformations are cached at the individual string level (not just per payload). If a string has appeared in *any* previous payload request, its cached transformation is reused across all future requests, minimizing external calls.
- **Payload Deduplication (`Payload`)**: 
  Payloads are identified by a deterministic SHA-256 hash of the input lists (`list_1` and `list_2`). If the identical input structure is submitted again, the service immediately returns the existing payload ID without recomputation.
- **Interleaving Algorithm**: 
  Alternates transformed strings between `list_1` and `list_2` in $O(N)$ time after ensuring equal list lengths.
- **Async Database Architecture**: 
  Built on SQLModel and SQLAlchemy 2.0 async engine (`asyncpg` for PostgreSQL, `aiosqlite` for SQLite / in-memory testing).
- **Separation of Concerns**: 
  - `app/models/`: Internal database tables and storage persistence.
  - `app/schemas/`: Public API request/response validation and contracts.
  - `app/services/`: Isolated, framework-agnostic business logic.
  - `app/api/`: Thin HTTP routing layer.
- **CLI Tool (`cache-cli`)**: 
  Command-line utility built with Pydantic Settings and `httpx` supporting iterations, file/stdin inputs, and file/stdout outputs.
- **Dockerized Multi-Container Setup**: 
  Single-command deployment with FastAPI and PostgreSQL via Docker Compose with automated migrations.

---

## Project Structure

```text
caching-service/
├── app/
│   ├── main.py                      # FastAPI app factory & /health endpoint
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── payload.py           # POST /payload, GET /payload/{id}
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic Settings (environment config)
│   │   └── database.py              # Async engine & session dependency
│   ├── models/
│   │   ├── __init__.py
│   │   ├── payload.py               # Payload SQLModel table
│   │   └── transform_cache.py       # TransformCache SQLModel table
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── payload.py               # Pydantic validation schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── transformer.py           # Mock transformer (simulates external latency)
│   │   └── payload_service.py       # Caching, deduplication, interleaving logic
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py              # Pytest async SQLite fixtures & test client
│       ├── test_cache_logic.py      # Service layer unit tests
│       ├── test_payload_api.py      # Route integration tests
│       ├── test_cli.py              # CLI unit and integration tests
│       └── test_integration.py      # End-to-end lifecycle integration tests
├── cli/
│   ├── __init__.py
│   └── main.py                      # cache-cli entry point
├── docker/
│   ├── Dockerfile                   # Minimal Python 3.11-slim container
│   └── docker-compose.yml           # App + PostgreSQL container orchestration
├── alembic/                         # Database migrations
│   ├── env.py
│   └── versions/
│       └── 06d4d66679ae_initial_schema.py
├── alembic.ini                      # Alembic configuration
├── docker-compose.yml               # Root Docker compose shortcut
├── pyproject.toml                   # Project dependencies and CLI entry point
├── .env.example                     # Sample environment variables
└── README.md
```

---

## Quickstart & Setup

### Option 1: Running with Docker (Recommended)

To start the API service alongside PostgreSQL:

```bash
docker compose up --build
```

The service will automatically:
1. Wait for PostgreSQL to become healthy.
2. Run database migrations via Alembic.
3. Start the FastAPI ASGI server at `http://localhost:8000`.

To tear down:
```bash
docker compose down -v
```

---

### Option 2: Local Development Setup

1. **Prerequisites**: Python 3.11+ and a PostgreSQL instance (or SQLite for development).

2. **Clone & Create Virtual Environment**:
   ```bash
   git clone <repo-url>
   cd caching-service
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -e .
   ```

4. **Environment Variables**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to match your database credentials:
   ```dotenv
   PGUSER=postgres
   PGPASSWORD=postgres
   DB_NAME=caching_service
   PGHOST=localhost
   PGPORT=5432
   ENVIRONMENT=development
   DEBUG=true
   ```

5. **Apply Database Migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Start the API Server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   Interactive OpenAPI docs are accessible at: `http://localhost:8000/docs`.

---

## API Reference & Examples

### 1. Health Check
```http
GET /health
```
**Response (`200 OK`)**:
```json
{
  "status": "ok"
}
```

---

### 2. Create / Deduplicate Payload
```http
POST /payload
Content-Type: application/json
```
**Request Body**:
```json
{
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"]
}
```
**Response (`201 Created`)**:
```json
{
  "id": 1
}
```

- If this exact input is sent again, the service detects the match via deterministic hash and returns the same `id` immediately without re-transforming strings.
- If individual strings (e.g. `"first string"`) were transformed in another request, they are read from cache directly from the database.

---

### 3. Retrieve Payload
```http
GET /payload/{id}
```
**Response (`200 OK`)**:
```json
{
  "id": 1,
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"],
  "output": "FIRST STRING OTHER STRING SECOND STRING ANOTHER STRING THIRD STRING LAST STRING",
  "created_at": "2026-10-14T00:18:00Z"
}
```

---

## CLI Utility (`cache-cli`)

The CLI utility allows programmatic testing and benchmarking against the service.

### CLI Syntax
```bash
cache-cli [-h] [--host HOST] [-r REPEAT] [-i INPUT] [-j JSON_DATA] [-o OUTPUT]
```

| Flag | Short | Description | Default |
|---|---|---|---|
| `--host` | | Target server URL | `http://localhost:8000` |
| `--repeat` | `-r` | Number of iterations | `1` |
| `--input` | `-i` | File path (`-` for stdin) | Stdin if no JSON passed |
| `--json` | `-j` | Inline JSON string | `None` |
| `--output` | `-o` | Output file (`-` for stdout)| `-` (stdout) |

### CLI Usage Examples

1. **Send Inline JSON Payload**:
   ```bash
   cache-cli --host http://localhost:8000 --json '{"list_1": ["hello"], "list_2": ["world"]}'
   ```

2. **Benchmark / Repeat Requests (Deduplication Check)**:
   ```bash
   cache-cli --repeat 10 --json '{"list_1": ["alpha", "beta"], "list_2": ["gamma", "delta"]}'
   ```

3. **Read from File and Write to File**:
   ```bash
   echo '{"list_1": ["foo"], "list_2": ["bar"]}' > input.json
   cache-cli --input input.json --output results.txt
   ```

4. **Pipe from Stdin**:
   ```bash
   cat input.json | cache-cli
   ```

---

## Running Automated Tests

The test suite contains unit tests, route integration tests, CLI tests, and end-to-end integration tests using an isolated in-memory SQLite database.

Run the test suite:
```bash
pytest -v
```

All 34 test cases run asynchronously and validate:
- String transformation and mock latency
- String-level database caching and external call minimization
- Payload deduplication via deterministic SHA-256 hashing
- List interleaving and validation edge cases
- API status codes (`201`, `200`, `404`, `422`)
- CLI argument parsing, stdin/stdout piping, and error handling
- Cross-request string cache sharing and Unicode preservation

---

## Design Decisions & Trade-Offs

1. **String-Level Caching vs Payload-Level Caching**:
   - *Decision*: Cache at both the string level (`TransformCache`) and payload level (`Payload`).
   - *Rationale*: A payload cache only helps if the entire payload is repeated. By caching individual strings, any overlapping terms in future requests skip the expensive external transformer service, maximizing cache hits across the entire system.

2. **Deterministic Input Hashing**:
   - *Decision*: SHA-256 over normalized JSON-serialized inputs.
   - *Rationale*: Allows $O(1)$ database lookup using an indexed `input_hash` column rather than comparing large JSON arrays or performing expensive table scans.

3. **SQLModel + Async Engine**:
   - *Decision*: Combine SQLModel with async SQLAlchemy 2.0 session handling.
   - *Rationale*: Provides Pydantic compatibility while keeping full access to SQLAlchemy's robust async relationship and connection pooling capabilities.

4. **Decoupled Architecture (Thin Routes, Fat Services)**:
   - *Decision*: Keep route handlers minimal and encapsulate all business logic in `app/services/payload_service.py`.
   - *Rationale*: Enables straightforward unit testing of core business rules without requiring an active HTTP server or network overhead.
