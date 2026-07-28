"""PDF Loader for NeuroForge.

Extracts text from PDF files using pdfplumber (primary) with PyMuPDF (fitz) as fallback.
Handles:
- Page-level text extraction with page numbers
- Heading detection via font size analysis
- Multi-column layout detection and splitting
- Scanned/image-only PDF detection (routes to OCR)

Usage:
    from src.ingestion.pdf_loader import extract_pdf
    doc = extract_pdf("path/to/file.pdf")
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Optional

from models.document import Document, DocumentMetadata, InputFormat, Section


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# If a page yields fewer characters than this, consider it scanned/image-only
SCANNED_PAGE_CHAR_THRESHOLD = 50

# Font size ratio above the median to qualify as a heading
HEADING_FONT_SIZE_RATIO = 1.25

# Minimum gap (in pts) between columns to detect multi-column layout
COLUMN_GAP_THRESHOLD = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_columns(words: list[dict]) -> bool:
    """Detect multi-column layout by looking for a large horizontal gap.

    Checks whether there's a significant gap in the middle third of the page
    where no text appears — a strong indicator of a two-column layout.
    """
    if not words:
        return False

    # Get page width from the rightmost word
    x_positions = [w["x0"] for w in words] + [w["x1"] for w in words]
    if not x_positions:
        return False

    page_width = max(x_positions)
    if page_width == 0:
        return False

    # Define the middle zone (30%-70% of page width)
    mid_left = page_width * 0.30
    mid_right = page_width * 0.70

    # Find words that start or end in the middle zone
    mid_zone_words = [
        w for w in words
        if (mid_left <= w["x0"] <= mid_right) or (mid_left <= w["x1"] <= mid_right)
    ]

    # If very few words appear in the middle zone relative to total, it's columnar
    if len(words) > 20 and len(mid_zone_words) < len(words) * 0.1:
        return True

    return False


def _split_columns(words: list[dict], page_width: float) -> str:
    """Split two-column text by reading left column first, then right."""
    midpoint = page_width / 2.0

    left_words = [w for w in words if w["x1"] <= midpoint + COLUMN_GAP_THRESHOLD]
    right_words = [w for w in words if w["x0"] >= midpoint - COLUMN_GAP_THRESHOLD]

    def _words_to_text(word_list: list[dict]) -> str:
        """Convert a list of word dicts to text, preserving line order."""
        if not word_list:
            return ""
        # Sort by top (vertical position), then by x0 (horizontal)
        sorted_words = sorted(word_list, key=lambda w: (round(w["top"], 1), w["x0"]))
        lines: list[str] = []
        current_line: list[str] = []
        current_top: Optional[float] = None

        for w in sorted_words:
            word_top = round(w["top"], 1)
            if current_top is None or abs(word_top - current_top) > 3:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [w["text"]]
                current_top = word_top
            else:
                current_line.append(w["text"])

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)

    left_text = _words_to_text(left_words)
    right_text = _words_to_text(right_words)

    return f"{left_text}\n\n{right_text}"


def _extract_headings_from_chars(chars: list[dict], page_number: int) -> list[Section]:
    """Identify headings by analyzing font sizes in character data.

    Characters with font size significantly above the median are treated as headings.
    """
    if not chars:
        return []

    # Collect font sizes
    sizes = [c.get("size", 0) for c in chars if c.get("size")]
    if not sizes:
        return []

    median_size = statistics.median(sizes)
    if median_size == 0:
        return []

    heading_threshold = median_size * HEADING_FONT_SIZE_RATIO

    # Group consecutive characters into runs of same size
    headings: list[Section] = []
    current_heading_chars: list[str] = []
    current_size: Optional[float] = None

    for c in chars:
        char_size = c.get("size", 0)
        char_text = c.get("text", "")

        if char_size >= heading_threshold:
            if current_size is not None and abs(char_size - current_size) > 1:
                # Size changed — flush current heading
                heading_text = "".join(current_heading_chars).strip()
                if heading_text and len(heading_text) > 2:
                    level = 1 if char_size >= median_size * 1.5 else 2
                    headings.append(Section(
                        heading=heading_text,
                        content=heading_text,
                        level=level,
                        page_number=page_number,
                    ))
                current_heading_chars = []

            current_heading_chars.append(char_text)
            current_size = char_size
        else:
            # Flush any accumulated heading
            if current_heading_chars:
                heading_text = "".join(current_heading_chars).strip()
                if heading_text and len(heading_text) > 2:
                    level = 1 if (current_size or 0) >= median_size * 1.5 else 2
                    headings.append(Section(
                        heading=heading_text,
                        content=heading_text,
                        level=level,
                        page_number=page_number,
                    ))
                current_heading_chars = []
                current_size = None

    # Flush remaining
    if current_heading_chars:
        heading_text = "".join(current_heading_chars).strip()
        if heading_text and len(heading_text) > 2:
            level = 1 if (current_size or 0) >= median_size * 1.5 else 2
            headings.append(Section(
                heading=heading_text,
                content=heading_text,
                level=level,
                page_number=page_number,
            ))

    return headings


# ---------------------------------------------------------------------------
# Primary Extraction: pdfplumber
# ---------------------------------------------------------------------------


def _extract_with_pdfplumber(file_path: str) -> Optional[Document]:
    """Extract PDF content using pdfplumber.

    Returns a Document or None if extraction fails.
    """
    try:
        import pdfplumber
    except ImportError:
        print("[WARNING] pdfplumber not installed. Falling back to PyMuPDF.")
        return None

    try:
        all_text_parts: list[str] = []
        all_sections: list[Section] = []
        scanned_pages: list[int] = []
        total_pages = 0

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract words for column detection
                words = page.extract_words() or []

                # Detect multi-column layout
                if _detect_columns(words):
                    page_text = _split_columns(words, page.width)
                else:
                    page_text = page.extract_text() or ""

                # Check for scanned/image-only page
                if len(page_text.strip()) < SCANNED_PAGE_CHAR_THRESHOLD:
                    scanned_pages.append(page_num)
                    page_text = page_text.strip() if page_text else ""

                all_text_parts.append(page_text)

                # Extract heading structure from character-level data
                chars = page.chars or []
                page_headings = _extract_headings_from_chars(chars, page_num)
                all_sections.extend(page_headings)

        # Warn about scanned pages
        if scanned_pages:
            print(
                f"[OCR NEEDED] Pages with little/no text detected (likely scanned): "
                f"{scanned_pages}. Route these pages to OCR for text extraction."
            )

        full_text = "\n\n".join(all_text_parts).strip()

        # If no text was extracted at all, return None to trigger fallback
        if not full_text:
            return None

        # Determine title from first heading, if available
        title = all_sections[0].heading if all_sections else None

        metadata = DocumentMetadata(
            source=str(Path(file_path).resolve()),
            format=InputFormat.PDF,
            title=title,
            total_pages=total_pages,
        )

        return Document(
            content=full_text,
            metadata=metadata,
            sections=all_sections,
        )

    except Exception as e:
        print(f"[WARNING] pdfplumber extraction failed: {e}. Falling back to PyMuPDF.")
        return None


# ---------------------------------------------------------------------------
# Fallback Extraction: PyMuPDF (fitz)
# ---------------------------------------------------------------------------


def _extract_with_pymupdf(file_path: str) -> Document:
    """Extract PDF content using PyMuPDF (fitz) as fallback.

    This is simpler — extracts text per page without advanced heading detection.
    """
    import fitz  # PyMuPDF

    all_text_parts: list[str] = []
    all_sections: list[Section] = []
    scanned_pages: list[int] = []

    doc = fitz.open(file_path)
    total_pages = len(doc)

    for page_num in range(total_pages):
        page = doc[page_num]
        page_text = page.get_text("text") or ""

        # Detect scanned pages
        if len(page_text.strip()) < SCANNED_PAGE_CHAR_THRESHOLD:
            scanned_pages.append(page_num + 1)

        all_text_parts.append(page_text)

        # Basic heading detection via text blocks with larger font
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])
        for block in blocks:
            if block.get("type") != 0:  # text block type
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_size = span.get("size", 0)
                    span_text = span.get("text", "").strip()
                    # Heuristic: font size > 14 and short text → heading
                    if span_size > 14 and span_text and len(span_text) < 200:
                        flags = span.get("flags", 0)
                        is_bold = bool(flags & 2**4)  # bit 4 = bold
                        level = 1 if span_size > 18 or is_bold else 2
                        all_sections.append(Section(
                            heading=span_text,
                            content=span_text,
                            level=level,
                            page_number=page_num + 1,
                        ))

    doc.close()

    # Warn about scanned pages
    if scanned_pages:
        print(
            f"[OCR NEEDED] Pages with little/no text detected (likely scanned): "
            f"{scanned_pages}. Route these pages to OCR for text extraction."
        )

    full_text = "\n\n".join(all_text_parts).strip()

    # If completely empty, provide a placeholder
    if not full_text:
        full_text = "[No extractable text — document may be fully scanned/image-based]"

    title = all_sections[0].heading if all_sections else None

    metadata = DocumentMetadata(
        source=str(Path(file_path).resolve()),
        format=InputFormat.PDF,
        title=title,
        total_pages=total_pages,
    )

    return Document(
        content=full_text,
        metadata=metadata,
        sections=all_sections,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class PDFLoader:
    """PDF document loader with pdfplumber primary and PyMuPDF fallback.

    Extracts text, heading structure, handles multi-column layouts, and
    detects scanned pages that need OCR processing.

    Usage:
        loader = PDFLoader()
        doc = loader.load("path/to/file.pdf")
    """

    def __init__(self) -> None:
        """Initialize PDFLoader."""
        pass

    def load(self, file_path: str) -> Document:
        """Load a PDF file and extract its content into a Document model.

        Uses pdfplumber as the primary extractor. Falls back to PyMuPDF (fitz)
        if pdfplumber fails or produces no output.

        Features:
        - Page-level text extraction with page numbers
        - Heading detection from font size analysis
        - Multi-column layout handling (left-then-right reading order)
        - Scanned/image-only PDF detection with OCR routing flag

        Args:
            file_path: Path to the PDF file.

        Returns:
            A Document instance with extracted content, metadata, and sections.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file is not a PDF.
        """
        return extract_pdf(file_path)

    def is_scanned(self, file_path: str) -> bool:
        """Check if a PDF is likely scanned (image-only, needs OCR).

        A PDF is considered scanned if more than half its pages have
        fewer than SCANNED_PAGE_CHAR_THRESHOLD characters of extractable text.

        Args:
            file_path: Path to the PDF file.

        Returns:
            True if the PDF appears to be scanned/image-based.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        try:
            import pdfplumber

            scanned_count = 0
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if len(text.strip()) < SCANNED_PAGE_CHAR_THRESHOLD:
                        scanned_count += 1

            return scanned_count > total_pages / 2
        except Exception:
            # Fall back to PyMuPDF check
            import fitz

            doc = fitz.open(file_path)
            scanned_count = 0
            total_pages = len(doc)
            for page in doc:
                text = page.get_text("text") or ""
                if len(text.strip()) < SCANNED_PAGE_CHAR_THRESHOLD:
                    scanned_count += 1
            doc.close()
            return scanned_count > total_pages / 2


def extract_pdf(file_path: str) -> Document:
    """Extract text and structure from a PDF file.

    Uses pdfplumber as the primary extractor with PyMuPDF as fallback.
    Detects headings from font sizes, handles multi-column layouts,
    and warns about scanned pages that need OCR.

    Args:
        file_path: Path to the PDF file.

    Returns:
        A Document instance with extracted content, metadata, and sections.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file is not a PDF.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {path.suffix}")

    # Try pdfplumber first
    result = _extract_with_pdfplumber(file_path)

    if result is not None:
        return result

    # Fallback to PyMuPDF
    return _extract_with_pymupdf(file_path)
