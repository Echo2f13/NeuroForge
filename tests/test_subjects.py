"""Tests for Subject Management.

Tests for SubjectManager CRUD operations, subject-scoped storage,
subject-scoped features, and migration functionality.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from models.subject import (
    Subject,
    SubjectDocument,
    SubjectSettings,
    SubjectStatus,
    SubjectSummary,
)
from src.subjects.manager import (
    DefaultSubjectError,
    SubjectExistsError,
    SubjectManager,
    SubjectNotFoundError,
)
from src.subjects.storage import DEFAULT_SUBJECT_ID, SubjectStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary data directory."""
    data_dir = tmp_path / "neuroforge_data"
    data_dir.mkdir()
    return str(data_dir)


@pytest.fixture
def manager(tmp_data_dir):
    """Create a fresh SubjectManager with a temp data directory."""
    return SubjectManager(data_dir=tmp_data_dir)


@pytest.fixture
def storage(tmp_data_dir):
    """Create a fresh SubjectStorage with a temp data directory."""
    return SubjectStorage(data_dir=tmp_data_dir)


# ---------------------------------------------------------------------------
# Subject Model Tests
# ---------------------------------------------------------------------------


class TestSubjectModel:
    """Tests for Subject Pydantic model."""

    def test_create_subject_minimal(self):
        """Subject can be created with just a name."""
        subject = Subject(name="Test Subject")
        assert subject.name == "Test Subject"
        assert subject.id is not None
        assert len(subject.id) == 36  # UUID format
        assert subject.status == SubjectStatus.ACTIVE
        assert subject.is_default is False

    def test_create_subject_full(self):
        """Subject can be created with all fields."""
        settings = SubjectSettings(default_quiz_count=20)
        subject = Subject(
            name="Full Subject",
            description="A detailed description",
            color="#FF5733",
            icon="📚",
            settings=settings,
        )
        assert subject.name == "Full Subject"
        assert subject.description == "A detailed description"
        assert subject.color == "#FF5733"
        assert subject.icon == "📚"
        assert subject.settings.default_quiz_count == 20


    def test_name_validation_empty(self):
        """Subject name cannot be empty."""
        with pytest.raises(ValueError):
            Subject(name="")

    def test_name_validation_too_long(self):
        """Subject name cannot exceed 100 characters."""
        with pytest.raises(ValueError):
            Subject(name="x" * 101)

    def test_color_validation_valid(self):
        """Valid hex colors are accepted."""
        subject = Subject(name="Test", color="#FF5733")
        assert subject.color == "#FF5733"

    def test_color_validation_invalid(self):
        """Invalid hex colors are rejected."""
        with pytest.raises(ValueError):
            Subject(name="Test", color="not-a-color")
        with pytest.raises(ValueError):
            Subject(name="Test", color="#GG5733")

    def test_serialization_round_trip(self):
        """Subject can be serialized and deserialized."""
        original = Subject(
            name="Serialize Test",
            description="Testing serialization",
            color="#123456",
        )
        data = original.to_dict()
        restored = Subject.from_dict(data)
        assert restored.name == original.name
        assert restored.id == original.id
        assert restored.color == original.color


# ---------------------------------------------------------------------------
# SubjectManager Initialization Tests
# ---------------------------------------------------------------------------


class TestSubjectManagerInit:
    """Tests for SubjectManager initialization."""

    def test_creates_default_subject(self, manager):
        """Manager creates default 'General' subject on init."""
        subject = manager.get_subject(DEFAULT_SUBJECT_ID)
        assert subject.name == "General"
        assert subject.is_default is True

    def test_default_subject_directory_created(self, manager, tmp_data_dir):
        """Default subject directory structure is created."""
        subject_dir = Path(tmp_data_dir) / "subjects" / DEFAULT_SUBJECT_ID
        assert subject_dir.exists()
        assert (subject_dir / "knowledge_graph.json").exists()
        assert (subject_dir / "learning_state.json").exists()
        assert (subject_dir / "sr_state.json").exists()

    def test_loads_existing_subjects(self, tmp_data_dir):
        """Manager loads existing subjects on init."""
        # Create first manager and add a subject
        manager1 = SubjectManager(data_dir=tmp_data_dir)
        manager1.create_subject("Physics")
        
        # Create second manager, should load existing subjects
        manager2 = SubjectManager(data_dir=tmp_data_dir)
        subjects = manager2.list_subjects()
        names = [s.name for s in subjects]
        assert "General" in names
        assert "Physics" in names


