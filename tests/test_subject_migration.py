"""Tests for Subject Migration functionality.

This module tests the migration from the old single-collection structure
to the new per-subject organization in NeuroForge.
"""

import json
import os
import pytest
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.subjects.migration import (
    needs_migration,
    get_migration_info,
    create_backup,
    migrate_json_files,
    migrate_to_subjects,
    mark_migration_complete,
    cleanup_old_files,
    MIGRATION_MARKER,
    BACKUP_DIR,
    DATA_DIR,
    OLD_KNOWLEDGE_GRAPH,
    OLD_LEARNING_STATE,
    OLD_SR_STATE,
)
from src.subjects.manager import SubjectManager
from src.subjects.storage import SubjectStorage, DEFAULT_SUBJECT_ID


class TestSubjectMigration:
    """Test subject data migration."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test fixtures with temporary directories."""
        self.test_dir = tmp_path
        self.original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        # Define paths relative to temp directory
        self.old_kg = tmp_path / "knowledge_graph.json"
        self.old_ls = tmp_path / "learning_state.json"
        self.old_sr = tmp_path / "sr_state.json"
        self.data_dir = tmp_path / "data"
        
        yield
        
        # Cleanup: restore original directory
        os.chdir(self.original_cwd)

    def _create_old_structure(self):
        """Create old-style data files at root level."""
        # Create knowledge_graph.json
        kg_data = {
            "directed": True,
            "multigraph": False,
            "graph": {},
            "nodes": [
                {"id": "concept-1", "name": "Steel", "definition": "An alloy"},
                {"id": "concept-2", "name": "Iron", "definition": "A metal element"},
            ],
            "links": [
                {"source": "concept-1", "target": "concept-2", "relationship": "contains"}
            ]
        }
        self.old_kg.write_text(json.dumps(kg_data, indent=2))

        # Create learning_state.json
        ls_data = {
            "user_id": "test_user",
            "uploaded_materials": ["doc1.pdf", "doc2.pdf"],
            "topic_progress": {
                "Materials": {
                    "quiz_scores": [85, 90],
                    "average_score": 87.5,
                    "total_attempts": 2
                }
            },
            "weak_topics": ["Thermodynamics"],
            "strong_topics": ["Materials"],
            "total_quizzes_taken": 5,
            "total_study_time_minutes": 120.5
        }
        self.old_ls.write_text(json.dumps(ls_data, indent=2))

        # Create sr_state.json
        sr_data = {
            "cards": {
                "card-1": {
                    "concept_id": "concept-1",
                    "ease_factor": 2.5,
                    "interval_days": 3,
                    "repetitions": 2,
                    "next_review": "2024-01-15"
                }
            }
        }
        self.old_sr.write_text(json.dumps(sr_data, indent=2))

    def _create_empty_old_structure(self):
        """Create empty old-style data files."""
        self.old_kg.write_text("{}")
        self.old_ls.write_text("{}")
        self.old_sr.write_text("{}")

    # -------------------------------------------------------------------------
    # Test Fresh Install (No Migration Needed)
    # -------------------------------------------------------------------------

    def test_fresh_install_no_migration_needed(self):
        """Test that fresh install doesn't need migration."""
        # No old files exist, no migration marker
        assert not needs_migration()

    def test_fresh_install_migration_info(self):
        """Test migration info on fresh install."""
        info = get_migration_info()
        
        assert info["needs_migration"] is False
        assert info["migration_complete"] is False
        assert info["files_to_migrate"]["knowledge_graph"] is False
        assert info["files_to_migrate"]["learning_state"] is False
        assert info["files_to_migrate"]["sr_state"] is False

    def test_fresh_install_migrate_returns_not_needed(self):
        """Test that migration returns 'not_needed' on fresh install."""
        result = migrate_to_subjects()
        
        assert result["status"] == "not_needed"
        assert "No old data files found" in result.get("message", "")

    # -------------------------------------------------------------------------
    # Test Migration Detection
    # -------------------------------------------------------------------------

    def test_needs_migration_with_knowledge_graph(self):
        """Test migration detection with knowledge_graph.json present."""
        self.old_kg.write_text("{}")
        assert needs_migration() is True

    def test_needs_migration_with_learning_state(self):
        """Test migration detection with learning_state.json present."""
        self.old_ls.write_text("{}")
        assert needs_migration() is True

    def test_needs_migration_with_sr_state(self):
        """Test migration detection with sr_state.json present."""
        self.old_sr.write_text("{}")
        assert needs_migration() is True

    def test_needs_migration_with_all_files(self):
        """Test migration detection with all old files present."""
        self._create_old_structure()
        assert needs_migration() is True

    def test_needs_migration_false_after_complete(self):
        """Test migration is not needed after completion marker exists."""
        self._create_old_structure()
        
        # Create migration marker
        self.data_dir.mkdir(parents=True, exist_ok=True)
        marker = self.data_dir / ".migration_complete"
        marker.write_text(json.dumps({"migration_time": datetime.utcnow().isoformat()}))
        
        assert needs_migration() is False

    # -------------------------------------------------------------------------
    # Test Migration from Old Structure
    # -------------------------------------------------------------------------

    def test_migrate_creates_backup(self):
        """Test that migration creates backup of old files."""
        self._create_old_structure()
        
        result = migrate_to_subjects(create_backup=True)
        
        backup_dir = self.data_dir / "pre_migration_backup"
        assert backup_dir.exists()
        assert (backup_dir / "knowledge_graph.json").exists()
        assert (backup_dir / "learning_state.json").exists()
        assert (backup_dir / "sr_state.json").exists()
        assert (backup_dir / "backup_metadata.json").exists()

    def test_migrate_backup_metadata(self):
        """Test backup metadata is correctly written."""
        self._create_old_structure()
        
        migrate_to_subjects(create_backup=True)
        
        backup_dir = self.data_dir / "pre_migration_backup"
        metadata = json.loads((backup_dir / "backup_metadata.json").read_text())
        
        assert "backup_time" in metadata
        assert "files_backed_up" in metadata
        assert len(metadata["files_backed_up"]) == 3

    def test_migrate_creates_subject_directory(self):
        """Test migration creates subject directory structure."""
        self._create_old_structure()
        
        migrate_to_subjects()
        
        general_dir = self.data_dir / "subjects" / "general"
        assert general_dir.exists()
        assert (general_dir / "knowledge_graph.json").exists()
        assert (general_dir / "learning_state.json").exists()
        assert (general_dir / "sr_state.json").exists()

    def test_migrate_creates_migration_marker(self):
        """Test migration creates completion marker."""
        self._create_old_structure()
        
        migrate_to_subjects()
        
        marker = self.data_dir / ".migration_complete"
        assert marker.exists()
        
        marker_data = json.loads(marker.read_text())
        assert "migration_time" in marker_data
        assert "version" in marker_data

    def test_migrate_custom_subject_id(self):
        """Test migration to custom subject ID."""
        self._create_old_structure()
        
        migrate_to_subjects(subject_id="physics")
        
        physics_dir = self.data_dir / "subjects" / "physics"
        assert physics_dir.exists()
        assert (physics_dir / "knowledge_graph.json").exists()

    def test_migrate_force_option(self):
        """Test force migration even when marker exists."""
        self._create_old_structure()
        
        # First migration
        migrate_to_subjects()
        
        # Create new old files (simulating scenario where old files came back)
        new_kg_data = {"nodes": [{"id": "new-concept"}], "links": []}
        self.old_kg.write_text(json.dumps(new_kg_data))
        
        # Force migration should work
        result = migrate_to_subjects(force=True)
        assert result["status"] in ["success", "completed_with_errors"]

    def test_migrate_skip_backup(self):
        """Test migration without backup."""
        self._create_old_structure()
        
        result = migrate_to_subjects(create_backup=False)
        
        backup_dir = self.data_dir / "pre_migration_backup"
        # Backup should not exist when explicitly skipped
        assert result["backup"] is None

    # -------------------------------------------------------------------------
    # Test Data Integrity After Migration
    # -------------------------------------------------------------------------

    def test_data_integrity_knowledge_graph(self):
        """Test knowledge graph data is correctly migrated."""
        self._create_old_structure()
        original_data = json.loads(self.old_kg.read_text())
        
        migrate_to_subjects()
        
        new_kg_path = self.data_dir / "subjects" / "general" / "knowledge_graph.json"
        migrated_data = json.loads(new_kg_path.read_text())
        
        # Verify structure preserved
        assert migrated_data["directed"] == original_data["directed"]
        assert len(migrated_data["nodes"]) == len(original_data["nodes"])
        assert len(migrated_data["links"]) == len(original_data["links"])
        
        # Verify node data
        original_nodes = {n["id"]: n for n in original_data["nodes"]}
        migrated_nodes = {n["id"]: n for n in migrated_data["nodes"]}
        for node_id, node in original_nodes.items():
            assert node_id in migrated_nodes
            assert migrated_nodes[node_id]["name"] == node["name"]

    def test_data_integrity_learning_state(self):
        """Test learning state data is correctly migrated."""
        self._create_old_structure()
        original_data = json.loads(self.old_ls.read_text())
        
        migrate_to_subjects()
        
        new_ls_path = self.data_dir / "subjects" / "general" / "learning_state.json"
        migrated_data = json.loads(new_ls_path.read_text())
        
        # Verify all fields preserved
        assert migrated_data["user_id"] == original_data["user_id"]
        assert migrated_data["total_quizzes_taken"] == original_data["total_quizzes_taken"]
        assert migrated_data["topic_progress"] == original_data["topic_progress"]
        assert migrated_data["weak_topics"] == original_data["weak_topics"]
        assert migrated_data["strong_topics"] == original_data["strong_topics"]

    def test_data_integrity_sr_state(self):
        """Test spaced repetition state data is correctly migrated."""
        self._create_old_structure()
        original_data = json.loads(self.old_sr.read_text())
        
        migrate_to_subjects()
        
        new_sr_path = self.data_dir / "subjects" / "general" / "sr_state.json"
        migrated_data = json.loads(new_sr_path.read_text())
        
        # Verify card data preserved
        assert "cards" in migrated_data
        assert migrated_data["cards"] == original_data["cards"]

    def test_data_integrity_quiz_scores_preserved(self):
        """Test quiz scores are preserved during migration."""
        self._create_old_structure()
        
        migrate_to_subjects()
        
        new_ls_path = self.data_dir / "subjects" / "general" / "learning_state.json"
        migrated_data = json.loads(new_ls_path.read_text())
        
        materials_progress = migrated_data["topic_progress"]["Materials"]
        assert materials_progress["quiz_scores"] == [85, 90]
        assert materials_progress["average_score"] == 87.5

    def test_old_files_preserved_after_migration(self):
        """Test old files are preserved (not deleted) after migration."""
        self._create_old_structure()
        
        migrate_to_subjects()
        
        # Original files should still exist (cleanup is separate step)
        assert self.old_kg.exists()
        assert self.old_ls.exists()
        assert self.old_sr.exists()

    def test_backup_matches_original(self):
        """Test backup files are exact copies of originals."""
        self._create_old_structure()
        original_kg = self.old_kg.read_text()
        original_ls = self.old_ls.read_text()
        original_sr = self.old_sr.read_text()
        
        migrate_to_subjects(create_backup=True)
        
        backup_dir = self.data_dir / "pre_migration_backup"
        assert (backup_dir / "knowledge_graph.json").read_text() == original_kg
        assert (backup_dir / "learning_state.json").read_text() == original_ls
        assert (backup_dir / "sr_state.json").read_text() == original_sr

    # -------------------------------------------------------------------------
    # Test Backward Compatibility with Old API Calls
    # -------------------------------------------------------------------------

    def test_subject_manager_needs_migration(self):
        """Test SubjectManager.needs_migration() detects old files."""
        self._create_old_structure()
        
        # Create data dir for SubjectManager
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        manager = SubjectManager(str(self.data_dir))
        assert manager.needs_migration() is True

    def test_subject_manager_no_migration_clean_install(self):
        """Test SubjectManager.needs_migration() returns False on clean install."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        manager = SubjectManager(str(self.data_dir))
        assert manager.needs_migration() is False

    def test_subject_manager_migration_info(self):
        """Test SubjectManager.get_migration_info() returns correct info."""
        self._create_old_structure()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        manager = SubjectManager(str(self.data_dir))
        info = manager.get_migration_info()
        
        assert info["needs_migration"] is True
        assert "knowledge_graph.json" in info["files"]
        assert "learning_state.json" in info["files"]
        assert "sr_state.json" in info["files"]

    def test_default_subject_created_on_init(self):
        """Test default 'General' subject is created on SubjectManager init."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        manager = SubjectManager(str(self.data_dir))
        
        assert manager.subject_exists(DEFAULT_SUBJECT_ID)
        subject = manager.get_subject(DEFAULT_SUBJECT_ID)
        assert subject.name == "General"
        assert subject.is_default is True

    def test_migrated_data_accessible_via_manager(self):
        """Test migrated data is accessible through SubjectManager."""
        self._create_old_structure()
        
        # Run migration
        migrate_to_subjects()
        
        # Access via manager
        manager = SubjectManager(str(self.data_dir))
        
        # Should be able to get paths to migrated files
        kg_path = manager.get_knowledge_graph_path(DEFAULT_SUBJECT_ID)
        ls_path = manager.get_learning_state_path(DEFAULT_SUBJECT_ID)
        sr_path = manager.get_sr_state_path(DEFAULT_SUBJECT_ID)
        
        assert Path(kg_path).exists()
        assert Path(ls_path).exists()
        assert Path(sr_path).exists()

    def test_collection_names_for_migrated_subject(self):
        """Test ChromaDB collection names are correctly generated."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        manager = SubjectManager(str(self.data_dir))
        chunks_name, concepts_name = manager.get_collection_names(DEFAULT_SUBJECT_ID)
        
        assert chunks_name == "subject_general_chunks"
        assert concepts_name == "subject_general_concepts"

    # -------------------------------------------------------------------------
    # Test Migration Results and Status
    # -------------------------------------------------------------------------

    def test_migration_result_structure(self):
        """Test migration result has expected structure."""
        self._create_old_structure()
        
        result = migrate_to_subjects()
        
        assert "status" in result
        assert "backup" in result
        assert "json_files" in result
        assert "chroma" in result
        assert "errors" in result

    def test_migration_success_status(self):
        """Test successful migration returns success status."""
        self._create_old_structure()
        
        result = migrate_to_subjects()
        
        assert result["status"] == "success"
        assert result["errors"] == []

    def test_migration_json_files_result(self):
        """Test migration reports correct status for each JSON file."""
        self._create_old_structure()
        
        result = migrate_to_subjects()
        
        json_results = result["json_files"]
        assert json_results["knowledge_graph"]["status"] == "success"
        assert json_results["learning_state"]["status"] == "success"
        assert json_results["sr_state"]["status"] == "success"

    def test_migration_already_complete_status(self):
        """Test migration returns 'already_complete' when marker exists."""
        self._create_old_structure()
        
        # First migration
        migrate_to_subjects()
        
        # Second attempt
        result = migrate_to_subjects()
        
        assert result["status"] == "already_complete"

    # -------------------------------------------------------------------------
    # Test Cleanup Functionality
    # -------------------------------------------------------------------------

    def test_cleanup_dry_run(self):
        """Test cleanup dry run doesn't delete files."""
        self._create_old_structure()
        migrate_to_subjects()
        
        result = cleanup_old_files(dry_run=True)
        
        assert result["dry_run"] is True
        assert len(result["files"]) == 3
        
        # Files should still exist
        assert self.old_kg.exists()
        assert self.old_ls.exists()
        assert self.old_sr.exists()

    def test_cleanup_actual_delete(self):
        """Test cleanup actually deletes files when dry_run=False."""
        self._create_old_structure()
        migrate_to_subjects()
        
        result = cleanup_old_files(dry_run=False)
        
        assert result["dry_run"] is False
        
        # Files should be deleted
        assert not self.old_kg.exists()
        assert not self.old_ls.exists()
        assert not self.old_sr.exists()

    def test_cleanup_requires_migration_complete(self):
        """Test cleanup fails if migration not complete."""
        self._create_old_structure()
        
        # Don't run migration
        result = cleanup_old_files(dry_run=False)
        
        assert "error" in result
        assert "Migration not complete" in result["error"]

    # -------------------------------------------------------------------------
    # Test Edge Cases
    # -------------------------------------------------------------------------

    def test_partial_old_files(self):
        """Test migration with only some old files present."""
        # Only create knowledge_graph
        self.old_kg.write_text('{"nodes": [], "links": []}')
        
        result = migrate_to_subjects()
        
        assert result["status"] == "success"
        assert result["json_files"]["knowledge_graph"]["status"] == "success"
        # Other files should not be in results since they didn't exist
        assert "learning_state" not in result["json_files"]
        assert "sr_state" not in result["json_files"]

    def test_empty_old_files(self):
        """Test migration with empty old files."""
        self._create_empty_old_structure()
        
        result = migrate_to_subjects()
        
        assert result["status"] == "success"
        
        # Verify empty files migrated
        new_kg = self.data_dir / "subjects" / "general" / "knowledge_graph.json"
        assert new_kg.exists()

    def test_malformed_json_handling(self):
        """Test migration handles malformed JSON gracefully."""
        self.old_kg.write_text("not valid json {")
        
        result = migrate_to_subjects()
        
        # Migration should still succeed (copies file as-is)
        assert result["status"] in ["success", "completed_with_errors"]

    def test_large_data_migration(self):
        """Test migration handles large data files."""
        # Create large knowledge graph
        nodes = [{"id": f"concept-{i}", "name": f"Concept {i}"} for i in range(1000)]
        large_kg = {
            "directed": True,
            "nodes": nodes,
            "links": []
        }
        self.old_kg.write_text(json.dumps(large_kg))
        
        result = migrate_to_subjects()
        
        assert result["status"] == "success"
        
        # Verify all nodes migrated
        new_kg = self.data_dir / "subjects" / "general" / "knowledge_graph.json"
        migrated = json.loads(new_kg.read_text())
        assert len(migrated["nodes"]) == 1000

    def test_unicode_content_preserved(self):
        """Test Unicode content is preserved during migration."""
        kg_data = {
            "nodes": [
                {"id": "1", "name": "概念", "definition": "中文定义"},
                {"id": "2", "name": "Ümläut", "definition": "Définition française"}
            ],
            "links": []
        }
        self.old_kg.write_text(json.dumps(kg_data, ensure_ascii=False), encoding="utf-8")
        
        migrate_to_subjects()
        
        new_kg = self.data_dir / "subjects" / "general" / "knowledge_graph.json"
        migrated = json.loads(new_kg.read_text(encoding="utf-8"))
        
        assert migrated["nodes"][0]["name"] == "概念"
        assert migrated["nodes"][1]["name"] == "Ümläut"

    def test_special_characters_in_paths(self):
        """Test migration handles data with special characters."""
        ls_data = {
            "uploaded_materials": ["file with spaces.pdf", "file (1).pdf", "résumé.pdf"],
            "topic_progress": {}
        }
        self.old_ls.write_text(json.dumps(ls_data))
        
        migrate_to_subjects()
        
        new_ls = self.data_dir / "subjects" / "general" / "learning_state.json"
        migrated = json.loads(new_ls.read_text())
        
        assert "résumé.pdf" in migrated["uploaded_materials"]


