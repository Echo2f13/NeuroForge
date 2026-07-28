"""Tests for the Solution Generation Workflow.

Tests the SolutionWorkflow pipeline with mocked LLM and Retriever
to validate depth scaling, prompt construction, and output formatting.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from models.output import Solution
from src.workflows.solutions import (
    DEPTH_PROMPTS,
    SolutionWorkflow,
    _build_solution_prompt,
    _get_depth_category,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm(solution_data: dict) -> MagicMock:
    """Create a mock LLMClient that returns the given solution data."""
    mock_llm = MagicMock()
    solution = Solution.model_validate(solution_data)
    mock_llm.generate_json.return_value = (
        solution,
        {"provider": "groq", "total_tokens": 100, "latency_seconds": 0.5},
    )
    return mock_llm


def _make_mock_retriever(chunks: list[dict] | None = None) -> MagicMock:
    """Create a mock Retriever that returns the given chunks."""
    mock_retriever = MagicMock()
    if chunks is None:
        chunks = [
            {"content": "Photosynthesis is the process by which plants convert light energy.", "score": 0.9},
            {"content": "Chlorophyll absorbs light primarily in red and blue wavelengths.", "score": 0.8},
        ]
    mock_retriever.semantic_search.return_value = chunks
    return mock_retriever


# ---------------------------------------------------------------------------
# Depth Category Tests
# ---------------------------------------------------------------------------


class TestDepthCategory:
    def test_low_marks_are_brief(self):
        assert _get_depth_category(1) == "brief"
        assert _get_depth_category(2) == "brief"
        assert _get_depth_category(3) == "brief"

    def test_medium_marks_are_moderate(self):
        assert _get_depth_category(4) == "moderate"
        assert _get_depth_category(5) == "moderate"
        assert _get_depth_category(6) == "moderate"

    def test_high_marks_are_detailed(self):
        assert _get_depth_category(7) == "detailed"
        assert _get_depth_category(10) == "detailed"
        assert _get_depth_category(20) == "detailed"
        assert _get_depth_category(100) == "detailed"


# ---------------------------------------------------------------------------
# Prompt Construction Tests
# ---------------------------------------------------------------------------


class TestPromptConstruction:
    def test_brief_prompt_contains_depth_instruction(self):
        prompt = _build_solution_prompt(
            question="Define osmosis",
            topic="Biology",
            marks=2,
            context="Osmosis is the movement of water molecules.",
        )
        assert "2-3 sentences" in prompt
        assert "Define osmosis" in prompt
        assert "Biology" in prompt
        assert "2" in prompt

    def test_moderate_prompt_contains_key_points(self):
        prompt = _build_solution_prompt(
            question="Explain photosynthesis",
            topic="Biology",
            marks=5,
            context="Plants convert light to energy.",
        )
        assert "key points" in prompt.lower()
        assert "Explain photosynthesis" in prompt

    def test_detailed_prompt_contains_examples(self):
        prompt = _build_solution_prompt(
            question="Discuss the causes of WWI",
            topic="History",
            marks=10,
            context="WWI began in 1914.",
        )
        assert "examples" in prompt.lower()
        assert "diagram" in prompt.lower()
        assert "comprehensive" in prompt.lower()

    def test_empty_context_handled(self):
        prompt = _build_solution_prompt(
            question="What is gravity?",
            topic="Physics",
            marks=3,
            context="",
        )
        assert "No specific context available" in prompt


# ---------------------------------------------------------------------------
# SolutionWorkflow Tests
# ---------------------------------------------------------------------------


class TestSolutionWorkflow:
    def test_generate_brief_solution(self):
        """Test 2-mark brief answer generation."""
        solution_data = {
            "question": "Define osmosis",
            "marks": 2,
            "answer": "Osmosis is the movement of water molecules through a semi-permeable membrane from high to low concentration.",
            "marking_scheme": [
                "1 mark: Mention movement of water molecules",
                "1 mark: Through semi-permeable membrane",
            ],
            "key_points": [
                "Water molecules move through membrane",
                "High to low concentration gradient",
            ],
            "topic": "Biology",
        }
        mock_llm = _make_mock_llm(solution_data)
        mock_retriever = _make_mock_retriever()

        workflow = SolutionWorkflow(llm_client=mock_llm, retriever=mock_retriever)
        result = workflow.generate(
            question="Define osmosis", topic="Biology", marks=2
        )

        assert isinstance(result, Solution)
        assert result.marks == 2
        assert result.question == "Define osmosis"
        assert len(result.marking_scheme) == 2
        assert len(result.key_points) == 2

        # Verify retriever was called
        mock_retriever.semantic_search.assert_called_once()

        # Verify LLM was called with correct params
        mock_llm.generate_json.assert_called_once()
        call_kwargs = mock_llm.generate_json.call_args[1]
        assert call_kwargs["response_model"] == Solution
        assert call_kwargs["max_tokens"] == 512  # brief

    def test_generate_moderate_solution(self):
        """Test 5-mark moderate answer generation."""
        solution_data = {
            "question": "Explain photosynthesis",
            "marks": 5,
            "answer": "Photosynthesis is the process by which green plants convert light energy into chemical energy...",
            "marking_scheme": [
                "1 mark: Define photosynthesis",
                "1 mark: Mention light energy conversion",
                "1 mark: Role of chlorophyll",
                "1 mark: CO2 + H2O equation",
                "1 mark: Products (glucose + oxygen)",
            ],
            "key_points": [
                "Light energy converted to chemical energy",
                "Occurs in chloroplasts",
                "Requires CO2 and H2O",
                "Produces glucose and oxygen",
                "Chlorophyll is the key pigment",
            ],
            "topic": "Biology",
        }
        mock_llm = _make_mock_llm(solution_data)
        mock_retriever = _make_mock_retriever()

        workflow = SolutionWorkflow(llm_client=mock_llm, retriever=mock_retriever)
        result = workflow.generate(
            question="Explain photosynthesis", topic="Biology", marks=5
        )

        assert result.marks == 5
        assert len(result.marking_scheme) == 5
        assert len(result.key_points) == 5

        call_kwargs = mock_llm.generate_json.call_args[1]
        assert call_kwargs["max_tokens"] == 1024  # moderate

    def test_generate_detailed_solution(self):
        """Test 10-mark detailed answer generation."""
        solution_data = {
            "question": "Discuss the process of photosynthesis in detail",
            "marks": 10,
            "answer": "Photosynthesis is a complex biochemical process...",
            "marking_scheme": [
                "1 mark: Define photosynthesis",
                "1 mark: Light-dependent reactions",
                "1 mark: Light-independent reactions (Calvin cycle)",
                "1 mark: Role of chlorophyll and pigments",
                "1 mark: Equation with reactants and products",
                "1 mark: Location in chloroplast (thylakoid, stroma)",
                "1 mark: Factors affecting rate",
                "1 mark: Importance for ecosystems",
                "1 mark: Diagram of chloroplast structure",
                "1 mark: Example of C3 vs C4 plants",
            ],
            "key_points": [
                "Two stages: light-dependent and light-independent",
                "Occurs in chloroplasts",
                "Light reactions in thylakoid membranes",
                "Calvin cycle in stroma",
                "ATP and NADPH as energy carriers",
                "CO2 fixation by RuBisCO",
                "Overall equation: 6CO2 + 6H2O → C6H12O6 + 6O2",
                "Rate affected by light, CO2, temperature",
                "Essential for food chains",
                "Evolved ~2.5 billion years ago",
            ],
            "topic": "Biology",
        }
        mock_llm = _make_mock_llm(solution_data)
        mock_retriever = _make_mock_retriever()

        workflow = SolutionWorkflow(llm_client=mock_llm, retriever=mock_retriever)
        result = workflow.generate(
            question="Discuss the process of photosynthesis in detail",
            topic="Biology",
            marks=10,
        )

        assert result.marks == 10
        assert len(result.marking_scheme) == 10
        assert len(result.key_points) == 10

        call_kwargs = mock_llm.generate_json.call_args[1]
        assert call_kwargs["max_tokens"] == 2048  # detailed

    def test_generate_without_retriever(self):
        """Test generation works when no retriever is provided."""
        solution_data = {
            "question": "What is gravity?",
            "marks": 3,
            "answer": "Gravity is a fundamental force of attraction between objects with mass.",
            "marking_scheme": [
                "1 mark: Identify as fundamental force",
                "1 mark: Attraction between masses",
                "1 mark: Proportional to mass, inversely to distance squared",
            ],
            "key_points": [
                "Fundamental force",
                "Acts between all masses",
                "Described by Newton's law of gravitation",
            ],
            "topic": "Physics",
        }
        mock_llm = _make_mock_llm(solution_data)

        workflow = SolutionWorkflow(llm_client=mock_llm, retriever=None)
        result = workflow.generate(
            question="What is gravity?", topic="Physics", marks=3
        )

        assert isinstance(result, Solution)
        assert result.topic == "Physics"

    def test_generate_with_retriever_failure(self):
        """Test graceful handling when retriever raises an exception."""
        solution_data = {
            "question": "Define entropy",
            "marks": 4,
            "answer": "Entropy is a measure of disorder in a system.",
            "marking_scheme": [
                "1 mark: Measure of disorder",
                "1 mark: Thermodynamic property",
                "1 mark: Increases in isolated systems",
                "1 mark: Units (J/K)",
            ],
            "key_points": [
                "Measure of disorder/randomness",
                "Second law of thermodynamics",
                "Always increases in isolated systems",
                "State function",
            ],
            "topic": "Chemistry",
        }
        mock_llm = _make_mock_llm(solution_data)
        mock_retriever = MagicMock()
        mock_retriever.semantic_search.side_effect = RuntimeError("DB connection failed")

        workflow = SolutionWorkflow(llm_client=mock_llm, retriever=mock_retriever)
        result = workflow.generate(
            question="Define entropy", topic="Chemistry", marks=4
        )

        # Should still produce a solution (without context)
        assert isinstance(result, Solution)
        assert result.question == "Define entropy"

    def test_invalid_marks_raises_value_error(self):
        """Test that marks outside 1-100 raises ValueError."""
        mock_llm = MagicMock()
        workflow = SolutionWorkflow(llm_client=mock_llm)

        with pytest.raises(ValueError, match="marks must be between 1 and 100"):
            workflow.generate(question="Test", topic="Test", marks=0)

        with pytest.raises(ValueError, match="marks must be between 1 and 100"):
            workflow.generate(question="Test", topic="Test", marks=101)

    def test_context_passed_to_prompt(self):
        """Verify retrieved context is passed into the LLM prompt."""
        solution_data = {
            "question": "Explain mitosis",
            "marks": 5,
            "answer": "Mitosis is cell division...",
            "marking_scheme": ["1 mark: Define mitosis"] * 5,
            "key_points": ["Cell division", "Produces identical cells"] * 2 + ["DNA replication"],
            "topic": "Biology",
        }
        mock_llm = _make_mock_llm(solution_data)
        mock_retriever = _make_mock_retriever([
            {"content": "Mitosis produces two genetically identical daughter cells.", "score": 0.95},
        ])

        workflow = SolutionWorkflow(llm_client=mock_llm, retriever=mock_retriever)
        workflow.generate(question="Explain mitosis", topic="Biology", marks=5)

        # Check the prompt sent to LLM contains the retrieved context
        call_kwargs = mock_llm.generate_json.call_args[1]
        prompt = call_kwargs["prompt"]
        assert "Mitosis produces two genetically identical daughter cells" in prompt
