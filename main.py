"""NeuroForge — FastAPI Backend Application.

A FastAPI-powered backend that exposes the NeuroForge adaptive learning engine
via REST APIs. Integrates document ingestion, knowledge extraction, quiz/flashcard
generation, chat tutoring, and learning progress tracking.

Run with: uvicorn main:app --reload
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import subject manager exceptions at module level
from src.subjects.manager import (
    SubjectNotFoundError,
    SubjectExistsError,
    DefaultSubjectError,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("neuroforge.api")


# ---------------------------------------------------------------------------
# Lifespan & Application Setup
# ---------------------------------------------------------------------------

# Global instances (initialized in lifespan)
_llm_client = None
_vector_store = None
_knowledge_graph = None
_retriever = None
_progress_tracker = None
_sr_scheduler = None
_orchestrator = None
_subject_manager = None  # NEW: Subject manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up application resources."""
    global _llm_client, _vector_store, _knowledge_graph
    global _retriever, _progress_tracker, _sr_scheduler, _orchestrator
    global _subject_manager

    logger.info("Starting NeuroForge API...")

    # Import dependencies
    from src.llm import LLMClient
    from src.store.vector_store import VectorStore
    from src.store.knowledge_graph import KnowledgeGraph
    from src.retrieval.retriever import Retriever
    from src.memory.progress import ProgressTracker
    from src.memory.spaced_repetition import SpacedRepetitionScheduler
    from src.agents.multi_agent import MultiAgentOrchestrator
    from src.subjects import SubjectManager, needs_migration, migrate_to_subjects

    # Check for and run migration if needed
    if needs_migration():
        logger.info("Migration needed. Running migration to subject-based organization...")
        migration_result = migrate_to_subjects()
        logger.info(f"Migration completed with status: {migration_result['status']}")
        if migration_result['status'] not in ('success', 'already_complete', 'not_needed'):
            logger.warning(f"Migration had issues: {migration_result.get('errors', [])}")

    # Initialize subject manager (NEW)
    _subject_manager = SubjectManager(data_dir="./data")
    logger.info(f"Subject manager initialized with {len(_subject_manager._subjects)} subjects")

    # Initialize core components
    _llm_client = LLMClient()
    _vector_store = VectorStore(persist_directory="./chroma_db/")
    _vector_store.init_collections()
    _knowledge_graph = KnowledgeGraph()

    # Try to load existing knowledge graph (for backward compatibility)
    kg_path = Path("./knowledge_graph.json")
    if kg_path.exists():
        try:
            _knowledge_graph.load(str(kg_path))
            logger.info(f"Loaded knowledge graph with {len(_knowledge_graph)} concepts")
        except Exception as e:
            logger.warning(f"Could not load knowledge graph: {e}")

    # Initialize retriever
    _retriever = Retriever(vector_store=_vector_store, knowledge_graph=_knowledge_graph)

    # Initialize memory components
    _progress_tracker = ProgressTracker(state_file="./learning_state.json")
    _sr_scheduler = SpacedRepetitionScheduler(state_file="./sr_state.json")

    # Initialize orchestrator
    _orchestrator = MultiAgentOrchestrator(
        llm_client=_llm_client,
        retriever=_retriever,
        knowledge_graph=_knowledge_graph,
        progress_tracker=_progress_tracker,
        scheduler=_sr_scheduler,
    )

    logger.info("NeuroForge API initialized successfully!")

    yield

    # Cleanup
    logger.info("Shutting down NeuroForge API...")
    _progress_tracker.save()
    _sr_scheduler.save()
    if len(_knowledge_graph) > 0:
        _knowledge_graph.save(str(kg_path))
    
    # Save all subject data
    if _subject_manager:
        _subject_manager.save_all()


app = FastAPI(
    title="NeuroForge API",
    description="Adaptive Learning Engine - Transform study material into personalized learning experiences",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    message: str
    components: dict


class UploadResponse(BaseModel):
    status: str
    message: str
    document_id: str
    chunks_created: int
    concepts_extracted: int


class QuizRequest(BaseModel):
    topic: str = Field(..., description="Topic for quiz generation")
    subject_id: Optional[str] = Field(default="general", description="Subject ID (defaults to 'general')")
    difficulty: Optional[str] = Field(None, description="easy, medium, or hard")
    num_questions: int = Field(default=10, ge=1, le=50)
    question_types: Optional[list[str]] = Field(
        default=None, description="mcq, short_answer, true_false"
    )


class FlashcardRequest(BaseModel):
    topic: str = Field(..., description="Topic for flashcard generation")
    subject_id: Optional[str] = Field(default="general", description="Subject ID (defaults to 'general')")
    difficulty: Optional[str] = Field(None, description="easy, medium, or hard")
    num_cards: int = Field(default=10, ge=1, le=50)


class NotesRequest(BaseModel):
    topic: str = Field(..., description="Topic for revision notes generation")
    subject_id: Optional[str] = Field(default="general", description="Subject ID (defaults to 'general')")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User's question or message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    subject_id: Optional[str] = Field(default="general", description="Subject ID (defaults to 'general')")


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    is_grounded: bool
    session_id: str


class MindMapRequest(BaseModel):
    topic: str = Field(..., description="Topic for mind map generation")
    subject_id: Optional[str] = Field(default="general", description="Subject ID (defaults to 'general')")
    max_depth: int = Field(default=3, ge=1, le=5)


class AdditionalInfoRequest(BaseModel):
    topic: str = Field(..., description="Topic for additional info generation")
    subject_id: Optional[str] = Field(default="general", description="Subject ID (defaults to 'general')")


class SolutionRequest(BaseModel):
    question: str = Field(..., description="The question to answer")
    topic: str = Field(default="General", description="Topic/subject area")
    subject_id: Optional[str] = Field(default="general", description="Subject ID (defaults to 'general')")
    marks: int = Field(default=5, ge=1, le=20, description="Mark allocation affects depth")


class ScoreRequest(BaseModel):
    topic: str = Field(..., description="Topic the quiz was about")
    subject_id: Optional[str] = Field(default="general", description="Subject ID (defaults to 'general')")
    score: float = Field(..., ge=0, le=100, description="Quiz score (0-100)")


class CardReviewRequest(BaseModel):
    card_id: str = Field(..., description="Flashcard ID")
    quality: int = Field(..., ge=0, le=5, description="Review quality (0-5)")


class ProcessRequest(BaseModel):
    """Generic request for the multi-agent orchestrator."""
    query: str = Field(..., description="Natural language query")


# ---------------------------------------------------------------------------
# Subject Request/Response Models
# ---------------------------------------------------------------------------


class CreateSubjectRequest(BaseModel):
    """Request to create a new subject."""
    name: str = Field(..., min_length=1, max_length=100, description="Subject name")
    description: Optional[str] = Field(None, max_length=500, description="Description")
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="Hex color")
    icon: Optional[str] = Field(None, max_length=10, description="Emoji icon")


