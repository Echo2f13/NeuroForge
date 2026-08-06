"""NeuroForge Core Module Tests.

Unit tests for core modules.
Run with: pytest tests/test_core.py -v
"""

import pytest
import json


class TestCacheModule:
    """Test the caching module."""

    def test_simple_cache_basic(self):
        """Test basic cache operations."""
        from src.cache import SimpleCache
        
        cache = SimpleCache(max_size=10, default_ttl=60)
        
        # Set and get
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Non-existent key
        assert cache.get("nonexistent") is None

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        import time
        from src.cache import SimpleCache
        
        cache = SimpleCache(max_size=10, default_ttl=0.1)  # 100ms TTL
        cache.set("key", "value")
        
        assert cache.get("key") == "value"
        time.sleep(0.2)  # Wait for expiration
        assert cache.get("key") is None

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        from src.cache import SimpleCache
        
        cache = SimpleCache(max_size=3, default_ttl=0)
        
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")
        cache.set("k4", "v4")  # Should evict oldest
        
        assert cache.get("k1") is None  # Evicted
        assert cache.get("k4") == "v4"

    def test_cache_make_key(self):
        """Test deterministic key generation."""
        from src.cache import SimpleCache
        
        cache = SimpleCache()
        
        key1 = cache.make_key({"a": 1, "b": 2})
        key2 = cache.make_key({"b": 2, "a": 1})  # Same data, different order
        
        assert key1 == key2  # Should be same due to sorting

    def test_cache_stats(self):
        """Test cache statistics."""
        from src.cache import SimpleCache
        
        cache = SimpleCache(max_size=10, default_ttl=60)
        
        cache.set("k1", "v1")
        cache.get("k1")  # Hit
        cache.get("k2")  # Miss
        
        stats = cache.stats
        assert stats.hits == 1
        assert stats.misses == 1


class TestRobustExtractor:
    """Test robust knowledge extraction."""

    def test_extract_json_from_text_direct(self):
        """Test direct JSON parsing."""
        from src.extraction.robust_extractor import extract_json_from_text
        
        text = '{"concepts": [{"name": "Test", "definition": "A test"}]}'
        result = extract_json_from_text(text)
        
        assert result is not None
        assert "concepts" in result

    def test_extract_json_from_markdown(self):
        """Test JSON extraction from markdown code block."""
        from src.extraction.robust_extractor import extract_json_from_text
        
        text = """Here is the JSON:
```json
{"concepts": [{"name": "Test", "definition": "A test"}]}
```
"""
        result = extract_json_from_text(text)
        
        assert result is not None
        assert "concepts" in result

    def test_extract_json_embedded(self):
        """Test JSON extraction when embedded in text."""
        from src.extraction.robust_extractor import extract_json_from_text
        
        text = """I found these concepts:
{"concepts": [{"name": "Steel", "definition": "An alloy of iron"}]}
Hope this helps!"""
        
        result = extract_json_from_text(text)
        
        assert result is not None
        assert result["concepts"][0]["name"] == "Steel"

    def test_parse_concepts_flexible(self):
        """Test flexible concept parsing."""
        from src.extraction.robust_extractor import parse_concepts_flexible
        
        text = '{"concepts": [{"name": "Test", "definition": "A definition", "difficulty": "medium", "keywords": ["kw1"]}]}'
        concepts = parse_concepts_flexible(text)
        
        assert len(concepts) == 1
        assert concepts[0].name == "Test"
        assert concepts[0].definition == "A definition"

    def test_parse_concepts_handles_malformed(self):
        """Test concept parsing handles malformed input gracefully."""
        from src.extraction.robust_extractor import parse_concepts_flexible
        
        text = "This is not JSON at all"
        concepts = parse_concepts_flexible(text)
        
        assert concepts == []  # Should return empty list, not raise


