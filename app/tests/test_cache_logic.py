"""Unit tests for Stage 3 business logic, transformer, and caching services."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.payload import Payload
from app.models.transform_cache import TransformCache
from app.services.payload_service import (
    format_interleaved_output,
    generate_input_hash,
    get_cached_transformations,
    interleave_strings,
    process_payload,
    transform_and_cache_strings,
)
from app.services.transformer import transform_string, transform_strings


@pytest.mark.asyncio
async def test_transformer_uppercase():
    """Verify that transform_string correctly converts text to uppercase."""
    result = await transform_string("hello world", delay=0)
    assert result == "HELLO WORLD"


@pytest.mark.asyncio
async def test_transformer_batch():
    """Verify that transform_strings transforms multiple inputs concurrently."""
    inputs = ["apple", "banana", "cherry"]
    results = await transform_strings(inputs, delay=0)
    assert results == ["APPLE", "BANANA", "CHERRY"]


def test_interleave_strings_success():
    """Verify interleaving of two equal-length lists."""
    list_1 = ["first", "third"]
    list_2 = ["second", "fourth"]
    interleaved = interleave_strings(list_1, list_2)
    assert interleaved == ["first", "second", "third", "fourth"]
    assert format_interleaved_output(interleaved) == "first second third fourth"


def test_interleave_strings_length_mismatch():
    """Verify that interleave_strings raises ValueError when lengths differ."""
    with pytest.raises(ValueError, match="equal length"):
        interleave_strings(["a", "b"], ["c"])


def test_generate_input_hash_deterministic():
    """Verify deterministic hashing for identical and different inputs."""
    hash1 = generate_input_hash(["a", "b"], ["c", "d"])
    hash2 = generate_input_hash(["a", "b"], ["c", "d"])
    hash3 = generate_input_hash(["b", "a"], ["c", "d"])

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64


@pytest.mark.asyncio
async def test_string_caching_and_reuse(test_session: AsyncSession):
    """Verify that strings are cached in DB and reused without recomputation."""
    # First call: transforms and populates DB cache
    mapping1 = await transform_and_cache_strings(test_session, ["alpha", "beta"], delay=0)
    assert mapping1 == {"alpha": "ALPHA", "beta": "BETA"}

    # Verify rows in DB
    result = await test_session.execute(select(TransformCache))
    rows = result.scalars().all()
    assert len(rows) == 2

    # Second call with overlap: beta is cached, gamma is new
    mapping2 = await transform_and_cache_strings(
        test_session, ["beta", "gamma"], delay=0
    )
    assert mapping2 == {"beta": "BETA", "gamma": "GAMMA"}

    result2 = await test_session.execute(select(TransformCache))
    rows2 = result2.scalars().all()
    assert len(rows2) == 3


@pytest.mark.asyncio
async def test_process_payload_fresh_and_deduplication(test_session: AsyncSession):
    """Verify process_payload handles fresh creation and subsequent deduplication."""
    list_1 = ["first", "third"]
    list_2 = ["second", "fourth"]

    # 1. Fresh creation
    payload1, is_created1 = await process_payload(test_session, list_1, list_2, delay=0)
    assert is_created1 is True
    assert payload1.id is not None
    assert payload1.output == "FIRST SECOND THIRD FOURTH"
    assert payload1.list_1 == list_1
    assert payload1.list_2 == list_2

    # 2. Duplicate submission
    payload2, is_created2 = await process_payload(test_session, list_1, list_2, delay=0)
    assert is_created2 is False
    assert payload2.id == payload1.id
    assert payload2.output == payload1.output

    # Total payload count in DB should remain 1
    result = await test_session.execute(select(Payload))
    all_payloads = result.scalars().all()
    assert len(all_payloads) == 1


@pytest.mark.asyncio
async def test_minimizes_transformer_calls_via_cache(test_session: AsyncSession):
    """Verify that transform_string is only called for uncached strings."""
    with patch("app.services.payload_service.transform_string", wraps=transform_string) as mock_transform:
        # First call with 3 strings
        res1 = await transform_and_cache_strings(test_session, ["one", "two", "three"], delay=0)
        assert res1 == {"one": "ONE", "two": "TWO", "three": "THREE"}
        assert mock_transform.call_count == 3

        mock_transform.reset_mock()

        # Second call with 2 already cached + 1 new string
        res2 = await transform_and_cache_strings(test_session, ["two", "three", "four"], delay=0)
        assert res2 == {"two": "TWO", "three": "THREE", "four": "FOUR"}
        assert mock_transform.call_count == 1
        assert mock_transform.call_args[0][0] == "four"

        mock_transform.reset_mock()

        # Third call with completely cached strings
        res3 = await transform_and_cache_strings(test_session, ["one", "two"], delay=0)
        assert res3 == {"one": "ONE", "two": "TWO"}
        # Transformer should not be called at all
        assert mock_transform.call_count == 0


def test_interleave_strings_empty():
    """Verify interleaving empty lists produces empty list and empty string."""
    interleaved = interleave_strings([], [])
    assert interleaved == []
    assert format_interleaved_output(interleaved) == ""


def test_interleave_strings_single():
    """Verify interleaving single-item lists."""
    interleaved = interleave_strings(["only_first"], ["only_second"])
    assert interleaved == ["only_first", "only_second"]
    assert format_interleaved_output(interleaved) == "only_first only_second"
