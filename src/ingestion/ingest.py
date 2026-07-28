"""Format Detection & Unified Ingestion Interface for NeuroForge.

Provides automatic format detection (file extension, URL pattern) and a
unified `ingest(source) -> Document` entry point that routes to the
appropriate loader.

Usage:
    from src.ingestion import ingest, detect_format

    doc = ingest("path/to/file.pdf")
    doc = ingest("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    fmt = detect_format("report.docx")  # InputFormat.DOCX
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

from models.document import Document, InputFormat

logger = logging.getLogger("neuroforge.ingest")

# Extension-to-format mapping
_EXTENSION_MAP: dict[str, InputFormat] = {
    ".pdf": InputFormat.PDF,
    ".pptx": InputFormat.PPTX,
    ".docx": InputFormat.DOCX,
    ".png": InputFormat.IMAGE,
    ".jpg": InputFormat.IMAGE,
    ".jpeg": InputFormat.IMAGE,
    ".bmp": InputFormat.IMAGE,
    ".tiff": InputFormat.IMAGE,
    ".tif": InputFormat.IMAGE,
    ".txt": InputFormat.TEXT,
    ".md": InputFormat.MARKDOWN,
}

# YouTube URL hostnames
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


class IngestionError(Exception):
    """Raised when an ingestion operation fails.

    Wraps underlying loader exceptions to provide a unified error interface.
    """

    pass


class UnsupportedFormatError(Exception):
    """Raised when the source format cannot be detected or is not supported."""

    pass


def _is_url(source: str) -> bool:
    """Check if source looks like a URL."""
    return source.startswith("http://") or source.startswith("https://")


def _is_youtube_url(source: str) -> bool:
    """Check if source is a YouTube URL.

    Matches youtube.com, www.youtube.com, m.youtube.com, and youtu.be hostnames.
    """
    try:
        parsed = urlparse(source)
        hostname = parsed.hostname
        if hostname is None:
            return False
        # Strip www. for consistent matching
        return hostname in _YOUTUBE_HOSTS
    except Exception:
        return False


def detect_format(source: str) -> InputFormat:
    """Detect the input format from a source path or URL.

    Detection rules (in order):
    1. URL pattern: youtube.com or youtu.be → YOUTUBE
    2. File extension: maps known extensions to their format
    3. Unknown → raises UnsupportedFormatError

    Args:
        source: File path or URL string.

    Returns:
        The detected InputFormat enum value.

    Raises:
        UnsupportedFormatError: If the format cannot be determined.
    """
    if not source or not source.strip():
        raise UnsupportedFormatError("Source cannot be empty.")

    source = source.strip()

    # Check for YouTube URL first
    if _is_url(source) and _is_youtube_url(source):
        return InputFormat.YOUTUBE

    # Check file extension
    # For URLs that aren't YouTube, try to get extension from path
    if _is_url(source):
        parsed = urlparse(source)
        path_str = parsed.path
    else:
        path_str = source

    ext = Path(path_str).suffix.lower()

    if ext in _EXTENSION_MAP:
        return _EXTENSION_MAP[ext]

    raise UnsupportedFormatError(
        f"Unsupported format for source: '{source}'. "
        f"Cannot determine format from extension '{ext}'. "
        f"Supported extensions: {sorted(_EXTENSION_MAP.keys())}"
    )


def ingest(source: str) -> Document:
    """Unified ingestion entry point.

    Detects the source format and routes to the appropriate loader.
    Returns a Document object with extracted content, metadata, and sections.

    Args:
        source: File path or URL to ingest.

    Returns:
        A Document instance from the appropriate loader.

    Raises:
        UnsupportedFormatError: If the format cannot be detected.
        IngestionError: If the loader fails (wraps the underlying exception).
    """
    fmt = detect_format(source)

    try:
        if fmt == InputFormat.PDF:
            from src.ingestion.pdf_loader import PDFLoader

            loader = PDFLoader()
            return loader.load(source)

        elif fmt == InputFormat.PPTX:
            from src.ingestion.pptx_loader import PPTXLoader

            loader = PPTXLoader()
            return loader.load(source)

        elif fmt == InputFormat.DOCX:
            from src.ingestion.docx_loader import DOCXLoader

            loader = DOCXLoader()
            return loader.load(source)

        elif fmt == InputFormat.IMAGE:
            from src.ingestion.image_loader import ImageLoader

            loader = ImageLoader()
            return loader.load(source)

        elif fmt == InputFormat.YOUTUBE:
            from src.ingestion.youtube_loader import YouTubeLoader

            loader = YouTubeLoader()
            return loader.load(source)

        elif fmt in (InputFormat.TEXT, InputFormat.MARKDOWN):
            from src.ingestion.text_loader import TextLoader

            loader = TextLoader()
            return loader.load(source)

        else:
            raise UnsupportedFormatError(f"No loader available for format: {fmt}")

    except (UnsupportedFormatError, IngestionError):
        # Re-raise our own errors without wrapping
        raise
    except Exception as e:
        raise IngestionError(
            f"Failed to ingest '{source}' (format: {fmt.value}): {e}"
        ) from e
