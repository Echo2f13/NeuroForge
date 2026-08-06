"""Pytest configuration and fixtures."""

import os
import sys

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import pytest


@pytest.fixture(scope="session")
def project_root_path():
    """Return the project root path."""
    return project_root


@pytest.fixture
def sample_text():
    """Sample text for testing."""
    return """
    Engineering Materials are substances used in construction and manufacturing.
    Steel is an alloy of iron and carbon. It has excellent strength and durability.
    Heat treatment is a process used to alter the physical properties of metals.
    """


@pytest.fixture
def sample_chunks():
    """Sample chunks for testing."""
    from models import Chunk, ChunkMetadata
    
    return [
        Chunk(
            id="chunk-1",
            content="Steel is an alloy of iron and carbon with excellent strength.",
            document_id="doc-1",
            chunk_index=0,
            metadata=ChunkMetadata(
                start_char=0,
                end_char=60,
                token_count=12
            )
        ),
        Chunk(
            id="chunk-2",
            content="Heat treatment alters the physical properties of metals.",
            document_id="doc-1",
            chunk_index=1,
            metadata=ChunkMetadata(
                start_char=61,
                end_char=120,
                token_count=10
            )
        ),
    ]


@pytest.fixture
def sample_concepts():
    """Sample concepts for testing."""
    from models import Concept, Difficulty
    
    return [
        Concept(
            id="concept-1",
            name="Steel",
            definition="An alloy of iron and carbon",
            topics=["Materials"],
            difficulty=Difficulty.EASY,
            prerequisites=[],
            keywords=["iron", "carbon", "alloy"],
            source_chunk_ids=["chunk-1"]
        ),
        Concept(
            id="concept-2",
            name="Heat Treatment",
            definition="Process to alter metal properties",
            topics=["Materials Processing"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=["concept-1"],
            keywords=["heating", "cooling", "properties"],
            source_chunk_ids=["chunk-2"]
        ),
    ]