# ---------------------------------------------------------------------------
# Create Subject Tests
# ---------------------------------------------------------------------------


class TestCreateSubject:
    """Tests for creating subjects."""

    def test_create_subject_minimal(self, manager):
        """Create subject with just a name."""
        subject = manager.create_subject("Mathematics")
        assert subject.name == "Mathematics"
        assert subject.id is not None
        assert manager.subject_exists(subject.id)

    def test_create_subject_full(self, manager):
        """Create subject with all fields."""
        subject = manager.create_subject(
            name="Chemistry",
            description="Study of matter and reactions",
            color="#3498db",
            icon="🧪",
        )
        assert subject.name == "Chemistry"
        assert subject.description == "Study of matter and reactions"
        assert subject.color == "#3498db"
        assert subject.icon == "🧪"

    def test_create_subject_directory_created(self, manager, tmp_data_dir):
        """Creating a subject creates its directory structure."""
        subject = manager.create_subject("Biology")
        subject_dir = Path(tmp_data_dir) / "subjects" / subject.id
        assert subject_dir.exists()
        assert (subject_dir / "knowledge_graph.json").exists()

    def test_create_duplicate_name_raises(self, manager):
        """Creating subject with existing name raises error."""
        manager.create_subject("Physics")
        with pytest.raises(SubjectExistsError):
            manager.create_subject("Physics")


    def test_create_duplicate_name_case_insensitive(self, manager):
        """Duplicate name check is case-insensitive."""
        manager.create_subject("Physics")
        with pytest.raises(SubjectExistsError):
            manager.create_subject("PHYSICS")
        with pytest.raises(SubjectExistsError):
            manager.create_subject("physics")

    def test_create_subject_persists(self, tmp_data_dir):
        """Created subject persists across manager instances."""
        manager1 = SubjectManager(data_dir=tmp_data_dir)
        subject = manager1.create_subject("History")
        
        manager2 = SubjectManager(data_dir=tmp_data_dir)
        loaded = manager2.get_subject(subject.id)
        assert loaded.name == "History"


# ---------------------------------------------------------------------------
# Read Subject Tests
# ---------------------------------------------------------------------------


class TestReadSubject:
    """Tests for reading subjects."""

    def test_get_subject(self, manager):
        """Get subject by ID."""
        created = manager.create_subject("Geography")
        retrieved = manager.get_subject(created.id)
        assert retrieved.name == "Geography"
        assert retrieved.id == created.id

    def test_get_subject_not_found(self, manager):
        """Getting non-existent subject raises error."""
        with pytest.raises(SubjectNotFoundError):
            manager.get_subject("nonexistent-id")

    def test_subject_exists(self, manager):
        """Check if subject exists."""
        subject = manager.create_subject("Literature")
        assert manager.subject_exists(subject.id) is True
        assert manager.subject_exists("fake-id") is False


    def test_list_subjects_active_only(self, manager):
        """List subjects returns only active by default."""
        manager.create_subject("Active1")
        archived = manager.create_subject("Archived1")
        manager.archive_subject(archived.id)
        
        subjects = manager.list_subjects()
        names = [s.name for s in subjects]
        assert "Active1" in names
        assert "Archived1" not in names

    def test_list_subjects_include_archived(self, manager):
        """List subjects can include archived."""
        manager.create_subject("Active2")
        archived = manager.create_subject("Archived2")
        manager.archive_subject(archived.id)
        
        subjects = manager.list_subjects(include_archived=True)
        names = [s.name for s in subjects]
        assert "Active2" in names
        assert "Archived2" in names

    def test_list_subjects_returns_summaries(self, manager):
        """List subjects returns SubjectSummary objects."""
        manager.create_subject("SummaryTest")
        subjects = manager.list_subjects()
        assert all(isinstance(s, SubjectSummary) for s in subjects)


