"""Pydantic schemas for payload request and response serialization."""
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class PayloadCreateRequest(BaseModel):
    """Request schema for creating or deduplicating a transformation payload."""

    list_1: list[str] = Field(
        ...,
        description="First list of strings to transform and interleave",
        examples=[["first string", "third string"]],
    )
    list_2: list[str] = Field(
        ...,
        description="Second list of strings to transform and interleave",
        examples=[["second string", "fourth string"]],
    )

    @model_validator(mode="after")
    def validate_equal_lengths(self) -> "PayloadCreateRequest":
        """Ensure both input lists have the same number of elements."""
        if len(self.list_1) != len(self.list_2):
            raise ValueError(
                f"list_1 and list_2 must have equal length (got {len(self.list_1)} and {len(self.list_2)})"
            )
        return self


class PayloadCreateResponse(BaseModel):
    """Response schema returned after payload creation or deduplication."""

    id: int = Field(..., description="Unique payload identifier")


class PayloadResponse(BaseModel):
    """Response schema for payload details and interleaved output."""

    id: int = Field(..., description="Unique payload identifier")
    list_1: list[str] = Field(..., description="Original first list of strings")
    list_2: list[str] = Field(..., description="Original second list of strings")
    output: str = Field(..., description="Interleaved transformed output string")
    created_at: datetime = Field(..., description="Timestamp of creation")
