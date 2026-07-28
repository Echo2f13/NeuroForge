"""Tests for the NeuroForge Metadata Extraction module.

Tests MetadataExtractor functionality with mocked LLM calls:
- Difficulty classification per chunk
- Study time estimation per concept
- Keyword extraction per chunk
- Chunk-level summary generation
- Document-level summary generation
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from models import Chunk, ChunkMetadata, Concept, Difficulty, Document, DocumentMetadata, InputFormat
from src.extraction.metadata import (
    ChunkSummariesResponse,
    DifficultyResponse,
    DocumentSummaryResponse,
    KeywordsResponse,
    MetadataExtractor,
    PREREQ_TIME_BONUS,
    MAX_PREREQ_BONUS,
    STUDY_TIME_RANGES,
)
from src.llm import LLMClient, LLMProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str, content: str, index: int = 0) -> Chunk:
    """Helper to create a test chunk."""
    return Chunk(
        id=chunk_id,
        content=content,
        document_id="doc-001",
        chunk_index=index,
        metadata=ChunkMetadata(
            token_count=len(content.split()),
            start_char=0,
            end_char=len(content),
        ),
    )


def _make_concept(
    concept_id: str,
    name: str,
    difficulty: Difficulty = Difficulty.MEDIUM,
    prerequisites: list[str] | None = None,
) -> Concept:
    """Helper to create a test concept."""
    return Concept(
        id=concept_id,
        name=name,
        definition=f"Definition of {name}",
        topics=["Test Topic"],
        difficulty=difficulty,
        prerequisites=prerequisites or [],
        keywords=[],
        source_chunk_ids=["chunk-001"],
    )


def _make_document(content: str = "Test document content.") -> Document:
    """Helper to create a test document."""
    return Document(
        content=content,
        metadata=DocumentMetadata(
            source="test.pdf",
            format=InputFormat.PDF,
            title="Test Document",
        ),
    )


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock(spec=LLMClient)
    return client


@pytest.fixture
def extractor(mock_llm_client):
    """Create a MetadataExtractor with mocked LLM client."""
    return MetadataExtractor(llm_client=mock_llm_client, batch_size=3)


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        _make_chunk("chunk-001", "Photosynthesis is the process of converting light energy.", 0),
        _make_chunk("chunk-002", "The Krebs cycle involves complex biochemical reactions.", 1),
        _make_chunk("chunk-003", "DNA stores genetic information in nucleotide sequences.", 2),
    ]


# ---------------------------------------------------------------------------
# Difficulty Classification Tests
# ---------------------------------------------------------------------------


class TestClassifyDifficulty:
    def test_empty_chunks_returns_empty(self, extractor):
        result = extractor.classify_difficulty([])
        assert result == {}

    def test_classifies_all_chunks(self, extractor, mock_llm_client, sample_chunks):
        mock_response = DifficultyResponse(
            classifications=[
                {"chunk_id": "chunk-001", "difficulty": "easy"},
                {"chunk_id": "chunk-002", "difficulty": "hard"},
                {"chunk_id": "chunk-003", "difficulty": "medium"},
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 50})

        result = extractor.classify_difficulty(sample_chunks)

        assert result["chunk-001"] == Difficulty.EASY
        assert result["chunk-002"] == Difficulty.HARD
        assert result["chunk-003"] == Difficulty.MEDIUM

    def test_defaults_to_medium_on_failure(self, extractor, mock_llm_client, sample_chunks):
        mock_llm_client.generate_json.side_effect = Exception("LLM error")

        result = extractor.classify_difficulty(sample_chunks)

        # All should default to MEDIUM
        for chunk in sample_chunks:
            assert result[chunk.id] == Difficulty.MEDIUM

    def test_handles_unknown_difficulty_string(self, extractor, mock_llm_client):
        chunks = [_make_chunk("chunk-001", "Some content")]
        mock_response = DifficultyResponse(
            classifications=[
                {"chunk_id": "chunk-001", "difficulty": "unknown_level"},
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 20})

        result = extractor.classify_difficulty(chunks)
        # Unknown difficulty defaults to MEDIUM
        assert result["chunk-001"] == Difficulty.MEDIUM

    def test_batches_chunks(self, extractor, mock_llm_client):
        """Verify chunks are processed in batches (batch_size=3)."""
        chunks = [_make_chunk(f"chunk-{i:03d}", f"Content {i}", i) for i in range(7)]

        # Return appropriate responses per batch
        def mock_generate_json(prompt, response_model, **kwargs):
            # Parse chunk IDs from the prompt to return matching classifications
            classifications = []
            for chunk in chunks:
                if chunk.id in prompt:
                    classifications.append(
                        {"chunk_id": chunk.id, "difficulty": "easy"}
                    )
            return DifficultyResponse(classifications=classifications), {"total_tokens": 30}

        mock_llm_client.generate_json.side_effect = mock_generate_json

        result = extractor.classify_difficulty(chunks)

        # Should have been called 3 times (7 chunks / batch_size 3 = 3 batches)
        assert mock_llm_client.generate_json.call_count == 3
        assert len(result) == 7


# ---------------------------------------------------------------------------
# Study Time Estimation Tests
# ---------------------------------------------------------------------------


class TestEstimateStudyTime:
    def test_empty_concepts_returns_empty(self, extractor):
        result = extractor.estimate_study_time([])
        assert result == {}

    def test_easy_concept_base_time(self, extractor):
        concepts = [_make_concept("c1", "Simple Concept", Difficulty.EASY)]
        result = extractor.estimate_study_time(concepts)

        min_t, max_t = STUDY_TIME_RANGES[Difficulty.EASY]
        expected = (min_t + max_t) / 2.0
        assert result["c1"] == expected

    def test_medium_concept_base_time(self, extractor):
        concepts = [_make_concept("c2", "Moderate Concept", Difficulty.MEDIUM)]
        result = extractor.estimate_study_time(concepts)

        min_t, max_t = STUDY_TIME_RANGES[Difficulty.MEDIUM]
        expected = (min_t + max_t) / 2.0
        assert result["c2"] == expected

    def test_hard_concept_base_time(self, extractor):
        concepts = [_make_concept("c3", "Complex Concept", Difficulty.HARD)]
        result = extractor.estimate_study_time(concepts)

        min_t, max_t = STUDY_TIME_RANGES[Difficulty.HARD]
        expected = (min_t + max_t) / 2.0
        assert result["c3"] == expected

    def test_prerequisites_increase_time(self, extractor):
        concept_no_prereq = _make_concept("c1", "No Prereqs", Difficulty.MEDIUM)
        concept_with_prereqs = _make_concept(
            "c2", "With Prereqs", Difficulty.MEDIUM, prerequisites=["p1", "p2", "p3"]
        )

        result = extractor.estimate_study_time([concept_no_prereq, concept_with_prereqs])

        # Concept with prerequisites should take longer
        assert result["c2"] > result["c1"]
        # Bonus should be 3 prereqs * PREREQ_TIME_BONUS
        expected_bonus = 3 * PREREQ_TIME_BONUS
        assert result["c2"] - result["c1"] == pytest.approx(expected_bonus, rel=0.01)

    def test_prereq_bonus_capped(self, extractor):
        # Many prerequisites should be capped at MAX_PREREQ_BONUS
        many_prereqs = [f"p{i}" for i in range(20)]
        concept = _make_concept("c1", "Many Prereqs", Difficulty.EASY, prerequisites=many_prereqs)

        result = extractor.estimate_study_time([concept])

        min_t, max_t = STUDY_TIME_RANGES[Difficulty.EASY]
        base = (min_t + max_t) / 2.0
        expected_max = base + MAX_PREREQ_BONUS
        assert result["c1"] == pytest.approx(expected_max, rel=0.01)

    def test_multiple_concepts(self, extractor):
        concepts = [
            _make_concept("c1", "Easy", Difficulty.EASY),
            _make_concept("c2", "Medium", Difficulty.MEDIUM),
            _make_concept("c3", "Hard", Difficulty.HARD),
        ]
        result = extractor.estimate_study_time(concepts)

        assert len(result) == 3
        # Easy < Medium < Hard
        assert result["c1"] < result["c2"] < result["c3"]


# ---------------------------------------------------------------------------
# Keyword Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractKeywords:
    def test_empty_chunks_returns_empty(self, extractor):
        result = extractor.extract_keywords([])
        assert result == {}

    def test_extracts_keywords_per_chunk(self, extractor, mock_llm_client, sample_chunks):
        mock_response = KeywordsResponse(
            results=[
                {"chunk_id": "chunk-001", "keywords": ["photosynthesis", "light", "energy", "chloroplast", "glucose"]},
                {"chunk_id": "chunk-002", "keywords": ["krebs cycle", "biochemistry", "ATP", "mitochondria", "oxidation"]},
                {"chunk_id": "chunk-003", "keywords": ["DNA", "genetics", "nucleotide", "helix", "gene expression"]},
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 60})

        result = extractor.extract_keywords(sample_chunks)

        assert len(result) == 3
        assert len(result["chunk-001"]) == 5
        assert "photosynthesis" in result["chunk-001"]
        assert "DNA" in result["chunk-003"]

    def test_returns_empty_keywords_on_failure(self, extractor, mock_llm_client, sample_chunks):
        mock_llm_client.generate_json.side_effect = Exception("LLM error")

        result = extractor.extract_keywords(sample_chunks)

        for chunk in sample_chunks:
            assert result[chunk.id] == []


# ---------------------------------------------------------------------------
# Chunk Summary Tests
# ---------------------------------------------------------------------------


class TestGenerateChunkSummaries:
    def test_empty_chunks_returns_empty(self, extractor):
        result = extractor.generate_chunk_summaries([])
        assert result == {}

    def test_generates_summaries(self, extractor, mock_llm_client, sample_chunks):
        mock_response = ChunkSummariesResponse(
            summaries=[
                {"chunk_id": "chunk-001", "summary": "Describes the process of photosynthesis and energy conversion."},
                {"chunk_id": "chunk-002", "summary": "Explains the Krebs cycle and its biochemical reactions."},
                {"chunk_id": "chunk-003", "summary": "Covers DNA structure and genetic information storage."},
            ]
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 80})

        result = extractor.generate_chunk_summaries(sample_chunks)

        assert len(result) == 3
        assert "photosynthesis" in result["chunk-001"]
        assert "Krebs cycle" in result["chunk-002"]

    def test_returns_empty_summaries_on_failure(self, extractor, mock_llm_client, sample_chunks):
        mock_llm_client.generate_json.side_effect = Exception("LLM error")

        result = extractor.generate_chunk_summaries(sample_chunks)

        for chunk in sample_chunks:
            assert result[chunk.id] == ""


# ---------------------------------------------------------------------------
# Document Summary Tests
# ---------------------------------------------------------------------------


class TestGenerateDocumentSummary:
    def test_empty_document_returns_empty(self, extractor):
        # Document requires non-empty content per model validation,
        # so we test with a document that has minimal content
        doc = _make_document("x")
        mock_response = DocumentSummaryResponse(summary="Brief summary.")
        extractor.llm_client.generate_json.return_value = (mock_response, {"total_tokens": 30})

        result = extractor.generate_document_summary(doc)
        assert result == "Brief summary."

    def test_generates_summary(self, extractor, mock_llm_client):
        doc = _make_document(
            "This is a comprehensive document about machine learning algorithms. "
            "It covers supervised and unsupervised methods in detail."
        )
        mock_response = DocumentSummaryResponse(
            summary="This document covers machine learning algorithms. "
            "It discusses supervised and unsupervised methods. "
            "The material is suitable for intermediate learners."
        )
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 100})

        result = extractor.generate_document_summary(doc)

        assert "machine learning" in result
        assert len(result) > 0

    def test_returns_empty_on_failure(self, extractor, mock_llm_client):
        doc = _make_document("Some content here.")
        mock_llm_client.generate_json.side_effect = Exception("LLM error")

        result = extractor.generate_document_summary(doc)
        assert result == ""

    def test_truncates_long_content(self, extractor, mock_llm_client):
        """Verify that long documents are truncated before sending to LLM."""
        long_content = "A" * 5000
        doc = _make_document(long_content)
        mock_response = DocumentSummaryResponse(summary="Summary of long doc.")
        mock_llm_client.generate_json.return_value = (mock_response, {"total_tokens": 50})

        result = extractor.generate_document_summary(doc)

        # Verify the prompt sent to LLM has truncated content
        call_args = mock_llm_client.generate_json.call_args
        prompt = call_args.kwargs.get("prompt") or call_args[1].get("prompt") or call_args[0][0]
        assert "[... content truncated" in prompt


# ---------------------------------------------------------------------------
# Integration & Constructor Tests
# ---------------------------------------------------------------------------


class TestMetadataExtractorInit:
    def test_default_batch_size(self, mock_llm_client):
        extractor = MetadataExtractor(llm_client=mock_llm_client)
        assert extractor.batch_size == 5

    def test_custom_batch_size(self, mock_llm_client):
        extractor = MetadataExtractor(llm_client=mock_llm_client, batch_size=10)
        assert extractor.batch_size == 10

    def test_provider_stored(self, mock_llm_client):
        extractor = MetadataExtractor(
            llm_client=mock_llm_client, provider=LLMProvider.GITHUB
        )
        assert extractor.provider == LLMProvider.GITHUB


class TestExportFromPackage:
    def test_metadata_extractor_importable(self):
        """Verify MetadataExtractor is exported from the extraction package."""
        from src.extraction import MetadataExtractor as ME
        assert ME is MetadataExtractor
