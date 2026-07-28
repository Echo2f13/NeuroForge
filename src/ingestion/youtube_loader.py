"""YouTube Transcript Loader for NeuroForge.

Extracts transcripts from YouTube videos using youtube-transcript-api.
Supports auto-generated and manual captions, groups transcript segments
into time-based sections, and handles unavailable transcripts gracefully.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

from models.document import Document, DocumentMetadata, InputFormat, Section

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

# Time-based section grouping interval (seconds)
SECTION_INTERVAL_SECONDS = 300  # 5 minutes


def extract_video_id(url: str) -> str:
    """Parse a YouTube video ID from various URL formats.

    Supported formats:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtube.com/watch?v=VIDEO_ID
        - https://m.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://www.youtube.com/v/VIDEO_ID
        - https://www.youtube.com/shorts/VIDEO_ID
        - Plain video ID string (11 characters)

    Args:
        url: YouTube URL or video ID string.

    Returns:
        The extracted video ID.

    Raises:
        ValueError: If the URL format is not recognized or video ID cannot be extracted.
    """
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")

    url = url.strip()

    # Check if it's already a bare video ID (typically 11 chars, alphanumeric + _ -)
    if re.match(r"^[A-Za-z0-9_-]{11}$", url):
        return url

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"Invalid URL format: {url}") from e

    # Handle youtu.be short URLs
    if parsed.hostname in ("youtu.be",):
        video_id = parsed.path.lstrip("/")
        if video_id:
            return video_id.split("/")[0]
        raise ValueError(f"Could not extract video ID from short URL: {url}")

    # Handle youtube.com variants
    if parsed.hostname in (
        "www.youtube.com",
        "youtube.com",
        "m.youtube.com",
        "www.youtube-nocookie.com",
    ):
        # Standard watch URL: /watch?v=VIDEO_ID
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            video_ids = qs.get("v")
            if video_ids:
                return video_ids[0]
            raise ValueError(f"Missing 'v' parameter in URL: {url}")

        # Embed, shorts, or /v/ URLs: /embed/VIDEO_ID, /v/VIDEO_ID, /shorts/VIDEO_ID
        path_patterns = ("/embed/", "/v/", "/shorts/", "/live/")
        for pattern in path_patterns:
            if parsed.path.startswith(pattern):
                video_id = parsed.path[len(pattern):].split("/")[0]
                if video_id:
                    return video_id

    raise ValueError(
        f"Unrecognized YouTube URL format: {url}. "
        "Supported formats: youtube.com/watch?v=, youtu.be/, /embed/, /shorts/, /v/"
    )


def _format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS timestamp string.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted timestamp string.
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _group_transcript_into_sections(
    transcript_snippets: list,
    interval_seconds: int = SECTION_INTERVAL_SECONDS,
) -> list[Section]:
    """Group transcript snippets into time-based sections.

    Groups every `interval_seconds` worth of transcript text into a single
    Section with the timestamp range as the heading.

    Args:
        transcript_snippets: List of transcript snippet objects with text and start attributes.
        interval_seconds: Number of seconds per section group.

    Returns:
        List of Section objects with timestamp headings.
    """
    if not transcript_snippets:
        return []

    sections: list[Section] = []
    current_texts: list[str] = []
    section_start_time: float = 0.0
    current_boundary: float = interval_seconds

    for snippet in transcript_snippets:
        start = snippet.start if hasattr(snippet, "start") else snippet["start"]
        text = snippet.text if hasattr(snippet, "text") else snippet["text"]

        # If this snippet crosses the current boundary, finalize the section
        if start >= current_boundary and current_texts:
            heading = (
                f"[{_format_timestamp(section_start_time)} - "
                f"{_format_timestamp(current_boundary)}]"
            )
            content = " ".join(current_texts).strip()
            if content:
                sections.append(
                    Section(heading=heading, content=content, level=2)
                )
            current_texts = []
            section_start_time = current_boundary
            # Advance boundary to cover the current snippet
            while current_boundary <= start:
                current_boundary += interval_seconds

        current_texts.append(text.strip())

    # Finalize remaining text
    if current_texts:
        content = " ".join(current_texts).strip()
        if content:
            heading = (
                f"[{_format_timestamp(section_start_time)} - "
                f"{_format_timestamp(current_boundary)}]"
            )
            sections.append(Section(heading=heading, content=content, level=2))

    return sections


def extract_youtube(url: str) -> Document:
    """Extract transcript from a YouTube video and return a Document.

    Attempts to fetch the transcript using youtube-transcript-api. Prefers
    manually created captions over auto-generated ones. Falls back to
    auto-generated if manual is unavailable.

    If no transcript is available, returns a Document with a placeholder
    content and a warning note in metadata.

    Args:
        url: YouTube video URL or video ID.

    Returns:
        Document with transcript content, time-based sections, and metadata.

    Raises:
        ValueError: If the URL/video ID is invalid.
    """
    # Extract video ID (may raise ValueError for invalid URLs)
    video_id = extract_video_id(url)
    source_url = url if url.startswith("http") else f"https://www.youtube.com/watch?v={video_id}"

    if YouTubeTranscriptApi is None:
        raise ImportError(
            "youtube-transcript-api is required. Install with: "
            "pip install youtube-transcript-api"
        )

    # Attempt to fetch transcript
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)

        # Prefer manual captions, fall back to auto-generated
        fetched_transcript: Optional[object] = None
        is_generated = False

        try:
            transcript = transcript_list.find_manually_created_transcript(["en"])
            fetched_transcript = transcript.fetch()
            is_generated = False
            logger.info(
                "Found manual English transcript for video %s", video_id
            )
        except Exception:
            # Fall back to any available transcript (auto-generated included)
            try:
                transcript = transcript_list.find_transcript(["en"])
                fetched_transcript = transcript.fetch()
                is_generated = transcript.is_generated
                logger.info(
                    "Found %s English transcript for video %s",
                    "auto-generated" if is_generated else "manual",
                    video_id,
                )
            except Exception:
                # Try fetching any available transcript regardless of language
                try:
                    for t in transcript_list:
                        fetched_transcript = t.fetch()
                        is_generated = t.is_generated
                        logger.info(
                            "Found %s transcript (%s) for video %s",
                            "auto-generated" if is_generated else "manual",
                            t.language,
                            video_id,
                        )
                        break
                except Exception:
                    fetched_transcript = None

        if fetched_transcript is None or len(fetched_transcript) == 0:
            return _create_empty_document(video_id, source_url, "No transcript content available")

        # Build full text from transcript snippets
        full_text = " ".join(
            snippet.text.strip() for snippet in fetched_transcript
        )

        if not full_text.strip():
            return _create_empty_document(video_id, source_url, "Transcript is empty")

        # Create time-based sections
        sections = _group_transcript_into_sections(list(fetched_transcript))

        # Build metadata
        title = video_id  # Video ID as title placeholder (no API key available)
        metadata = DocumentMetadata(
            source=source_url,
            format=InputFormat.YOUTUBE,
            title=title,
        )

        return Document(
            content=full_text,
            metadata=metadata,
            sections=sections,
        )

    except ValueError:
        raise
    except Exception as e:
        # Handle all transcript-related errors gracefully
        error_msg = str(e)
        logger.warning(
            "Could not retrieve transcript for video %s: %s",
            video_id,
            error_msg,
        )
        return _create_empty_document(video_id, source_url, error_msg)


def _create_empty_document(
    video_id: str, source_url: str, warning: str
) -> Document:
    """Create a Document with empty/placeholder content for unavailable transcripts.

    Args:
        video_id: The YouTube video ID.
        source_url: The original source URL.
        warning: Warning message describing why the transcript is unavailable.

    Returns:
        Document with placeholder content and warning in metadata.
    """
    metadata = DocumentMetadata(
        source=source_url,
        format=InputFormat.YOUTUBE,
        title=video_id,
        author=f"WARNING: {warning}",
    )

    return Document(
        content=f"[Transcript unavailable] {warning}",
        metadata=metadata,
        sections=[],
    )


class YouTubeLoader:
    """YouTube transcript loader for NeuroForge.

    Extracts transcripts from YouTube videos using youtube-transcript-api.
    Supports auto-generated and manual captions, groups transcript segments
    into time-based sections, and handles unavailable transcripts gracefully.

    Usage:
        loader = YouTubeLoader()
        doc = loader.load("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        # Or use the functional API directly:
        from src.ingestion.youtube_loader import extract_youtube
        doc = extract_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    """

    def __init__(self) -> None:
        """Initialize YouTubeLoader."""
        pass

    def load(self, url: str) -> Document:
        """Load a YouTube video transcript and extract its content into a Document.

        Fetches the transcript using youtube-transcript-api. Prefers manually
        created captions over auto-generated ones. Falls back to auto-generated
        if manual is unavailable. English is preferred, but other languages are
        accepted as a final fallback.

        The transcript is grouped into time-based sections (every 5 minutes)
        with timestamp range headings for easy navigation.

        Args:
            url: YouTube video URL or bare video ID.
                 Supported URL formats:
                 - https://www.youtube.com/watch?v=VIDEO_ID
                 - https://youtu.be/VIDEO_ID
                 - https://www.youtube.com/embed/VIDEO_ID
                 - https://www.youtube.com/shorts/VIDEO_ID
                 - Bare 11-character video ID

        Returns:
            A Document instance with:
            - content: Full transcript text
            - metadata: Source URL, format (YOUTUBE), title (video ID)
            - sections: Time-based sections with timestamp headings

        Raises:
            ValueError: If the URL/video ID is invalid or unrecognized.
            ImportError: If youtube-transcript-api is not installed.
        """
        return extract_youtube(url)
