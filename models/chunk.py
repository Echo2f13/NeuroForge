"""Chunk Models for NeuroForge.

Defines the models used for document chunking:
- ChunkMetadata: Positional and structural metadata for a chunk
- Chunk: A text segment from a larger document
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk.

    Tracks the position and structural context of a chunk
    within its source document.

    Attributes:
        section_heading: Heading of the section containing this chunk.
        page_number: Page number where this chunk appears.
        token_count: Number of tokens in the chunk.
        start_char: Starting character index in the original document.
        end_char: Ending character index in the original document.
    """

    section_heading: Optional[str] = Field(
        default=None, description="Heading of the containing section"
    )
    page_number: Optional[int] = Field(
        default=None, ge=1, description="Page number in source document"
    )
    token_count: int = Field(..., gt=0, description="Number of tokens in this chunk")
    start_char: int = Field(
        ..., ge=0, description="Starting character index in source"
    )
    end_char: int = Field(..., ge=0, description="Ending character index in source")

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "ChunkMetadata":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "ChunkMetadata":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class Chunk(BaseModel):
    """A text chunk extracted from a document.

    Represents a segment of text that has been split from a larger
    document during the chunking process.

    Attributes:
        id: Unique identifier for this chunk.
        content: The text content of the chunk.
        document_id: ID of the parent document.
        chunk_index: Position index within the document.
        metadata: Positional and structural metadata.
    """

    id: str = Field(..., min_length=1, description="Unique chunk identifier")
    content: str = Field(..., min_length=1, description="Chunk text content")
    document_id: str = Field(
        ..., min_length=1, description="Parent document identifier"
    )
    chunk_index: int = Field(
        ..., ge=0, description="Position index within the document"
    )
    metadata: ChunkMetadata = Field(..., description="Chunk positional metadata")

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Chunk":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Chunk":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
