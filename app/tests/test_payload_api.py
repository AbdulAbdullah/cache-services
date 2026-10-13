"""Integration tests for FastAPI endpoints (POST /payload, GET /payload/{id}, /health)."""
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.services.transformer import transform_string


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
    assert isinstance(res_json["id"], int)
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
async def test_cross_request_string_level_caching(test_client: AsyncClient):
    """Verify string caching is shared across different payloads."""
    with patch("app.services.payload_service.transform_string", wraps=transform_string) as mock_transform:
        # Request 1 has "cat" and "dog"
        req1 = {"list_1": ["cat"], "list_2": ["dog"]}
        res1 = await test_client.post("/payload", json=req1)
        assert res1.status_code == 201
        assert mock_transform.call_count == 2

        mock_transform.reset_mock()

        # Request 2 shares "dog" and adds "bird"
        req2 = {"list_1": ["dog"], "list_2": ["bird"]}
        res2 = await test_client.post("/payload", json=req2)
        assert res2.status_code == 201
        # Only "bird" should trigger a transformer call
        assert mock_transform.call_count == 1
        assert mock_transform.call_args[0][0] == "bird"


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


@pytest.mark.asyncio
async def test_create_payload_empty_lists(test_client: AsyncClient):
    """Verify creating a payload with empty lists succeeds."""
    payload_data = {"list_1": [], "list_2": []}
    post_res = await test_client.post("/payload", json=payload_data)
    assert post_res.status_code == 201
    payload_id = post_res.json()["id"]

    get_res = await test_client.get(f"/payload/{payload_id}")
    assert get_res.status_code == 200
    assert get_res.json()["output"] == ""
