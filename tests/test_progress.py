"""Tests for the ProgressTracker.

Tests recording scores, mastery levels, weak/strong topic identification,
persistence, and overall stats with simulated quiz sequences.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from models.learning import LearningState, TopicProgress
from src.memory import ProgressTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_state_file(tmp_path):
    """Provide a temporary state file path."""
    return str(tmp_path / "test_state.json")


@pytest.fixture
def tracker(tmp_state_file):
    """Create a fresh ProgressTracker with a temp state file."""
    return ProgressTracker(state_file=tmp_state_file)


# ---------------------------------------------------------------------------
# Initialization Tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_fresh_state_when_file_missing(self, tmp_state_file):
        tracker = ProgressTracker(state_file=tmp_state_file)
        assert tracker.state.total_quizzes_taken == 0
        assert tracker.state.topic_progress == {}

    def test_loads_existing_state(self, tmp_state_file):
        # Create a state file first
        state = LearningState()
        state.update_topic_score("math", 80.0)
        Path(tmp_state_file).write_text(
            state.model_dump_json(indent=2), encoding="utf-8"
        )

        tracker = ProgressTracker(state_file=tmp_state_file)
        assert "math" in tracker.state.topic_progress
        assert tracker.state.topic_progress["math"].average_score == 80.0

    def test_handles_corrupted_file(self, tmp_state_file):
        Path(tmp_state_file).write_text("not valid json{{{", encoding="utf-8")
        tracker = ProgressTracker(state_file=tmp_state_file)
        assert tracker.state.total_quizzes_taken == 0


# ---------------------------------------------------------------------------
# Score Recording Tests
# ---------------------------------------------------------------------------


class TestRecordScore:
    def test_record_single_score(self, tracker):
        tracker.record_score("python", 75.0)
        progress = tracker.get_topic_progress("python")
        assert progress.attempts == 1
        assert progress.average_score == 75.0

    def test_record_multiple_scores_same_topic(self, tracker):
        tracker.record_score("python", 60.0)
        tracker.record_score("python", 80.0)
        tracker.record_score("python", 100.0)
        progress = tracker.get_topic_progress("python")
        assert progress.attempts == 3
        assert progress.average_score == 80.0

    def test_record_scores_different_topics(self, tracker):
        tracker.record_score("math", 90.0)
        tracker.record_score("physics", 50.0)
        assert tracker.state.total_quizzes_taken == 2
        assert len(tracker.state.topic_progress) == 2

    def test_invalid_score_raises(self, tracker):
        with pytest.raises(ValueError):
            tracker.record_score("math", 101.0)
        with pytest.raises(ValueError):
            tracker.record_score("math", -1.0)

    def test_record_score_updates_timestamp(self, tracker):
        tracker.record_score("python", 70.0)
        progress = tracker.get_topic_progress("python")
        assert progress.last_attempted is not None

    def test_record_score_auto_saves(self, tracker, tmp_state_file):
        tracker.record_score("python", 85.0)
        assert Path(tmp_state_file).exists()
        data = json.loads(Path(tmp_state_file).read_text(encoding="utf-8"))
        assert data["total_quizzes_taken"] == 1


# ---------------------------------------------------------------------------
# Mastery Level Tests
# ---------------------------------------------------------------------------


class TestMasteryLevel:
    def test_not_started(self, tracker):
        assert tracker.get_mastery_level("unknown") == "not_started"

    def test_learning_below_60(self, tracker):
        tracker.record_score("hard_topic", 40.0)
        tracker.record_score("hard_topic", 50.0)
        assert tracker.get_mastery_level("hard_topic") == "learning"

    def test_familiar_between_60_and_85(self, tracker):
        tracker.record_score("medium_topic", 70.0)
        tracker.record_score("medium_topic", 75.0)
        assert tracker.get_mastery_level("medium_topic") == "familiar"

    def test_mastered_above_85(self, tracker):
        tracker.record_score("easy_topic", 90.0)
        tracker.record_score("easy_topic", 95.0)
        assert tracker.get_mastery_level("easy_topic") == "mastered"


# ---------------------------------------------------------------------------
# Weak/Strong Topic Tests
# ---------------------------------------------------------------------------


class TestWeakStrongTopics:
    def test_weak_topics(self, tracker):
        tracker.record_score("struggling", 30.0)
        tracker.record_score("struggling", 40.0)
        tracker.record_score("okay", 70.0)
        assert "struggling" in tracker.get_weak_topics()
        assert "okay" not in tracker.get_weak_topics()

    def test_strong_topics(self, tracker):
        tracker.record_score("excelling", 90.0)
        tracker.record_score("excelling", 95.0)
        tracker.record_score("okay", 70.0)
        assert "excelling" in tracker.get_strong_topics()
        assert "okay" not in tracker.get_strong_topics()

    def test_topic_moves_from_weak_to_strong(self, tracker):
        # Start weak
        tracker.record_score("improving", 30.0)
        assert "improving" in tracker.get_weak_topics()

        # Improve significantly
        tracker.record_score("improving", 100.0)
        tracker.record_score("improving", 100.0)
        tracker.record_score("improving", 100.0)
        # Average: (30+100+100+100)/4 = 82.5 — not quite strong yet
        assert "improving" not in tracker.get_weak_topics()

        tracker.record_score("improving", 100.0)
        # Average: (30+100*4)/5 = 86 — now strong
        assert "improving" in tracker.get_strong_topics()


# ---------------------------------------------------------------------------
# Overall Stats Tests
# ---------------------------------------------------------------------------


class TestOverallStats:
    def test_empty_stats(self, tracker):
        stats = tracker.get_overall_stats()
        assert stats["total_quizzes"] == 0
        assert stats["total_topics"] == 0
        assert stats["average_score"] == 0.0

    def test_stats_after_scores(self, tracker):
        tracker.record_score("math", 80.0)
        tracker.record_score("math", 90.0)
        tracker.record_score("physics", 60.0)
        stats = tracker.get_overall_stats()
        assert stats["total_quizzes"] == 3
        assert stats["total_topics"] == 2
        # (80 + 90 + 60) / 3 = 76.67
        assert abs(stats["average_score"] - 76.67) < 0.01

    def test_stats_includes_weak_strong_counts(self, tracker):
        tracker.record_score("weak_topic", 30.0)
        tracker.record_score("strong_topic", 95.0)
        stats = tracker.get_overall_stats()
        assert stats["weak_count"] == 1
        assert stats["strong_count"] == 1


# ---------------------------------------------------------------------------
# Persistence Tests
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_and_load(self, tmp_state_file):
        tracker1 = ProgressTracker(state_file=tmp_state_file)
        tracker1.record_score("biology", 88.0)
        tracker1.record_score("chemistry", 45.0)

        # Create a new tracker from the same file
        tracker2 = ProgressTracker(state_file=tmp_state_file)
        assert tracker2.get_topic_progress("biology").average_score == 88.0
        assert tracker2.get_topic_progress("chemistry").average_score == 45.0
        assert tracker2.state.total_quizzes_taken == 2

    def test_reset_clears_state_and_file(self, tracker, tmp_state_file):
        tracker.record_score("math", 70.0)
        assert Path(tmp_state_file).exists()

        tracker.reset()
        assert tracker.state.total_quizzes_taken == 0
        assert tracker.state.topic_progress == {}
        assert not Path(tmp_state_file).exists()

    def test_creates_parent_directories(self, tmp_path):
        nested_path = str(tmp_path / "deep" / "nested" / "state.json")
        tracker = ProgressTracker(state_file=nested_path)
        tracker.record_score("test", 80.0)
        assert Path(nested_path).exists()


# ---------------------------------------------------------------------------
# Simulated Sequence Tests
# ---------------------------------------------------------------------------


class TestSimulatedSequences:
    def test_student_learning_journey(self, tracker):
        """Simulate a student progressing through multiple topics over time."""
        # Week 1: Student starts learning
        tracker.record_score("python_basics", 45.0)
        tracker.record_score("data_structures", 35.0)
        tracker.record_score("algorithms", 50.0)

        assert set(tracker.get_weak_topics()) == {
            "python_basics",
            "data_structures",
            "algorithms",
        }
        assert tracker.get_strong_topics() == []

        # Week 2: Improvement in python_basics
        tracker.record_score("python_basics", 70.0)
        tracker.record_score("python_basics", 85.0)
        # Average: (45+70+85)/3 = 66.67 — familiar now
        assert "python_basics" not in tracker.get_weak_topics()
        assert tracker.get_mastery_level("python_basics") == "familiar"

        # Week 3: Mastery in python_basics, data_structures improving
        tracker.record_score("python_basics", 95.0)
        tracker.record_score("python_basics", 92.0)
        # Average: (45+70+85+95+92)/5 = 77.4 — still familiar
        tracker.record_score("data_structures", 65.0)
        tracker.record_score("data_structures", 75.0)

        # Final stats check
        stats = tracker.get_overall_stats()
        assert stats["total_quizzes"] == 9
        assert stats["total_topics"] == 3

    def test_multiple_topics_mixed_performance(self, tracker):
        """Simulate mixed performance across many topics."""
        scores = {
            "linear_algebra": [90, 88, 92, 95],  # Strong
            "calculus": [70, 75, 72, 68],  # Familiar
            "statistics": [40, 45, 50, 55],  # Weak (learning)
            "discrete_math": [85, 90, 88, 92],  # Strong
            "probability": [55, 50, 45, 60],  # Weak (borderline)
        }
        for topic, topic_scores in scores.items():
            for score in topic_scores:
                tracker.record_score(topic, score)

        # Verify classifications
        strong = tracker.get_strong_topics()
        weak = tracker.get_weak_topics()

        assert "linear_algebra" in strong
        assert "discrete_math" in strong
        assert "statistics" in weak
        assert "calculus" not in weak
        assert "calculus" not in strong

        # probability average: (55+50+45+60)/4 = 52.5 — weak
        assert "probability" in weak

        stats = tracker.get_overall_stats()
        assert stats["total_quizzes"] == 20
        assert stats["total_topics"] == 5
