"""Integration tests for FastAPI endpoints (POST /payload, GET /payload/{id}, /health)."""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.database import get_session
from app.main import app


@pytest.fixture
async def test_client():
    """Create a test client with an isolated in-memory SQLite database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_session():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_health_check(test_client: AsyncClient):
    """Verify health check endpoint returns 200 OK."""
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_and_get_payload(test_client: AsyncClient):
    """Verify creating a payload and fetching it by ID."""
    payload_data = {
        "list_1": ["first string", "third string"],
        "list_2": ["second string", "fourth string"],
    }

    # 1. POST /payload
    post_res = await test_client.post("/payload", json=payload_data)
    assert post_res.status_code == 201
    res_json = post_res.json()
    assert "id" in res_json
    payload_id = res_json["id"]

    # 2. GET /payload/{id}
    get_res = await test_client.get(f"/payload/{payload_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == payload_id
    assert detail["list_1"] == payload_data["list_1"]
    assert detail["list_2"] == payload_data["list_2"]
    assert (
        detail["output"]
        == "FIRST STRING SECOND STRING THIRD STRING FOURTH STRING"
    )
    assert "created_at" in detail


@pytest.mark.asyncio
async def test_payload_deduplication(test_client: AsyncClient):
    """Verify identical payload POST requests return the existing ID."""
    payload_data = {
        "list_1": ["apple", "cherry"],
        "list_2": ["banana", "date"],
    }

    # First request
    res1 = await test_client.post("/payload", json=payload_data)
    assert res1.status_code == 201
    id1 = res1.json()["id"]

    # Second request with identical payload
    res2 = await test_client.post("/payload", json=payload_data)
    assert res2.status_code == 201
    id2 = res2.json()["id"]

    assert id1 == id2


@pytest.mark.asyncio
async def test_create_payload_unequal_lengths(test_client: AsyncClient):
    """Verify 422 error when list_1 and list_2 have different lengths."""
    payload_data = {
        "list_1": ["one", "two"],
        "list_2": ["three"],
    }

    response = await test_client.post("/payload", json=payload_data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_payload_invalid_structure(test_client: AsyncClient):
    """Verify 422 error when body is malformed."""
    response = await test_client.post("/payload", json={"list_1": "not a list"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_payload(test_client: AsyncClient):
    """Verify 404 error when requesting a non-existent payload ID."""
    response = await test_client.get("/payload/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Payload not found"
