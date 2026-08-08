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


class StoredDocument(BaseModel):
    """A document file stored for viewing and source attribution.
    
    Represents a document that has been uploaded and stored on the
    filesystem, enabling later viewing in the document viewer.
    
    Attributes:
        id: Unique document identifier.
        subject_id: ID of the subject this document belongs to.
        filename: Original filename as uploaded.
        format: Document format (pdf/docx/txt/etc.).
        storage_path: Relative path to stored file.
        file_size: File size in bytes.
        total_pages: Total number of pages (for paginated formats).
        uploaded_at: Upload timestamp (ISO format).
        checksum: SHA-256 hash for integrity verification.
        title: Optional document title (extracted or user-provided).
        author: Optional document author.
    """
    
    id: str = Field(..., min_length=1, description="Unique document identifier")
    subject_id: str = Field(..., min_length=1, description="Owning subject ID")
    filename: str = Field(..., min_length=1, description="Original filename")
    format: InputFormat = Field(..., description="Document format")
    storage_path: str = Field(..., min_length=1, description="Relative path to stored file")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    total_pages: Optional[int] = Field(
        default=None, ge=1, description="Total number of pages"
    )
    uploaded_at: str = Field(..., description="Upload timestamp (ISO format)")
    checksum: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash")
    title: Optional[str] = Field(default=None, description="Document title")
    author: Optional[str] = Field(default=None, description="Document author")
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict) -> "StoredDocument":
        """Deserialize from dictionary."""
        return cls.model_validate(data)
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "StoredDocument":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
    
    def get_content_type(self) -> str:
        """Get the MIME content type for this document format.
        
        Returns:
            MIME type string for the document format.
        """
        content_types = {
            InputFormat.PDF: "application/pdf",
            InputFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            InputFormat.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            InputFormat.TEXT: "text/plain",
            InputFormat.MARKDOWN: "text/markdown",
            InputFormat.IMAGE: "image/png",  # Default, should detect actual type
        }
        return content_types.get(self.format, "application/octet-stream")
    
    @property
    def display_size(self) -> str:
        """Get human-readable file size.
        
        Returns:
            Formatted file size string (e.g., "2.5 MB").
        """
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.1f} GB"
