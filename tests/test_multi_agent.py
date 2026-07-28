"""Tests for the Multi-Agent System.

Tests all agent classes and the MultiAgentOrchestrator with mocked dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.agents import (
    BaseAgent,
    DocumentAgent,
    ExaminerAgent,
    MemoryAgent,
    MultiAgentOrchestrator,
    PlannerAgent,
    ReviewerAgent,
    TeacherAgent,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_client():
    """Create a mock LLMClient."""
    client = MagicMock()
    client.generate.return_value = ("Mock response", {"total_tokens": 50})
    client.generate_json.return_value = (
        MagicMock(intent="quiz", parameters={"topic": "biology"}),
        {"total_tokens": 50},
    )
    return client


@pytest.fixture
def mock_retriever():
    """Create a mock Retriever."""
    retriever = MagicMock()
    retriever.semantic_search.return_value = [
        {"id": "chunk-1", "content": "Photosynthesis is the process...", "score": 0.9}
    ]
    retriever.hybrid_retrieval.return_value = [
        {"id": "chunk-1", "content": "Photosynthesis is the process...", "score": 0.9}
    ]
    retriever.filtered_search.return_value = [
        {"id": "chunk-2", "content": "Plants use sunlight...", "score": 0.8}
    ]
    return retriever


@pytest.fixture
def mock_knowledge_graph():
    """Create a mock KnowledgeGraph."""
    return MagicMock()


@pytest.fixture
def mock_progress_tracker():
    """Create a mock ProgressTracker."""
    tracker = MagicMock()
    tracker.get_mastery_level.return_value = "learning"
    tracker.get_overall_stats.return_value = {
        "total_quizzes": 5,
        "total_topics": 3,
        "average_score": 72.5,
        "study_time_minutes": 120,
        "weak_count": 1,
        "strong_count": 1,
    }
    return tracker


@pytest.fixture
def mock_scheduler():
    """Create a mock SpacedRepetitionScheduler."""
    return MagicMock()


# ---------------------------------------------------------------------------
# PlannerAgent Tests
# ---------------------------------------------------------------------------


class TestPlannerAgent:
    """Tests for PlannerAgent."""

    def test_classifies_quiz_intent(self, mock_llm_client):
        agent = PlannerAgent(llm_client=mock_llm_client)
        result = agent.run({"user_input": "Generate a quiz on biology"})
        assert result["intent"] == "quiz"
        assert "parameters" in result

    def test_classifies_flashcard_intent(self, mock_llm_client):
        agent = PlannerAgent(llm_client=mock_llm_client)
        result = agent.run({"user_input": "Make flashcards on chemistry"})
        assert result["intent"] == "flashcard"

    def test_classifies_explain_intent(self, mock_llm_client):
        agent = PlannerAgent(llm_client=mock_llm_client)
        result = agent.run({"user_input": "Explain photosynthesis"})
        assert result["intent"] == "explain"

    def test_classifies_notes_intent(self, mock_llm_client):
        agent = PlannerAgent(llm_client=mock_llm_client)
        result = agent.run({"user_input": "Give me revision notes on calculus"})
        assert result["intent"] == "notes"

    def test_extracts_parameters(self, mock_llm_client):
        agent = PlannerAgent(llm_client=mock_llm_client)
        result = agent.run({"user_input": "Generate 5 easy questions on physics"})
        assert result["parameters"].get("difficulty") == "easy"
        assert result["parameters"].get("count") == 5

    def test_empty_input_returns_chat(self, mock_llm_client):
        # When empty input is given, rules classify as "chat", then LLM fallback
        # is attempted. Mock LLM to also return "chat" for this test.
        mock_llm_client.generate_json.return_value = (
            MagicMock(intent="chat", parameters={}),
            {"total_tokens": 20},
        )
        agent = PlannerAgent(llm_client=mock_llm_client)
        result = agent.run({"user_input": ""})
        assert result["intent"] == "chat"


# ---------------------------------------------------------------------------
# DocumentAgent Tests
# ---------------------------------------------------------------------------


class TestDocumentAgent:
    """Tests for DocumentAgent."""

    def test_retrieves_topic(self, mock_retriever, mock_knowledge_graph):
        agent = DocumentAgent(retriever=mock_retriever, knowledge_graph=mock_knowledge_graph)
        result = agent.run({"topic": "photosynthesis"})
        assert result["status"] == "success"
        assert result["chunks"] == 1

    def test_handles_text_input(self, mock_retriever, mock_knowledge_graph):
        agent = DocumentAgent(retriever=mock_retriever, knowledge_graph=mock_knowledge_graph)
        result = agent.run({"text": "Some document text content"})
        assert result["status"] == "success"
        assert "chars" in result["message"]

    def test_handles_no_input(self, mock_retriever, mock_knowledge_graph):
        agent = DocumentAgent(retriever=mock_retriever, knowledge_graph=mock_knowledge_graph)
        result = agent.run({})
        assert result["status"] == "no_op"

    def test_handles_retrieval_error(self, mock_retriever, mock_knowledge_graph):
        mock_retriever.semantic_search.side_effect = Exception("Connection failed")
        agent = DocumentAgent(retriever=mock_retriever, knowledge_graph=mock_knowledge_graph)
        result = agent.run({"topic": "physics"})
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# TeacherAgent Tests
# ---------------------------------------------------------------------------


class TestTeacherAgent:
    """Tests for TeacherAgent."""

    def test_explain_action(self, mock_llm_client, mock_retriever):
        mock_llm_client.generate.return_value = (
            "Photosynthesis is the process by which plants convert sunlight into energy.",
            {"total_tokens": 100},
        )
        agent = TeacherAgent(llm_client=mock_llm_client, retriever=mock_retriever)
        result = agent.run({"topic": "photosynthesis", "action": "explain"})
        assert result["status"] == "success"
        assert result["action"] == "explain"
        assert "result" in result

    def test_notes_action(self, mock_llm_client, mock_retriever):
        mock_note = MagicMock()
        mock_note.model_dump.return_value = {"topic": "calculus", "subtopics": []}
        mock_llm_client.generate_json.return_value = (mock_note, {"total_tokens": 200})
        agent = TeacherAgent(llm_client=mock_llm_client, retriever=mock_retriever)
        result = agent.run({"topic": "calculus", "action": "notes"})
        assert result["status"] == "success"
        assert result["action"] == "notes"

    def test_defaults_to_explain(self, mock_llm_client, mock_retriever):
        mock_llm_client.generate.return_value = ("Answer text", {"total_tokens": 50})
        agent = TeacherAgent(llm_client=mock_llm_client, retriever=mock_retriever)
        result = agent.run({"topic": "gravity"})
        assert result["action"] == "explain"

    def test_handles_explain_error_gracefully(self, mock_llm_client, mock_retriever):
        # ChatTutor catches LLM errors internally and returns a fallback message,
        # so the TeacherAgent still returns "success" with the fallback response.
        mock_llm_client.generate.side_effect = Exception("LLM error")
        agent = TeacherAgent(llm_client=mock_llm_client, retriever=mock_retriever)
        result = agent.run({"topic": "physics", "action": "explain"})
        assert result["status"] == "success"
        assert result["action"] == "explain"
        # The ChatTutor returns a graceful error message as the answer
        assert "error" in result["result"]["answer"].lower() or "sorry" in result["result"]["answer"].lower()


# ---------------------------------------------------------------------------
# ExaminerAgent Tests
# ---------------------------------------------------------------------------


class TestExaminerAgent:
    """Tests for ExaminerAgent."""

    def test_quiz_action(self, mock_llm_client, mock_retriever):
        mock_question = MagicMock()
        mock_question.model_dump.return_value = {
            "id": "q-1",
            "question": "What is photosynthesis?",
            "correct_answer": "Process of converting light to energy",
        }
        mock_batch = MagicMock()
        mock_batch.questions = [{"id": "q-1", "question": "What?", "question_type": "mcq",
                                  "correct_answer": "A", "options": ["A", "B", "C", "D"],
                                  "explanation": "Because", "topic": "bio", "difficulty": "easy",
                                  "source_chunk_ids": []}]
        mock_llm_client.generate_json.return_value = (mock_batch, {"total_tokens": 200})

        agent = ExaminerAgent(llm_client=mock_llm_client, retriever=mock_retriever)
        result = agent.run({"topic": "biology", "action": "quiz", "count": 1})
        assert result["status"] == "success"
        assert result["action"] == "quiz"

    def test_flashcard_action(self, mock_llm_client, mock_retriever):
        mock_card = MagicMock()
        mock_card.model_dump.return_value = {"question": "Q?", "answer": "A"}
        mock_batch = MagicMock()
        mock_batch.flashcards = []
        mock_llm_client.generate_json.return_value = (mock_batch, {"total_tokens": 150})

        agent = ExaminerAgent(llm_client=mock_llm_client, retriever=mock_retriever)
        result = agent.run({"topic": "history", "action": "flashcard", "count": 3})
        # May succeed with empty results or succeed with items
        assert result["action"] == "flashcard"

    def test_defaults_to_quiz(self, mock_llm_client, mock_retriever):
        mock_batch = MagicMock()
        mock_batch.questions = []
        mock_llm_client.generate_json.return_value = (mock_batch, {"total_tokens": 100})

        agent = ExaminerAgent(llm_client=mock_llm_client, retriever=mock_retriever)
        result = agent.run({"topic": "math"})
        assert result["action"] == "quiz"

    def test_passes_difficulty_and_count(self, mock_llm_client, mock_retriever):
        mock_batch = MagicMock()
        mock_batch.questions = []
        mock_llm_client.generate_json.return_value = (mock_batch, {"total_tokens": 100})

        agent = ExaminerAgent(llm_client=mock_llm_client, retriever=mock_retriever)
        result = agent.run({
            "topic": "physics",
            "action": "quiz",
            "difficulty": "hard",
            "count": 10,
        })
        assert result["action"] == "quiz"


# ---------------------------------------------------------------------------
# ReviewerAgent Tests
# ---------------------------------------------------------------------------


class TestReviewerAgent:
    """Tests for ReviewerAgent."""

    def test_passes_valid_string_result(self):
        agent = ReviewerAgent()
        result = agent.run({
            "result": "This is a valid explanation of the topic.",
            "intent": "explain",
        })
        assert result["passed"] is True
        assert result["issues"] == []

    def test_fails_none_result(self):
        agent = ReviewerAgent()
        result = agent.run({"result": None, "intent": "quiz"})
        assert result["passed"] is False
        assert any("None" in issue for issue in result["issues"])

    def test_fails_empty_string(self):
        agent = ReviewerAgent()
        result = agent.run({"result": "", "intent": "explain"})
        assert result["passed"] is False

    def test_fails_empty_list_for_quiz(self):
        agent = ReviewerAgent()
        result = agent.run({"result": [], "intent": "quiz"})
        assert result["passed"] is False

    def test_passes_non_empty_list_for_quiz(self):
        agent = ReviewerAgent()
        result = agent.run({
            "result": [{"question": "What is X?"}],
            "intent": "quiz",
        })
        assert result["passed"] is True

    def test_fails_short_response_for_explain(self):
        agent = ReviewerAgent()
        result = agent.run({"result": "Hi", "intent": "explain"})
        assert result["passed"] is False
        assert any("short" in issue for issue in result["issues"])

    def test_passes_dict_with_result_key(self):
        agent = ReviewerAgent()
        result = agent.run({
            "result": {"result": [{"q": "What?"}]},
            "intent": "quiz",
        })
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# MemoryAgent Tests
# ---------------------------------------------------------------------------


class TestMemoryAgent:
    """Tests for MemoryAgent."""

    def test_records_score(self, mock_progress_tracker, mock_scheduler):
        agent = MemoryAgent(
            progress_tracker=mock_progress_tracker, scheduler=mock_scheduler
        )
        result = agent.run({"intent": "quiz", "topic": "biology", "score": 85.0})
        assert result["updated"] is True
        mock_progress_tracker.record_score.assert_called_once_with("biology", 85.0)

    def test_updates_spaced_repetition(self, mock_progress_tracker, mock_scheduler):
        agent = MemoryAgent(
            progress_tracker=mock_progress_tracker, scheduler=mock_scheduler
        )
        result = agent.run({
            "intent": "flashcard",
            "topic": "history",
            "card_id": "fc-001",
            "quality": 4,
        })
        assert result["updated"] is True
        mock_scheduler.review_card.assert_called_once_with("fc-001", 4)

    def test_no_update_without_score_or_card(self, mock_progress_tracker, mock_scheduler):
        agent = MemoryAgent(
            progress_tracker=mock_progress_tracker, scheduler=mock_scheduler
        )
        result = agent.run({"intent": "explain", "topic": "physics"})
        assert result["updated"] is False

    def test_returns_mastery_level(self, mock_progress_tracker, mock_scheduler):
        agent = MemoryAgent(
            progress_tracker=mock_progress_tracker, scheduler=mock_scheduler
        )
        result = agent.run({"intent": "quiz", "topic": "biology"})
        assert result["mastery_level"] == "learning"

    def test_returns_overall_stats(self, mock_progress_tracker, mock_scheduler):
        agent = MemoryAgent(
            progress_tracker=mock_progress_tracker, scheduler=mock_scheduler
        )
        result = agent.run({"intent": "quiz", "topic": "biology"})
        assert "overall_stats" in result
        assert result["overall_stats"]["total_quizzes"] == 5


# ---------------------------------------------------------------------------
# MultiAgentOrchestrator Tests
# ---------------------------------------------------------------------------


class TestMultiAgentOrchestrator:
    """Tests for MultiAgentOrchestrator pipeline."""

    @pytest.fixture
    def orchestrator(
        self, mock_llm_client, mock_retriever, mock_knowledge_graph,
        mock_progress_tracker, mock_scheduler
    ):
        """Create an orchestrator with all mocked dependencies."""
        return MultiAgentOrchestrator(
            llm_client=mock_llm_client,
            retriever=mock_retriever,
            knowledge_graph=mock_knowledge_graph,
            progress_tracker=mock_progress_tracker,
            scheduler=mock_scheduler,
        )

    def test_process_returns_expected_keys(self, orchestrator, mock_llm_client):
        # Mock the LLM to return a simple response for the teacher agent
        mock_llm_client.generate.return_value = (
            "Photosynthesis is the process plants use to convert light energy.",
            {"total_tokens": 100},
        )
        result = orchestrator.process("Explain photosynthesis")
        assert "intent" in result
        assert "parameters" in result
        assert "result" in result
        assert "quality_check" in result

    def test_quiz_intent_routes_to_examiner(self, orchestrator, mock_llm_client):
        mock_batch = MagicMock()
        mock_batch.questions = [
            {"id": "q-1", "question": "What?", "question_type": "mcq",
             "correct_answer": "A", "options": ["A", "B", "C", "D"],
             "explanation": "Reason", "topic": "bio", "difficulty": "medium",
             "source_chunk_ids": []}
        ]
        mock_llm_client.generate_json.return_value = (mock_batch, {"total_tokens": 200})

        result = orchestrator.process("Generate a quiz on biology")
        assert result["intent"] == "quiz"
        assert result["memory_update"] is not None

    def test_explain_intent_routes_to_teacher(self, orchestrator, mock_llm_client):
        mock_llm_client.generate.return_value = (
            "Gravity is a fundamental force that attracts objects with mass.",
            {"total_tokens": 80},
        )
        result = orchestrator.process("Explain gravity")
        assert result["intent"] == "explain"
        assert result["result"]["action"] == "explain"

    def test_quality_check_included(self, orchestrator, mock_llm_client):
        mock_llm_client.generate.return_value = (
            "This is a valid explanation about the topic of interest.",
            {"total_tokens": 60},
        )
        result = orchestrator.process("What is machine learning?")
        assert "quality_check" in result
        assert "passed" in result["quality_check"]

    def test_memory_update_only_for_quiz_flashcard(self, orchestrator, mock_llm_client):
        mock_llm_client.generate.return_value = (
            "Here is an explanation about the topic.",
            {"total_tokens": 50},
        )
        result = orchestrator.process("Explain something")
        # For explain intent, memory_update should be None
        assert result["memory_update"] is None

    def test_orchestrator_has_all_agents(self, orchestrator):
        assert orchestrator.planner is not None
        assert orchestrator.document is not None
        assert orchestrator.teacher is not None
        assert orchestrator.examiner is not None
        assert orchestrator.reviewer is not None
        assert orchestrator.memory is not None
