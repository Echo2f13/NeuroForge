"""Progress Tracker for NeuroForge.

Wraps the LearningState Pydantic model with JSON file persistence and
convenience methods for recording scores, querying mastery, and identifying
weak/strong topics.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from models.learning import LearningState, TopicProgress


class ProgressTracker:
    """Persistent learning progress tracker.

    Wraps a LearningState model and provides:
    - JSON file persistence (save/load)
    - Score recording with automatic timestamp
    - Running averages and mastery level queries
    - Weak/strong topic identification
    - Overall stats aggregation

    Args:
        state_file: Path to the JSON state file. Defaults to "./learning_state.json".
    """

    def __init__(self, state_file: str = "./learning_state.json") -> None:
        self.state_file = state_file
        self._state: LearningState = LearningState()
        self.load()

    @property
    def state(self) -> LearningState:
        """Access the underlying LearningState model."""
        return self._state

    def record_score(self, topic: str, score: float) -> None:
        """Record a quiz score for a topic.

        Updates the topic progress, refreshes weak/strong classifications,
        and persists state to disk.

        Args:
            topic: Topic name.
            score: Quiz score between 0 and 100.

        Raises:
            ValueError: If score is not between 0 and 100.
        """
        if score < 0 or score > 100:
            raise ValueError(f"Score must be between 0 and 100, got {score}")

        # Ensure topic exists in progress
        if topic not in self._state.topic_progress:
            self._state.topic_progress[topic] = TopicProgress(topic=topic)

        # Record the score and update timestamp
        self._state.topic_progress[topic].add_score(score)
        self._state.topic_progress[topic].last_attempted = (
            datetime.now(timezone.utc).isoformat()
        )

        # Update global counters
        self._state.total_quizzes_taken += 1

        # Refresh weak/strong classifications
        self._state._refresh_topic_classifications()

        # Auto-save
        self.save()

    def get_topic_progress(self, topic: str) -> TopicProgress:
        """Get progress for a specific topic.

        Args:
            topic: Topic name.

        Returns:
            TopicProgress for the topic. Returns a new (empty) TopicProgress
            if the topic hasn't been attempted yet.
        """
        if topic in self._state.topic_progress:
            return self._state.topic_progress[topic]
        return TopicProgress(topic=topic)

    def get_weak_topics(self) -> list[str]:
        """Get topics with average score < 60%.

        Returns:
            List of topic names classified as weak.
        """
        return list(self._state.weak_topics)

    def get_strong_topics(self) -> list[str]:
        """Get topics with average score > 85%.

        Returns:
            List of topic names classified as strong.
        """
        return list(self._state.strong_topics)

    def get_mastery_level(self, topic: str) -> str:
        """Get the mastery level for a topic.

        Returns one of: not_started, learning, familiar, mastered.

        Args:
            topic: Topic name.

        Returns:
            Mastery level string.
        """
        if topic in self._state.topic_progress:
            return self._state.topic_progress[topic].mastery_level
        return "not_started"

    def get_overall_stats(self) -> dict:
        """Get aggregated statistics across all topics.

        Returns:
            Dictionary with:
            - total_quizzes: Total quiz attempts across all topics
            - total_topics: Number of topics attempted
            - average_score: Weighted average score across all topics
            - study_time_minutes: Total tracked study time
            - weak_count: Number of weak topics
            - strong_count: Number of strong topics
        """
        total_topics = len(self._state.topic_progress)
        total_quizzes = self._state.total_quizzes_taken

        # Compute overall average from all individual scores
        all_scores: list[float] = []
        for progress in self._state.topic_progress.values():
            all_scores.extend(progress.quiz_scores)

        average_score = (
            sum(all_scores) / len(all_scores) if all_scores else 0.0
        )

        return {
            "total_quizzes": total_quizzes,
            "total_topics": total_topics,
            "average_score": round(average_score, 2),
            "study_time_minutes": self._state.total_study_time_minutes,
            "weak_count": len(self._state.weak_topics),
            "strong_count": len(self._state.strong_topics),
        }

    def save(self) -> None:
        """Persist the current state to the JSON file.

        Creates parent directories if they don't exist.
        """
        path = Path(self.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._state.model_dump_json(indent=2), encoding="utf-8")

    def load(self) -> None:
        """Load state from the JSON file.

        If the file doesn't exist, initializes with a fresh LearningState.
        """
        path = Path(self.state_file)
        if path.exists():
            try:
                data = path.read_text(encoding="utf-8")
                self._state = LearningState.model_validate_json(data)
            except (json.JSONDecodeError, ValueError):
                # Corrupted file — start fresh
                self._state = LearningState()
        else:
            self._state = LearningState()

    def reset(self) -> None:
        """Clear all progress and remove the state file."""
        self._state = LearningState()
        path = Path(self.state_file)
        if path.exists():
            path.unlink()
