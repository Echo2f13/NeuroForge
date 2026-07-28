"""Tests for NeuroForge Topic & Concept Extraction.

Tests the TopicExtractor class with mocked LLM calls to verify:
- Topic extraction from chunks
- Concept extraction with definitions
- Batch processing behavior
- Deduplication logic
- Full extraction pipeline
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from models import Chunk, ChunkMetadata, Concept, Difficulty, KnowledgeExtraction
from src.extraction.topics import (
    ConceptListResponse,
    ConceptResponse,
    RelationshipListResponse,
    RelationshipResponse,
    TopicExtractor,
    TopicListResponse,
)
from src.llm import LLMClient, LLMProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_chunk(id: str, content: str, doc_id: str = "doc-1", index: int = 0) -> Chunk:
    """Helper to create a Chunk with minimal metadata."""
    return Chunk(
        id=id,
        content=content,
        document_id=doc_id,
        chunk_index=index,
        metadata=ChunkMetadata(
            token_count=len(content.split()),
            start_char=0,
            end_char=len(content),
        ),
    )


def make_concept(
    name: str,
    definition: str = "A test definition.",
    topics: list[str] | None = None,
    keywords: list[str] | None = None,
    source_chunk_ids: list[str] | None = None,
) -> Concept:
    """Helper to create a Concept for testing."""
    return Concept(
        id=f"concept-{name.lower().replace(' ', '-')}",
        name=name,
        definition=definition,
        topics=topics or ["General"],
        difficulty=Difficulty.MEDIUM,
        keywords=keywords or [],
        source_chunk_ids=source_chunk_ids or [],
    )


@pytest.fixture
def mock_llm_client():
    """Create a mock LLMClient."""
    client = MagicMock(spec=LLMClient)
    return client


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        make_chunk("chunk-1", "Machine learning is a subset of artificial intelligence."),
        make_chunk("chunk-2", "Neural networks are inspired by biological neurons."),
        make_chunk("chunk-3", "Gradient descent optimizes model parameters iteratively."),
    ]


# ---------------------------------------------------------------------------
# Topic Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractTopics:
    def test_extract_topics_single_batch(self, mock_llm_client, sample_chunks):
        """Topics are extracted from chunks in a single batch."""
        mock_llm_client.generate_json.return_value = (
            TopicListResponse(
                topics=["Machine Learning", "Neural Networks", "Optimization"]
            ),
            {"provider": "groq", "total_tokens": 100},
        )

        extractor = TopicExtractor(llm_client=mock_llm_client, batch_size=5)
        topics = extractor.extract_topics(sample_chunks)

        assert "Machine Learning" in topics
        assert "Neural Networks" in topics
        assert "Optimization" in topics
        assert mock_llm_client.generate_json.call_count == 1

    def test_extract_topics_multiple_batches(self, mock_llm_client):
        """Chunks are processed in batches when exceeding batch_size."""
        chunks = [make_chunk(f"c-{i}", f"Content about topic {i}") for i in range(7)]

        mock_llm_client.generate_json.side_effect = [
            (TopicListResponse(topics=["Topic A", "Topic B"]), {}),
            (TopicListResponse(topics=["Topic C", "Topic D"]), {}),
            (TopicListResponse(topics=["Topic E"]), {}),
        ]

        extractor = TopicExtractor(llm_client=mock_llm_client, batch_size=3)
        topics = extractor.extract_topics(chunks)

        assert mock_llm_client.generate_json.call_count == 3
        assert len(topics) == 5

    def test_extract_topics_deduplication(self, mock_llm_client):
        """Duplicate topics (case-insensitive) are removed."""
        chunks = [make_chunk("c-1", "Content"), make_chunk("c-2", "More content")]

        mock_llm_client.generate_json.side_effect = [
            (TopicListResponse(topics=["Machine Learning", "neural networks"]), {}),
            (TopicListResponse(topics=["machine learning", "Neural Networks"]), {}),
        ]

        extractor = TopicExtractor(llm_client=mock_llm_client, batch_size=1)
        topics = extractor.extract_topics(chunks)

        # Should deduplicate case-insensitively
        assert len(topics) == 2
        topic_lower = [t.lower() for t in topics]
        assert "machine learning" in topic_lower
        assert "neural networks" in topic_lower

    def test_extract_topics_empty_chunks(self, mock_llm_client):
        """Empty chunk list returns empty topics."""
        extractor = TopicExtractor(llm_client=mock_llm_client)
        topics = extractor.extract_topics([])

        assert topics == []
        mock_llm_client.generate_json.assert_not_called()

    def test_extract_topics_handles_llm_failure(self, mock_llm_client, sample_chunks):
        """LLM failures in a batch are handled gracefully."""
        mock_llm_client.generate_json.side_effect = Exception("API Error")

        extractor = TopicExtractor(llm_client=mock_llm_client)
        topics = extractor.extract_topics(sample_chunks)

        assert topics == []


# ---------------------------------------------------------------------------
# Concept Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractConcepts:
    def test_extract_concepts_success(self, mock_llm_client, sample_chunks):
        """Concepts are extracted and converted to Concept models."""
        mock_llm_client.generate_json.return_value = (
            ConceptListResponse(
                concepts=[
                    ConceptResponse(
                        name="Machine Learning",
                        definition="A subset of AI that learns from data.",
                        topics=["AI"],
                        difficulty="medium",
                        keywords=["AI", "data", "models"],
                        prerequisites=["Statistics"],
                    ),
                    ConceptResponse(
                        name="Neural Network",
                        definition="A computing system inspired by biological neurons.",
                        topics=["AI", "Deep Learning"],
                        difficulty="hard",
                        keywords=["neurons", "layers"],
                        prerequisites=["Linear Algebra"],
                    ),
                ]
            ),
            {"provider": "groq", "total_tokens": 200},
        )

        extractor = TopicExtractor(llm_client=mock_llm_client, batch_size=5)
        concepts = extractor.extract_concepts(sample_chunks, topics=["AI", "Deep Learning"])

        assert len(concepts) == 2
        assert all(isinstance(c, Concept) for c in concepts)

        ml = next(c for c in concepts if c.name == "Machine Learning")
        assert ml.definition == "A subset of AI that learns from data."
        assert ml.difficulty == Difficulty.MEDIUM
        assert "AI" in ml.keywords
        assert "Statistics" in ml.prerequisites
        # Source chunk IDs should be set from the batch
        assert len(ml.source_chunk_ids) == 3

    def test_extract_concepts_empty_inputs(self, mock_llm_client):
        """Returns empty list when chunks or topics are empty."""
        extractor = TopicExtractor(llm_client=mock_llm_client)

        assert extractor.extract_concepts([], ["Topic"]) == []
        assert extractor.extract_concepts([make_chunk("c-1", "text")], []) == []
        mock_llm_client.generate_json.assert_not_called()

    def test_extract_concepts_handles_llm_failure(self, mock_llm_client, sample_chunks):
        """LLM failures during concept extraction are handled gracefully."""
        mock_llm_client.generate_json.side_effect = Exception("Timeout")

        extractor = TopicExtractor(llm_client=mock_llm_client)
        concepts = extractor.extract_concepts(sample_chunks, ["AI"])

        assert concepts == []

    def test_extract_concepts_difficulty_mapping(self, mock_llm_client, sample_chunks):
        """Difficulty strings are correctly mapped to Difficulty enum."""
        mock_llm_client.generate_json.return_value = (
            ConceptListResponse(
                concepts=[
                    ConceptResponse(
                        name="Easy Concept",
                        definition="Simple thing.",
                        topics=["General"],
                        difficulty="easy",
                        keywords=[],
                        prerequisites=[],
                    ),
                    ConceptResponse(
                        name="Hard Concept",
                        definition="Complex thing.",
                        topics=["General"],
                        difficulty="hard",
                        keywords=[],
                        prerequisites=[],
                    ),
                ]
            ),
            {},
        )

        extractor = TopicExtractor(llm_client=mock_llm_client)
        concepts = extractor.extract_concepts(sample_chunks, ["General"])

        easy = next(c for c in concepts if c.name == "Easy Concept")
        hard = next(c for c in concepts if c.name == "Hard Concept")
        assert easy.difficulty == Difficulty.EASY
        assert hard.difficulty == Difficulty.HARD


# ---------------------------------------------------------------------------
# Deduplication Tests
# ---------------------------------------------------------------------------


class TestDeduplicateConcepts:
    def test_no_duplicates(self, mock_llm_client):
        """Concepts with unique names are not merged."""
        concepts = [
            make_concept("Concept A"),
            make_concept("Concept B"),
        ]

        extractor = TopicExtractor(llm_client=mock_llm_client)
        result = extractor.deduplicate_concepts(concepts)

        assert len(result) == 2

    def test_case_insensitive_dedup(self, mock_llm_client):
        """Concepts with same name (different case) are merged."""
        concepts = [
            make_concept("Machine Learning", definition="Short def."),
            make_concept("machine learning", definition="A longer and more complete definition here."),
        ]

        extractor = TopicExtractor(llm_client=mock_llm_client)
        result = extractor.deduplicate_concepts(concepts)

        assert len(result) == 1
        # Should keep the longer definition
        assert "longer" in result[0].definition

    def test_merge_keywords(self, mock_llm_client):
        """Keywords from duplicate concepts are merged."""
        concepts = [
            make_concept("ML", keywords=["ai", "data"]),
            make_concept("ml", keywords=["models", "data"]),
        ]

        extractor = TopicExtractor(llm_client=mock_llm_client)
        result = extractor.deduplicate_concepts(concepts)

        assert len(result) == 1
        assert "ai" in result[0].keywords
        assert "models" in result[0].keywords
        assert "data" in result[0].keywords
        # "data" should not be duplicated
        assert result[0].keywords.count("data") == 1

    def test_merge_source_chunk_ids(self, mock_llm_client):
        """Source chunk IDs from duplicates are merged."""
        concepts = [
            make_concept("Neural Net", source_chunk_ids=["c-1", "c-2"]),
            make_concept("neural net", source_chunk_ids=["c-2", "c-3"]),
        ]

        extractor = TopicExtractor(llm_client=mock_llm_client)
        result = extractor.deduplicate_concepts(concepts)

        assert len(result) == 1
        assert set(result[0].source_chunk_ids) == {"c-1", "c-2", "c-3"}

    def test_empty_list(self, mock_llm_client):
        """Empty input returns empty output."""
        extractor = TopicExtractor(llm_client=mock_llm_client)
        assert extractor.deduplicate_concepts([]) == []

    def test_merge_topics(self, mock_llm_client):
        """Topics from duplicate concepts are merged."""
        concepts = [
            make_concept("Backprop", topics=["Deep Learning"]),
            make_concept("backprop", topics=["Optimization", "Deep Learning"]),
        ]

        extractor = TopicExtractor(llm_client=mock_llm_client)
        result = extractor.deduplicate_concepts(concepts)

        assert len(result) == 1
        assert "Deep Learning" in result[0].topics
        assert "Optimization" in result[0].topics
        assert result[0].topics.count("Deep Learning") == 1


# ---------------------------------------------------------------------------
# Full Pipeline (extract_batch) Tests
# ---------------------------------------------------------------------------


class TestExtractBatch:
    def test_extract_batch_empty(self, mock_llm_client):
        """Empty chunks produce empty extraction."""
        extractor = TopicExtractor(llm_client=mock_llm_client)
        result = extractor.extract_batch([])

        assert isinstance(result, KnowledgeExtraction)
        assert result.concepts == []
        assert result.relationships == []

    def test_extract_batch_full_pipeline(self, mock_llm_client, sample_chunks):
        """Full pipeline: topics → concepts → relationships."""
        # Mock topic extraction
        topic_response = (
            TopicListResponse(topics=["AI", "Machine Learning"]),
            {},
        )
        # Mock concept extraction
        concept_response = (
            ConceptListResponse(
                concepts=[
                    ConceptResponse(
                        name="AI",
                        definition="Artificial Intelligence is the simulation of human intelligence.",
                        topics=["AI"],
                        difficulty="medium",
                        keywords=["intelligence"],
                        prerequisites=[],
                    ),
                    ConceptResponse(
                        name="ML",
                        definition="Machine Learning is a subset of AI.",
                        topics=["Machine Learning"],
                        difficulty="easy",
                        keywords=["learning"],
                        prerequisites=["AI"],
                    ),
                ]
            ),
            {},
        )
        # Mock relationship extraction
        relationship_response = (
            RelationshipListResponse(
                relationships=[
                    RelationshipResponse(
                        source="AI",
                        target="ML",
                        relationship_type="prerequisite",
                    )
                ]
            ),
            {},
        )

        mock_llm_client.generate_json.side_effect = [
            topic_response,
            concept_response,
            relationship_response,
        ]

        extractor = TopicExtractor(llm_client=mock_llm_client, batch_size=5)
        result = extractor.extract_batch(sample_chunks)

        assert isinstance(result, KnowledgeExtraction)
        assert len(result.concepts) == 2
        assert len(result.relationships) == 1
        assert result.relationships[0].relationship_type == "prerequisite"


# ---------------------------------------------------------------------------
# Batch Processing Tests
# ---------------------------------------------------------------------------


class TestBatchProcessing:
    def test_batch_chunks_exact(self, mock_llm_client):
        """Chunks split exactly into batch_size groups."""
        extractor = TopicExtractor(llm_client=mock_llm_client, batch_size=3)
        chunks = [make_chunk(f"c-{i}", f"text {i}") for i in range(6)]
        batches = extractor._batch_chunks(chunks)

        assert len(batches) == 2
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3

    def test_batch_chunks_remainder(self, mock_llm_client):
        """Remaining chunks form a smaller final batch."""
        extractor = TopicExtractor(llm_client=mock_llm_client, batch_size=3)
        chunks = [make_chunk(f"c-{i}", f"text {i}") for i in range(7)]
        batches = extractor._batch_chunks(chunks)

        assert len(batches) == 3
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3
        assert len(batches[2]) == 1

    def test_batch_chunks_single_item(self, mock_llm_client):
        """Single chunk produces one batch."""
        extractor = TopicExtractor(llm_client=mock_llm_client, batch_size=5)
        chunks = [make_chunk("c-1", "text")]
        batches = extractor._batch_chunks(chunks)

        assert len(batches) == 1
        assert len(batches[0]) == 1
