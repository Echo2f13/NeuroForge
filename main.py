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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up application resources."""
    global _llm_client, _vector_store, _knowledge_graph
    global _retriever, _progress_tracker, _sr_scheduler, _orchestrator

    logger.info("Starting NeuroForge API...")

    # Import dependencies
    from src.llm import LLMClient
    from src.store.vector_store import VectorStore
    from src.store.knowledge_graph import KnowledgeGraph
    from src.retrieval.retriever import Retriever
    from src.memory.progress import ProgressTracker
    from src.memory.spaced_repetition import SpacedRepetitionScheduler
    from src.agents.multi_agent import MultiAgentOrchestrator

    # Initialize core components
    _llm_client = LLMClient()
    _vector_store = VectorStore(persist_directory="./chroma_db/")
    _vector_store.init_collections()
    _knowledge_graph = KnowledgeGraph()

    # Try to load existing knowledge graph
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
    difficulty: Optional[str] = Field(None, description="easy, medium, or hard")
    num_questions: int = Field(default=10, ge=1, le=50)
    question_types: Optional[list[str]] = Field(
        default=None, description="mcq, short_answer, true_false"
    )


class FlashcardRequest(BaseModel):
    topic: str = Field(..., description="Topic for flashcard generation")
    difficulty: Optional[str] = Field(None, description="easy, medium, or hard")
    num_cards: int = Field(default=10, ge=1, le=50)


class NotesRequest(BaseModel):
    topic: str = Field(..., description="Topic for revision notes generation")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User's question or message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    is_grounded: bool
    session_id: str


class MindMapRequest(BaseModel):
    topic: str = Field(..., description="Topic for mind map generation")
    max_depth: int = Field(default=3, ge=1, le=5)


class AdditionalInfoRequest(BaseModel):
    topic: str = Field(..., description="Topic for additional info generation")


class SolutionRequest(BaseModel):
    question: str = Field(..., description="The question to answer")
    topic: str = Field(default="General", description="Topic/subject area")
    marks: int = Field(default=5, ge=1, le=20, description="Mark allocation affects depth")


class ScoreRequest(BaseModel):
    topic: str = Field(..., description="Topic the quiz was about")
    score: float = Field(..., ge=0, le=100, description="Quiz score (0-100)")


class CardReviewRequest(BaseModel):
    card_id: str = Field(..., description="Flashcard ID")
    quality: int = Field(..., ge=0, le=5, description="Review quality (0-5)")


class ProcessRequest(BaseModel):
    """Generic request for the multi-agent orchestrator."""
    query: str = Field(..., description="Natural language query")


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
    }


# Chat session storage (in-memory for now)
_chat_sessions: dict[str, Any] = {}


def get_or_create_chat_session(session_id: Optional[str]) -> tuple[str, Any]:
    """Get existing or create new chat tutor session."""
    from src.workflows.chat_tutor import ChatTutor

    if session_id and session_id in _chat_sessions:
        return session_id, _chat_sessions[session_id]

    # Create new session
    new_id = str(uuid.uuid4())
    tutor = ChatTutor(retriever=_retriever, llm_client=_llm_client)
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
    uploaded study material.
    """
    from src.workflows.quiz import QuizWorkflow

    components = get_components()
    workflow = QuizWorkflow(
        llm_client=components["llm_client"],
        retriever=components["retriever"],
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
    """
    from src.workflows.flashcards import FlashcardWorkflow

    components = get_components()
    workflow = FlashcardWorkflow(
        retriever=components["retriever"],
        llm_client=components["llm_client"],
    )

    try:
        cards = workflow.generate(
            topic=request.topic,
            difficulty=request.difficulty,
            num_cards=request.num_cards,
        )

        # Register cards with spaced repetition scheduler
        for card in cards:
            components["sr_scheduler"].add_card(card.id)

        return {
            "status": "success",
            "topic": request.topic,
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
    and mnemonics.
    """
    from src.workflows.revision_notes import RevisionNotesWorkflow

    components = get_components()
    workflow = RevisionNotesWorkflow(
        retriever=components["retriever"],
        llm_client=components["llm_client"],
    )

    try:
        notes = workflow.generate(topic=request.topic)

        return {
            "status": "success",
            "topic": request.topic,
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
    """
    from src.workflows.solutions import SolutionWorkflow

    components = get_components()
    workflow = SolutionWorkflow(
        retriever=components["retriever"],
        llm_client=components["llm_client"],
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
    """
    from src.workflows.mind_map import MindMapWorkflow

    components = get_components()
    workflow = MindMapWorkflow(knowledge_graph=components["knowledge_graph"])

    try:
        mindmap = workflow.generate(
            topic=request.topic,
            max_depth=request.max_depth,
        )

        return {
            "status": "success",
            "topic": request.topic,
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
    """
    session_id, tutor = get_or_create_chat_session(request.session_id)

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
async def get_progress():
    """Get overall learning progress and statistics."""
    components = get_components()
    stats = components["progress_tracker"].get_overall_stats()
    weak = components["progress_tracker"].get_weak_topics()
    strong = components["progress_tracker"].get_strong_topics()

    return {
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
    """Record a quiz score for a topic."""
    components = get_components()

    try:
        components["progress_tracker"].record_score(request.topic, request.score)
        mastery = components["progress_tracker"].get_mastery_level(request.topic)

        return {
            "status": "success",
            "topic": request.topic,
            "score": request.score,
            "mastery_level": mastery,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Dashboard
# ---------------------------------------------------------------------------


@app.get("/dashboard", tags=["Dashboard"])
async def get_dashboard():
    """Get comprehensive dashboard data for spaced repetition progress.
    
    Returns all metrics needed for the visual dashboard:
    - Streak information (current, longest)
    - Cards due (today, this week, this month)
    - Topic mastery breakdown with percentages
    - Heatmap calendar data (last 365 days)
    - Exam readiness score with breakdown
    - Learning velocity trends (8 weeks)
    """
    components = get_components()
    
    # Get comprehensive dashboard data from progress tracker
    dashboard = components["progress_tracker"].get_dashboard_data()
    
    # Add due cards info from spaced repetition scheduler
    from datetime import date, timedelta
    today = date.today()
    
    due_today = components["sr_scheduler"].get_due_cards(today.isoformat())
    
    # Calculate due this week
    week_end = today + timedelta(days=6 - today.weekday())
    due_week = set(due_today)
    for i in range(1, 7):
        future_date = today + timedelta(days=i)
        if future_date <= week_end:
            due_week.update(components["sr_scheduler"].get_due_cards(future_date.isoformat()))
    
    # Calculate due this month
    month_end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    due_month = set(due_today)
    current = today + timedelta(days=1)
    while current <= month_end:
        due_month.update(components["sr_scheduler"].get_due_cards(current.isoformat()))
        current += timedelta(days=1)
    
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
