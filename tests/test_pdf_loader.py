"""Tests for src/ingestion/pdf_loader.py — PDFLoader class."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.document import Document, DocumentMetadata, InputFormat, Section
from src.ingestion.pdf_loader import (
    COLUMN_GAP_THRESHOLD,
    HEADING_FONT_SIZE_RATIO,
    SCANNED_PAGE_CHAR_THRESHOLD,
    PDFLoader,
    _detect_columns,
    _extract_headings_from_chars,
    _split_columns,
    extract_pdf,
)


# ---------------------------------------------------------------------------
# PDFLoader class tests
# ---------------------------------------------------------------------------


class TestPDFLoader:
    """Tests for the PDFLoader class interface."""

    def test_init(self):
        """PDFLoader can be instantiated."""
        loader = PDFLoader()
        assert loader is not None

    def test_load_file_not_found(self):
        """load() raises FileNotFoundError for missing files."""
        loader = PDFLoader()
        with pytest.raises(FileNotFoundError, match="not found"):
            loader.load("nonexistent_file.pdf")

    def test_load_non_pdf_extension(self, tmp_path):
        """load() raises ValueError for non-PDF files."""
        txt_file = tmp_path / "file.txt"
        txt_file.write_text("hello")
        loader = PDFLoader()
        with pytest.raises(ValueError, match="Expected a PDF"):
            loader.load(str(txt_file))

    def test_load_delegates_to_extract_pdf(self, tmp_path):
        """load() delegates to the extract_pdf function."""
        loader = PDFLoader()
        with patch("src.ingestion.pdf_loader.extract_pdf") as mock_extract:
            mock_extract.return_value = Document(
                content="test",
                metadata=DocumentMetadata(source="test.pdf", format=InputFormat.PDF),
                sections=[],
            )
            # We patch extract_pdf so we don't need a real PDF
            result = loader.load("test.pdf")
            mock_extract.assert_called_once_with("test.pdf")
            assert result.content == "test"


# ---------------------------------------------------------------------------
# extract_pdf function tests
# ---------------------------------------------------------------------------


class TestExtractPdf:
    """Tests for the extract_pdf entry point."""

    def test_file_not_found(self):
        """Raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            extract_pdf("/no/such/file.pdf")

    def test_non_pdf_extension(self, tmp_path):
        """Raises ValueError for non-PDF extension."""
        f = tmp_path / "data.docx"
        f.write_text("test")
        with pytest.raises(ValueError, match="Expected a PDF"):
            extract_pdf(str(f))


# ---------------------------------------------------------------------------
# Column detection tests
# ---------------------------------------------------------------------------


class TestDetectColumns:
    """Tests for the _detect_columns helper."""

    def test_empty_words(self):
        """Returns False for empty word list."""
        assert _detect_columns([]) is False

    def test_single_column_layout(self):
        """Returns False when words are spread across the page."""
        # Simulate words spread evenly
        words = [
            {"x0": i * 10, "x1": i * 10 + 30, "top": i * 20, "text": f"word{i}"}
            for i in range(30)
        ]
        assert _detect_columns(words) is False

    def test_two_column_layout(self):
        """Returns True when there's a clear gap in the middle zone."""
        page_width = 600
        # Left column words (x: 20-250)
        left_words = [
            {"x0": 20, "x1": 100, "top": i * 15, "text": f"left{i}"}
            for i in range(15)
        ]
        # Right column words (x: 350-580)
        right_words = [
            {"x0": 350, "x1": 500, "top": i * 15, "text": f"right{i}"}
            for i in range(15)
        ]
        words = left_words + right_words
        # Check: middle zone (30%-70% of 600 = 180-420) has few words
        # left_words end at x1=100, right_words start at x0=350
        # Only right_words starting at 350 fall in mid zone (180-420)
        # Let's adjust to make a clear gap
        left_words_clear = [
            {"x0": 20, "x1": 150, "top": i * 15, "text": f"left{i}"}
            for i in range(15)
        ]
        right_words_clear = [
            {"x0": 450, "x1": 580, "top": i * 15, "text": f"right{i}"}
            for i in range(15)
        ]
        words_clear = left_words_clear + right_words_clear
        assert _detect_columns(words_clear) is True

    def test_few_words_not_detected(self):
        """Returns False when there are too few words (< 20)."""
        words = [
            {"x0": 20, "x1": 100, "top": 10, "text": "word1"},
            {"x0": 400, "x1": 500, "top": 10, "text": "word2"},
        ]
        assert _detect_columns(words) is False


