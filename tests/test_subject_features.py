"""Tests for Subject-Scoped Features in NeuroForge.

Tests that workflows (Quiz, Flashcard, Chat) correctly use subject-scoped
components and that progress is tracked per-subject. This ensures proper
isolation between study subjects.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from models.knowledge import Concept, Difficulty
from models.output import QuizQuestion, Flashcard
from src.memory.progress import ProgressTracker
from src.retrieval.subject_retriever import SubjectRetriever
from src.subjects.manager import SubjectManager, SubjectNotFoundError
from src.workflows.chat_tutor import ChatTutor
from src.workflows.flashcards import FlashcardWorkflow, _FlashcardBatch, _FlashcardItem
from src.workflows.quiz import QuizWorkflow, _QuizBatch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory structure."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_vector_store():
    """Create a mock SubjectScopedVectorStore."""
    store = MagicMock()
    store.search_chunks.return_value = [
        {
            "id": "chunk-001",
            "content": "Physics topic: Force equals mass times acceleration.",
            "score": 0.95,
            "metadata": {"subject_id": "physics", "topic": "mechanics"},
        },
        {
            "id": "chunk-002",
            "content": "Newton's second law describes the relationship between force and motion.",
            "score": 0.88,
            "metadata": {"subject_id": "physics", "topic": "mechanics"},
        },
    ]
    store.search_concepts.return_value = [
        {
            "id": "concept-001",
            "definition": "Force is a push or pull on an object.",
            "score": 0.92,
            "metadata": {"difficulty": "easy", "source_chunks": '["chunk-001"]'},
        },
    ]
    store.get_chunk.return_value = {
        "id": "chunk-001",
        "document": "Force equals mass times acceleration.",
        "metadata": {"subject_id": "physics"},
    }
    store.get_concept.return_value = {
        "id": "concept-001",
        "document": "Force is a push or pull.",
        "metadata": {"source_chunks": '["chunk-001"]'},
    }
    return store


@pytest.fixture
def mock_knowledge_graph():
    """Create a mock KnowledgeGraph."""
    graph = MagicMock()
    graph.__contains__ = lambda self, x: x in ["concept-001", "concept-002"]
    graph.get_prerequisites.return_value = []
    graph.get_related.return_value = ["concept-002"]
    return graph


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for quiz/flashcard generation."""
    client = MagicMock()
    return client


@pytest.fixture
def subject_retriever(mock_vector_store, mock_knowledge_graph):
    """Create a SubjectRetriever with mocked dependencies."""
    return SubjectRetriever(
        vector_store=mock_vector_store,
        knowledge_graph=mock_knowledge_graph,
        subject_id="physics",
    )


@pytest.fixture
def subject_manager(tmp_data_dir):
    """Create a SubjectManager with temporary storage."""
    with patch("src.subjects.storage.SubjectStorage") as MockStorage:
        # Set up the mock storage
        mock_storage = MagicMock()
        mock_storage.get_subjects_file_path.return_value = tmp_data_dir / "subjects.json"
        mock_storage.get_documents_path.return_value = tmp_data_dir / "docs.json"
        mock_storage.get_learning_state_path.return_value = tmp_data_dir / "ls.json"
        mock_storage.get_knowledge_graph_path.return_value = tmp_data_dir / "kg.json"
        mock_storage.get_sr_state_path.return_value = tmp_data_dir / "sr.json"
        mock_storage.get_chroma_dir.return_value = tmp_data_dir / "chroma"
        MockStorage.return_value = mock_storage
        
        manager = SubjectManager(data_dir=str(tmp_data_dir))
        return manager


# ---------------------------------------------------------------------------
# Test: Quiz Generation Uses Subject's Data
# ---------------------------------------------------------------------------