class UpdateSubjectRequest(BaseModel):
    """Request to update a subject."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: Optional[str] = Field(None, max_length=10)


class MoveDocumentRequest(BaseModel):
    """Request to move a document to another subject."""
    target_subject_id: str = Field(..., description="Destination subject ID")


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def get_components():
    """Get initialized component instances."""
    return {
        "llm_client": _llm_client,
        "vector_store": _vector_store,
        "knowledge_graph": _knowledge_graph,
        "retriever": _retriever,
        "progress_tracker": _progress_tracker,
        "sr_scheduler": _sr_scheduler,
        "orchestrator": _orchestrator,
        "subject_manager": _subject_manager,  # NEW
    }


# Chat session storage (in-memory for now)
_chat_sessions: dict[str, Any] = {}


def get_or_create_chat_session(
    session_id: Optional[str],
    subject_id: str = "general",
) -> tuple[str, Any]:
    """Get existing or create new chat tutor session.
    
    Args:
        session_id: Existing session ID (can include subject prefix).
        subject_id: Subject identifier for scoped retrieval.
        
    Returns:
        Tuple of (session_id, ChatTutor instance).
    """
    from src.workflows.chat_tutor import ChatTutor

    if session_id and session_id in _chat_sessions:
        return session_id, _chat_sessions[session_id]

    # Create new session
    new_id = str(uuid.uuid4())
    
    # Get subject-scoped retriever
    components = get_components()
    subject_manager = components["subject_manager"]
    
    if subject_manager.subject_exists(subject_id):
        retriever = subject_manager.get_subject_retriever(subject_id)
    else:
        retriever = _retriever
    
    tutor = ChatTutor(
        retriever=retriever, 
        llm_client=_llm_client,
        subject_id=subject_id,
    )
    _chat_sessions[new_id] = tutor
    return new_id, tutor


# ---------------------------------------------------------------------------
# Endpoints: Health & Info
# ---------------------------------------------------------------------------


@app.get("/", tags=["Info"])
async def root():
    """API root - basic info."""
    return {
        "name": "NeuroForge API",
        "version": "1.0.0",
        "description": "Adaptive Learning Engine",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["Info"])
async def health_check():
    """Check API health and component status."""
    components = get_components()
    
    status = {
        "llm_client": components["llm_client"] is not None,
        "vector_store": components["vector_store"] is not None,
        "knowledge_graph": components["knowledge_graph"] is not None,
        "retriever": components["retriever"] is not None,
    }
    
    all_healthy = all(status.values())
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        message="All components operational" if all_healthy else "Some components unavailable",
        components=status,
    )


@app.get("/stats", tags=["Info"])
async def get_stats():
    """Get knowledge base and learning statistics."""
    components = get_components()
    
    vs_stats = components["vector_store"].get_stats()
    kg_size = len(components["knowledge_graph"])
    learning_stats = components["progress_tracker"].get_overall_stats()
    
    return {
        "knowledge_base": {
            "chunks": vs_stats["chunk_count"],
            "concepts": vs_stats["concept_count"],
            "graph_nodes": kg_size,
        },
        "learning": learning_stats,
    }


# ---------------------------------------------------------------------------
# Endpoints: Document Ingestion
# ---------------------------------------------------------------------------

# Upload job tracking (in-memory, for production use Redis)
_upload_jobs: dict[str, dict[str, Any]] = {}


class UploadJobStatus(BaseModel):
    """Status of an upload job."""
    job_id: str
    status: str  # "pending", "processing", "extracting", "completed", "failed"
    progress: int  # 0-100
    message: str
    document_id: Optional[str] = None
    chunks_created: int = 0
    concepts_extracted: int = 0
    error: Optional[str] = None


def process_document_background(
    job_id: str,
    file_path: str,
    filename: str,
):
    """Background task for document processing."""
    import hashlib
    from src.ingestion import ingest
    from src.processing import DocumentChunker
    from src.extraction.robust_extractor import RobustExtractor
    
    try:
        # Update status: processing
        _upload_jobs[job_id]["status"] = "processing"
        _upload_jobs[job_id]["progress"] = 10
        _upload_jobs[job_id]["message"] = "Ingesting document..."
        
        # Ingest document
        document = ingest(file_path)
        document.metadata.source = filename
        doc_id = hashlib.sha256(filename.encode()).hexdigest()[:12]
        
        _upload_jobs[job_id]["document_id"] = doc_id
        _upload_jobs[job_id]["progress"] = 30
        _upload_jobs[job_id]["message"] = "Chunking document..."
        
        # Chunk the document
        chunker = DocumentChunker()
        chunks = chunker.chunk(document, strategy="paragraph")
        
        _upload_jobs[job_id]["chunks_created"] = len(chunks)
        _upload_jobs[job_id]["progress"] = 50
        _upload_jobs[job_id]["message"] = f"Created {len(chunks)} chunks. Storing..."
        
        # Store chunks
        components = get_components()
        components["vector_store"].add_chunks(chunks)
        
        _upload_jobs[job_id]["progress"] = 60
        _upload_jobs[job_id]["status"] = "extracting"
        _upload_jobs[job_id]["message"] = "Extracting knowledge concepts..."
        
        # Extract knowledge using robust extractor
        try:
            extractor = RobustExtractor(llm_client=components["llm_client"])
            knowledge = extractor.extract(chunks)
            
            _upload_jobs[job_id]["progress"] = 85
            _upload_jobs[job_id]["message"] = f"Extracted {len(knowledge.concepts)} concepts. Saving..."
            
            if knowledge.concepts:
                components["vector_store"].add_concepts(knowledge.concepts)
                components["knowledge_graph"].add_concepts(knowledge.concepts)
                _upload_jobs[job_id]["concepts_extracted"] = len(knowledge.concepts)
            
            if knowledge.relationships:
                components["knowledge_graph"].add_relationships(knowledge.relationships)
            
            components["knowledge_graph"].save("./knowledge_graph.json")
            
        except Exception as e:
            logger.warning(f"Knowledge extraction failed: {e}")
            _upload_jobs[job_id]["message"] = f"Chunks stored. Concept extraction partial: {e}"
        
        # Complete
        _upload_jobs[job_id]["status"] = "completed"
        _upload_jobs[job_id]["progress"] = 100
        _upload_jobs[job_id]["message"] = f"Successfully processed {filename}"
        
    except Exception as e:
        logger.error(f"Background processing failed: {e}")
        _upload_jobs[job_id]["status"] = "failed"
        _upload_jobs[job_id]["error"] = str(e)
        _upload_jobs[job_id]["message"] = f"Processing failed: {e}"
    
    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            os.unlink(file_path)


@app.post("/upload", response_model=UploadResponse, tags=["Ingestion"])
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    async_mode: bool = False,
):
    """Upload and process a document (PDF, PPTX, DOCX, or image).
    
    Supported formats:
    - PDF (.pdf)
    - PowerPoint (.pptx)
    - Word Document (.docx)
    - Images (.png, .jpg, .jpeg)
    - Text/Markdown (.txt, .md)
    
    Set async_mode=true to process in background and get a job_id for status tracking.
    """
    from src.ingestion import ingest, detect_format, UnsupportedFormatError
    from src.processing import DocumentChunker
    from src.extraction.robust_extractor import RobustExtractor

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    try:
        detect_format(file.filename)
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Save uploaded file temporarily
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    # Async mode: process in background
    if async_mode and background_tasks:
        job_id = str(uuid.uuid4())
        _upload_jobs[job_id] = {
            "status": "pending",
            "progress": 0,
            "message": "Upload received, starting processing...",
            "document_id": None,
            "chunks_created": 0,
            "concepts_extracted": 0,
            "error": None,
        }
        
        background_tasks.add_task(
            process_document_background,
            job_id,
            tmp_path,
            file.filename,
        )
        
        return UploadResponse(
            status="processing",
            message=f"Processing started. Track status at /upload/status/{job_id}",
            document_id=job_id,
            chunks_created=0,
            concepts_extracted=0,
        )

    # Sync mode: process immediately
    try:
        # Ingest document
        logger.info(f"Processing uploaded file: {file.filename}")
        document = ingest(tmp_path)
        
        # Update the source in metadata to use the original filename
        document.metadata.source = file.filename
        
        # Generate a document ID from the filename
        import hashlib
        doc_id = hashlib.sha256(file.filename.encode()).hexdigest()[:12]
        
        # Chunk the document
        chunker = DocumentChunker()
        chunks = chunker.chunk(document, strategy="paragraph")
        logger.info(f"Created {len(chunks)} chunks from document")

        # Store chunks in vector store
        components = get_components()
        components["vector_store"].add_chunks(chunks)

        # Extract knowledge using robust extractor
        concepts_extracted = 0
        try:
            extractor = RobustExtractor(llm_client=components["llm_client"])
            knowledge = extractor.extract(chunks)
            
            if knowledge.concepts:
                components["vector_store"].add_concepts(knowledge.concepts)
                components["knowledge_graph"].add_concepts(knowledge.concepts)
                concepts_extracted = len(knowledge.concepts)
                
            if knowledge.relationships:
                components["knowledge_graph"].add_relationships(knowledge.relationships)
                
            components["knowledge_graph"].save("./knowledge_graph.json")
            logger.info(f"Extracted {concepts_extracted} concepts and {len(knowledge.relationships)} relationships")
            
        except Exception as e:
            logger.warning(f"Knowledge extraction partial failure: {e}")
            import traceback
            logger.warning(traceback.format_exc())

        return UploadResponse(
            status="success",
            message=f"Document '{file.filename}' processed successfully",
            document_id=doc_id,
            chunks_created=len(chunks),
            concepts_extracted=concepts_extracted,
        )

    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/upload/status/{job_id}", response_model=UploadJobStatus, tags=["Ingestion"])
async def get_upload_status(job_id: str):
    """Get the status of a background upload job."""
    if job_id not in _upload_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = _upload_jobs[job_id]
    return UploadJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        document_id=job.get("document_id"),
        chunks_created=job.get("chunks_created", 0),
        concepts_extracted=job.get("concepts_extracted", 0),
        error=job.get("error"),
    )


@app.post("/upload/youtube", tags=["Ingestion"])
async def upload_youtube(url: str = Form(...)):
    """Process a YouTube video (extracts transcript).
    
    Provide a YouTube URL to extract and process the video transcript.
    """
    from src.ingestion import ingest, detect_format, UnsupportedFormatError
    from src.processing import DocumentChunker

    try:
        fmt = detect_format(url)
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        logger.info(f"Processing YouTube URL: {url}")
        document = ingest(url)
        
        chunker = DocumentChunker()
        chunks = chunker.chunk(document)
        
        components = get_components()
        components["vector_store"].add_chunks(chunks)

        return {
            "status": "success",
            "message": f"YouTube video processed successfully",
            "document_id": document.id,
            "title": document.metadata.get("title", "Unknown"),
            "chunks_created": len(chunks),
        }

    except Exception as e:
        logger.error(f"YouTube processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# ---------------------------------------------------------------------------
# Endpoints: Content Generation
# ---------------------------------------------------------------------------


@app.post("/quiz", tags=["Generation"])
async def generate_quiz(request: QuizRequest):
    """Generate quiz questions for a topic.
    
    Returns MCQ, short answer, and/or true/false questions based on
    uploaded study material. Optionally scoped to a specific subject.
    """
    from src.workflows.quiz import QuizWorkflow

    components = get_components()
    subject_id = request.subject_id or "general"
    
    # Get subject-scoped retriever if subject_id is provided
    subject_manager = components["subject_manager"]
    if subject_manager.subject_exists(subject_id):
        retriever = subject_manager.get_subject_retriever(subject_id)
    else:
        retriever = components["retriever"]

    workflow = QuizWorkflow(
        llm_client=components["llm_client"],
        retriever=retriever,
        subject_id=subject_id,
    )

    try:
        questions = workflow.generate(
            topic=request.topic,
            difficulty=request.difficulty,
            num_questions=request.num_questions,
            question_types=request.question_types,
        )

        return {
            "status": "success",
            "topic": request.topic,
            "subject_id": subject_id,
            "count": len(questions),
            "questions": [q.model_dump() for q in questions],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/flashcards", tags=["Generation"])
async def generate_flashcards(request: FlashcardRequest):
    """Generate flashcards for a topic.
    
    Returns Q/A flashcards with hints, mnemonics, and related topics.
    Optionally scoped to a specific subject.
    """
    from src.workflows.flashcards import FlashcardWorkflow

    components = get_components()
    subject_id = request.subject_id or "general"
    
    # Get subject-scoped retriever if subject_id is provided
    subject_manager = components["subject_manager"]
    if subject_manager.subject_exists(subject_id):
        retriever = subject_manager.get_subject_retriever(subject_id)
        sr_scheduler = subject_manager.get_subject_sr_scheduler(subject_id)
    else:
        retriever = components["retriever"]
        sr_scheduler = components["sr_scheduler"]

    workflow = FlashcardWorkflow(
        retriever=retriever,
        llm_client=components["llm_client"],
        subject_id=subject_id,
    )

    try:
        cards = workflow.generate(
            topic=request.topic,
            difficulty=request.difficulty,
            num_cards=request.num_cards,
        )

        # Register cards with the appropriate spaced repetition scheduler
        for card in cards:
            sr_scheduler.add_card(card.id)

        return {
            "status": "success",
            "topic": request.topic,
            "subject_id": subject_id,
            "count": len(cards),
            "flashcards": [c.model_dump() for c in cards],
        }

    except Exception as e:
        logger.error(f"Flashcard generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/notes", tags=["Generation"])
async def generate_notes(request: NotesRequest):
    """Generate revision notes for a topic.
    
    Returns hierarchical notes with subtopics, key terms, formulae,
    and mnemonics. Optionally scoped to a specific subject.
    """
    from src.workflows.revision_notes import RevisionNotesWorkflow

    components = get_components()
    subject_id = request.subject_id or "general"
    
    # Get subject-scoped retriever if subject_id is provided
    subject_manager = components["subject_manager"]
    if subject_manager.subject_exists(subject_id):
        retriever = subject_manager.get_subject_retriever(subject_id)
    else:
        retriever = components["retriever"]

    workflow = RevisionNotesWorkflow(
        retriever=retriever,
        llm_client=components["llm_client"],
        subject_id=subject_id,
    )

    try:
        notes = workflow.generate(topic=request.topic)

        return {
            "status": "success",
            "topic": request.topic,
            "subject_id": subject_id,
            "notes": notes.model_dump(),
        }

    except Exception as e:
        logger.error(f"Notes generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/solution", tags=["Generation"])
async def generate_solution(request: SolutionRequest):
    """Generate a structured solution for a question.
    
    Solution depth is determined by mark allocation:
    - 1-3 marks: brief (2-3 sentences)
    - 4-6 marks: moderate (key points, paragraphs)
    - 7+ marks: detailed (full explanation, examples)
    
    Optionally scoped to a specific subject.
    """
    from src.workflows.solutions import SolutionWorkflow

    components = get_components()
    subject_id = request.subject_id or "general"
    
    # Get subject-scoped retriever if subject_id is provided
    subject_manager = components["subject_manager"]
    if subject_manager.subject_exists(subject_id):
        retriever = subject_manager.get_subject_retriever(subject_id)
    else:
        retriever = components["retriever"]

    workflow = SolutionWorkflow(
        retriever=retriever,
        llm_client=components["llm_client"],
        subject_id=subject_id,
    )

    try:
        solution = workflow.generate(
            question=request.question,
            topic=request.topic,
            marks=request.marks,
        )

        return {
            "status": "success",
            "question": request.question,
            "topic": request.topic,
            "subject_id": subject_id,
            "marks": request.marks,
            "solution": solution.model_dump(),
        }

    except Exception as e:
        logger.error(f"Solution generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/mindmap", tags=["Generation"])
async def generate_mindmap(request: MindMapRequest):
    """Generate a mind map for a topic.
    
    Returns a hierarchical node-edge structure for visualization.
    Optionally scoped to a specific subject.
    """
    from src.workflows.mind_map import MindMapWorkflow

    components = get_components()
    subject_id = request.subject_id or "general"
    
    # Get subject-scoped knowledge graph if subject_id is provided
    subject_manager = components["subject_manager"]
    if subject_manager.subject_exists(subject_id):
        knowledge_graph = subject_manager.get_subject_knowledge_graph(subject_id)
    else:
        knowledge_graph = components["knowledge_graph"]

    workflow = MindMapWorkflow(
        knowledge_graph=knowledge_graph,
        subject_id=subject_id,
    )

    try:
        mindmap = workflow.generate(
            topic=request.topic,
            max_depth=request.max_depth,
        )

        return {
            "status": "success",
            "topic": request.topic,
            "subject_id": subject_id,
            "mindmap": mindmap.model_dump(),
        }

    except Exception as e:
        logger.error(f"Mind map generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/additional-info", tags=["Generation"])
async def generate_additional_info(request: AdditionalInfoRequest):
    """Generate additional information for a topic.
    
    Returns applications, industry uses, common mistakes, and
    interview questions.
    """
    from src.workflows.additional_info import AdditionalInfoWorkflow

    components = get_components()
    workflow = AdditionalInfoWorkflow(
        retriever=components["retriever"],
        llm_client=components["llm_client"],
    )

    try:
        info = workflow.generate(topic=request.topic)

        return {
            "status": "success",
            "topic": request.topic,
            "additional_info": info,
        }

    except Exception as e:
        logger.error(f"Additional info generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


# ---------------------------------------------------------------------------
# Endpoints: Chat Tutor
# ---------------------------------------------------------------------------


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """Chat with the AI tutor.
    
    RAG-powered conversational tutor that answers questions based on
    uploaded study material. Maintains conversation context per session.
    Optionally scoped to a specific subject.
    """
    subject_id = request.subject_id or "general"
    session_key = f"{subject_id}:{request.session_id}" if request.session_id else None
    session_id, tutor = get_or_create_chat_session(session_key, subject_id)

    try:
        result = tutor.ask(request.message)

        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            is_grounded=result["is_grounded"],
            session_id=session_id,
        )

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.delete("/chat/{session_id}", tags=["Chat"])
async def reset_chat(session_id: str):
    """Reset a chat session (clear conversation history)."""
    if session_id in _chat_sessions:
        _chat_sessions[session_id].reset()
        return {"status": "success", "message": f"Session {session_id} reset"}
    raise HTTPException(status_code=404, detail="Session not found")


# ---------------------------------------------------------------------------
# Endpoints: Learning Progress
# ---------------------------------------------------------------------------


@app.get("/progress", tags=["Progress"])
async def get_progress(subject_id: Optional[str] = None):
    """Get overall learning progress and statistics.
    
    If subject_id is provided, returns progress for that subject only.
    Otherwise returns global progress across all subjects.
    """
    components = get_components()
    subject_manager = components["subject_manager"]
    
    if subject_id and subject_manager.subject_exists(subject_id):
        progress_tracker = subject_manager.get_subject_progress_tracker(subject_id)
    else:
        progress_tracker = components["progress_tracker"]
    
    stats = progress_tracker.get_overall_stats()
    weak = progress_tracker.get_weak_topics()
    strong = progress_tracker.get_strong_topics()

    return {
        "subject_id": subject_id or "global",
        "stats": stats,
        "weak_topics": weak,
        "strong_topics": strong,
    }


@app.get("/progress/{topic}", tags=["Progress"])
async def get_topic_progress(topic: str):
    """Get learning progress for a specific topic."""
    components = get_components()
    progress = components["progress_tracker"].get_topic_progress(topic)

    return {
        "topic": topic,
        "progress": progress.model_dump(),
        "mastery_level": components["progress_tracker"].get_mastery_level(topic),
    }


@app.post("/progress/score", tags=["Progress"])
async def record_score(request: ScoreRequest):
    """Record a quiz score for a topic.
    
    Optionally scoped to a specific subject.
    """
    components = get_components()
    subject_id = request.subject_id or "general"
    subject_manager = components["subject_manager"]
    
    if subject_manager.subject_exists(subject_id):
        progress_tracker = subject_manager.get_subject_progress_tracker(subject_id)
        subject_manager.update_activity(subject_id)
    else:
        progress_tracker = components["progress_tracker"]

    try:
        progress_tracker.record_score(request.topic, request.score)
        mastery = progress_tracker.get_mastery_level(request.topic)

        return {
            "status": "success",
            "topic": request.topic,
            "subject_id": subject_id,
            "score": request.score,
            "mastery_level": mastery,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Dashboard
# ---------------------------------------------------------------------------


@app.get("/dashboard", tags=["Dashboard"])
async def get_dashboard(subject_id: Optional[str] = None):
    """Get comprehensive dashboard data for spaced repetition progress.
    
    If subject_id is provided, returns dashboard for that subject only.
    Otherwise returns global dashboard data.
    
    Returns all metrics needed for the visual dashboard:
    - Streak information (current, longest)
    - Cards due (today, this week, this month)
    - Topic mastery breakdown with percentages
    - Heatmap calendar data (last 365 days)
    - Exam readiness score with breakdown
    - Learning velocity trends (8 weeks)
    """
    components = get_components()
    subject_manager = components["subject_manager"]
    
    # Get subject-scoped trackers if subject_id provided
    if subject_id and subject_manager.subject_exists(subject_id):
        progress_tracker = subject_manager.get_subject_progress_tracker(subject_id)
        sr_scheduler = subject_manager.get_subject_sr_scheduler(subject_id)
    else:
        progress_tracker = components["progress_tracker"]
        sr_scheduler = components["sr_scheduler"]
    
    # Get comprehensive dashboard data from progress tracker
    dashboard = progress_tracker.get_dashboard_data()
    
    # Add due cards info from spaced repetition scheduler
    from datetime import date, timedelta
    today = date.today()
    
    due_today = sr_scheduler.get_due_cards(today.isoformat())
    
    # Calculate due this week
    week_end = today + timedelta(days=6 - today.weekday())
    due_week = set(due_today)
    for i in range(1, 7):
        future_date = today + timedelta(days=i)
        if future_date <= week_end:
            due_week.update(sr_scheduler.get_due_cards(future_date.isoformat()))
    
    # Calculate due this month
    month_end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    due_month = set(due_today)
    current = today + timedelta(days=1)
    while current <= month_end:
        due_month.update(sr_scheduler.get_due_cards(current.isoformat()))
        current += timedelta(days=1)
    
    dashboard["subject_id"] = subject_id or "global"
    dashboard["due_cards"] = {
        "today": len(due_today),
        "this_week": len(due_week),
        "this_month": len(due_month),
        "card_ids_today": due_today,
    }
    
    return dashboard


@app.post("/dashboard/record-review", tags=["Dashboard"])
async def record_review(card_id: str, quality: int):
    """Record a flashcard review and update both SR scheduler and streak tracking.
    
    This endpoint should be used instead of /spaced-repetition/review
    when you want to track reviews for the dashboard streak/heatmap.
    """
    components = get_components()
    
    try:
        # Update spaced repetition scheduler
        components["sr_scheduler"].review_card(card_id, quality)
        
        # Update progress tracker for streak/heatmap
        components["progress_tracker"].record_card_review(card_id)
        
        # Get updated stats
        sr_stats = components["sr_scheduler"].get_card_stats(card_id)
        streak = components["progress_tracker"]._state.current_streak
        
        return {
            "status": "success",
            "card_id": card_id,
            "quality": quality,
            "next_review": sr_stats["next_review"],
            "interval_days": sr_stats["interval"],
            "current_streak": streak,
        }
    
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Spaced Repetition
# ---------------------------------------------------------------------------


@app.get("/spaced-repetition/due", tags=["Spaced Repetition"])
async def get_due_cards(date: Optional[str] = None):
    """Get flashcards due for review.
    
    Optionally specify a date (YYYY-MM-DD) to check cards due on that day.
    Defaults to today.
    """
    components = get_components()
    due_cards = components["sr_scheduler"].get_due_cards(date)

    return {
        "date": date or "today",
        "due_count": len(due_cards),
        "card_ids": due_cards,
    }


@app.post("/spaced-repetition/review", tags=["Spaced Repetition"])
async def review_card(request: CardReviewRequest):
    """Submit a flashcard review (SM-2 algorithm).
    
    Quality scale:
    - 0: Complete blackout
    - 1: Incorrect, but upon seeing answer, remembered
    - 2: Incorrect, but answer seemed easy to recall
    - 3: Correct with serious difficulty
    - 4: Correct after hesitation
    - 5: Perfect response
    """
    components = get_components()

    try:
        components["sr_scheduler"].review_card(request.card_id, request.quality)
        stats = components["sr_scheduler"].get_card_stats(request.card_id)

        return {
            "status": "success",
            "card_id": request.card_id,
            "quality": request.quality,
            "next_review": stats["next_review"],
            "interval_days": stats["interval"],
        }

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/spaced-repetition/card/{card_id}", tags=["Spaced Repetition"])
async def get_card_stats(card_id: str):
    """Get scheduling statistics for a flashcard."""
    components = get_components()

    try:
        stats = components["sr_scheduler"].get_card_stats(card_id)
        return {"card_id": card_id, **stats}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Multi-Agent Orchestrator
# ---------------------------------------------------------------------------


@app.post("/process", tags=["Orchestrator"])
async def process_query(request: ProcessRequest):
    """Process a natural language query through the multi-agent orchestrator.
    
    The orchestrator automatically:
    1. Classifies user intent (quiz, flashcard, explain, notes, etc.)
    2. Routes to the appropriate agent
    3. Validates output quality
    4. Updates learning progress if applicable
    
    This is the recommended endpoint for general queries.
    """
    components = get_components()

    try:
        result = components["orchestrator"].process(request.query)
        return {
            "status": "success",
            "intent": result["intent"],
            "parameters": result["parameters"],
            "result": result["result"],
            "quality_check": result["quality_check"],
            "memory_update": result.get("memory_update"),
        }

    except Exception as e:
        logger.error(f"Orchestrator processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# ---------------------------------------------------------------------------
# Endpoints: Search
# ---------------------------------------------------------------------------


@app.get("/search", tags=["Search"])
async def search(query: str, top_k: int = 5, method: str = "semantic"):
    """Search the knowledge base.
    
    Methods:
    - semantic: Embedding-based similarity search
    - hybrid: Combines semantic search with graph traversal
    - filtered: Semantic search with metadata filters (use topic/difficulty params)
    """
    components = get_components()

    if method == "hybrid":
        results = components["retriever"].hybrid_retrieval(query=query, top_k=top_k)
    elif method == "filtered":
        results = components["retriever"].filtered_search(query=query, top_k=top_k)
    else:
        results = components["retriever"].semantic_search(query=query, top_k=top_k)

    return {
        "query": query,
        "method": method,
        "count": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Endpoints: Subject Management
# ---------------------------------------------------------------------------


@app.post("/subjects", tags=["Subjects"])
async def create_subject(request: CreateSubjectRequest):
    """Create a new study subject.
    
    Subjects provide isolated learning environments with their own:
    - Document storage and chunks
    - Knowledge graph
    - Learning progress tracking
    - Flashcard scheduling
    """
    components = get_components()
    subject_manager = components["subject_manager"]
    
    try:
        subject = subject_manager.create_subject(
            name=request.name,
            description=request.description,
            color=request.color,
            icon=request.icon,
        )
        
        return {
            "status": "success",
            "message": f"Subject '{request.name}' created",
            "subject": subject.to_dict(),
        }
    
    except SubjectExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/subjects", tags=["Subjects"])
async def list_subjects(include_archived: bool = False, sort_by: str = "last_activity"):
    """List all subjects.
    
    Args:
        include_archived: Whether to include archived subjects.
        sort_by: Sort order - "name", "last_activity", "created", "mastery".
    """
    components = get_components()
    subject_manager = components["subject_manager"]
    
    subjects = subject_manager.list_subjects(
        include_archived=include_archived,
        sort_by=sort_by,
    )
    
    return {
        "subjects": [s.model_dump(mode="json") for s in subjects],
        "total_count": len(subjects),
        "active_count": sum(1 for s in subjects if s.status.value == "active"),
        "archived_count": sum(1 for s in subjects if s.status.value == "archived"),
    }


@app.get("/subjects/{subject_id}", tags=["Subjects"])
async def get_subject(subject_id: str):
    """Get detailed information about a subject."""
    components = get_components()
    subject_manager = components["subject_manager"]
    
    try:
        subject = subject_manager.get_subject(subject_id)
        stats = subject_manager.get_subject_stats(subject_id)
        
        return {
            "subject": subject.to_dict(),
            "stats": stats,
        }
    
    except SubjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")


@app.put("/subjects/{subject_id}", tags=["Subjects"])
async def update_subject(subject_id: str, request: UpdateSubjectRequest):
    """Update a subject's properties."""
    components = get_components()
    subject_manager = components["subject_manager"]
    
    try:
        subject = subject_manager.update_subject(
            subject_id=subject_id,
            name=request.name,
            description=request.description,
            color=request.color,
            icon=request.icon,
        )
        
        return {
            "status": "success",
            "subject": subject.to_dict(),
        }
    
    except SubjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")
    except SubjectExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.delete("/subjects/{subject_id}", tags=["Subjects"])
