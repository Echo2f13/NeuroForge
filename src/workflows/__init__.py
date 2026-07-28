"""NeuroForge Workflows module.

Provides LangGraph-style workflow implementations for learning content generation:
- MindMapWorkflow: Generates mind maps from knowledge graph structure
- RevisionNotesWorkflow: Generates hierarchical revision notes for a topic
- QuizWorkflow: Generates quiz questions (MCQ, short answer, true/false)
- AdditionalInfoWorkflow: Generates real-world applications, industry uses,
  common mistakes, and interview questions for a topic
- ChatTutor: RAG-powered conversational tutor with memory
"""

from .additional_info import AdditionalInfoWorkflow
from .chat_tutor import ChatTutor
from .mind_map import MindMapWorkflow
from .quiz import QuizWorkflow
from .revision_notes import RevisionNotesWorkflow

__all__ = [
    "AdditionalInfoWorkflow",
    "ChatTutor",
    "MindMapWorkflow",
    "QuizWorkflow",
    "RevisionNotesWorkflow",
]
