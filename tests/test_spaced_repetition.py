"""Tests for the SpacedRepetitionScheduler.

Tests SM-2 algorithm correctness, card lifecycle, due-card queue generation,
persistence, and simulated multi-day review sequences.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from src.memory import SpacedRepetitionScheduler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_state_file(tmp_path):
    """Provide a temporary state file path."""
    return str(tmp_path / "sr_state.json")


@pytest.fixture
def scheduler(tmp_state_file):
    """Create a fresh SpacedRepetitionScheduler with a temp state file."""
    return SpacedRepetitionScheduler(state_file=tmp_state_file)


# ---------------------------------------------------------------------------
# Initialization Tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_fresh_state_when_file_missing(self, tmp_state_file):
        sched = SpacedRepetitionScheduler(state_file=tmp_state_file)
        assert sched.get_due_cards() == []

    def test_loads_existing_state(self, tmp_state_file):
        # Create state file manually
        cards = {
            "card_1": {
                "ease_factor": 2.5,
                "interval": 6,
                "repetitions": 2,
                "next_review": date.today().isoformat(),
            }
        }
        Path(tmp_state_file).write_text(json.dumps(cards), encoding="utf-8")

        sched = SpacedRepetitionScheduler(state_file=tmp_state_file)
        stats = sched.get_card_stats("card_1")
        assert stats["interval"] == 6
        assert stats["repetitions"] == 2

    def test_handles_corrupted_file(self, tmp_state_file):
        Path(tmp_state_file).write_text("not valid json{{{", encoding="utf-8")
        sched = SpacedRepetitionScheduler(state_file=tmp_state_file)
        assert sched.get_due_cards() == []


# ---------------------------------------------------------------------------
# Add Card Tests
# ---------------------------------------------------------------------------


class TestAddCard:
    def test_add_new_card(self, scheduler):
        scheduler.add_card("card_1")
        stats = scheduler.get_card_stats("card_1")
        assert stats["ease_factor"] == 2.5
        assert stats["interval"] == 0
        assert stats["repetitions"] == 0
        assert stats["next_review"] == date.today().isoformat()

    def test_add_duplicate_card_is_noop(self, scheduler):
        scheduler.add_card("card_1")
        scheduler.review_card("card_1", 4)
        # Adding again should NOT reset its state
        scheduler.add_card("card_1")
        stats = scheduler.get_card_stats("card_1")
        assert stats["repetitions"] == 1

    def test_add_multiple_cards(self, scheduler):
        scheduler.add_card("a")
        scheduler.add_card("b")
        scheduler.add_card("c")
        due = scheduler.get_due_cards()
        assert set(due) == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Review Card Tests (SM-2 Algorithm)
# ---------------------------------------------------------------------------


class TestReviewCard:
    def test_invalid_quality_raises(self, scheduler):
        scheduler.add_card("card_1")
        with pytest.raises(ValueError):
            scheduler.review_card("card_1", -1)
        with pytest.raises(ValueError):
            scheduler.review_card("card_1", 6)

    def test_unknown_card_raises(self, scheduler):
        with pytest.raises(KeyError):
            scheduler.review_card("nonexistent", 4)

    def test_first_successful_review_interval_1(self, scheduler):
        scheduler.add_card("card_1")
        scheduler.review_card("card_1", 4)
        stats = scheduler.get_card_stats("card_1")
        assert stats["interval"] == 1
        assert stats["repetitions"] == 1
        expected_next = (date.today() + timedelta(days=1)).isoformat()
        assert stats["next_review"] == expected_next

    def test_second_successful_review_interval_6(self, scheduler):
        scheduler.add_card("card_1")
        scheduler.review_card("card_1", 4)
        scheduler.review_card("card_1", 4)
        stats = scheduler.get_card_stats("card_1")
        assert stats["interval"] == 6
        assert stats["repetitions"] == 2

    def test_third_successful_review_uses_ef(self, scheduler):
        scheduler.add_card("card_1")
        # Three perfect reviews (quality=5)
        scheduler.review_card("card_1", 5)
        scheduler.review_card("card_1", 5)
        scheduler.review_card("card_1", 5)
        stats = scheduler.get_card_stats("card_1")
        assert stats["repetitions"] == 3
        # EF after three q=5 reviews: 2.5 + 0.1 = 2.6 (first), 2.7, 2.8
        # interval = round(6 * 2.8) = round(16.8) = 17
        assert stats["interval"] == 17

    def test_failed_review_resets(self, scheduler):
        scheduler.add_card("card_1")
        # Build up some repetitions
        scheduler.review_card("card_1", 5)
        scheduler.review_card("card_1", 5)
        assert scheduler.get_card_stats("card_1")["repetitions"] == 2

        # Fail
        scheduler.review_card("card_1", 2)
        stats = scheduler.get_card_stats("card_1")
        assert stats["repetitions"] == 0
        assert stats["interval"] == 1

    def test_ease_factor_minimum_enforced(self, scheduler):
        scheduler.add_card("card_1")
        # Multiple reviews with quality=0 should not drop EF below 1.3
        for _ in range(10):
            scheduler.review_card("card_1", 0)
        stats = scheduler.get_card_stats("card_1")
        assert stats["ease_factor"] >= 1.3

    def test_ease_factor_update_quality_3(self, scheduler):
        scheduler.add_card("card_1")
        scheduler.review_card("card_1", 3)
        stats = scheduler.get_card_stats("card_1")
        # EF = 2.5 + (0.1 - (5-3)*(0.08 + (5-3)*0.02))
        # EF = 2.5 + (0.1 - 2*(0.08 + 2*0.02))
        # EF = 2.5 + (0.1 - 2*0.12) = 2.5 + (0.1 - 0.24) = 2.5 - 0.14 = 2.36
        assert abs(stats["ease_factor"] - 2.36) < 0.001

    def test_ease_factor_update_quality_5(self, scheduler):
        scheduler.add_card("card_1")
        scheduler.review_card("card_1", 5)
        stats = scheduler.get_card_stats("card_1")
        # EF = 2.5 + (0.1 - (5-5)*(0.08 + (5-5)*0.02))
        # EF = 2.5 + (0.1 - 0) = 2.6
        assert abs(stats["ease_factor"] - 2.6) < 0.001


# ---------------------------------------------------------------------------
# Due Cards Tests
# ---------------------------------------------------------------------------


class TestDueCards:
    def test_new_cards_are_due_today(self, scheduler):
        scheduler.add_card("card_1")
        scheduler.add_card("card_2")
        due = scheduler.get_due_cards()
        assert set(due) == {"card_1", "card_2"}

    def test_reviewed_cards_not_due_today(self, scheduler):
        scheduler.add_card("card_1")
        scheduler.review_card("card_1", 4)
        # After review with interval=1, next_review is tomorrow
        due = scheduler.get_due_cards()
        assert "card_1" not in due

    def test_cards_due_on_specific_date(self, scheduler):
        scheduler.add_card("card_1")
        scheduler.review_card("card_1", 4)
        # Card is due tomorrow
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        due = scheduler.get_due_cards(on_date=tomorrow)
        assert "card_1" in due

    def test_overdue_cards_included(self, scheduler):
        scheduler.add_card("card_1")
        # Card's next_review is today, check for future date
        future = (date.today() + timedelta(days=5)).isoformat()
        due = scheduler.get_due_cards(on_date=future)
        assert "card_1" in due


# ---------------------------------------------------------------------------
# Persistence Tests
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_and_load(self, tmp_state_file):
        sched1 = SpacedRepetitionScheduler(state_file=tmp_state_file)
        sched1.add_card("card_1")
        sched1.review_card("card_1", 5)

        sched2 = SpacedRepetitionScheduler(state_file=tmp_state_file)
        stats = sched2.get_card_stats("card_1")
        assert stats["repetitions"] == 1
        assert abs(stats["ease_factor"] - 2.6) < 0.001

    def test_reset_clears_state_and_file(self, scheduler, tmp_state_file):
        scheduler.add_card("card_1")
        assert Path(tmp_state_file).exists()

        scheduler.reset()
        assert not Path(tmp_state_file).exists()
        assert scheduler.get_due_cards() == []

    def test_creates_parent_directories(self, tmp_path):
        nested_path = str(tmp_path / "deep" / "nested" / "sr_state.json")
        sched = SpacedRepetitionScheduler(state_file=nested_path)
        sched.add_card("card_1")
        assert Path(nested_path).exists()


# ---------------------------------------------------------------------------
# Simulated Multi-Day Review Tests
# ---------------------------------------------------------------------------


class TestSimulatedDays:
    def test_multi_day_review_progression(self, tmp_state_file):
        """Simulate reviewing a card over multiple days with perfect recall."""
        sched = SpacedRepetitionScheduler(state_file=tmp_state_file)
        sched.add_card("card_1")

        # Day 0: card is due, review it perfectly
        today = date.today()

        with patch("src.memory.spaced_repetition.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.fromisoformat = date.fromisoformat
            sched.review_card("card_1", 5)
            stats = sched.get_card_stats("card_1")
            assert stats["interval"] == 1
            # next_review = today + 1 day

        # Day 1: card is due again
        day1 = today + timedelta(days=1)
        with patch("src.memory.spaced_repetition.date") as mock_date:
            mock_date.today.return_value = day1
            mock_date.fromisoformat = date.fromisoformat
            due = sched.get_due_cards(on_date=day1.isoformat())
            assert "card_1" in due
            sched.review_card("card_1", 5)
            stats = sched.get_card_stats("card_1")
            assert stats["interval"] == 6

        # Day 7: card is due again (day1 + 6 days)
        day7 = day1 + timedelta(days=6)
        with patch("src.memory.spaced_repetition.date") as mock_date:
            mock_date.today.return_value = day7
            mock_date.fromisoformat = date.fromisoformat
            due = sched.get_due_cards(on_date=day7.isoformat())
            assert "card_1" in due
            sched.review_card("card_1", 5)
            stats = sched.get_card_stats("card_1")
            # EF after 3 q=5: 2.5+0.1+0.1+0.1 = 2.8
            # interval = round(6 * 2.8) = 17
            assert stats["interval"] == 17
            assert stats["repetitions"] == 3

    def test_lapse_and_recovery(self, tmp_state_file):
        """Simulate a card being learned, lapsed, and re-learned."""
        sched = SpacedRepetitionScheduler(state_file=tmp_state_file)
        sched.add_card("vocab_1")

        today = date.today()

        # Build up to repetition 2
        with patch("src.memory.spaced_repetition.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.fromisoformat = date.fromisoformat
            sched.review_card("vocab_1", 4)  # rep=1, interval=1

        day1 = today + timedelta(days=1)
        with patch("src.memory.spaced_repetition.date") as mock_date:
            mock_date.today.return_value = day1
            mock_date.fromisoformat = date.fromisoformat
            sched.review_card("vocab_1", 4)  # rep=2, interval=6

        # Lapse on day 7
        day7 = day1 + timedelta(days=6)
        with patch("src.memory.spaced_repetition.date") as mock_date:
            mock_date.today.return_value = day7
            mock_date.fromisoformat = date.fromisoformat
            sched.review_card("vocab_1", 1)  # Fail! rep=0, interval=1
            stats = sched.get_card_stats("vocab_1")
            assert stats["repetitions"] == 0
            assert stats["interval"] == 1

        # Recovery on day 8
        day8 = day7 + timedelta(days=1)
        with patch("src.memory.spaced_repetition.date") as mock_date:
            mock_date.today.return_value = day8
            mock_date.fromisoformat = date.fromisoformat
            sched.review_card("vocab_1", 4)  # rep=1, interval=1
            stats = sched.get_card_stats("vocab_1")
            assert stats["repetitions"] == 1
            assert stats["interval"] == 1

    def test_multiple_cards_staggered_reviews(self, tmp_state_file):
        """Simulate multiple cards with different review schedules."""
        sched = SpacedRepetitionScheduler(state_file=tmp_state_file)
        sched.add_card("easy")
        sched.add_card("medium")
        sched.add_card("hard")

        today = date.today()

        with patch("src.memory.spaced_repetition.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.fromisoformat = date.fromisoformat
            # Review all on day 0
            sched.review_card("easy", 5)
            sched.review_card("medium", 3)
            sched.review_card("hard", 1)

        # Day 1: all should be due (easy/hard interval=1, medium interval=1)
        day1 = today + timedelta(days=1)
        due = sched.get_due_cards(on_date=day1.isoformat())
        assert set(due) == {"easy", "medium", "hard"}

        with patch("src.memory.spaced_repetition.date") as mock_date:
            mock_date.today.return_value = day1
            mock_date.fromisoformat = date.fromisoformat
            sched.review_card("easy", 5)   # rep=2, interval=6
            sched.review_card("medium", 4)  # rep=2, interval=6
            sched.review_card("hard", 5)    # rep=1, interval=1

        # Day 2: only hard should be due (interval=1 from day1)
        # easy: interval=6, due day1+6=day7
        # medium: interval=6, due day1+6=day7
        # hard: interval=1, due day1+1=day2
        day2 = today + timedelta(days=2)
        due = sched.get_due_cards(on_date=day2.isoformat())
        assert "easy" not in due
        assert "medium" not in due
        assert "hard" in due

        # Day 7: easy and medium become due again
        day7 = day1 + timedelta(days=6)
        due = sched.get_due_cards(on_date=day7.isoformat())
        assert "easy" in due
        assert "medium" in due
