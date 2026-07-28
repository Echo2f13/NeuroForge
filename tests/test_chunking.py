"""Tests for the DocumentChunker module."""

from __future__ import annotations

import hashlib

import pytest
import tiktoken

from models import Chunk, ChunkMetadata, Document, DocumentMetadata, InputFormat, Section
from src.processing.chunking import DocumentChunker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def encoding():
    """Shared tiktoken encoding for verification."""
    return tiktoken.get_encoding("cl100k_base")


@pytest.fixture
def chunker():
    """Default DocumentChunker instance."""
    return DocumentChunker(max_tokens=500, overlap=50)


@pytest.fixture
def small_chunker():
    """Chunker with small max_tokens for easier testing."""
    return DocumentChunker(max_tokens=20, overlap=5)


@pytest.fixture
def simple_document():
    """A simple document with short content."""
    return Document(
        content="This is a simple test document with a single paragraph.",
        metadata=DocumentMetadata(
            source="test_file.pdf",
            format=InputFormat.PDF,
        ),
    )


@pytest.fixture
def sectioned_document():
    """A document with markdown headings."""
    content = (
        "# Introduction\n\n"
        "This is the introduction section with some content.\n\n"
        "## Background\n\n"
        "Here is background information about the topic.\n\n"
        "## Methods\n\n"
        "We used the following methods in our research."
    )
    return Document(
        content=content,
        metadata=DocumentMetadata(
            source="research_paper.md",
            format=InputFormat.MARKDOWN,
        ),
    )


@pytest.fixture
def document_with_sections():
    """A document with pre-parsed Section objects."""
    content = "Introduction content here.\n\nMethods content here."
    return Document(
        content=content,
        metadata=DocumentMetadata(
            source="structured.docx",
            format=InputFormat.DOCX,
        ),
        sections=[
            Section(heading="Introduction", content="Introduction content here.", level=1),
            Section(heading="Methods", content="Methods content here.", level=2),
        ],
    )


@pytest.fixture
def long_document():
    """A document long enough to require multiple token chunks."""
    # Generate text that will be ~200 tokens repeated to exceed 500 tokens
    paragraph = "The quick brown fox jumps over the lazy dog. " * 50
    content = paragraph.strip()
    return Document(
        content=content,
        metadata=DocumentMetadata(
            source="long_text.txt",
            format=InputFormat.TEXT,
        ),
    )


@pytest.fixture
def multi_paragraph_document():
    """A document with multiple paragraphs separated by double newlines."""
    content = (
        "First paragraph with some introductory content.\n\n"
        "Second paragraph explains the details of the topic.\n\n"
        "Third paragraph concludes the document with a summary."
    )
    return Document(
        content=content,
        metadata=DocumentMetadata(
            source="paragraphs.txt",
            format=InputFormat.TEXT,
        ),
    )


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------


class TestDocumentChunkerInit:
    """Tests for DocumentChunker initialization."""

    def test_default_parameters(self):
        chunker = DocumentChunker()
        assert chunker.max_tokens == 500
        assert chunker.overlap == 50

    def test_custom_parameters(self):
        chunker = DocumentChunker(max_tokens=1000, overlap=100)
        assert chunker.max_tokens == 1000
        assert chunker.overlap == 100


# ---------------------------------------------------------------------------
# Tests: chunk() dispatch
# ---------------------------------------------------------------------------


class TestChunkDispatch:
    """Tests for the main chunk() entry point."""

    def test_invalid_strategy_raises(self, chunker, simple_document):
        with pytest.raises(ValueError, match="Unknown strategy"):
            chunker.chunk(simple_document, strategy="invalid")

    def test_section_strategy(self, chunker, simple_document):
        chunks = chunker.chunk(simple_document, strategy="section")
        assert isinstance(chunks, list)
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_paragraph_strategy(self, chunker, simple_document):
        chunks = chunker.chunk(simple_document, strategy="paragraph")
        assert isinstance(chunks, list)
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_token_strategy(self, chunker, simple_document):
        chunks = chunker.chunk(simple_document, strategy="token")
        assert isinstance(chunks, list)
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_default_strategy_is_section(self, chunker, simple_document):
        default_chunks = chunker.chunk(simple_document)
        section_chunks = chunker.chunk(simple_document, strategy="section")
        assert len(default_chunks) == len(section_chunks)
        for d, s in zip(default_chunks, section_chunks):
            assert d.content == s.content


# ---------------------------------------------------------------------------
# Tests: chunk_by_tokens()
# ---------------------------------------------------------------------------


class TestChunkByTokens:
    """Tests for pure token-based splitting."""

    def test_short_text_single_chunk(self, chunker):
        text = "Hello world"
        result = chunker.chunk_by_tokens(text)
        assert result == [text]

    def test_respects_max_tokens(self, small_chunker, encoding):
        text = "word " * 100  # Much longer than 20 tokens
        chunks = small_chunker.chunk_by_tokens(text)
        for chunk_text in chunks:
            token_count = len(encoding.encode(chunk_text))
            assert token_count <= small_chunker.max_tokens

    def test_overlap_between_chunks(self, encoding):
        chunker = DocumentChunker(max_tokens=20, overlap=5)
        text = "word " * 100
        chunks = chunker.chunk_by_tokens(text)
        assert len(chunks) > 1

        # Check that consecutive chunks share tokens
        for i in range(len(chunks) - 1):
            tokens_a = encoding.encode(chunks[i])
            tokens_b = encoding.encode(chunks[i + 1])
            # The last `overlap` tokens of chunk A should match
            # the first `overlap` tokens of chunk B
            overlap_a = tokens_a[-chunker.overlap:]
            overlap_b = tokens_b[: chunker.overlap]
            assert overlap_a == overlap_b

    def test_custom_max_tokens_and_overlap(self, chunker):
        text = "token " * 200
        chunks = chunker.chunk_by_tokens(text, max_tokens=30, overlap=10)
        assert len(chunks) > 1

    def test_empty_text_returns_single_chunk(self, chunker):
        # Empty string encodes to 0 tokens, which is <= max_tokens
        result = chunker.chunk_by_tokens("")
        assert result == [""]


