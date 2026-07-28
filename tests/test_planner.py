"""Tests for the Planner / Intent Router.

Tests rule-based and LLM-based intent classification, parameter extraction,
and workflow routing.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.planner import IntentRouter
from src.planner.router import (
    IntentResult,
    _extract_topic,
    INTENT_KEYWORDS,
    DIFFICULTY_MAP,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_client():
    """Create a mock LLMClient."""
    return MagicMock()


@pytest.fixture
def router(mock_llm_client):
    """Create an IntentRouter with mocked LLM client."""
    return IntentRouter(llm_client=mock_llm_client)


# ---------------------------------------------------------------------------
# Rule-Based Classification Tests
# ---------------------------------------------------------------------------


class TestClassifyIntentRules:
    """Tests for rule-based intent classification."""

    def test_quiz_intent_from_keyword_quiz(self, router):
        result = router.classify_intent_rules("Generate a quiz on photosynthesis")
        assert result["intent"] == "quiz"

    def test_quiz_intent_from_keyword_test(self, router):
        result = router.classify_intent_rules("Give me a test on algebra")
        assert result["intent"] == "quiz"

    def test_quiz_intent_from_keyword_exam(self, router):
        result = router.classify_intent_rules("Create an exam about history")
        assert result["intent"] == "quiz"

    def test_flashcard_intent(self, router):
        result = router.classify_intent_rules("Make flashcards for biology")
        assert result["intent"] == "flashcard"

    def test_flashcard_intent_from_card(self, router):
        result = router.classify_intent_rules("Create memory cards on chemistry")
        assert result["intent"] == "flashcard"

    def test_notes_intent(self, router):
        result = router.classify_intent_rules("Give me revision notes on calculus")
        assert result["intent"] == "notes"

    def test_notes_intent_from_summary(self, router):
        result = router.classify_intent_rules("Summarize the chapter on thermodynamics")
        assert result["intent"] == "notes"

    def test_solution_intent(self, router):
        result = router.classify_intent_rules("Solve this 5 marks question on integration")
        assert result["intent"] == "solution"

    def test_solution_intent_from_marks(self, router):
        result = router.classify_intent_rules("Give me a 10 marks answer on databases")
        assert result["intent"] == "solution"

    def test_mind_map_intent(self, router):
        result = router.classify_intent_rules("Create a mind map of machine learning")
        assert result["intent"] == "mind_map"

    def test_mind_map_intent_from_concept_map(self, router):
        result = router.classify_intent_rules("Show me a concept map for data structures")
        assert result["intent"] == "mind_map"

    def test_additional_info_intent(self, router):
        result = router.classify_intent_rules("What are industry applications of AI?")
        assert result["intent"] == "additional_info"

    def test_additional_info_intent_from_interview(self, router):
        result = router.classify_intent_rules("Give me interview questions on Python")
        assert result["intent"] == "additional_info"

    def test_explain_intent(self, router):
        result = router.classify_intent_rules("Explain photosynthesis")
        assert result["intent"] == "explain"

    def test_explain_intent_from_what_is(self, router):
        result = router.classify_intent_rules("What is machine learning?")
        assert result["intent"] == "explain"

    def test_explain_intent_from_define(self, router):
        result = router.classify_intent_rules("Define osmosis")
        assert result["intent"] == "explain"

    def test_default_chat_intent(self, router):
        result = router.classify_intent_rules("Hello, how are you?")
        assert result["intent"] == "chat"

    def test_ambiguous_defaults_to_chat(self, router):
        result = router.classify_intent_rules("I need help with my homework")
        assert result["intent"] == "chat"


# ---------------------------------------------------------------------------
# Parameter Extraction Tests
# ---------------------------------------------------------------------------


class TestParameterExtraction:
    """Tests for parameter extraction from user input."""

    def test_extracts_difficulty_easy(self, router):
        result = router.classify_intent_rules("Generate easy quiz on physics")
        assert result["parameters"]["difficulty"] == "easy"

    def test_extracts_difficulty_hard(self, router):
        result = router.classify_intent_rules("Make hard flashcards on chemistry")
        assert result["parameters"]["difficulty"] == "hard"

    def test_extracts_difficulty_from_advanced(self, router):
        result = router.classify_intent_rules("Create advanced notes on quantum physics")
        assert result["parameters"]["difficulty"] == "hard"

    def test_extracts_difficulty_from_simple(self, router):
        result = router.classify_intent_rules("Give me simple questions on math")
        assert result["parameters"]["difficulty"] == "easy"

    def test_extracts_count(self, router):
        result = router.classify_intent_rules("Generate 5 questions on biology")
        assert result["parameters"]["count"] == 5

    def test_extracts_count_cards(self, router):
        result = router.classify_intent_rules("Make 10 flashcards on history")
        assert result["parameters"]["count"] == 10

    def test_extracts_marks(self, router):
        result = router.classify_intent_rules("Solve this 5 marks question on derivatives")
        assert result["parameters"]["marks"] == 5

    def test_extracts_marks_hyphenated(self, router):
        result = router.classify_intent_rules("Write a 10-mark answer on osmosis")
        assert result["parameters"]["marks"] == 10

    def test_extracts_topic(self, router):
        result = router.classify_intent_rules("Generate a quiz on photosynthesis")
        assert "photosynthesis" in result["parameters"].get("topic", "").lower()

    def test_extracts_topic_compound(self, router):
        result = router.classify_intent_rules("Make flashcards on machine learning")
        topic = result["parameters"].get("topic", "").lower()
        assert "machine" in topic or "learning" in topic

    def test_no_difficulty_if_not_mentioned(self, router):
        result = router.classify_intent_rules("Generate a quiz on biology")
        assert "difficulty" not in result["parameters"]

    def test_no_count_if_not_mentioned(self, router):
        result = router.classify_intent_rules("Generate a quiz on biology")
        assert "count" not in result["parameters"]

    def test_no_marks_if_not_mentioned(self, router):
        result = router.classify_intent_rules("Make flashcards on history")
        assert "marks" not in result["parameters"]

    def test_multiple_parameters_extracted(self, router):
        result = router.classify_intent_rules(
            "Generate 5 easy questions on photosynthesis"
        )
        assert result["parameters"]["difficulty"] == "easy"
        assert result["parameters"]["count"] == 5
        assert "photosynthesis" in result["parameters"].get("topic", "").lower()


# ---------------------------------------------------------------------------
# LLM-Based Classification Tests
# ---------------------------------------------------------------------------


class TestClassifyIntentLLM:
    """Tests for LLM-based intent classification."""

    def test_llm_classification_returns_result(self, router, mock_llm_client):
        mock_llm_client.generate_json.return_value = (
            IntentResult(intent="quiz", parameters={"topic": "biology", "count": 5}),
            {"provider": "groq", "total_tokens": 100},
        )
        result = router.classify_intent_llm("Help me study biology with some practice")
        assert result["intent"] == "quiz"
        assert result["parameters"]["topic"] == "biology"

    def test_llm_classification_invalid_intent_defaults_to_chat(self, router, mock_llm_client):
        mock_llm_client.generate_json.return_value = (
            IntentResult(intent="unknown_intent", parameters={}),
            {"provider": "groq", "total_tokens": 50},
        )
        result = router.classify_intent_llm("Do something weird")
        assert result["intent"] == "chat"

    def test_llm_classification_raises_on_failure(self, router, mock_llm_client):
        mock_llm_client.generate_json.side_effect = Exception("API error")
        with pytest.raises(Exception, match="API error"):
            router.classify_intent_llm("test input")


# ---------------------------------------------------------------------------
# Combined classify_intent Tests (rule-based + LLM fallback)
# ---------------------------------------------------------------------------


class TestClassifyIntent:
    """Tests for the combined classification strategy."""

    def test_uses_rules_when_clear_keyword(self, router, mock_llm_client):
        result = router.classify_intent("Generate a quiz on photosynthesis")
        assert result["intent"] == "quiz"
        # LLM should not be called if rules detect a clear intent
        mock_llm_client.generate_json.assert_not_called()

    def test_falls_back_to_llm_on_chat_default(self, router, mock_llm_client):
        mock_llm_client.generate_json.return_value = (
            IntentResult(intent="quiz", parameters={"topic": "science"}),
            {"provider": "groq", "total_tokens": 100},
        )
        result = router.classify_intent("I want to practice science")
        assert result["intent"] == "quiz"
        mock_llm_client.generate_json.assert_called_once()

    def test_returns_chat_if_both_give_chat(self, router, mock_llm_client):
        mock_llm_client.generate_json.return_value = (
            IntentResult(intent="chat", parameters={}),
            {"provider": "groq", "total_tokens": 50},
        )
        result = router.classify_intent("Hello there!")
        assert result["intent"] == "chat"

    def test_returns_rules_result_on_llm_failure(self, router, mock_llm_client):
        mock_llm_client.generate_json.side_effect = Exception("timeout")
        result = router.classify_intent("Help me study somehow")
        assert result["intent"] == "chat"  # Fallback to rule-based default


# ---------------------------------------------------------------------------
# Routing Tests
# ---------------------------------------------------------------------------


class TestRoute:
    """Tests for workflow routing."""

    def test_routes_to_quiz_workflow(self, router):
        mock_workflow = MagicMock()
        mock_workflow.generate.return_value = ["question1", "question2"]

        workflows = {"quiz": mock_workflow}
        result = router.route("Generate a quiz on biology", workflows)

        mock_workflow.generate.assert_called_once()
        assert result == ["question1", "question2"]

    def test_routes_explain_to_chat_workflow(self, router):
        mock_chat = MagicMock()
        mock_chat.generate.return_value = "Photosynthesis is..."

        workflows = {"chat": mock_chat}
        result = router.route("Explain photosynthesis", workflows)

        mock_chat.generate.assert_called_once()
        assert result == "Photosynthesis is..."

    def test_routes_with_extracted_parameters(self, router):
        mock_workflow = MagicMock()
        mock_workflow.generate.return_value = []

        workflows = {"quiz": mock_workflow}
        router.route("Generate 5 easy questions on physics", workflows)

        call_kwargs = mock_workflow.generate.call_args[1]
        assert call_kwargs.get("difficulty") == "easy"
        assert call_kwargs.get("num_questions") == 5

    def test_returns_none_for_unregistered_workflow(self, router):
        workflows = {"quiz": MagicMock()}
        result = router.route("Make flashcards on biology", workflows)
        assert result is None

    def test_routes_to_callable_workflow(self, router):
        def my_workflow(topic, **kwargs):
            return f"Generated for {topic}"

        workflows = {"notes": my_workflow}
        result = router.route("Give me notes on calculus", workflows)
        assert "calculus" in result.lower() or "Generated for" in result

    def test_route_passes_marks_parameter(self, router):
        mock_workflow = MagicMock()
        mock_workflow.generate.return_value = "solution"

        workflows = {"solution": mock_workflow}
        router.route("Solve this 5 marks question on derivatives", workflows)

        call_kwargs = mock_workflow.generate.call_args[1]
        assert call_kwargs.get("marks") == 5


# ---------------------------------------------------------------------------
# Topic Extraction Tests
# ---------------------------------------------------------------------------


class TestTopicExtraction:
    """Tests for the _extract_topic helper function."""

    def test_extracts_simple_topic(self):
        topic = _extract_topic("Generate a quiz on photosynthesis")
        assert "photosynthesis" in topic.lower()

    def test_extracts_multi_word_topic(self):
        topic = _extract_topic("Make flashcards on machine learning algorithms")
        assert "machine" in topic.lower() or "learning" in topic.lower()

    def test_strips_count_patterns(self):
        topic = _extract_topic("Generate 5 questions on biology")
        assert "5" not in topic

    def test_returns_empty_for_pure_noise(self):
        topic = _extract_topic("generate create make give me")
        assert topic == ""

    def test_preserves_hyphenated_words(self):
        topic = _extract_topic("Explain object-oriented programming")
        assert "object-oriented" in topic.lower() or "programming" in topic.lower()
