"""Tests for the TextCleaner module.

Verifies cleaning pipeline behavior on noisy and clean text,
ensuring garbage is removed while meaningful content is preserved.
"""

from __future__ import annotations

import pytest

from src.processing.cleaning import TextCleaner


@pytest.fixture
def cleaner() -> TextCleaner:
    """Create a TextCleaner instance with default settings."""
    return TextCleaner()


# ---------------------------------------------------------------------------
# Full Pipeline Tests
# ---------------------------------------------------------------------------


class TestCleanPipeline:
    """Test the full clean() pipeline."""

    def test_clean_empty_string(self, cleaner):
        assert cleaner.clean("") == ""

    def test_clean_whitespace_only(self, cleaner):
        assert cleaner.clean("   \n\n   ") == "   \n\n   "

    def test_clean_already_clean_text(self, cleaner):
        text = "This is a perfectly clean paragraph.\n\nAnother paragraph here."
        result = cleaner.clean(text)
        assert "perfectly clean paragraph" in result
        assert "Another paragraph" in result

    def test_clean_preserves_meaningful_content(self, cleaner):
        text = "Important data: 42 results found.\n- Item one\n- Item two\n\n1. First\n2. Second"
        result = cleaner.clean(text)
        assert "Important data: 42 results found" in result
        assert "- Item one" in result
        assert "1. First" in result

    def test_clean_noisy_text(self, cleaner):
        text = (
            "Header Line\n"
            "\x00\x01Some text with \ufb01ligatures and \ufb02ags.\n"
            "- 3 -\n"
            "Real content here.\n"
            "   Multiple   spaces   collapse.\n"
            "\n\n\n\nToo many blank lines.\n"
        )
        result = cleaner.clean(text)
        assert "filigatures" in result
        assert "flags" in result
        assert "\x00" not in result
        assert "Multiple spaces collapse" in result
        # Excessive blank lines collapsed
        assert "\n\n\n" not in result


# ---------------------------------------------------------------------------
# Header/Footer Removal Tests
# ---------------------------------------------------------------------------


class TestRemoveHeadersFooters:
    """Test header/footer detection and removal."""

    def test_no_removal_with_few_pages(self, cleaner):
        text = "Page 1 content\n\nPage 2 content"
        result = cleaner.remove_headers_footers(text)
        assert result == text

    def test_removes_repeated_header(self, cleaner):
        # Simulate 4 pages with form feeds, each having same header
        pages = []
        for i in range(4):
            pages.append(f"Company Confidential\nPage {i+1} content here.\nMore text.")
        text = "\f".join(pages)
        result = cleaner.remove_headers_footers(text)
        assert "Company Confidential" not in result
        assert "content here" in result

    def test_removes_repeated_footer(self, cleaner):
        pages = []
        for i in range(4):
            pages.append(f"Content on page {i+1}.\nSome detail.\n© 2024 ACME Corp")
        text = "\f".join(pages)
        result = cleaner.remove_headers_footers(text)
        assert "© 2024 ACME Corp" not in result
        assert "Content on page" in result

    def test_preserves_unique_lines(self, cleaner):
        pages = []
        for i in range(4):
            pages.append(f"Report Title\nUnique content {i}.\nFooter Text Here")
        text = "\f".join(pages)
        result = cleaner.remove_headers_footers(text)
        # Unique content should remain
        assert "Unique content 0" in result
        assert "Unique content 3" in result


# ---------------------------------------------------------------------------
# Page Number Removal Tests
# ---------------------------------------------------------------------------