# ---------------------------------------------------------------------------
# Update Subject Tests
# ---------------------------------------------------------------------------


class TestUpdateSubject:
    """Tests for updating subjects."""

    def test_update_name(self, manager):
        """Update subject name."""
        subject = manager.create_subject("Old Name")
        updated = manager.update_subject(subject.id, name="New Name")
        assert updated.name == "New Name"

    def test_update_description(self, manager):
        """Update subject description."""
        subject = manager.create_subject("DescTest")
        updated = manager.update_subject(
            subject.id, description="New description"
        )
        assert updated.description == "New description"


    def test_update_color_and_icon(self, manager):
        """Update subject color and icon."""
        subject = manager.create_subject("StyleTest")
        updated = manager.update_subject(
            subject.id, color="#FF0000", icon="🎨"
        )
        assert updated.color == "#FF0000"
        assert updated.icon == "🎨"

    def test_update_nonexistent_raises(self, manager):
        """Updating non-existent subject raises error."""
        with pytest.raises(SubjectNotFoundError):
            manager.update_subject("fake-id", name="New Name")

    def test_update_to_duplicate_name_raises(self, manager):
        """Updating to existing name raises error."""
        manager.create_subject("ExistingName")
        subject = manager.create_subject("OriginalName")
        with pytest.raises(SubjectExistsError):
            manager.update_subject(subject.id, name="ExistingName")

    def test_update_updates_timestamp(self, manager):
        """Update changes updated_at timestamp."""
        import time
        subject = manager.create_subject("TimestampTest")
        original_updated = subject.updated_at
        time.sleep(0.1)
        updated = manager.update_subject(subject.id, description="Changed")
        assert updated.updated_at > original_updated

    def test_update_persists(self, tmp_data_dir):
        """Updates persist across manager instances."""
        manager1 = SubjectManager(data_dir=tmp_data_dir)
        subject = manager1.create_subject("PersistTest")
        manager1.update_subject(subject.id, name="UpdatedName")
        
        manager2 = SubjectManager(data_dir=tmp_data_dir)
        loaded = manager2.get_subject(subject.id)
        assert loaded.name == "UpdatedName"


# ---------------------------------------------------------------------------
# Delete Subject Tests
# ---------------------------------------------------------------------------


class TestDeleteSubject:
    """Tests for deleting subjects."""

    def test_delete_subject(self, manager):
        """Delete a non-default subject."""
        subject = manager.create_subject("ToDelete")
        result = manager.delete_subject(subject.id)
        assert result is True
        assert manager.subject_exists(subject.id) is False

    def test_delete_subject_removes_directory(self, manager, tmp_data_dir):
        """Deleting subject removes its directory."""
        subject = manager.create_subject("DirDelete")
        subject_dir = Path(tmp_data_dir) / "subjects" / subject.id
        assert subject_dir.exists()
        
        manager.delete_subject(subject.id)
        assert not subject_dir.exists()

    def test_delete_default_raises(self, manager):
        """Cannot delete default subject without force."""
        with pytest.raises(DefaultSubjectError):
            manager.delete_subject(DEFAULT_SUBJECT_ID)

    def test_delete_default_with_force(self, manager):
        """Can delete default subject with force=True."""
        # First create another subject so system isn't empty
        manager.create_subject("Replacement")
        result = manager.delete_subject(DEFAULT_SUBJECT_ID, force=True)
        assert result is True
        assert manager.subject_exists(DEFAULT_SUBJECT_ID) is False

    def test_delete_nonexistent_raises(self, manager):
        """Deleting non-existent subject raises error."""
        with pytest.raises(SubjectNotFoundError):
            manager.delete_subject("nonexistent-id")


# ---------------------------------------------------------------------------
# Archive/Restore Tests
# ---------------------------------------------------------------------------


