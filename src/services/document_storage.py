"""Document Storage Service for NeuroForge.

Manages the storage and retrieval of original document files for source
attribution and inline document viewing. Documents are stored in a
subject-scoped directory structure.

Storage Structure:
    subjects/
    ├── {subject_id}/
    │   ├── documents/
    │   │   ├── {doc_id}/
    │   │   │   ├── metadata.json
    │   │   │   └── original.{ext}
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator, Optional

from models import InputFormat, StoredDocument

logger = logging.getLogger(__name__)

# Maximum file size: 100MB
MAX_FILE_SIZE = 100 * 1024 * 1024

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".pdf": InputFormat.PDF,
    ".docx": InputFormat.DOCX,
    ".pptx": InputFormat.PPTX,
    ".txt": InputFormat.TEXT,
    ".md": InputFormat.MARKDOWN,
    ".png": InputFormat.IMAGE,
    ".jpg": InputFormat.IMAGE,
    ".jpeg": InputFormat.IMAGE,
}


class DocumentStorageError(Exception):
    """Base exception for document storage errors."""
    pass


class DocumentNotFoundError(DocumentStorageError):
    """Raised when a document is not found."""
    pass


class InvalidDocumentError(DocumentStorageError):
    """Raised when a document is invalid (wrong type, too large, etc.)."""
    pass


class DocumentStorageService:
    """Manages document file storage for source attribution.
    
    Provides methods to store, retrieve, and delete original document files
    enabling the inline document viewer and source citation features.
    
    Attributes:
        base_dir: Base directory for all document storage.
    """
    
    def __init__(self, base_dir: Path | str) -> None:
        """Initialize the DocumentStorageService.
        
        Args:
            base_dir: Base directory for document storage (usually project data dir).
        """
        self.base_dir = Path(base_dir)
        self._ensure_base_dir()
    
    def _ensure_base_dir(self) -> None:
        """Ensure the base directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_subject_docs_dir(self, subject_id: str) -> Path:
        """Get the documents directory for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Path to subjects/{subject_id}/documents/
        """
        self._validate_id(subject_id, "subject_id")
        return self.base_dir / "subjects" / subject_id / "documents"
    
    def _get_document_dir(self, subject_id: str, doc_id: str) -> Path:
        """Get the directory for a specific document.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            
        Returns:
            Path to subjects/{subject_id}/documents/{doc_id}/
        """
        self._validate_id(doc_id, "doc_id")
        return self._get_subject_docs_dir(subject_id) / doc_id
    
    def _validate_id(self, id_value: str, id_name: str) -> None:
        """Validate an ID to prevent path traversal attacks.
        
        Args:
            id_value: The ID value to validate.
            id_name: Name of the ID for error messages.
            
        Raises:
            InvalidDocumentError: If the ID contains invalid characters.
        """
        if not id_value:
            raise InvalidDocumentError(f"{id_name} cannot be empty")
        
        # Only allow alphanumeric, dash, underscore
        if not re.match(r'^[\w\-]+$', id_value):
            raise InvalidDocumentError(
                f"{id_name} contains invalid characters. "
                "Only alphanumeric, dash, and underscore allowed."
            )
        
        # Prevent path traversal
        if ".." in id_value or id_value.startswith("/") or id_value.startswith("\\"):
            raise InvalidDocumentError(f"{id_name} contains path traversal characters")
    
    def _validate_filename(self, filename: str) -> tuple[str, InputFormat]:
        """Validate and sanitize a filename.
        
        Args:
            filename: Original filename to validate.
            
        Returns:
            Tuple of (sanitized filename, detected format).
            
        Raises:
            InvalidDocumentError: If filename is invalid or unsupported.
        """
        if not filename:
            raise InvalidDocumentError("Filename cannot be empty")
        
        # Get extension and validate
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise InvalidDocumentError(
                f"Unsupported file type: {ext}. "
                f"Supported: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
            )
        
        # Sanitize filename (remove path components, dangerous chars)
        safe_name = Path(filename).name
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)
        
        return safe_name, SUPPORTED_EXTENSIONS[ext]
    
    def _calculate_checksum(self, file_content: bytes) -> str:
        """Calculate SHA-256 checksum of file content.
        
        Args:
            file_content: File content as bytes.
            
        Returns:
            Hex-encoded SHA-256 hash.
        """
        return hashlib.sha256(file_content).hexdigest()
    
    def _read_file_in_chunks(
        self, 
        file: BinaryIO, 
        chunk_size: int = 8192
    ) -> Iterator[bytes]:
        """Read a file in chunks for efficient processing.
        
        Args:
            file: File object to read.
            chunk_size: Size of chunks to read.
            
        Yields:
            Chunks of file content.
        """
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            yield chunk
    
    def store_document(
        self,
        subject_id: str,
        doc_id: str,
        filename: str,
        file_content: bytes,
        title: Optional[str] = None,
        author: Optional[str] = None,
        total_pages: Optional[int] = None,
    ) -> StoredDocument:
        """Store an uploaded document file.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            filename: Original filename.
            file_content: Document content as bytes.
            title: Optional document title.
            author: Optional document author.
            total_pages: Optional total page count.
            
        Returns:
            StoredDocument with metadata.
            
        Raises:
            InvalidDocumentError: If document is invalid.
        """
        # Validate inputs
        self._validate_id(subject_id, "subject_id")
        self._validate_id(doc_id, "doc_id")
        safe_filename, doc_format = self._validate_filename(filename)
        
        # Check file size
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE:
            raise InvalidDocumentError(
                f"File too large: {file_size / (1024*1024):.1f}MB. "
                f"Maximum: {MAX_FILE_SIZE / (1024*1024):.0f}MB"
            )
        
        if file_size == 0:
            raise InvalidDocumentError("File is empty")
        
        # Create directory structure
        doc_dir = self._get_document_dir(subject_id, doc_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine storage filename
        ext = Path(safe_filename).suffix.lower()
        storage_filename = f"original{ext}"
        file_path = doc_dir / storage_filename
        
        # Calculate checksum
        checksum = self._calculate_checksum(file_content)
        
        # Write file
        file_path.write_bytes(file_content)
        logger.info(f"Stored document: {file_path}")
        
        # Create metadata
        now = datetime.now(timezone.utc).isoformat()
        storage_path = f"subjects/{subject_id}/documents/{doc_id}/{storage_filename}"
        
        stored_doc = StoredDocument(
            id=doc_id,
            subject_id=subject_id,
            filename=safe_filename,
            format=doc_format,
            storage_path=storage_path,
            file_size=file_size,
            total_pages=total_pages,
            uploaded_at=now,
            checksum=checksum,
            title=title,
            author=author,
        )
        
        # Save metadata
        metadata_path = doc_dir / "metadata.json"
        metadata_path.write_text(stored_doc.to_json())
        
        return stored_doc
    
    def get_document(self, subject_id: str, doc_id: str) -> StoredDocument:
        """Get document metadata.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            
        Returns:
            StoredDocument with metadata.
            
        Raises:
            DocumentNotFoundError: If document doesn't exist.
        """
        doc_dir = self._get_document_dir(subject_id, doc_id)
        metadata_path = doc_dir / "metadata.json"
        
        if not metadata_path.exists():
            raise DocumentNotFoundError(
                f"Document not found: subject={subject_id}, doc={doc_id}"
            )
        
        return StoredDocument.from_json(metadata_path.read_text())
    
    def get_document_path(self, subject_id: str, doc_id: str) -> Path:
        """Get the file path for a stored document.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            
        Returns:
            Path to the document file.
            
        Raises:
            DocumentNotFoundError: If document doesn't exist.
        """
        doc = self.get_document(subject_id, doc_id)
        file_path = self.base_dir / doc.storage_path
        
        if not file_path.exists():
            raise DocumentNotFoundError(
                f"Document file missing: {file_path}"
            )
        
        return file_path
    
    def get_document_content(self, subject_id: str, doc_id: str) -> bytes:
        """Get document file content.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            
        Returns:
            Document content as bytes.
            
        Raises:
            DocumentNotFoundError: If document doesn't exist.
        """
        file_path = self.get_document_path(subject_id, doc_id)
        return file_path.read_bytes()
    
    def stream_document(
        self,
        subject_id: str,
        doc_id: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> Iterator[bytes]:
        """Stream document content with optional range support.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            start: Starting byte position (optional).
            end: Ending byte position (optional).
            
        Yields:
            Chunks of document content.
            
        Raises:
            DocumentNotFoundError: If document doesn't exist.
        """
        file_path = self.get_document_path(subject_id, doc_id)
        file_size = file_path.stat().st_size
        
        # Handle range
        start = start or 0
        end = end or file_size
        
        # Clamp values
        start = max(0, min(start, file_size))
        end = max(start, min(end, file_size))
        
        chunk_size = 8192
        
        with open(file_path, 'rb') as f:
            f.seek(start)
            remaining = end - start
            
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                chunk = f.read(read_size)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
    
    def list_documents(self, subject_id: str) -> list[StoredDocument]:
        """List all documents for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            List of StoredDocument objects.
        """
        docs_dir = self._get_subject_docs_dir(subject_id)
        
        if not docs_dir.exists():
            return []
        
        documents = []
        for doc_dir in docs_dir.iterdir():
            if doc_dir.is_dir():
                metadata_path = doc_dir / "metadata.json"
                if metadata_path.exists():
                    try:
                        doc = StoredDocument.from_json(metadata_path.read_text())
                        documents.append(doc)
                    except Exception as e:
                        logger.warning(f"Failed to load document metadata: {e}")
        
        # Sort by upload date (newest first)
        documents.sort(key=lambda d: d.uploaded_at, reverse=True)
        return documents
    
    def delete_document(self, subject_id: str, doc_id: str) -> bool:
        """Delete a stored document.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        doc_dir = self._get_document_dir(subject_id, doc_id)
        
        if not doc_dir.exists():
            return False
        
        try:
            shutil.rmtree(doc_dir)
            logger.info(f"Deleted document: subject={subject_id}, doc={doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            raise DocumentStorageError(f"Failed to delete document: {e}")
    
    def document_exists(self, subject_id: str, doc_id: str) -> bool:
        """Check if a document exists.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            
        Returns:
            True if document exists.
        """
        try:
            self._validate_id(subject_id, "subject_id")
            self._validate_id(doc_id, "doc_id")
        except InvalidDocumentError:
            return False
            
        doc_dir = self._get_document_dir(subject_id, doc_id)
        metadata_path = doc_dir / "metadata.json"
        return metadata_path.exists()
    
    def verify_checksum(self, subject_id: str, doc_id: str) -> bool:
        """Verify document integrity using stored checksum.
        
        Args:
            subject_id: Subject identifier.
            doc_id: Document identifier.
            
        Returns:
            True if checksum matches, False otherwise.
            
        Raises:
            DocumentNotFoundError: If document doesn't exist.
        """
        doc = self.get_document(subject_id, doc_id)
        content = self.get_document_content(subject_id, doc_id)
        current_checksum = self._calculate_checksum(content)
        return current_checksum == doc.checksum
    
    def get_storage_stats(self, subject_id: Optional[str] = None) -> dict:
        """Get storage statistics.
        
        Args:
            subject_id: Optional subject to get stats for.
                       If None, returns global stats.
            
        Returns:
            Dict with storage statistics.
        """
        if subject_id:
            docs = self.list_documents(subject_id)
            total_size = sum(d.file_size for d in docs)
            return {
                "subject_id": subject_id,
                "document_count": len(docs),
                "total_size_bytes": total_size,
                "total_size_display": self._format_size(total_size),
            }
        
        # Global stats
        subjects_dir = self.base_dir / "subjects"
        if not subjects_dir.exists():
            return {
                "subject_count": 0,
                "document_count": 0,
                "total_size_bytes": 0,
                "total_size_display": "0 B",
            }
        
        total_docs = 0
        total_size = 0
        subject_count = 0
        
        for subject_dir in subjects_dir.iterdir():
            if subject_dir.is_dir():
                subject_count += 1
                docs = self.list_documents(subject_dir.name)
                total_docs += len(docs)
                total_size += sum(d.file_size for d in docs)
        
        return {
            "subject_count": subject_count,
            "document_count": total_docs,
            "total_size_bytes": total_size,
            "total_size_display": self._format_size(total_size),
        }
    
    def _format_size(self, size_bytes: int) -> str:
        """Format byte size as human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