async def delete_subject(subject_id: str, force: bool = False):
    """Delete a subject and all its data.
    
    WARNING: This permanently deletes all documents, progress, and data
    associated with the subject.
    
    Args:
        force: Required to delete the default "General" subject.
    """
    components = get_components()
    subject_manager = components["subject_manager"]
    
    try:
        subject_manager.delete_subject(subject_id, force=force)
        
        return {
            "status": "success",
            "message": f"Subject '{subject_id}' deleted",
        }
    
    except SubjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")
    except DefaultSubjectError:
        raise HTTPException(status_code=403, detail="Cannot delete the default subject")


@app.post("/subjects/{subject_id}/archive", tags=["Subjects"])
async def archive_subject(subject_id: str):
    """Archive a subject (soft delete)."""
    components = get_components()
    subject_manager = components["subject_manager"]
    
    try:
        subject = subject_manager.archive_subject(subject_id)
        
        return {
            "status": "success",
            "message": f"Subject '{subject_id}' archived",
            "subject": subject.to_dict(),
        }
    
    except SubjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")
    except DefaultSubjectError:
        raise HTTPException(status_code=403, detail="Cannot archive the default subject")


@app.post("/subjects/{subject_id}/restore", tags=["Subjects"])
async def restore_subject(subject_id: str):
    """Restore an archived subject."""
    components = get_components()
    subject_manager = components["subject_manager"]
    
    try:
        subject = subject_manager.restore_subject(subject_id)
        
        return {
            "status": "success",
            "message": f"Subject '{subject_id}' restored",
            "subject": subject.to_dict(),
        }
    
    except SubjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")


