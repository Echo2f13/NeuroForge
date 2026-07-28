"""NeuroForge — Multi-Agent System.

Provides a set of thin-wrapper agents coordinated by a sequential orchestrator.
Each agent encapsulates a specific responsibility:

- PlannerAgent: Routes user intent (wraps IntentRouter)
- DocumentAgent: Handles ingestion and knowledge extraction
- TeacherAgent: Explains concepts, generates notes (wraps ChatTutor + RevisionNotesWorkflow)
- ExaminerAgent: Creates quizzes and assessments (wraps QuizWorkflow + FlashcardWorkflow)
- ReviewerAgent: Validates output quality (basic checks)
- MemoryAgent: Updates learning progress (wraps ProgressTracker + SpacedRepetitionScheduler)

The MultiAgentOrchestrator coordinates these agents in a sequential pipeline:
  PlannerAgent → Route to agent → ReviewerAgent → MemoryAgent → Return result
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.llm import LLMClient
from src.memory.progress import ProgressTracker
from src.memory.spaced_repetition import SpacedRepetitionScheduler
from src.planner.router import IntentRouter
from src.retrieval.retriever import Retriever
from src.store.knowledge_graph import KnowledgeGraph
from src.workflows.chat_tutor import ChatTutor
from src.workflows.flashcards import FlashcardWorkflow
from src.workflows.quiz import QuizWorkflow
from src.workflows.revision_notes import RevisionNotesWorkflow

logger = logging.getLogger("neuroforge.agents")


# ---------------------------------------------------------------------------
# Agent Base
# ---------------------------------------------------------------------------


class BaseAgent:
    """Base class for all agents. Defines the run interface."""

    name: str = "base"

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's task.

        Args:
            input: Dict with agent-specific input data.

        Returns:
            Dict with agent-specific output data.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# PlannerAgent
# ---------------------------------------------------------------------------


class PlannerAgent(BaseAgent):
    """Routes user intent using the IntentRouter.

    Wraps IntentRouter.classify_intent to determine what the user wants.

    Args:
        llm_client: LLMClient instance for LLM-based classification fallback.
    """

    name = "planner"

    def __init__(self, llm_client: LLMClient) -> None:
        self.router = IntentRouter(llm_client=llm_client)

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Classify user intent.

        Args:
            input: Dict with key "user_input" (str).

        Returns:
            Dict with "intent" (str) and "parameters" (dict).
        """
        user_input = input.get("user_input", "")
        result = self.router.classify_intent(user_input)
        return {
            "intent": result["intent"],
            "parameters": result.get("parameters", {}),
        }


# ---------------------------------------------------------------------------
# DocumentAgent
# ---------------------------------------------------------------------------


