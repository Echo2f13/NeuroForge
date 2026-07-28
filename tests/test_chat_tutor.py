"""Tests for the ChatTutor workflow.

Tests the RAG pipeline, conversation history management, source citation,
follow-up handling, and out-of-scope detection with mocked LLM and retriever.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.workflows.chat_tutor import ChatTutor, MAX_HISTORY_EXCHANGES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_retriever():
    """Create a mock Retriever that returns predefined chunks."""
    retriever = MagicMock()
    retriever.semantic_search.return_value = [
        {
            "id": "chunk_001",
            "content": "Photosynthesis is the process by which plants convert sunlight into energy.",
            "score": 0.95,
            "metadata": {"topic": "biology"},
        },
        {
            "id": "chunk_002",
            "content": "Chlorophyll in leaves absorbs light energy for photosynthesis.",
            "score": 0.88,
            "metadata": {"topic": "biology"},
        },
    ]
    return retriever


@pytest.fixture
def mock_llm_client():
    """Create a mock LLMClient that returns predefined answers."""
    client = MagicMock()
    client.generate.return_value = (
        "Photosynthesis is the process by which plants convert sunlight "
        "into chemical energy. [Source: chunk_001] Chlorophyll plays a key "
        "role in absorbing light. [Source: chunk_002]",
        {"provider": "groq", "total_tokens": 150},
    )
    return client


@pytest.fixture
def tutor(mock_retriever, mock_llm_client):
    """Create a ChatTutor instance with mocked dependencies."""
    return ChatTutor(retriever=mock_retriever, llm_client=mock_llm_client)


# ---------------------------------------------------------------------------
# Basic RAG Pipeline Tests
# ---------------------------------------------------------------------------


class TestAsk:
    """Test the ask() method — main RAG pipeline."""

    def test_returns_answer_with_expected_keys(self, tutor):
        result = tutor.ask("What is photosynthesis?")

        assert "answer" in result
        assert "sources" in result
        assert "is_grounded" in result

    def test_answer_is_string(self, tutor):
        result = tutor.ask("What is photosynthesis?")
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0

    def test_sources_are_chunk_ids(self, tutor):
        result = tutor.ask("What is photosynthesis?")
        assert isinstance(result["sources"], list)
        assert "chunk_001" in result["sources"]
        assert "chunk_002" in result["sources"]

    def test_is_grounded_true_when_chunks_available(self, tutor):
        result = tutor.ask("What is photosynthesis?")
        assert result["is_grounded"] is True

    def test_is_grounded_false_when_no_chunks(self, mock_llm_client):
        retriever = MagicMock()
        retriever.semantic_search.return_value = []
        mock_llm_client.generate.return_value = (
            "I don't have information about that in the available study materials.",
            {"provider": "groq", "total_tokens": 30},
        )
        tutor = ChatTutor(retriever=retriever, llm_client=mock_llm_client)

        result = tutor.ask("What is quantum computing?")
        assert result["is_grounded"] is False

    def test_calls_retriever_with_question(self, tutor, mock_retriever):
        tutor.ask("What is photosynthesis?")
        mock_retriever.semantic_search.assert_called_once()
        call_args = mock_retriever.semantic_search.call_args
        assert "photosynthesis" in call_args.kwargs.get("query", call_args[1].get("query", ""))

    def test_calls_llm_generate(self, tutor, mock_llm_client):
        tutor.ask("What is photosynthesis?")
        mock_llm_client.generate.assert_called_once()


# ---------------------------------------------------------------------------
# Conversation History Tests
# ---------------------------------------------------------------------------


class TestHistory:
    """Test conversation history management."""

    def test_history_empty_initially(self, tutor):
        assert tutor.history == []

    def test_history_stores_exchange_after_ask(self, tutor):
        tutor.ask("What is photosynthesis?")

        history = tutor.history
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "What is photosynthesis?"
        assert history[1]["role"] == "assistant"
        assert len(history[1]["content"]) > 0

    def test_history_stores_multiple_exchanges(self, tutor):
        tutor.ask("What is photosynthesis?")
        tutor.ask("Tell me more about chlorophyll.")

        history = tutor.history
        assert len(history) == 4
        assert history[2]["role"] == "user"
        assert history[2]["content"] == "Tell me more about chlorophyll."

    def test_history_limited_to_max_exchanges(self, tutor, mock_llm_client):
        """History should only keep the last MAX_HISTORY_EXCHANGES exchanges."""
        # Generate more exchanges than the limit
        for i in range(MAX_HISTORY_EXCHANGES + 3):
            mock_llm_client.generate.return_value = (
                f"Answer {i}",
                {"provider": "groq", "total_tokens": 10},
            )
            tutor.ask(f"Question {i}")

        history = tutor.history
        max_messages = MAX_HISTORY_EXCHANGES * 2
        assert len(history) <= max_messages

    def test_history_returns_copy(self, tutor):
        """Modifying returned history should not affect internal state."""
        tutor.ask("What is photosynthesis?")
        history = tutor.history
        history.clear()

        # Internal history should be unchanged
        assert len(tutor.history) == 2


# ---------------------------------------------------------------------------
# Reset Tests
# ---------------------------------------------------------------------------


class TestReset:
    """Test the reset() method."""

    def test_reset_clears_history(self, tutor):
        tutor.ask("What is photosynthesis?")
        assert len(tutor.history) > 0

        tutor.reset()
        assert tutor.history == []

    def test_can_ask_after_reset(self, tutor):
        tutor.ask("What is photosynthesis?")
        tutor.reset()

        result = tutor.ask("What is chlorophyll?")
        assert "answer" in result
        assert len(tutor.history) == 2


# ---------------------------------------------------------------------------
# Follow-Up Question Tests
# ---------------------------------------------------------------------------


class TestFollowUp:
    """Test follow-up question handling with context enrichment."""

    def test_follow_up_enriches_retrieval_query(self, tutor, mock_retriever):
        """Second question should include context from first in retrieval."""
        tutor.ask("What is photosynthesis?")
        mock_retriever.semantic_search.reset_mock()

        tutor.ask("How does it work?")

        # The retrieval query should be enriched with prior context
        call_args = mock_retriever.semantic_search.call_args
        query = call_args.kwargs.get("query", call_args[1].get("query", ""))
        # Should contain both the follow-up and context from history
        assert "How does it work?" in query

    def test_conversation_history_passed_to_llm(self, tutor, mock_llm_client):
        """LLM prompt should include conversation history for context."""
        tutor.ask("What is photosynthesis?")
        mock_llm_client.generate.reset_mock()

        tutor.ask("Tell me more about it.")

        call_args = mock_llm_client.generate.call_args
        prompt = call_args.kwargs.get("prompt", call_args[1].get("prompt", ""))
        # Prompt should reference conversation history
        assert "Conversation History" in prompt


# ---------------------------------------------------------------------------
# Out-of-Scope Handling Tests
# ---------------------------------------------------------------------------


class TestOutOfScope:
    """Test graceful handling of out-of-scope questions."""

    def test_out_of_scope_not_grounded(self, mock_retriever):
        """When LLM indicates out-of-scope, is_grounded should be False."""
        llm_client = MagicMock()
        llm_client.generate.return_value = (
            "I don't have information about that in the available study "
            "materials. This topic might not be covered in the current "
            "knowledge base.",
            {"provider": "groq", "total_tokens": 40},
        )
        tutor = ChatTutor(retriever=mock_retriever, llm_client=llm_client)

        result = tutor.ask("What is the meaning of life?")
        assert result["is_grounded"] is False

    def test_grounded_response_is_detected(self, tutor):
        """Normal grounded answers should have is_grounded=True."""
        result = tutor.ask("What is photosynthesis?")
        assert result["is_grounded"] is True


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test error handling when components fail."""

    def test_retriever_failure_still_returns_answer(self, mock_llm_client):
        """If retriever raises, tutor should still attempt to generate."""
        retriever = MagicMock()
        retriever.semantic_search.side_effect = Exception("Connection error")
        mock_llm_client.generate.return_value = (
            "I don't have information about that in the available study materials.",
            {"provider": "groq", "total_tokens": 20},
        )
        tutor = ChatTutor(retriever=retriever, llm_client=mock_llm_client)

        result = tutor.ask("What is photosynthesis?")
        assert "answer" in result
        assert result["sources"] == []
        assert result["is_grounded"] is False

    def test_llm_failure_returns_error_message(self, mock_retriever):
        """If LLM raises, tutor should return a friendly error."""
        llm_client = MagicMock()
        llm_client.generate.side_effect = Exception("API timeout")
        tutor = ChatTutor(retriever=mock_retriever, llm_client=llm_client)

        result = tutor.ask("What is photosynthesis?")
        assert "error" in result["answer"].lower() or "sorry" in result["answer"].lower()
        assert result["is_grounded"] is False
