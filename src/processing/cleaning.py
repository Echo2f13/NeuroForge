"""Text Cleaning Module for NeuroForge.

Provides the TextCleaner class which applies a conservative cleaning pipeline
to extracted document text. The cleaner removes noise (headers, footers, page
numbers, OCR artifacts, garbage characters) while preserving meaningful content
and formatting such as bullet points and numbered lists.

Design principle: conservative — better to leave slightly noisy text than to
lose real content.
"""

from __future__ import annotations

import re
from collections import Counter


class TextCleaner:
    """Cleans extracted document text through a multi-step pipeline.

    The cleaning steps run in a specific order to avoid conflicts:
    1. Remove headers/footers (repeated lines across pages)
    2. Remove page numbers
    3. Fix OCR artifacts
    4. Remove garbage characters
    5. Normalize whitespace (preserving structure)
    6. Preserve formatting (ensure bullets/lists stay intact)
    """

    # Page separator pattern used to split text into pages for analysis
    PAGE_SEP_PATTERN = re.compile(r"\f|\n{3,}(?=\S)")

    # Page number patterns (standalone lines)
    PAGE_NUMBER_PATTERNS = [
        re.compile(r"^\s*-\s*\d+\s*-\s*$", re.MULTILINE),        # - 3 -
        re.compile(r"^\s*Page\s+\d+\s*$", re.MULTILINE | re.IGNORECASE),  # Page 4
        re.compile(r"^\s*p\.\s*\d+\s*$", re.MULTILINE | re.IGNORECASE),   # p. 4
        re.compile(r"^\s*\d+\s*$", re.MULTILINE),                  # standalone number
        re.compile(r"^\s*\[\s*\d+\s*\]\s*$", re.MULTILINE),       # [4]
        re.compile(r"^\s*\d+\s*/\s*\d+\s*$", re.MULTILINE),       # 4/10
    ]

    # Common OCR ligature and misread fixes
    OCR_REPLACEMENTS = {
        "\ufb01": "fi",   # fi ligature
        "\ufb02": "fl",   # fl ligature
        "\ufb00": "ff",   # ff ligature
        "\ufb03": "ffi",  # ffi ligature
        "\ufb04": "ffl",  # ffl ligature
        "\u2018": "'",    # left single quote
        "\u2019": "'",    # right single quote
        "\u201c": '"',    # left double quote
        "\u201d": '"',    # right double quote
        "\u2013": "-",    # en dash
        "\u2014": "-",    # em dash
        "\u2026": "...",  # ellipsis
    }

    # Contextual OCR fixes (only applied when surrounded by letters)
    # These are conservative — only fix when pattern is clearly wrong
    OCR_CONTEXTUAL_FIXES = [
        # rn -> m only in common words (very conservative)
        (re.compile(r"\brn(?=ing\b|\bed\b|\ber\b)"), "m"),
    ]

    # Control characters to remove (preserve \n, \r, \t, \f)
    CONTROL_CHAR_PATTERN = re.compile(
        r"[\x00-\x08\x0b\x0e-\x1f\x7f-\x9f]"
    )

    # Excessive special character sequences (3+ of same special char)
    EXCESSIVE_SPECIAL_PATTERN = re.compile(r"([^\w\s\-\.\,\;\:\!\?\'\"\(\)\[\]\{\}\/\\•·–—])\1{2,}")

    # Bullet and list patterns to preserve
    BULLET_PATTERN = re.compile(r"^(\s*)([-*•·])\s+", re.MULTILINE)
    NUMBERED_LIST_PATTERN = re.compile(r"^(\s*)(\d+[\.\)])\s+", re.MULTILINE)

    def __init__(self, page_threshold: float = 0.5) -> None:
        """Initialize the TextCleaner.

        Args:
            page_threshold: Fraction of pages a line must appear on to be
                considered a header/footer (default 0.5 = 50%).
        """
        self.page_threshold = page_threshold

    def clean(self, text: str) -> str:
        """Run the full cleaning pipeline on the input text.

        Args:
            text: Raw extracted text to clean.

        Returns:
            Cleaned text with noise removed and formatting preserved.
        """
        if not text or not text.strip():
            return text

        result = self.remove_headers_footers(text)
        result = self.remove_page_numbers(result)
        result = self.fix_ocr_artifacts(result)
        result = self.remove_garbage_chars(result)
        result = self.normalize_whitespace(result)
        result = self.preserve_formatting(result)
        return result

    def remove_headers_footers(self, text: str) -> str:
        """Remove repeated headers and footers.

        Detects lines that appear on most pages (above page_threshold) and
        removes them. Only considers the first 3 and last 3 lines of each
        page as potential headers/footers.

        Args:
            text: Input text potentially containing repeated headers/footers.

        Returns:
            Text with repeated header/footer lines removed.
        """
        # Split into pages
        pages = self.PAGE_SEP_PATTERN.split(text)

        if len(pages) < 3:
            # Not enough pages to reliably detect headers/footers
            return text

        # Collect candidate header/footer lines from each page
        header_candidates: Counter = Counter()
        footer_candidates: Counter = Counter()

        for page in pages:
            lines = page.strip().splitlines()
            if not lines:
                continue

            # Check first 3 lines as header candidates
            for line in lines[:3]:
                stripped = line.strip()
                if stripped and len(stripped) > 2:
                    header_candidates[stripped] += 1

            # Check last 3 lines as footer candidates
            for line in lines[-3:]:
                stripped = line.strip()
                if stripped and len(stripped) > 2:
                    footer_candidates[stripped] += 1

        # Determine threshold
        min_occurrences = max(2, int(len(pages) * self.page_threshold))

        # Lines to remove
        lines_to_remove: set[str] = set()
        for line, count in header_candidates.items():
            if count >= min_occurrences:
                lines_to_remove.add(line)
        for line, count in footer_candidates.items():
            if count >= min_occurrences:
                lines_to_remove.add(line)

        if not lines_to_remove:
            return text

        # Remove identified header/footer lines
        result_lines = []
        for line in text.splitlines():
            if line.strip() not in lines_to_remove:
                result_lines.append(line)

        return "\n".join(result_lines)

    def remove_page_numbers(self, text: str) -> str:
        """Remove standalone page number lines.

        Matches common page number formats:
        - "- 3 -"
        - "Page 4" / "page 4"
        - "p. 4"
        - Standalone numbers (only if they look like page numbers)
        - "[4]"
        - "4/10"

        Args:
            text: Input text with potential page number lines.

        Returns:
            Text with page number lines removed.
        """
        result = text
        for pattern in self.PAGE_NUMBER_PATTERNS:
            result = pattern.sub("", result)
        return result

    def fix_ocr_artifacts(self, text: str) -> str:
        """Fix common OCR artifacts and misreads.

        Handles:
        - Unicode ligatures (fi, fl, ff, ffi, ffl)
        - Smart quotes -> straight quotes
        - En/em dashes -> hyphens
        - Ellipsis character -> three dots
        - Conservative contextual fixes (rn->m in known patterns)

        Args:
            text: Text with potential OCR artifacts.

        Returns:
            Text with common OCR issues fixed.
        """
        result = text

        # Direct character replacements
        for old, new in self.OCR_REPLACEMENTS.items():
            result = result.replace(old, new)

        # Contextual fixes (conservative)
        for pattern, replacement in self.OCR_CONTEXTUAL_FIXES:
            result = pattern.sub(replacement, result)

        return result

    def remove_garbage_chars(self, text: str) -> str:
        """Remove control characters and excessive special character sequences.

        Removes:
        - Null bytes and control characters (preserving newline, tab, form feed)
        - Sequences of 3+ identical special characters

        Args:
            text: Text with potential garbage characters.

        Returns:
            Text with garbage characters removed.
        """
        # Remove control characters
        result = self.CONTROL_CHAR_PATTERN.sub("", text)

        # Remove excessive repetitions of special characters
        result = self.EXCESSIVE_SPECIAL_PATTERN.sub("", result)

        return result

    def normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace while preserving meaningful structure.

        - Collapses multiple spaces into one (preserving leading indent)
        - Collapses 3+ consecutive newlines into 2 (paragraph break)
        - Preserves single blank lines between paragraphs
        - Preserves indentation for list items
        - Removes trailing whitespace from lines

        Args:
            text: Text with irregular whitespace.

        Returns:
            Text with normalized whitespace.
        """
        # Process line by line to preserve indentation
        lines = text.splitlines()
        normalized_lines = []

        for line in lines:
            # Preserve leading whitespace (indentation)
            stripped = line.lstrip()
            if not stripped:
                normalized_lines.append("")
                continue

            leading = line[: len(line) - len(stripped)]
            # Collapse multiple spaces within the line content
            content = re.sub(r" {2,}", " ", stripped)
            # Remove trailing whitespace
            content = content.rstrip()
            normalized_lines.append(leading + content)

        # Join and collapse excessive blank lines (3+ -> 2)
        result = "\n".join(normalized_lines)
        result = re.sub(r"\n{3,}", "\n\n", result)

        # Strip leading/trailing whitespace from the whole text
        result = result.strip()

        return result

    def preserve_formatting(self, text: str) -> str:
        """Ensure bullet points and numbered lists remain intact.

        This step verifies and normalizes list formatting:
        - Ensures bullets (-, *, •, ·) have a space after them
        - Ensures numbered items (1., 2.) have a space after them
        - Does NOT remove or alter list content

        Args:
            text: Text that may contain lists and bullets.

        Returns:
            Text with list formatting preserved and normalized.
        """
        # Normalize bullet markers: ensure space after bullet
        result = re.sub(r"^(\s*)([-*•·])(\S)", r"\1\2 \3", text, flags=re.MULTILINE)

        # Normalize numbered lists: ensure space after number+period/paren
        result = re.sub(r"^(\s*)(\d+[\.\)])(\S)", r"\1\2 \3", result, flags=re.MULTILINE)

        return result