class TestRemovePageNumbers:
    """Test page number removal."""

    def test_removes_dash_format(self, cleaner):
        text = "Some text.\n- 3 -\nMore text."
        result = cleaner.remove_page_numbers(text)
        assert "- 3 -" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_removes_page_word_format(self, cleaner):
        text = "Content.\nPage 4\nMore content."
        result = cleaner.remove_page_numbers(text)
        assert "Page 4" not in result

    def test_removes_standalone_number(self, cleaner):
        text = "Paragraph one.\n7\nParagraph two."
        result = cleaner.remove_page_numbers(text)
        assert "\n7\n" not in result

    def test_preserves_numbers_in_text(self, cleaner):
        text = "There are 42 items in the list."
        result = cleaner.remove_page_numbers(text)
        assert "42" in result

    def test_removes_bracket_format(self, cleaner):
        text = "Text here.\n[5]\nMore text."
        result = cleaner.remove_page_numbers(text)
        assert "[5]" not in result

    def test_removes_fraction_format(self, cleaner):
        text = "Text.\n4/10\nMore text."
        result = cleaner.remove_page_numbers(text)
        assert "4/10" not in result


# ---------------------------------------------------------------------------
# OCR Artifact Fixes Tests
# ---------------------------------------------------------------------------


class TestFixOcrArtifacts:
    """Test OCR artifact correction."""

    def test_fi_ligature(self, cleaner):
        text = "The \ufb01rst \ufb01nding was signi\ufb01cant."
        result = cleaner.fix_ocr_artifacts(text)
        assert "first" in result
        assert "finding" in result
        assert "significant" in result

    def test_fl_ligature(self, cleaner):
        text = "The \ufb02ow of \ufb02uid was measured."
        result = cleaner.fix_ocr_artifacts(text)
        assert "flow" in result
        assert "fluid" in result

    def test_ff_ligature(self, cleaner):
        text = "The e\ufb00ect was di\ufb00erent."
        result = cleaner.fix_ocr_artifacts(text)
        assert "effect" in result
        assert "different" in result

    def test_smart_quotes_normalized(self, cleaner):
        text = "\u201cHello,\u201d she said. \u2018World.\u2019"
        result = cleaner.fix_ocr_artifacts(text)
        assert '"Hello,"' in result
        assert "'World.'" in result

    def test_en_em_dash_normalized(self, cleaner):
        text = "range 1\u20135 and also\u2014this"
        result = cleaner.fix_ocr_artifacts(text)
        assert "1-5" in result
        assert "also-this" in result

    def test_ellipsis_expanded(self, cleaner):
        text = "Wait\u2026 what?"
        result = cleaner.fix_ocr_artifacts(text)
        assert "Wait... what?" in result


# ---------------------------------------------------------------------------
# Garbage Character Removal Tests
# ---------------------------------------------------------------------------


class TestRemoveGarbageChars:
    """Test garbage character removal."""

    def test_removes_null_bytes(self, cleaner):
        text = "Hello\x00World\x00!"
        result = cleaner.remove_garbage_chars(text)
        assert "\x00" not in result
        assert "HelloWorld!" in result

    def test_removes_control_chars(self, cleaner):
        text = "Data\x01\x02\x03here."
        result = cleaner.remove_garbage_chars(text)
        assert "Datahere." in result

    def test_preserves_newlines_and_tabs(self, cleaner):
        text = "Line one\nLine two\tTabbed"
        result = cleaner.remove_garbage_chars(text)
        assert "\n" in result
        assert "\t" in result

    def test_removes_excessive_special_chars(self, cleaner):
        text = "Normal text ~~~~ more text"
        result = cleaner.remove_garbage_chars(text)
        assert "~~~~" not in result
        assert "Normal text" in result
        assert "more text" in result

    def test_preserves_normal_punctuation(self, cleaner):
        text = "Hello, world! How are you? Fine (thanks)."
        result = cleaner.remove_garbage_chars(text)
        assert result == text


# ---------------------------------------------------------------------------
# Whitespace Normalization Tests
# ---------------------------------------------------------------------------


