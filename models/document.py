"""Core Document Models for NeuroForge.

Defines the foundational models for document ingestion and structure:
- InputFormat: Supported input file/source types
- DocumentMetadata: Metadata about the source document
- Document: The unified document object after ingestion
- Section: Structural breakdown of a document
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InputFormat(str, Enum):
    """Supported input format types for document ingestion."""

    PDF = "pdf"
    PPTX = "pptx"
    DOCX = "docx"
    IMAGE = "image"
    YOUTUBE = "youtube"
    TEXT = "text"
    MARKDOWN = "markdown"


class DocumentMetadata(BaseModel):
    """Metadata about the source document.

    Attributes:
        source: File path or URL of the original document.
        format: The detected input format.
        title: Optional title extracted from the document.
        total_pages: Total number of pages (for paginated formats).
        author: Author of the document if available.
        created_at: Creation timestamp as ISO string.
    """

    source: str = Field(..., description="File path or URL of the source document")
    format: InputFormat = Field(..., description="Detected input format type")
    title: Optional[str] = Field(default=None, description="Document title")
    total_pages: Optional[int] = Field(
        default=None, ge=1, description="Total number of pages"
    )
    author: Optional[str] = Field(default=None, description="Document author")
    created_at: Optional[str] = Field(
        default=None, description="Creation timestamp (ISO format)"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentMetadata":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "DocumentMetadata":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class Section(BaseModel):
    """A structural section within a document.

    Attributes:
        heading: The section heading text.
        content: The text content of the section.
        level: Heading level (1 = top-level).
        page_number: Page where this section starts.
    """

    heading: Optional[str] = Field(default=None, description="Section heading text")
    content: str = Field(..., min_length=1, description="Section text content")
    level: int = Field(default=1, ge=1, le=6, description="Heading level (1-6)")
    page_number: Optional[int] = Field(
        default=None, ge=1, description="Starting page number"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Section":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Section":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class Document(BaseModel):
    """Unified document object after ingestion.

    Represents the full extracted content along with metadata
    and structural breakdown.

    Attributes:
        content: Full extracted text content.
        metadata: Source document metadata.
        sections: Structural breakdown into sections.
    """

    content: str = Field(..., min_length=1, description="Full extracted text content")
    metadata: DocumentMetadata = Field(..., description="Document metadata")
    sections: list[Section] = Field(
        default_factory=list, description="Structural breakdown into sections"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Document":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
