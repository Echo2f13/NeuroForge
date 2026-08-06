"""Quiz Generation Workflow for NeuroForge.

Implements a sequential pipeline: retrieve → generate → validate → format.
Produces quiz questions (MCQ, short_answer, true_false) from retrieved
knowledge chunks using an LLM.

Enhanced with expert-level prompts for maximum quality output.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from pydantic import BaseModel

from models.knowledge import Difficulty
from models.output import QuizQuestion
from src.llm import LLMClient
from src.retrieval.retriever import Retriever
from src.prompts.enhanced import QUIZ_SYSTEM_PROMPT, QUIZ_USER_PROMPT_TEMPLATE

logger = logging.getLogger("neuroforge.workflows.quiz")


# ---------------------------------------------------------------------------
# Internal model for LLM batch response parsing
# ---------------------------------------------------------------------------


class _QuizBatch(BaseModel):
    """Batch of quiz questions returned by the LLM."""

    questions: list[dict]


# ---------------------------------------------------------------------------
# Quiz Workflow
# ---------------------------------------------------------------------------

# Default question types when none specified
DEFAULT_QUESTION_TYPES = ["mcq", "short_answer", "true_false"]


class QuizWorkflow:
    """Quiz generation workflow: retrieve → generate → validate → format.

    Orchestrates the Retriever and LLMClient to produce validated
    QuizQuestion objects for a given topic.

    Args:
        llm_client: Initialized LLMClient instance.
        retriever: Initialized Retriever instance.
    """

    def __init__(self, llm_client: LLMClient, retriever: Retriever) -> None:
        self.llm_client = llm_client
        self.retriever = retriever

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        topic: str,
        difficulty: Optional[str] = None,
        num_questions: int = 10,
        question_types: Optional[list[str]] = None,
    ) -> list[QuizQuestion]:
        """Generate quiz questions for a topic.

        Pipeline stages:
        1. Retrieve — fetch relevant chunks/concepts from the knowledge base.
        2. Generate — prompt the LLM to create questions from context.
        3. Validate — parse and validate each question with Pydantic.
        4. Format — return validated QuizQuestion objects.

        Args:
            topic: The topic to generate questions about.
            difficulty: Optional difficulty filter (easy, medium, hard).
            num_questions: Number of questions to generate (default 10).
            question_types: Types to include (mcq, short_answer, true_false).
                           Defaults to all three types.

        Returns:
            List of validated QuizQuestion objects.
        """
        types = question_types or DEFAULT_QUESTION_TYPES
        self._validate_question_types(types)

        if difficulty:
            # Validate difficulty value
            Difficulty(difficulty)

        # Stage 1: Retrieve
        logger.info(f"Retrieving context for topic='{topic}', difficulty={difficulty}")
        chunks = self._retrieve(topic, difficulty)

        # Stage 2: Generate
        logger.info(f"Generating {num_questions} questions (types={types})")
        raw_questions = self._generate(
            topic=topic,
            difficulty=difficulty,
            num_questions=num_questions,
            question_types=types,
            chunks=chunks,
        )

        # Stage 3: Validate
        logger.info(f"Validating {len(raw_questions)} raw questions")
        validated = self._validate(raw_questions, topic, difficulty)

        # Stage 4: Format (trim to requested count)
        result = validated[:num_questions]
        logger.info(f"Returning {len(result)} validated questions")
        return result

    # ------------------------------------------------------------------
    # Pipeline Stages
    # ------------------------------------------------------------------

    def _retrieve(self, topic: str, difficulty: Optional[str]) -> list[dict]:
        """Stage 1: Retrieve relevant chunks from the knowledge base.

        Uses filtered_search if difficulty is provided, otherwise
        falls back to semantic_search.
        """
        try:
            if difficulty:
                chunks = self.retriever.filtered_search(
                    query=topic, top_k=10, topic=topic, difficulty=difficulty
                )
            else:
                chunks = self.retriever.semantic_search(query=topic, top_k=10)
        except Exception as e:
            logger.warning(f"Retrieval failed: {e}. Proceeding with empty context.")
            chunks = []

        return chunks

    def _generate(
        self,
        topic: str,
        difficulty: Optional[str],
        num_questions: int,
        question_types: list[str],
        chunks: list[dict],
    ) -> list[dict]:
        """Stage 2: Use LLM to generate quiz questions from context.

        Uses enhanced prompts for maximum quality output.
        """
        # Build context from chunks
        if chunks:
            context_parts = []
            for chunk in chunks[:12]:  # More context for better questions
                content = chunk.get("content", "")
                if content:
                    context_parts.append(content)
            context_text = "\n\n---\n\n".join(context_parts)
        else:
            context_text = f"General knowledge about: {topic}"

        # Format question types for prompt
        type_str = ", ".join(question_types)
        
        # Build the enhanced prompt
        prompt = QUIZ_USER_PROMPT_TEMPLATE.format(
            num_questions=num_questions,
            topic=topic,
            difficulty=difficulty or "medium",
            question_types=type_str,
            context=context_text,
        )

        try:
            result, _usage = self.llm_client.generate_json(
                prompt=prompt,
                response_model=_QuizBatch,
                system_prompt=QUIZ_SYSTEM_PROMPT,
                temperature=0.6,  # Slightly lower for more consistent quality
                max_tokens=4096,  # More tokens for detailed explanations
            )
            return result.questions
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return []

    def _validate(
        self,
        raw_questions: list[dict],
        topic: str,
        difficulty: Optional[str],
    ) -> list[QuizQuestion]:
        """Stage 3: Validate raw question dicts against the QuizQuestion model.

        Skips invalid questions and logs warnings for each.
        """
        validated: list[QuizQuestion] = []

        for i, raw in enumerate(raw_questions):
            try:
                # Ensure required fields have defaults
                if "id" not in raw or not raw["id"]:
                    raw["id"] = f"q-{uuid.uuid4().hex[:8]}"
                if "topic" not in raw or not raw["topic"]:
                    raw["topic"] = topic
                if "difficulty" not in raw or not raw["difficulty"]:
                    raw["difficulty"] = difficulty or "medium"
                if "source_chunk_ids" not in raw:
                    raw["source_chunk_ids"] = []

                question = QuizQuestion.model_validate(raw)
                validated.append(question)
            except Exception as e:
                logger.warning(f"Question {i} validation failed: {e}")

        return validated

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_question_types(types: list[str]) -> None:
        """Raise ValueError if any question type is invalid."""
        allowed = {"mcq", "short_answer", "true_false"}
        for t in types:
            if t not in allowed:
                raise ValueError(
                    f"Invalid question type '{t}'. Allowed: {sorted(allowed)}"
                )

    @staticmethod
    def _build_prompt(
        topic: str,
        difficulty: Optional[str],
        num_questions: int,
        question_types: list[str],
        chunks: list[dict],
    ) -> str:
        """Build the generation prompt including context and instructions."""
        # Format context from chunks
        if chunks:
            context_parts = []
            for chunk in chunks[:10]:  # Limit context size
                content = chunk.get("content", "")
                if content:
                    context_parts.append(content)
            context_text = "\n---\n".join(context_parts)
        else:
            context_text = f"General knowledge about: {topic}"

        # Build type-specific instructions
        type_instructions = []
        if "mcq" in question_types:
            type_instructions.append(
                "- MCQ (question_type='mcq'): Provide exactly 4 options. "
                "The correct_answer must be one of the options."
            )
        if "short_answer" in question_types:
            type_instructions.append(
                "- Short answer (question_type='short_answer'): "
                "options should be null. correct_answer is a brief text answer."
            )
        if "true_false" in question_types:
            type_instructions.append(
                "- True/False (question_type='true_false'): "
                "options should be null. correct_answer must be 'True' or 'False'."
            )

        difficulty_instruction = ""
        if difficulty:
            difficulty_instruction = f"\nAll questions must be at '{difficulty}' difficulty level."

        prompt = f"""Generate exactly {num_questions} quiz questions about "{topic}".
{difficulty_instruction}

Use a mix of these question types:
{chr(10).join(type_instructions)}

Base the questions on this context:
---
{context_text}
---

Return a JSON object with a "questions" array. Each question must have:
- "id": unique string identifier (e.g., "q-001")
- "question": the question text
- "question_type": one of {question_types}
- "options": list of 4 strings for MCQ, null for others
- "correct_answer": the correct answer text
- "explanation": why this answer is correct
- "topic": "{topic}"
- "difficulty": "{difficulty or 'medium'}"
- "source_chunk_ids": []

Respond with ONLY the JSON object, no other text."""

        return prompt
