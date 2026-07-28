"""NeuroForge Data Models.

This module exports all Pydantic data models used throughout the
NeuroForge adaptive learning engine.

Model Groups:
- Core Document: InputFormat, DocumentMetadata, Document, Section
- Chunk: Chunk, ChunkMetadata
- Knowledge: Difficulty, Concept, ConceptRelationship, KnowledgeExtraction,
             Formula, Example, KeyDate, KeyPerson
- Output: QuizQuestion, Flashcard, Solution, RevisionNote, SubtopicNote,
          MindMapNode, MindMap
- Learning State: TopicProgress, LearningState
"""

from .chunk import Chunk, ChunkMetadata
from .document import Document, DocumentMetadata, InputFormat, Section
from .knowledge import (
    Concept,
    ConceptRelationship,
    Difficulty,
    Example,
    Formula,
    KeyDate,
    KeyPerson,
    KnowledgeExtraction,
)
from .learning import LearningState, TopicProgress
from .output import (
    Flashcard,
    MindMap,
    MindMapNode,
    QuizQuestion,
    RevisionNote,
    Solution,
    SubtopicNote,
)

__all__ = [
    # Core Document Models
    "InputFormat",
    "DocumentMetadata",
    "Document",
    "Section",
    # Chunk Models
    "Chunk",
    "ChunkMetadata",
    # Knowledge Models
    "Difficulty",
    "Concept",
    "ConceptRelationship",
    "KnowledgeExtraction",
    "Formula",
    "Example",
    "KeyDate",
    "KeyPerson",
    # Output Models
    "QuizQuestion",
    "Flashcard",
    "Solution",
    "RevisionNote",
    "SubtopicNote",
    "MindMapNode",
    "MindMap",
    # Learning State Models
    "TopicProgress",
    "LearningState",
]
