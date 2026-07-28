"""Tests for the Plain Text & Markdown Loader.

Creates sample .txt and .md files in-memory and verifies extraction
of headings, paragraphs, code blocks, and lists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from models.document import Document, InputFormat, Section
from src.ingestion.text_loader import TextLoadError, TextLoader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def loader() -> TextLoader:
    """Provide a TextLoader instance."""
    return TextLoader()


@pytest.fixture
def plain_text_file(tmp_path) -> Path:
    """Create a simple plain text file with paragraphs."""
    content = (
        "This is the first paragraph of the document.\n"
        "It has multiple lines within the same paragraph.\n"
        "\n"
        "This is the second paragraph, separated by a blank line.\n"
        "\n"
        "And a third paragraph for good measure."
    )
    file_path = tmp_path / "sample.txt"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def markdown_file(tmp_path) -> Path:
    """Create a markdown file with headings, code blocks, and lists."""
    content = (
        "# Project Title\n"
        "\n"
        "Introduction paragraph here.\n"
        "\n"
        "## Installation\n"
        "\n"
        "Run the following command:\n"
        "\n"
        "```bash\n"
        "pip install neuroforge\n"
        "```\n"
        "\n"
        "## Features\n"
        "\n"
        "- Feature one\n"
        "- Feature two\n"
        "- Feature three\n"
        "\n"
        "### Sub-features\n"
        "\n"
        "1. Sub-feature A\n"
        "2. Sub-feature B\n"
    )
    file_path = tmp_path / "readme.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def markdown_with_code_heading(tmp_path) -> Path:
    """Create markdown with a heading-like pattern inside a code block."""
    content = (
        "# Real Heading\n"
        "\n"
        "Some text.\n"
        "\n"
        "```python\n"
        "# This is a comment, not a heading\n"
        "def hello():\n"
        "    pass\n"
        "```\n"
        "\n"
        "## Another Heading\n"
        "\n"
        "More text after code.\n"
    )
    file_path = tmp_path / "code_example.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def empty_file(tmp_path) -> Path:
    """Create an empty text file."""
    file_path = tmp_path / "empty.txt"
    file_path.write_text("", encoding="utf-8")
    return file_path


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------


class TestTextLoaderErrors:
    def test_file_not_found(self, loader):
        with pytest.raises(TextLoadError, match="File not found"):
            loader.load("/nonexistent/path/file.txt")

    def test_not_a_file(self, loader, tmp_path):
        with pytest.raises(TextLoadError, match="Not a file"):
            loader.load(str(tmp_path))

    def test_empty_text_string(self, loader):
        with pytest.raises(TextLoadError, match="Cannot load empty text"):
            loader.load_text("")

    def test_whitespace_only_text(self, loader):
        with pytest.raises(TextLoadError, match="Cannot load empty text"):
            loader.load_text("   \n\n  ")


# ---------------------------------------------------------------------------
# Plain Text Loading Tests
# ---------------------------------------------------------------------------


class TestPlainTextLoading:
    def test_returns_document(self, loader, plain_text_file):
        result = loader.load(str(plain_text_file))
        assert isinstance(result, Document)

    def test_metadata_format_is_text(self, loader, plain_text_file):
        result = loader.load(str(plain_text_file))
        assert result.metadata.format == InputFormat.TEXT

    def test_metadata_source(self, loader, plain_text_file):
        result = loader.load(str(plain_text_file))
        assert "sample.txt" in result.metadata.source

    def test_content_preserved(self, loader, plain_text_file):
        result = loader.load(str(plain_text_file))
        assert "first paragraph" in result.content
        assert "second paragraph" in result.content
        assert "third paragraph" in result.content

    def test_paragraphs_become_sections(self, loader, plain_text_file):
        result = loader.load(str(plain_text_file))
        assert len(result.sections) == 3

    def test_sections_have_no_heading(self, loader, plain_text_file):
        result = loader.load(str(plain_text_file))
        for section in result.sections:
            assert section.heading is None

    def test_sections_level_is_one(self, loader, plain_text_file):
        result = loader.load(str(plain_text_file))
        for section in result.sections:
            assert section.level == 1

    def test_title_is_none_for_plain_text(self, loader, plain_text_file):
        result = loader.load(str(plain_text_file))
        assert result.metadata.title is None


# ---------------------------------------------------------------------------
# Markdown Loading Tests
# ---------------------------------------------------------------------------


class TestMarkdownLoading:
    def test_returns_document(self, loader, markdown_file):
        result = loader.load(str(markdown_file))
        assert isinstance(result, Document)

    def test_metadata_format_is_markdown(self, loader, markdown_file):
        result = loader.load(str(markdown_file))
        assert result.metadata.format == InputFormat.MARKDOWN

    def test_title_from_first_heading(self, loader, markdown_file):
        result = loader.load(str(markdown_file))
        assert result.metadata.title == "Project Title"

    def test_heading_hierarchy(self, loader, markdown_file):
        result = loader.load(str(markdown_file))
        headings = {s.heading: s.level for s in result.sections if s.heading}
        assert headings.get("Project Title") == 1 or "Project Title" in [
            s.heading for s in result.sections
        ]
        assert headings.get("Installation") == 2
        assert headings.get("Features") == 2
        assert headings.get("Sub-features") == 3

    def test_code_block_preserved(self, loader, markdown_file):
        result = loader.load(str(markdown_file))
        # Find the Installation section
        install_section = next(
            (s for s in result.sections if s.heading == "Installation"), None
        )
        assert install_section is not None
        assert "```bash" in install_section.content
        assert "pip install neuroforge" in install_section.content
        assert "```" in install_section.content

    def test_list_items_preserved(self, loader, markdown_file):
        result = loader.load(str(markdown_file))
        features_section = next(
            (s for s in result.sections if s.heading == "Features"), None
        )
        assert features_section is not None
        assert "- Feature one" in features_section.content
        assert "- Feature two" in features_section.content

    def test_numbered_list_preserved(self, loader, markdown_file):
        result = loader.load(str(markdown_file))
        sub_section = next(
            (s for s in result.sections if s.heading == "Sub-features"), None
        )
        assert sub_section is not None
        assert "1. Sub-feature A" in sub_section.content

    def test_code_block_not_treated_as_heading(self, loader, markdown_with_code_heading):
        result = loader.load(str(markdown_with_code_heading))
        headings = [s.heading for s in result.sections if s.heading]
        # The comment inside the code block should NOT be a heading
        assert "This is a comment, not a heading" not in headings
        assert "Real Heading" in headings
        assert "Another Heading" in headings


# ---------------------------------------------------------------------------
# load_text() Tests
# ---------------------------------------------------------------------------


class TestLoadText:
    def test_plain_text_detection(self, loader):
        result = loader.load_text("Hello world.\n\nAnother paragraph.")
        assert result.metadata.format == InputFormat.TEXT

    def test_markdown_detection(self, loader):
        result = loader.load_text("# Title\n\nSome content.")
        assert result.metadata.format == InputFormat.MARKDOWN

    def test_source_metadata(self, loader):
        result = loader.load_text("Hello", source="my_source")
        assert result.metadata.source == "my_source"

    def test_default_source(self, loader):
        result = loader.load_text("Hello world content here.")
        assert result.metadata.source == "direct_input"

    def test_code_block_triggers_markdown_detection(self, loader):
        text = "Some intro.\n\n```python\nprint('hi')\n```\n"
        result = loader.load_text(text)
        assert result.metadata.format == InputFormat.MARKDOWN

    def test_sections_from_text(self, loader):
        result = loader.load_text("Para one.\n\nPara two.")
        assert len(result.sections) == 2

    def test_sections_from_markdown(self, loader):
        result = loader.load_text("# H1\n\nContent\n\n## H2\n\nMore content")
        headings = [s.heading for s in result.sections if s.heading]
        assert "H1" in headings
        assert "H2" in headings


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_single_line_text(self, loader):
        result = loader.load_text("Just a single line.")
        assert result.content == "Just a single line."
        assert len(result.sections) == 1

    def test_heading_only_markdown(self, loader):
        result = loader.load_text("# Just a Heading")
        assert result.metadata.title == "Just a Heading"
        # No content under the heading means no section created
        assert len(result.sections) == 0

    def test_multiple_code_blocks(self, loader):
        text = (
            "# Demo\n\n"
            "```python\nx = 1\n```\n\n"
            "Middle text.\n\n"
            "```js\nlet y = 2;\n```\n"
        )
        result = loader.load_text(text)
        assert "x = 1" in result.content
        assert "let y = 2;" in result.content

    def test_empty_file_handling(self, loader, tmp_path):
        file_path = tmp_path / "empty.txt"
        file_path.write_text("   ", encoding="utf-8")
        result = loader.load(str(file_path))
        # content should be at least 1 char for the Document model
        assert len(result.content) >= 1

    def test_unicode_content(self, loader):
        text = "# Ünïcödë\n\nCafé résumé naïve"
        result = loader.load_text(text)
        assert "Ünïcödë" in result.content
        assert "Café" in result.content