@app.get("/subjects/{subject_id}/documents", tags=["Subjects"])
async def list_subject_documents(subject_id: str):
    """List all documents in a subject."""
    components = get_components()
    subject_manager = components["subject_manager"]
    
    try:
        documents = subject_manager.list_documents(subject_id)
        
        return {
            "subject_id": subject_id,
            "documents": [d.to_dict() for d in documents],
            "total_count": len(documents),
        }
    
    except SubjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")


@app.get("/subjects/{subject_id}/stats", tags=["Subjects"])
async def get_subject_stats(subject_id: str):
    """Get detailed statistics for a subject."""
    components = get_components()
    subject_manager = components["subject_manager"]
    
    try:
        stats = subject_manager.get_subject_stats(subject_id)
        
        return {
            "subject_id": subject_id,
            "stats": stats,
        }
    
    except SubjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")


# ---------------------------------------------------------------------------
# Endpoints: Migration
# ---------------------------------------------------------------------------


@app.get("/migration/status", tags=["Migration"])
async def get_migration_status():
    """Get current migration status.
    
    Returns information about:
    - Whether migration is needed
    - Whether migration is complete
    - Which old files still exist
    - Whether cleanup can be performed
    """
    from src.subjects.migration import get_migration_info
    
    info = get_migration_info()
    
    return {
        "needs_migration": info["needs_migration"],
        "migration_complete": info["migration_complete"],
        "files_to_migrate": info["files_to_migrate"],
        "backup_exists": info["backup_exists"],
        "can_cleanup": info["migration_complete"] and not info["needs_migration"],
    }


