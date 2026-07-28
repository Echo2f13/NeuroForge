"""Solution Generation Workflow for NeuroForge.

Implements a sequential pipeline (retrieve → generate → format) that produces
structured answers with depth scaled by mark allocation:
- 2-mark: Brief 2-3 sentence answer
- 5-mark: Moderate detail with key points
- 10-mark: Detailed answer with marking scheme, examples, diagram hints

Uses the Retriever for context and LLMClient for generation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from models.output import Solution
from src.llm import LLMClient, LLMProvider
from src.retrieval.retriever import Retriever

logger = logging.getLogger("neuroforge.workflows.solutions")


# ---------------------------------------------------------------------------
# Depth prompts keyed by mark ranges
# ---------------------------------------------------------------------------

DEPTH_PROMPTS: dict[str, str] = {
    "brief": (
        "Provide a brief answer in 2-3 sentences. "
        "Focus only on the core fact or definition. "
        "No examples or elaboration needed."
    ),
    "moderate": (
        "Provide a moderately detailed answer with key points. "
        "Include a short explanation, 3-5 key points, and a concise marking scheme. "
        "Use clear structure but keep it focused."
    ),
    "detailed": (
        "Provide a comprehensive, detailed answer suitable for a high-mark question. "
        "Include thorough explanation with examples, diagram hints where relevant, "
        "a full marking scheme breakdown, and all key points a student must cover. "
        "Structure with clear paragraphs and subheadings if appropriate."
    ),
}


def _get_depth_category(marks: int) -> str:
    """Map marks to a depth category.

    Args:
        marks: Number of marks allocated (1-100).

    Returns:
        One of 'brief', 'moderate', or 'detailed'.
    """
    if marks <= 3:
        return "brief"
    elif marks <= 6:
        return "moderate"
    else:
        return "detailed"


def _build_solution_prompt(
    question: str,
    topic: str,
    marks: int,
    context: str,
) -> str:
    """Build the LLM prompt for solution generation.

    Args:
        question: The question to answer.
        topic: The topic area.
        marks: Mark allocation.
        context: Retrieved context from knowledge base.

    Returns:
        Formatted prompt string.
    """
    depth_category = _get_depth_category(marks)
    depth_instruction = DEPTH_PROMPTS[depth_category]

    prompt = f"""You are an expert tutor generating a model answer for a student.

**Question:** {question}
**Topic:** {topic}
**Marks allocated:** {marks}

**Depth instruction:** {depth_instruction}

**Relevant context from study materials:**
{context if context else "No specific context available — use general knowledge."}

Generate a structured answer as JSON with these fields:
- "question": the original question (string)
- "marks": the marks allocated (integer)
- "answer": the full answer text (string)
- "marking_scheme": list of strings, each describing a mark-worthy point (e.g., "1 mark: Define the term correctly")
- "key_points": list of strings, each a key point students must include
- "topic": the topic (string)

Rules:
- The marking_scheme items should sum to the total marks.
- For {marks}-mark questions, provide approximately {marks} marking scheme items.
- key_points should list {max(2, marks)} essential points.
- Answer depth and length must match the marks: {"2-3 sentences" if depth_category == "brief" else "1-2 paragraphs with structure" if depth_category == "moderate" else "multiple paragraphs with examples and thorough coverage"}.
"""
    return prompt


class SolutionWorkflow:
    """Workflow for generating structured solutions with marks-based depth.

    Implements a sequential pipeline:
    1. Retrieve relevant context for the question
    2. Generate answer with depth scaled to marks
    3. Format and validate as Solution model

    Args:
        llm_client: Initialized LLMClient instance.
        retriever: Optional Retriever for context fetching.
                   If None, generates without retrieved context.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        retriever: Optional[Retriever] = None,
    ) -> None:
        """Initialize the SolutionWorkflow.

        Args:
            llm_client: LLMClient for text generation.
            retriever: Optional Retriever for fetching relevant context.
        """
        self.llm_client = llm_client
        self.retriever = retriever

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _retrieve_context(self, question: str, topic: str, top_k: int = 5) -> str:
        """Retrieve relevant context from the knowledge base.

        Args:
            question: The question text.
            topic: The topic to filter by.
            top_k: Number of chunks to retrieve.

        Returns:
            Concatenated context string from retrieved chunks.
        """
        if self.retriever is None:
            return ""

        try:
            results = self.retriever.semantic_search(query=question, top_k=top_k)
            if not results:
                return ""

            context_parts: list[str] = []
            for result in results:
                content = result.get("content", "")
                if content:
                    context_parts.append(content)

            return "\n\n---\n\n".join(context_parts)
        except Exception as e:
            logger.warning(f"Retrieval failed, proceeding without context: {e}")
            return ""

    def _generate_solution(
        self,
        question: str,
        topic: str,
        marks: int,
        context: str,
        provider: Optional[LLMProvider] = None,
    ) -> tuple[Solution, dict[str, Any]]:
        """Generate a solution using the LLM.

        Args:
            question: The question to answer.
            topic: The topic area.
            marks: Mark allocation (controls depth).
            context: Retrieved context string.
            provider: Optional preferred LLM provider.

        Returns:
            Tuple of (Solution instance, usage info).
        """
        prompt = _build_solution_prompt(question, topic, marks, context)

        system_prompt = (
            "You are a precise exam-answer generator. "
            "Produce JSON matching the exact schema requested. "
            "Scale answer depth to the marks allocated."
        )

        # Scale max tokens based on marks
        depth_category = _get_depth_category(marks)
        if depth_category == "brief":
            max_tokens = 512
        elif depth_category == "moderate":
            max_tokens = 1024
        else:
            max_tokens = 2048

        solution, usage = self.llm_client.generate_json(
            prompt=prompt,
            response_model=Solution,
            system_prompt=system_prompt,
            provider=provider,
            temperature=0.5,
            max_tokens=max_tokens,
        )

        return solution, usage

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        question: str,
        topic: str,
        marks: int = 5,
        provider: Optional[LLMProvider] = None,
    ) -> Solution:
        """Generate a structured solution for a question.

        Pipeline: retrieve context → generate answer → validate output.

        Args:
            question: The question to answer.
            topic: The topic/subject area.
            marks: Mark allocation (1-100). Controls answer depth:
                   - 1-3 marks: brief (2-3 sentences)
                   - 4-6 marks: moderate (key points, short paragraphs)
                   - 7+  marks: detailed (full explanation, examples, diagrams)
            provider: Optional preferred LLM provider.

        Returns:
            Validated Solution instance.

        Raises:
            ValueError: If marks is outside valid range.
            LLMError: If generation fails after retries.
        """
        if marks < 1 or marks > 100:
            raise ValueError(f"marks must be between 1 and 100, got {marks}")

        logger.info(
            f"Generating solution: topic='{topic}', marks={marks}, "
            f"depth='{_get_depth_category(marks)}'"
        )

        # Step 1: Retrieve context
        context = self._retrieve_context(question, topic)

        # Step 2: Generate solution
        solution, usage = self._generate_solution(
            question=question,
            topic=topic,
            marks=marks,
            context=context,
            provider=provider,
        )

        logger.info(
            f"Solution generated: {len(solution.key_points)} key points, "
            f"{len(solution.marking_scheme)} marking items, "
            f"tokens={usage.get('total_tokens', 0)}"
        )

        return solution
