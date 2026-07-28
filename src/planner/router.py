"""NeuroForge — Intent Router.

Classifies natural language user inputs into intents and extracts parameters,
then routes to the appropriate workflow.

Supports two classification modes:
- Rule-based (keyword matching) — fast fallback, no LLM call needed
- LLM-based — handles complex or ambiguous inputs

Supported intents:
- quiz: Generate quiz questions
- flashcard: Generate flashcards
- notes: Generate revision notes
- explain: Explain a concept (routes to chat)
- solution: Generate a detailed solution with marks-based depth
- mind_map: Generate a mind/concept map
- additional_info: Real-world applications, interview questions, common mistakes
- chat: General conversational tutor (default)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from pydantic import BaseModel

from src.llm import LLMClient

logger = logging.getLogger("neuroforge.planner")


# ---------------------------------------------------------------------------
# Intent Classification Result Model
# ---------------------------------------------------------------------------


class IntentResult(BaseModel):
    """Structured result from intent classification."""

    intent: str
    parameters: dict[str, Any]


# ---------------------------------------------------------------------------
# Keyword patterns for rule-based classification
# ---------------------------------------------------------------------------

# Each entry: (list of keyword patterns, intent label)
INTENT_KEYWORDS: list[tuple[list[str], str]] = [
    # More specific intents first (to avoid false matches with generic words)
    (["mind map", "mindmap", "concept map", "diagram", "visual map"], "mind_map"),
    (["solution", "solve", "mark question"], "solution"),
    (
        ["application", "industry", "interview", "mistake", "real world", "real-world"],
        "additional_info",
    ),
    (["flashcard", "flash card", "memory card"], "flashcard"),
    (["notes", "revision", "summary", "summarize", "summarise"], "notes"),
    (["quiz", "test", "exam"], "quiz"),
    (["explain", "what is", "define", "definition", "tell me about", "describe"], "explain"),
]

# Patterns that require more nuanced detection (checked after keyword scan)
# "marks" → solution, but "questions"/"question" → quiz (only if no other intent matched)
SECONDARY_KEYWORDS: list[tuple[list[str], str]] = [
    (["marks", "answer"], "solution"),
    (["questions", "question"], "quiz"),
    (["card", "cards"], "flashcard"),
]

# Difficulty keywords
DIFFICULTY_KEYWORDS = ["easy", "medium", "hard", "difficult", "simple", "basic", "advanced"]

# Difficulty normalization
DIFFICULTY_MAP = {
    "easy": "easy",
    "simple": "easy",
    "basic": "easy",
    "medium": "medium",
    "hard": "hard",
    "difficult": "hard",
    "advanced": "hard",
}

# Pattern for extracting count (e.g., "5 questions", "10 cards", "5 easy questions")
COUNT_PATTERN = re.compile(
    r"(\d+)\s+(?:\w+\s+)*?(?:questions?|cards?|flashcards?|items?|problems?|quizzes?)",
    re.IGNORECASE,
)

# Simpler pattern: just a number followed directly by a unit word
COUNT_PATTERN_SIMPLE = re.compile(
    r"(\d+)\s*(?:questions?|cards?|flashcards?|items?|problems?|quizzes?)", re.IGNORECASE
)

# Pattern for extracting marks (e.g., "5 marks", "10-mark")
MARKS_PATTERN = re.compile(r"(\d+)[\s-]*marks?", re.IGNORECASE)


# ---------------------------------------------------------------------------
# LLM Classification Prompt
# ---------------------------------------------------------------------------

CLASSIFICATION_SYSTEM_PROMPT = """\
You are an intent classifier for an educational AI assistant called NeuroForge.
Given a user's natural language input, classify their intent and extract parameters.

Possible intents:
- "quiz" — user wants quiz questions (MCQ, short answer, true/false)
- "flashcard" — user wants flashcards for memorization
- "notes" — user wants revision notes or summaries
- "explain" — user wants a concept explained
- "solution" — user wants a detailed solution/answer to a question (often with marks)
- "mind_map" — user wants a visual concept map or mind map
- "additional_info" — user wants real-world applications, interview questions, or common mistakes
- "chat" — general conversation or unclear intent