@app.post("/migration/cleanup", tags=["Migration"])
async def cleanup_old_files(dry_run: bool = True):
    """Cleanup old root-level data files after migration.
    
    This endpoint removes the old data files that were migrated to the
    subject-based organization. Only available after migration is complete.
    
    Args:
        dry_run: If True, only report what would be deleted without actually
                 deleting. Set to False to perform the actual cleanup.
    
    Returns:
        List of files that were/would be deleted.
    
    WARNING: Setting dry_run=False will permanently delete the old files.
    Make sure the migration was successful and backups exist before cleanup.
    """
    from src.subjects.migration import cleanup_old_files as do_cleanup, get_migration_info
    
    # Check migration is complete first
    info = get_migration_info()
    if info["needs_migration"]:
        raise HTTPException(
            status_code=400,
            detail="Migration must be completed before cleanup. Old files still need to be migrated.",
        )
    
    if not info["migration_complete"]:
        raise HTTPException(
            status_code=400,
            detail="Migration marker not found. Run migration first.",
        )
    
    result = do_cleanup(dry_run=dry_run)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        "status": "success",
        "dry_run": dry_run,
        "message": "Files deleted successfully" if not dry_run else "Dry run complete - no files deleted",
        "files": result.get("files", []),
    }


# ---------------------------------------------------------------------------
# Endpoints: Source Attribution & Document Viewing
# ---------------------------------------------------------------------------

