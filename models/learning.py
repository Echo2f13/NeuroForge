"""Learning State Models for NeuroForge.

Defines models for tracking user learning progress:
- TopicProgress: Progress tracking for a single topic
- LearningState: Complete learning state for a user
- ReviewHistory: Daily review activity tracking for streaks and heatmaps
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TopicProgress(BaseModel):
    """Progress tracking for a single topic.

    Tracks quiz scores, mastery level, and learning history.

    Attributes:
        topic: Name of the topic.
        quiz_scores: List of quiz scores (0-100) for this topic.
        average_score: Computed average of all quiz scores.
        attempts: Number of quiz attempts.
        mastery_level: Current mastery level.
        last_attempted: ISO timestamp of last attempt.
    """

    topic: str = Field(..., min_length=1, description="Topic name")
    quiz_scores: list[float] = Field(
        default_factory=list, description="Quiz scores (0-100)"
    )
    average_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Average score (0-100)"
    )
    attempts: int = Field(default=0, ge=0, description="Number of attempts")
    mastery_level: str = Field(
        default="not_started",
        description="Mastery level: not_started, learning, familiar, mastered",
    )
    last_attempted: Optional[str] = Field(
        default=None, description="ISO timestamp of last attempt"
    )

    @field_validator("quiz_scores")
    @classmethod
    def validate_quiz_scores(cls, v: list[float]) -> list[float]:
        """Validate that all quiz scores are between 0 and 100."""
        for score in v:
            if score < 0 or score > 100:
                raise ValueError(
                    f"Quiz scores must be between 0 and 100, got {score}"
                )
        return v

    @field_validator("mastery_level")
    @classmethod
    def validate_mastery_level(cls, v: str) -> str:
        """Validate that mastery_level is one of the allowed values."""
        allowed = {"not_started", "learning", "familiar", "mastered"}
        if v not in allowed:
            raise ValueError(
                f"mastery_level must be one of {allowed}, got '{v}'"
            )
        return v

    def add_score(self, score: float) -> None:
        """Add a quiz score and update computed fields.

        Args:
            score: Quiz score between 0 and 100.
        """
        if score < 0 or score > 100:
            raise ValueError(f"Score must be between 0 and 100, got {score}")
        self.quiz_scores.append(score)
        self.attempts = len(self.quiz_scores)
        self.average_score = sum(self.quiz_scores) / len(self.quiz_scores)
        self._update_mastery_level()

    def _update_mastery_level(self) -> None:
        """Update mastery level based on average score."""
        if self.attempts == 0:
            self.mastery_level = "not_started"
        elif self.average_score >= 85:
            self.mastery_level = "mastered"
        elif self.average_score >= 60:
            self.mastery_level = "familiar"
        else:
            self.mastery_level = "learning"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "TopicProgress":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TopicProgress":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class DailyActivity(BaseModel):
    """Activity record for a single day.
    
    Tracks reviews, quizzes, and cards reviewed on a specific day.
    """
    date: str = Field(..., description="ISO date string (YYYY-MM-DD)")
    reviews_completed: int = Field(default=0, ge=0, description="Number of card reviews")
    quizzes_completed: int = Field(default=0, ge=0, description="Number of quizzes taken")
    cards_reviewed: list[str] = Field(default_factory=list, description="Card IDs reviewed")
    score_sum: float = Field(default=0.0, description="Sum of scores for averaging")
    

class LearningState(BaseModel):
    """Complete learning state for a user.

    Tracks all progress, uploaded materials, and adaptive learning data.

    Attributes:
        user_id: Unique user identifier.
        uploaded_materials: List of uploaded material paths/names.
        topic_progress: Progress per topic (keyed by topic name).
        weak_topics: Topics with score < 60%.
        strong_topics: Topics with score > 85%.
        flashcard_review_queue: Flashcard IDs pending review.
        total_quizzes_taken: Total number of quizzes completed.
        total_study_time_minutes: Total study time in minutes.
        daily_activity: Daily activity records for streaks/heatmap (keyed by date).
        current_streak: Current consecutive days of activity.
        longest_streak: Longest streak ever achieved.
        total_cards_reviewed: Total flashcard reviews completed.
    """

    user_id: str = Field(
        default="default", min_length=1, description="User identifier"
    )
    uploaded_materials: list[str] = Field(
        default_factory=list, description="Uploaded material paths"
    )
    topic_progress: dict[str, TopicProgress] = Field(
        default_factory=dict, description="Progress per topic"
    )
    weak_topics: list[str] = Field(
        default_factory=list, description="Topics with score < 60%"
    )
    strong_topics: list[str] = Field(
        default_factory=list, description="Topics with score > 85%"
    )
    flashcard_review_queue: list[str] = Field(
        default_factory=list, description="Flashcard IDs pending review"
    )
    total_quizzes_taken: int = Field(
        default=0, ge=0, description="Total quizzes completed"
    )
    total_study_time_minutes: float = Field(
        default=0.0, ge=0.0, description="Total study time in minutes"
    )
    # New fields for dashboard
    daily_activity: dict[str, DailyActivity] = Field(
        default_factory=dict, description="Daily activity records (keyed by date)"
    )
    current_streak: int = Field(
        default=0, ge=0, description="Current consecutive days streak"
    )
    longest_streak: int = Field(
        default=0, ge=0, description="Longest streak ever achieved"
    )
    total_cards_reviewed: int = Field(
        default=0, ge=0, description="Total flashcard reviews"
    )

    def update_topic_score(self, topic: str, score: float) -> None:
        """Record a quiz score for a topic and update weak/strong lists.

        Args:
            topic: Topic name.
            score: Quiz score between 0 and 100.
        """
        if topic not in self.topic_progress:
            self.topic_progress[topic] = TopicProgress(topic=topic)
        self.topic_progress[topic].add_score(score)
        self.total_quizzes_taken += 1
        self._refresh_topic_classifications()
        
        # Record daily activity
        self._record_daily_quiz(score)

    def record_card_review(self, card_id: str) -> None:
        """Record a flashcard review for streak tracking.
        
        Args:
            card_id: The flashcard ID that was reviewed.
        """
        today = date.today().isoformat()
        
        if today not in self.daily_activity:
            self.daily_activity[today] = DailyActivity(date=today)
        
        self.daily_activity[today].reviews_completed += 1
        if card_id not in self.daily_activity[today].cards_reviewed:
            self.daily_activity[today].cards_reviewed.append(card_id)
        
        self.total_cards_reviewed += 1
        self._update_streak()

    def _record_daily_quiz(self, score: float) -> None:
        """Record quiz activity for the day."""
        today = date.today().isoformat()
        
        if today not in self.daily_activity:
            self.daily_activity[today] = DailyActivity(date=today)
        
        self.daily_activity[today].quizzes_completed += 1
        self.daily_activity[today].score_sum += score
        self._update_streak()

    def _update_streak(self) -> None:
        """Calculate and update current streak based on daily activity."""
        today = date.today()
        streak = 0
        current_date = today
        
        while True:
            date_str = current_date.isoformat()
            if date_str in self.daily_activity:
                activity = self.daily_activity[date_str]
                if activity.reviews_completed > 0 or activity.quizzes_completed > 0:
                    streak += 1
                    current_date -= timedelta(days=1)
                else:
                    break
            else:
                # Check if it's today (give benefit of the doubt for today)
                if current_date == today:
                    current_date -= timedelta(days=1)
                else:
                    break
        
        self.current_streak = streak
        if streak > self.longest_streak:
            self.longest_streak = streak

    def get_heatmap_data(self, days: int = 365) -> list[dict]:
        """Get activity data for heatmap visualization.
        
        Args:
            days: Number of days to include (default 365).
            
        Returns:
            List of dicts with date, count, and level (0-4).
        """
        today = date.today()
        heatmap = []
        
        for i in range(days):
            current_date = today - timedelta(days=days - 1 - i)
            date_str = current_date.isoformat()
            
            if date_str in self.daily_activity:
                activity = self.daily_activity[date_str]
                count = activity.reviews_completed + activity.quizzes_completed
            else:
                count = 0
            
            # Calculate level (0-4) based on activity count
            if count == 0:
                level = 0
            elif count <= 2:
                level = 1
            elif count <= 5:
                level = 2
            elif count <= 10:
                level = 3
            else:
                level = 4
            
            heatmap.append({
                "date": date_str,
                "count": count,
                "level": level,
            })
        
        return heatmap

    def get_weekly_stats(self) -> dict:
        """Get statistics for the current week."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # Monday
        
        reviews = 0
        quizzes = 0
        
        for i in range(7):
            date_str = (week_start + timedelta(days=i)).isoformat()
            if date_str in self.daily_activity:
                activity = self.daily_activity[date_str]
                reviews += activity.reviews_completed
                quizzes += activity.quizzes_completed
        
        return {
            "reviews_this_week": reviews,
            "quizzes_this_week": quizzes,
            "total_this_week": reviews + quizzes,
        }

    def _refresh_topic_classifications(self) -> None:
        """Refresh weak and strong topic lists based on current scores."""
        self.weak_topics = [
            name
            for name, progress in self.topic_progress.items()
            if progress.average_score < 60 and progress.attempts > 0
        ]
        self.strong_topics = [
            name
            for name, progress in self.topic_progress.items()
            if progress.average_score >= 85 and progress.attempts > 0
        ]

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "LearningState":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "LearningState":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
