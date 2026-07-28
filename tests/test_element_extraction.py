"""Tests for the NeuroForge Element Extractor.

Tests formula, example, date, and people extraction with mocked LLM calls.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from models import Chunk, ChunkMetadata, Example, Formula, KeyDate, KeyPerson
from src.extraction.elements import (
    DEFAULT_BATCH_SIZE,
    DateListResponse,
    ElementExtractor,
    ExampleListResponse,
    FormulaListResponse,
    PersonListResponse,
)
from src.llm import LLMClient, LLMProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock(spec=LLMClient)
    client.available_providers = [LLMProvider.GROQ]
    return client


@pytest.fixture
def extractor(mock_llm_client):
    """Create an ElementExtractor with mocked LLM client."""
    return ElementExtractor(llm_client=mock_llm_client, batch_size=4)


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        Chunk(
            id="chunk-physics-1",
            content="Einstein published his theory of special relativity in 1905. "
            "The famous mass-energy equivalence formula E = mc^2 shows that "
            "energy equals mass times the speed of light squared.",
            document_id="doc-physics",
            chunk_index=0,
            metadata=ChunkMetadata(token_count=40, start_char=0, end_char=200),
        ),
        Chunk(
            id="chunk-physics-2",
            content="Isaac Newton formulated the law of universal gravitation in 1687. "
            "The gravitational force between two objects is given by F = G(m1*m2)/r^2. "
            "For example, calculating the gravitational pull between Earth and the Moon "
            "demonstrates the inverse square relationship.",
            document_id="doc-physics",
            chunk_index=1,
            metadata=ChunkMetadata(token_count=55, start_char=200, end_char=500),
        ),
        Chunk(
            id="chunk-physics-3",
            content="Marie Curie won Nobel Prizes in Physics (1903) and Chemistry (1911). "
            "Her research on radioactivity led to the discovery of radium and polonium. "
            "The decay rate formula N(t) = N0 * e^(-lambda*t) describes how radioactive "
            "substances diminish over time.",
            document_id="doc-physics",
            chunk_index=2,
            metadata=ChunkMetadata(token_count=50, start_char=500, end_char=800),
        ),
    ]


# ---------------------------------------------------------------------------
# Constructor Tests
# ---------------------------------------------------------------------------


class TestElementExtractorInit:
    def test_default_batch_size(self, mock_llm_client):
        extractor = ElementExtractor(llm_client=mock_llm_client)
        assert extractor.batch_size == DEFAULT_BATCH_SIZE

    def test_custom_batch_size(self, mock_llm_client):
        extractor = ElementExtractor(llm_client=mock_llm_client, batch_size=3)
        assert extractor.batch_size == 3

    def test_custom_provider(self, mock_llm_client):
        extractor = ElementExtractor(
            llm_client=mock_llm_client, provider=LLMProvider.GITHUB
        )
        assert extractor.provider == LLMProvider.GITHUB

    def test_stores_llm_client(self, mock_llm_client):
        extractor = ElementExtractor(llm_client=mock_llm_client)
        assert extractor.llm_client is mock_llm_client


# ---------------------------------------------------------------------------
# Formula Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractFormulae:
    def test_empty_chunks_returns_empty(self, extractor):
        result = extractor.extract_formulae([])
        assert result == []

    def test_extracts_formulae_with_source_chunk_id(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_response = FormulaListResponse(
            formulae=[
                {
                    "expression": "E = mc^2",
                    "description": "Mass-energy equivalence",
                    "context": "Special relativity",
                }
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 50})

        result = extractor.extract_formulae(sample_chunks)

        assert len(result) == 1
        assert isinstance(result[0], Formula)
        assert result[0].expression == "E = mc^2"
        assert result[0].description == "Mass-energy equivalence"
        assert result[0].context == "Special relativity"
        # Should match chunk-physics-1 because "e = mc^2" is in its content
        assert result[0].source_chunk_id == "chunk-physics-1"

    def test_multiple_formulae_extracted(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_response = FormulaListResponse(
            formulae=[
                {
                    "expression": "E = mc^2",
                    "description": "Mass-energy equivalence",
                    "context": "Special relativity",
                },
                {
                    "expression": "F = G(m1*m2)/r^2",
                    "description": "Gravitational force",
                    "context": "Newton's law of gravitation",
                },
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 80})

        result = extractor.extract_formulae(sample_chunks)

        assert len(result) == 2
        assert result[0].expression == "E = mc^2"
        assert result[1].expression == "F = G(m1*m2)/r^2"

    def test_handles_llm_failure_gracefully(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_llm_client.generate_json.side_effect = Exception("LLM error")

        result = extractor.extract_formulae(sample_chunks)
        assert result == []

    def test_fallback_source_chunk_when_no_match(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_response = FormulaListResponse(
            formulae=[
                {
                    "expression": "x = (-b ± sqrt(b^2 - 4ac)) / 2a",
                    "description": "Quadratic formula",
                    "context": "Algebra",
                }
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 40})

        result = extractor.extract_formulae(sample_chunks)

        assert len(result) == 1
        # Falls back to first chunk in batch
        assert result[0].source_chunk_id == "chunk-physics-1"


# ---------------------------------------------------------------------------
# Example Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractExamples:
    def test_empty_chunks_returns_empty(self, extractor):
        result = extractor.extract_examples([])
        assert result == []

    def test_extracts_examples_with_related_concepts(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_response = ExampleListResponse(
            examples=[
                {
                    "title": "Earth-Moon Gravitational Pull",
                    "content": "calculating the gravitational pull between Earth and the Moon",
                    "related_concepts": ["Gravity", "Inverse Square Law"],
                }
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 60})

        result = extractor.extract_examples(sample_chunks)

        assert len(result) == 1
        assert isinstance(result[0], Example)
        assert result[0].title == "Earth-Moon Gravitational Pull"
        assert "gravitational pull" in result[0].content
        assert result[0].related_concepts == ["Gravity", "Inverse Square Law"]
        assert result[0].source_chunk_id == "chunk-physics-2"

    def test_handles_llm_failure_gracefully(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_llm_client.generate_json.side_effect = Exception("LLM error")

        result = extractor.extract_examples(sample_chunks)
        assert result == []


# ---------------------------------------------------------------------------
# Date Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractDates:
    def test_empty_chunks_returns_empty(self, extractor):
        result = extractor.extract_dates([])
        assert result == []

    def test_extracts_dates_with_significance(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_response = DateListResponse(
            dates=[
                {
                    "date": "1905",
                    "event": "Einstein published special relativity",
                    "significance": "Revolutionized understanding of space and time",
                },
                {
                    "date": "1687",
                    "event": "Newton published Principia Mathematica",
                    "significance": "Established classical mechanics",
                },
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 70})

        result = extractor.extract_dates(sample_chunks)

        assert len(result) == 2
        assert isinstance(result[0], KeyDate)
        assert result[0].date == "1905"
        assert result[0].source_chunk_id == "chunk-physics-1"
        assert result[1].date == "1687"
        assert result[1].source_chunk_id == "chunk-physics-2"

    def test_handles_llm_failure_gracefully(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_llm_client.generate_json.side_effect = Exception("LLM error")

        result = extractor.extract_dates(sample_chunks)
        assert result == []


# ---------------------------------------------------------------------------
# People Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractPeople:
    def test_empty_chunks_returns_empty(self, extractor):
        result = extractor.extract_people([])
        assert result == []

    def test_extracts_people_with_contributions(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_response = PersonListResponse(
            people=[
                {
                    "name": "Einstein",
                    "role": "Physicist",
                    "contribution": "Developed theory of special relativity",
                },
                {
                    "name": "Isaac Newton",
                    "role": "Physicist and mathematician",
                    "contribution": "Formulated the law of universal gravitation",
                },
                {
                    "name": "Marie Curie",
                    "role": "Physicist and chemist",
                    "contribution": "Research on radioactivity",
                },
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 90})

        result = extractor.extract_people(sample_chunks)

        assert len(result) == 3
        assert isinstance(result[0], KeyPerson)
        assert result[0].name == "Einstein"
        assert result[0].source_chunk_id == "chunk-physics-1"
        assert result[1].name == "Isaac Newton"
        assert result[1].source_chunk_id == "chunk-physics-2"
        assert result[2].name == "Marie Curie"
        assert result[2].source_chunk_id == "chunk-physics-3"

    def test_handles_llm_failure_gracefully(
        self, extractor, mock_llm_client, sample_chunks
    ):
        mock_llm_client.generate_json.side_effect = Exception("LLM error")

        result = extractor.extract_people(sample_chunks)
        assert result == []


# ---------------------------------------------------------------------------
# Extract All Tests
# ---------------------------------------------------------------------------


class TestExtractAll:
    def test_empty_chunks_returns_empty_dict(self, extractor):
        result = extractor.extract_all([])
        assert result == {
            "formulae": [],
            "examples": [],
            "dates": [],
            "people": [],
        }

    def test_extract_all_combines_results(
        self, extractor, mock_llm_client, sample_chunks
    ):
        # Set up sequential returns for each extraction type
        formula_resp = FormulaListResponse(
            formulae=[
                {
                    "expression": "E = mc^2",
                    "description": "Mass-energy equivalence",
                    "context": "Relativity",
                }
            ]
        )
        example_resp = ExampleListResponse(
            examples=[
                {
                    "title": "Gravity Demo",
                    "content": "Earth and Moon gravitational pull",
                    "related_concepts": ["Gravity"],
                }
            ]
        )
        date_resp = DateListResponse(
            dates=[
                {
                    "date": "1905",
                    "event": "Special relativity published",
                    "significance": "Changed physics",
                }
            ]
        )
        person_resp = PersonListResponse(
            people=[
                {
                    "name": "Einstein",
                    "role": "Physicist",
                    "contribution": "Relativity theory",
                }
            ]
        )

        mock_llm_client.generate_json.side_effect = [
            (formula_resp, {"total_tokens": 40}),
            (example_resp, {"total_tokens": 50}),
            (date_resp, {"total_tokens": 40}),
            (person_resp, {"total_tokens": 45}),
        ]

        result = extractor.extract_all(sample_chunks)

        assert len(result["formulae"]) == 1
        assert len(result["examples"]) == 1
        assert len(result["dates"]) == 1
        assert len(result["people"]) == 1
        assert result["formulae"][0].expression == "E = mc^2"
        assert result["examples"][0].title == "Gravity Demo"
        assert result["dates"][0].date == "1905"
        assert result["people"][0].name == "Einstein"


# ---------------------------------------------------------------------------
# Batch Processing Tests
# ---------------------------------------------------------------------------


class TestBatchProcessing:
    def test_batches_chunks_correctly(self, mock_llm_client):
        extractor = ElementExtractor(llm_client=mock_llm_client, batch_size=2)
        chunks = [
            Chunk(
                id=f"c-{i}",
                content=f"Content {i}",
                document_id="doc-1",
                chunk_index=i,
                metadata=ChunkMetadata(token_count=10, start_char=i * 50, end_char=(i + 1) * 50),
            )
            for i in range(5)
        ]

        batches = extractor._batch_chunks(chunks)
        assert len(batches) == 3  # 2 + 2 + 1
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2
        assert len(batches[2]) == 1

    def test_format_chunks_includes_ids(self, extractor):
        chunks = [
            Chunk(
                id="test-chunk-1",
                content="Hello world",
                document_id="doc-1",
                chunk_index=0,
                metadata=ChunkMetadata(token_count=5, start_char=0, end_char=11),
            ),
        ]
        formatted = extractor._format_chunks(chunks)
        assert "[Chunk ID: test-chunk-1]" in formatted
        assert "Hello world" in formatted

    def test_processes_multiple_batches(self, mock_llm_client):
        extractor = ElementExtractor(llm_client=mock_llm_client, batch_size=2)
        chunks = [
            Chunk(
                id=f"c-{i}",
                content=f"Person {i} contributed to science",
                document_id="doc-1",
                chunk_index=i,
                metadata=ChunkMetadata(token_count=10, start_char=i * 50, end_char=(i + 1) * 50),
            )
            for i in range(3)
        ]

        # Each batch call returns one person
        resp1 = PersonListResponse(
            people=[{"name": "Person 0", "role": "Scientist", "contribution": "Discovery"}]
        )
        resp2 = PersonListResponse(
            people=[{"name": "Person 2", "role": "Engineer", "contribution": "Invention"}]
        )
        mock_llm_client.generate_json.side_effect = [
            (resp1, {"total_tokens": 30}),
            (resp2, {"total_tokens": 30}),
        ]

        result = extractor.extract_people(chunks)
        assert len(result) == 2
        assert mock_llm_client.generate_json.call_count == 2


# ---------------------------------------------------------------------------
# Source Chunk Matching Tests
# ---------------------------------------------------------------------------


class TestSourceChunkMatching:
    def test_finds_correct_source_chunk(self, extractor):
        chunks = [
            Chunk(
                id="a",
                content="The sky is blue",
                document_id="doc-1",
                chunk_index=0,
                metadata=ChunkMetadata(token_count=5, start_char=0, end_char=15),
            ),
            Chunk(
                id="b",
                content="Grass is green and Newton discovered gravity",
                document_id="doc-1",
                chunk_index=1,
                metadata=ChunkMetadata(token_count=8, start_char=15, end_char=55),
            ),
        ]

        result = extractor._find_source_chunk("Newton", chunks, ["a", "b"])
        assert result == "b"

    def test_case_insensitive_matching(self, extractor):
        chunks = [
            Chunk(
                id="x",
                content="EINSTEIN was a genius",
                document_id="doc-1",
                chunk_index=0,
                metadata=ChunkMetadata(token_count=5, start_char=0, end_char=21),
            ),
        ]

        result = extractor._find_source_chunk("einstein", chunks, ["x"])
        assert result == "x"

    def test_fallback_to_first_chunk(self, extractor):
        chunks = [
            Chunk(
                id="first",
                content="Nothing matches here",
                document_id="doc-1",
                chunk_index=0,
                metadata=ChunkMetadata(token_count=5, start_char=0, end_char=20),
            ),
        ]

        result = extractor._find_source_chunk("xyz_not_found", chunks, ["first"])
        assert result == "first"
