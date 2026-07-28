"""Tests for format detection and unified ingest interface.

Tests detect_format() for all supported extensions and URL patterns,
and tests the ingest() function for routing and error handling.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from models.document import Document, DocumentMetadata, InputFormat, Section
from src.ingestion.ingest import (
    IngestionError,
    UnsupportedFormatError,
    detect_format,
    ingest,
)


# ---------------------------------------------------------------------------
# detect_format() tests
# ---------------------------------------------------------------------------


class TestDetectFormat:
    """Tests for detect_format() function."""

    # -- File extension detection --

    def test_pdf_extension(self):
        assert detect_format("report.pdf") == InputFormat.PDF

    def test_pdf_extension_uppercase(self):
        assert detect_format("REPORT.PDF") == InputFormat.PDF

    def test_pptx_extension(self):
        assert detect_format("slides.pptx") == InputFormat.PPTX

    def test_docx_extension(self):
        assert detect_format("document.docx") == InputFormat.DOCX

    def test_png_extension(self):
        assert detect_format("screenshot.png") == InputFormat.IMAGE

    def test_jpg_extension(self):
        assert detect_format("photo.jpg") == InputFormat.IMAGE

    def test_jpeg_extension(self):
        assert detect_format("image.jpeg") == InputFormat.IMAGE

    def test_bmp_extension(self):
        assert detect_format("bitmap.bmp") == InputFormat.IMAGE

    def test_tiff_extension(self):
        assert detect_format("scan.tiff") == InputFormat.IMAGE

    def test_tif_extension(self):
        assert detect_format("scan.tif") == InputFormat.IMAGE

    def test_txt_extension(self):
        assert detect_format("notes.txt") == InputFormat.TEXT

    def test_md_extension(self):
        assert detect_format("README.md") == InputFormat.MARKDOWN

    # -- Full file paths --

    def test_full_path_pdf(self):
        assert detect_format("/home/user/docs/report.pdf") == InputFormat.PDF

    def test_windows_path_docx(self):
        assert detect_format("C:\\Users\\docs\\file.docx") == InputFormat.DOCX

    def test_relative_path(self):
        assert detect_format("./data/slides.pptx") == InputFormat.PPTX

    # -- YouTube URL detection --

    def test_youtube_standard_url(self):
        assert detect_format("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == InputFormat.YOUTUBE

    def test_youtube_short_url(self):
        assert detect_format("https://youtu.be/dQw4w9WgXcQ") == InputFormat.YOUTUBE

    def test_youtube_mobile_url(self):
        assert detect_format("https://m.youtube.com/watch?v=abc123") == InputFormat.YOUTUBE

    def test_youtube_no_www(self):
        assert detect_format("https://youtube.com/watch?v=abc123") == InputFormat.YOUTUBE

    def test_youtube_embed_url(self):
        assert detect_format("https://www.youtube.com/embed/dQw4w9WgXcQ") == InputFormat.YOUTUBE

    # -- Unsupported / error cases --

    def test_unsupported_extension(self):
        with pytest.raises(UnsupportedFormatError):
            detect_format("data.csv")

    def test_no_extension(self):
        with pytest.raises(UnsupportedFormatError):
            detect_format("Makefile")

    def test_empty_source(self):
        with pytest.raises(UnsupportedFormatError):
            detect_format("")

    def test_whitespace_source(self):
        with pytest.raises(UnsupportedFormatError):
            detect_format("   ")

    def test_unknown_url(self):
        with pytest.raises(UnsupportedFormatError):
            detect_format("https://example.com/page")

    # -- Edge cases --

    def test_source_with_spaces_stripped(self):
        assert detect_format("  report.pdf  ") == InputFormat.PDF

    def test_dotfile_no_ext(self):
        with pytest.raises(UnsupportedFormatError):
            detect_format(".gitignore")


# ---------------------------------------------------------------------------
# ingest() tests — routing and error handling
# ---------------------------------------------------------------------------


class TestIngest:
    """Tests for ingest() unified entry point."""

    def _mock_document(self, fmt: InputFormat, source: str) -> Document:
        """Create a simple mock Document for testing."""
        return Document(
            content="Test content",
            metadata=DocumentMetadata(source=source, format=fmt),
            sections=[],
        )

    @patch("src.ingestion.pdf_loader.PDFLoader.load")
    def test_routes_pdf(self, mock_load):
        mock_load.return_value = self._mock_document(InputFormat.PDF, "test.pdf")

        result = ingest("test.pdf")

        mock_load.assert_called_once_with("test.pdf")
        assert result.metadata.format == InputFormat.PDF

    @patch("src.ingestion.pptx_loader.PPTXLoader.load")
    def test_routes_pptx(self, mock_load):
        mock_load.return_value = self._mock_document(InputFormat.PPTX, "slides.pptx")

        result = ingest("slides.pptx")

        mock_load.assert_called_once_with("slides.pptx")
        assert result.metadata.format == InputFormat.PPTX

    @patch("src.ingestion.docx_loader.DOCXLoader.load")
    def test_routes_docx(self, mock_load):
        mock_load.return_value = self._mock_document(InputFormat.DOCX, "doc.docx")

        result = ingest("doc.docx")

        mock_load.assert_called_once_with("doc.docx")
        assert result.metadata.format == InputFormat.DOCX

    @patch("src.ingestion.image_loader.ImageLoader.load")
    def test_routes_image(self, mock_load):
        mock_load.return_value = self._mock_document(InputFormat.IMAGE, "photo.png")

        result = ingest("photo.png")

        mock_load.assert_called_once_with("photo.png")
        assert result.metadata.format == InputFormat.IMAGE

    @patch("src.ingestion.youtube_loader.YouTubeLoader.load")
    def test_routes_youtube(self, mock_load):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        mock_load.return_value = self._mock_document(InputFormat.YOUTUBE, url)

        result = ingest(url)

        mock_load.assert_called_once_with(url)
        assert result.metadata.format == InputFormat.YOUTUBE

    @patch("src.ingestion.text_loader.TextLoader.load")
    def test_routes_text(self, mock_load):
        mock_load.return_value = self._mock_document(InputFormat.TEXT, "notes.txt")

        result = ingest("notes.txt")

        mock_load.assert_called_once_with("notes.txt")
        assert result.metadata.format == InputFormat.TEXT

    @patch("src.ingestion.text_loader.TextLoader.load")
    def test_routes_markdown(self, mock_load):
        mock_load.return_value = self._mock_document(InputFormat.MARKDOWN, "README.md")

        result = ingest("README.md")

        mock_load.assert_called_once_with("README.md")
        assert result.metadata.format == InputFormat.MARKDOWN

    # -- Error handling --

    def test_unsupported_format_raises(self):
        with pytest.raises(UnsupportedFormatError):
            ingest("data.csv")

    @patch("src.ingestion.pdf_loader.PDFLoader.load")
    def test_loader_exception_wrapped_in_ingestion_error(self, mock_load):
        mock_load.side_effect = FileNotFoundError("File not found: test.pdf")

        with pytest.raises(IngestionError) as exc_info:
            ingest("test.pdf")

        assert "test.pdf" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    @patch("src.ingestion.docx_loader.DOCXLoader.load")
    def test_loader_value_error_wrapped(self, mock_load):
        mock_load.side_effect = ValueError("Corrupt file")

        with pytest.raises(IngestionError) as exc_info:
            ingest("corrupt.docx")

        assert "corrupt.docx" in str(exc_info.value)

    def test_unsupported_format_error_not_wrapped(self):
        """UnsupportedFormatError should propagate directly, not wrapped."""
        with pytest.raises(UnsupportedFormatError):
            ingest("unknown.xyz")

    # -- Return type verification --

    @patch("src.ingestion.text_loader.TextLoader.load")
    def test_returns_document_instance(self, mock_load):
        doc = self._mock_document(InputFormat.TEXT, "notes.txt")
        mock_load.return_value = doc

        result = ingest("notes.txt")

        assert isinstance(result, Document)
        assert result.content == "Test content"
