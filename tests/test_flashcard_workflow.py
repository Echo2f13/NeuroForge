"""Tests for the Flashcard Generation Workflow.

Tests the FlashcardWorkflow pipeline (retrieve → generate → format)
with mocked LLM and Retriever dependencies.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from models.knowledge import Difficulty
from models.output import Flashcard
from src.workflows.flashcards import (
    FLASHCARD_SYSTEM_PROMPT,
    FlashcardWorkflow,
    _FlashcardBatch,
    _FlashcardItem,
)


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
            "content": "Photosynthesis is the process by which plants convert light energy into chemical energy.",
            "score": 0.95,
            "metadata": {"topic": "biology"},
        },
        {
            "id": "chunk-002",
            "content": "Chlorophyll absorbs light primarily in the blue and red wavelengths.",
            "score": 0.88,
            "metadata": {"topic": "biology"},
        },
        {
            "id": "chunk-003",
            "content": "The Calvin cycle fixes carbon dioxide into glucose molecules.",
            "score": 0.82,
            "metadata": {"topic": "biology"},
        },
    ]
    retriever.filtered_search.return_value = [
        {
            "id": "chunk-001",
            "content": "Photosynthesis converts light to chemical energy in plants.",
            "score": 0.90,
            "metadata": {"topic": "biology", "difficulty": "easy"},
        },
    ]
    return retriever


@pytest.fixture
def mock_llm_client():
    """Create a mock LLMClient that returns structured flashcard JSON."""
    client = MagicMock()

    # Default response: a batch of 3 flashcards
    batch = _FlashcardBatch(
        flashcards=[
            _FlashcardItem(
                question="What is photosynthesis?",
                answer="Light to chemical energy conversion",
                hint="Think about what plants do with sunlight",
                mnemonic="Photo (light) + Synthesis (making)",
                related_topics=["chlorophyll", "Calvin cycle"],
                difficulty="easy",
            ),
            _FlashcardItem(
                question="What pigment absorbs light in plants?",
                answer="Chlorophyll",
                hint="It's what makes plants green",
                mnemonic=None,
                related_topics=["photosynthesis", "light reactions"],
                difficulty="medium",
            ),
            _FlashcardItem(
                question="What does the Calvin cycle produce?",
                answer="Glucose",
                hint="Think of the final sugar product",
                mnemonic="Calvin Cooks Glucose",
                related_topics=["carbon fixation", "photosynthesis"],
                difficulty="hard",
            ),
        ]
    )

    client.generate_json.return_value = (batch, {"provider": "groq", "total_tokens": 200})
    return client


@pytest.fixture
def workflow(mock_retriever, mock_llm_client):
    """Create a FlashcardWorkflow with mocked dependencies."""
    return FlashcardWorkflow(retriever=mock_retriever, llm_client=mock_llm_client)


# ---------------------------------------------------------------------------
# Pipeline Integration Tests
# ---------------------------------------------------------------------------


class TestFlashcardWorkflowGenerate:
    """Test the full generate() pipeline."""

    def test_generate_returns_flashcard_list(self, workflow):
        """Generate returns a list of Flashcard model instances."""
        cards = workflow.generate(topic="photosynthesis", num_cards=3)
        assert isinstance(cards, list)
        assert all(isinstance(card, Flashcard) for card in cards)

    def test_generate_correct_count(self, workflow):
        """Generate returns the expected number of cards."""
        cards = workflow.generate(topic="photosynthesis", num_cards=3)
        assert len(cards) == 3

    def test_generate_card_fields_populated(self, workflow):
        """Each generated card has all required fields populated."""
        cards = workflow.generate(topic="photosynthesis", num_cards=3)
        for card in cards:
            assert card.id.startswith("fc-")
            assert len(card.id) > 3
            assert card.question
            assert card.answer
            assert card.difficulty in list(Difficulty)
            assert isinstance(card.related_topics, list)
            assert isinstance(card.source_chunk_ids, list)

    def test_generate_concise_answers(self, workflow):
        """Answers should be concise (1-10 words)."""
        cards = workflow.generate(topic="photosynthesis", num_cards=3)
        for card in cards:
            word_count = len(card.answer.split())
            assert 1 <= word_count <= 10, (
                f"Answer '{card.answer}' has {word_count} words, expected 1-10"
            )

    def test_generate_uses_semantic_search_without_difficulty(
        self, workflow, mock_retriever
    ):
        """Without difficulty filter, uses semantic_search."""
        workflow.generate(topic="photosynthesis", num_cards=3)
        mock_retriever.semantic_search.assert_called_once_with(
            query="photosynthesis", top_k=10
        )
        mock_retriever.filtered_search.assert_not_called()

    def test_generate_uses_filtered_search_with_difficulty(
        self, workflow, mock_retriever
    ):
        """With difficulty filter, uses filtered_search."""
        workflow.generate(topic="photosynthesis", difficulty="easy", num_cards=3)
        mock_retriever.filtered_search.assert_called_once_with(
            query="photosynthesis", top_k=10, difficulty="easy"
        )
        mock_retriever.semantic_search.assert_not_called()

    def test_generate_calls_llm_with_correct_model(
        self, workflow, mock_llm_client
    ):
        """LLM is called with _FlashcardBatch as response model."""
        workflow.generate(topic="photosynthesis", num_cards=3)
        call_kwargs = mock_llm_client.generate_json.call_args[1]
        assert call_kwargs["response_model"] is _FlashcardBatch
        assert call_kwargs["system_prompt"] == FLASHCARD_SYSTEM_PROMPT

    def test_generate_passes_topic_in_prompt(self, workflow, mock_llm_client):
        """The topic appears in the LLM prompt."""
        workflow.generate(topic="mitosis", num_cards=5)
        call_kwargs = mock_llm_client.generate_json.call_args[1]
        assert "mitosis" in call_kwargs["prompt"]

    def test_generate_includes_source_chunk_ids(self, workflow):
        """Generated cards reference the source chunks used."""
        cards = workflow.generate(topic="photosynthesis", num_cards=3)
        for card in cards:
            assert "chunk-001" in card.source_chunk_ids
            assert "chunk-002" in card.source_chunk_ids
            assert "chunk-003" in card.source_chunk_ids


# ---------------------------------------------------------------------------
# Retrieve Step Tests
# ---------------------------------------------------------------------------


class TestRetrieveStep:
    """Test the _retrieve step in isolation."""

    def test_retrieve_no_filter(self, workflow, mock_retriever):
        """Retrieve without difficulty uses semantic_search."""
        results = workflow._retrieve("biology")
        assert len(results) == 3
        mock_retriever.semantic_search.assert_called_once()

    def test_retrieve_with_difficulty_filter(self, workflow, mock_retriever):
        """Retrieve with difficulty uses filtered_search."""
        results = workflow._retrieve("biology", difficulty="easy")
        assert len(results) == 1
        mock_retriever.filtered_search.assert_called_once()


# ---------------------------------------------------------------------------
# Format Step Tests
# ---------------------------------------------------------------------------


class TestFormatStep:
    """Test the _format step in isolation."""

    def test_format_assigns_unique_ids(self, workflow):
        """Each card gets a unique ID."""
        raw_cards = [
            _FlashcardItem(
                question="Q1?", answer="A1", difficulty="easy",
                related_topics=[], hint=None, mnemonic=None,
            ),
            _FlashcardItem(
                question="Q2?", answer="A2", difficulty="medium",
                related_topics=[], hint=None, mnemonic=None,
            ),
        ]
        chunks = [{"id": "c1"}, {"id": "c2"}]
        result = workflow._format(raw_cards, chunks)
        ids = [card.id for card in result]
        assert len(set(ids)) == 2  # All unique

    def test_format_maps_difficulty_enum(self, workflow):
        """Difficulty strings are mapped to Difficulty enum values."""
        raw_cards = [
            _FlashcardItem(
                question="Q?", answer="A", difficulty="hard",
                related_topics=[], hint=None, mnemonic=None,
            ),
        ]
        result = workflow._format(raw_cards, [{"id": "c1"}])
        assert result[0].difficulty == Difficulty.HARD

    def test_format_handles_invalid_difficulty(self, workflow):
        """Invalid difficulty defaults to MEDIUM."""
        raw_cards = [
            _FlashcardItem(
                question="Q?", answer="A", difficulty="expert",
                related_topics=[], hint=None, mnemonic=None,
            ),
        ]
        result = workflow._format(raw_cards, [{"id": "c1"}])
        assert result[0].difficulty == Difficulty.MEDIUM

    def test_format_preserves_hints_and_mnemonics(self, workflow):
        """Hints and mnemonics from LLM are preserved in output."""
        raw_cards = [
            _FlashcardItem(
                question="What is DNA?",
                answer="Genetic blueprint",
                difficulty="medium",
                hint="Think of a double helix",
                mnemonic="DNA = Do Not Alter",
                related_topics=["genetics", "RNA"],
            ),
        ]
        result = workflow._format(raw_cards, [{"id": "c1"}])
        assert result[0].hint == "Think of a double helix"
        assert result[0].mnemonic == "DNA = Do Not Alter"
        assert result[0].related_topics == ["genetics", "RNA"]


# ---------------------------------------------------------------------------
# Context Building Tests
# ---------------------------------------------------------------------------


class TestBuildContext:
    """Test the _build_context helper."""

    def test_builds_context_from_chunks(self):
        """Combines chunk content with separators."""
        chunks = [
            {"id": "1", "content": "First chunk."},
            {"id": "2", "content": "Second chunk."},
        ]
        context = FlashcardWorkflow._build_context(chunks)
        assert "First chunk." in context
        assert "Second chunk." in context
        assert "---" in context

    def test_respects_max_chars_limit(self):
        """Stops adding chunks when max_chars is reached."""
        chunks = [
            {"id": "1", "content": "A" * 200},
            {"id": "2", "content": "B" * 200},
            {"id": "3", "content": "C" * 200},
        ]
        context = FlashcardWorkflow._build_context(chunks, max_chars=350)
        assert "A" * 200 in context
        # Second chunk should be partially included or not included
        assert len(context) <= 450  # Account for separators

    def test_empty_chunks_returns_fallback(self):
        """Returns fallback text when no chunks provided."""
        context = FlashcardWorkflow._build_context([])
        assert context == "No context available."

    def test_handles_chunks_without_content(self):
        """Gracefully handles chunks missing the content key."""
        chunks = [{"id": "1"}, {"id": "2", "content": "Has content"}]
        context = FlashcardWorkflow._build_context(chunks)
        assert "Has content" in context