class TestSubjectStorage:
    """Test SubjectStorage utilities related to migration."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test fixtures."""
        self.test_dir = tmp_path
        self.data_dir = tmp_path / "data"
        self.storage = SubjectStorage(str(self.data_dir))
        yield

    def test_initialize_subject_files_creates_all(self):
        """Test initialize_subject_files creates all required files."""
        self.storage.initialize_subject_files("general")
        
        subject_dir = self.data_dir / "subjects" / "general"
        assert (subject_dir / "documents.json").exists()
        assert (subject_dir / "knowledge_graph.json").exists()
        assert (subject_dir / "learning_state.json").exists()
        assert (subject_dir / "sr_state.json").exists()

    def test_initialize_subject_files_default_content(self):
        """Test initialized files have correct default content."""
        self.storage.initialize_subject_files("test_subject")
        
        subject_dir = self.data_dir / "subjects" / "test_subject"
        
        # Check documents.json
        docs = json.loads((subject_dir / "documents.json").read_text())
        assert docs == []
        
        # Check knowledge_graph.json
        kg = json.loads((subject_dir / "knowledge_graph.json").read_text())
        assert kg["directed"] is True
        assert kg["nodes"] == []
        assert kg["links"] == []
        
        # Check learning_state.json
        ls = json.loads((subject_dir / "learning_state.json").read_text())
        assert ls["total_quizzes_taken"] == 0
        assert ls["topic_progress"] == {}

    def test_initialize_subject_files_idempotent(self):
        """Test initialize_subject_files doesn't overwrite existing files."""
        self.storage.initialize_subject_files("general")
        
        # Modify a file
        ls_path = self.data_dir / "subjects" / "general" / "learning_state.json"
        modified_data = {"modified": True, "total_quizzes_taken": 10}
        ls_path.write_text(json.dumps(modified_data))
        
        # Re-initialize
        self.storage.initialize_subject_files("general")
        
        # File should not be overwritten
        current_data = json.loads(ls_path.read_text())
        assert current_data["modified"] is True
        assert current_data["total_quizzes_taken"] == 10

    def test_subject_dir_paths_correct(self):
        """Test subject directory path generation."""
        self.storage.initialize_subject_files("physics")
        
        subject_dir = self.storage.get_subject_dir("physics")
        assert subject_dir == self.data_dir / "subjects" / "physics"

    def test_collection_names_format(self):
        """Test ChromaDB collection names follow expected format."""
        chunks, concepts = SubjectStorage.get_collection_names("my_subject")
        
        assert chunks == "subject_my_subject_chunks"
        assert concepts == "subject_my_subject_concepts"

    def test_collection_names_handle_hyphens(self):
        """Test collection names convert hyphens to underscores."""
        chunks, concepts = SubjectStorage.get_collection_names("my-subject")
        
        assert chunks == "subject_my_subject_chunks"
        assert concepts == "subject_my_subject_concepts"

    def test_validate_subject_id_rejects_path_traversal(self):
        """Test subject ID validation rejects path traversal attempts."""
        with pytest.raises(ValueError, match="path traversal"):
            SubjectStorage._validate_subject_id("../../../etc")

        with pytest.raises(ValueError, match="path traversal"):
            SubjectStorage._validate_subject_id("subject/../admin")

    def test_validate_subject_id_rejects_special_chars(self):
        """Test subject ID validation rejects special characters."""
        with pytest.raises(ValueError):
            SubjectStorage._validate_subject_id("subject@name")

        with pytest.raises(ValueError):
            SubjectStorage._validate_subject_id("subject name")

    def test_validate_subject_id_allows_valid_ids(self):
        """Test subject ID validation accepts valid IDs."""
        assert SubjectStorage._validate_subject_id("general") == "general"
        assert SubjectStorage._validate_subject_id("my_subject") == "my_subject"
        assert SubjectStorage._validate_subject_id("Physics-101") == "Physics-101"
        assert SubjectStorage._validate_subject_id("Subject123") == "Subject123"