# Document storage service (initialized lazily)
_doc_storage_service = None


def get_doc_storage():
    """Get or create the document storage service."""
    global _doc_storage_service
    if _doc_storage_service is None:
        from src.services import DocumentStorageService
        _doc_storage_service = DocumentStorageService(base_dir=Path("./data"))
    return _doc_storage_service


class CitationBatchRequest(BaseModel):
    """Request to get citations for multiple chunks."""
    chunk_ids: list[str] = Field(..., description="List of chunk IDs to enrich")
    subject_id: Optional[str] = Field(default="general", description="Subject ID for lookup")


@app.get("/chunks/{chunk_id}/citation", tags=["Citations"])
async def get_chunk_citation(chunk_id: str, subject_id: str = "general"):
    """Get full citation data for a chunk.
    
    Returns detailed source attribution information including:
    - Document name and format
    - Page and paragraph numbers
    - Text excerpt and full content
    - Bounding boxes for PDF highlighting
    """
    from src.services import CitationEnrichmentService
    
    components = get_components()
    doc_storage = get_doc_storage()
    
    enrichment_service = CitationEnrichmentService(
        vector_store=components["vector_store"],
        doc_storage=doc_storage,
        subject_id=subject_id,
    )
    
    try:
        citation = enrichment_service.enrich_chunk(chunk_id, subject_id=subject_id)
        return {
            "status": "success",
            "citation": citation.to_dict(),
        }
    except Exception as e:
        logger.error(f"Citation enrichment failed for {chunk_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Chunk not found: {chunk_id}")


