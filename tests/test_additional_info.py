"""Tests for the Additional Information Workflow.

Tests the AdditionalInfoWorkflow pipeline (retrieve → generate → format)
with mocked LLM and Retriever dependencies.
"""

from unittest.mock import MagicMock

import pytest

from src.workflows.additional_info import (
    ADDITIONAL_INFO_SYSTEM_PROMPT,
    AdditionalInfoWorkflow,
    _AdditionalInfoOutput,
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
            "content": "Neural networks are computational models inspired by the human brain.",
            "score": 0.95,
            "metadata": {"topic": "machine learning"},
        },
        {
            "id": "chunk-002",
            "content": "Backpropagation is the algorithm used to train neural networks by computing gradients.",
            "score": 0.88,
            "metadata": {"topic": "machine learning"},
        },
        {
            "id": "chunk-003",
            "content": "Convolutional neural networks excel at image recognition tasks.",
            "score": 0.80,
            "metadata": {"topic": "deep learning"},
        },
    ]
    return retriever


@pytest.fixture
def mock_llm_client():
    """Create a mock LLMClient that returns structured additional info JSON."""
    client = MagicMock()

    output = _AdditionalInfoOutput(
        applications=[
            "Image classification in medical diagnosis (detecting tumors in X-rays)",
            "Natural language processing for chatbots and virtual assistants",
            "Autonomous vehicle perception systems for object detection",
            "Recommendation engines for streaming platforms like Netflix",
        ],
        industry_uses=[
            "Healthcare: radiology image analysis and drug discovery",
            "Finance: fraud detection and algorithmic trading",
            "Automotive: self-driving car perception pipelines",
            "E-commerce: personalized product recommendations",
        ],
        common_mistakes=[
            "Overfitting by using too complex a model without regularization",
            "Not normalizing input features leading to slow convergence",
            "Using too high a learning rate causing training instability",
            "Ignoring class imbalance in training data",
        ],
        interview_questions=[
            "Explain the difference between a CNN and an RNN.",
            "What is backpropagation and how does it work?",
            "How do you handle overfitting in a neural network?",
            "Describe the vanishing gradient problem and solutions.",
        ],
    )

    client.generate_json.return_value = (output, {"provider": "groq", "total_tokens": 350})
    return client


@pytest.fixture
def workflow(mock_retriever, mock_llm_client):
    """Create an AdditionalInfoWorkflow with mocked dependencies."""
    return AdditionalInfoWorkflow(retriever=mock_retriever, llm_client=mock_llm_client)


# ---------------------------------------------------------------------------
# Pipeline Integration Tests
# ---------------------------------------------------------------------------


class TestAdditionalInfoWorkflowGenerate:
    """Test the full generate() pipeline."""

    def test_generate_returns_dict(self, workflow):
        """Generate returns a dict with expected keys."""
        result = workflow.generate(topic="neural networks")
        assert isinstance(result, dict)

    def test_generate_has_required_keys(self, workflow):
        """Result dict contains all four required keys."""
        result = workflow.generate(topic="neural networks")
        expected_keys = {"applications", "industry_uses", "common_mistakes", "interview_questions"}
        assert set(result.keys()) == expected_keys

    def test_generate_values_are_lists_of_strings(self, workflow):
        """Each value in the result is a list of strings."""
        result = workflow.generate(topic="neural networks")
        for key, value in result.items():
            assert isinstance(value, list), f"{key} should be a list"
            for item in value:
                assert isinstance(item, str), f"Items in {key} should be strings"

    def test_generate_list_lengths(self, workflow):
        """Each list should have 3-5 items."""
        result = workflow.generate(topic="neural networks")
        for key, value in result.items():
            assert 3 <= len(value) <= 5, (
                f"{key} has {len(value)} items, expected 3-5"
            )

    def test_generate_uses_semantic_search(self, workflow, mock_retriever):
        """Generate uses semantic_search to retrieve context."""
        workflow.generate(topic="neural networks")
        mock_retriever.semantic_search.assert_called_once_with(
            query="neural networks", top_k=8
        )

    def test_generate_calls_llm_with_correct_model(self, workflow, mock_llm_client):
        """LLM is called with _AdditionalInfoOutput as response model."""
        workflow.generate(topic="neural networks")
        call_kwargs = mock_llm_client.generate_json.call_args[1]
        assert call_kwargs["response_model"] is _AdditionalInfoOutput
        assert call_kwargs["system_prompt"] == ADDITIONAL_INFO_SYSTEM_PROMPT

    def test_generate_passes_topic_in_prompt(self, workflow, mock_llm_client):
        """The topic appears in the LLM prompt."""
        workflow.generate(topic="backpropagation")
        call_kwargs = mock_llm_client.generate_json.call_args[1]
        assert "backpropagation" in call_kwargs["prompt"]

    def test_generate_content_is_relevant(self, workflow):
        """Generated content relates to the topic domain."""
        result = workflow.generate(topic="neural networks")
        # Check that applications mention relevant terms
        all_text = " ".join(result["applications"])
        assert any(
            term in all_text.lower()
            for term in ["image", "language", "vehicle", "recommendation"]
        )


