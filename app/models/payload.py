"""Database model for generated payloads and deduplication tracking."""
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON


class Payload(SQLModel, table=True):
    """Stores generated payload records with deterministic input hashes for deduplication."""

    __tablename__ = "payloads"

    id: Optional[int] = Field(default=None, primary_key=True)
    input_hash: str = Field(index=True, unique=True, nullable=False)
    list_1: list[str] = Field(sa_column=Column(JSON, nullable=False))
    list_2: list[str] = Field(sa_column=Column(JSON, nullable=False))
    output: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