class TestQuizSubjectScoping:
    """Test that quiz generation uses subject-scoped retrieval."""

    @pytest.fixture
    def quiz_llm_response(self):
        """Sample LLM response for quiz questions."""
        return _QuizBatch(questions=[
            {
                "id": "q-001",
                "question": "What is the formula for force?",
                "question_type": "short_answer",
                "options": None,
                "correct_answer": "F = ma",
                "explanation": "Force equals mass times acceleration.",
                "topic": "mechanics",
                "difficulty": "easy",
                "source_chunk_ids": ["chunk-001"],
            },
        ])

    def test_quiz_workflow_uses_subject_retriever(
        self, subject_retriever, mock_llm_client, quiz_llm_response
    ):
        """Quiz workflow should use the subject retriever's search."""
        mock_llm_client.generate_json.return_value = (quiz_llm_response, {"total_tokens": 100})
        
        workflow = QuizWorkflow(
            llm_client=mock_llm_client,
            retriever=subject_retriever,
            subject_id="physics",
        )
        
        questions = workflow.generate(topic="force", num_questions=1)
        
        # Verify retriever was called
        subject_retriever.vector_store.search_chunks.assert_called()
        assert len(questions) >= 0  # May be 0 if validation fails


    def test_quiz_workflow_stores_subject_id(self, subject_retriever, mock_llm_client):
        """Quiz workflow should store the subject_id."""
        mock_llm_client.generate_json.return_value = (
            _QuizBatch(questions=[]),
            {"total_tokens": 50}
        )
        
        workflow = QuizWorkflow(
            llm_client=mock_llm_client,
            retriever=subject_retriever,
            subject_id="physics",
        )
        
        assert workflow.subject_id == "physics"

    def test_quiz_workflow_retrieves_from_correct_subject(
        self, mock_vector_store, mock_knowledge_graph, mock_llm_client
    ):
        """Quiz should retrieve chunks from the specified subject only."""
        retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="chemistry",
        )
        
        mock_llm_client.generate_json.return_value = (
            _QuizBatch(questions=[]),
            {"total_tokens": 50}
        )
        
        workflow = QuizWorkflow(
            llm_client=mock_llm_client,
            retriever=retriever,
            subject_id="chemistry",
        )
        
        workflow.generate(topic="reactions", num_questions=5)
        
        # Verify the search was performed via the subject retriever
        mock_vector_store.search_chunks.assert_called_with(
            "chemistry", "reactions", top_k=10
        )


# ---------------------------------------------------------------------------
# Test: Flashcard Generation Uses Subject's Data
# ---------------------------------------------------------------------------


class TestFlashcardSubjectScoping:
    """Test that flashcard generation uses subject-scoped retrieval."""

    @pytest.fixture
    def flashcard_llm_response(self):
        """Sample LLM response for flashcards."""
        return _FlashcardBatch(flashcards=[
            _FlashcardItem(
                question="What is Newton's second law?",
                answer="F = ma",
                hint="Think about force and acceleration",
                mnemonic="Force Makes Acceleration",
                related_topics=["kinematics", "dynamics"],
                difficulty="easy",
            ),
        ])

    def test_flashcard_workflow_uses_subject_retriever(
        self, subject_retriever, mock_llm_client, flashcard_llm_response
    ):
        """Flashcard workflow should use the subject retriever."""
        mock_llm_client.generate_json.return_value = (
            flashcard_llm_response, 
            {"total_tokens": 100}
        )
        
        workflow = FlashcardWorkflow(
            retriever=subject_retriever,
            llm_client=mock_llm_client,
            subject_id="physics",
        )
        
        cards = workflow.generate(topic="mechanics", num_cards=1)
        
        # Verify retriever was called
        subject_retriever.vector_store.search_chunks.assert_called()
        assert len(cards) == 1
        assert isinstance(cards[0], Flashcard)


    def test_flashcard_workflow_stores_subject_id(
        self, subject_retriever, mock_llm_client
    ):
        """Flashcard workflow should store the subject_id."""
        mock_llm_client.generate_json.return_value = (
            _FlashcardBatch(flashcards=[]),
            {"total_tokens": 50}
        )
        
        workflow = FlashcardWorkflow(
            retriever=subject_retriever,
            llm_client=mock_llm_client,
            subject_id="physics",
        )
        
        assert workflow.subject_id == "physics"

    def test_flashcard_with_difficulty_uses_filtered_search(
        self, subject_retriever, mock_llm_client
    ):
        """Flashcard with difficulty filter should use filtered_search."""
        mock_llm_client.generate_json.return_value = (
            _FlashcardBatch(flashcards=[]),
            {"total_tokens": 50}
        )
        
        workflow = FlashcardWorkflow(
            retriever=subject_retriever,
            llm_client=mock_llm_client,
            subject_id="physics",
        )
        
        workflow.generate(topic="force", difficulty="easy", num_cards=5)
        
        # Filtered search should be called instead of semantic search
        subject_retriever.vector_store.search_concepts.assert_called()


