"""Tests for the YouTube Transcript Loader.

Tests cover:
- Video ID extraction from various URL formats
- Timestamp formatting
- Transcript grouping into time-based sections
- Graceful handling of unavailable transcripts
- Full extract_youtube flow with mocked API
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from models.document import InputFormat
from src.ingestion.youtube_loader import (
    SECTION_INTERVAL_SECONDS,
    YouTubeLoader,
    _format_timestamp,
    _group_transcript_into_sections,
    extract_video_id,
    extract_youtube,
)


# ============================================================================
# Tests for extract_video_id
# ============================================================================


class TestExtractVideoId:
    """Tests for parsing video IDs from various YouTube URL formats."""

    def test_standard_watch_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120&list=PLxyz"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_short_url(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_short_url_with_params(self):
        url = "https://youtu.be/dQw4w9WgXcQ?t=30"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_embed_url(self):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_v_url(self):
        url = "https://www.youtube.com/v/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_mobile_url(self):
        url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_bare_video_id(self):
        assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_nocookie_embed(self):
        url = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_live_url(self):
        url = "https://www.youtube.com/live/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_empty_url_raises(self):
        with pytest.raises(ValueError, match="URL cannot be empty"):
            extract_video_id("")

    def test_whitespace_url_raises(self):
        with pytest.raises(ValueError, match="URL cannot be empty"):
            extract_video_id("   ")

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Unrecognized YouTube URL format"):
            extract_video_id("https://example.com/video/123")

    def test_youtube_url_missing_v_param(self):
        with pytest.raises(ValueError, match="Missing 'v' parameter"):
            extract_video_id("https://www.youtube.com/watch?list=PLxyz")

    def test_strips_whitespace(self):
        url = "  https://youtu.be/dQw4w9WgXcQ  "
        assert extract_video_id(url) == "dQw4w9WgXcQ"


# ============================================================================
# Tests for _format_timestamp
# ============================================================================


class TestFormatTimestamp:
    """Tests for timestamp formatting."""

    def test_zero_seconds(self):
        assert _format_timestamp(0) == "00:00"

    def test_seconds_only(self):
        assert _format_timestamp(45) == "00:45"

    def test_minutes_and_seconds(self):
        assert _format_timestamp(125) == "02:05"

    def test_exactly_one_hour(self):
        assert _format_timestamp(3600) == "01:00:00"

    def test_hours_minutes_seconds(self):
        assert _format_timestamp(3661) == "01:01:01"

    def test_large_value(self):
        assert _format_timestamp(7384) == "02:03:04"


# ============================================================================
# Tests for _group_transcript_into_sections
# ============================================================================


class TestGroupTranscriptIntoSections:
    """Tests for grouping transcript snippets into time-based sections."""

    def test_empty_transcript(self):
        sections = _group_transcript_into_sections([])
        assert sections == []

    def test_single_short_transcript(self):
        """A single snippet within the first interval produces one section."""
        snippets = [MagicMock(start=0.0, text="Hello world")]
        sections = _group_transcript_into_sections(snippets, interval_seconds=300)
        assert len(sections) == 1
        assert sections[0].heading == "[00:00 - 05:00]"
        assert "Hello world" in sections[0].content

    def test_multiple_sections(self):
        """Snippets spanning multiple intervals produce multiple sections."""
        snippets = [
            MagicMock(start=0.0, text="Segment 1"),
            MagicMock(start=60.0, text="Segment 2"),
            MagicMock(start=310.0, text="Segment 3"),
            MagicMock(start=620.0, text="Segment 4"),
        ]
        sections = _group_transcript_into_sections(snippets, interval_seconds=300)
        assert len(sections) == 3
        assert sections[0].heading == "[00:00 - 05:00]"
        assert "Segment 1" in sections[0].content
        assert "Segment 2" in sections[0].content
        assert sections[1].heading == "[05:00 - 10:00]"
        assert "Segment 3" in sections[1].content
        assert sections[2].heading == "[10:00 - 15:00]"
        assert "Segment 4" in sections[2].content

    def test_section_level_is_2(self):
        """All generated sections use heading level 2."""
        snippets = [MagicMock(start=0.0, text="Test")]
        sections = _group_transcript_into_sections(snippets)
        assert all(s.level == 2 for s in sections)

    def test_works_with_dict_snippets(self):
        """Should handle dict-based snippets (raw data format)."""
        snippets = [
            {"start": 0.0, "text": "Hello", "duration": 2.0},
            {"start": 350.0, "text": "World", "duration": 1.5},
        ]
        sections = _group_transcript_into_sections(snippets, interval_seconds=300)
        assert len(sections) == 2


# ============================================================================
# Tests for extract_youtube (integration with mocked API)
# ============================================================================


class TestExtractYoutube:
    """Tests for the main extract_youtube function with mocked youtube-transcript-api."""

    def _make_mock_snippet(self, start: float, text: str, duration: float = 2.0):
        """Create a mock transcript snippet."""
        snippet = MagicMock()
        snippet.start = start
        snippet.text = text
        snippet.duration = duration
        return snippet

    @patch("src.ingestion.youtube_loader.YouTubeTranscriptApi")
    def test_successful_manual_transcript(self, MockApi):
        """Should prefer manual transcript and build Document correctly."""
        mock_api = MockApi.return_value
        mock_transcript_list = MagicMock()
        mock_api.list.return_value = mock_transcript_list

        # Simulate finding a manual transcript
        mock_transcript = MagicMock()
        mock_transcript.is_generated = False
        snippets = [
            self._make_mock_snippet(0.0, "Hello everyone"),
            self._make_mock_snippet(2.0, "Welcome to the course"),
        ]
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = lambda self: iter(snippets)
        mock_fetched.__len__ = lambda self: len(snippets)
        mock_transcript.fetch.return_value = mock_fetched
        mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript

        doc = extract_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert doc.metadata.format == InputFormat.YOUTUBE
        assert doc.metadata.source == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert doc.metadata.title == "dQw4w9WgXcQ"
        assert "Hello everyone" in doc.content
        assert "Welcome to the course" in doc.content
        assert len(doc.sections) >= 1

    @patch("src.ingestion.youtube_loader.YouTubeTranscriptApi")
    def test_fallback_to_auto_generated(self, MockApi):
        """Should fall back to auto-generated transcript if manual is unavailable."""
        mock_api = MockApi.return_value
        mock_transcript_list = MagicMock()
        mock_api.list.return_value = mock_transcript_list

        # Manual transcript not available
        mock_transcript_list.find_manually_created_transcript.side_effect = Exception(
            "No manual transcript"
        )

        # Auto-generated available
        mock_transcript = MagicMock()
        mock_transcript.is_generated = True
        snippets = [self._make_mock_snippet(0.0, "Auto generated text")]
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = lambda self: iter(snippets)
        mock_fetched.__len__ = lambda self: len(snippets)
        mock_transcript.fetch.return_value = mock_fetched
        mock_transcript_list.find_transcript.return_value = mock_transcript

        doc = extract_youtube("https://youtu.be/dQw4w9WgXcQ")

        assert "Auto generated text" in doc.content
        assert doc.metadata.format == InputFormat.YOUTUBE

    @patch("src.ingestion.youtube_loader.YouTubeTranscriptApi")
    def test_unavailable_transcript_graceful(self, MockApi):
        """Should return Document with placeholder content when transcript unavailable."""
        mock_api = MockApi.return_value
        mock_api.list.side_effect = Exception("Transcripts are disabled for this video")

        doc = extract_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert "[Transcript unavailable]" in doc.content
        assert doc.metadata.format == InputFormat.YOUTUBE
        assert doc.metadata.title == "dQw4w9WgXcQ"
        assert "WARNING" in (doc.metadata.author or "")
        assert doc.sections == []

    def test_invalid_url_raises_value_error(self):
        """Should raise ValueError for completely invalid URLs."""
        with pytest.raises(ValueError):
            extract_youtube("not-a-valid-url-at-all-123456")

    @patch("src.ingestion.youtube_loader.YouTubeTranscriptApi")
    def test_bare_video_id_builds_url(self, MockApi):
        """Should construct full URL when given a bare video ID."""
        mock_api = MockApi.return_value
        mock_api.list.side_effect = Exception("Test error")

        doc = extract_youtube("dQw4w9WgXcQ")

        assert doc.metadata.source == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    @patch("src.ingestion.youtube_loader.YouTubeTranscriptApi")
    def test_sections_have_timestamp_headings(self, MockApi):
        """Sections should have timestamp-based headings."""
        mock_api = MockApi.return_value
        mock_transcript_list = MagicMock()
        mock_api.list.return_value = mock_transcript_list

        # Create snippets spanning multiple 5-min intervals
        snippets = [
            self._make_mock_snippet(0.0, "Intro text"),
            self._make_mock_snippet(120.0, "More content"),
            self._make_mock_snippet(310.0, "Second section"),
        ]
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = lambda self: iter(snippets)
        mock_fetched.__len__ = lambda self: len(snippets)

        mock_transcript = MagicMock()
        mock_transcript.is_generated = False
        mock_transcript.fetch.return_value = mock_fetched
        mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript

        doc = extract_youtube("https://www.youtube.com/watch?v=test12345ab")

        assert len(doc.sections) >= 1
        # Check that headings contain timestamp patterns
        for section in doc.sections:
            assert "[" in section.heading
            assert "]" in section.heading


# ============================================================================
# Tests for YouTubeLoader class
# ============================================================================


class TestYouTubeLoader:
    """Tests for the YouTubeLoader class interface."""

    def test_instantiation(self):
        """YouTubeLoader can be instantiated without arguments."""
        loader = YouTubeLoader()
        assert loader is not None

    @patch("src.ingestion.youtube_loader.YouTubeTranscriptApi")
    def test_load_delegates_to_extract_youtube(self, MockApi):
        """YouTubeLoader.load() produces the same result as extract_youtube."""
        mock_api = MockApi.return_value
        mock_transcript_list = MagicMock()
        mock_api.list.return_value = mock_transcript_list

        snippet = MagicMock()
        snippet.start = 0.0
        snippet.text = "Test content"
        snippet.duration = 2.0

        mock_fetched = MagicMock()
        mock_fetched.__iter__ = lambda self: iter([snippet])
        mock_fetched.__len__ = lambda self: 1

        mock_transcript = MagicMock()
        mock_transcript.is_generated = False
        mock_transcript.fetch.return_value = mock_fetched
        mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript

        loader = YouTubeLoader()
        doc = loader.load("https://www.youtube.com/watch?v=test12345ab")

        assert doc.metadata.format == InputFormat.YOUTUBE
        assert "Test content" in doc.content
        assert doc.metadata.source == "https://www.youtube.com/watch?v=test12345ab"

    def test_load_invalid_url_raises(self):
        """YouTubeLoader.load() raises ValueError for invalid URLs."""
        loader = YouTubeLoader()
        with pytest.raises(ValueError):
            loader.load("not-a-valid-url-at-all-123456")

    def test_importable_from_ingestion_package(self):
        """YouTubeLoader is importable from src.ingestion."""
        from src.ingestion import YouTubeLoader as LoaderFromPackage
        assert LoaderFromPackage is YouTubeLoader
