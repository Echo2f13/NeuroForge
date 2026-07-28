"""Tests for the Image/OCR Loader.

Tests file validation, reading order sorting, diagram detection,
PaddleOCR/Tesseract fallback logic, and document construction.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.document import Document, InputFormat
from src.ingestion.ocr_loader import (
    OCREngineError,
    SUPPORTED_EXTENSIONS,
    UnsupportedImageFormatError,
    _detect_diagrams,
    _sort_boxes_reading_order,
    _validate_file,
    extract_image,
)


# ---------------------------------------------------------------------------
# File Validation Tests
# ---------------------------------------------------------------------------


class TestValidateFile:
    def test_supported_extensions(self):
        """All declared extensions should be in the supported set."""
        expected = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}
        assert SUPPORTED_EXTENSIONS == expected

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _validate_file(str(tmp_path / "nonexistent.png"))

    def test_unsupported_format(self, tmp_path):
        gif_file = tmp_path / "image.gif"
        gif_file.write_bytes(b"fake")
        with pytest.raises(UnsupportedImageFormatError):
            _validate_file(str(gif_file))

    @pytest.mark.parametrize("ext", [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"])
    def test_valid_extensions(self, tmp_path, ext):
        img_file = tmp_path / f"test{ext}"
        img_file.write_bytes(b"fake image data")
        result = _validate_file(str(img_file))
        assert result.exists()


# ---------------------------------------------------------------------------
# Reading Order Sort Tests
# ---------------------------------------------------------------------------


class TestSortBoxesReadingOrder:
    def test_empty_results(self):
        assert _sort_boxes_reading_order([]) == []

    def test_single_result(self):
        results = [([[0, 0], [100, 0], [100, 30], [0, 30]], "hello", 0.95)]
        sorted_r = _sort_boxes_reading_order(results)
        assert len(sorted_r) == 1
        assert sorted_r[0][1] == "hello"

    def test_top_to_bottom_ordering(self):
        """Items at different Y positions should be sorted top-to-bottom."""
        top = ([[10, 10], [100, 10], [100, 40], [10, 40]], "top", 0.9)
        bottom = ([[10, 200], [100, 200], [100, 230], [10, 230]], "bottom", 0.9)
        results = [bottom, top]
        sorted_r = _sort_boxes_reading_order(results)
        assert sorted_r[0][1] == "top"
        assert sorted_r[1][1] == "bottom"

    def test_left_to_right_same_line(self):
        """Items on the same line should be sorted left-to-right."""
        left = ([[10, 10], [50, 10], [50, 40], [10, 40]], "left", 0.9)
        right = ([[200, 10], [300, 10], [300, 40], [200, 40]], "right", 0.9)
        results = [right, left]
        sorted_r = _sort_boxes_reading_order(results)
        assert sorted_r[0][1] == "left"
        assert sorted_r[1][1] == "right"

    def test_multiline_reading_order(self):
        """Full reading order: top-left, top-right, bottom-left, bottom-right."""
        tl = ([[10, 10], [100, 10], [100, 40], [10, 40]], "TL", 0.9)
        tr = ([[200, 10], [300, 10], [300, 40], [200, 40]], "TR", 0.9)
        bl = ([[10, 200], [100, 200], [100, 230], [10, 230]], "BL", 0.9)
        br = ([[200, 200], [300, 200], [300, 230], [200, 230]], "BR", 0.9)
        results = [br, tl, bl, tr]
        sorted_r = _sort_boxes_reading_order(results)
        texts = [r[1] for r in sorted_r]
        assert texts == ["TL", "TR", "BL", "BR"]


# ---------------------------------------------------------------------------
# Diagram Detection Tests
# ---------------------------------------------------------------------------


class TestDetectDiagrams:
    def test_no_results_suggests_diagram(self):
        """Empty OCR results suggest the image is a pure diagram/photo."""
        assert _detect_diagrams([], 1000, 800) is True

    def test_dense_text_no_diagram(self):
        """Image full of text should not be detected as diagram."""
        # Create results that cover most of the image
        results = [
            ([[0, 0], [900, 0], [900, 700], [0, 700]], "lots of text here", 0.95),
        ]
        assert _detect_diagrams(results, 1000, 800) is False

    def test_sparse_text_suggests_diagram(self):
        """Very little text in a large image suggests diagrams."""
        # Small text box in large image
        results = [
            ([[100, 100], [150, 100], [150, 120], [100, 120]], "label", 0.8),
        ]
        assert _detect_diagrams(results, 2000, 2000) is True

    def test_scattered_boxes_suggest_diagram(self):
        """Widely scattered boxes with low density suggest diagram labels."""
        results = [
            ([[10, 10], [60, 10], [60, 30], [10, 30]], "A", 0.9),
            ([[900, 10], [950, 10], [950, 30], [900, 30]], "B", 0.9),
            ([[10, 900], [60, 900], [60, 920], [10, 920]], "C", 0.9),
            ([[900, 900], [950, 900], [950, 920], [900, 920]], "D", 0.9),
        ]
        assert _detect_diagrams(results, 1000, 1000) is True


# ---------------------------------------------------------------------------
# OCR Engine Fallback Tests
# ---------------------------------------------------------------------------


class TestOCRFallback:
    @patch("src.ingestion.ocr_loader._ocr_with_paddleocr", return_value=None)
    @patch("src.ingestion.ocr_loader._ocr_with_tesseract", return_value=None)
    def test_no_engine_available_raises_error(self, mock_tess, mock_paddle, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake png data")
        with patch("src.ingestion.ocr_loader._validate_file", return_value=img):
            with pytest.raises(OCREngineError):
                extract_image(str(img))

    @patch("src.ingestion.ocr_loader._get_image_dimensions", return_value=(800, 600))
    @patch("src.ingestion.ocr_loader._ocr_with_tesseract")
    @patch("src.ingestion.ocr_loader._ocr_with_paddleocr")
    def test_paddleocr_used_first(self, mock_paddle, mock_tess, mock_dims, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake png data")

        mock_paddle.return_value = [
            ([[10, 10], [100, 10], [100, 40], [10, 40]], "Hello World", 0.95),
        ]

        with patch("src.ingestion.ocr_loader._validate_file", return_value=img):
            doc = extract_image(str(img))

        assert "Hello World" in doc.content
        mock_tess.assert_not_called()

    @patch("src.ingestion.ocr_loader._get_image_dimensions", return_value=(800, 600))
    @patch("src.ingestion.ocr_loader._ocr_with_tesseract")
    @patch("src.ingestion.ocr_loader._ocr_with_paddleocr")
    def test_tesseract_fallback_on_paddle_failure(
        self, mock_paddle, mock_tess, mock_dims, tmp_path
    ):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake png data")

        mock_paddle.return_value = None  # PaddleOCR not available
        mock_tess.return_value = [
            ([[10, 10], [100, 10], [100, 40], [10, 40]], "Fallback text", 0.85),
        ]

        with patch("src.ingestion.ocr_loader._validate_file", return_value=img):
            doc = extract_image(str(img))

        assert "Fallback text" in doc.content


# ---------------------------------------------------------------------------
# Document Construction Tests
# ---------------------------------------------------------------------------


class TestExtractImage:
    @patch("src.ingestion.ocr_loader._get_image_dimensions", return_value=(1024, 768))
    @patch("src.ingestion.ocr_loader._ocr_with_paddleocr")
    def test_document_structure(self, mock_paddle, mock_dims, tmp_path):
        img = tmp_path / "whiteboard.jpg"
        img.write_bytes(b"fake jpg")

        mock_paddle.return_value = [
            ([[10, 10], [200, 10], [200, 40], [10, 40]], "Meeting Notes", 0.92),
            ([[10, 60], [300, 60], [300, 90], [10, 90]], "Action items for Q4", 0.88),
        ]

        with patch("src.ingestion.ocr_loader._validate_file", return_value=img):
            doc = extract_image(str(img))

        assert isinstance(doc, Document)
        assert doc.metadata.format == InputFormat.IMAGE
        assert doc.metadata.title == "OCR: whiteboard.jpg"
        assert str(img) in doc.metadata.source
        assert len(doc.sections) == 1
        assert "Meeting Notes" in doc.content
        assert "Action items for Q4" in doc.content

    @patch("src.ingestion.ocr_loader._get_image_dimensions", return_value=(800, 600))
    @patch("src.ingestion.ocr_loader._ocr_with_paddleocr")
    def test_empty_ocr_results(self, mock_paddle, mock_dims, tmp_path):
        """When OCR finds no text, document should contain placeholder."""
        img = tmp_path / "blank.png"
        img.write_bytes(b"fake png")

        mock_paddle.return_value = []

        with patch("src.ingestion.ocr_loader._validate_file", return_value=img):
            doc = extract_image(str(img))

        assert "[No text detected]" in doc.content

    @patch("src.ingestion.ocr_loader._get_image_dimensions", return_value=(1000, 1000))
    @patch("src.ingestion.ocr_loader._ocr_with_paddleocr")
    def test_low_confidence_handwriting(self, mock_paddle, mock_dims, tmp_path):
        """Low confidence scores should still produce a valid document."""
        img = tmp_path / "handwritten.png"
        img.write_bytes(b"fake png")

        mock_paddle.return_value = [
            ([[10, 10], [200, 10], [200, 40], [10, 40]], "scribble", 0.4),
            ([[10, 60], [200, 60], [200, 90], [10, 90]], "more scribble", 0.35),
        ]

        with patch("src.ingestion.ocr_loader._validate_file", return_value=img):
            doc = extract_image(str(img))

        assert "scribble" in doc.content
        assert isinstance(doc, Document)

    @patch("src.ingestion.ocr_loader._get_image_dimensions", return_value=(500, 500))
    @patch("src.ingestion.ocr_loader._ocr_with_paddleocr")
    def test_multiple_text_blocks_joined(self, mock_paddle, mock_dims, tmp_path):
        """Multiple OCR results should be joined with spaces."""
        img = tmp_path / "scan.tiff"
        img.write_bytes(b"fake tiff")

        mock_paddle.return_value = [
            ([[10, 10], [50, 10], [50, 30], [10, 30]], "Hello", 0.95),
            ([[60, 10], [120, 10], [120, 30], [60, 30]], "World", 0.93),
        ]

        with patch("src.ingestion.ocr_loader._validate_file", return_value=img):
            doc = extract_image(str(img))

        assert doc.content == "Hello World"