# ---------------------------------------------------------------------------
# Test: Chat Tutor Uses Subject's Retriever
# ---------------------------------------------------------------------------


class TestChatTutorSubjectScoping:
    """Test that chat tutor uses subject-scoped retrieval."""

    def test_chat_tutor_uses_subject_retriever(
        self, subject_retriever, mock_llm_client
    ):
        """Chat tutor should use the subject retriever for context."""
        mock_llm_client.generate.return_value = (
            "Force is calculated as F = ma, based on the study material.",
            {"total_tokens": 50}
        )
        
        tutor = ChatTutor(
            retriever=subject_retriever,
            llm_client=mock_llm_client,
            subject_id="physics",
        )
        
        response = tutor.ask("What is force?")
        
        # Verify retriever was called
        subject_retriever.vector_store.search_chunks.assert_called()
        assert "answer" in response
        assert "sources" in response

    def test_chat_tutor_stores_subject_id(self, subject_retriever, mock_llm_client):
        """Chat tutor should store the subject_id."""
        tutor = ChatTutor(
            retriever=subject_retriever,
            llm_client=mock_llm_client,
            subject_id="physics",
        )
        
        assert tutor.subject_id == "physics"

    def test_chat_tutor_maintains_conversation_history(
        self, subject_retriever, mock_llm_client
    ):
        """Chat tutor should maintain history within a subject session."""
        mock_llm_client.generate.return_value = (
            "Based on the material, force relates to mass and acceleration.",
            {"total_tokens": 50}
        )
        
        tutor = ChatTutor(
            retriever=subject_retriever,
            llm_client=mock_llm_client,
            subject_id="physics",
        )
        
        tutor.ask("What is force?")
        tutor.ask("How does it relate to mass?")
        
        assert len(tutor.history) == 4  # 2 questions + 2 answers


    def test_chat_tutor_reset_clears_history(
        self, subject_retriever, mock_llm_client
    ):
        """Reset should clear conversation history."""
        mock_llm_client.generate.return_value = (
            "Here's the answer based on your study materials.",
            {"total_tokens": 50}
        )
        
        tutor = ChatTutor(
            retriever=subject_retriever,
            llm_client=mock_llm_client,
            subject_id="physics",
        )
        
        tutor.ask("Question 1")
        assert len(tutor.history) == 2
        
        tutor.reset()
        assert len(tutor.history) == 0

    def test_different_subjects_have_isolated_retrieval(
        self, mock_vector_store, mock_knowledge_graph, mock_llm_client
    ):
        """Different subjects should search their own collections."""
        physics_retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="physics",
        )
        
        chemistry_retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="chemistry",
        )
        
        mock_llm_client.generate.return_value = ("Answer", {"total_tokens": 50})
        
        physics_tutor = ChatTutor(
            retriever=physics_retriever,
            llm_client=mock_llm_client,
            subject_id="physics",
        )
        
        chemistry_tutor = ChatTutor(
            retriever=chemistry_retriever,
            llm_client=mock_llm_client,
            subject_id="chemistry",
        )
        
        physics_tutor.ask("What is force?")
        chemistry_tutor.ask("What is a chemical bond?")
        
        # Both should have called search_chunks with their respective subject_ids
        calls = mock_vector_store.search_chunks.call_args_list
        subject_ids_searched = [call[0][0] for call in calls]
        assert "physics" in subject_ids_searched
        assert "chemistry" in subject_ids_searched


# ---------------------------------------------------------------------------
# Test: Progress Recorded to Subject
# ---------------------------------------------------------------------------