# ---------------------------------------------------------------------------
# Retrieve Step Tests
# ---------------------------------------------------------------------------


class TestRetrieveStep:
    """Test the _retrieve step in isolation."""

    def test_retrieve_calls_semantic_search(self, workflow, mock_retriever):
        """Retrieve uses semantic_search with top_k=8."""
        results = workflow._retrieve("deep learning")
        mock_retriever.semantic_search.assert_called_once_with(
            query="deep learning", top_k=8
        )
        assert len(results) == 3

    def test_retrieve_returns_chunk_list(self, workflow):
        """Retrieve returns a list of chunk dicts."""
        results = workflow._retrieve("neural networks")
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)


# ---------------------------------------------------------------------------
# Format Step Tests
# ---------------------------------------------------------------------------


class TestFormatStep:
    """Test the _format step in isolation."""

    def test_format_returns_dict_with_correct_keys(self, workflow):
        """Format returns a dict with the four expected keys."""
        raw = _AdditionalInfoOutput(
            applications=["App 1", "App 2", "App 3"],
            industry_uses=["Industry 1", "Industry 2", "Industry 3"],
            common_mistakes=["Mistake 1", "Mistake 2", "Mistake 3"],
            interview_questions=["Q1?", "Q2?", "Q3?"],
        )
        result = workflow._format(raw)
        assert set(result.keys()) == {
            "applications", "industry_uses", "common_mistakes", "interview_questions"
        }

    def test_format_truncates_to_max_five(self, workflow):
        """Format truncates lists longer than 5 items."""
        raw = _AdditionalInfoOutput(
            applications=[f"App {i}" for i in range(8)],
            industry_uses=[f"Industry {i}" for i in range(7)],
            common_mistakes=[f"Mistake {i}" for i in range(6)],
            interview_questions=[f"Q{i}?" for i in range(10)],
        )
        result = workflow._format(raw)
        for key, value in result.items():
            assert len(value) <= 5, f"{key} should be truncated to 5 max"

    def test_format_preserves_content(self, workflow):
        """Format preserves the actual string content."""
        raw = _AdditionalInfoOutput(
            applications=["Self-driving cars", "Medical imaging", "NLP chatbots"],
            industry_uses=["Healthcare", "Finance", "Automotive"],
            common_mistakes=["Overfitting", "Bad learning rate", "No regularization"],
            interview_questions=["What is a CNN?", "Explain RNN", "Describe GAN"],
        )
        result = workflow._format(raw)
        assert result["applications"][0] == "Self-driving cars"
        assert result["industry_uses"][1] == "Finance"
        assert result["common_mistakes"][2] == "No regularization"


# ---------------------------------------------------------------------------
# Context Building Tests
# ---------------------------------------------------------------------------


class TestBuildContext:
    """Test the _build_context helper."""

    def test_builds_context_from_chunks(self):
        """Combines chunk content with separators."""
        chunks = [
            {"id": "1", "content": "First chunk about neural networks."},
            {"id": "2", "content": "Second chunk about backpropagation."},
        ]
        context = AdditionalInfoWorkflow._build_context(chunks)
        assert "First chunk about neural networks." in context
        assert "Second chunk about backpropagation." in context
        assert "---" in context

    def test_respects_max_chars_limit(self):
        """Stops adding chunks when max_chars is reached."""
        chunks = [
            {"id": "1", "content": "A" * 200},
            {"id": "2", "content": "B" * 200},
            {"id": "3", "content": "C" * 200},
        ]
        context = AdditionalInfoWorkflow._build_context(chunks, max_chars=350)
        assert "A" * 200 in context
        assert len(context) <= 450  # Account for separators

    def test_empty_chunks_returns_fallback(self):
        """Returns fallback text when no chunks provided."""
        context = AdditionalInfoWorkflow._build_context([])
        assert context == "No context available."

    def test_handles_chunks_without_content(self):
        """Gracefully handles chunks missing the content key."""
        chunks = [{"id": "1"}, {"id": "2", "content": "Has content"}]
        context = AdditionalInfoWorkflow._build_context(chunks)
        assert "Has content" in context
