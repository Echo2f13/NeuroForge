"""NeuroForge Retrieval module.

Provides hybrid retrieval combining semantic search, metadata-filtered search,
graph-based retrieval, and hybrid approaches for knowledge-augmented responses.

Includes subject-scoped retrieval for multi-subject learning isolation.
"""

from .retriever import Retriever
from .subject_retriever import SubjectRetriever

__all__ = ["Retriever", "SubjectRetriever"]
