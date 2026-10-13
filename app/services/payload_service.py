"""Business logic service for payload generation, deduplication, and string caching."""
import hashlib
import json
from itertools import chain
from typing import Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.payload import Payload
from app.models.transform_cache import TransformCache
from app.services.transformer import transform_string


def generate_input_hash(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """Generate a deterministic SHA-256 hash for the given input lists.

    Used for payload deduplication so identical input payloads are reused without
    recomputing transformations.

    Args:
        list_1: First list of strings.
        list_2: Second list of strings.

    Returns:
        Hex-encoded SHA-256 string hash.
    """
    serialized = json.dumps({"list_1": list(list_1), "list_2": list(list_2)}, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def interleave_strings(list_1: Sequence[str], list_2: Sequence[str]) -> list[str]:
    """Interleave two equal-length lists of strings.

    Args:
        list_1: First sequence of strings.
        list_2: Second sequence of strings.

    Returns:
        Interleaved list alternating elements from list_1 and list_2.

    Raises:
        ValueError: If list_1 and list_2 have different lengths.
    """
    if len(list_1) != len(list_2):
        raise ValueError(
            f"Lists must have equal length, got {len(list_1)} and {len(list_2)}"
        )
    return list(chain.from_iterable(zip(list_1, list_2)))


def format_interleaved_output(interleaved: Sequence[str]) -> str:
    """Format an interleaved sequence of strings into the stored output representation.

    Args:
        interleaved: Interleaved list of strings.

    Returns:
        Space-separated string output.
    """
    return " ".join(interleaved)


async def get_payload_by_id(session: AsyncSession, payload_id: int) -> Optional[Payload]:
    """Retrieve a stored payload by its unique ID.

    Args:
        session: Active async database session.
        payload_id: Primary key ID of the payload.

    Returns:
        Payload record if found, None otherwise.
    """
    return await session.get(Payload, payload_id)


async def get_payload_by_hash(session: AsyncSession, input_hash: str) -> Optional[Payload]:
    """Retrieve an existing payload by its deterministic input hash.

    Args:
        session: Active async database session.
        input_hash: Deterministic input hash string.

    Returns:
        Payload record if found, None otherwise.
    """
    statement = select(Payload).where(Payload.input_hash == input_hash)
    result = await session.execute(statement)
    return result.scalars().first()


async def get_cached_transformations(
    session: AsyncSession, strings: Sequence[str]
) -> dict[str, str]:
    """Look up cached string transformations from the database.

    Args:
        session: Active async database session.
        strings: Sequence of input strings to query.

    Returns:
        Dictionary mapping input_string to transformed_string for all cache hits.
    """
    unique_strings = list(set(strings))
    if not unique_strings:
        return {}

    statement = select(TransformCache).where(TransformCache.input_string.in_(unique_strings))
    result = await session.execute(statement)
    cached_records = result.scalars().all()

    return {record.input_string: record.transformed_string for record in cached_records}


async def transform_and_cache_strings(
    session: AsyncSession, strings: Sequence[str], delay: float = 0.05
) -> dict[str, str]:
    """Ensure all given strings are transformed and cached in the database.

    Checks the database cache first to avoid redundant calls to the expensive
    transformer service. Missing strings are transformed, persisted to the database,
    and returned along with existing cached values.

    Args:
        session: Active async database session.
        strings: Sequence of strings to transform.
        delay: Simulated delay for cache-miss transformations.

    Returns:
        Dictionary mapping every input string to its transformed value.
    """
    unique_strings = list(set(strings))
    if not unique_strings:
        return {}

    # Check cache for existing transformations
    cache_map = await get_cached_transformations(session, unique_strings)
    missing_strings = [s for s in unique_strings if s not in cache_map]

    if missing_strings:
        new_entries: list[TransformCache] = []
        for text in missing_strings:
            transformed = await transform_string(text, delay=delay)
            cache_map[text] = transformed
            new_entries.append(
                TransformCache(input_string=text, transformed_string=transformed)
            )

        session.add_all(new_entries)
        await session.commit()

    return cache_map


async def process_payload(
    session: AsyncSession,
    list_1: list[str],
    list_2: list[str],
    delay: float = 0.05,
) -> tuple[Payload, bool]:
    """Process an input payload: check for existing payload, transform/cache, and store.

    Flow:
    1. Validate input lists have equal length.
    2. Compute input hash and return existing payload if already cached (deduplication).
    3. Transform any uncached individual strings via the transformer service and store in cache.
    4. Interleave the transformed strings from list_1 and list_2.
    5. Save new Payload record and return (payload, is_created).

    Args:
        session: Active async database session.
        list_1: First list of strings.
        list_2: Second list of strings.
        delay: Simulated transformer delay.

    Returns:
        Tuple of (Payload instance, bool indicating whether a new payload was created).

    Raises:
        ValueError: If input list lengths do not match.
    """
    if len(list_1) != len(list_2):
        raise ValueError(
            f"Input lists must have equal length, got {len(list_1)} and {len(list_2)}"
        )

    # 1. Check for payload deduplication
    input_hash = generate_input_hash(list_1, list_2)
    existing_payload = await get_payload_by_hash(session, input_hash)
    if existing_payload is not None:
        return existing_payload, False

    # 2. Transform and cache unique strings
    all_strings = list_1 + list_2
    transform_map = await transform_and_cache_strings(session, all_strings, delay=delay)

    # 3. Apply transformations to both lists
    transformed_1 = [transform_map[s] for s in list_1]
    transformed_2 = [transform_map[s] for s in list_2]

    # 4. Interleave transformed strings and format output
    interleaved = interleave_strings(transformed_1, transformed_2)
    output = format_interleaved_output(interleaved)

    # 5. Persist payload
    new_payload = Payload(
        input_hash=input_hash,
        list_1=list_1,
        list_2=list_2,
        output=output,
    )
    session.add(new_payload)
    await session.commit()
    await session.refresh(new_payload)

    return new_payload, True
