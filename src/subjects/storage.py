"""Subject Storage Utilities for NeuroForge.

Provides directory structure management and path utilities for
subject-scoped data storage.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Optional

# Default data directory
DEFAULT_DATA_DIR = "./data"

# Default subject ID for backward compatibility
DEFAULT_SUBJECT_ID = "general"


class SubjectStorage:
    """Manages directory structure and paths for subject data.
    
    Directory Structure:
        data/
        ├── subjects.json              # Subject registry
        ├── subjects/
        │   ├── {subject_id}/
        │   │   ├── metadata.json      # Subject details
        │   │   ├── documents.json     # Document registry
        │   │   ├── knowledge_graph.json
        │   │   ├── learning_state.json
        │   │   └── sr_state.json
        │   └── general/               # Default subject
        └── chroma_db/                 # ChromaDB collections
    
    Args:
        data_dir: Base directory for all data. Defaults to "./data".
    """

    def __init__(self, data_dir: str = DEFAULT_DATA_DIR) -> None:
        """Initialize subject storage.
        
        Args:
            data_dir: Base directory for data storage.
        """
        self.data_dir = Path(data_dir)
        self._ensure_base_structure()

    def _ensure_base_structure(self) -> None:
        """Create base directory structure if it doesn't exist."""
        # Create main directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "subjects").mkdir(exist_ok=True)
        
        # Initialize subjects registry if it doesn't exist
        subjects_file = self.get_subjects_file_path()
        if not subjects_file.exists():
            subjects_file.write_text("{}", encoding="utf-8")

    # -------------------------------------------------------------------------
    # Path Getters
    # -------------------------------------------------------------------------

    def get_subjects_file_path(self) -> Path:
        """Get path to the subjects registry file.
        
        Returns:
            Path to subjects.json
        """
        return self.data_dir / "subjects.json"

    def get_subject_dir(self, subject_id: str) -> Path:
        """Get the directory for a subject.
        
        Args:
            subject_id: Subject identifier (validated).
            
        Returns:
            Path to subject directory.
            
        Raises:
            ValueError: If subject_id is invalid.
        """
        safe_id = self._validate_subject_id(subject_id)
        return self.data_dir / "subjects" / safe_id

    def get_metadata_path(self, subject_id: str) -> Path:
        """Get path to subject metadata file.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to metadata.json
        """
        return self.get_subject_dir(subject_id) / "metadata.json"

    def get_documents_path(self, subject_id: str) -> Path:
        """Get path to subject documents registry.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to documents.json
        """
        return self.get_subject_dir(subject_id) / "documents.json"

    def get_knowledge_graph_path(self, subject_id: str) -> Path:
        """Get path to subject knowledge graph.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to knowledge_graph.json
        """
        return self.get_subject_dir(subject_id) / "knowledge_graph.json"

    def get_learning_state_path(self, subject_id: str) -> Path:
        """Get path to subject learning state.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to learning_state.json
        """
        return self.get_subject_dir(subject_id) / "learning_state.json"

    def get_sr_state_path(self, subject_id: str) -> Path:
        """Get path to subject spaced repetition state.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to sr_state.json
        """
        return self.get_subject_dir(subject_id) / "sr_state.json"

    def get_chroma_dir(self) -> Path:
        """Get path to ChromaDB directory.
        
        Returns:
            Path to chroma_db directory.
        """
        return self.data_dir / "chroma_db"

    # -------------------------------------------------------------------------
    # ChromaDB Collection Names
    # -------------------------------------------------------------------------

    @staticmethod
    def get_collection_names(subject_id: str) -> tuple[str, str]:
        """Get ChromaDB collection names for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Tuple of (chunks_collection_name, concepts_collection_name)
        """
        # Replace hyphens with underscores for valid collection names
        safe_id = subject_id.replace("-", "_")
        return (
            f"subject_{safe_id}_chunks",
            f"subject_{safe_id}_concepts",
        )

    # -------------------------------------------------------------------------
    # Directory Operations
    # -------------------------------------------------------------------------

    def ensure_subject_dirs(self, subject_id: str) -> Path:
        """Create all directories needed for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to the created subject directory.
        """
        subject_dir = self.get_subject_dir(subject_id)
        subject_dir.mkdir(parents=True, exist_ok=True)
        return subject_dir

    def initialize_subject_files(self, subject_id: str) -> None:
        """Initialize empty data files for a new subject.
        
        Creates empty/default JSON files for:
        - documents.json (empty list)
        - knowledge_graph.json (empty graph)
        - learning_state.json (default state)
        - sr_state.json (empty state)
        
        Args:
            subject_id: Subject identifier.
        """
        self.ensure_subject_dirs(subject_id)
        
        # Initialize documents registry
        docs_path = self.get_documents_path(subject_id)
        if not docs_path.exists():
            docs_path.write_text("[]", encoding="utf-8")
        
        # Initialize knowledge graph (NetworkX node-link format)
        kg_path = self.get_knowledge_graph_path(subject_id)
        if not kg_path.exists():
            empty_graph = {"directed": True, "multigraph": False, "graph": {}, "nodes": [], "links": []}
            kg_path.write_text(json.dumps(empty_graph, indent=2), encoding="utf-8")
        
        # Initialize learning state
        ls_path = self.get_learning_state_path(subject_id)
        if not ls_path.exists():
            default_state = {
                "user_id": "default",
                "uploaded_materials": [],
                "topic_progress": {},
                "weak_topics": [],
                "strong_topics": [],
                "flashcard_review_queue": [],
                "total_quizzes_taken": 0,
                "total_study_time_minutes": 0.0,
                "daily_activity": {},
                "current_streak": 0,
                "longest_streak": 0,
                "total_cards_reviewed": 0,
            }
            ls_path.write_text(json.dumps(default_state, indent=2), encoding="utf-8")
        
        # Initialize SR state
        sr_path = self.get_sr_state_path(subject_id)
        if not sr_path.exists():
            sr_path.write_text("{}", encoding="utf-8")

    def delete_subject_dir(self, subject_id: str) -> bool:
        """Delete a subject's directory and all its data.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            True if deleted, False if didn't exist.
        """
        subject_dir = self.get_subject_dir(subject_id)
        if subject_dir.exists():
            shutil.rmtree(subject_dir)
            return True
        return False

    def subject_dir_exists(self, subject_id: str) -> bool:
        """Check if a subject directory exists.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            True if exists, False otherwise.
        """
        return self.get_subject_dir(subject_id).exists()

    def list_subject_dirs(self) -> list[str]:
        """List all subject directories.
        
        Returns:
            List of subject IDs that have directories.
        """
        subjects_dir = self.data_dir / "subjects"
        if not subjects_dir.exists():
            return []
        return [
            d.name for d in subjects_dir.iterdir() 
            if d.is_dir()
        ]

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_subject_id(subject_id: str) -> str:
        """Validate and sanitize a subject ID.
        
        Prevents path traversal attacks and ensures valid directory names.
        
        Args:
            subject_id: Subject identifier to validate.
            
        Returns:
            Sanitized subject ID.
            
        Raises:
            ValueError: If subject_id is invalid or contains dangerous characters.
        """
        if not subject_id:
            raise ValueError("Subject ID cannot be empty")
        
        # Check for path traversal attempts
        if ".." in subject_id or "/" in subject_id or "\\" in subject_id:
            raise ValueError(f"Invalid subject ID: '{subject_id}' contains path traversal characters")
        
        # Only allow alphanumeric, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', subject_id):
            raise ValueError(
                f"Invalid subject ID: '{subject_id}' - only alphanumeric, "
                "hyphens, and underscores are allowed"
            )
        
        # Limit length
        if len(subject_id) > 100:
            raise ValueError(f"Subject ID too long: max 100 characters, got {len(subject_id)}")
        
        return subject_id
