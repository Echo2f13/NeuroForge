"""NeuroForge — Source Package.

Convenience aggregation of all public classes from sub-packages.
Users can import directly from `src` or from individual sub-packages:

    # Top-level convenience imports
    from src import LLMClient
    from src import ingest, PDFLoader, DOCXLoader

    # Or from sub-packages directly
    from src.llm import LLMClient
    from src.ingestion import ingest, PDFLoader

Sub-packages:
- src.llm: Unified LLM client with provider fallback
- src.ingestion: Document loaders (PDF, DOCX, PPTX, Image, YouTube, Text)
- src.processing: Text cleaning, chunking, and structure extraction
- src.extraction: Topic, relationship, metadata, and element extraction
- src.store: Vector store (ChromaDB) and knowledge graph (NetworkX)
- src.retrieval: Hybrid retriever combining semantic, filtered, and graph search
- src.workflows: Content generation pipelines (quiz, flashcard, solution, etc.)
- src.memory: Progress tracking, adaptive difficulty, spaced repetition
- src.planner: Intent routing and parameter extraction
- src.agents: Multi-agent orchestration system
"""

# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------
from src.llm import LLMClient

# ---------------------------------------------------------------------------
# Ingestion — Document loaders and ingest orchestrator
# ---------------------------------------------------------------------------
from src.ingestion import (
    DOCXLoader,
    ImageLoader,
    PDFLoader,
    PPTXLoader,
    TextLoader,
    YouTubeLoader,
    ingest,
)

# ---------------------------------------------------------------------------
# Processing — Text cleaning, chunking, structure extraction
# ---------------------------------------------------------------------------
from src.processing import DocumentChunker, StructureExtractor, TextCleaner

# ---------------------------------------------------------------------------
# Extraction — Knowledge extraction from chunks
# ---------------------------------------------------------------------------
from src.extraction import (
    ElementExtractor,
    MetadataExtractor,
    RelationshipExtractor,
    TopicExtractor,
)

# ---------------------------------------------------------------------------
# Store — Vector store and knowledge graph
# ---------------------------------------------------------------------------
from src.store import KnowledgeGraph, VectorStore

# ---------------------------------------------------------------------------
# Retrieval — Hybrid retriever
# ---------------------------------------------------------------------------
from src.retrieval import Retriever

# ---------------------------------------------------------------------------
# Workflows — Content generation pipelines
# ---------------------------------------------------------------------------
from src.workflows import (
    AdditionalInfoWorkflow,
    ChatTutor,
    FlashcardWorkflow,
    MindMapWorkflow,
    QuizWorkflow,
    RevisionNotesWorkflow,
    SolutionWorkflow,
)

# ---------------------------------------------------------------------------
# Memory — Learning progress and adaptive difficulty
# ---------------------------------------------------------------------------
from src.memory import (
    AdaptiveDifficulty,
    ProgressTracker,
    RecommendationEngine,
    SpacedRepetitionScheduler,
)

# ---------------------------------------------------------------------------
# Planner — Intent routing
# ---------------------------------------------------------------------------
from src.planner import IntentRouter

# ---------------------------------------------------------------------------
# Agents — Multi-agent orchestration
# ---------------------------------------------------------------------------
from src.agents import MultiAgentOrchestrator

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
__all__ = [
    # LLM
    "LLMClient",
    # Ingestion
    "ingest",
    "PDFLoader",
    "DOCXLoader",
    "PPTXLoader",
    "ImageLoader",
    "YouTubeLoader",
    "TextLoader",
    # Processing
    "TextCleaner",
    "DocumentChunker",
    "StructureExtractor",
    # Extraction
    "TopicExtractor",
    "RelationshipExtractor",
    "MetadataExtractor",
    "ElementExtractor",
    # Store
    "VectorStore",
    "KnowledgeGraph",
    # Retrieval
    "Retriever",
    # Workflows
    "QuizWorkflow",
    "FlashcardWorkflow",
    "SolutionWorkflow",
    "RevisionNotesWorkflow",
    "MindMapWorkflow",
    "AdditionalInfoWorkflow",
    "ChatTutor",
    # Memory
    "ProgressTracker",
    "AdaptiveDifficulty",
    "SpacedRepetitionScheduler",
    "RecommendationEngine",
    # Planner
    "IntentRouter",
    # Agents
    "MultiAgentOrchestrator",
]
