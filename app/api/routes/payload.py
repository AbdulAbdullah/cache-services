"""API endpoints for payload processing and retrieval."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.payload import (
    PayloadCreateRequest,
    PayloadCreateResponse,
    PayloadResponse,
)
from app.services.payload_service import get_payload_by_id, process_payload

router = APIRouter(prefix="/payload", tags=["Payloads"])


@router.post(
    "",
    response_model=PayloadCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or deduplicate transformation payload",
    description=(
        "Processes two equal-length lists of strings. Checks for deduplication, "
        "transforms uncached strings with simulated latency, caches them, "
        "interleaves results, and returns the payload ID."
    ),
)
async def create_payload(
    payload_data: PayloadCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> PayloadCreateResponse:
    """Create a new payload or return the existing ID if inputs are identical."""
    try:
        payload, _ = await process_payload(
            session=session,
            list_1=payload_data.list_1,
            list_2=payload_data.list_2,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PayloadCreateResponse(id=payload.id)


@router.get(
    "/{payload_id}",
    response_model=PayloadResponse,
    summary="Retrieve payload by ID",
    description="Fetches a stored payload and its interleaved transformed output string.",
)
async def get_payload(
    payload_id: int,
    session: AsyncSession = Depends(get_session),
) -> PayloadResponse:
    """Retrieve stored payload by ID."""
    payload = await get_payload_by_id(session=session, payload_id=payload_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payload not found",
        )

    return PayloadResponse(
        id=payload.id,
        list_1=payload.list_1,
        list_2=payload.list_2,
        output=payload.output,
        created_at=payload.created_at,
    )