class DocumentAgent(BaseAgent):
    """Handles document ingestion and knowledge extraction.

    Wraps the ingest pipeline and extraction modules to process
    documents into the knowledge base.

    Args:
        retriever: Retriever instance for storing/querying chunks.
        knowledge_graph: KnowledgeGraph instance for concept storage.
    """

    name = "document"

    def __init__(self, retriever: Retriever, knowledge_graph: KnowledgeGraph) -> None:
        self.retriever = retriever
        self.knowledge_graph = knowledge_graph

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Process a document ingestion request.

        Args:
            input: Dict with optional keys:
                - "file_path" (str): Path to document to ingest.
                - "text" (str): Raw text to process.
                - "topic" (str): Topic for knowledge retrieval.

        Returns:
            Dict with "status" (str) and "message" (str).
        """
        file_path = input.get("file_path")
        text = input.get("text")
        topic = input.get("topic")

        if file_path:
            try:
                from src.ingestion import ingest

                result = ingest(file_path)
                return {
                    "status": "success",
                    "message": f"Ingested document: {file_path}",
                    "chunks": len(result) if isinstance(result, list) else 1,
                }
            except Exception as e:
                return {"status": "error", "message": f"Ingestion failed: {e}"}

        if topic:
            # Retrieve existing knowledge for a topic
            try:
                chunks = self.retriever.semantic_search(query=topic, top_k=5)
                return {
                    "status": "success",
                    "message": f"Retrieved {len(chunks)} chunks for '{topic}'",
                    "chunks": len(chunks),
                }
            except Exception as e:
                return {"status": "error", "message": f"Retrieval failed: {e}"}

        if text:
            return {
                "status": "success",
                "message": f"Received text ({len(text)} chars) for processing",
                "chunks": 1,
            }

        return {"status": "no_op", "message": "No file_path, text, or topic provided"}


# ---------------------------------------------------------------------------
# TeacherAgent
# ---------------------------------------------------------------------------


class TeacherAgent(BaseAgent):
    """Explains concepts and generates revision notes.

    Wraps ChatTutor (for explanations) and RevisionNotesWorkflow
    (for structured notes generation).

    Args:
        llm_client: LLMClient for generation.
        retriever: Retriever for knowledge base access.
    """

    name = "teacher"

    def __init__(self, llm_client: LLMClient, retriever: Retriever) -> None:
        self.chat_tutor = ChatTutor(retriever=retriever, llm_client=llm_client)
        self.notes_workflow = RevisionNotesWorkflow(
            retriever=retriever, llm_client=llm_client
        )

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Explain a concept or generate revision notes.

        Args:
            input: Dict with keys:
                - "topic" (str): The topic to explain or generate notes for.
                - "action" (str): "explain" or "notes". Defaults to "explain".

        Returns:
            Dict with "result" containing the explanation or notes.
        """
        topic = input.get("topic", "")
        action = input.get("action", "explain")

        if action == "notes":
            try:
                notes = self.notes_workflow.generate(topic=topic)
                return {
                    "status": "success",
                    "action": "notes",
                    "result": notes.model_dump() if hasattr(notes, "model_dump") else str(notes),
                }
            except Exception as e:
                logger.error(f"TeacherAgent notes generation failed: {e}")
                return {"status": "error", "action": "notes", "result": str(e)}
        else:
            # Default: explain via chat tutor
            try:
                response = self.chat_tutor.ask(topic)
                return {
                    "status": "success",
                    "action": "explain",
                    "result": response,
                }
            except Exception as e:
                logger.error(f"TeacherAgent explanation failed: {e}")
                return {"status": "error", "action": "explain", "result": str(e)}


# ---------------------------------------------------------------------------
# ExaminerAgent
# ---------------------------------------------------------------------------


class ExaminerAgent(BaseAgent):
    """Creates quizzes and flashcard assessments.

    Wraps QuizWorkflow and FlashcardWorkflow to generate
    assessment materials.

    Args:
        llm_client: LLMClient for generation.
        retriever: Retriever for knowledge base access.
    """

    name = "examiner"

    def __init__(self, llm_client: LLMClient, retriever: Retriever) -> None:
        self.quiz_workflow = QuizWorkflow(llm_client=llm_client, retriever=retriever)
        self.flashcard_workflow = FlashcardWorkflow(
            retriever=retriever, llm_client=llm_client
        )

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Generate quiz questions or flashcards.

        Args:
            input: Dict with keys:
                - "topic" (str): Topic for assessment generation.
                - "action" (str): "quiz" or "flashcard". Defaults to "quiz".
                - "difficulty" (str, optional): easy/medium/hard.
                - "count" (int, optional): Number of items to generate.

        Returns:
            Dict with "result" containing generated items.
        """
        topic = input.get("topic", "")
        action = input.get("action", "quiz")
        difficulty = input.get("difficulty")
        count = input.get("count", 5)

        if action == "flashcard":
            try:
                cards = self.flashcard_workflow.generate(
                    topic=topic, difficulty=difficulty, num_cards=count
                )
                return {
                    "status": "success",
                    "action": "flashcard",
                    "result": [c.model_dump() for c in cards],
                    "count": len(cards),
                }
            except Exception as e:
                logger.error(f"ExaminerAgent flashcard generation failed: {e}")
                return {"status": "error", "action": "flashcard", "result": str(e)}
        else:
            # Default: quiz
            try:
                questions = self.quiz_workflow.generate(
                    topic=topic, difficulty=difficulty, num_questions=count
                )
                return {
                    "status": "success",
                    "action": "quiz",
                    "result": [q.model_dump() for q in questions],
                    "count": len(questions),
                }
            except Exception as e:
                logger.error(f"ExaminerAgent quiz generation failed: {e}")
                return {"status": "error", "action": "quiz", "result": str(e)}


# ---------------------------------------------------------------------------
# ReviewerAgent
# ---------------------------------------------------------------------------


class ReviewerAgent(BaseAgent):
    """Validates output quality with basic checks.

    Performs simple quality validation:
    - Non-empty output
    - Correct format (dict/list as expected)
    - Minimum content length
    """

    name = "reviewer"

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Validate the quality of agent output.

        Args:
            input: Dict with keys:
                - "result" (Any): The output to validate.
                - "intent" (str): The original intent (for format expectations).

        Returns:
            Dict with "passed" (bool) and "issues" (list[str]).
        """
        result = input.get("result")
        intent = input.get("intent", "")

        issues: list[str] = []

        # Check 1: Non-empty
        if result is None:
            issues.append("Result is None")
        elif isinstance(result, str) and len(result.strip()) == 0:
            issues.append("Result is an empty string")
        elif isinstance(result, (list, dict)) and len(result) == 0:
            issues.append("Result is an empty collection")

        # Check 2: For quiz/flashcard intents, expect a list result
        if intent in ("quiz", "flashcard"):
            actual_result = result
            # If result is a dict with a "result" key, unwrap it
            if isinstance(result, dict) and "result" in result:
                actual_result = result["result"]
            if isinstance(actual_result, list) and len(actual_result) == 0:
                issues.append(f"Expected non-empty list for {intent} intent")

        # Check 3: For explain/notes intents, check minimum content
        if intent in ("explain", "notes", "chat"):
            content = result
            if isinstance(result, dict):
                content = result.get("result", result.get("answer", ""))
                if isinstance(content, dict):
                    content = str(content)
            if isinstance(content, str) and len(content) < 10:
                issues.append("Response too short (less than 10 characters)")

        passed = len(issues) == 0
        return {"passed": passed, "issues": issues}


