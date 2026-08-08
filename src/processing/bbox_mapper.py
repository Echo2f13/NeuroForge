"""Bounding Box Mapper for NeuroForge.

Maps extracted text content to bounding box coordinates for PDF highlighting.
Enables precise source attribution by tracking the visual location of text
in PDF documents.

Usage:
    from src.processing.bbox_mapper import BboxMapper, PageBboxData
    
    mapper = BboxMapper()
    page_data = mapper.extract_page_bboxes(pdf_path)
    chunk_bboxes = mapper.map_text_to_bboxes(text, start_char, end_char, page_data)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from models import BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class WordBox:
    """A word with its bounding box coordinates.
    
    Attributes:
        text: The word text.
        x0: Left coordinate (points).
        y0: Top coordinate (points).
        x1: Right coordinate (points).
        y1: Bottom coordinate (points).
        page_number: Page number (1-indexed).
        char_start: Starting character index in page text.
        char_end: Ending character index in page text.
    """
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page_number: int
    char_start: int = 0
    char_end: int = 0


@dataclass
class PageBboxData:
    """Bounding box data for a single PDF page.
    
    Attributes:
        page_number: Page number (1-indexed).
        page_width: Page width in points.
        page_height: Page height in points.
        word_boxes: List of word bounding boxes.
        text: Full text of the page.
        char_offset: Character offset from document start.
    """
    page_number: int
    page_width: float
    page_height: float
    word_boxes: list[WordBox] = field(default_factory=list)
    text: str = ""
    char_offset: int = 0  # Offset from document start


@dataclass
class DocumentBboxData:
    """Bounding box data for an entire document.
    
    Attributes:
        pages: List of page bounding box data.
        total_chars: Total character count in document.
    """
    pages: list[PageBboxData] = field(default_factory=list)
    total_chars: int = 0


class BboxMapper:
    """Maps text content to bounding box coordinates.
    
    Extracts word-level bounding boxes from PDFs and provides methods
    to map arbitrary text ranges to their visual locations.
    """
    
    def __init__(self) -> None:
        """Initialize the BboxMapper."""
        pass
    
    def extract_document_bboxes(self, file_path: str) -> DocumentBboxData:
        """Extract bounding box data from a PDF document.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            DocumentBboxData with per-page bounding box information.
            
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
        result = self._extract_with_pdfplumber(file_path)
        
        if result is not None:
            return result
        
        # Fallback to PyMuPDF
        return self._extract_with_pymupdf(file_path)
    
    def _extract_with_pdfplumber(self, file_path: str) -> Optional[DocumentBboxData]:
        """Extract bounding boxes using pdfplumber.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            DocumentBboxData or None if extraction fails.
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed, falling back to PyMuPDF")
            return None
        
        try:
            doc_data = DocumentBboxData()
            char_offset = 0
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_data = PageBboxData(
                        page_number=page_num,
                        page_width=page.width,
                        page_height=page.height,
                        char_offset=char_offset,
                    )
                    
                    # Extract words with bounding boxes
                    words = page.extract_words() or []
                    page_text = page.extract_text() or ""
                    page_data.text = page_text
                    
                    # Track character positions within the page
                    current_char = 0
                    
                    for word in words:
                        word_text = word.get("text", "")
                        if not word_text:
                            continue
                        
                        # Find this word in the page text
                        word_pos = page_text.find(word_text, current_char)
                        if word_pos == -1:
                            word_pos = current_char
                        
                        word_box = WordBox(
                            text=word_text,
                            x0=word.get("x0", 0),
                            y0=word.get("top", 0),
                            x1=word.get("x1", 0),
                            y1=word.get("bottom", 0),
                            page_number=page_num,
                            char_start=word_pos,
                            char_end=word_pos + len(word_text),
                        )
                        page_data.word_boxes.append(word_box)
                        current_char = word_pos + len(word_text)
                    
                    doc_data.pages.append(page_data)
                    char_offset += len(page_text) + 2  # +2 for page separator
            
            doc_data.total_chars = char_offset
            return doc_data
            
        except Exception as e:
            logger.warning(f"pdfplumber bbox extraction failed: {e}")
            return None
    
    def _extract_with_pymupdf(self, file_path: str) -> DocumentBboxData:
        """Extract bounding boxes using PyMuPDF (fitz).
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            DocumentBboxData with per-page bounding box information.
        """
        import fitz  # PyMuPDF
        
        doc_data = DocumentBboxData()
        char_offset = 0
        
        doc = fitz.open(file_path)
        
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                rect = page.rect
                
                page_data = PageBboxData(
                    page_number=page_num + 1,
                    page_width=rect.width,
                    page_height=rect.height,
                    char_offset=char_offset,
                )
                
                # Get text with positions
                page_text = page.get_text("text") or ""
                page_data.text = page_text
                
                # Extract words with bounding boxes
                words = page.get_text("words")  # Returns list of tuples
                current_char = 0
                
                for word_tuple in words:
                    # word_tuple: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
                    if len(word_tuple) < 5:
                        continue
                    
                    x0, y0, x1, y1, word_text = word_tuple[:5]
                    
                    if not word_text:
                        continue
                    
                    # Find word position in page text
                    word_pos = page_text.find(word_text, current_char)
                    if word_pos == -1:
                        word_pos = current_char
                    
                    word_box = WordBox(
                        text=word_text,
                        x0=x0,
                        y0=y0,
                        x1=x1,
                        y1=y1,
                        page_number=page_num + 1,
                        char_start=word_pos,
                        char_end=word_pos + len(word_text),
                    )
                    page_data.word_boxes.append(word_box)
                    current_char = word_pos + len(word_text)
                
                doc_data.pages.append(page_data)
                char_offset += len(page_text) + 2
        finally:
            doc.close()
        
        doc_data.total_chars = char_offset
        return doc_data
    
    def map_text_to_bboxes(
        self,
        doc_data: DocumentBboxData,
        start_char: int,
        end_char: int,
    ) -> list[BoundingBox]:
        """Map a character range to bounding boxes.
        
        Given document-level character offsets, returns the bounding boxes
        that cover the specified text range.
        
        Args:
            doc_data: Document bounding box data.
            start_char: Starting character index in document.
            end_char: Ending character index in document.
            
        Returns:
            List of BoundingBox objects covering the text range.
        """
        bboxes: list[BoundingBox] = []
        
        for page_data in doc_data.pages:
            page_start = page_data.char_offset
            page_end = page_start + len(page_data.text)
            
            # Check if this page overlaps with our range
            if end_char <= page_start or start_char >= page_end:
                continue
            
            # Calculate local character offsets for this page
            local_start = max(0, start_char - page_start)
            local_end = min(len(page_data.text), end_char - page_start)
            
            # Find word boxes that overlap with this range
            page_bboxes = self._get_word_boxes_in_range(
                page_data, local_start, local_end
            )
            bboxes.extend(page_bboxes)
        
        return bboxes
    
    def _get_word_boxes_in_range(
        self,
        page_data: PageBboxData,
        start_char: int,
        end_char: int,
    ) -> list[BoundingBox]:
        """Get bounding boxes for words in a character range on a page.
        
        Args:
            page_data: Page bounding box data.
            start_char: Starting character index (page-local).
            end_char: Ending character index (page-local).
            
        Returns:
            List of BoundingBox objects.
        """
        bboxes: list[BoundingBox] = []
        
        for word_box in page_data.word_boxes:
            # Check if this word overlaps with the range
            if word_box.char_end <= start_char or word_box.char_start >= end_char:
                continue
            
            # Convert to normalized coordinates (0-100%)
            bbox = BoundingBox(
                x0=(word_box.x0 / page_data.page_width) * 100,
                y0=(word_box.y0 / page_data.page_height) * 100,
                x1=(word_box.x1 / page_data.page_width) * 100,
                y1=(word_box.y1 / page_data.page_height) * 100,
                page_width=page_data.page_width,
                page_height=page_data.page_height,
            )
            bboxes.append(bbox)
        
        # Merge adjacent boxes on the same line for cleaner highlighting
        return self._merge_adjacent_boxes(bboxes)
    
    def _merge_adjacent_boxes(
        self,
        boxes: list[BoundingBox],
        y_tolerance: float = 1.0,
        x_gap: float = 2.0,
    ) -> list[BoundingBox]:
        """Merge adjacent bounding boxes on the same line.
        
        Args:
            boxes: List of bounding boxes to merge.
            y_tolerance: Maximum Y difference to consider same line (%).
            x_gap: Maximum X gap to merge boxes (%).
            
        Returns:
            Merged list of bounding boxes.
        """
        if not boxes:
            return []
        
        # Sort by y0, then x0
        sorted_boxes = sorted(boxes, key=lambda b: (b.y0, b.x0))
        
        merged: list[BoundingBox] = []
        current = sorted_boxes[0]
        
        for box in sorted_boxes[1:]:
            # Check if on same line and adjacent
            same_line = abs(box.y0 - current.y0) < y_tolerance
            adjacent = (box.x0 - current.x1) < x_gap
            
            if same_line and adjacent:
                # Merge: extend current box
                current = BoundingBox(
                    x0=current.x0,
                    y0=min(current.y0, box.y0),
                    x1=box.x1,
                    y1=max(current.y1, box.y1),
                    page_width=current.page_width,
                    page_height=current.page_height,
                )
            else:
                merged.append(current)
                current = box
        
        merged.append(current)
        return merged
    
    def get_page_for_char(
        self,
        doc_data: DocumentBboxData,
        char_index: int,
    ) -> Optional[int]:
        """Get the page number for a character index.
        
        Args:
            doc_data: Document bounding box data.
            char_index: Character index in document.
            
        Returns:
            Page number (1-indexed) or None if not found.
        """
        for page_data in doc_data.pages:
            page_start = page_data.char_offset
            page_end = page_start + len(page_data.text)
            
            if page_start <= char_index < page_end:
                return page_data.page_number
        
        return None
    
    def get_line_numbers(
        self,
        page_data: PageBboxData,
        start_char: int,
        end_char: int,
    ) -> tuple[Optional[int], Optional[int]]:
        """Get line numbers for a character range on a page.
        
        Args:
            page_data: Page bounding box data.
            start_char: Starting character index (page-local).
            end_char: Ending character index (page-local).
            
        Returns:
            Tuple of (start_line, end_line) numbers (1-indexed).
        """
        if not page_data.text:
            return None, None
        
        lines = page_data.text.split('\n')
        char_pos = 0
        start_line = None
        end_line = None
        
        for line_num, line in enumerate(lines, start=1):
            line_end = char_pos + len(line)
            
            # Check if start_char is in this line
            if start_line is None and start_char <= line_end:
                start_line = line_num
            
            # Check if end_char is in this line
            if end_char <= line_end + 1:  # +1 for newline
                end_line = line_num
                break
            
            char_pos = line_end + 1  # +1 for newline
        
        # Handle case where end is past last line
        if start_line and end_line is None:
            end_line = len(lines)
        
        return start_line, end_line
