"""Subject Models for NeuroForge.

Defines models for the subject/session management system:
- Subject: Core subject model representing a study subject/course
- SubjectSummary: Lightweight subject info for lists
- SubjectSettings: Per-subject customization settings
- SubjectDocument: Document metadata within a subject
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SubjectStatus(str, Enum):
    """Status of a subject."""
    ACTIVE = "active"
    ARCHIVED = "archived"


class SubjectSettings(BaseModel):
    """Per-subject customization settings.
    
    Attributes:
        default_difficulty: Default difficulty for quizzes/flashcards.
        default_quiz_count: Default number of quiz questions.
        default_flashcard_count: Default number of flashcards.
        track_streak_separately: If True, streak is tracked per-subject.
    """
    default_difficulty: Optional[str] = Field(
        None, 
        description="Default difficulty: easy, medium, hard"
    )
    default_quiz_count: int = Field(
        default=10, 
        ge=1, 
        le=50, 
        description="Default number of quiz questions"
    )
    default_flashcard_count: int = Field(
        default=10, 
        ge=1, 
        le=50, 
        description="Default number of flashcards"
    )
    track_streak_separately: bool = Field(
        default=False, 
        description="If True, streak is per-subject"
    )

    @field_validator("default_difficulty")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        """Validate difficulty is one of allowed values."""
        if v is not None:
            allowed = {"easy", "medium", "hard"}
            if v.lower() not in allowed:
                raise ValueError(f"difficulty must be one of {allowed}, got '{v}'")
            return v.lower()
        return v


class Subject(BaseModel):
    """Core subject model representing a study subject/course.
    
    A subject is an isolated learning environment containing:
    - Its own documents and chunks
    - Its own knowledge graph
    - Its own learning progress and flashcard scheduling
    
    Attributes:
        id: Unique identifier (UUID).
        name: Display name (1-100 characters).
        description: Optional description (max 500 characters).
        color: Optional hex color for UI (e.g., "#FF5733").
        icon: Optional emoji or icon identifier.
        status: Active or archived.
        settings: Per-subject settings.
        is_default: Whether this is the default subject.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        last_activity_at: Last activity (upload, quiz, etc.) timestamp.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), 
        description="Unique subject ID"
    )
    name: str = Field(
        ..., 
        min_length=1, 
        max_length=100, 
        description="Subject name"
    )
    description: Optional[str] = Field(
        None, 
        max_length=500, 
        description="Subject description"
    )
    color: Optional[str] = Field(
        None, 
        pattern=r'^#[0-9A-Fa-f]{6}$', 
        description="Hex color code"
    )
    icon: Optional[str] = Field(
        None, 
        max_length=10,
        description="Emoji or icon identifier"
    )
    status: SubjectStatus = Field(
        default=SubjectStatus.ACTIVE, 
        description="Subject status"
    )
    settings: SubjectSettings = Field(
        default_factory=SubjectSettings, 
        description="Subject settings"
    )
    is_default: bool = Field(
        default=False, 
        description="Whether this is the default subject"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, 
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, 
        description="Last update timestamp"
    )
    last_activity_at: Optional[datetime] = Field(
        None, 
        description="Last activity timestamp"
    )

    def update_activity(self) -> None:
        """Update the last activity timestamp to now."""
        self.last_activity_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> "Subject":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Subject":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class SubjectSummary(BaseModel):
    """Lightweight subject info for lists.
    
    Contains only the essential fields needed for displaying
    subjects in a list or selector, plus computed stats.
    
    Attributes:
        id: Unique subject ID.
        name: Subject name.
        description: Optional description (truncated).
        color: Hex color for UI.
        icon: Emoji or icon.
        status: Active or archived.
        is_default: Whether this is the default subject.
        document_count: Number of documents in subject.
        chunk_count: Number of chunks in subject.
        concept_count: Number of concepts extracted.
        quiz_count: Number of quizzes taken.
        average_score: Average quiz score.
        mastery_percent: Overall mastery percentage.
        last_activity_at: Last activity timestamp.
    """
    id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    status: SubjectStatus = SubjectStatus.ACTIVE
    is_default: bool = False
    
    # Computed stats (calculated when building summary)
    document_count: int = 0
    chunk_count: int = 0
    concept_count: int = 0
    quiz_count: int = 0
    average_score: float = 0.0
    mastery_percent: float = 0.0
    last_activity_at: Optional[datetime] = None

    @classmethod
    def from_subject(
        cls, 
        subject: Subject, 
        document_count: int = 0,
        chunk_count: int = 0,
        concept_count: int = 0,
        quiz_count: int = 0,
        average_score: float = 0.0,
        mastery_percent: float = 0.0,
    ) -> "SubjectSummary":
        """Create a summary from a Subject with stats."""
        return cls(
            id=subject.id,
            name=subject.name,
            description=subject.description[:100] + "..." if subject.description and len(subject.description) > 100 else subject.description,
            color=subject.color,
            icon=subject.icon,
            status=subject.status,
            is_default=subject.is_default,
            document_count=document_count,
            chunk_count=chunk_count,
            concept_count=concept_count,
            quiz_count=quiz_count,
            average_score=average_score,
            mastery_percent=mastery_percent,
            last_activity_at=subject.last_activity_at,
        )


class SubjectDocument(BaseModel):
    """Document metadata within a subject.
    
    Tracks information about documents uploaded to a subject.
    
    Attributes:
        id: Unique document ID (hash of filename).
        subject_id: Subject this document belongs to.
        filename: Original filename.
        upload_date: When the document was uploaded.
        file_type: Document type (pdf, docx, pptx, etc.).
        chunk_count: Number of chunks created from document.
        concept_count: Number of concepts extracted.
        file_size_bytes: File size in bytes (if known).
    """
    id: str = Field(..., description="Unique document ID")
    subject_id: str = Field(..., description="Parent subject ID")
    filename: str = Field(..., description="Original filename")
    upload_date: datetime = Field(
        default_factory=datetime.utcnow, 
        description="Upload timestamp"
    )
    file_type: str = Field(..., description="File type (pdf, docx, etc.)")
    chunk_count: int = Field(default=0, ge=0, description="Number of chunks")
    concept_count: int = Field(default=0, ge=0, description="Number of concepts")
    file_size_bytes: Optional[int] = Field(None, ge=0, description="File size")

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> "SubjectDocument":
        """Deserialize from dictionary."""
        return cls.model_validate(data)


class SubjectDocumentList(BaseModel):
    """List of documents in a subject.
    
    Attributes:
        subject_id: Subject ID.
        documents: List of document metadata.
        total_count: Total number of documents.
    """
    subject_id: str
    documents: list[SubjectDocument] = Field(default_factory=list)
    total_count: int = 0