# ---------------------------------------------------------------------------
# MemoryAgent
# ---------------------------------------------------------------------------


class MemoryAgent(BaseAgent):
    """Updates learning progress and spaced repetition state.

    Wraps ProgressTracker and SpacedRepetitionScheduler to record
    quiz results and schedule reviews.

    Args:
        progress_tracker: ProgressTracker instance.
        scheduler: SpacedRepetitionScheduler instance.
    """

    name = "memory"

    def __init__(
        self,
        progress_tracker: ProgressTracker,
        scheduler: SpacedRepetitionScheduler,
    ) -> None:
        self.progress_tracker = progress_tracker
        self.scheduler = scheduler

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Update learning progress based on completed activity.

        Args:
            input: Dict with keys:
                - "intent" (str): The activity type (quiz, flashcard, etc.)
                - "topic" (str): Topic that was studied.
                - "score" (float, optional): Quiz score (0-100) if applicable.
                - "card_id" (str, optional): Card ID for spaced repetition.
                - "quality" (int, optional): Review quality (0-5) for SR.

        Returns:
            Dict with "updated" (bool) and progress info.
        """
        intent = input.get("intent", "")
        topic = input.get("topic", "")
        score = input.get("score")
        card_id = input.get("card_id")
        quality = input.get("quality")

        updated = False

        # Record quiz score if provided
        if score is not None and topic:
            try:
                self.progress_tracker.record_score(topic, score)
                updated = True
            except Exception as e:
                logger.warning(f"Failed to record score: {e}")

        # Update spaced repetition if card review data provided
        if card_id and quality is not None:
            try:
                self.scheduler.review_card(card_id, quality)
                updated = True
            except Exception as e:
                logger.warning(f"Failed to update spaced repetition: {e}")

        # Get current progress info
        mastery = self.progress_tracker.get_mastery_level(topic) if topic else "unknown"
        stats = self.progress_tracker.get_overall_stats()

        return {
            "updated": updated,
            "topic": topic,
            "mastery_level": mastery,
            "overall_stats": stats,
        }


# ---------------------------------------------------------------------------
# MultiAgentOrchestrator
# ---------------------------------------------------------------------------

# Mapping from intent to agent action config
_INTENT_TO_AGENT: dict[str, tuple[str, str]] = {
    "quiz": ("examiner", "quiz"),
    "flashcard": ("examiner", "flashcard"),
    "notes": ("teacher", "notes"),
    "explain": ("teacher", "explain"),
    "chat": ("teacher", "explain"),
    "solution": ("teacher", "explain"),
    "mind_map": ("teacher", "notes"),
    "additional_info": ("teacher", "explain"),
}


class MultiAgentOrchestrator:
    """Coordinates multiple agents in a sequential pipeline.

    Pipeline:
    1. PlannerAgent classifies user intent
    2. Routes to appropriate agent (DocumentAgent, TeacherAgent, ExaminerAgent)
    3. ReviewerAgent validates output quality
    4. MemoryAgent updates progress if applicable
    5. Returns result dict with {intent, result, quality_check}

    Args:
        llm_client: LLMClient instance.
        retriever: Retriever instance.
        knowledge_graph: KnowledgeGraph instance.
        progress_tracker: ProgressTracker instance.
        scheduler: SpacedRepetitionScheduler instance.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        retriever: Retriever,
        knowledge_graph: KnowledgeGraph,
        progress_tracker: ProgressTracker,
        scheduler: SpacedRepetitionScheduler,
    ) -> None:
        self.planner = PlannerAgent(llm_client=llm_client)
        self.document = DocumentAgent(retriever=retriever, knowledge_graph=knowledge_graph)
        self.teacher = TeacherAgent(llm_client=llm_client, retriever=retriever)
        self.examiner = ExaminerAgent(llm_client=llm_client, retriever=retriever)
        self.reviewer = ReviewerAgent()
        self.memory = MemoryAgent(
            progress_tracker=progress_tracker, scheduler=scheduler
        )

    def process(self, user_input: str) -> dict[str, Any]:
        """Process a user request through the full agent pipeline.

        Steps:
        1. Classify intent via PlannerAgent
        2. Route to the appropriate domain agent
        3. Validate output via ReviewerAgent
        4. Update progress via MemoryAgent (for quiz/flashcard intents)
        5. Return combined result

        Args:
            user_input: Natural language input from the user.

        Returns:
            Dict with keys:
                - "intent" (str): Classified intent.
                - "parameters" (dict): Extracted parameters.
                - "result" (Any): Agent output.
                - "quality_check" (dict): Reviewer validation result.
                - "memory_update" (dict, optional): Progress update info.
        """
        # Step 1: Classify intent
        plan = self.planner.run({"user_input": user_input})
        intent = plan["intent"]
        parameters = plan["parameters"]
        topic = parameters.get("topic", user_input)

        logger.info(f"Orchestrator: intent={intent}, topic={topic}")

        # Step 2: Route to appropriate agent
        agent_result = self._route(intent, parameters, topic)

        # Step 3: Review output quality
        quality_check = self.reviewer.run({"result": agent_result, "intent": intent})

        # Step 4: Update memory if applicable
        memory_update = None
        if intent in ("quiz", "flashcard"):
            memory_update = self.memory.run({
                "intent": intent,
                "topic": topic,
            })

        return {
            "intent": intent,
            "parameters": parameters,
            "result": agent_result,
            "quality_check": quality_check,
            "memory_update": memory_update,
        }

    def _route(
        self, intent: str, parameters: dict[str, Any], topic: str
    ) -> dict[str, Any]:
        """Route to the appropriate domain agent based on intent.

        Args:
            intent: Classified intent string.
            parameters: Extracted parameters.
            topic: The topic extracted from user input.

        Returns:
            Agent output dict.
        """
        agent_key, action = _INTENT_TO_AGENT.get(intent, ("teacher", "explain"))

        input_data: dict[str, Any] = {
            "topic": topic,
            "action": action,
        }

        # Pass through relevant parameters
        if parameters.get("difficulty"):
            input_data["difficulty"] = parameters["difficulty"]
        if parameters.get("count"):
            input_data["count"] = parameters["count"]

        if agent_key == "examiner":
            return self.examiner.run(input_data)
        elif agent_key == "teacher":
            return self.teacher.run(input_data)
        elif agent_key == "document":
            return self.document.run(input_data)
        else:
            return self.teacher.run(input_data)
