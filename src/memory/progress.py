"""Progress Tracker for NeuroForge.

Wraps the LearningState Pydantic model with JSON file persistence and
convenience methods for recording scores, querying mastery, and identifying
weak/strong topics. Enhanced with dashboard data methods for streaks and heatmaps.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
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

    def record_card_review(self, card_id: str) -> None:
        """Record a flashcard review for streak tracking.
        
        Args:
            card_id: The flashcard ID that was reviewed.
        """
        self._state.record_card_review(card_id)
        self.save()

    def get_dashboard_data(self) -> dict:
        """Get comprehensive dashboard data for the frontend.
        
        Returns:
            Dictionary with all dashboard metrics including:
            - streak info (current, longest)
            - cards due counts
            - topic mastery breakdown
            - heatmap data
            - weekly/monthly stats
            - exam readiness score
        """
        # Get basic stats
        overall = self.get_overall_stats()
        
        # Get streak info
        streak_info = {
            "current_streak": self._state.current_streak,
            "longest_streak": self._state.longest_streak,
            "total_cards_reviewed": self._state.total_cards_reviewed,
        }
        
        # Get weekly stats
        weekly = self._state.get_weekly_stats()
        
        # Calculate monthly stats
        monthly = self._get_monthly_stats()
        
        # Get topic mastery breakdown
        topic_mastery = self._get_topic_mastery()
        
        # Get heatmap data (last 365 days)
        heatmap = self._state.get_heatmap_data(365)
        
        # Calculate exam readiness score
        readiness = self._calculate_exam_readiness()
        
        # Get learning velocity (score trend over time)
        velocity = self._get_learning_velocity()
        
        return {
            "streak": streak_info,
            "overall": overall,
            "weekly": weekly,
            "monthly": monthly,
            "topic_mastery": topic_mastery,
            "heatmap": heatmap,
            "exam_readiness": readiness,
            "learning_velocity": velocity,
        }

    def _get_monthly_stats(self) -> dict:
        """Get statistics for the current month."""
        today = date.today()
        month_start = today.replace(day=1)
        
        reviews = 0
        quizzes = 0
        
        current = month_start
        while current <= today:
            date_str = current.isoformat()
            if date_str in self._state.daily_activity:
                activity = self._state.daily_activity[date_str]
                reviews += activity.reviews_completed
                quizzes += activity.quizzes_completed
            current += timedelta(days=1)
        
        return {
            "reviews_this_month": reviews,
            "quizzes_this_month": quizzes,
            "total_this_month": reviews + quizzes,
        }

    def _get_topic_mastery(self) -> list[dict]:
        """Get mastery breakdown for all topics."""
        topics = []
        for name, progress in self._state.topic_progress.items():
            topics.append({
                "topic": name,
                "mastery_percent": round(progress.average_score, 1),
                "mastery_level": progress.mastery_level,
                "attempts": progress.attempts,
                "last_attempted": progress.last_attempted,
            })
        
        # Sort by mastery percent descending
        topics.sort(key=lambda x: x["mastery_percent"], reverse=True)
        return topics

    def _calculate_exam_readiness(self) -> dict:
        """Calculate predicted exam readiness score.
        
        Formula:
        - 40% average mastery across topics
        - 30% consistency (streak factor)
        - 20% coverage (topics attempted / topics with material)
        - 10% recency (activity in last 7 days)
        """
        # Average mastery (0-100)
        if self._state.topic_progress:
            avg_mastery = sum(
                p.average_score for p in self._state.topic_progress.values()
            ) / len(self._state.topic_progress)
        else:
            avg_mastery = 0
        
        # Consistency factor based on streak (max at 30 days)
        streak_factor = min(self._state.current_streak / 30, 1.0) * 100
        
        # Coverage (assume we have some topics)
        total_topics = max(len(self._state.topic_progress), 1)
        mastered_topics = len(self._state.strong_topics)
        coverage = (mastered_topics / total_topics) * 100 if total_topics else 0
        
        # Recency (activity in last 7 days)
        today = date.today()
        recent_activity = 0
        for i in range(7):
            date_str = (today - timedelta(days=i)).isoformat()
            if date_str in self._state.daily_activity:
                activity = self._state.daily_activity[date_str]
                if activity.reviews_completed > 0 or activity.quizzes_completed > 0:
                    recent_activity += 1
        recency_score = (recent_activity / 7) * 100
        
        # Weighted score
        readiness_score = (
            avg_mastery * 0.4 +
            streak_factor * 0.3 +
            coverage * 0.2 +
            recency_score * 0.1
        )
        
        # Determine readiness level
        if readiness_score >= 80:
            level = "excellent"
            message = "You're well prepared! Keep reviewing to maintain momentum."
        elif readiness_score >= 60:
            level = "good"
            message = "Good progress! Focus on weak topics to improve further."
        elif readiness_score >= 40:
            level = "moderate"
            message = "Making progress. Increase daily reviews for better retention."
        else:
            level = "needs_work"
            message = "Keep studying! Regular practice will boost your readiness."
        
        return {
            "score": round(readiness_score, 1),
            "level": level,
            "message": message,
            "breakdown": {
                "mastery": round(avg_mastery, 1),
                "consistency": round(streak_factor, 1),
                "coverage": round(coverage, 1),
                "recency": round(recency_score, 1),
            }
        }

    def _get_learning_velocity(self) -> list[dict]:
        """Get learning velocity data (score trends over time).
        
        Returns weekly averages for the last 8 weeks.
        """
        today = date.today()
        velocity = []
        
        for week in range(8):
            week_end = today - timedelta(days=week * 7)
            week_start = week_end - timedelta(days=6)
            
            scores = []
            current = week_start
            while current <= week_end:
                date_str = current.isoformat()
                if date_str in self._state.daily_activity:
                    activity = self._state.daily_activity[date_str]
                    if activity.quizzes_completed > 0:
                        avg = activity.score_sum / activity.quizzes_completed
                        scores.append(avg)
                current += timedelta(days=1)
            
            avg_score = sum(scores) / len(scores) if scores else None
            
            velocity.append({
                "week": f"Week {8 - week}",
                "week_start": week_start.isoformat(),
                "average_score": round(avg_score, 1) if avg_score else None,
                "quizzes": len(scores),
            })
        
        # Reverse to show oldest first
        velocity.reverse()
        return velocity

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
