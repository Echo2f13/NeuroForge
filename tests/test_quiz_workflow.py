"""Tests for the Quiz Generation Workflow.

Tests the QuizWorkflow pipeline (retrieve → generate → validate → format)
with mocked LLM and Retriever dependencies.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from models.knowledge import Difficulty
from models.output import QuizQuestion
from src.workflows.quiz import QuizWorkflow, _QuizBatch, DEFAULT_QUESTION_TYPES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_retriever():
    """Create a mock Retriever that returns sample chunks."""
    retriever = MagicMock()
    retriever.semantic_search.return_value = [
        {
            "id": "chunk-001",
            "content": "Photosynthesis is the process by which plants convert sunlight into energy.",
            "score": 0.95,
            "metadata": {"topic": "biology"},
        },
        {
            "id": "chunk-002",
            "content": "Chlorophyll is the green pigment that absorbs light energy.",
            "score": 0.88,
            "metadata": {"topic": "biology"},
        },
    ]
    retriever.filtered_search.return_value = [
        {
            "id": "chunk-003",
            "content": "The light reactions occur in the thylakoid membrane.",
            "score": 0.90,
            "metadata": {"topic": "biology", "difficulty": "medium"},
        },
    ]
    return retriever


@pytest.fixture
def sample_llm_response():
    """Sample valid LLM response with mixed question types."""
    return {
        "questions": [
            {
                "id": "q-001",
                "question": "What is the primary purpose of photosynthesis?",
                "question_type": "mcq",
                "options": [
                    "Convert sunlight to energy",
                    "Break down glucose",
                    "Absorb water from soil",
                    "Release carbon dioxide",
                ],
                "correct_answer": "Convert sunlight to energy",
                "explanation": "Photosynthesis converts sunlight into chemical energy (glucose).",
                "topic": "biology",
                "difficulty": "easy",
                "source_chunk_ids": ["chunk-001"],
            },
            {
                "id": "q-002",
                "question": "Chlorophyll absorbs light energy for photosynthesis.",
                "question_type": "true_false",
                "options": None,
                "correct_answer": "True",
                "explanation": "Chlorophyll is the green pigment responsible for absorbing light.",
                "topic": "biology",
                "difficulty": "easy",
                "source_chunk_ids": ["chunk-002"],
            },
            {
                "id": "q-003",
                "question": "What pigment gives plants their green color?",
                "question_type": "short_answer",
                "options": None,
                "correct_answer": "Chlorophyll",
                "explanation": "Chlorophyll is the green pigment found in chloroplasts.",
                "topic": "biology",
                "difficulty": "easy",
                "source_chunk_ids": ["chunk-002"],
            },
        ]
    }


@pytest.fixture
def mock_llm_client(sample_llm_response):
    """Create a mock LLMClient that returns sample questions."""
    client = MagicMock()
    batch = _QuizBatch(questions=sample_llm_response["questions"])
    client.generate_json.return_value = (batch, {"provider": "groq", "total_tokens": 500})
    return client


@pytest.fixture
def workflow(mock_llm_client, mock_retriever):
    """Create a QuizWorkflow with mocked dependencies."""
    return QuizWorkflow(llm_client=mock_llm_client, retriever=mock_retriever)


# ---------------------------------------------------------------------------
# QuizWorkflow Initialization Tests
# ---------------------------------------------------------------------------


class TestQuizWorkflowInit:
    def test_init_stores_dependencies(self, mock_llm_client, mock_retriever):
        wf = QuizWorkflow(llm_client=mock_llm_client, retriever=mock_retriever)
        assert wf.llm_client is mock_llm_client
        assert wf.retriever is mock_retriever


# ---------------------------------------------------------------------------
# Generate - Full Pipeline Tests
# ---------------------------------------------------------------------------


class TestQuizWorkflowGenerate:
    def test_generate_returns_quiz_questions(self, workflow):
        result = workflow.generate(topic="biology", num_questions=3)
        assert len(result) == 3
        assert all(isinstance(q, QuizQuestion) for q in result)

    def test_generate_respects_num_questions(self, workflow):
        result = workflow.generate(topic="biology", num_questions=2)
        assert len(result) == 2

    def test_generate_with_difficulty_filter(self, workflow, mock_retriever):
        workflow.generate(topic="biology", difficulty="medium", num_questions=3)
        mock_retriever.filtered_search.assert_called_once_with(
            query="biology", top_k=10, topic="biology", difficulty="medium"
        )

    def test_generate_without_difficulty_uses_semantic_search(self, workflow, mock_retriever):
        workflow.generate(topic="biology", num_questions=3)
        mock_retriever.semantic_search.assert_called_once_with(query="biology", top_k=10)

    def test_generate_with_specific_question_types(self, workflow, mock_llm_client):
        workflow.generate(topic="biology", question_types=["mcq"], num_questions=3)
        # Check prompt contains mcq type instruction
        call_args = mock_llm_client.generate_json.call_args
        prompt = call_args.kwargs.get("prompt") or call_args[1].get("prompt")
        assert "mcq" in prompt

    def test_generate_invalid_question_type_raises(self, workflow):
        with pytest.raises(ValueError, match="Invalid question type 'essay'"):
            workflow.generate(topic="biology", question_types=["essay"])

    def test_generate_invalid_difficulty_raises(self, workflow):
        with pytest.raises(ValueError):
            workflow.generate(topic="biology", difficulty="expert")

    def test_generate_uses_default_types(self, workflow):
        workflow.generate(topic="biology", num_questions=3)
        call_args = workflow.llm_client.generate_json.call_args
        prompt = call_args.kwargs.get("prompt") or call_args[1].get("prompt")
        # Default includes all three types
        assert "mcq" in prompt
        assert "short_answer" in prompt
        assert "true_false" in prompt


# ---------------------------------------------------------------------------
# Retrieval Stage Tests
# ---------------------------------------------------------------------------


class TestRetrievalStage:
    def test_retrieve_with_topic_only(self, workflow, mock_retriever):
        chunks = workflow._retrieve("photosynthesis", None)
        mock_retriever.semantic_search.assert_called_once_with(
            query="photosynthesis", top_k=10
        )
        assert len(chunks) == 2

    def test_retrieve_with_difficulty(self, workflow, mock_retriever):
        chunks = workflow._retrieve("photosynthesis", "medium")
        mock_retriever.filtered_search.assert_called_once()
        assert len(chunks) == 1

    def test_retrieve_handles_exception(self, workflow, mock_retriever):
        mock_retriever.semantic_search.side_effect = Exception("DB error")
        chunks = workflow._retrieve("biology", None)
        assert chunks == []


# ---------------------------------------------------------------------------
# Validation Stage Tests
# ---------------------------------------------------------------------------


class TestValidationStage:
    def test_validate_valid_questions(self, workflow):
        raw = [
            {
                "id": "q-001",
                "question": "What is 2+2?",
                "question_type": "short_answer",
                "options": None,
                "correct_answer": "4",
                "explanation": "Basic arithmetic.",
                "topic": "math",
                "difficulty": "easy",
                "source_chunk_ids": [],
            }
        ]
        result = workflow._validate(raw, "math", "easy")
        assert len(result) == 1
        assert result[0].question == "What is 2+2?"

    def test_validate_adds_missing_id(self, workflow):
        raw = [
            {
                "question": "What is 2+2?",
                "question_type": "short_answer",
                "options": None,
                "correct_answer": "4",
                "explanation": "Basic arithmetic.",
                "topic": "math",
                "difficulty": "easy",
                "source_chunk_ids": [],
            }
        ]
        result = workflow._validate(raw, "math", "easy")
        assert len(result) == 1
        assert result[0].id.startswith("q-")

    def test_validate_adds_missing_topic(self, workflow):
        raw = [
            {
                "id": "q-001",
                "question": "What is DNA?",
                "question_type": "short_answer",
                "options": None,
                "correct_answer": "Deoxyribonucleic acid",
                "explanation": "DNA stores genetic info.",
                "difficulty": "easy",
                "source_chunk_ids": [],
            }
        ]
        result = workflow._validate(raw, "biology", None)
        assert result[0].topic == "biology"

    def test_validate_adds_missing_difficulty(self, workflow):
        raw = [
            {
                "id": "q-001",
                "question": "What is DNA?",
                "question_type": "short_answer",
                "options": None,
                "correct_answer": "Deoxyribonucleic acid",
                "explanation": "DNA stores genetic info.",
                "topic": "biology",
                "source_chunk_ids": [],
            }
        ]
        result = workflow._validate(raw, "biology", "hard")
        assert result[0].difficulty == Difficulty.HARD

    def test_validate_skips_invalid_mcq_without_4_options(self, workflow):
        raw = [
            {
                "id": "q-001",
                "question": "Which is correct?",
                "question_type": "mcq",
                "options": ["A", "B"],  # Only 2 options — invalid
                "correct_answer": "A",
                "explanation": "A is correct.",
                "topic": "math",
                "difficulty": "easy",
                "source_chunk_ids": [],
            }
        ]
        result = workflow._validate(raw, "math", "easy")
        assert len(result) == 0  # Invalid MCQ should be skipped

    def test_validate_skips_invalid_question_type(self, workflow):
        raw = [
            {
                "id": "q-001",
                "question": "Write an essay.",
                "question_type": "essay",  # Invalid type
                "options": None,
                "correct_answer": "Anything",
                "explanation": "Open ended.",
                "topic": "english",
                "difficulty": "hard",
                "source_chunk_ids": [],
            }
        ]
        result = workflow._validate(raw, "english", "hard")
        assert len(result) == 0


# ---------------------------------------------------------------------------
# MCQ Validation Tests
# ---------------------------------------------------------------------------


class TestMCQValidation:
    def test_valid_mcq_with_4_options(self, workflow):
        raw = [
            {
                "id": "q-mcq",
                "question": "What color is the sky?",
                "question_type": "mcq",
                "options": ["Blue", "Red", "Green", "Yellow"],
                "correct_answer": "Blue",
                "explanation": "The sky appears blue due to Rayleigh scattering.",
                "topic": "physics",
                "difficulty": "easy",
                "source_chunk_ids": [],
            }
        ]
        result = workflow._validate(raw, "physics", "easy")
        assert len(result) == 1
        assert result[0].options == ["Blue", "Red", "Green", "Yellow"]

    def test_mcq_with_no_options_is_invalid(self, workflow):
        raw = [
            {
                "id": "q-mcq",
                "question": "What color is the sky?",
                "question_type": "mcq",
                "options": None,
                "correct_answer": "Blue",
                "explanation": "Rayleigh scattering.",
                "topic": "physics",
                "difficulty": "easy",
                "source_chunk_ids": [],
            }
        ]
        result = workflow._validate(raw, "physics", "easy")
        assert len(result) == 0

    def test_mcq_with_5_options_is_invalid(self, workflow):
        raw = [
            {
                "id": "q-mcq",
                "question": "Pick one:",
                "question_type": "mcq",
                "options": ["A", "B", "C", "D", "E"],
                "correct_answer": "A",
                "explanation": "A is correct.",
                "topic": "general",
                "difficulty": "medium",
                "source_chunk_ids": [],
            }
        ]
        result = workflow._validate(raw, "general", "medium")
        assert len(result) == 0


# ---------------------------------------------------------------------------
# LLM Generation Failure Tests
# ---------------------------------------------------------------------------


class TestGenerationFailure:
    def test_llm_failure_returns_empty_list(self, workflow, mock_llm_client):
        mock_llm_client.generate_json.side_effect = Exception("API error")
        result = workflow.generate(topic="biology", num_questions=5)
        assert result == []

    def test_retrieval_failure_still_generates(self, workflow, mock_retriever):
        mock_retriever.semantic_search.side_effect = Exception("DB down")
        # Should still call LLM with empty context
        result = workflow.generate(topic="biology", num_questions=3)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Prompt Building Tests
# ---------------------------------------------------------------------------


class TestPromptBuilding:
    def test_prompt_includes_topic(self):
        prompt = QuizWorkflow._build_prompt(
            topic="machine learning",
            difficulty=None,
            num_questions=5,
            question_types=["mcq"],
            chunks=[],
        )
        assert "machine learning" in prompt

    def test_prompt_includes_difficulty(self):
        prompt = QuizWorkflow._build_prompt(
            topic="physics",
            difficulty="hard",
            num_questions=3,
            question_types=["mcq", "true_false"],
            chunks=[],
        )
        assert "hard" in prompt

    def test_prompt_includes_chunk_content(self):
        chunks = [
            {"id": "c1", "content": "Mitosis is cell division.", "score": 0.9, "metadata": {}},
        ]
        prompt = QuizWorkflow._build_prompt(
            topic="biology",
            difficulty=None,
            num_questions=2,
            question_types=["short_answer"],
            chunks=chunks,
        )
        assert "Mitosis is cell division." in prompt

    def test_prompt_with_no_chunks_uses_general_knowledge(self):
        prompt = QuizWorkflow._build_prompt(
            topic="history",
            difficulty=None,
            num_questions=5,
            question_types=["mcq"],
            chunks=[],
        )
        assert "General knowledge about: history" in prompt

    def test_prompt_requests_correct_num_questions(self):
        prompt = QuizWorkflow._build_prompt(
            topic="chemistry",
            difficulty="medium",
            num_questions=7,
            question_types=["mcq", "short_answer", "true_false"],
            chunks=[],
        )
        assert "7" in prompt
