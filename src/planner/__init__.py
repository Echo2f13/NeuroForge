"""NeuroForge Planner module.

Provides intent classification and routing for natural language user inputs.
Detects user intent (quiz, flashcard, notes, explain, solution, mind_map,
additional_info, chat) and extracts parameters (topic, difficulty, count, marks).
"""

from .router import IntentRouter

__all__ = ["IntentRouter"]