class TestArchiveRestore:
    """Tests for archive and restore operations."""

    def test_archive_subject(self, manager):
        """Archive a subject."""
        subject = manager.create_subject("ToArchive")
        archived = manager.archive_subject(subject.id)
        assert archived.status == SubjectStatus.ARCHIVED

    def test_archive_default_raises(self, manager):
        """Cannot archive default subject."""
        with pytest.raises(DefaultSubjectError):
            manager.archive_subject(DEFAULT_SUBJECT_ID)

    def test_restore_subject(self, manager):
        """Restore an archived subject."""
        subject = manager.create_subject("ToRestore")
        manager.archive_subject(subject.id)
        restored = manager.restore_subject(subject.id)
        assert restored.status == SubjectStatus.ACTIVE

    def test_archived_excluded_from_list(self, manager):
        """Archived subjects not in default list."""
        subject = manager.create_subject("ArchivedTest")
        manager.archive_subject(subject.id)
        
        subjects = manager.list_subjects()
        ids = [s.id for s in subjects]
        assert subject.id not in ids

    def test_archived_data_preserved(self, manager, tmp_data_dir):
        """Archived subject data is preserved."""
        subject = manager.create_subject("DataPreserve")
        subject_dir = Path(tmp_data_dir) / "subjects" / subject.id
        
        manager.archive_subject(subject.id)
        
        # Data should still exist
        assert subject_dir.exists()
        assert (subject_dir / "knowledge_graph.json").exists()


# ---------------------------------------------------------------------------
# Document Management Tests
# ---------------------------------------------------------------------------


class TestDocumentManagement:
    """Tests for document management within subjects."""

    def test_add_document(self, manager):
        """Add a document to a subject."""
        subject = manager.create_subject("DocSubject")
        doc = manager.add_document(
            subject_id=subject.id,
            doc_id="doc-123",
            filename="test.pdf",
            file_type="pdf",
            chunk_count=10,
            concept_count=5,
        )
        assert doc.id == "doc-123"
        assert doc.filename == "test.pdf"
        assert doc.chunk_count == 10

    def test_list_documents(self, manager):
        """List documents in a subject."""
        subject = manager.create_subject("ListDocsSubject")
        manager.add_document(
            subject_id=subject.id,
            doc_id="doc-1",
            filename="file1.pdf",
            file_type="pdf",
        )
        manager.add_document(
            subject_id=subject.id,
            doc_id="doc-2",
            filename="file2.docx",
            file_type="docx",
        )
        
        docs = manager.list_documents(subject.id)
        assert len(docs) == 2
        filenames = [d.filename for d in docs]
        assert "file1.pdf" in filenames
        assert "file2.docx" in filenames

    def test_delete_document(self, manager):
        """Delete a document from a subject."""
        subject = manager.create_subject("DeleteDocSubject")
        manager.add_document(
            subject_id=subject.id,
            doc_id="doc-to-delete",
            filename="delete_me.pdf",
            file_type="pdf",
        )
        
        result = manager.delete_document(subject.id, "doc-to-delete")
        assert result is True
        
        docs = manager.list_documents(subject.id)
        assert len(docs) == 0


# ---------------------------------------------------------------------------
# Statistics Tests
# ---------------------------------------------------------------------------


class TestSubjectStats:
    """Tests for subject statistics."""

    def test_get_stats_empty(self, manager):
        """Get stats for subject with no data."""
        subject = manager.create_subject("EmptyStats")
        stats = manager.get_subject_stats(subject.id)
        assert stats["document_count"] == 0
        assert stats["chunk_count"] == 0
        assert stats["quiz_count"] == 0

    def test_get_stats_with_documents(self, manager):
        """Get stats reflects document counts."""
        subject = manager.create_subject("StatsWithDocs")
        manager.add_document(
            subject_id=subject.id,
            doc_id="doc-1",
            filename="file1.pdf",
            file_type="pdf",
            chunk_count=15,
            concept_count=8,
        )
        
        stats = manager.get_subject_stats(subject.id)
        assert stats["document_count"] == 1
        assert stats["chunk_count"] == 15
        assert stats["concept_count"] == 8

    def test_get_global_stats(self, manager):
        """Get aggregated stats across all subjects."""
        # Add docs to different subjects
        sub1 = manager.create_subject("GlobalStats1")
        sub2 = manager.create_subject("GlobalStats2")
        
        manager.add_document(sub1.id, "d1", "f1.pdf", "pdf", chunk_count=10)
        manager.add_document(sub2.id, "d2", "f2.pdf", "pdf", chunk_count=20)
        
        stats = manager.get_global_stats()
        assert stats["subject_count"] >= 2  # At least our subjects + default
        assert stats["document_count"] >= 2
        assert stats["chunk_count"] >= 30