@app.post("/citations/batch", tags=["Citations"])
async def get_citations_batch(request: CitationBatchRequest):
    """Get citations for multiple chunks at once.
    
    Efficiently fetches citation data for multiple chunks in a single request.
    Useful for enriching quiz questions, flashcards, or chat responses.
    """
    from src.services import CitationEnrichmentService
    
    components = get_components()
    doc_storage = get_doc_storage()
    
    enrichment_service = CitationEnrichmentService(
        vector_store=components["vector_store"],
        doc_storage=doc_storage,
        subject_id=request.subject_id,
    )
    
    try:
        citations = enrichment_service.enrich_batch(
            request.chunk_ids,
            subject_id=request.subject_id,
        )
        return {
            "status": "success",
            "citations": [c.to_dict() for c in citations],
            "count": len(citations),
        }
    except Exception as e:
        logger.error(f"Batch citation enrichment failed: {e}")
        raise HTTPException(status_code=500, detail=f"Citation enrichment failed: {str(e)}")


@app.get("/subjects/{subject_id}/documents/{doc_id}/file", tags=["Documents"])
async def get_document_file(
    subject_id: str,
    doc_id: str,
    range_header: Optional[str] = None,
):
    """Serve a document file for viewing.
    
    Supports HTTP Range headers for partial content (PDF streaming).
    Returns the document with appropriate Content-Type header.
    """
    from fastapi.responses import StreamingResponse, Response
    from src.services import DocumentStorageService
    from src.services.document_storage import DocumentNotFoundError
    
    doc_storage = get_doc_storage()
    
    try:
        # Get document metadata
        stored_doc = doc_storage.get_document(subject_id, doc_id)
        content_type = stored_doc.get_content_type()
        file_path = doc_storage.get_document_path(subject_id, doc_id)
        file_size = stored_doc.file_size
        
        # Handle range requests for streaming
        if range_header:
            # Parse range header (e.g., "bytes=0-1023")
            import re
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                end = min(end, file_size - 1)
                
                content_length = end - start + 1
                
                return StreamingResponse(
                    doc_storage.stream_document(subject_id, doc_id, start, end + 1),
                    status_code=206,
                    media_type=content_type,
                    headers={
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Content-Length": str(content_length),
                        "Accept-Ranges": "bytes",
                        "Content-Disposition": f'inline; filename="{stored_doc.filename}"',
                    },
                )
        
        # Full file response
        return StreamingResponse(
            doc_storage.stream_document(subject_id, doc_id),
            media_type=content_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{stored_doc.filename}"',
            },
        )
        
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    except Exception as e:
        logger.error(f"Error serving document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving document: {str(e)}")