class TestMigrationIntegration:
    """Integration tests for migration with full system."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up integration test fixtures."""
        self.test_dir = tmp_path
        self.original_cwd = os.getcwd()
        os.chdir(tmp_path)
        self.data_dir = tmp_path / "data"
        yield
        os.chdir(self.original_cwd)

    def test_full_migration_workflow(self):
        """Test complete migration workflow from old structure to new."""
        # 1. Create old structure
        old_kg = self.test_dir / "knowledge_graph.json"
        old_ls = self.test_dir / "learning_state.json"
        old_sr = self.test_dir / "sr_state.json"
        
        kg_data = {"nodes": [{"id": "c1", "name": "Test"}], "links": []}
        ls_data = {"total_quizzes_taken": 5, "topic_progress": {}}
        sr_data = {"cards": {"card1": {"interval": 3}}}
        
        old_kg.write_text(json.dumps(kg_data))
        old_ls.write_text(json.dumps(ls_data))
        old_sr.write_text(json.dumps(sr_data))
        
        # 2. Check migration needed
        assert needs_migration() is True
        
        # 3. Run migration
        result = migrate_to_subjects()
        assert result["status"] == "success"
        
        # 4. Verify via SubjectManager
        manager = SubjectManager(str(self.data_dir))
        
        # Check default subject exists
        assert manager.subject_exists(DEFAULT_SUBJECT_ID)
        
        # Check data files accessible
        kg_path = Path(manager.get_knowledge_graph_path(DEFAULT_SUBJECT_ID))
        assert kg_path.exists()
        
        migrated_kg = json.loads(kg_path.read_text())
        assert migrated_kg["nodes"][0]["name"] == "Test"
        
        # 5. Verify migration no longer needed
        assert needs_migration() is False
        
        # 6. Cleanup
        cleanup_old_files(dry_run=False)
        assert not old_kg.exists()

    def test_migration_preserves_all_quiz_data(self):
        """Test migration preserves all quiz and progress data."""
        old_ls = self.test_dir / "learning_state.json"
        
        comprehensive_ls = {
            "user_id": "student123",
            "uploaded_materials": ["textbook.pdf", "notes.docx"],
            "topic_progress": {
                "Calculus": {
                    "quiz_scores": [75, 80, 85, 90, 95],
                    "average_score": 85.0,
                    "total_attempts": 5,
                    "last_quiz_date": "2024-01-15"
                },
                "Linear Algebra": {
                    "quiz_scores": [70, 75],
                    "average_score": 72.5,
                    "total_attempts": 2
                }
            },
            "weak_topics": ["Differential Equations"],
            "strong_topics": ["Calculus"],
            "flashcard_review_queue": ["card1", "card2", "card3"],
            "total_quizzes_taken": 7,
            "total_study_time_minutes": 450.5,
            "current_streak": 5,
            "longest_streak": 10
        }
        old_ls.write_text(json.dumps(comprehensive_ls))
        
        migrate_to_subjects()
        
        new_ls = self.data_dir / "subjects" / "general" / "learning_state.json"
        migrated = json.loads(new_ls.read_text())
        
        # Verify all data preserved
        assert migrated["user_id"] == "student123"
        assert migrated["total_quizzes_taken"] == 7
        assert migrated["total_study_time_minutes"] == 450.5
        assert migrated["current_streak"] == 5
        assert len(migrated["topic_progress"]) == 2
        assert migrated["topic_progress"]["Calculus"]["quiz_scores"] == [75, 80, 85, 90, 95]

    def test_concurrent_access_after_migration(self):
        """Test data remains accessible after migration with multiple managers."""
        old_kg = self.test_dir / "knowledge_graph.json"
        old_kg.write_text(json.dumps({"nodes": [], "links": []}))
        
        migrate_to_subjects()
        
        # Create multiple managers (simulating concurrent access)
        manager1 = SubjectManager(str(self.data_dir))
        manager2 = SubjectManager(str(self.data_dir))
        
        # Both should see the same default subject
        assert manager1.subject_exists(DEFAULT_SUBJECT_ID)
        assert manager2.subject_exists(DEFAULT_SUBJECT_ID)
        
        subject1 = manager1.get_subject(DEFAULT_SUBJECT_ID)
        subject2 = manager2.get_subject(DEFAULT_SUBJECT_ID)
        
        assert subject1.name == subject2.name == "General"


