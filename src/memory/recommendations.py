"""Personalized Recommendation Engine for NeuroForge.

Generates study recommendations by combining signals from:
- ProgressTracker: weak topics, mastery levels, last-attempted timestamps
- KnowledgeGraph (optional): prerequisite relationships for next-topic suggestions
- SpacedRepetitionScheduler (optional): due flashcards for revision timing

The engine is stateless — it reads from the above components and produces
prioritized recommendations on each call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.memory.progress import ProgressTracker
from src.memory.spaced_repetition import SpacedRepetitionScheduler
from src.store.knowledge_graph import KnowledgeGraph


class RecommendationEngine:
    """Generates personalized study recommendations.

    Combines progress data, knowledge graph structure, and spaced repetition
    scheduling to produce prioritized study actions and daily plans.

    Args:
        progress_tracker: ProgressTracker instance for mastery/weak topic data.
        knowledge_graph: Optional KnowledgeGraph for prerequisite-based suggestions.
        scheduler: Optional SpacedRepetitionScheduler for revision timing.
    """

    def __init__(
        self,
        progress_tracker: ProgressTracker,
        knowledge_graph: Optional[KnowledgeGraph] = None,
        scheduler: Optional[SpacedRepetitionScheduler] = None,
    ) -> None:
        self.progress_tracker = progress_tracker
        self.knowledge_graph = knowledge_graph
        self.scheduler = scheduler

    def get_study_recommendations(self) -> list[dict]:
        """Generate a prioritized list of study recommendations.

        Combines signals from weak topics (high priority), due flashcards
        (medium priority), and suggested next topics (medium-low priority).

        Returns:
            List of recommendation dicts, each with:
            - action (str): What to do (e.g., "review", "practice", "learn")
            - topic (str): The topic or card ID
            - reason (str): Why this is recommended
            - priority (int): 1-5, where 5 is highest priority
        """
        recommendations: list[dict] = []

        # High priority: weak topics (priority 5)
        weak_topics = self.progress_tracker.get_weak_topics()
        for topic in weak_topics:
            progress = self.progress_tracker.get_topic_progress(topic)
            recommendations.append({
                "action": "practice",
                "topic": topic,
                "reason": f"Weak topic with average score {progress.average_score:.0f}%",
                "priority": 5,
            })

        # Medium priority: due flashcards (priority 3)
        if self.scheduler:
            due_cards = self.scheduler.get_due_cards()
            for card_id in due_cards:
                recommendations.append({
                    "action": "review",
                    "topic": card_id,
                    "reason": "Flashcard due for spaced repetition review",
                    "priority": 3,
                })

        # Medium-low priority: next topics (priority 2)
        next_topics = self.suggest_next_topics()
        for topic in next_topics:
            recommendations.append({
                "action": "learn",
                "topic": topic,
                "reason": "All prerequisites mastered — ready to learn",
                "priority": 2,
            })

        # Sort by priority descending
        recommendations.sort(key=lambda r: r["priority"], reverse=True)

        return recommendations

    def suggest_next_topics(self) -> list[str]:
        """Suggest topics whose prerequisites are all mastered or familiar.

        Uses the knowledge graph to find concepts where every prerequisite
        has a mastery level of 'mastered' or 'familiar', and the concept
        itself is not yet mastered.

        Returns:
            List of topic/concept names ready to learn.
        """
        if not self.knowledge_graph:
            return []

        suggestions: list[str] = []

        for node_id in self.knowledge_graph.graph.nodes():
            node_data = self.knowledge_graph.graph.nodes[node_id]
            node_name = node_data.get("name", node_id)

            # Skip if already mastered or familiar
            mastery = self.progress_tracker.get_mastery_level(node_name)
            if mastery in ("mastered", "familiar"):
                continue

            # Get prerequisites for this concept
            prerequisites = self.knowledge_graph.get_prerequisites(node_id)

            if not prerequisites:
                # No prerequisites — always a valid suggestion if not mastered
                if mastery == "not_started":
                    suggestions.append(node_name)
                continue

            # Check if all prerequisites are mastered or familiar
            all_prereqs_met = True
            for prereq_id in prerequisites:
                prereq_data = self.knowledge_graph.graph.nodes.get(prereq_id, {})
                prereq_name = prereq_data.get("name", prereq_id)
                prereq_mastery = self.progress_tracker.get_mastery_level(prereq_name)
                if prereq_mastery not in ("mastered", "familiar"):
                    all_prereqs_met = False
                    break

            if all_prereqs_met:
                suggestions.append(node_name)

        return suggestions

    def suggest_revision_topics(self) -> list[str]:
        """Suggest topics that haven't been reviewed recently.

        Identifies topics where the last attempt was more than 7 days ago,
        or topics that have been attempted but are not yet mastered.

        Returns:
            List of topic names that should be revised.
        """
        revision_topics: list[str] = []
        now = datetime.now(timezone.utc)

        state = self.progress_tracker.state
        for topic_name, progress in state.topic_progress.items():
            if progress.attempts == 0:
                continue

            # Already mastered with recent review — skip
            if progress.mastery_level == "mastered":
                # Even mastered topics need periodic review
                if progress.last_attempted:
                    try:
                        last = datetime.fromisoformat(progress.last_attempted)
                        days_since = (now - last).days
                        if days_since > 14:
                            revision_topics.append(topic_name)
                    except (ValueError, TypeError):
                        pass
                continue

            # Not mastered — check if stale (> 7 days since last attempt)
            if progress.last_attempted:
                try:
                    last = datetime.fromisoformat(progress.last_attempted)
                    days_since = (now - last).days
                    if days_since > 7:
                        revision_topics.append(topic_name)
                except (ValueError, TypeError):
                    # If timestamp is invalid, suggest revision
                    revision_topics.append(topic_name)
            else:
                # Has attempts but no timestamp — suggest revision
                revision_topics.append(topic_name)

        return revision_topics

    def get_daily_plan(self) -> dict:
        """Generate a structured daily study plan.

        Combines due flashcards, weak topics, and next topics into a
        cohesive plan with time estimates.

        Returns:
            Dictionary with:
            - review_cards (list): Card IDs due for review today
            - weak_topics (list): Topics needing practice
            - next_topics (list): New topics ready to learn
            - estimated_time_minutes (int): Estimated total study time
        """
        review_cards: list[str] = []
        if self.scheduler:
            review_cards = self.scheduler.get_due_cards()

        weak_topics = self.progress_tracker.get_weak_topics()
        next_topics = self.suggest_next_topics()

        # Time estimates:
        # - 2 minutes per flashcard review
        # - 15 minutes per weak topic practice
        # - 20 minutes per new topic
        estimated_time = (
            len(review_cards) * 2
            + len(weak_topics) * 15
            + len(next_topics) * 20
        )

        return {
            "review_cards": review_cards,
            "weak_topics": weak_topics,
            "next_topics": next_topics,
            "estimated_time_minutes": estimated_time,
        }
