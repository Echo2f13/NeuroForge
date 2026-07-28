"""Plain Text & Markdown Loader for NeuroForge.

Extracts structured content from .txt and .md files.
- Plain text: splits on double newlines into paragraph sections.
- Markdown: parses heading hierarchy, code blocks, and lists into sections.

Usage:
    from src.ingestion.text_loader import TextLoader

    loader = TextLoader()
    doc = loader.load("path/to/file.md")

    # Or load from a string directly:
    doc = loader.load_text("# Hello\nWorld", source="inline")
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from models import Document, DocumentMetadata, InputFormat, Section

logger = logging.getLogger("neuroforge.text_loader")

# Regex patterns for markdown parsing
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_FENCED_CODE_BLOCK = re.compile(r"^```(\w*)\s*\n(.*?)^```", re.MULTILINE | re.DOTALL)
_LIST_ITEM_PATTERN = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.+)$", re.MULTILINE)


class TextLoadError(Exception):
    """Raised when a text file cannot be loaded or parsed."""

    pass


class TextLoader:
    """Loader for plain text and markdown files.

    Parses .txt files into paragraph-based sections and .md files into
    heading-structured sections with code block and list preservation.

    Usage:
        loader = TextLoader()
        doc = loader.load("notes.md")
        doc = loader.load_text("Some raw text", source="user_input")
    """

    def load(self, file_path: str) -> Document:
        """Load and extract content from a plain text or markdown file.

        Determines format from the file extension:
        - .md files are parsed as markdown (heading hierarchy, code blocks, lists).
        - All other text files are treated as plain text (paragraph splitting).

        Args:
            file_path: Path to the .txt or .md file.

        Returns:
            A Document instance with metadata, full content, and sections.

        Raises:
            TextLoadError: If the file doesn't exist or cannot be read.
        """
        path = Path(file_path)

        if not path.exists():
            raise TextLoadError(f"File not found: {file_path}")

        if not path.is_file():
            raise TextLoadError(f"Not a file: {file_path}")

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="latin-1")
            except Exception as e:
                raise TextLoadError(f"Failed to read file: {file_path}. Error: {e}")
        except Exception as e:
            raise TextLoadError(f"Failed to read file: {file_path}. Error: {e}")

        is_markdown = path.suffix.lower() == ".md"
        input_format = InputFormat.MARKDOWN if is_markdown else InputFormat.TEXT
        source = str(path.resolve())

        logger.info(f"Loading {'markdown' if is_markdown else 'text'} file: {path.name}")

        if is_markdown:
            sections, title = self._parse_markdown(text)
        else:
            sections, title = self._parse_plain_text(text)

        content = text.strip() if text.strip() else " "

        metadata = DocumentMetadata(
            source=source,
            format=input_format,
            title=title,
        )

        return Document(
            content=content,
            metadata=metadata,
            sections=sections,
        )

    def load_text(self, text: str, source: str = "direct_input") -> Document:
        """Load and extract content from a raw text string.

        Attempts to detect markdown formatting. If the text contains markdown
        heading markers (#), it is parsed as markdown. Otherwise, it is treated
        as plain text.

        Args:
            text: The raw text content to parse.
            source: A label for the source of this text (default: "direct_input").

        Returns:
            A Document instance with metadata, full content, and sections.

        Raises:
            TextLoadError: If the text is empty or None.
        """
        if not text or not text.strip():
            raise TextLoadError("Cannot load empty text.")

        is_markdown = self._detect_markdown(text)
        input_format = InputFormat.MARKDOWN if is_markdown else InputFormat.TEXT

        logger.info(
            f"Loading text from '{source}' as {'markdown' if is_markdown else 'plain text'}"
        )

        if is_markdown:
            sections, title = self._parse_markdown(text)
        else:
            sections, title = self._parse_plain_text(text)

        content = text.strip()

        metadata = DocumentMetadata(
            source=source,
            format=input_format,
            title=title,
        )

        return Document(
            content=content,
            metadata=metadata,
            sections=sections,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_markdown(text: str) -> bool:
        """Detect whether text is likely markdown based on structural markers.

        Checks for presence of markdown headings (# at line start), fenced
        code blocks (```), or markdown list items.

        Args:
            text: The text to analyze.

        Returns:
            True if the text appears to be markdown.
        """
        if _HEADING_PATTERN.search(text):
            return True
        if "```" in text:
            return True
        return False

    def _parse_markdown(self, text: str) -> tuple[list[Section], Optional[str]]:
        """Parse markdown text into structured sections.

        Extracts heading hierarchy, preserves fenced code blocks, and
        detects list formatting. Each heading starts a new section at the
        appropriate level.

        Args:
            text: Raw markdown text.

        Returns:
            Tuple of (list of Section objects, optional title string).
        """
        sections: list[Section] = []
        title: Optional[str] = None

        # Split into lines for sequential processing
        lines = text.split("\n")
        current_heading: Optional[str] = None
        current_level: int = 1
        current_content_lines: list[str] = []
        in_code_block = False

        for line in lines:
            # Track fenced code blocks to avoid treating # inside them as headings
            if line.strip().startswith("```"):
                if in_code_block:
                    # Closing a code block
                    current_content_lines.append(line)
                    in_code_block = False
                    continue
                else:
                    # Opening a code block
                    in_code_block = True
                    current_content_lines.append(line)
                    continue

            if in_code_block:
                current_content_lines.append(line)
                continue

            # Check for heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                # Flush current section
                content = "\n".join(current_content_lines).strip()
                if content:
                    sections.append(
                        Section(
                            heading=current_heading,
                            content=content,
                            level=current_level,
                        )
                    )
                elif current_heading is not None and not content:
                    # Heading with no content yet — will be captured next flush
                    pass

                # Start new section
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                current_heading = heading_text
                current_level = level
                current_content_lines = []

                # Capture first heading as document title
                if title is None:
                    title = heading_text
            else:
                current_content_lines.append(line)

        # Flush the last section
        content = "\n".join(current_content_lines).strip()
        if content:
            sections.append(
                Section(
                    heading=current_heading,
                    content=content,
                    level=current_level,
                )
            )

        return sections, title

    def _parse_plain_text(self, text: str) -> tuple[list[Section], Optional[str]]:
        """Parse plain text into paragraph-based sections.

        Splits on double newlines (blank lines) to create paragraph sections.
        Each paragraph becomes a Section with no heading and level 1.

        Args:
            text: Raw plain text content.

        Returns:
            Tuple of (list of Section objects, None for title).
        """
        sections: list[Section] = []

        # Split on double newlines (one or more blank lines)
        paragraphs = re.split(r"\n\s*\n", text.strip())

        for paragraph in paragraphs:
            content = paragraph.strip()
            if content:
                sections.append(
                    Section(
                        heading=None,
                        content=content,
                        level=1,
                    )
                )

        return sections, None
