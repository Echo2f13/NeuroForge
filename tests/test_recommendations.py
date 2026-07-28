"""Tests for the RecommendationEngine.

Tests personalized study recommendations, next-topic suggestions based on
prerequisite completion, revision timing, and daily plan generation across
various learning states.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.memory import ProgressTracker, RecommendationEngine, SpacedRepetitionScheduler
from src.store import KnowledgeGraph
from models import Concept, ConceptRelationship, Difficulty


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_progress_file(tmp_path):
    """Provide a temporary progress state file."""
    return str(tmp_path / "progress.json")


@pytest.fixture
def tmp_sr_file(tmp_path):
    """Provide a temporary spaced repetition state file."""
    return str(tmp_path / "sr_state.json")


@pytest.fixture
def progress_tracker(tmp_progress_file):
    """Create a fresh ProgressTracker."""
    return ProgressTracker(state_file=tmp_progress_file)


@pytest.fixture
def scheduler(tmp_sr_file):
    """Create a fresh SpacedRepetitionScheduler."""
    return SpacedRepetitionScheduler(state_file=tmp_sr_file)


@pytest.fixture
def knowledge_graph():
    """Create a knowledge graph with prerequisite relationships."""
    kg = KnowledgeGraph()
    concepts = [
        Concept(
            id="algebra",
            name="Algebra",
            definition="Basic algebra",
            difficulty=Difficulty.EASY,
            topics=["math"],
        ),
        Concept(
            id="calculus",
            name="Calculus",
            definition="Differential calculus",
            difficulty=Difficulty.MEDIUM,
            topics=["math"],
        ),
        Concept(
            id="linear_algebra",
            name="Linear Algebra",
            definition="Vectors and matrices",
            difficulty=Difficulty.MEDIUM,
            topics=["math"],
        ),
        Concept(
            id="machine_learning",
            name="Machine Learning",
            definition="ML fundamentals",
            difficulty=Difficulty.HARD,
            topics=["cs"],
        ),
    ]
    relationships = [
        ConceptRelationship(
            source_concept="algebra",
            target_concept="calculus",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="algebra",
            target_concept="linear_algebra",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="calculus",
            target_concept="machine_learning",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="linear_algebra",
            target_concept="machine_learning",
            relationship_type="prerequisite",
        ),
    ]
    kg.add_concepts(concepts)
    kg.add_relationships(relationships)
    return kg


@pytest.fixture
def engine(progress_tracker):
    """Create a RecommendationEngine with only a progress tracker."""
    return RecommendationEngine(progress_tracker=progress_tracker)


@pytest.fixture
def full_engine(progress_tracker, knowledge_graph, scheduler):
    """Create a RecommendationEngine with all components."""
    return RecommendationEngine(
        progress_tracker=progress_tracker,
        knowledge_graph=knowledge_graph,
        scheduler=scheduler,
    )


# ---------------------------------------------------------------------------
# Initialization Tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_with_progress_only(self, progress_tracker):
        engine = RecommendationEngine(progress_tracker=progress_tracker)
        assert engine.progress_tracker is progress_tracker
        assert engine.knowledge_graph is None
        assert engine.scheduler is None

    def test_creates_with_all_components(self, progress_tracker, knowledge_graph, scheduler):
        engine = RecommendationEngine(
            progress_tracker=progress_tracker,
            knowledge_graph=knowledge_graph,
            scheduler=scheduler,
        )
        assert engine.knowledge_graph is knowledge_graph
        assert engine.scheduler is scheduler


# ---------------------------------------------------------------------------
# Study Recommendations Tests
# ---------------------------------------------------------------------------


class TestGetStudyRecommendations:
    def test_empty_state_returns_empty(self, engine):
        recs = engine.get_study_recommendations()
        assert recs == []

    def test_weak_topics_generate_high_priority(self, engine):
        engine.progress_tracker.record_score("Python", 30)
        engine.progress_tracker.record_score("Python", 40)

        recs = engine.get_study_recommendations()
        assert len(recs) >= 1
        python_rec = next(r for r in recs if r["topic"] == "Python")
        assert python_rec["priority"] == 5
        assert python_rec["action"] == "practice"
        assert "35" in python_rec["reason"]  # average score

    def test_due_cards_generate_medium_priority(self, full_engine, scheduler):
        scheduler.add_card("card_1")
        scheduler.add_card("card_2")

        recs = full_engine.get_study_recommendations()
        card_recs = [r for r in recs if r["action"] == "review"]
        assert len(card_recs) == 2
        assert all(r["priority"] == 3 for r in card_recs)

    def test_recommendations_sorted_by_priority(self, full_engine, scheduler):
        # Create a weak topic (priority 5)
        full_engine.progress_tracker.record_score("Algebra", 85)
        full_engine.progress_tracker.record_score("Python", 30)

        # Add due cards (priority 3)
        scheduler.add_card("card_1")

        recs = full_engine.get_study_recommendations()
        priorities = [r["priority"] for r in recs]
        assert priorities == sorted(priorities, reverse=True)

    def test_next_topics_generate_low_priority(self, full_engine):
        # Master Algebra so Calculus becomes suggested
        full_engine.progress_tracker.record_score("Algebra", 90)
        full_engine.progress_tracker.record_score("Algebra", 90)

        recs = full_engine.get_study_recommendations()
        learn_recs = [r for r in recs if r["action"] == "learn"]
        assert len(learn_recs) > 0
        assert all(r["priority"] == 2 for r in learn_recs)

    def test_recommendation_dict_structure(self, engine):
        engine.progress_tracker.record_score("Math", 20)

        recs = engine.get_study_recommendations()
        assert len(recs) >= 1
        rec = recs[0]
        assert "action" in rec
        assert "topic" in rec
        assert "reason" in rec
        assert "priority" in rec
        assert isinstance(rec["priority"], int)
        assert 1 <= rec["priority"] <= 5


# ---------------------------------------------------------------------------
# Suggest Next Topics Tests
# ---------------------------------------------------------------------------


class TestSuggestNextTopics:
    def test_no_graph_returns_empty(self, engine):
        suggestions = engine.suggest_next_topics()
        assert suggestions == []

    def test_all_unstarted_suggests_root_concepts(self, full_engine):
        # Algebra has no prerequisites, so it should be suggested
        suggestions = full_engine.suggest_next_topics()
        assert "Algebra" in suggestions

    def test_mastered_prereq_unlocks_next(self, full_engine):
        # Master Algebra -> Calculus and Linear Algebra become available
        full_engine.progress_tracker.record_score("Algebra", 90)
        full_engine.progress_tracker.record_score("Algebra", 90)

        suggestions = full_engine.suggest_next_topics()
        assert "Calculus" in suggestions
        assert "Linear Algebra" in suggestions

    def test_partial_prereqs_not_suggested(self, full_engine):
        # Only master Calculus, not Linear Algebra
        # Machine Learning requires both -> should NOT be suggested
        full_engine.progress_tracker.record_score("Algebra", 90)
        full_engine.progress_tracker.record_score("Calculus", 90)

        suggestions = full_engine.suggest_next_topics()
        assert "Machine Learning" not in suggestions

    def test_all_prereqs_mastered_unlocks_advanced(self, full_engine):
        # Master all prerequisites for Machine Learning
        full_engine.progress_tracker.record_score("Algebra", 90)
        full_engine.progress_tracker.record_score("Calculus", 90)
        full_engine.progress_tracker.record_score("Linear Algebra", 85)

        suggestions = full_engine.suggest_next_topics()
        assert "Machine Learning" in suggestions

    def test_already_mastered_not_suggested(self, full_engine):
        full_engine.progress_tracker.record_score("Algebra", 95)

        suggestions = full_engine.suggest_next_topics()
        assert "Algebra" not in suggestions

    def test_familiar_topic_not_suggested(self, full_engine):
        # Familiar (60-84%) topics should not be re-suggested
        full_engine.progress_tracker.record_score("Algebra", 70)

        suggestions = full_engine.suggest_next_topics()
        assert "Algebra" not in suggestions


# ---------------------------------------------------------------------------
# Suggest Revision Topics Tests
# ---------------------------------------------------------------------------


class TestSuggestRevisionTopics:
    def test_empty_state_returns_empty(self, engine):
        revisions = engine.suggest_revision_topics()
        assert revisions == []

    def test_recent_topic_not_suggested(self, engine):
        # Record a score just now — should NOT need revision yet
        engine.progress_tracker.record_score("Python", 70)

        revisions = engine.suggest_revision_topics()
        assert "Python" not in revisions

    def test_stale_topic_suggested_for_revision(self, engine):
        # Record a score, then manually set last_attempted to 10 days ago
        engine.progress_tracker.record_score("Python", 70)
        old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        engine.progress_tracker.state.topic_progress["Python"].last_attempted = old_time

        revisions = engine.suggest_revision_topics()
        assert "Python" in revisions

    def test_mastered_topic_stale_after_14_days(self, engine):
        # Mastered topic, but last reviewed 15 days ago
        engine.progress_tracker.record_score("Math", 95)
        old_time = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        engine.progress_tracker.state.topic_progress["Math"].last_attempted = old_time

        revisions = engine.suggest_revision_topics()
        assert "Math" in revisions

    def test_mastered_topic_recent_not_suggested(self, engine):
        # Mastered and recently reviewed — no revision needed
        engine.progress_tracker.record_score("Math", 95)

        revisions = engine.suggest_revision_topics()
        assert "Math" not in revisions

    def test_multiple_stale_topics(self, engine):
        engine.progress_tracker.record_score("Topic A", 65)
        engine.progress_tracker.record_score("Topic B", 50)
        old_time = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        engine.progress_tracker.state.topic_progress["Topic A"].last_attempted = old_time
        engine.progress_tracker.state.topic_progress["Topic B"].last_attempted = old_time

        revisions = engine.suggest_revision_topics()
        assert "Topic A" in revisions
        assert "Topic B" in revisions


# ---------------------------------------------------------------------------
# Daily Plan Tests
# ---------------------------------------------------------------------------


class TestGetDailyPlan:
    def test_empty_state_plan(self, engine):
        plan = engine.get_daily_plan()
        assert plan["review_cards"] == []
        assert plan["weak_topics"] == []
        assert plan["next_topics"] == []
        assert plan["estimated_time_minutes"] == 0

    def test_plan_includes_due_cards(self, full_engine, scheduler):
        scheduler.add_card("card_a")
        scheduler.add_card("card_b")

        plan = full_engine.get_daily_plan()
        assert set(plan["review_cards"]) == {"card_a", "card_b"}

    def test_plan_includes_weak_topics(self, full_engine):
        full_engine.progress_tracker.record_score("Python", 30)

        plan = full_engine.get_daily_plan()
        assert "Python" in plan["weak_topics"]

    def test_plan_includes_next_topics(self, full_engine):
        # No prerequisites mastered yet — Algebra (root) is a next topic
        plan = full_engine.get_daily_plan()
        assert "Algebra" in plan["next_topics"]

    def test_time_estimation(self, full_engine, scheduler):
        # 2 cards * 2 min + 1 weak topic * 15 min + next topics * 20 min
        scheduler.add_card("card_1")
        scheduler.add_card("card_2")
        full_engine.progress_tracker.record_score("Python", 30)

        plan = full_engine.get_daily_plan()
        # 2*2 + 1*15 + next_topics*20
        expected_card_time = 2 * 2
        expected_weak_time = 1 * 15
        expected_next_time = len(plan["next_topics"]) * 20
        assert plan["estimated_time_minutes"] == (
            expected_card_time + expected_weak_time + expected_next_time
        )

    def test_plan_structure(self, engine):
        plan = engine.get_daily_plan()
        assert "review_cards" in plan
        assert "weak_topics" in plan
        assert "next_topics" in plan
        assert "estimated_time_minutes" in plan
        assert isinstance(plan["estimated_time_minutes"], int)


# ---------------------------------------------------------------------------
# Integration: Various Learning States
# ---------------------------------------------------------------------------


class TestVariousLearningStates:
    def test_beginner_state(self, full_engine):
        """No progress at all — should suggest root topics."""
        recs = full_engine.get_study_recommendations()
        # Only learn recommendations (root concepts with no prereqs)
        assert all(r["action"] == "learn" for r in recs)

    def test_intermediate_state(self, full_engine, scheduler):
        """Some topics mastered, some weak, some cards due."""
        full_engine.progress_tracker.record_score("Algebra", 90)
        full_engine.progress_tracker.record_score("Calculus", 40)
        scheduler.add_card("flashcard_1")

        recs = full_engine.get_study_recommendations()
        actions = {r["action"] for r in recs}
        assert "practice" in actions  # Calculus is weak
        assert "review" in actions  # flashcard due
        assert "learn" in actions  # Linear Algebra unlocked

    def test_advanced_state(self, full_engine):
        """Most topics mastered — fewer recommendations."""
        full_engine.progress_tracker.record_score("Algebra", 95)
        full_engine.progress_tracker.record_score("Calculus", 90)
        full_engine.progress_tracker.record_score("Linear Algebra", 88)

        recs = full_engine.get_study_recommendations()
        # Machine Learning should now be suggested
        learn_recs = [r for r in recs if r["action"] == "learn"]
        topics = [r["topic"] for r in learn_recs]
        assert "Machine Learning" in topics

    def test_struggling_state(self, full_engine):
        """Multiple weak topics — all get high priority."""
        full_engine.progress_tracker.record_score("Algebra", 30)
        full_engine.progress_tracker.record_score("Calculus", 25)
        full_engine.progress_tracker.record_score("Linear Algebra", 40)

        recs = full_engine.get_study_recommendations()
        practice_recs = [r for r in recs if r["action"] == "practice"]
        assert len(practice_recs) == 3
        assert all(r["priority"] == 5 for r in practice_recs)