# ---------------------------------------------------------------------------
# SubjectStorage Tests
# ---------------------------------------------------------------------------


class TestSubjectStorage:
    """Tests for SubjectStorage utility class."""

    def test_get_subject_dir(self, storage, tmp_data_dir):
        """Get subject directory path."""
        path = storage.get_subject_dir("test-subject")
        assert "subjects" in str(path)
        assert "test-subject" in str(path)

    def test_ensure_subject_dirs(self, storage, tmp_data_dir):
        """Ensure subject directory structure is created."""
        storage.ensure_subject_dirs("new-subject")
        subject_dir = Path(tmp_data_dir) / "subjects" / "new-subject"
        assert subject_dir.exists()

    def test_path_traversal_prevention(self, storage):
        """Prevent path traversal attacks."""
        # These should raise ValueError due to path traversal characters
        with pytest.raises(ValueError) as exc_info:
            storage.get_subject_dir("../../../etc")
        assert "path traversal" in str(exc_info.value).lower()
        
        with pytest.raises(ValueError) as exc_info:
            storage.get_subject_dir("..\\..\\windows")
        assert "path traversal" in str(exc_info.value).lower()
        
    def test_get_collection_names(self, storage):
        """Get ChromaDB collection names for subject."""
        # Note: hyphens are converted to underscores for valid collection names
        chunks_name, concepts_name = storage.get_collection_names("my-subject")
        assert "my_subject" in chunks_name  # hyphen -> underscore
        assert "chunks" in chunks_name
        assert "my_subject" in concepts_name  # hyphen -> underscore
        assert "concepts" in concepts_name

    def test_initialize_subject_files(self, storage, tmp_data_dir):
        """Initialize empty subject files."""
        storage.initialize_subject_files("init-test")
        subject_dir = Path(tmp_data_dir) / "subjects" / "init-test"
        
        assert (subject_dir / "knowledge_graph.json").exists()
        assert (subject_dir / "learning_state.json").exists()
        assert (subject_dir / "sr_state.json").exists()
        assert (subject_dir / "documents.json").exists()


# ---------------------------------------------------------------------------
# Component Factory Tests
# ---------------------------------------------------------------------------


class TestComponentFactories:
    """Tests for subject component factories."""

    def test_get_knowledge_graph_path(self, manager):
        """Get knowledge graph path for subject."""
        subject = manager.create_subject("KGPathTest")
        path = manager.get_knowledge_graph_path(subject.id)
        assert subject.id in path
        assert "knowledge_graph.json" in path

    def test_get_learning_state_path(self, manager):
        """Get learning state path for subject."""
        subject = manager.create_subject("LSPathTest")
        path = manager.get_learning_state_path(subject.id)
        assert subject.id in path
        assert "learning_state.json" in path

    def test_get_sr_state_path(self, manager):
        """Get spaced repetition state path for subject."""
        subject = manager.create_subject("SRPathTest")
        path = manager.get_sr_state_path(subject.id)
        assert subject.id in path
        assert "sr_state.json" in path

    def test_get_collection_names(self, manager):
        """Get ChromaDB collection names for subject."""
        subject = manager.create_subject("CollectionTest")
        chunks, concepts = manager.get_collection_names(subject.id)
        # UUID hyphens are converted to underscores for valid collection names
        subject_id_safe = subject.id.replace("-", "_")
        assert subject_id_safe in chunks
        assert subject_id_safe in concepts

    def test_component_paths_for_nonexistent_raises(self, manager):
        """Getting paths for non-existent subject raises error."""
        with pytest.raises(SubjectNotFoundError):
            manager.get_knowledge_graph_path("fake-id")


