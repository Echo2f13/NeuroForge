"""NeuroForge Memory module.

Provides persistent learning progress tracking and adaptive difficulty:
- ProgressTracker: Wraps LearningState with JSON file persistence and
  convenience methods for tracking quiz scores, mastery levels, and
  identifying weak/strong topics.
- AdaptiveDifficulty: Recommends quiz/flashcard difficulty based on
  learner mastery levels from ProgressTracker.
- SpacedRepetitionScheduler: SM-2 algorithm for flashcard scheduling with
  ease factor, interval, and review date tracking.
- RecommendationEngine: Personalized study recommendations combining
  progress, knowledge graph, and spaced repetition signals.
"""

from .adaptive import AdaptiveDifficulty
from .progress import ProgressTracker
from .recommendations import RecommendationEngine
from .spaced_repetition import SpacedRepetitionScheduler

__all__ = [
    "AdaptiveDifficulty",
    "ProgressTracker",
    "RecommendationEngine",
    "SpacedRepetitionScheduler",
]
