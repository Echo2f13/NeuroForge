"""Tests for the AdaptiveDifficulty module.

Tests difficulty recommendations, quiz/flashcard parameter adjustments,
and adaptation over multiple rounds of score changes.
"""

import tempfile
from pathlib import Path

import pytest

from src.memory import AdaptiveDifficulty, ProgressTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_state_file(tmp_path):
    """Provide a temporary state file path."""
    return str(tmp_path / "adaptive_test_state.json")


@pytest.fixture
def tracker(tmp_state_file):
    """Create a fresh ProgressTracker with a temp state file."""
    return ProgressTracker(state_file=tmp_state_file)


@pytest.fixture
def adaptive(tracker):
    """Create an AdaptiveDifficulty instance wrapping a fresh tracker."""
    return AdaptiveDifficulty(progress_tracker=tracker)


# ---------------------------------------------------------------------------
# Difficulty Recommendation Tests
# ---------------------------------------------------------------------------


class TestGetRecommendedDifficulty:
    def test_unknown_topic_returns_easy(self, adaptive):
        """Topics with no attempts should default to easy (mastery=0)."""
        assert adaptive.get_recommended_difficulty("never_seen") == "easy"

    def test_low_mastery_returns_easy(self, tracker, adaptive):
        """Mastery < 40% → easy."""
        tracker.record_score("weak_topic", 20.0)
        tracker.record_score("weak_topic", 30.0)
        # Average: 25%
        assert adaptive.get_recommended_difficulty("weak_topic") == "easy"

    def test_medium_mastery_returns_medium(self, tracker, adaptive):
        """40% <= mastery < 70% → medium."""
        tracker.record_score("mid_topic", 50.0)
        tracker.record_score("mid_topic", 60.0)
        # Average: 55%
        assert adaptive.get_recommended_difficulty("mid_topic") == "medium"

    def test_high_mastery_returns_hard(self, tracker, adaptive):
        """Mastery >= 70% → hard."""
        tracker.record_score("strong_topic", 80.0)
        tracker.record_score("strong_topic", 90.0)
        # Average: 85%
        assert adaptive.get_recommended_difficulty("strong_topic") == "hard"

    def test_boundary_at_40(self, tracker, adaptive):
        """Exactly 40% should return medium."""
        tracker.record_score("boundary_40", 40.0)
        assert adaptive.get_recommended_difficulty("boundary_40") == "medium"

    def test_boundary_at_70(self, tracker, adaptive):
        """Exactly 70% should return hard."""
        tracker.record_score("boundary_70", 70.0)
        assert adaptive.get_recommended_difficulty("boundary_70") == "hard"

    def test_just_below_40(self, tracker, adaptive):
        """Score of 39% should return easy."""
        tracker.record_score("below_40", 39.0)
        assert adaptive.get_recommended_difficulty("below_40") == "easy"

    def test_just_below_70(self, tracker, adaptive):
        """Score of 69% should return medium."""
        tracker.record_score("below_70", 69.0)
        assert adaptive.get_recommended_difficulty("below_70") == "medium"


# ---------------------------------------------------------------------------
# Batch Difficulty Tests
# ---------------------------------------------------------------------------


class TestGetDifficultyForTopics:
    def test_empty_list(self, adaptive):
        assert adaptive.get_difficulty_for_topics([]) == {}

    def test_multiple_topics(self, tracker, adaptive):
        tracker.record_score("weak", 20.0)
        tracker.record_score("mid", 55.0)
        tracker.record_score("strong", 85.0)

        result = adaptive.get_difficulty_for_topics(["weak", "mid", "strong", "new"])
        assert result == {
            "weak": "easy",
            "mid": "medium",
            "strong": "hard",
            "new": "easy",
        }


# ---------------------------------------------------------------------------
# Quiz Parameter Adjustment Tests
# ---------------------------------------------------------------------------


class TestAdjustQuizParams:
    def test_easy_params(self, tracker, adaptive):
        tracker.record_score("weak", 25.0)
        params = adaptive.adjust_quiz_params("weak", base_num_questions=10)
        assert params["difficulty"] == "easy"
        assert params["num_questions"] == 7  # 10 - 3
        assert "mcq" in params["question_types"]
        assert "true_false" in params["question_types"]
        assert "short_answer" not in params["question_types"]

    def test_medium_params(self, tracker, adaptive):
        tracker.record_score("mid", 55.0)
        params = adaptive.adjust_quiz_params("mid", base_num_questions=10)
        assert params["difficulty"] == "medium"
        assert params["num_questions"] == 10
        assert "mcq" in params["question_types"]
        assert "short_answer" in params["question_types"]
        assert "true_false" in params["question_types"]

    def test_hard_params(self, tracker, adaptive):
        tracker.record_score("strong", 85.0)
        params = adaptive.adjust_quiz_params("strong", base_num_questions=10)
        assert params["difficulty"] == "hard"
        assert params["num_questions"] == 12  # 10 + 2
        assert "mcq" in params["question_types"]
        assert "short_answer" in params["question_types"]

    def test_easy_minimum_questions(self, tracker, adaptive):
        """Even with small base, num_questions should not drop below 5."""
        tracker.record_score("weak", 20.0)
        params = adaptive.adjust_quiz_params("weak", base_num_questions=5)
        assert params["num_questions"] == 5

    def test_custom_base_questions(self, tracker, adaptive):
        tracker.record_score("topic", 50.0)
        params = adaptive.adjust_quiz_params("topic", base_num_questions=20)
        assert params["num_questions"] == 20


# ---------------------------------------------------------------------------
# Flashcard Parameter Adjustment Tests
# ---------------------------------------------------------------------------


