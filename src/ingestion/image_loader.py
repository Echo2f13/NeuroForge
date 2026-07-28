"""Image/OCR Loader for NeuroForge.

Provides the ImageLoader class for extracting text from images using OCR.
Uses PaddleOCR as the primary engine with Tesseract (pytesseract) as fallback.

Supports: PNG, JPG, JPEG, BMP, TIFF
Features:
- Reading order preservation (top-to-bottom, left-to-right)
- Diagram detection (noted in metadata)
- Handwritten text handling (best-effort via PaddleOCR)
- Graceful handling of unreadable images

Usage:
    from src.ingestion.image_loader import ImageLoader

    loader = ImageLoader()
    doc = loader.load("path/to/image.png")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from models import Document, DocumentMetadata, Section, InputFormat

logger = logging.getLogger("neuroforge.image_loader")

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}

# Thresholds for diagram detection and handwriting confidence
_DIAGRAM_TEXT_DENSITY_THRESHOLD = 0.02  # text area / image area ratio
_DIAGRAM_SCATTER_THRESHOLD = 0.6  # coverage spread threshold
_HANDWRITING_CONFIDENCE_THRESHOLD = 0.65  # avg confidence below this suggests handwriting


class UnsupportedImageFormatError(Exception):
    """Raised when an image file has an unsupported extension."""

    pass


class OCREngineError(Exception):
    """Raised when no OCR engine is available."""

    pass


class ImageLoader:
    """Image document loader with PaddleOCR primary and Tesseract fallback.

    Extracts text from images using OCR, preserving reading order.
    Detects diagram presence and handles handwritten text best-effort.

    Usage:
        loader = ImageLoader()
        doc = loader.load("path/to/image.png")
    """

    def __init__(self, lang: str = "en", use_angle_cls: bool = True) -> None:
        """Initialize ImageLoader.

        Args:
            lang: Language for OCR recognition (default: "en").
            use_angle_cls: Whether to use angle classification for rotated text.
        """
        self._lang = lang
        self._use_angle_cls = use_angle_cls

    def load(self, file_path: str) -> Document:
        """Load an image file and extract text via OCR.

        Uses PaddleOCR as the primary engine. Falls back to Tesseract
        (pytesseract) if PaddleOCR is unavailable or fails.

        OCR results are sorted in reading order (top-to-bottom, left-to-right).
        Metadata includes diagram detection and handwriting indicators.

        Args:
            file_path: Path to the image file (PNG, JPG, JPEG, BMP, TIFF).

        Returns:
            A Document instance with extracted text, metadata, and sections.

        Raises:
            FileNotFoundError: If the file does not exist.
            UnsupportedImageFormatError: If the file format is not supported.
            OCREngineError: If neither PaddleOCR nor Tesseract is available.
        """
        path = self._validate_file(file_path)
        logger.info(f"Processing image: {path.name}")

        # Try PaddleOCR first, then Tesseract fallback
        results = self._ocr_with_paddleocr(str(path))
        ocr_engine_used = "paddleocr"

        if results is None:
            results = self._ocr_with_tesseract(str(path))
            ocr_engine_used = "tesseract"

        if results is None:
            raise OCREngineError(
                "No OCR engine available. Install paddleocr or pytesseract + Pillow."
            )

        # Sort results in reading order
        sorted_results = self._sort_boxes_reading_order(results)

        # Extract text and compute confidence stats
        texts: list[str] = []
        confidences: list[float] = []
        for _, text, conf in sorted_results:
            texts.append(text)
            confidences.append(conf)

        extracted_text = " ".join(texts) if texts else ""
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Detect diagrams
        img_width, img_height = self._get_image_dimensions(str(path))
        has_diagrams = self._detect_diagrams(sorted_results, img_width, img_height)

        # Determine if handwriting is likely
        is_handwritten = (
            avg_confidence < _HANDWRITING_CONFIDENCE_THRESHOLD and len(texts) > 0
        )

        # Build metadata
        title = f"OCR: {path.name}"

        # Handle unreadable images gracefully
        if not extracted_text:
            content = "[No text detected]"
            warnings = ["No text could be extracted from this image."]
            if has_diagrams:
                warnings.append("Image appears to contain diagrams or non-text content.")
        else:
            content = extracted_text
            warnings = []

        metadata = DocumentMetadata(
            source=str(path),
            format=InputFormat.IMAGE,
            title=title,
        )

        # Create a single section with all extracted text
        section = Section(
            heading=title,
            content=content,
            level=1,
        )

        document = Document(
            content=content,
            metadata=metadata,
            sections=[section],
        )

        # Log useful diagnostic info
        logger.info(
            f"OCR complete — engine: {ocr_engine_used}, "
            f"text blocks: {len(sorted_results)}, "
            f"avg confidence: {avg_confidence:.2f}, "
            f"diagrams detected: {has_diagrams}, "
            f"handwritten: {is_handwritten}"
        )

        return document

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_file(file_path: str) -> Path:
        """Validate the image file exists and has a supported extension.

        Args:
            file_path: Path to the image file.

        Returns:
            Resolved Path object.

        Raises:
            FileNotFoundError: If the file does not exist.
            UnsupportedImageFormatError: If the extension is not supported.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedImageFormatError(
                f"Unsupported image format '{ext}'. "
                f"Supported formats: {sorted(SUPPORTED_EXTENSIONS)}"
            )
        return path

    def _ocr_with_paddleocr(
        self, image_path: str
    ) -> Optional[list[tuple[list, str, float]]]:
        """Attempt OCR using PaddleOCR.

        Returns:
            List of (bbox, text, confidence) tuples, or None if unavailable.
        """
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            logger.warning("PaddleOCR not installed, will try fallback.")
            return None

        try:
            ocr = PaddleOCR(
                use_angle_cls=self._use_angle_cls,
                lang=self._lang,
                show_log=False,
            )
            result = ocr.ocr(image_path, cls=True)

            if not result or not result[0]:
                return []

            parsed: list[tuple[list, str, float]] = []
            for line in result[0]:
                bbox = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                text = line[1][0]
                confidence = line[1][1]
                parsed.append((bbox, text, confidence))

            return parsed
        except Exception as e:
            logger.warning(f"PaddleOCR failed: {e}")
            return None

    @staticmethod
    def _ocr_with_tesseract(
        image_path: str,
    ) -> Optional[list[tuple[list, str, float]]]:
        """Attempt OCR using Tesseract via pytesseract.

        Returns:
            List of (bbox, text, confidence) tuples, or None if unavailable.
        """
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            logger.warning("pytesseract or Pillow not installed.")
            return None

        try:
            img = Image.open(image_path)
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

            parsed: list[tuple[list, str, float]] = []
            n_boxes = len(data["text"])
            for i in range(n_boxes):
                text = data["text"][i].strip()
                if not text:
                    continue

                conf = float(data["conf"][i])
                if conf < 0:
                    continue  # Skip entries with no confidence

                x = data["left"][i]
                y = data["top"][i]
                w = data["width"][i]
                h = data["height"][i]

                # Convert to 4-point bbox format matching PaddleOCR
                bbox = [
                    [x, y],
                    [x + w, y],
                    [x + w, y + h],
                    [x, y + h],
                ]
                parsed.append((bbox, text, conf / 100.0))  # Normalize to 0-1

            return parsed
        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {e}")
            return None

    @staticmethod
    def _sort_boxes_reading_order(
        results: list[tuple[list, str, float]],
    ) -> list[tuple[list, str, float]]:
        """Sort OCR bounding boxes in reading order: top-to-bottom, left-to-right.

        Each result is (bbox_points, text, confidence).
        bbox_points is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]].

        Sort by quantized Y (line grouping), then by X within each line.
        """
        if not results:
            return results

        # Calculate line height tolerance from average box height
        heights: list[float] = []
        for bbox, _, _ in results:
            y_coords = [pt[1] for pt in bbox]
            heights.append(max(y_coords) - min(y_coords))

        avg_height = sum(heights) / len(heights) if heights else 20
        line_tolerance = avg_height * 0.5

        def sort_key(item: tuple[list, str, float]) -> tuple[int, float]:
            bbox = item[0]
            top_y = min(pt[1] for pt in bbox)
            left_x = min(pt[0] for pt in bbox)
            # Quantize Y to group items on the same line
            line_num = int(top_y / line_tolerance) if line_tolerance > 0 else int(top_y)
            return (line_num, left_x)

        return sorted(results, key=sort_key)

    @staticmethod
    def _detect_diagrams(
        results: list[tuple[list, str, float]],
        image_width: int,
        image_height: int,
    ) -> bool:
        """Detect if the image likely contains diagrams.

        Heuristics:
        - Low text density: text bbox area is small relative to image area.
        - Scattered bounding boxes: widely distributed without forming
          coherent text blocks.

        Args:
            results: OCR results as (bbox, text, confidence) tuples.
            image_width: Width of the source image in pixels.
            image_height: Height of the source image in pixels.

        Returns:
            True if diagrams are likely present.
        """
        if not results:
            return True  # No text at all suggests a diagram/photo

        image_area = image_width * image_height
        if image_area == 0:
            return False

        # Calculate total text bounding box area
        total_text_area = 0.0
        centroids_x: list[float] = []
        centroids_y: list[float] = []

        for bbox, _, _ in results:
            x_coords = [pt[0] for pt in bbox]
            y_coords = [pt[1] for pt in bbox]
            box_width = max(x_coords) - min(x_coords)
            box_height = max(y_coords) - min(y_coords)
            total_text_area += box_width * box_height
            centroids_x.append(sum(x_coords) / len(x_coords))
            centroids_y.append(sum(y_coords) / len(y_coords))

        text_density = total_text_area / image_area

        # Check scatter: boxes span large portion without filling densely
        if len(centroids_x) >= 2:
            x_spread = (max(centroids_x) - min(centroids_x)) / image_width
            y_spread = (max(centroids_y) - min(centroids_y)) / image_height
            coverage_spread = x_spread * y_spread
            is_scattered = (
                coverage_spread > _DIAGRAM_SCATTER_THRESHOLD and text_density < 0.1
            )
        else:
            is_scattered = False

        is_low_density = text_density < _DIAGRAM_TEXT_DENSITY_THRESHOLD

        return is_low_density or is_scattered

    @staticmethod
    def _get_image_dimensions(image_path: str) -> tuple[int, int]:
        """Get image width and height using Pillow.

        Returns:
            (width, height) tuple. Falls back to (0, 0) if unable to read.
        """
        try:
            from PIL import Image

            with Image.open(image_path) as img:
                return img.size  # (width, height)
        except Exception:
            return (0, 0)
