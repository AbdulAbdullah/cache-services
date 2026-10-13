"""Database model for caching individual string transformations."""
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class TransformCache(SQLModel, table=True):
    """Stores individual transformed string results to avoid duplicate external calls."""

    __tablename__ = "transform_cache"

    id: Optional[int] = Field(default=None, primary_key=True)
    input_string: str = Field(index=True, unique=True, nullable=False)
    transformed_string: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