class TestAdjustFlashcardParams:
    def test_easy_params(self, tracker, adaptive):
        tracker.record_score("weak", 25.0)
        params = adaptive.adjust_flashcard_params("weak", base_num_cards=10)
        assert params["difficulty"] == "easy"
        assert params["num_cards"] == 7  # 10 - 3
        assert "definition" in params["card_types"]
        assert "basic_concept" in params["card_types"]

    def test_medium_params(self, tracker, adaptive):
        tracker.record_score("mid", 55.0)
        params = adaptive.adjust_flashcard_params("mid", base_num_cards=10)
        assert params["difficulty"] == "medium"
        assert params["num_cards"] == 10
        assert "definition" in params["card_types"]
        assert "concept" in params["card_types"]
        assert "application" in params["card_types"]

    def test_hard_params(self, tracker, adaptive):
        tracker.record_score("strong", 85.0)
        params = adaptive.adjust_flashcard_params("strong", base_num_cards=10)
        assert params["difficulty"] == "hard"
        assert params["num_cards"] == 13  # 10 + 3
        assert "concept" in params["card_types"]
        assert "application" in params["card_types"]
        assert "analysis" in params["card_types"]

    def test_easy_minimum_cards(self, tracker, adaptive):
        """Even with small base, num_cards should not drop below 5."""
        tracker.record_score("weak", 20.0)
        params = adaptive.adjust_flashcard_params("weak", base_num_cards=5)
        assert params["num_cards"] == 5


# ---------------------------------------------------------------------------
# Adaptation Over Multiple Rounds
# ---------------------------------------------------------------------------


class TestAdaptationOverRounds:
    def test_difficulty_adapts_as_student_improves(self, tracker, adaptive):
        """Student starts weak and gradually improves."""
        # Round 1: Low mastery → easy
        tracker.record_score("python", 30.0)
        assert adaptive.get_recommended_difficulty("python") == "easy"

        # Round 2: Slight improvement, still easy
        tracker.record_score("python", 35.0)
        # Average: 32.5%
        assert adaptive.get_recommended_difficulty("python") == "easy"

        # Round 3: Break into medium range
        tracker.record_score("python", 60.0)
        # Average: (30+35+60)/3 = 41.67%
        assert adaptive.get_recommended_difficulty("python") == "medium"

        # Round 4-5: Keep improving
        tracker.record_score("python", 75.0)
        tracker.record_score("python", 80.0)
        # Average: (30+35+60+75+80)/5 = 56%
        assert adaptive.get_recommended_difficulty("python") == "medium"

        # Round 6-8: Strong performance pushes into hard
        tracker.record_score("python", 90.0)
        tracker.record_score("python", 95.0)
        tracker.record_score("python", 95.0)
        # Average: (30+35+60+75+80+90+95+95)/8 = 70%
        assert adaptive.get_recommended_difficulty("python") == "hard"

    def test_difficulty_decreases_with_poor_performance(self, tracker, adaptive):
        """Student was strong but performance drops."""
        # Start strong
        tracker.record_score("math", 90.0)
        tracker.record_score("math", 85.0)
        # Average: 87.5%
        assert adaptive.get_recommended_difficulty("math") == "hard"

        # Performance drops significantly
        tracker.record_score("math", 20.0)
        tracker.record_score("math", 25.0)
        # Average: (90+85+20+25)/4 = 55%
        assert adaptive.get_recommended_difficulty("math") == "medium"

        # Continues to struggle
        tracker.record_score("math", 15.0)
        tracker.record_score("math", 20.0)
        # Average: (90+85+20+25+15+20)/6 = 42.5%
        assert adaptive.get_recommended_difficulty("math") == "medium"

        tracker.record_score("math", 10.0)
        tracker.record_score("math", 15.0)
        # Average: (90+85+20+25+15+20+10+15)/8 = 35%
        assert adaptive.get_recommended_difficulty("math") == "easy"

    def test_quiz_params_adapt_with_progress(self, tracker, adaptive):
        """Quiz parameters change as the student progresses."""
        # Weak phase
        tracker.record_score("physics", 25.0)
        params = adaptive.adjust_quiz_params("physics")
        assert params["difficulty"] == "easy"
        assert params["num_questions"] == 7

        # Medium phase
        tracker.record_score("physics", 80.0)
        # Average: (25+80)/2 = 52.5%
        params = adaptive.adjust_quiz_params("physics")
        assert params["difficulty"] == "medium"
        assert params["num_questions"] == 10

        # Hard phase
        tracker.record_score("physics", 95.0)
        tracker.record_score("physics", 90.0)
        # Average: (25+80+95+90)/4 = 72.5%
        params = adaptive.adjust_quiz_params("physics")
        assert params["difficulty"] == "hard"
        assert params["num_questions"] == 12

    def test_multiple_topics_adapt_independently(self, tracker, adaptive):
        """Each topic adapts independently based on its own mastery."""
        tracker.record_score("easy_topic", 20.0)
        tracker.record_score("medium_topic", 55.0)
        tracker.record_score("hard_topic", 85.0)

        assert adaptive.get_recommended_difficulty("easy_topic") == "easy"
        assert adaptive.get_recommended_difficulty("medium_topic") == "medium"
        assert adaptive.get_recommended_difficulty("hard_topic") == "hard"

        # Improve easy_topic only
        tracker.record_score("easy_topic", 80.0)
        # easy_topic average: (20+80)/2 = 50% → medium
        assert adaptive.get_recommended_difficulty("easy_topic") == "medium"
        # Others unchanged
        assert adaptive.get_recommended_difficulty("medium_topic") == "medium"
        assert adaptive.get_recommended_difficulty("hard_topic") == "hard"
