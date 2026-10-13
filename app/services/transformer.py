"""Transformer service that simulates an expensive external transformation."""
import asyncio
from typing import Sequence


async def transform_string(text: str, delay: float = 0.05) -> str:
    """Transform a single string by converting to uppercase with simulated latency.

    Treats the transformation as an expensive external service call by introducing
    an asynchronous delay.

    Args:
        text: Input string to transform.
        delay: Simulated network/processing latency in seconds.

    Returns:
        The transformed string in uppercase.
    """
    if delay > 0:
        await asyncio.sleep(delay)
    return text.upper()


async def transform_strings(texts: Sequence[str], delay: float = 0.05) -> list[str]:
    """Transform multiple strings concurrently.

    Args:
        texts: Sequence of input strings.
        delay: Simulated latency per string transformation.

    Returns:
        List of transformed strings in the same order as input.
    """
    if not texts:
        return []
    tasks = [transform_string(text, delay=delay) for text in texts]
    return await asyncio.gather(*tasks)
