"""Adaptive Difficulty for NeuroForge.

Adjusts quiz and flashcard difficulty based on learner mastery levels.
Reads from ProgressTracker to recommend difficulty without storing its own state.

Rules:
- mastery < 40%  → "easy"
- 40% <= mastery < 70% → "medium"
- mastery >= 70% → "hard"
"""

from __future__ import annotations

from src.memory.progress import ProgressTracker


class AdaptiveDifficulty:
    """Recommends difficulty settings based on learner progress.

    Reads mastery data from a ProgressTracker instance to determine
    appropriate difficulty for quizzes and flashcards. Does not store
    its own state — all decisions are derived from the tracker.

    Args:
        progress_tracker: An initialized ProgressTracker instance.
    """

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        self.progress_tracker = progress_tracker

    def get_recommended_difficulty(self, topic: str) -> str:
        """Return recommended difficulty for a topic based on mastery.

        Mastery thresholds:
        - < 40%  → "easy"
        - 40% to < 70% → "medium"
        - >= 70% → "hard"

        Args:
            topic: The topic to get difficulty for.

        Returns:
            One of "easy", "medium", or "hard".
        """
        mastery = self._get_mastery_percentage(topic)

        if mastery < 40:
            return "easy"
        elif mastery < 70:
            return "medium"
        else:
            return "hard"

    def get_difficulty_for_topics(self, topics: list[str]) -> dict[str, str]:
        """Batch version: get recommended difficulty for multiple topics.

        Args:
            topics: List of topic names.

        Returns:
            Dict mapping topic name to difficulty string.
        """
        return {topic: self.get_recommended_difficulty(topic) for topic in topics}

    def adjust_quiz_params(self, topic: str, base_num_questions: int = 10) -> dict:
        """Return adjusted quiz parameters based on topic mastery.

        Weak topics (easy): fewer questions, mostly easy types to build confidence.
        Medium topics: standard parameters.
        Strong topics (hard): more questions, advanced question types.

        Args:
            topic: The topic to adjust parameters for.
            base_num_questions: Base number of questions (default 10).

        Returns:
            Dict with keys: difficulty, num_questions, question_types.
        """
        difficulty = self.get_recommended_difficulty(topic)

        if difficulty == "easy":
            return {
                "difficulty": "easy",
                "num_questions": max(5, base_num_questions - 3),
                "question_types": ["mcq", "true_false"],
            }
        elif difficulty == "medium":
            return {
                "difficulty": "medium",
                "num_questions": base_num_questions,
                "question_types": ["mcq", "short_answer", "true_false"],
            }
        else:  # hard
            return {
                "difficulty": "hard",
                "num_questions": base_num_questions + 2,
                "question_types": ["mcq", "short_answer"],
            }

    def adjust_flashcard_params(self, topic: str, base_num_cards: int = 10) -> dict:
        """Return adjusted flashcard parameters based on topic mastery.

        Weak topics (easy): fewer cards, focused on definitions/basics.
        Medium topics: standard set with mixed complexity.
        Strong topics (hard): more cards, advanced concepts.

        Args:
            topic: The topic to adjust parameters for.
            base_num_cards: Base number of flashcards (default 10).

        Returns:
            Dict with keys: difficulty, num_cards, card_types.
        """
        difficulty = self.get_recommended_difficulty(topic)

        if difficulty == "easy":
            return {
                "difficulty": "easy",
                "num_cards": max(5, base_num_cards - 3),
                "card_types": ["definition", "basic_concept"],
            }
        elif difficulty == "medium":
            return {
                "difficulty": "medium",
                "num_cards": base_num_cards,
                "card_types": ["definition", "concept", "application"],
            }
        else:  # hard
            return {
                "difficulty": "hard",
                "num_cards": base_num_cards + 3,
                "card_types": ["concept", "application", "analysis"],
            }

    def _get_mastery_percentage(self, topic: str) -> float:
        """Get mastery percentage (average score) for a topic.

        Returns 0.0 for topics with no attempts (treated as unknown → easy).

        Args:
            topic: Topic name.

        Returns:
            Mastery percentage (0-100).
        """
        progress = self.progress_tracker.get_topic_progress(topic)
        if progress.attempts == 0:
            return 0.0
        return progress.average_score