@app.get("/subjects/{subject_id}/documents/{doc_id}/metadata", tags=["Documents"])
async def get_document_metadata(subject_id: str, doc_id: str):
    """Get metadata for a stored document.
    
    Returns document information including filename, format, size,
    page count, and upload date.
    """
    from src.services.document_storage import DocumentNotFoundError
    
    doc_storage = get_doc_storage()
    
    try:
        stored_doc = doc_storage.get_document(subject_id, doc_id)
        return {
            "status": "success",
            "document": stored_doc.to_dict(),
        }
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")


@app.get("/subjects/{subject_id}/documents/{doc_id}/chunks", tags=["Documents"])
async def get_document_chunks(
    subject_id: str,
    doc_id: str,
    include_content: bool = True,
):
    """Get all chunks from a specific document.
    
    Returns chunks with their position information for source navigation.
    Useful for building a document outline or navigation.
    """
    components = get_components()
    
    try:
        # Query chunks by document_id in metadata
        results = components["vector_store"].chunks_collection.get(
            where={"document_id": doc_id},
            include=["documents", "metadatas"] if include_content else ["metadatas"],
        )
        
        if not results or not results.get("ids"):
            return {
                "status": "success",
                "document_id": doc_id,
                "chunks": [],
                "count": 0,
            }
        
        chunks = []
        for i, chunk_id in enumerate(results["ids"]):
            chunk_data = {
                "id": chunk_id,
                "metadata": results["metadatas"][i] if results.get("metadatas") else {},
            }
            if include_content and results.get("documents"):
                chunk_data["content"] = results["documents"][i]
            chunks.append(chunk_data)
        
        # Sort by chunk_index
        chunks.sort(key=lambda c: c["metadata"].get("chunk_index", 0))
        
        return {
            "status": "success",
            "document_id": doc_id,
            "subject_id": subject_id,
            "chunks": chunks,
            "count": len(chunks),
        }
        
    except Exception as e:
        logger.error(f"Error getting document chunks: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving chunks: {str(e)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
