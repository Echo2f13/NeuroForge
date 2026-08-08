"""Chunk Models for NeuroForge.

Defines the models used for document chunking:
- BoundingBox: Coordinates for PDF text highlighting
- ChunkMetadata: Positional and structural metadata for a chunk
- Chunk: A text segment from a larger document
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BoundingBox(BaseModel):
    """Bounding box coordinates for PDF text highlighting.
    
    Coordinates are normalized to percentages (0-100) of the page dimensions
    to enable proper positioning regardless of zoom level or rendering size.
    
    Attributes:
        x0: Left x coordinate (0-100% of page width).
        y0: Top y coordinate (0-100% of page height).
        x1: Right x coordinate (0-100% of page width).
        y1: Bottom y coordinate (0-100% of page height).
        page_width: Original page width in points (for reference).
        page_height: Original page height in points (for reference).
    """
    
    x0: float = Field(..., ge=0, le=100, description="Left x coordinate (0-100%)")
    y0: float = Field(..., ge=0, le=100, description="Top y coordinate (0-100%)")
    x1: float = Field(..., ge=0, le=100, description="Right x coordinate (0-100%)")
    y1: float = Field(..., ge=0, le=100, description="Bottom y coordinate (0-100%)")
    page_width: float = Field(..., gt=0, description="Original page width in points")
    page_height: float = Field(..., gt=0, description="Original page height in points")
    
    @field_validator("x1")
    @classmethod
    def x1_must_be_greater_than_x0(cls, v: float, info) -> float:
        """Ensure x1 >= x0."""
        if "x0" in info.data and v < info.data["x0"]:
            raise ValueError("x1 must be >= x0")
        return v
    
    @field_validator("y1")
    @classmethod
    def y1_must_be_greater_than_y0(cls, v: float, info) -> float:
        """Ensure y1 >= y0."""
        if "y0" in info.data and v < info.data["y0"]:
            raise ValueError("y1 must be >= y0")
        return v
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict) -> "BoundingBox":
        """Deserialize from dictionary."""
        return cls.model_validate(data)
    
    def to_absolute(self, scale: float = 1.0) -> dict:
        """Convert normalized coordinates to absolute pixels at given scale.
        
        Args:
            scale: Zoom scale factor (1.0 = 100%).
            
        Returns:
            Dict with absolute pixel coordinates.
        """
        return {
            "x0": (self.x0 / 100) * self.page_width * scale,
            "y0": (self.y0 / 100) * self.page_height * scale,
            "x1": (self.x1 / 100) * self.page_width * scale,
            "y1": (self.y1 / 100) * self.page_height * scale,
            "width": ((self.x1 - self.x0) / 100) * self.page_width * scale,
            "height": ((self.y1 - self.y0) / 100) * self.page_height * scale,
        }
    
    @classmethod
    def from_absolute(
        cls, 
        x0: float, 
        y0: float, 
        x1: float, 
        y1: float,
        page_width: float,
        page_height: float
    ) -> "BoundingBox":
        """Create BoundingBox from absolute coordinates.
        
        Args:
            x0, y0, x1, y1: Absolute coordinates in points.
            page_width: Page width in points.
            page_height: Page height in points.
            
        Returns:
            BoundingBox with normalized coordinates.
        """
        return cls(
            x0=(x0 / page_width) * 100,
            y0=(y0 / page_height) * 100,
            x1=(x1 / page_width) * 100,
            y1=(y1 / page_height) * 100,
            page_width=page_width,
            page_height=page_height,
        )


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk.

    Tracks the position and structural context of a chunk
    within its source document. Enhanced to support source attribution
    with precise positioning and bounding boxes for PDF highlighting.

    Attributes:
        section_heading: Heading of the section containing this chunk.
        page_number: Page number where this chunk appears.
        paragraph_number: Paragraph number within the page (1-indexed).
        line_start: Starting line number within the document.
        line_end: Ending line number within the document.
        token_count: Number of tokens in the chunk.
        start_char: Starting character index in the original document.
        end_char: Ending character index in the original document.
        bounding_boxes: List of bounding boxes for PDF highlighting.
        source_file: Original filename of the source document.
        document_format: Format of the source document (pdf/docx/txt).
    """

    section_heading: Optional[str] = Field(
        default=None, description="Heading of the containing section"
    )
    page_number: Optional[int] = Field(
        default=None, ge=1, description="Page number in source document"
    )
    paragraph_number: Optional[int] = Field(
        default=None, ge=1, description="Paragraph number within the page"
    )
    line_start: Optional[int] = Field(
        default=None, ge=1, description="Starting line number in document"
    )
    line_end: Optional[int] = Field(
        default=None, ge=1, description="Ending line number in document"
    )
    token_count: int = Field(..., gt=0, description="Number of tokens in this chunk")
    start_char: int = Field(
        ..., ge=0, description="Starting character index in source"
    )
    end_char: int = Field(..., ge=0, description="Ending character index in source")
    bounding_boxes: Optional[list[BoundingBox]] = Field(
        default=None, description="Bounding boxes for PDF text highlighting"
    )
    source_file: Optional[str] = Field(
        default=None, description="Original filename of source document"
    )
    document_format: Optional[str] = Field(
        default=None, description="Format of source document (pdf/docx/txt)"
    )

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
