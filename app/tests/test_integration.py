"""End-to-end integration tests verifying cross-component behavior."""
import pytest
from httpx import AsyncClient
from sqlmodel import select

from app.models.payload import Payload
from app.models.transform_cache import TransformCache


@pytest.mark.asyncio
async def test_end_to_end_caching_and_deduplication_flow(test_client: AsyncClient, test_session):
    """Verify complete lifecycle: creation, string caching, deduplication, and retrieval."""
    req_1 = {
        "list_1": ["apple", "banana"],
        "list_2": ["cherry", "date"],
    }

    # Step 1: First payload creation
    res1 = await test_client.post("/payload", json=req_1)
    assert res1.status_code == 201
    payload_id_1 = res1.json()["id"]

    # Step 2: Fetch and verify first payload
    get1 = await test_client.get(f"/payload/{payload_id_1}")
    assert get1.status_code == 200
    data1 = get1.json()
    assert data1["output"] == "APPLE CHERRY BANANA DATE"

    # Step 3: Second payload with partially overlapping strings
    req_2 = {
        "list_1": ["banana", "elderberry"],
        "list_2": ["date", "fig"],
    }
    res2 = await test_client.post("/payload", json=req_2)
    assert res2.status_code == 201
    payload_id_2 = res2.json()["id"]
    assert payload_id_2 != payload_id_1

    # Step 4: Fetch and verify second payload
    get2 = await test_client.get(f"/payload/{payload_id_2}")
    assert get2.status_code == 200
    data2 = get2.json()
    assert data2["output"] == "BANANA DATE ELDERBERRY FIG"

    # Step 5: Duplicate request for first payload
    res3 = await test_client.post("/payload", json=req_1)
    assert res3.status_code == 201
    assert res3.json()["id"] == payload_id_1


@pytest.mark.asyncio
async def test_special_characters_and_unicode_handling(test_client: AsyncClient):
    """Verify that unicode characters and special punctuation are preserved and handled."""
    req = {
        "list_1": ["hello-world", "café"],
        "list_2": ["123_456", "naïve"],
    }
    post_res = await test_client.post("/payload", json=req)
    assert post_res.status_code == 201
    payload_id = post_res.json()["id"]

    get_res = await test_client.get(f"/payload/{payload_id}")
    assert get_res.status_code == 200
    assert get_res.json()["output"] == "HELLO-WORLD 123_456 CAFÉ NAÏVE"
