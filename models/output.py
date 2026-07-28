"""Output Models for NeuroForge.

Defines models for generated learning outputs:
- QuizQuestion: A generated quiz question (MCQ, short answer, true/false)
- Flashcard: A study flashcard with spaced repetition support
- Solution: A structured answer to a question with marking scheme
- RevisionNote: Hierarchical revision notes for a topic
- SubtopicNote: Notes for a specific subtopic
- MindMapNode: A node in a mind map
- MindMap: Complete mind map with nodes and edges
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .knowledge import Difficulty


class QuizQuestion(BaseModel):
    """A generated quiz question.

    Supports MCQ, short answer, and true/false question types.

    Attributes:
        id: Unique question identifier.
        question: The question text.
        question_type: Type of question (mcq, short_answer, true_false).
        options: Answer options for MCQ questions.
        correct_answer: The correct answer.
        explanation: Explanation of why the answer is correct.
        topic: Topic this question covers.
        difficulty: Difficulty level.
        source_chunk_ids: Source chunks used to generate this question.
    """

    id: str = Field(..., min_length=1, description="Unique question identifier")
    question: str = Field(..., min_length=1, description="Question text")
    question_type: str = Field(
        ..., description="Question type: mcq, short_answer, or true_false"
    )
    options: Optional[list[str]] = Field(
        default=None, description="Answer options (required for MCQ)"
    )
    correct_answer: str = Field(..., min_length=1, description="Correct answer")
    explanation: str = Field(
        ..., min_length=1, description="Explanation for the correct answer"
    )
    topic: str = Field(..., min_length=1, description="Topic covered")
    difficulty: Difficulty = Field(..., description="Difficulty level")
    source_chunk_ids: list[str] = Field(
        default_factory=list, description="Source chunk IDs"
    )

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, v: str) -> str:
        """Validate that question_type is one of the allowed values."""
        allowed = {"mcq", "short_answer", "true_false"}
        if v not in allowed:
            raise ValueError(
                f"question_type must be one of {allowed}, got '{v}'"
            )
        return v

    @model_validator(mode="after")
    def validate_mcq_options(self) -> "QuizQuestion":
        """Validate that MCQ questions have exactly 4 options."""
        if self.question_type == "mcq":
            if self.options is None or len(self.options) != 4:
                raise ValueError(
                    "MCQ questions must have exactly 4 options"
                )
        return self

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "QuizQuestion":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "QuizQuestion":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class Flashcard(BaseModel):
    """A study flashcard with spaced repetition support.

    Attributes:
        id: Unique flashcard identifier.
        question: The front of the card (question/prompt).
        answer: The back of the card (answer).
        hint: Optional hint for difficult cards.
        mnemonic: Optional mnemonic device.
        related_topics: Topics related to this flashcard.
        difficulty: Difficulty level.
        source_chunk_ids: Source chunk IDs for traceability.
    """

    id: str = Field(..., min_length=1, description="Unique flashcard identifier")
    question: str = Field(..., min_length=1, description="Card front (question)")
    answer: str = Field(..., min_length=1, description="Card back (answer)")
    hint: Optional[str] = Field(default=None, description="Hint for difficult cards")
    mnemonic: Optional[str] = Field(default=None, description="Mnemonic device")
    related_topics: list[str] = Field(
        default_factory=list, description="Related topic names"
    )
    difficulty: Difficulty = Field(..., description="Difficulty level")
    source_chunk_ids: list[str] = Field(
        default_factory=list, description="Source chunk IDs"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Flashcard":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Flashcard":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class Solution(BaseModel):
    """A structured answer to a question with marking scheme.

    Scales depth based on marks allocation.

    Attributes:
        question: The question being answered.
        marks: Marks allocated to this question.
        answer: The full answer text.
        marking_scheme: Breakdown of marks by point.
        key_points: Key points that must be covered.
        topic: Topic this question belongs to.
    """

    question: str = Field(..., min_length=1, description="Question text")
    marks: int = Field(..., ge=1, le=100, description="Marks allocated (1-100)")
    answer: str = Field(..., min_length=1, description="Full answer text")
    marking_scheme: list[str] = Field(
        default_factory=list, description="Marks breakdown by point"
    )
    key_points: list[str] = Field(
        default_factory=list, description="Key points to cover"
    )
    topic: str = Field(..., min_length=1, description="Topic")

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Solution":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Solution":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class SubtopicNote(BaseModel):
    """Revision notes for a specific subtopic.

    Attributes:
        title: Subtopic title.
        points: Bullet points for this subtopic.
        importance: Importance level (high, medium, low).
    """

    title: str = Field(..., min_length=1, description="Subtopic title")
    points: list[str] = Field(
        ..., min_length=1, description="Bullet points"
    )
    importance: str = Field(
        default="medium", description="Importance: high, medium, or low"
    )

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v: str) -> str:
        """Validate that importance is one of the allowed values."""
        allowed = {"high", "medium", "low"}
        if v not in allowed:
            raise ValueError(
                f"importance must be one of {allowed}, got '{v}'"
            )
        return v

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "SubtopicNote":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "SubtopicNote":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class RevisionNote(BaseModel):
    """Hierarchical revision notes for a topic.

    Organizes information as topic → subtopics → bullet points.

    Attributes:
        topic: Main topic name.
        subtopics: List of subtopic notes.
        key_terms: Important terms and definitions.
        formulae: Relevant formulae.
        mnemonics: Memory aids.
    """

    topic: str = Field(..., min_length=1, description="Main topic name")
    subtopics: list[SubtopicNote] = Field(
        default_factory=list, description="Subtopic notes"
    )
    key_terms: list[str] = Field(
        default_factory=list, description="Key terms and definitions"
    )
    formulae: list[str] = Field(
        default_factory=list, description="Relevant formulae"
    )
    mnemonics: list[str] = Field(
        default_factory=list, description="Memory aids"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "RevisionNote":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "RevisionNote":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class MindMapNode(BaseModel):
    """A node in a mind map.

    Attributes:
        id: Unique node identifier.
        label: Display label for the node.
        type: Node type (topic, subtopic, concept, example).
        parent_id: ID of the parent node (None for root).
    """

    id: str = Field(..., min_length=1, description="Unique node identifier")
    label: str = Field(..., min_length=1, description="Display label")
    type: str = Field(
        ..., description="Node type: topic, subtopic, concept, or example"
    )
    parent_id: Optional[str] = Field(
        default=None, description="Parent node ID (None for root)"
    )

    @field_validator("type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        """Validate that type is one of the allowed values."""
        allowed = {"topic", "subtopic", "concept", "example"}
        if v not in allowed:
            raise ValueError(
                f"type must be one of {allowed}, got '{v}'"
            )
        return v

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "MindMapNode":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "MindMapNode":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class MindMap(BaseModel):
    """A complete mind map with nodes and edges.

    Attributes:
        nodes: All nodes in the mind map.
        edges: Connections between nodes (source, target, label).
    """

    nodes: list[MindMapNode] = Field(
        default_factory=list, description="Mind map nodes"
    )
    edges: list[dict] = Field(
        default_factory=list,
        description="Edges as dicts with 'source', 'target', 'label' keys",
    )

    @field_validator("edges")
    @classmethod
    def validate_edges(cls, v: list[dict]) -> list[dict]:
        """Validate that each edge has required keys."""
        for edge in v:
            if "source" not in edge or "target" not in edge:
                raise ValueError(
                    "Each edge must have 'source' and 'target' keys"
                )
        return v

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "MindMap":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "MindMap":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
