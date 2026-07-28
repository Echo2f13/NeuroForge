"""NeuroForge Workflows module.

Provides LangGraph-style workflow implementations for learning content generation:
- QuizWorkflow: Generates quiz questions (MCQ, short answer, true/false)
- FlashcardWorkflow: Generates concise Q/A flashcards from retrieved knowledge
- SolutionWorkflow: Generates structured solutions with marks-based depth
- RevisionNotesWorkflow: Generates hierarchical revision notes for a topic
- MindMapWorkflow: Generates mind maps from knowledge graph structure
- AdditionalInfoWorkflow: Generates real-world applications, industry uses,
  common mistakes, and interview questions for a topic
- ChatTutor: RAG-powered conversational tutor with memory
"""

from .additional_info import AdditionalInfoWorkflow
from .chat_tutor import ChatTutor
from .flashcards import FlashcardWorkflow
from .mind_map import MindMapWorkflow
from .quiz import QuizWorkflow
from .revision_notes import RevisionNotesWorkflow
from .solutions import SolutionWorkflow

__all__ = [
    "AdditionalInfoWorkflow",
    "ChatTutor",
    "FlashcardWorkflow",
    "MindMapWorkflow",
    "QuizWorkflow",
    "RevisionNotesWorkflow",
    "SolutionWorkflow",
]