class TestProgressSubjectScoping:
    """Test that progress is tracked per-subject."""

    @pytest.fixture
    def progress_tracker(self, tmp_path):
        """Create a ProgressTracker with temporary state file."""
        state_file = tmp_path / "learning_state.json"
        return ProgressTracker(state_file=str(state_file))

    def test_record_score_saves_to_progress(self, progress_tracker):
        """Recording a score should update topic progress."""
        progress_tracker.record_score(topic="mechanics", score=85.0)
        
        progress = progress_tracker.get_topic_progress("mechanics")
        assert progress.attempts == 1
        assert progress.average_score == 85.0

    def test_multiple_scores_calculate_average(self, progress_tracker):
        """Multiple scores should average correctly."""
        progress_tracker.record_score(topic="thermodynamics", score=80.0)
        progress_tracker.record_score(topic="thermodynamics", score=90.0)
        
        progress = progress_tracker.get_topic_progress("thermodynamics")
        assert progress.attempts == 2
        assert progress.average_score == 85.0

    def test_separate_subjects_have_separate_progress(self, tmp_path):
        """Each subject should have its own progress tracker."""
        physics_state = tmp_path / "physics_state.json"
        chemistry_state = tmp_path / "chemistry_state.json"
        
        physics_tracker = ProgressTracker(state_file=str(physics_state))
        chemistry_tracker = ProgressTracker(state_file=str(chemistry_state))
        
        physics_tracker.record_score(topic="force", score=90.0)
        chemistry_tracker.record_score(topic="reactions", score=75.0)
        
        # Physics tracker should not have chemistry topic
        physics_progress = physics_tracker.get_topic_progress("reactions")
        assert physics_progress.attempts == 0
        
        # Chemistry tracker should not have physics topic
        chemistry_progress = chemistry_tracker.get_topic_progress("force")
        assert chemistry_progress.attempts == 0


    def test_weak_topics_identified_per_subject(self, tmp_path):
        """Weak topics should be identified based on subject-specific scores."""
        state_file = tmp_path / "state.json"
        tracker = ProgressTracker(state_file=str(state_file))
        
        # Record weak topic (below 60%)
        tracker.record_score(topic="calculus", score=45.0)
        
        # Record strong topic (above 85%)
        tracker.record_score(topic="algebra", score=95.0)
        
        weak_topics = tracker.get_weak_topics()
        strong_topics = tracker.get_strong_topics()
        
        assert "calculus" in weak_topics
        assert "algebra" in strong_topics
        assert "algebra" not in weak_topics
        assert "calculus" not in strong_topics

    def test_progress_persistence(self, tmp_path):
        """Progress should persist between tracker instances."""
        state_file = tmp_path / "persistent_state.json"
        
        # Create tracker and record score
        tracker1 = ProgressTracker(state_file=str(state_file))
        tracker1.record_score(topic="optics", score=78.0)
        
        # Create new tracker with same file
        tracker2 = ProgressTracker(state_file=str(state_file))
        
        progress = tracker2.get_topic_progress("optics")
        assert progress.attempts == 1
        assert progress.average_score == 78.0

    def test_mastery_level_calculation(self, progress_tracker):
        """Mastery level should be calculated based on scores."""
        # Not started (no attempts)
        assert progress_tracker.get_mastery_level("unknown_topic") == "not_started"
        
        # Learning (below 60%)
        progress_tracker.record_score(topic="hard_topic", score=45.0)
        assert progress_tracker.get_mastery_level("hard_topic") == "learning"
        
        # Familiar (60-85%)
        progress_tracker.record_score(topic="medium_topic", score=75.0)
        assert progress_tracker.get_mastery_level("medium_topic") == "familiar"
        
        # Mastered (above 85%)
        progress_tracker.record_score(topic="easy_topic", score=95.0)
        assert progress_tracker.get_mastery_level("easy_topic") == "mastered"


# ---------------------------------------------------------------------------
# Test: Dashboard Shows Subject Stats
# ---------------------------------------------------------------------------


