"""Tests for the Revision Notes Workflow.

Tests the RevisionNotesWorkflow pipeline with mocked LLM and Retriever
to verify the retrieve → generate → format flow works correctly.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from models.output import RevisionNote, SubtopicNote
from src.workflows.revision_notes import RevisionNotesWorkflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_retriever():
    """Create a mock Retriever with predefined search results."""
    retriever = MagicMock()
    retriever.hybrid_retrieval.return_value = [
        {
            "id": "chunk_1",
            "content": "Photosynthesis is the process by which plants convert "
            "sunlight into chemical energy. It occurs in chloroplasts.",
            "score": 0.95,
            "metadata": {"topic": "biology"},
        },
        {
            "id": "chunk_2",
            "content": "The light-dependent reactions occur in the thylakoid "
            "membrane and produce ATP and NADPH.",
            "score": 0.88,
            "metadata": {"topic": "biology"},
        },
        {
            "id": "chunk_3",
            "content": "The Calvin cycle (light-independent reactions) fixes "
            "CO2 into glucose using ATP and NADPH from the light reactions.",
            "score": 0.82,
            "metadata": {"topic": "biology"},
        },
    ]
    retriever.semantic_search.return_value = [
        {
            "id": "chunk_1",
            "content": "Photosynthesis overview content.",
            "score": 0.90,
            "metadata": {"topic": "biology"},
        },
    ]
    return retriever


@pytest.fixture
def sample_revision_note_data():
    """Sample revision note JSON that the LLM would return."""
    return {
        "topic": "Photosynthesis",
        "subtopics": [
            {
                "title": "Light-Dependent Reactions",
                "points": [
                    "Occur in thylakoid membranes",
                    "Water is split (photolysis) releasing O2",
                    "Produce ATP and NADPH for the Calvin cycle",
                ],
                "importance": "high",
            },
            {
                "title": "Calvin Cycle (Light-Independent)",
                "points": [
                    "Occurs in the stroma of chloroplasts",
                    "CO2 is fixed by RuBisCO enzyme",
                    "Produces G3P which is used to make glucose",
                ],
                "importance": "high",
            },
            {
                "title": "Factors Affecting Rate",
                "points": [
                    "Light intensity increases rate up to a plateau",
                    "CO2 concentration is a limiting factor",
                    "Temperature affects enzyme activity",
                ],
                "importance": "medium",
            },
        ],
        "key_terms": [
            "Photolysis: splitting of water molecules by light",
            "RuBisCO: enzyme that fixes CO2 in the Calvin cycle",
            "Thylakoid: membrane structure where light reactions occur",
            "Stroma: fluid-filled space where Calvin cycle occurs",
        ],
        "formulae": [
            "6CO2 + 6H2O → C6H12O6 + 6O2 (overall equation)",
            "ATP + H2O → ADP + Pi (energy release)",
        ],
        "mnemonics": [
            "Light reactions make ATP and NADPH: 'A Nice Pool of Hydrogen'",
            "Calvin cycle: 'Carbon And Light Vary In Necessity'",
        ],
    }


@pytest.fixture
def mock_llm_client(sample_revision_note_data):
    """Create a mock LLMClient that returns structured revision notes."""
    llm_client = MagicMock()
    revision_note = RevisionNote.model_validate(sample_revision_note_data)
    llm_client.generate_json.return_value = (
        revision_note,
        {
            "provider": "groq",
            "model": "test-model",
            "total_tokens": 500,
            "latency_seconds": 1.2,
        },
    )
    return llm_client


# ---------------------------------------------------------------------------
# Workflow Initialization Tests
# ---------------------------------------------------------------------------


class TestRevisionNotesWorkflowInit:
    def test_init_with_defaults(self, mock_retriever, mock_llm_client):
        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )
        assert workflow.retriever is mock_retriever
        assert workflow.llm_client is mock_llm_client
        assert workflow.top_k == 8
        assert workflow.provider is None

    def test_init_with_custom_params(self, mock_retriever, mock_llm_client):
        from src.llm import LLMProvider

        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
            top_k=5,
            provider=LLMProvider.GROQ,
        )
        assert workflow.top_k == 5
        assert workflow.provider == LLMProvider.GROQ


# ---------------------------------------------------------------------------
# Generate Method Tests
# ---------------------------------------------------------------------------


class TestRevisionNotesGenerate:
    def test_generate_returns_revision_note(
        self, mock_retriever, mock_llm_client
    ):
        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )

        result = workflow.generate("Photosynthesis")

        assert isinstance(result, RevisionNote)
        assert result.topic == "Photosynthesis"

    def test_generate_has_subtopics(self, mock_retriever, mock_llm_client):
        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )

        result = workflow.generate("Photosynthesis")

        assert len(result.subtopics) == 3
        assert result.subtopics[0].title == "Light-Dependent Reactions"
        assert result.subtopics[0].importance == "high"
        assert len(result.subtopics[0].points) == 3

    def test_generate_has_key_terms(self, mock_retriever, mock_llm_client):
        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )

        result = workflow.generate("Photosynthesis")

        assert len(result.key_terms) == 4
        assert any("RuBisCO" in term for term in result.key_terms)

    def test_generate_has_formulae(self, mock_retriever, mock_llm_client):
        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )

        result = workflow.generate("Photosynthesis")

        assert len(result.formulae) == 2
        assert any("6CO2" in formula for formula in result.formulae)

    def test_generate_has_mnemonics(self, mock_retriever, mock_llm_client):
        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )

        result = workflow.generate("Photosynthesis")

        assert len(result.mnemonics) == 2

    def test_generate_calls_retriever(self, mock_retriever, mock_llm_client):
        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
            top_k=5,
        )

        workflow.generate("Photosynthesis")

        mock_retriever.hybrid_retrieval.assert_called_once_with(
            query="Photosynthesis", top_k=5
        )

    def test_generate_calls_llm_with_context(
        self, mock_retriever, mock_llm_client
    ):
        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )

        workflow.generate("Photosynthesis")

        # Verify generate_json was called
        mock_llm_client.generate_json.assert_called_once()
        call_kwargs = mock_llm_client.generate_json.call_args.kwargs
        assert call_kwargs["response_model"] is RevisionNote
        assert "Photosynthesis" in call_kwargs["prompt"]
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 4096


# ---------------------------------------------------------------------------
# Context Retrieval Tests
# ---------------------------------------------------------------------------


class TestContextRetrieval:
    def test_falls_back_to_semantic_when_hybrid_empty(
        self, mock_retriever, mock_llm_client
    ):
        mock_retriever.hybrid_retrieval.return_value = []

        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )

        workflow.generate("Photosynthesis")

        mock_retriever.semantic_search.assert_called_once_with(
            query="Photosynthesis", top_k=8
        )

    def test_context_includes_chunk_content(
        self, mock_retriever, mock_llm_client
    ):
        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )

        workflow.generate("Photosynthesis")

        # Check that the prompt sent to LLM includes retrieved content
        call_kwargs = mock_llm_client.generate_json.call_args.kwargs
        prompt = call_kwargs["prompt"]
        assert "Photosynthesis is the process" in prompt
        assert "light-dependent reactions" in prompt.lower() or "light" in prompt.lower()

    def test_empty_retrieval_uses_topic_as_context(
        self, mock_retriever, mock_llm_client
    ):
        mock_retriever.hybrid_retrieval.return_value = []
        mock_retriever.semantic_search.return_value = []

        workflow = RevisionNotesWorkflow(
            retriever=mock_retriever,
            llm_client=mock_llm_client,
        )

        workflow.generate("Quantum Mechanics")

        call_kwargs = mock_llm_client.generate_json.call_args.kwargs
        prompt = call_kwargs["prompt"]
        assert "Quantum Mechanics" in prompt


# ---------------------------------------------------------------------------
# SubtopicNote Model Tests
# ---------------------------------------------------------------------------


class TestSubtopicNoteModel:
    def test_valid_subtopic(self):
        note = SubtopicNote(
            title="Test Subtopic",
            points=["Point 1", "Point 2"],
            importance="high",
        )
        assert note.title == "Test Subtopic"
        assert note.importance == "high"

    def test_invalid_importance_rejected(self):
        with pytest.raises(ValueError):
            SubtopicNote(
                title="Test",
                points=["Point 1"],
                importance="critical",
            )

    def test_empty_points_rejected(self):
        with pytest.raises(ValueError):
            SubtopicNote(
                title="Test",
                points=[],
                importance="medium",
            )


# ---------------------------------------------------------------------------
# RevisionNote Model Tests
# ---------------------------------------------------------------------------


class TestRevisionNoteModel:
    def test_valid_revision_note(self, sample_revision_note_data):
        note = RevisionNote.model_validate(sample_revision_note_data)
        assert note.topic == "Photosynthesis"
        assert len(note.subtopics) == 3

    def test_minimal_revision_note(self):
        note = RevisionNote(
            topic="Test Topic",
            subtopics=[
                SubtopicNote(
                    title="Sub 1",
                    points=["Point 1"],
                    importance="low",
                )
            ],
        )
        assert note.topic == "Test Topic"
        assert note.key_terms == []
        assert note.formulae == []
        assert note.mnemonics == []

    def test_serialization_roundtrip(self, sample_revision_note_data):
        note = RevisionNote.model_validate(sample_revision_note_data)
        json_str = note.to_json()
        restored = RevisionNote.from_json(json_str)
        assert restored.topic == note.topic
        assert len(restored.subtopics) == len(note.subtopics)
        assert restored.key_terms == note.key_terms