# ---------------------------------------------------------------------------
# Column splitting tests
# ---------------------------------------------------------------------------


class TestSplitColumns:
    """Tests for the _split_columns helper."""

    def test_basic_split(self):
        """Splits left and right columns correctly."""
        page_width = 600
        words = [
            {"x0": 20, "x1": 100, "top": 10, "text": "Left1"},
            {"x0": 20, "x1": 100, "top": 25, "text": "Left2"},
            {"x0": 400, "x1": 500, "top": 10, "text": "Right1"},
            {"x0": 400, "x1": 500, "top": 25, "text": "Right2"},
        ]
        result = _split_columns(words, page_width)
        assert "Left1" in result
        assert "Left2" in result
        assert "Right1" in result
        assert "Right2" in result
        # Left should come before right
        assert result.index("Left1") < result.index("Right1")

    def test_empty_words(self):
        """Returns empty-ish text for no words."""
        result = _split_columns([], 600)
        assert result.strip() == ""


# ---------------------------------------------------------------------------
# Heading extraction tests
# ---------------------------------------------------------------------------


class TestExtractHeadingsFromChars:
    """Tests for _extract_headings_from_chars."""

    def test_empty_chars(self):
        """Returns empty list for no characters."""
        assert _extract_headings_from_chars([], 1) == []

    def test_no_headings_uniform_size(self):
        """Returns no headings when all chars have same font size."""
        chars = [{"text": c, "size": 12.0} for c in "Hello World"]
        result = _extract_headings_from_chars(chars, 1)
        assert result == []

    def test_detects_heading_from_large_font(self):
        """Detects heading when some chars have significantly larger font."""
        # Body text at size 12
        body_chars = [{"text": c, "size": 12.0} for c in "This is body text. " * 5]
        # Heading at size 20 (> 12 * 1.25 = 15)
        heading_chars = [{"text": c, "size": 20.0} for c in "Big Heading"]
        chars = body_chars + heading_chars + body_chars

        result = _extract_headings_from_chars(chars, 1)
        assert len(result) >= 1
        assert "Big Heading" in result[0].heading
        assert result[0].page_number == 1

    def test_heading_level_assignment(self):
        """Level 1 for very large fonts (>= 1.5x median), level 2 otherwise."""
        # Body text at size 12 → median ~12
        body_chars = [{"text": c, "size": 12.0} for c in "Body text here. " * 10]
        # Level 1 heading: size 20 (20/12 = 1.67 > 1.5)
        h1_chars = [{"text": c, "size": 20.0} for c in "Title"]
        # Level 2 heading: size 16 (16/12 = 1.33 > 1.25 but < 1.5)
        h2_chars = [{"text": c, "size": 16.0} for c in "Subtitle"]

        chars = body_chars + h1_chars + body_chars + h2_chars + body_chars
        result = _extract_headings_from_chars(chars, 2)

        # Should find at least 2 headings
        assert len(result) >= 2
        # First heading should be level 1
        title_section = [s for s in result if "Title" in (s.heading or "")]
        subtitle_section = [s for s in result if "Subtitle" in (s.heading or "")]
        if title_section:
            assert title_section[0].level == 1
        if subtitle_section:
            assert subtitle_section[0].level == 2