class TestModels:
    """Test Pydantic models."""

    def test_chunk_model(self):
        """Test Chunk model creation."""
        from models import Chunk, ChunkMetadata
        
        chunk = Chunk(
            id="test-chunk-1",
            content="This is test content",
            document_id="doc-1",
            chunk_index=0,
            metadata=ChunkMetadata(
                start_char=0,
                end_char=20,
                token_count=4
            )
        )
        
        assert chunk.id == "test-chunk-1"
        assert chunk.content == "This is test content"
        assert chunk.document_id == "doc-1"

    def test_concept_model(self):
        """Test Concept model creation."""
        from models import Concept, Difficulty
        
        concept = Concept(
            id="concept-1",
            name="Test Concept",
            definition="A test definition",
            topics=["Topic1"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=[],
            keywords=["keyword1", "keyword2"],
            source_chunk_ids=["chunk-1"]
        )
        
        assert concept.name == "Test Concept"
        assert concept.difficulty == Difficulty.MEDIUM

    def test_quiz_question_model(self):
        """Test QuizQuestion model."""
        from models import QuizQuestion
        
        question = QuizQuestion(
            id="q-1",
            question="What is steel?",
            question_type="mcq",
            options=["A", "B", "C", "D"],
            correct_answer="A",
            explanation="Steel is an alloy of iron and carbon",
            topic="Materials",
            difficulty="medium"
        )
        
        assert question.question_type == "mcq"
        assert len(question.options) == 4

    def test_flashcard_model(self):
        """Test Flashcard model."""
        from models import Flashcard
        
        card = Flashcard(
            id="fc-1",
            question="What is the melting point of steel?",
            answer="Around 1370°C to 1530°C",
            hint="It's higher than iron",
            mnemonic="Steel Starts Softening at Fourteen hundred",
            related_topics=["Steel", "Heat Treatment"],
            difficulty="medium",
            source_chunk_ids=["chunk-1"]
        )
        
        assert card.question.startswith("What is")
        assert card.mnemonic is not None


class TestLLMClient:
    """Test LLM client functionality."""

    def test_llm_client_initialization(self):
        """Test LLM client initializes properly."""
        from src.llm import LLMClient
        
        client = LLMClient()
        
        # Client should initialize without error
        assert client is not None

    def test_llm_client_has_generate(self):
        """Test LLM client has generate method."""
        from src.llm import LLMClient
        
        client = LLMClient()
        
        # Should have generate method
        assert hasattr(client, 'generate')


class TestVectorStore:
    """Test vector store operations."""

    def test_vector_store_initialization(self):
        """Test vector store initializes."""
        from src.store.vector_store import VectorStore
        
        vs = VectorStore(persist_directory="./test_chroma_db")
        vs.init_collections()
        
        stats = vs.get_stats()
        assert "chunk_count" in stats
        assert "concept_count" in stats


class TestKnowledgeGraph:
    """Test knowledge graph operations."""

    def test_graph_initialization(self):
        """Test knowledge graph initializes."""
        from src.store.knowledge_graph import KnowledgeGraph
        
        kg = KnowledgeGraph()
        assert len(kg) == 0  # Empty initially

    def test_graph_add_concepts(self):
        """Test adding concepts to graph."""
        from src.store.knowledge_graph import KnowledgeGraph
        from models import Concept, Difficulty
        
        kg = KnowledgeGraph()
        
        concepts = [
            Concept(
                id="c1",
                name="Concept 1",
                definition="Definition 1",
                topics=["Topic"],
                difficulty=Difficulty.EASY,
                prerequisites=[],
                keywords=["kw1"],
                source_chunk_ids=["chunk1"]
            )
        ]
        
        kg.add_concepts(concepts)
        assert len(kg) == 1

    def test_graph_save_load(self, tmp_path):
        """Test graph save and load."""
        from src.store.knowledge_graph import KnowledgeGraph
        from models import Concept, Difficulty
        
        kg = KnowledgeGraph()
        concepts = [
            Concept(
                id="c1",
                name="Test",
                definition="Test def",
                topics=["Test Topic"],  # Must have at least one topic
                difficulty=Difficulty.MEDIUM,
                prerequisites=[],
                keywords=[],
                source_chunk_ids=[]
            )
        ]
        kg.add_concepts(concepts)
        
        save_path = tmp_path / "test_graph.json"
        kg.save(str(save_path))
        
        # Load into new graph
        kg2 = KnowledgeGraph()
        kg2.load(str(save_path))
        
        assert len(kg2) == 1
