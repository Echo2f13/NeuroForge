"""Intelligent Chunking Module for NeuroForge.

Provides the DocumentChunker class which splits documents into smaller,
semantically meaningful chunks for downstream embedding and retrieval.

Supported strategies:
- "section": Split at heading boundaries first, then token-chunk within sections.
- "paragraph": Split on paragraph boundaries (double newlines).
- "token": Pure token-based sliding window with configurable overlap.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

import tiktoken

from models import Chunk, ChunkMetadata, Document


class DocumentChunker:
    """Splits documents into chunks using configurable strategies.

    Attributes:
        max_tokens: Maximum number of tokens per chunk (default 500).
        overlap: Number of overlapping tokens between consecutive chunks (default 50).
    """

    # Heading pattern to detect markdown-style headings (# Heading)
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def __init__(self, max_tokens: int = 500, overlap: int = 50) -> None:
        """Initialize the DocumentChunker.

        Args:
            max_tokens: Maximum tokens per chunk.
            overlap: Token overlap between consecutive chunks.
        """
        self.max_tokens = max_tokens
        self.overlap = overlap
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def chunk(self, document: Document, strategy: str = "section") -> list[Chunk]:
        """Main entry point for chunking a document.

        Args:
            document: The Document object to chunk.
            strategy: Chunking strategy — "section", "paragraph", or "token".

        Returns:
            Ordered list of Chunk objects.

        Raises:
            ValueError: If strategy is not one of the supported values.
        """
        strategies = {
            "section": self.chunk_by_section,
            "paragraph": self.chunk_by_paragraph,
            "token": self._chunk_by_token_strategy,
        }

        if strategy not in strategies:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Supported: {list(strategies.keys())}"
            )

        return strategies[strategy](document)

    def chunk_by_section(self, document: Document) -> list[Chunk]:
        """Split document at section boundaries, then token-chunk within sections.

        If the document has pre-parsed sections, those are used directly.
        Otherwise, sections are detected via markdown heading patterns.

        Args:
            document: The Document to chunk.

        Returns:
            Ordered list of Chunk objects.
        """
        source_hash = self._source_hash(document)
        sections = self._get_sections(document)

        chunks: list[Chunk] = []
        chunk_index = 0

        for heading, content, page_number in sections:
            if not content.strip():
                continue

            # Token-chunk within this section if it exceeds max_tokens
            token_chunks = self.chunk_by_tokens(content)

            for text_piece in token_chunks:
                start_char = document.content.find(text_piece)
                if start_char == -1:
                    # Fallback: approximate position
                    start_char = 0
                end_char = start_char + len(text_piece)
                token_count = len(self._encoding.encode(text_piece))

                metadata = ChunkMetadata(
                    section_heading=heading,
                    page_number=page_number,
                    token_count=token_count,
                    start_char=start_char,
                    end_char=end_char,
                )

                chunk_id = f"{source_hash}_{chunk_index:04d}"
                chunk = Chunk(
                    id=chunk_id,
                    content=text_piece,
                    document_id=source_hash,
                    chunk_index=chunk_index,
                    metadata=metadata,
                )
                chunks.append(chunk)
                chunk_index += 1

        return chunks

    def chunk_by_paragraph(self, document: Document) -> list[Chunk]:
        """Split document on paragraph boundaries (double newlines).

        Paragraphs that exceed max_tokens are further split using
        token-based chunking.

        Args:
            document: The Document to chunk.

        Returns:
            Ordered list of Chunk objects.
        """
        source_hash = self._source_hash(document)
        content = document.content

        # Split on double newlines (paragraph boundaries)
        paragraphs = re.split(r"\n\s*\n", content)

        chunks: list[Chunk] = []
        chunk_index = 0
        current_pos = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                # Advance position past the whitespace
                current_pos = content.find("\n\n", current_pos)
                if current_pos != -1:
                    current_pos += 2
                continue

            # Find the actual position in the original content
            start_char = content.find(paragraph, current_pos)
            if start_char == -1:
                start_char = current_pos

            token_count = len(self._encoding.encode(paragraph))

            if token_count <= self.max_tokens:
                # Paragraph fits in one chunk
                end_char = start_char + len(paragraph)
                metadata = ChunkMetadata(
                    section_heading=self._find_section_heading(
                        document, start_char
                    ),
                    page_number=None,
                    token_count=token_count,
                    start_char=start_char,
                    end_char=end_char,
                )
                chunk_id = f"{source_hash}_{chunk_index:04d}"
                chunk = Chunk(
                    id=chunk_id,
                    content=paragraph,
                    document_id=source_hash,
                    chunk_index=chunk_index,
                    metadata=metadata,
                )
                chunks.append(chunk)
                chunk_index += 1
            else:
                # Paragraph is too large — sub-chunk with token-based splitting
                sub_chunks = self.chunk_by_tokens(paragraph)
                sub_pos = start_char
                for sub_text in sub_chunks:
                    sub_start = content.find(sub_text, sub_pos)
                    if sub_start == -1:
                        sub_start = sub_pos
                    sub_end = sub_start + len(sub_text)
                    sub_token_count = len(self._encoding.encode(sub_text))

                    metadata = ChunkMetadata(
                        section_heading=self._find_section_heading(
                            document, sub_start
                        ),
                        page_number=None,
                        token_count=sub_token_count,
                        start_char=sub_start,
                        end_char=sub_end,
                    )
                    chunk_id = f"{source_hash}_{chunk_index:04d}"
                    chunk = Chunk(
                        id=chunk_id,
                        content=sub_text,
                        document_id=source_hash,
                        chunk_index=chunk_index,
                        metadata=metadata,
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    sub_pos = sub_end

            current_pos = start_char + len(paragraph)

        return chunks

    def chunk_by_tokens(
        self, text: str, max_tokens: Optional[int] = None, overlap: Optional[int] = None
    ) -> list[str]:
        """Pure token-based splitting with overlap.

        Splits text into chunks of at most max_tokens tokens, with overlap
        tokens repeated between consecutive chunks.

        Args:
            text: The text to split.
            max_tokens: Maximum tokens per chunk (defaults to self.max_tokens).
            overlap: Overlap between chunks (defaults to self.overlap).

        Returns:
            List of text strings, each within the token limit.
        """
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        overlap = overlap if overlap is not None else self.overlap

        tokens = self._encoding.encode(text)

        if len(tokens) <= max_tokens:
            return [text]

        chunks: list[str] = []
        start = 0

        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self._encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

            if end >= len(tokens):
                break

            # Advance by (max_tokens - overlap) to create overlap
            start += max_tokens - overlap

        return chunks

    def _chunk_by_token_strategy(self, document: Document) -> list[Chunk]:
        """Token-based chunking strategy entry point for a full document.

        Args:
            document: The Document to chunk.

        Returns:
            Ordered list of Chunk objects.
        """
        source_hash = self._source_hash(document)
        content = document.content
        text_chunks = self.chunk_by_tokens(content)

        chunks: list[Chunk] = []
        current_pos = 0

        for chunk_index, text_piece in enumerate(text_chunks):
            start_char = content.find(text_piece, current_pos)
            if start_char == -1:
                start_char = current_pos
            end_char = start_char + len(text_piece)
            token_count = len(self._encoding.encode(text_piece))

            metadata = ChunkMetadata(
                section_heading=self._find_section_heading(document, start_char),
                page_number=None,
                token_count=token_count,
                start_char=start_char,
                end_char=end_char,
            )

            chunk_id = f"{source_hash}_{chunk_index:04d}"
            chunk = Chunk(
                id=chunk_id,
                content=text_piece,
                document_id=source_hash,
                chunk_index=chunk_index,
                metadata=metadata,
            )
            chunks.append(chunk)
            current_pos = start_char + len(text_piece) - self.overlap

        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _source_hash(self, document: Document) -> str:
        """Generate an 8-char SHA-256 hex digest of the document source.

        Args:
            document: The document whose source to hash.

        Returns:
            First 8 characters of the SHA-256 hex digest.
        """
        source = document.metadata.source
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:8]

    def _get_sections(
        self, document: Document
    ) -> list[tuple[Optional[str], str, Optional[int]]]:
        """Extract sections from document.

        Uses pre-parsed sections if available, otherwise detects headings
        from the content.

        Returns:
            List of (heading, content, page_number) tuples.
        """
        if document.sections:
            return [
                (section.heading, section.content, section.page_number)
                for section in document.sections
            ]

        # Parse sections from content using heading patterns
        content = document.content
        matches = list(self.HEADING_PATTERN.finditer(content))

        if not matches:
            # No headings found — treat entire content as one section
            return [(None, content, None)]

        sections: list[tuple[Optional[str], str, Optional[int]]] = []

        # Content before the first heading
        if matches[0].start() > 0:
            preamble = content[: matches[0].start()].strip()
            if preamble:
                sections.append((None, preamble, None))

        # Each heading and its content
        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start:end].strip()
            if section_content:
                sections.append((heading, section_content, None))

        return sections

    def _find_section_heading(
        self, document: Document, char_pos: int
    ) -> Optional[str]:
        """Find the section heading that contains the given character position.

        Args:
            document: The source document.
            char_pos: Character position in the document content.

        Returns:
            The heading string, or None if not within a headed section.
        """
        content = document.content
        matches = list(self.HEADING_PATTERN.finditer(content))

        if not matches:
            return None

        # Find the last heading before char_pos
        current_heading: Optional[str] = None
        for match in matches:
            if match.start() <= char_pos:
                current_heading = match.group(2).strip()
            else:
                break

        return current_heading
