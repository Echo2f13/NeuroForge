"""Citation Models for NeuroForge.

Defines models for source attribution and citation display:
- Citation: A source citation linking generated content to source documents
- CitationGroup: A collection of citations for a single generated item
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .chunk import BoundingBox


class Citation(BaseModel):
    """A source citation for generated content.
    
    Links a piece of generated content (quiz answer, flashcard, etc.)
    back to the specific location in the source document where the
    information was extracted.
    
    Attributes:
        id: Unique citation identifier.
        chunk_id: ID of the source chunk.
        document_id: ID of the source document.
        document_name: Human-readable filename.
        document_format: File format (pdf/docx/txt).
        page_number: Page number in source (if applicable).
        paragraph_number: Paragraph number within page (if applicable).
        excerpt: Short text excerpt from source (~200 chars).
        full_text: Full chunk content.
        relevance_score: How relevant this source is (0-1).
        bounding_boxes: Bounding boxes for PDF highlighting.
        start_char: Starting character offset in document.
        end_char: Ending character offset in document.
        line_start: Starting line number (for text files).
        line_end: Ending line number (for text files).
        section_heading: Section heading containing this citation.
    """
    
    id: str = Field(..., min_length=1, description="Unique citation identifier")
    chunk_id: str = Field(..., min_length=1, description="Source chunk ID")
    document_id: str = Field(..., min_length=1, description="Source document ID")
    document_name: str = Field(..., min_length=1, description="Human-readable filename")
    document_format: str = Field(
        ..., 
        description="File format (pdf/docx/txt/image)"
    )
    page_number: Optional[int] = Field(
        default=None, ge=1, description="Page number in source document"
    )
    paragraph_number: Optional[int] = Field(
        default=None, ge=1, description="Paragraph number within page"
    )
    excerpt: str = Field(
        ..., 
        max_length=500, 
        description="Short text excerpt from source"
    )
    full_text: str = Field(..., description="Full chunk content")
    relevance_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Relevance score (0-1)"
    )
    bounding_boxes: Optional[list[BoundingBox]] = Field(
        default=None, description="Bounding boxes for PDF highlighting"
    )
    start_char: int = Field(..., ge=0, description="Starting character offset")
    end_char: int = Field(..., ge=0, description="Ending character offset")
    line_start: Optional[int] = Field(
        default=None, ge=1, description="Starting line number"
    )
    line_end: Optional[int] = Field(
        default=None, ge=1, description="Ending line number"
    )
    section_heading: Optional[str] = Field(
        default=None, description="Section heading containing this citation"
    )
    
    @field_validator("document_format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate document format is supported."""
        supported = {"pdf", "docx", "txt", "image", "markdown", "pptx"}
        v_lower = v.lower()
        if v_lower not in supported:
            raise ValueError(f"Unsupported format: {v}. Supported: {supported}")
        return v_lower
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict) -> "Citation":
        """Deserialize from dictionary."""
        return cls.model_validate(data)
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "Citation":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
    
    @classmethod
    def create_excerpt(cls, text: str, max_length: int = 200) -> str:
        """Create a truncated excerpt from full text.
        
        Args:
            text: Full text to excerpt.
            max_length: Maximum length of excerpt.
            
        Returns:
            Truncated text with ellipsis if needed.
        """
        if len(text) <= max_length:
            return text
        # Find a word boundary near max_length
        truncated = text[:max_length]
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.7:  # Only use word boundary if reasonable
            truncated = truncated[:last_space]
        return truncated.rstrip() + "..."


class CitationGroup(BaseModel):
    """Group of citations for a generated item.
    
    Associates multiple source citations with a single piece of
    generated content (e.g., a quiz question, flashcard, or chat response).
    
    Attributes:
        item_id: Unique ID of the generated item.
        item_type: Type of generated content (quiz/flashcard/note/chat).
        citations: List of source citations.
        primary_citation_id: ID of the most relevant citation (optional).
    """
    
    item_id: str = Field(..., min_length=1, description="ID of the generated item")
    item_type: str = Field(
        ..., 
        description="Type of content (quiz/flashcard/note/chat)"
    )
    citations: list[Citation] = Field(
        default_factory=list, 
        description="List of source citations"
    )
    primary_citation_id: Optional[str] = Field(
        default=None, 
        description="ID of the most relevant citation"
    )
    
    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        """Validate item type is supported."""
        supported = {"quiz", "flashcard", "note", "chat", "solution", "mindmap"}
        v_lower = v.lower()
        if v_lower not in supported:
            raise ValueError(f"Unsupported item type: {v}. Supported: {supported}")
        return v_lower
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict) -> "CitationGroup":
        """Deserialize from dictionary."""
        return cls.model_validate(data)
    
    def get_primary_citation(self) -> Optional[Citation]:
        """Get the primary (most relevant) citation.
        
        Returns:
            Primary citation if set, or highest relevance citation,
            or None if no citations.
        """
        if not self.citations:
            return None
        
        if self.primary_citation_id:
            for cit in self.citations:
                if cit.id == self.primary_citation_id:
                    return cit
        
        # Fall back to highest relevance
        return max(self.citations, key=lambda c: c.relevance_score)
    
    def sort_by_relevance(self) -> None:
        """Sort citations by relevance score (highest first)."""
        self.citations.sort(key=lambda c: c.relevance_score, reverse=True)
    
    def sort_by_page(self) -> None:
        """Sort citations by page number (for document order)."""
        self.citations.sort(
            key=lambda c: (c.page_number or 0, c.start_char)
        )
    
    @property
    def document_count(self) -> int:
        """Count unique source documents."""
        return len(set(c.document_id for c in self.citations))
    
    @property
    def page_range(self) -> str:
        """Get formatted page range string."""
        pages = sorted(set(
            c.page_number for c in self.citations if c.page_number
        ))
        if not pages:
            return ""
        if len(pages) == 1:
            return f"p. {pages[0]}"
        if pages == list(range(pages[0], pages[-1] + 1)):
            return f"pp. {pages[0]}-{pages[-1]}"
        return f"pp. {', '.join(map(str, pages))}"