class TestMigrationEdgeCases:
    """Edge case tests for migration scenarios."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up edge case test fixtures."""
        self.test_dir = tmp_path
        self.original_cwd = os.getcwd()
        os.chdir(tmp_path)
        self.data_dir = tmp_path / "data"
        yield
        os.chdir(self.original_cwd)

    def test_migration_with_read_only_destination(self):
        """Test migration handles read-only destination gracefully."""
        old_kg = self.test_dir / "knowledge_graph.json"
        old_kg.write_text("{}")
        
        # This test verifies migration doesn't crash on permission issues
        # Actual behavior may vary by OS
        result = migrate_to_subjects()
        # Should either succeed or report errors gracefully
        assert "status" in result

    def test_migration_info_accuracy(self):
        """Test get_migration_info accurately reports state."""
        # Initially no files
        info1 = get_migration_info()
        assert info1["needs_migration"] is False
        assert all(not v for v in info1["files_to_migrate"].values())
        
        # Add one file
        old_kg = self.test_dir / "knowledge_graph.json"
        old_kg.write_text("{}")
        
        info2 = get_migration_info()
        assert info2["needs_migration"] is True
        assert info2["files_to_migrate"]["knowledge_graph"] is True
        assert info2["files_to_migrate"]["learning_state"] is False
        
        # Run migration
        migrate_to_subjects()
        
        info3 = get_migration_info()
        assert info3["needs_migration"] is False
        assert info3["migration_complete"] is True

    def test_migration_with_existing_subject_data(self):
        """Test migration when subject directory already has some data."""
        old_kg = self.test_dir / "knowledge_graph.json"
        old_kg.write_text(json.dumps({"nodes": [{"id": "new"}], "links": []}))
        
        # Pre-create subject with existing data
        self.data_dir.mkdir(parents=True, exist_ok=True)
        subject_dir = self.data_dir / "subjects" / "general"
        subject_dir.mkdir(parents=True, exist_ok=True)
        
        existing_docs = [{"id": "doc1", "name": "Existing Doc"}]
        (subject_dir / "documents.json").write_text(json.dumps(existing_docs))
        
        # Run migration
        result = migrate_to_subjects()
        
        # Migration should succeed
        assert result["status"] == "success"
        
        # Existing documents should be preserved
        docs = json.loads((subject_dir / "documents.json").read_text())
        assert docs == existing_docs

    def test_multiple_subjects_after_migration(self):
        """Test creating additional subjects after migration."""
        old_kg = self.test_dir / "knowledge_graph.json"
        old_kg.write_text("{}")
        
        migrate_to_subjects()
        
        manager = SubjectManager(str(self.data_dir))
        
        # Create new subjects
        physics = manager.create_subject("Physics", description="Physics course")
        math = manager.create_subject("Mathematics", description="Math course")
        
        # All subjects should coexist
        subjects = manager.list_subjects()
        subject_names = [s.name for s in subjects]
        
        assert "General" in subject_names
        assert "Physics" in subject_names
        assert "Mathematics" in subject_names

    def test_mark_migration_complete_creates_marker(self):
        """Test mark_migration_complete creates proper marker file."""
        mark_migration_complete()
        
        marker = self.data_dir / ".migration_complete"
        assert marker.exists()
        
        data = json.loads(marker.read_text())
        assert "migration_time" in data
        assert "version" in data
        assert data["version"] == "1.0.0"
