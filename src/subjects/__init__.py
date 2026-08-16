"""Subject Management Module for NeuroForge.

Provides the SubjectManager for managing study subjects/sessions,
enabling isolated learning environments per subject.
"""

from .manager import SubjectManager
from .migration import (
    cleanup_old_files,
    get_migration_info,
    migrate_to_subjects,
    needs_migration,
)
from .storage import SubjectStorage

__all__ = [
    "SubjectManager",
    "SubjectStorage",
    "needs_migration",
    "get_migration_info",
    "migrate_to_subjects",
    "cleanup_old_files",
]
