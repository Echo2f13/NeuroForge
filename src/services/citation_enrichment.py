"""Citation Enrichment Service for NeuroForge.

Transforms chunk references into rich citation objects with full metadata
for source attribution display. Bridges the gap between raw chunk IDs
and user-facing citation information.

Usage:
    from src.services.citation_enrichment import CitationEnrichmentService
    
    service = CitationEnrichmentService(vector_store, doc_storage)
    citation = service.enrich_chunk("chunk_001")
    citations = service.enrich_batch(["chunk_001", "chunk_002"])
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from models import BoundingBox, Citation, CitationGroup

logger = logging.getLogger(__name__)

# Default excerpt length
DEFAULT_EXCERPT_LENGTH = 200


class CitationEnrichmentError(Exception):
    """Base exception for citation enrichment errors."""
    pass


class ChunkNotFoundError(CitationEnrichmentError):
    """Raised when a chunk cannot be found."""
    pass


class CitationEnrichmentService:
    """Enriches chunk references with full citation data.
    
    Takes chunk IDs and returns Citation objects with all the metadata
    needed for source attribution display, including document names,
    page numbers, excerpts, and bounding boxes.
    
    Attributes:
        vector_store: Vector store for chunk retrieval.
        doc_storage: Document storage service for document metadata.
    """
    
    def __init__(
        self,
        vector_store: Any,
        doc_storage: Optional[Any] = None,
        subject_id: Optional[str] = None,
    ) -> None:
        """Initialize the CitationEnrichmentService.
        
        Args:
            vector_store: Vector store instance for chunk retrieval.
            doc_storage: Document storage service for document metadata.
            subject_id: Default subject ID for chunk lookups.
        """
        self.vector_store = vector_store
        self.doc_storage = doc_storage
        self.subject_id = subject_id
        self._doc_cache: dict[str, dict] = {}
    
    def enrich_chunk(
        self,
        chunk_id: str,
        relevance_score: float = 1.0,
        subject_id: Optional[str] = None,
    ) -> Citation:
        """Convert a chunk ID to a full Citation object.
        
        Args:
            chunk_id: The chunk ID to enrich.
            relevance_score: Relevance score for this citation (0-1).
            subject_id: Subject ID for chunk lookup (optional).
            
        Returns:
            Citation object with full metadata.
            
        Raises:
            ChunkNotFoundError: If the chunk cannot be found.
        """
        subject = subject_id or self.subject_id
        
        # Fetch chunk from vector store
        chunk_data = self._fetch_chunk(chunk_id, subject)
        
        if not chunk_data:
            raise ChunkNotFoundError(f"Chunk not found: {chunk_id}")
        
        # Extract metadata
        metadata = chunk_data.get("metadata", {})
        content = chunk_data.get("document", chunk_data.get("content", ""))
        
        # Get document info
        doc_id = metadata.get("document_id", "")
        doc_info = self._get_document_info(doc_id, subject)
        
        # Create excerpt
        excerpt = self._create_excerpt(content, DEFAULT_EXCERPT_LENGTH)
        
        # Parse bounding boxes if present
        bboxes = self._parse_bounding_boxes(metadata.get("bounding_boxes"))
        
        # Generate citation ID
        citation_id = f"cit_{uuid.uuid4().hex[:8]}"
        
        return Citation(
            id=citation_id,
            chunk_id=chunk_id,
            document_id=doc_id,
            document_name=doc_info.get("filename", metadata.get("source_file", "Unknown")),
            document_format=doc_info.get("format", metadata.get("document_format", "txt")),
            page_number=metadata.get("page_number"),
            paragraph_number=metadata.get("paragraph_number"),
            excerpt=excerpt,
            full_text=content,
            relevance_score=max(0.0, min(1.0, relevance_score)),
            bounding_boxes=bboxes,
            start_char=metadata.get("start_char", 0),
            end_char=metadata.get("end_char", len(content)),
            line_start=metadata.get("line_start"),
            line_end=metadata.get("line_end"),
            section_heading=metadata.get("section_heading"),
        )
    
    def enrich_batch(
        self,
        chunk_ids: list[str],
        relevance_scores: Optional[list[float]] = None,
        subject_id: Optional[str] = None,
    ) -> list[Citation]:
        """Enrich multiple chunks efficiently.
        
        Args:
            chunk_ids: List of chunk IDs to enrich.
            relevance_scores: Optional relevance scores for each chunk.
            subject_id: Subject ID for chunk lookups.
            
        Returns:
            List of Citation objects (in same order as input).
        """
        if not chunk_ids:
            return []
        
        # Default scores
        if relevance_scores is None:
            relevance_scores = [1.0] * len(chunk_ids)
        elif len(relevance_scores) < len(chunk_ids):
            relevance_scores.extend([1.0] * (len(chunk_ids) - len(relevance_scores)))
        
        citations = []
        
        for chunk_id, score in zip(chunk_ids, relevance_scores):
            try:
                citation = self.enrich_chunk(chunk_id, score, subject_id)
                citations.append(citation)
            except ChunkNotFoundError as e:
                logger.warning(f"Skipping missing chunk: {e}")
            except Exception as e:
                logger.error(f"Error enriching chunk {chunk_id}: {e}")
        
        return citations
    
    def enrich_from_retrieval_results(
        self,
        results: list[dict],
        subject_id: Optional[str] = None,
    ) -> list[Citation]:
        """Enrich citations from retrieval results.
        
        Converts retrieval results (with id, content, score, metadata)
        directly to Citation objects without additional lookups.
        
        Args:
            results: List of retrieval result dicts.
            subject_id: Subject ID for document lookups.
            
        Returns:
            List of Citation objects.
        """
        citations = []
        subject = subject_id or self.subject_id
        
        for result in results:
            try:
                chunk_id = result.get("id", "")
                content = result.get("content", result.get("document", ""))
                metadata = result.get("metadata", {})
                
                # Convert distance to relevance score (1 - distance for cosine)
                score = result.get("score", 0)
                if "distance" in result:
                    # ChromaDB returns distance, convert to similarity
                    score = max(0, 1 - result["distance"])
                
                # Get document info
                doc_id = metadata.get("document_id", "")
                doc_info = self._get_document_info(doc_id, subject)
                
                # Create excerpt
                excerpt = self._create_excerpt(content, DEFAULT_EXCERPT_LENGTH)
                
                # Parse bounding boxes
                bboxes = self._parse_bounding_boxes(metadata.get("bounding_boxes"))
                
                citation = Citation(
                    id=f"cit_{uuid.uuid4().hex[:8]}",
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    document_name=doc_info.get("filename", metadata.get("source_file", "Unknown")),
                    document_format=doc_info.get("format", metadata.get("document_format", "txt")),
                    page_number=metadata.get("page_number"),
                    paragraph_number=metadata.get("paragraph_number"),
                    excerpt=excerpt,
                    full_text=content,
                    relevance_score=max(0.0, min(1.0, score)),
                    bounding_boxes=bboxes,
                    start_char=metadata.get("start_char", 0),
                    end_char=metadata.get("end_char", len(content)),
                    line_start=metadata.get("line_start"),
                    line_end=metadata.get("line_end"),
                    section_heading=metadata.get("section_heading"),
                )
                citations.append(citation)
                
            except Exception as e:
                logger.error(f"Error creating citation from result: {e}")
        
        return citations
    
    def create_citation_group(
        self,
        item_id: str,
        item_type: str,
        chunk_ids: list[str],
        relevance_scores: Optional[list[float]] = None,
        subject_id: Optional[str] = None,
    ) -> CitationGroup:
        """Create a citation group for a generated item.
        
        Args:
            item_id: ID of the generated item (quiz question, flashcard, etc.).
            item_type: Type of item (quiz/flashcard/note/chat).
            chunk_ids: List of source chunk IDs.
            relevance_scores: Optional relevance scores.
            subject_id: Subject ID for lookups.
            
        Returns:
            CitationGroup with all citations.
        """
        citations = self.enrich_batch(chunk_ids, relevance_scores, subject_id)
        
        # Find primary citation (highest relevance)
        primary_id = None
        if citations:
            primary = max(citations, key=lambda c: c.relevance_score)
            primary_id = primary.id
        
        return CitationGroup(
            item_id=item_id,
            item_type=item_type,
            citations=citations,
            primary_citation_id=primary_id,
        )
    
    def enrich_quiz_output(
        self,
        quiz_questions: list[dict],
        subject_id: Optional[str] = None,
    ) -> list[dict]:
        """Add citation data to quiz questions.
        
        Args:
            quiz_questions: List of quiz question dicts with source_chunk_ids.
            subject_id: Subject ID for lookups.
            
        Returns:
            Quiz questions with added 'citations' field.
        """
        for question in quiz_questions:
            chunk_ids = question.get("source_chunk_ids", [])
            if chunk_ids:
                citations = self.enrich_batch(chunk_ids, subject_id=subject_id)
                question["citations"] = [c.to_dict() for c in citations]
            else:
                question["citations"] = []
        
        return quiz_questions
    
    def enrich_flashcard_output(
        self,
        flashcards: list[dict],
        subject_id: Optional[str] = None,
    ) -> list[dict]:
        """Add citation data to flashcards.
        
        Args:
            flashcards: List of flashcard dicts with source_chunk_ids.
            subject_id: Subject ID for lookups.
            
        Returns:
            Flashcards with added 'citations' field.
        """
        for card in flashcards:
            chunk_ids = card.get("source_chunk_ids", [])
            if chunk_ids:
                citations = self.enrich_batch(chunk_ids, subject_id=subject_id)
                card["citations"] = [c.to_dict() for c in citations]
            else:
                card["citations"] = []
        
        return flashcards
    
    def enrich_chat_response(
        self,
        response: dict,
        subject_id: Optional[str] = None,
    ) -> dict:
        """Add citation data to a chat response.
        
        Args:
            response: Chat response dict with 'sources' list.
            subject_id: Subject ID for lookups.
            
        Returns:
            Response with added 'citations' field.
        """
        chunk_ids = response.get("sources", [])
        if chunk_ids:
            citations = self.enrich_batch(chunk_ids, subject_id=subject_id)
            response["citations"] = [c.to_dict() for c in citations]
        else:
            response["citations"] = []
        
        return response
    
    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    
    def _fetch_chunk(
        self,
        chunk_id: str,
        subject_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Fetch a chunk from the vector store.
        
        Args:
            chunk_id: The chunk ID to fetch.
            subject_id: Subject ID for scoped lookup.
            
        Returns:
            Chunk data dict or None if not found.
        """
        try:
            # Try subject-scoped lookup first
            if subject_id and hasattr(self.vector_store, 'get_chunk'):
                result = self.vector_store.get_chunk(subject_id, chunk_id)
                if result:
                    return result
            
            # Fall back to direct lookup
            if hasattr(self.vector_store, 'chunks_collection'):
                result = self.vector_store.chunks_collection.get(
                    ids=[chunk_id],
                    include=["documents", "metadatas"],
                )
                if result and result.get("ids"):
                    return {
                        "id": result["ids"][0],
                        "document": result["documents"][0] if result.get("documents") else "",
                        "metadata": result["metadatas"][0] if result.get("metadatas") else {},
                    }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error fetching chunk {chunk_id}: {e}")
            return None
    
    def _get_document_info(
        self,
        doc_id: str,
        subject_id: Optional[str] = None,
    ) -> dict:
        """Get document information from storage or cache.
        
        Args:
            doc_id: Document ID.
            subject_id: Subject ID for lookup.
            
        Returns:
            Dict with document info (filename, format, etc.).
        """
        if not doc_id:
            return {}
        
        # Check cache first
        cache_key = f"{subject_id}:{doc_id}"
        if cache_key in self._doc_cache:
            return self._doc_cache[cache_key]
        
        # Try to fetch from document storage
        if self.doc_storage and subject_id:
            try:
                stored_doc = self.doc_storage.get_document(subject_id, doc_id)
                doc_info = {
                    "filename": stored_doc.filename,
                    "format": stored_doc.format.value if hasattr(stored_doc.format, 'value') else str(stored_doc.format),
                    "total_pages": stored_doc.total_pages,
                    "title": stored_doc.title,
                }
                self._doc_cache[cache_key] = doc_info
                return doc_info
            except Exception as e:
                logger.debug(f"Could not fetch document info for {doc_id}: {e}")
        
        return {}
    
    def _create_excerpt(self, text: str, max_length: int) -> str:
        """Create a truncated excerpt from text.
        
        Args:
            text: Full text to excerpt.
            max_length: Maximum excerpt length.
            
        Returns:
            Truncated text with ellipsis if needed.
        """
        if not text:
            return ""
        
        # Clean up whitespace
        text = " ".join(text.split())
        
        if len(text) <= max_length:
            return text
        
        # Find a word boundary near max_length
        truncated = text[:max_length]
        last_space = truncated.rfind(" ")
        
        if last_space > max_length * 0.7:
            truncated = truncated[:last_space]
        
        return truncated.rstrip() + "..."
    
    def _parse_bounding_boxes(
        self,
        bbox_data: Optional[list],
    ) -> Optional[list[BoundingBox]]:
        """Parse bounding box data from metadata.
        
        Args:
            bbox_data: Raw bounding box data (list of dicts or BoundingBox objects).
            
        Returns:
            List of BoundingBox objects or None.
        """
        if not bbox_data:
            return None
        
        bboxes = []
        
        for item in bbox_data:
            try:
                if isinstance(item, BoundingBox):
                    bboxes.append(item)
                elif isinstance(item, dict):
                    bbox = BoundingBox.from_dict(item)
                    bboxes.append(bbox)
            except Exception as e:
                logger.debug(f"Error parsing bounding box: {e}")
        
        return bboxes if bboxes else None
    
    def clear_cache(self) -> None:
        """Clear the document info cache."""
        self._doc_cache.clear()
