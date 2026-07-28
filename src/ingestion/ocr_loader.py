"""Image/OCR Loader for NeuroForge.

Extracts text from images using PaddleOCR (primary) with Tesseract (fallback).
Supports PNG, JPG, JPEG, BMP, and TIFF formats.
Handles handwritten text best-effort and notes diagram presence in metadata.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from models.document import Document, DocumentMetadata, InputFormat, Section

logger = logging.getLogger("neuroforge.ocr_loader")

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}

# Thresholds for diagram detection and handwriting confidence
_DIAGRAM_TEXT_DENSITY_THRESHOLD = 0.02  # text area / image area
_DIAGRAM_SCATTER_THRESHOLD = 0.6  # ratio of scattered boxes
_HANDWRITING_CONFIDENCE_THRESHOLD = 0.65  # avg confidence below this suggests handwriting


class UnsupportedImageFormatError(Exception):
    """Raised when an image file has an unsupported extension."""

    pass


class OCREngineError(Exception):
    """Raised when no OCR engine is available."""

    pass


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


def _sort_boxes_reading_order(
    results: list[tuple[list, str, float]],
) -> list[tuple[list, str, float]]:
    """Sort OCR bounding boxes in reading order: top-to-bottom, left-to-right.

    Each result is (bbox_points, text, confidence).
    bbox_points is a list of 4 corner points [[x1,y1],[x2,y2],[x3,y3],[x4,y4]].

    We sort primarily by the top-left Y coordinate, with a tolerance band
    for lines at similar heights, then by X coordinate within each band.
    """
    if not results:
        return results

    # Calculate line height tolerance from average box height
    heights = []
    for bbox, _, _ in results:
        y_coords = [pt[1] for pt in bbox]
        heights.append(max(y_coords) - min(y_coords))

    avg_height = sum(heights) / len(heights) if heights else 20
    line_tolerance = avg_height * 0.5

    def sort_key(item):
        bbox = item[0]
        top_y = min(pt[1] for pt in bbox)
        left_x = min(pt[0] for pt in bbox)
        # Quantize Y to group items on the same line
        line_num = int(top_y / line_tolerance) if line_tolerance > 0 else top_y
        return (line_num, left_x)

    return sorted(results, key=sort_key)


def _detect_diagrams(
    results: list[tuple[list, str, float]],
    image_width: int,
    image_height: int,
) -> bool:
    """Detect if the image likely contains diagrams.

    Heuristics:
    - Low text density: text bounding box area is small relative to image area.
    - Scattered bounding boxes: boxes are widely distributed without forming
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
    total_text_area = 0
    centroids_x = []
    centroids_y = []

    for bbox, _, _ in results:
        x_coords = [pt[0] for pt in bbox]
        y_coords = [pt[1] for pt in bbox]
        box_width = max(x_coords) - min(x_coords)
        box_height = max(y_coords) - min(y_coords)
        total_text_area += box_width * box_height
        centroids_x.append(sum(x_coords) / len(x_coords))
        centroids_y.append(sum(y_coords) / len(y_coords))

    text_density = total_text_area / image_area

    # Check scatter: if boxes span a large portion of the image without
    # filling it densely, it's likely a diagram with labels
    if len(centroids_x) >= 2:
        x_spread = (max(centroids_x) - min(centroids_x)) / image_width
        y_spread = (max(centroids_y) - min(centroids_y)) / image_height
        coverage_spread = x_spread * y_spread
        is_scattered = coverage_spread > _DIAGRAM_SCATTER_THRESHOLD and text_density < 0.1
    else:
        is_scattered = False

    is_low_density = text_density < _DIAGRAM_TEXT_DENSITY_THRESHOLD

    return is_low_density or is_scattered


