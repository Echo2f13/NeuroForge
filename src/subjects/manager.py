"""Subject Manager for NeuroForge.

Central manager for all subject-related operations including CRUD,
component factories, and statistics aggregation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from models.subject import (
    Subject,
    SubjectDocument,
    SubjectSettings,
    SubjectStatus,
    SubjectSummary,
)

from .storage import DEFAULT_DATA_DIR, DEFAULT_SUBJECT_ID, SubjectStorage

logger = logging.getLogger("neuroforge.subjects")


class SubjectNotFoundError(Exception):
    """Raised when a subject doesn't exist."""
    
    def __init__(self, subject_id: str):
        self.subject_id = subject_id
        super().__init__(f"Subject '{subject_id}' not found")


class SubjectExistsError(Exception):
    """Raised when trying to create a subject that already exists."""
    
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Subject with name '{name}' already exists")


class DefaultSubjectError(Exception):
    """Raised when trying to perform forbidden operations on default subject."""
    
    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(f"Cannot {operation} the default subject")


class SubjectManager:
    """Central manager for subject operations.
    
    Provides:
    - CRUD operations for subjects
    - Component factories (vector store, knowledge graph, etc.)
    - Document management within subjects
    - Statistics aggregation
    
    Args:
        data_dir: Base directory for data storage.
    """

    def __init__(self, data_dir: str = DEFAULT_DATA_DIR) -> None:
        """Initialize the subject manager.
        
        Args:
            data_dir: Base directory for all data.
        """
        self.storage = SubjectStorage(data_dir)
        self._subjects: dict[str, Subject] = {}
        self._load_subjects()
        self._ensure_default_subject()
        
        # Component caches (lazy-loaded)
        self._vector_stores: dict[str, Any] = {}
        self._knowledge_graphs: dict[str, Any] = {}
        self._progress_trackers: dict[str, Any] = {}
        self._sr_schedulers: dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Subject Registry Management
    # -------------------------------------------------------------------------

    def _load_subjects(self) -> None:
        """Load all subjects from the registry file."""
        subjects_file = self.storage.get_subjects_file_path()
        if subjects_file.exists():
            try:
                data = json.loads(subjects_file.read_text(encoding="utf-8"))
                for subject_id, subject_data in data.items():
                    self._subjects[subject_id] = Subject.from_dict(subject_data)
                logger.info(f"Loaded {len(self._subjects)} subjects")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to load subjects registry: {e}")
                self._subjects = {}

    def _save_subjects(self) -> None:
        """Save all subjects to the registry file."""
        subjects_file = self.storage.get_subjects_file_path()
        data = {
            subject_id: subject.to_dict()
            for subject_id, subject in self._subjects.items()
        }
        subjects_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _ensure_default_subject(self) -> None:
        """Ensure the default 'General' subject exists."""
        if DEFAULT_SUBJECT_ID not in self._subjects:
            logger.info("Creating default 'General' subject")
            self._subjects[DEFAULT_SUBJECT_ID] = Subject(
                id=DEFAULT_SUBJECT_ID,
                name="General",
                description="Default subject for uncategorized materials",
                icon="📚",
                is_default=True,
            )
            self.storage.initialize_subject_files(DEFAULT_SUBJECT_ID)
            self._save_subjects()

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_subject(
        self,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
        settings: Optional[SubjectSettings] = None,
    ) -> Subject:
        """Create a new subject.
        
        Args:
            name: Subject name (1-100 characters).
            description: Optional description (max 500 characters).
            color: Optional hex color code.
            icon: Optional emoji or icon.
            settings: Optional subject settings.
            
        Returns:
            The created Subject.
            
        Raises:
            SubjectExistsError: If a subject with this name already exists.
            ValueError: If name is invalid.
        """
        # Check for duplicate names (case-insensitive)
        for existing in self._subjects.values():
            if existing.name.lower() == name.lower():
                raise SubjectExistsError(name)
        
        # Create new subject
        subject = Subject(
            name=name,
            description=description,
            color=color,
            icon=icon,
            settings=settings or SubjectSettings(),
        )
        
        # Initialize storage
        self.storage.initialize_subject_files(subject.id)
        
        # Add to registry
        self._subjects[subject.id] = subject
        self._save_subjects()
        
        logger.info(f"Created subject '{name}' with ID {subject.id}")
        return subject

    def get_subject(self, subject_id: str) -> Subject:
        """Get a subject by ID.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            The Subject.
            
        Raises:
            SubjectNotFoundError: If subject doesn't exist.
        """
        if subject_id not in self._subjects:
            raise SubjectNotFoundError(subject_id)
        return self._subjects[subject_id]

    def list_subjects(
        self, 
        include_archived: bool = False,
        sort_by: str = "last_activity",
    ) -> list[SubjectSummary]:
        """List all subjects with summary info.
        
        Args:
            include_archived: Whether to include archived subjects.
            sort_by: Sort field - "name", "last_activity", "created", "mastery".
            
        Returns:
            List of SubjectSummary objects.
        """
        summaries = []
        
        for subject in self._subjects.values():
            # Filter archived
            if not include_archived and subject.status == SubjectStatus.ARCHIVED:
                continue
            
            # Get stats for summary
            stats = self._get_subject_stats_internal(subject.id)
            
            summary = SubjectSummary.from_subject(
                subject,
                document_count=stats.get("document_count", 0),
                chunk_count=stats.get("chunk_count", 0),
                concept_count=stats.get("concept_count", 0),
                quiz_count=stats.get("quiz_count", 0),
                average_score=stats.get("average_score", 0.0),
                mastery_percent=stats.get("mastery_percent", 0.0),
            )
            summaries.append(summary)
        
        # Sort results
        if sort_by == "name":
            summaries.sort(key=lambda s: s.name.lower())
        elif sort_by == "created":
            summaries.sort(key=lambda s: s.last_activity_at or datetime.min, reverse=True)
        elif sort_by == "mastery":
            summaries.sort(key=lambda s: s.mastery_percent, reverse=True)
        else:  # last_activity (default)
            summaries.sort(key=lambda s: s.last_activity_at or datetime.min, reverse=True)
        
        return summaries

    def update_subject(
        self,
        subject_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
        settings: Optional[SubjectSettings] = None,
    ) -> Subject:
        """Update a subject's properties.
        
        Args:
            subject_id: Subject to update.
            name: New name (optional).
            description: New description (optional).
            color: New color (optional).
            icon: New icon (optional).
            settings: New settings (optional).
            
        Returns:
            The updated Subject.
            
        Raises:
            SubjectNotFoundError: If subject doesn't exist.
            SubjectExistsError: If new name conflicts with existing subject.
        """
        subject = self.get_subject(subject_id)
        
        # Check name uniqueness if changing
        if name and name != subject.name:
            for existing in self._subjects.values():
                if existing.id != subject_id and existing.name.lower() == name.lower():
                    raise SubjectExistsError(name)
            subject.name = name
        
        if description is not None:
            subject.description = description
        if color is not None:
            subject.color = color
        if icon is not None:
            subject.icon = icon
        if settings is not None:
            subject.settings = settings
        
        subject.updated_at = datetime.utcnow()
        self._save_subjects()
        
        logger.info(f"Updated subject {subject_id}")
        return subject

    def delete_subject(self, subject_id: str, force: bool = False) -> bool:
        """Delete a subject and all its data.
        
        Args:
            subject_id: Subject to delete.
            force: If True, allows deleting default subject (dangerous!).
            
        Returns:
            True if deleted successfully.
            
        Raises:
            SubjectNotFoundError: If subject doesn't exist.
            DefaultSubjectError: If trying to delete default without force.
        """
        subject = self.get_subject(subject_id)
        
        if subject.is_default and not force:
            raise DefaultSubjectError("delete")
        
        # Delete ChromaDB collections
        try:
            self._delete_subject_collections(subject_id)
        except Exception as e:
            logger.warning(f"Failed to delete ChromaDB collections for {subject_id}: {e}")
        
        # Delete subject directory
        self.storage.delete_subject_dir(subject_id)
        
        # Remove from registry
        del self._subjects[subject_id]
        self._save_subjects()
        
        # Clear from caches
        self._vector_stores.pop(subject_id, None)
        self._knowledge_graphs.pop(subject_id, None)
        self._progress_trackers.pop(subject_id, None)
        self._sr_schedulers.pop(subject_id, None)
        
        logger.info(f"Deleted subject {subject_id}")
        return True

    def archive_subject(self, subject_id: str) -> Subject:
        """Archive a subject (soft delete).
        
        Args:
            subject_id: Subject to archive.
            
        Returns:
            The archived Subject.
            
        Raises:
            SubjectNotFoundError: If subject doesn't exist.
            DefaultSubjectError: If trying to archive default subject.
        """
        subject = self.get_subject(subject_id)
        
        if subject.is_default:
            raise DefaultSubjectError("archive")
        
        subject.status = SubjectStatus.ARCHIVED
        subject.updated_at = datetime.utcnow()
        self._save_subjects()
        
        logger.info(f"Archived subject {subject_id}")
        return subject

    def restore_subject(self, subject_id: str) -> Subject:
        """Restore an archived subject.
        
        Args:
            subject_id: Subject to restore.
            
        Returns:
            The restored Subject.
            
        Raises:
            SubjectNotFoundError: If subject doesn't exist.
        """
        subject = self.get_subject(subject_id)
        subject.status = SubjectStatus.ACTIVE
        subject.updated_at = datetime.utcnow()
        self._save_subjects()
        
        logger.info(f"Restored subject {subject_id}")
        return subject

    # -------------------------------------------------------------------------
    # Subject Existence & Utility
    # -------------------------------------------------------------------------

    def subject_exists(self, subject_id: str) -> bool:
        """Check if a subject exists.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            True if exists, False otherwise.
        """
        return subject_id in self._subjects

    def get_default_subject_id(self) -> str:
        """Get the default subject ID.
        
        Returns:
            The default subject ID ("general").
        """
        return DEFAULT_SUBJECT_ID

    def update_activity(self, subject_id: str) -> None:
        """Update the last activity timestamp for a subject.
        
        Args:
            subject_id: Subject identifier.
        """
        if subject_id in self._subjects:
            self._subjects[subject_id].update_activity()
            self._save_subjects()

    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------

    def add_document(
        self,
        subject_id: str,
        doc_id: str,
        filename: str,
        file_type: str,
        chunk_count: int = 0,
        concept_count: int = 0,
        file_size_bytes: Optional[int] = None,
    ) -> SubjectDocument:
        """Add a document to a subject.
        
        Args:
            subject_id: Subject to add document to.
            doc_id: Document identifier.
            filename: Original filename.
            file_type: File type (pdf, docx, etc.).
            chunk_count: Number of chunks created.
            concept_count: Number of concepts extracted.
            file_size_bytes: File size in bytes.
            
        Returns:
            The created SubjectDocument.
        """
        self.get_subject(subject_id)  # Validate subject exists
        
        doc = SubjectDocument(
            id=doc_id,
            subject_id=subject_id,
            filename=filename,
            file_type=file_type,
            chunk_count=chunk_count,
            concept_count=concept_count,
            file_size_bytes=file_size_bytes,
        )
        
        # Load existing documents
        docs_path = self.storage.get_documents_path(subject_id)
        documents = []
        if docs_path.exists():
            try:
                documents = json.loads(docs_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                documents = []
        
        # Add new document
        documents.append(doc.to_dict())
        docs_path.write_text(json.dumps(documents, indent=2), encoding="utf-8")
        
        # Update activity
        self.update_activity(subject_id)
        
        return doc

    def list_documents(self, subject_id: str) -> list[SubjectDocument]:
        """List all documents in a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            List of SubjectDocument objects.
        """
        self.get_subject(subject_id)  # Validate subject exists
        
        docs_path = self.storage.get_documents_path(subject_id)
        if not docs_path.exists():
            return []
        
        try:
            data = json.loads(docs_path.read_text(encoding="utf-8"))
            return [SubjectDocument.from_dict(d) for d in data]
        except (json.JSONDecodeError, ValueError):
            return []

    def delete_document(self, subject_id: str, doc_id: str) -> bool:
        """Delete a document from a subject.
        
        Note: This only removes the metadata. Chunks and concepts
        should be deleted separately via the vector store.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        docs_path = self.storage.get_documents_path(subject_id)
        if not docs_path.exists():
            return False
        
        try:
            documents = json.loads(docs_path.read_text(encoding="utf-8"))
            original_count = len(documents)
            documents = [d for d in documents if d.get("id") != doc_id]
            
            if len(documents) < original_count:
                docs_path.write_text(json.dumps(documents, indent=2), encoding="utf-8")
                return True
            return False
        except json.JSONDecodeError:
            return False

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def _get_subject_stats_internal(self, subject_id: str) -> dict:
        """Get internal stats for a subject (no validation).
        
        Used internally to avoid repeated validation.
        """
        stats = {
            "document_count": 0,
            "chunk_count": 0,
            "concept_count": 0,
            "quiz_count": 0,
            "average_score": 0.0,
            "mastery_percent": 0.0,
        }
        
        # Document count
        docs_path = self.storage.get_documents_path(subject_id)
        if docs_path.exists():
            try:
                docs = json.loads(docs_path.read_text(encoding="utf-8"))
                stats["document_count"] = len(docs)
                stats["chunk_count"] = sum(d.get("chunk_count", 0) for d in docs)
                stats["concept_count"] = sum(d.get("concept_count", 0) for d in docs)
            except json.JSONDecodeError:
                pass
        
        # Learning stats
        ls_path = self.storage.get_learning_state_path(subject_id)
        if ls_path.exists():
            try:
                ls = json.loads(ls_path.read_text(encoding="utf-8"))
                stats["quiz_count"] = ls.get("total_quizzes_taken", 0)
                
                # Calculate average score and mastery
                topic_progress = ls.get("topic_progress", {})
                if topic_progress:
                    all_scores = []
                    mastery_scores = []
                    for tp in topic_progress.values():
                        scores = tp.get("quiz_scores", [])
                        all_scores.extend(scores)
                        if tp.get("average_score", 0) > 0:
                            mastery_scores.append(tp["average_score"])
                    
                    if all_scores:
                        stats["average_score"] = round(sum(all_scores) / len(all_scores), 2)
                    if mastery_scores:
                        stats["mastery_percent"] = round(sum(mastery_scores) / len(mastery_scores), 2)
            except json.JSONDecodeError:
                pass
        
        return stats

    def get_subject_stats(self, subject_id: str) -> dict:
        """Get comprehensive statistics for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Dictionary with document_count, chunk_count, concept_count,
            quiz_count, average_score, mastery_percent.
        """
        self.get_subject(subject_id)  # Validate exists
        return self._get_subject_stats_internal(subject_id)

    def get_global_stats(self) -> dict:
        """Get aggregated statistics across all active subjects.
        
        Returns:
            Dictionary with total counts and averages.
        """
        totals = {
            "subject_count": 0,
            "document_count": 0,
            "chunk_count": 0,
            "concept_count": 0,
            "quiz_count": 0,
            "average_score": 0.0,
        }
        
        all_scores = []
        
        for subject_id, subject in self._subjects.items():
            if subject.status == SubjectStatus.ARCHIVED:
                continue
            
            totals["subject_count"] += 1
            stats = self._get_subject_stats_internal(subject_id)
            totals["document_count"] += stats["document_count"]
            totals["chunk_count"] += stats["chunk_count"]
            totals["concept_count"] += stats["concept_count"]
            totals["quiz_count"] += stats["quiz_count"]
            
            if stats["average_score"] > 0:
                all_scores.append(stats["average_score"])
        
        if all_scores:
            totals["average_score"] = round(sum(all_scores) / len(all_scores), 2)
        
        return totals

    # -------------------------------------------------------------------------
    # Component Factories (Lazy Loading)
    # -------------------------------------------------------------------------

    def get_knowledge_graph_path(self, subject_id: str) -> str:
        """Get the knowledge graph file path for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to knowledge_graph.json as string.
        """
        self.get_subject(subject_id)  # Validate exists
        return str(self.storage.get_knowledge_graph_path(subject_id))

    def get_learning_state_path(self, subject_id: str) -> str:
        """Get the learning state file path for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to learning_state.json as string.
        """
        self.get_subject(subject_id)  # Validate exists
        return str(self.storage.get_learning_state_path(subject_id))

    def get_sr_state_path(self, subject_id: str) -> str:
        """Get the spaced repetition state file path for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to sr_state.json as string.
        """
        self.get_subject(subject_id)  # Validate exists
        return str(self.storage.get_sr_state_path(subject_id))

    def get_collection_names(self, subject_id: str) -> tuple[str, str]:
        """Get ChromaDB collection names for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Tuple of (chunks_collection_name, concepts_collection_name).
        """
        self.get_subject(subject_id)  # Validate exists
        return self.storage.get_collection_names(subject_id)

    def _delete_subject_collections(self, subject_id: str) -> None:
        """Delete ChromaDB collections for a subject.
        
        This is called during subject deletion.
        """
        # This will be implemented when we update VectorStore
        # For now, we'll leave the collections (they'll be orphaned but harmless)
        pass

    # -------------------------------------------------------------------------
    # Migration Support
    # -------------------------------------------------------------------------

    def needs_migration(self) -> bool:
        """Check if data migration is needed.
        
        Returns True if old-style data files exist at root level.
        """
        old_files = [
            Path("./knowledge_graph.json"),
            Path("./learning_state.json"),
            Path("./sr_state.json"),
        ]
        return any(f.exists() for f in old_files)

    def get_migration_info(self) -> dict:
        """Get information about what needs to be migrated.
        
        Returns:
            Dictionary with files that need migration.
        """
        info = {
            "needs_migration": self.needs_migration(),
            "files": [],
        }
        
        old_files = [
            ("knowledge_graph.json", "./knowledge_graph.json"),
            ("learning_state.json", "./learning_state.json"),
            ("sr_state.json", "./sr_state.json"),
        ]
        
        for name, path in old_files:
            if Path(path).exists():
                info["files"].append(name)
        
        return info

    # -------------------------------------------------------------------------
    # Component Factory Methods
    # -------------------------------------------------------------------------

    def get_subject_vector_store(self) -> "SubjectScopedVectorStore":
        """Get the shared subject-scoped vector store.
        
        Returns:
            SubjectScopedVectorStore instance.
        """
        from src.store.subject_vector_store import SubjectScopedVectorStore
        
        if not hasattr(self, "_subject_vector_store"):
            self._subject_vector_store = SubjectScopedVectorStore(
                persist_directory=str(self.storage.get_chroma_dir())
            )
        return self._subject_vector_store

    def get_subject_knowledge_graph(self, subject_id: str) -> "KnowledgeGraph":
        """Get or create a knowledge graph for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            KnowledgeGraph instance loaded from subject's file.
        """
        from src.store.knowledge_graph import KnowledgeGraph
        
        self.get_subject(subject_id)  # Validate exists
        
        if subject_id not in self._knowledge_graphs:
            kg = KnowledgeGraph()
            kg_path = self.storage.get_knowledge_graph_path(subject_id)
            if kg_path.exists():
                try:
                    kg.load(str(kg_path))
                except Exception as e:
                    logger.warning(f"Could not load knowledge graph for {subject_id}: {e}")
            self._knowledge_graphs[subject_id] = kg
        
        return self._knowledge_graphs[subject_id]

    def save_subject_knowledge_graph(self, subject_id: str) -> None:
        """Save a subject's knowledge graph to disk.
        
        Args:
            subject_id: Subject identifier.
        """
        if subject_id in self._knowledge_graphs:
            kg = self._knowledge_graphs[subject_id]
            kg_path = self.storage.get_knowledge_graph_path(subject_id)
            if len(kg) > 0:
                kg.save(str(kg_path))

    def get_subject_progress_tracker(self, subject_id: str) -> "ProgressTracker":
        """Get or create a progress tracker for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            ProgressTracker instance for the subject.
        """
        from src.memory.progress import ProgressTracker
        
        self.get_subject(subject_id)  # Validate exists
        
        if subject_id not in self._progress_trackers:
            state_path = str(self.storage.get_learning_state_path(subject_id))
            self._progress_trackers[subject_id] = ProgressTracker(state_file=state_path)
        
        return self._progress_trackers[subject_id]

    def get_subject_sr_scheduler(self, subject_id: str) -> "SpacedRepetitionScheduler":
        """Get or create a spaced repetition scheduler for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            SpacedRepetitionScheduler instance for the subject.
        """
        from src.memory.spaced_repetition import SpacedRepetitionScheduler
        
        self.get_subject(subject_id)  # Validate exists
        
        if subject_id not in self._sr_schedulers:
            state_path = str(self.storage.get_sr_state_path(subject_id))
            self._sr_schedulers[subject_id] = SpacedRepetitionScheduler(state_file=state_path)
        
        return self._sr_schedulers[subject_id]

    def get_subject_retriever(self, subject_id: str) -> "SubjectRetriever":
        """Get a retriever scoped to a specific subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            SubjectRetriever instance for the subject.
        """
        from src.retrieval.subject_retriever import SubjectRetriever
        
        vector_store = self.get_subject_vector_store()
        knowledge_graph = self.get_subject_knowledge_graph(subject_id)
        
        return SubjectRetriever(
            vector_store=vector_store,
            knowledge_graph=knowledge_graph,
            subject_id=subject_id,
        )

    def save_all_subject_data(self, subject_id: str) -> None:
        """Save all cached data for a subject.
        
        Args:
            subject_id: Subject identifier.
        """
        # Save knowledge graph
        self.save_subject_knowledge_graph(subject_id)
        
        # Save progress tracker
        if subject_id in self._progress_trackers:
            self._progress_trackers[subject_id].save()
        
        # Save SR scheduler
        if subject_id in self._sr_schedulers:
            self._sr_schedulers[subject_id].save()

    def save_all(self) -> None:
        """Save all cached subject data."""
        self._save_subjects()
        for subject_id in self._subjects:
            try:
                self.save_all_subject_data(subject_id)
            except Exception as e:
                logger.warning(f"Failed to save data for subject {subject_id}: {e}")