# ---------------------------------------------------------------------------
# Activity Tracking Tests
# ---------------------------------------------------------------------------


class TestActivityTracking:
    """Tests for activity timestamp tracking."""

    def test_update_activity(self, manager):
        """Update activity updates timestamp."""
        import time
        subject = manager.create_subject("ActivityTest")
        original_activity = subject.last_activity_at
        
        time.sleep(0.1)
        manager.update_activity(subject.id)
        
        updated = manager.get_subject(subject.id)
        assert updated.last_activity_at is not None
        if original_activity:
            assert updated.last_activity_at > original_activity

    def test_add_document_updates_activity(self, manager):
        """Adding document updates subject activity."""
        import time
        subject = manager.create_subject("DocActivityTest")
        original_activity = subject.last_activity_at
        
        time.sleep(0.1)
        manager.add_document(
            subject.id, "doc-1", "test.pdf", "pdf"
        )
        
        updated = manager.get_subject(subject.id)
        assert updated.last_activity_at is not None
        if original_activity:
            assert updated.last_activity_at > original_activity


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestSubjectIntegration:
    """Integration tests for subject workflows."""

    def test_full_subject_lifecycle(self, tmp_data_dir):
        """Test complete subject lifecycle."""
        manager = SubjectManager(data_dir=tmp_data_dir)
        
        # Create
        subject = manager.create_subject(
            name="Lifecycle Test",
            description="Testing full lifecycle",
            color="#FF5733",
            icon="🔬",
        )
        assert manager.subject_exists(subject.id)
        
        # Update
        updated = manager.update_subject(
            subject.id,
            name="Updated Lifecycle",
            description="Modified description",
        )
        assert updated.name == "Updated Lifecycle"
        
        # Add documents
        manager.add_document(subject.id, "doc-1", "file.pdf", "pdf")
        docs = manager.list_documents(subject.id)
        assert len(docs) == 1
        
        # Archive
        archived = manager.archive_subject(subject.id)
        assert archived.status == SubjectStatus.ARCHIVED
        
        # Restore
        restored = manager.restore_subject(subject.id)
        assert restored.status == SubjectStatus.ACTIVE
        
        # Delete
        manager.delete_subject(subject.id)
        assert not manager.subject_exists(subject.id)


    def test_multiple_subjects_isolation(self, manager):
        """Test that subjects are properly isolated."""
        sub1 = manager.create_subject("Subject1")
        sub2 = manager.create_subject("Subject2")
        
        # Add documents to different subjects
        manager.add_document(sub1.id, "doc-1", "sub1_file.pdf", "pdf")
        manager.add_document(sub2.id, "doc-2", "sub2_file.pdf", "pdf")
        
        # Each subject should only see its own documents
        docs1 = manager.list_documents(sub1.id)
        docs2 = manager.list_documents(sub2.id)
        
        assert len(docs1) == 1
        assert len(docs2) == 1
        assert docs1[0].filename == "sub1_file.pdf"
        assert docs2[0].filename == "sub2_file.pdf"

    def test_concurrent_subject_operations(self, tmp_data_dir):
        """Test concurrent operations on different subjects."""
        manager1 = SubjectManager(data_dir=tmp_data_dir)
        
        # Create subject with first manager
        sub1 = manager1.create_subject("ConcurrentTest1")
        
        # Second manager should load the subject (needs to be created after save)
        manager2 = SubjectManager(data_dir=tmp_data_dir)
        loaded = manager2.get_subject(sub1.id)
        assert loaded.name == "ConcurrentTest1"
        
        # Update with manager1
        manager1.update_subject(sub1.id, description="Update from manager1")
        
        # Reload and verify with a new manager instance
        manager3 = SubjectManager(data_dir=tmp_data_dir)
        final = manager3.get_subject(sub1.id)
        assert final.description == "Update from manager1"