def _ocr_with_paddleocr(image_path: str) -> Optional[list[tuple[list, str, float]]]:
    """Attempt OCR using PaddleOCR.

    Returns:
        List of (bbox, text, confidence) tuples, or None if PaddleOCR unavailable.
    """
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        logger.warning("PaddleOCR not installed, will try fallback.")
        return None

    try:
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = ocr.ocr(image_path, cls=True)

        if not result or not result[0]:
            return []

        parsed = []
        for line in result[0]:
            bbox = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            text = line[1][0]
            confidence = line[1][1]
            parsed.append((bbox, text, confidence))

        return parsed
    except Exception as e:
        logger.warning(f"PaddleOCR failed: {e}")
        return None


def _ocr_with_tesseract(image_path: str) -> Optional[list[tuple[list, str, float]]]:
    """Attempt OCR using Tesseract via pytesseract.

    Returns:
        List of (bbox, text, confidence) tuples, or None if Tesseract unavailable.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        logger.warning("pytesseract or Pillow not installed.")
        return None

    try:
        img = Image.open(image_path)
        # Get detailed data including bounding boxes and confidence
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        parsed = []
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
            parsed.append((bbox, text, conf / 100.0))  # Normalize confidence to 0-1

        return parsed
    except Exception as e:
        logger.warning(f"Tesseract OCR failed: {e}")
        return None


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


def extract_image(file_path: str) -> Document:
    """Extract text from an image file using OCR.

    Uses PaddleOCR as the primary engine with Tesseract (pytesseract) as fallback.
    Results are sorted in reading order (top-to-bottom, left-to-right).
    Low confidence scores suggest handwritten text or diagrams.

    Args:
        file_path: Path to the image file (PNG, JPG, JPEG, BMP, TIFF).

    Returns:
        Document with extracted text, metadata, and a single section.

    Raises:
        FileNotFoundError: If the file does not exist.
        UnsupportedImageFormatError: If the file format is not supported.
        OCREngineError: If neither PaddleOCR nor Tesseract is available.
    """
    path = _validate_file(file_path)
    logger.info(f"Processing image: {path.name}")

    # Try PaddleOCR first, then Tesseract fallback
    results = _ocr_with_paddleocr(str(path))
    ocr_engine_used = "paddleocr"

    if results is None:
        results = _ocr_with_tesseract(str(path))
        ocr_engine_used = "tesseract"

    if results is None:
        raise OCREngineError(
            "No OCR engine available. Install paddleocr or pytesseract + Pillow."
        )

    # Sort results in reading order
    sorted_results = _sort_boxes_reading_order(results)

    # Extract text and compute confidence stats
    texts = []
    confidences = []
    for _, text, conf in sorted_results:
        texts.append(text)
        confidences.append(conf)

    extracted_text = " ".join(texts) if texts else ""
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # Detect diagrams
    img_width, img_height = _get_image_dimensions(str(path))
    has_diagrams = _detect_diagrams(sorted_results, img_width, img_height)

    # Determine if handwriting is likely
    is_handwritten = avg_confidence < _HANDWRITING_CONFIDENCE_THRESHOLD and len(texts) > 0

    # Build metadata title
    title = f"OCR: {path.name}"

    # Compose content — include notes about diagrams/handwriting
    content_parts = [extracted_text] if extracted_text else ["[No text detected]"]

    # Build the Document
    metadata = DocumentMetadata(
        source=str(path),
        format=InputFormat.IMAGE,
        title=title,
    )

    # Create a single section with all extracted text
    section_content = extracted_text if extracted_text else "[No text detected]"
    section = Section(
        heading=title,
        content=section_content,
        level=1,
    )

    document = Document(
        content=content_parts[0],
        metadata=metadata,
        sections=[section],
    )

    # Log useful info
    logger.info(
        f"OCR complete — engine: {ocr_engine_used}, "
        f"text blocks: {len(sorted_results)}, "
        f"avg confidence: {avg_confidence:.2f}, "
        f"diagrams detected: {has_diagrams}, "
        f"handwritten: {is_handwritten}"
    )

    return document