class TestNormalizeWhitespace:
    """Test whitespace normalization."""

    def test_collapses_multiple_spaces(self, cleaner):
        text = "Too    many     spaces    here."
        result = cleaner.normalize_whitespace(text)
        assert "Too many spaces here." in result

    def test_collapses_excessive_newlines(self, cleaner):
        text = "Para one.\n\n\n\n\nPara two."
        result = cleaner.normalize_whitespace(text)
        assert "\n\n\n" not in result
        assert "Para one.\n\nPara two." == result

    def test_preserves_single_blank_line(self, cleaner):
        text = "Paragraph one.\n\nParagraph two."
        result = cleaner.normalize_whitespace(text)
        assert "Paragraph one.\n\nParagraph two." == result

    def test_preserves_indentation(self, cleaner):
        text = "Header\n  Indented line\n    Deeper indent"
        result = cleaner.normalize_whitespace(text)
        assert "  Indented line" in result
        assert "    Deeper indent" in result

    def test_strips_trailing_whitespace(self, cleaner):
        text = "Hello   \nWorld   "
        result = cleaner.normalize_whitespace(text)
        assert "Hello\nWorld" == result

    def test_strips_overall_leading_trailing(self, cleaner):
        text = "\n\n  Content here.  \n\n"
        result = cleaner.normalize_whitespace(text)
        assert result == "Content here."


# ---------------------------------------------------------------------------
# Formatting Preservation Tests
# ---------------------------------------------------------------------------


class TestPreserveFormatting:
    """Test that bullets and numbered lists are preserved."""

    def test_bullet_dash_preserved(self, cleaner):
        text = "Items:\n- First item\n- Second item"
        result = cleaner.preserve_formatting(text)
        assert "- First item" in result
        assert "- Second item" in result

    def test_bullet_asterisk_preserved(self, cleaner):
        text = "Items:\n* First item\n* Second item"
        result = cleaner.preserve_formatting(text)
        assert "* First item" in result
        assert "* Second item" in result

    def test_bullet_dot_preserved(self, cleaner):
        text = "Items:\n• First item\n• Second item"
        result = cleaner.preserve_formatting(text)
        assert "• First item" in result
        assert "• Second item" in result

    def test_numbered_list_preserved(self, cleaner):
        text = "Steps:\n1. Do this\n2. Do that\n3. Done"
        result = cleaner.preserve_formatting(text)
        assert "1. Do this" in result
        assert "2. Do that" in result
        assert "3. Done" in result

    def test_adds_space_after_bullet_if_missing(self, cleaner):
        text = "-Item without space"
        result = cleaner.preserve_formatting(text)
        assert "- Item without space" in result

    def test_adds_space_after_number_if_missing(self, cleaner):
        text = "1.Item without space"
        result = cleaner.preserve_formatting(text)
        assert "1. Item without space" in result

    def test_indented_list_preserved(self, cleaner):
        text = "  - Sub item\n    - Deeper sub item"
        result = cleaner.preserve_formatting(text)
        assert "  - Sub item" in result
        assert "    - Deeper sub item" in result


# ---------------------------------------------------------------------------
# Integration / Edge Case Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and integration scenarios."""

    def test_conservative_does_not_remove_real_content(self, cleaner):
        """Cleaner should NOT remove content that might be meaningful."""
        text = "Results: 42 patients, 15 controls.\nP-value: 0.001\nCI: [0.5, 0.8]"
        result = cleaner.clean(text)
        assert "42 patients" in result
        assert "0.001" in result
        assert "[0.5, 0.8]" in result

    def test_mixed_formatting_preserved(self, cleaner):
        text = (
            "# Heading\n\n"
            "Some paragraph text.\n\n"
            "- Bullet one\n"
            "- Bullet two\n\n"
            "1. Step one\n"
            "2. Step two\n"
        )
        result = cleaner.clean(text)
        assert "# Heading" in result
        assert "- Bullet one" in result
        assert "1. Step one" in result

    def test_long_document_performance(self, cleaner):
        """Ensure cleaner handles large text without issues."""
        text = "This is a sentence. " * 10000
        result = cleaner.clean(text)
        assert len(result) > 0
        assert "This is a sentence." in result

    def test_unicode_content_preserved(self, cleaner):
        text = "Ñoño said: café, naïve, résumé, über"
        result = cleaner.clean(text)
        assert "café" in result
        assert "naïve" in result
        assert "résumé" in result
        assert "über" in result
