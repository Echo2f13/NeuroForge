"""NeuroForge Data Models.

This module exports all Pydantic data models used throughout the
NeuroForge adaptive learning engine.

Model Groups:
- Core Document: InputFormat, DocumentMetadata, Document, Section, StoredDocument
- Chunk: BoundingBox, Chunk, ChunkMetadata
- Citation: Citation, CitationGroup
- Knowledge: Difficulty, Concept, ConceptRelationship, KnowledgeExtraction,
             Formula, Example, KeyDate, KeyPerson
- Output: QuizQuestion, Flashcard, Solution, RevisionNote, SubtopicNote,
          MindMapNode, MindMap
- Learning State: TopicProgress, LearningState
- Subject: Subject, SubjectSummary, SubjectSettings, SubjectStatus,
           SubjectDocument, SubjectDocumentList
"""

from .chunk import BoundingBox, Chunk, ChunkMetadata
from .citation import Citation, CitationGroup
from .document import Document, DocumentMetadata, InputFormat, Section, StoredDocument
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
from .subject import (
    Subject,
    SubjectDocument,
    SubjectDocumentList,
    SubjectSettings,
    SubjectStatus,
    SubjectSummary,
)

__all__ = [
    # Core Document Models
    "InputFormat",
    "DocumentMetadata",
    "Document",
    "Section",
    "StoredDocument",
    # Chunk Models
    "BoundingBox",
    "Chunk",
    "ChunkMetadata",
    # Citation Models
    "Citation",
    "CitationGroup",
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
    # Subject Models
    "Subject",
    "SubjectSummary",
    "SubjectSettings",
    "SubjectStatus",
    "SubjectDocument",
    "SubjectDocumentList",
]