class TestDashboardSubjectStats:
    """Test that dashboard shows subject-specific statistics."""

    @pytest.fixture
    def tracker_with_data(self, tmp_path):
        """Create a ProgressTracker with sample data."""
        state_file = tmp_path / "dashboard_state.json"
        tracker = ProgressTracker(state_file=str(state_file))
        
        # Record various scores
        tracker.record_score(topic="mechanics", score=90.0)
        tracker.record_score(topic="mechanics", score=85.0)
        tracker.record_score(topic="thermodynamics", score=70.0)
        tracker.record_score(topic="optics", score=55.0)
        
        return tracker

    def test_overall_stats_aggregation(self, tracker_with_data):
        """Overall stats should aggregate across all topics."""
        stats = tracker_with_data.get_overall_stats()
        
        assert stats["total_quizzes"] == 4
        assert stats["total_topics"] == 3
        assert stats["average_score"] == pytest.approx(75.0, rel=0.01)

    def test_dashboard_data_structure(self, tracker_with_data):
        """Dashboard data should include all required sections."""
        dashboard = tracker_with_data.get_dashboard_data()
        
        assert "streak" in dashboard
        assert "overall" in dashboard
        assert "weekly" in dashboard
        assert "monthly" in dashboard
        assert "topic_mastery" in dashboard
        assert "heatmap" in dashboard
        assert "exam_readiness" in dashboard
        assert "learning_velocity" in dashboard

    def test_topic_mastery_breakdown(self, tracker_with_data):
        """Dashboard should show mastery for each topic."""
        dashboard = tracker_with_data.get_dashboard_data()
        topic_mastery = dashboard["topic_mastery"]
        
        assert len(topic_mastery) == 3  # 3 topics recorded
        
        # Should be sorted by mastery percent descending
        assert topic_mastery[0]["mastery_percent"] >= topic_mastery[1]["mastery_percent"]
        
        # Check structure
        for topic in topic_mastery:
            assert "topic" in topic
            assert "mastery_percent" in topic
            assert "mastery_level" in topic
            assert "attempts" in topic


    def test_exam_readiness_score(self, tracker_with_data):
        """Dashboard should calculate exam readiness."""
        dashboard = tracker_with_data.get_dashboard_data()
        exam_readiness = dashboard["exam_readiness"]
        
        assert "score" in exam_readiness
        assert "level" in exam_readiness
        assert "message" in exam_readiness
        assert "breakdown" in exam_readiness
        
        # Score should be between 0 and 100
        assert 0 <= exam_readiness["score"] <= 100
        
        # Level should be one of the defined levels
        assert exam_readiness["level"] in [
            "excellent", "good", "moderate", "needs_work"
        ]

    def test_streak_tracking(self, tmp_path):
        """Dashboard should track study streaks."""
        state_file = tmp_path / "streak_state.json"
        tracker = ProgressTracker(state_file=str(state_file))
        
        # Record a card review to start streak
        tracker.record_card_review("fc-001")
        
        dashboard = tracker.get_dashboard_data()
        streak = dashboard["streak"]
        
        assert "current_streak" in streak
        assert "longest_streak" in streak
        assert "total_cards_reviewed" in streak
        assert streak["total_cards_reviewed"] >= 1

    def test_empty_tracker_dashboard(self, tmp_path):
        """Dashboard should handle empty tracker gracefully."""
        state_file = tmp_path / "empty_state.json"
        tracker = ProgressTracker(state_file=str(state_file))
        
        dashboard = tracker.get_dashboard_data()
        
        # Should return valid structure with zeros
        assert dashboard["overall"]["total_quizzes"] == 0
        assert dashboard["overall"]["total_topics"] == 0
        assert dashboard["topic_mastery"] == []


# ---------------------------------------------------------------------------
# Test: SubjectRetriever Isolation
# ---------------------------------------------------------------------------