Extract these parameters if mentioned:
- topic: the main subject/concept mentioned (string)
- difficulty: "easy", "medium", or "hard" if mentioned
- count: number of items requested (integer)
- marks: marks allocation if mentioned (integer)

Respond with ONLY valid JSON.
"""


# ---------------------------------------------------------------------------
# IntentRouter Class
# ---------------------------------------------------------------------------


class IntentRouter:
    """Routes natural language inputs to appropriate workflows.

    Supports both LLM-based and rule-based intent classification.

    Usage:
        from src.planner import IntentRouter
        from src.llm import LLMClient

        router = IntentRouter(llm_client=LLMClient())
        result = router.classify_intent("Generate 5 easy quiz questions on photosynthesis")
        # {'intent': 'quiz', 'parameters': {'topic': 'photosynthesis', 'difficulty': 'easy', 'count': 5}}
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize the IntentRouter.

        Args:
            llm_client: LLMClient instance for LLM-based classification.
        """
        self.llm_client = llm_client

    def classify_intent(self, user_input: str) -> dict[str, Any]:
        """Classify user intent using rule-based matching first, LLM as fallback.

        For simple inputs with clear keywords, uses fast rule-based matching.
        For ambiguous inputs, falls back to LLM classification.

        Args:
            user_input: Natural language input from the user.

        Returns:
            Dict with 'intent' (str) and 'parameters' (dict).
        """
        # Try rule-based first — it's fast and handles clear cases
        result = self.classify_intent_rules(user_input)

        # If rule-based returns "chat" (default), try LLM for better classification
        if result["intent"] == "chat":
            try:
                llm_result = self.classify_intent_llm(user_input)
                if llm_result["intent"] != "chat":
                    return llm_result
            except Exception as e:
                logger.warning(f"LLM classification failed, using rule-based result: {e}")

        return result

    def classify_intent_rules(self, user_input: str) -> dict[str, Any]:
        """Classify intent using rule-based keyword matching.

        Fast fallback that doesn't require an LLM call.

        Args:
            user_input: Natural language input from the user.

        Returns:
            Dict with 'intent' (str) and 'parameters' (dict).
        """
        text = user_input.lower().strip()
        intent = "chat"  # Default

        # First pass: check primary keyword patterns (specific intents)
        for keywords, label in INTENT_KEYWORDS:
            for keyword in keywords:
                if keyword in text:
                    intent = label
                    break
            if intent != "chat":
                break

        # Second pass: if still "chat", check secondary (more generic) keywords
        if intent == "chat":
            for keywords, label in SECONDARY_KEYWORDS:
                for keyword in keywords:
                    if keyword in text:
                        intent = label
                        break
                if intent != "chat":
                    break

        # Extract parameters
        parameters = self._extract_parameters(user_input)

        return {"intent": intent, "parameters": parameters}

    def classify_intent_llm(self, user_input: str) -> dict[str, Any]:
        """Classify intent using LLM for complex or ambiguous inputs.

        Args:
            user_input: Natural language input from the user.

        Returns:
            Dict with 'intent' (str) and 'parameters' (dict).

        Raises:
            Exception: If LLM call fails.
        """
        result, _usage = self.llm_client.generate_json(
            prompt=f"Classify this user input:\n\n\"{user_input}\"",
            response_model=IntentResult,
            system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
            temperature=0.1,
        )

        # Validate the intent is in our expected set
        valid_intents = {
            "quiz", "flashcard", "notes", "explain",
            "solution", "mind_map", "additional_info", "chat",
        }
        intent = result.intent if result.intent in valid_intents else "chat"

        return {"intent": intent, "parameters": result.parameters}

    def route(self, user_input: str, workflows: dict[str, Any]) -> Any:
        """Classify intent and dispatch to the appropriate workflow.

        Args:
            user_input: Natural language input from the user.
            workflows: Dict mapping intent names to workflow callables/objects.
                       Each workflow should accept (topic, **parameters).

        Returns:
            Result from the dispatched workflow, or None if no matching workflow.
        """
        classification = self.classify_intent(user_input)
        intent = classification["intent"]
        parameters = classification["parameters"]

        # Map "explain" intent to "chat" workflow
        effective_intent = "chat" if intent == "explain" else intent

        workflow = workflows.get(effective_intent)
        if workflow is None:
            logger.warning(
                f"No workflow registered for intent '{effective_intent}'. "
                f"Available: {list(workflows.keys())}"
            )
            return None

        topic = parameters.get("topic", user_input)

        # Build kwargs for the workflow from parameters
        kwargs: dict[str, Any] = {}
        if parameters.get("difficulty"):
            kwargs["difficulty"] = parameters["difficulty"]
        if parameters.get("count"):
            kwargs["num_questions"] = parameters["count"]
        if parameters.get("marks"):
            kwargs["marks"] = parameters["marks"]

        logger.info(
            f"Routing to '{effective_intent}' workflow | "
            f"topic='{topic}' | params={kwargs}"
        )

        # Call the workflow — assume it has a `generate` method or is callable
        if hasattr(workflow, "generate"):
            return workflow.generate(topic=topic, **kwargs)
        elif callable(workflow):
            return workflow(topic=topic, **kwargs)
        else:
            logger.error(f"Workflow '{effective_intent}' is not callable and has no generate method.")
            return None

    # -----------------------------------------------------------------------
    # Private Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _extract_parameters(user_input: str) -> dict[str, Any]:
        """Extract parameters (topic, difficulty, count, marks) from input.

        Args:
            user_input: The raw user input string.

        Returns:
            Dict of extracted parameters.
        """
        text = user_input.lower().strip()
        parameters: dict[str, Any] = {}

        # Extract difficulty
        for word in DIFFICULTY_KEYWORDS:
            if word in text:
                parameters["difficulty"] = DIFFICULTY_MAP[word]
                break

        # Extract count (try flexible pattern first, then simple)
        count_match = COUNT_PATTERN.search(user_input) or COUNT_PATTERN_SIMPLE.search(user_input)
        if count_match:
            parameters["count"] = int(count_match.group(1))

        # Extract marks
        marks_match = MARKS_PATTERN.search(user_input)
        if marks_match:
            parameters["marks"] = int(marks_match.group(1))

        # Extract topic — remove known intent keywords and parameters to isolate topic
        topic = _extract_topic(user_input)
        if topic:
            parameters["topic"] = topic

        return parameters


# ---------------------------------------------------------------------------
# Topic extraction helper
# ---------------------------------------------------------------------------

# Words to strip when extracting the topic
_STOP_WORDS = {
    "generate", "create", "make", "give", "me", "i", "want", "need", "please",
    "can", "you", "some", "a", "an", "the", "on", "about", "for", "of", "in",
    "with", "and", "or", "to", "from", "my", "do", "how", "what", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "having",
    "quiz", "test", "exam", "questions", "question", "flashcard", "flashcards",
    "card", "cards", "notes", "revision", "summary", "explain", "define",
    "definition", "solution", "answer", "solve", "mind", "map", "concept",
    "diagram", "application", "industry", "interview", "mistake", "real",
    "world", "easy", "medium", "hard", "difficult", "simple", "basic",
    "advanced", "marks", "mark", "items", "problems", "problem",
}

# Pattern to strip numbers with unit words (e.g., "5 questions")
_NUM_UNIT_PATTERN = re.compile(
    r"\d+\s*(?:questions?|cards?|flashcards?|items?|problems?|marks?|quizzes?)", re.IGNORECASE
)


def _extract_topic(user_input: str) -> str:
    """Extract the main topic from user input by removing noise words.

    Heuristic approach: strip known stop words, intent keywords, and
    parameter patterns to isolate the subject noun phrase.

    Args:
        user_input: Raw user input.

    Returns:
        Extracted topic string, or empty string if not identifiable.
    """
    text = user_input.strip()

    # Remove number+unit patterns ("5 questions", "10 marks")
    text = _NUM_UNIT_PATTERN.sub("", text)

    # Remove punctuation except hyphens (preserve compound words)
    text = re.sub(r"[^\w\s-]", "", text)

    # Split and filter stop words
    words = text.split()
    topic_words = [w for w in words if w.lower() not in _STOP_WORDS]

    # Rejoin and clean up extra whitespace
    topic = " ".join(topic_words).strip()

    return topic
