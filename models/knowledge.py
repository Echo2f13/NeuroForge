"""Knowledge Models for NeuroForge.

Defines models for knowledge extraction results:
- Difficulty: Difficulty level enum
- Concept: A knowledge concept extracted from material
- ConceptRelationship: Relationship between two concepts
- KnowledgeExtraction: Complete extraction results
- Formula: A mathematical formula or equation
- Example: An illustrative example
- KeyDate: An important date/event
- KeyPerson: An important person/contributor
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Difficulty(str, Enum):
    """Difficulty level for concepts and questions."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Concept(BaseModel):
    """A knowledge concept extracted from study material.

    Attributes:
        id: Unique identifier for the concept.
        name: Short name of the concept.
        definition: Clear definition or explanation.
        topics: List of topics this concept belongs to.
        difficulty: Assessed difficulty level.
        prerequisites: IDs of prerequisite concepts.
        keywords: Associated keywords for search.
        source_chunk_ids: Chunk IDs where this concept was found.
    """

    id: str = Field(..., min_length=1, description="Unique concept identifier")
    name: str = Field(..., min_length=1, description="Concept name")
    definition: str = Field(..., min_length=1, description="Concept definition")
    topics: list[str] = Field(
        ..., min_length=1, description="Topics this concept belongs to"
    )
    difficulty: Difficulty = Field(..., description="Difficulty level")
    prerequisites: list[str] = Field(
        default_factory=list, description="Prerequisite concept IDs"
    )
    keywords: list[str] = Field(
        default_factory=list, description="Associated keywords"
    )
    source_chunk_ids: list[str] = Field(
        default_factory=list, description="Source chunk IDs for traceability"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Concept":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Concept":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class ConceptRelationship(BaseModel):
    """A directional relationship between two concepts.

    Attributes:
        source_concept: ID of the source concept.
        target_concept: ID of the target concept.
        relationship_type: Type of relationship (prerequisite, related, part_of).
    """

    source_concept: str = Field(
        ..., min_length=1, description="Source concept identifier"
    )
    target_concept: str = Field(
        ..., min_length=1, description="Target concept identifier"
    )
    relationship_type: str = Field(
        ..., min_length=1, description="Relationship type (prerequisite, related, part_of)"
    )

    @field_validator("relationship_type")
    @classmethod
    def validate_relationship_type(cls, v: str) -> str:
        """Validate that relationship_type is one of the allowed values."""
        allowed = {"prerequisite", "related", "part_of"}
        if v not in allowed:
            raise ValueError(
                f"relationship_type must be one of {allowed}, got '{v}'"
            )
        return v

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "ConceptRelationship":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "ConceptRelationship":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class Formula(BaseModel):
    """A mathematical formula or equation extracted from material.

    Attributes:
        expression: The formula expression (LaTeX or plain text).
        description: What the formula represents.
        context: Context in which the formula is used.
        source_chunk_id: ID of the source chunk.
    """

    expression: str = Field(..., min_length=1, description="Formula expression")
    description: str = Field(
        ..., min_length=1, description="Description of what the formula represents"
    )
    context: str = Field(
        ..., min_length=1, description="Context of formula usage"
    )
    source_chunk_id: str = Field(
        ..., min_length=1, description="Source chunk identifier"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Formula":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Formula":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class Example(BaseModel):
    """An illustrative example extracted from material.

    Attributes:
        title: Short title for the example.
        content: Full example content.
        related_concepts: IDs of related concepts.
        source_chunk_id: ID of the source chunk.
    """

    title: str = Field(..., min_length=1, description="Example title")
    content: str = Field(..., min_length=1, description="Example content")
    related_concepts: list[str] = Field(
        default_factory=list, description="Related concept IDs"
    )
    source_chunk_id: str = Field(
        ..., min_length=1, description="Source chunk identifier"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Example":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Example":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class KeyDate(BaseModel):
    """An important date or event extracted from material.

    Attributes:
        date: The date (string format for flexibility).
        event: What happened on this date.
        significance: Why this date matters.
        source_chunk_id: ID of the source chunk.
    """

    date: str = Field(..., min_length=1, description="Date string")
    event: str = Field(..., min_length=1, description="Event description")
    significance: str = Field(
        ..., min_length=1, description="Why this date is important"
    )
    source_chunk_id: str = Field(
        ..., min_length=1, description="Source chunk identifier"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "KeyDate":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "KeyDate":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class KeyPerson(BaseModel):
    """An important person extracted from material.

    Attributes:
        name: Person's name.
        role: Their role or title.
        contribution: Their key contribution or significance.
        source_chunk_id: ID of the source chunk.
    """

    name: str = Field(..., min_length=1, description="Person's name")
    role: str = Field(..., min_length=1, description="Role or title")
    contribution: str = Field(
        ..., min_length=1, description="Key contribution or significance"
    )
    source_chunk_id: str = Field(
        ..., min_length=1, description="Source chunk identifier"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "KeyPerson":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "KeyPerson":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class KnowledgeExtraction(BaseModel):
    """Complete knowledge extraction results from a document or chunk set.

    Aggregates all extracted knowledge elements.

    Attributes:
        concepts: Extracted concepts.
        relationships: Concept relationships.
        formulae: Extracted formulae.
        examples: Extracted examples.
        key_dates: Important dates.
        key_people: Important people.
    """

    concepts: list[Concept] = Field(
        default_factory=list, description="Extracted concepts"
    )
    relationships: list[ConceptRelationship] = Field(
        default_factory=list, description="Concept relationships"
    )
    formulae: list[Formula] = Field(
        default_factory=list, description="Extracted formulae"
    )
    examples: list[Example] = Field(
        default_factory=list, description="Extracted examples"
    )
    key_dates: list[KeyDate] = Field(
        default_factory=list, description="Important dates"
    )
    key_people: list[KeyPerson] = Field(
        default_factory=list, description="Important people"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeExtraction":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "KnowledgeExtraction":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