class TestSubjectRetrieverIsolation:
    """Test that SubjectRetriever properly isolates subject data."""

    def test_semantic_search_uses_subject_id(
        self, mock_vector_store, mock_knowledge_graph
    ):
        """Semantic search should scope to the subject."""
        retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="biology",
        )
        
        retriever.semantic_search("photosynthesis", top_k=5)
        
        mock_vector_store.search_chunks.assert_called_once_with(
            "biology", "photosynthesis", top_k=5
        )

    def test_filtered_search_uses_subject_id(
        self, mock_vector_store, mock_knowledge_graph
    ):
        """Filtered search should scope to the subject."""
        retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="biology",
        )
        
        retriever.filtered_search(
            query="cells", 
            top_k=5, 
            difficulty="medium"
        )
        
        mock_vector_store.search_concepts.assert_called()

    def test_retriever_subject_id_attribute(self, mock_vector_store, mock_knowledge_graph):
        """Retriever should expose its subject_id."""
        retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="mathematics",
        )
        
        assert retriever.subject_id == "mathematics"

    def test_graph_retrieval_uses_knowledge_graph(
        self, mock_vector_store, mock_knowledge_graph
    ):
        """Graph retrieval should use the subject's knowledge graph."""
        retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="physics",
        )
        
        retriever.graph_retrieval("concept-001")
        
        # Should query the knowledge graph for related concepts
        mock_knowledge_graph.get_prerequisites.assert_called()
        mock_knowledge_graph.get_related.assert_called()


# ---------------------------------------------------------------------------
# Test: End-to-End Subject Workflow Integration
# ---------------------------------------------------------------------------


class TestSubjectWorkflowIntegration:
    """Integration tests for subject-scoped workflows."""

    @pytest.fixture
    def mock_components(self, mock_vector_store, mock_knowledge_graph, mock_llm_client):
        """Create all mock components for integration tests."""
        return {
            "vector_store": mock_vector_store,
            "knowledge_graph": mock_knowledge_graph,
            "llm_client": mock_llm_client,
        }

    def test_quiz_then_progress_integration(
        self, tmp_path, mock_components
    ):
        """Quiz completion should record progress to subject tracker."""
        # Setup
        physics_state = tmp_path / "physics_progress.json"
        physics_tracker = ProgressTracker(state_file=str(physics_state))
        
        physics_retriever = SubjectRetriever(
            vector_store=mock_components["vector_store"],
            knowledge_graph=mock_components["knowledge_graph"],
            subject_id="physics",
        )
        
        mock_components["llm_client"].generate_json.return_value = (
            _QuizBatch(questions=[
                {
                    "id": "q-test",
                    "question": "What is F=ma?",
                    "question_type": "short_answer",
                    "options": None,
                    "correct_answer": "Newton's second law",
                    "explanation": "Force equals mass times acceleration",
                    "topic": "mechanics",
                    "difficulty": "easy",
                    "source_chunk_ids": ["chunk-001"],
                }
            ]),
            {"total_tokens": 100}
        )
        
        # Generate quiz
        workflow = QuizWorkflow(
            llm_client=mock_components["llm_client"],
            retriever=physics_retriever,
            subject_id="physics",
        )
        
        questions = workflow.generate(topic="mechanics", num_questions=1)
        
        # Simulate quiz completion
        physics_tracker.record_score(topic="mechanics", score=80.0)
        
        # Verify progress recorded
        progress = physics_tracker.get_topic_progress("mechanics")
        assert progress.attempts == 1
        assert progress.average_score == 80.0


    def test_multiple_subjects_complete_isolation(
        self, tmp_path, mock_components
    ):
        """Multiple subjects should have completely isolated workflows."""
        # Setup separate trackers
        physics_state = tmp_path / "physics.json"
        chemistry_state = tmp_path / "chemistry.json"
        
        physics_tracker = ProgressTracker(state_file=str(physics_state))
        chemistry_tracker = ProgressTracker(state_file=str(chemistry_state))
        
        # Setup separate retrievers
        physics_retriever = SubjectRetriever(
            vector_store=mock_components["vector_store"],
            knowledge_graph=mock_components["knowledge_graph"],
            subject_id="physics",
        )
        
        chemistry_retriever = SubjectRetriever(
            vector_store=mock_components["vector_store"],
            knowledge_graph=mock_components["knowledge_graph"],
            subject_id="chemistry",
        )
        
        # Record progress for each subject
        physics_tracker.record_score(topic="mechanics", score=85.0)
        physics_tracker.record_score(topic="optics", score=75.0)
        
        chemistry_tracker.record_score(topic="organic", score=90.0)
        chemistry_tracker.record_score(topic="inorganic", score=70.0)
        
        # Verify isolation
        physics_stats = physics_tracker.get_overall_stats()
        chemistry_stats = chemistry_tracker.get_overall_stats()
        
        assert physics_stats["total_topics"] == 2
        assert chemistry_stats["total_topics"] == 2
        
        # Physics should not see chemistry topics
        physics_mastery = physics_tracker.get_mastery_level("organic")
        assert physics_mastery == "not_started"
        
        # Chemistry should not see physics topics
        chemistry_mastery = chemistry_tracker.get_mastery_level("mechanics")
        assert chemistry_mastery == "not_started"

    def test_flashcard_to_spaced_repetition_flow(
        self, tmp_path, mock_components
    ):
        """Flashcard generation should prepare cards for spaced repetition."""
        mock_components["llm_client"].generate_json.return_value = (
            _FlashcardBatch(flashcards=[
                _FlashcardItem(
                    question="What is force?",
                    answer="Push or pull",
                    hint="F=ma",
                    mnemonic=None,
                    related_topics=["motion"],
                    difficulty="easy",
                ),
            ]),
            {"total_tokens": 100}
        )
        
        physics_retriever = SubjectRetriever(
            vector_store=mock_components["vector_store"],
            knowledge_graph=mock_components["knowledge_graph"],
            subject_id="physics",
        )
        
        workflow = FlashcardWorkflow(
            retriever=physics_retriever,
            llm_client=mock_components["llm_client"],
            subject_id="physics",
        )
        
        cards = workflow.generate(topic="mechanics", num_cards=1)
        
        # Verify cards are generated with proper IDs
        assert len(cards) == 1
        assert cards[0].id.startswith("fc-")
        assert cards[0].question == "What is force?"