# ---------------------------------------------------------------------------
# Tests: chunk_by_section()
# ---------------------------------------------------------------------------


class TestChunkBySection:
    """Tests for section-aware chunking."""

    def test_uses_heading_boundaries(self, chunker, sectioned_document):
        chunks = chunker.chunk_by_section(sectioned_document)
        assert len(chunks) >= 3  # At least one chunk per section

    def test_uses_pre_parsed_sections(self, chunker, document_with_sections):
        chunks = chunker.chunk_by_section(document_with_sections)
        assert len(chunks) == 2
        assert chunks[0].metadata.section_heading == "Introduction"
        assert chunks[1].metadata.section_heading == "Methods"

    def test_chunk_ids_format(self, chunker, sectioned_document):
        chunks = chunker.chunk_by_section(sectioned_document)
        source_hash = hashlib.sha256(
            sectioned_document.metadata.source.encode("utf-8")
        ).hexdigest()[:8]
        for i, chunk in enumerate(chunks):
            assert chunk.id == f"{source_hash}_{i:04d}"

    def test_chunk_ordering(self, chunker, sectioned_document):
        chunks = chunker.chunk_by_section(sectioned_document)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_large_section_gets_sub_chunked(self, small_chunker, encoding):
        """A section longer than max_tokens should be split further."""
        long_content = "word " * 100
        doc = Document(
            content=f"# Big Section\n\n{long_content}",
            metadata=DocumentMetadata(source="big.md", format=InputFormat.MARKDOWN),
        )
        chunks = small_chunker.chunk_by_section(doc)
        assert len(chunks) > 1
        for chunk in chunks:
            token_count = len(encoding.encode(chunk.content))
            assert token_count <= small_chunker.max_tokens


# ---------------------------------------------------------------------------
# Tests: chunk_by_paragraph()
# ---------------------------------------------------------------------------


class TestChunkByParagraph:
    """Tests for paragraph-aware chunking."""

    def test_splits_on_double_newline(self, chunker, multi_paragraph_document):
        chunks = chunker.chunk_by_paragraph(multi_paragraph_document)
        assert len(chunks) == 3

    def test_preserves_paragraph_content(self, chunker, multi_paragraph_document):
        chunks = chunker.chunk_by_paragraph(multi_paragraph_document)
        assert "First paragraph" in chunks[0].content
        assert "Second paragraph" in chunks[1].content
        assert "Third paragraph" in chunks[2].content

    def test_large_paragraph_gets_sub_chunked(self, small_chunker, encoding):
        """A paragraph exceeding max_tokens should be split."""
        long_para = "word " * 100
        doc = Document(
            content=long_para,
            metadata=DocumentMetadata(source="long_para.txt", format=InputFormat.TEXT),
        )
        chunks = small_chunker.chunk_by_paragraph(doc)
        assert len(chunks) > 1
        for chunk in chunks:
            token_count = len(encoding.encode(chunk.content))
            assert token_count <= small_chunker.max_tokens


# ---------------------------------------------------------------------------
# Tests: Metadata
# ---------------------------------------------------------------------------


class TestChunkMetadata:
    """Tests for chunk metadata assignment."""

    def test_token_count_accurate(self, chunker, simple_document, encoding):
        chunks = chunker.chunk(simple_document)
        for chunk in chunks:
            expected = len(encoding.encode(chunk.content))
            assert chunk.metadata.token_count == expected

    def test_start_end_char_valid(self, chunker, sectioned_document):
        chunks = chunker.chunk(sectioned_document)
        for chunk in chunks:
            assert chunk.metadata.start_char >= 0
            assert chunk.metadata.end_char >= chunk.metadata.start_char

    def test_document_id_is_source_hash(self, chunker, simple_document):
        chunks = chunker.chunk(simple_document)
        expected_hash = hashlib.sha256(
            simple_document.metadata.source.encode("utf-8")
        ).hexdigest()[:8]
        for chunk in chunks:
            assert chunk.document_id == expected_hash

    def test_section_heading_in_metadata(self, chunker, sectioned_document):
        chunks = chunker.chunk_by_section(sectioned_document)
        # At least one chunk should have a section heading
        headings = [c.metadata.section_heading for c in chunks]
        assert any(h is not None for h in headings)


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_word_document(self, chunker):
        doc = Document(
            content="Hello",
            metadata=DocumentMetadata(source="single.txt", format=InputFormat.TEXT),
        )
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].content == "Hello"

    def test_no_sections_uses_full_content(self, chunker):
        doc = Document(
            content="No headings here, just plain text content.",
            metadata=DocumentMetadata(source="plain.txt", format=InputFormat.TEXT),
        )
        chunks = chunker.chunk_by_section(doc)
        assert len(chunks) == 1
        assert "No headings here" in chunks[0].content

    def test_consistent_chunk_ids_across_calls(self, chunker, simple_document):
        chunks_a = chunker.chunk(simple_document)
        chunks_b = chunker.chunk(simple_document)
        for a, b in zip(chunks_a, chunks_b):
            assert a.id == b.id
