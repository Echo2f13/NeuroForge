"""Spaced Repetition Scheduler for NeuroForge.

Implements the SM-2 algorithm for flashcard scheduling. Tracks ease factor,
interval, repetitions, and next review date per card. Provides a review queue
of cards due on a given day.

SM-2 Algorithm:
- quality 0-5 (0=total blackout, 5=perfect recall)
- After successful review (quality >= 3):
  - repetition 1: interval = 1 day
  - repetition 2: interval = 6 days
  - repetition 3+: interval = round(prev_interval * ease_factor)
- After failed review (quality < 3):
  - repetitions reset to 0, interval = 1 day
- Ease factor update: EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
- Minimum ease factor: 1.3
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


# Default initial ease factor per SM-2
_DEFAULT_EASE_FACTOR = 2.5
_MIN_EASE_FACTOR = 1.3


class SpacedRepetitionScheduler:
    """SM-2 based spaced repetition scheduler.

    Manages flashcard scheduling with persistence to a JSON state file.

    Args:
        state_file: Path to the JSON state file. Defaults to "./sr_state.json".
    """

    def __init__(self, state_file: str = "./sr_state.json") -> None:
        self.state_file = state_file
        self._cards: dict[str, dict] = {}
        self.load()

    def add_card(self, card_id: str) -> None:
        """Register a new card for scheduling.

        If the card already exists, this is a no-op.

        Args:
            card_id: Unique identifier for the card.
        """
        if card_id in self._cards:
            return

        self._cards[card_id] = {
            "ease_factor": _DEFAULT_EASE_FACTOR,
            "interval": 0,
            "repetitions": 0,
            "next_review": date.today().isoformat(),
        }
        self.save()

    def review_card(self, card_id: str, quality: int) -> None:
        """Process a review for a card using the SM-2 algorithm.

        Args:
            card_id: The card to review.
            quality: Review quality from 0-5 (0=blackout, 5=perfect).

        Raises:
            ValueError: If quality is not between 0 and 5.
            KeyError: If card_id is not registered.
        """
        if quality < 0 or quality > 5:
            raise ValueError(f"Quality must be between 0 and 5, got {quality}")
        if card_id not in self._cards:
            raise KeyError(f"Card '{card_id}' not found. Add it first.")

        card = self._cards[card_id]

        # Update ease factor
        ef = card["ease_factor"]
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ef = max(ef, _MIN_EASE_FACTOR)
        card["ease_factor"] = ef

        if quality >= 3:
            # Successful review
            card["repetitions"] += 1
            if card["repetitions"] == 1:
                card["interval"] = 1
            elif card["repetitions"] == 2:
                card["interval"] = 6
            else:
                card["interval"] = round(card["interval"] * ef)
        else:
            # Failed review — reset
            card["repetitions"] = 0
            card["interval"] = 1

        # Compute next review date
        today = date.today()
        card["next_review"] = (today + timedelta(days=card["interval"])).isoformat()

        self.save()

    def get_due_cards(self, on_date: str | None = None) -> list[str]:
        """Get cards that are due for review on a given date.

        Args:
            on_date: ISO date string (YYYY-MM-DD). Defaults to today.

        Returns:
            List of card_id strings due on or before the given date.
        """
        if on_date is None:
            target = date.today()
        else:
            target = date.fromisoformat(on_date)

        due: list[str] = []
        for card_id, card in self._cards.items():
            review_date = date.fromisoformat(card["next_review"])
            if review_date <= target:
                due.append(card_id)
        return due

    def get_card_stats(self, card_id: str) -> dict:
        """Return scheduling statistics for a card.

        Args:
            card_id: The card to query.

        Returns:
            Dictionary with ease_factor, interval, repetitions, next_review.

        Raises:
            KeyError: If card_id is not registered.
        """
        if card_id not in self._cards:
            raise KeyError(f"Card '{card_id}' not found.")

        card = self._cards[card_id]
        return {
            "ease_factor": card["ease_factor"],
            "interval": card["interval"],
            "repetitions": card["repetitions"],
            "next_review": card["next_review"],
        }

    def save(self) -> None:
        """Persist the current state to the JSON file."""
        path = Path(self.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._cards, indent=2), encoding="utf-8")

    def load(self) -> None:
        """Load state from the JSON file.

        If the file doesn't exist or is corrupted, starts with empty state.
        """
        path = Path(self.state_file)
        if path.exists():
            try:
                data = path.read_text(encoding="utf-8")
                self._cards = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                self._cards = {}
        else:
            self._cards = {}

    def reset(self) -> None:
        """Clear all cards and remove the state file."""
        self._cards = {}
        path = Path(self.state_file)
        if path.exists():
            path.unlink()