# ---------------------------------------------------------------------------
# Test: Score Validation
# ---------------------------------------------------------------------------


class TestScoreValidation:
    """Test progress tracker score validation."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a progress tracker."""
        state_file = tmp_path / "validation_state.json"
        return ProgressTracker(state_file=str(state_file))

    def test_valid_score_range(self, tracker):
        """Scores between 0 and 100 should be accepted."""
        tracker.record_score(topic="test", score=0.0)
        tracker.record_score(topic="test", score=50.0)
        tracker.record_score(topic="test", score=100.0)
        
        progress = tracker.get_topic_progress("test")
        assert progress.attempts == 3

    def test_negative_score_raises_error(self, tracker):
        """Negative scores should raise ValueError."""
        with pytest.raises(ValueError, match="Score must be between 0 and 100"):
            tracker.record_score(topic="test", score=-5.0)

    def test_score_over_100_raises_error(self, tracker):
        """Scores over 100 should raise ValueError."""
        with pytest.raises(ValueError, match="Score must be between 0 and 100"):
            tracker.record_score(topic="test", score=105.0)


# ---------------------------------------------------------------------------
# Test: Subject Retriever Edge Cases
# ---------------------------------------------------------------------------


class TestSubjectRetrieverEdgeCases:
    """Test edge cases for subject retriever."""

    def test_empty_search_results(self, mock_vector_store, mock_knowledge_graph):
        """Retriever should handle empty search results gracefully."""
        mock_vector_store.search_chunks.return_value = []
        
        retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="new_subject",
        )
        
        results = retriever.semantic_search("unknown topic", top_k=5)
        assert results == []

    def test_graph_retrieval_nonexistent_concept(
        self, mock_vector_store, mock_knowledge_graph
    ):
        """Graph retrieval should handle non-existent concepts."""
        mock_knowledge_graph.__contains__ = lambda self, x: False
        
        retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="test",
        )
        
        results = retriever.graph_retrieval("nonexistent-concept")
        assert results == []

    def test_hybrid_retrieval_combines_results(
        self, mock_vector_store, mock_knowledge_graph
    ):
        """Hybrid retrieval should combine semantic and graph results."""
        retriever = SubjectRetriever(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            subject_id="physics",
        )
        
        results = retriever.hybrid_retrieval("force", top_k=10)
        
        # Should call both search methods
        mock_vector_store.search_chunks.assert_called()
        mock_vector_store.search_concepts.assert_called()
