"""Additional Information Workflow for NeuroForge.

Implements a sequential pipeline (retrieve → generate → format) that produces
real-world applications, industry uses, common mistakes, and interview questions
for a given topic. Uses the Retriever for context gathering and LLMClient for
generation with structured output.

Enhanced with expert-level prompts for maximum quality output.

Pipeline steps:
1. Retrieve: Query the knowledge base for relevant concepts
2. Generate: Use LLM to produce additional info items
3. Format: Validate and structure output as a dict
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.llm import LLMClient
from src.retrieval import Retriever
from src.prompts.enhanced import (
    ADDITIONAL_INFO_SYSTEM_PROMPT,
    ADDITIONAL_INFO_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger("neuroforge.workflows.additional_info")


# ---------------------------------------------------------------------------
# Internal schema for LLM structured output
# ---------------------------------------------------------------------------


class _AdditionalInfoOutput(BaseModel):
    """Schema for additional info structured output from LLM."""

    applications: list[str] = Field(
        ..., description="5 real-world applications of this topic with industry names"
    )
    industry_uses: list[str] = Field(
        ..., description="5 industry uses in format 'Industry: Use case'"
    )
    common_mistakes: list[str] = Field(
        ..., description="5 common mistakes in format 'Mistake: Description → Consequence'"
    )
    interview_questions: list[str] = Field(
        ..., description="5 interview questions with difficulty levels"
    )


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class AdditionalInfoWorkflow:
    """Generates additional info using a retrieve → generate → format pipeline.

    Produces real-world applications, industry uses, common mistakes, and
    interview questions for a given topic.

    Args:
        retriever: Retriever instance for fetching relevant concepts.
        llm_client: LLMClient instance for generation.
    """

    def __init__(self, retriever: Retriever, llm_client: LLMClient) -> None:
        """Initialize the AdditionalInfoWorkflow.

        Args:
            retriever: Initialized Retriever for knowledge base queries.
            llm_client: Initialized LLMClient for text generation.
        """
        self.retriever = retriever
        self.llm_client = llm_client

    def generate(self, topic: str) -> dict:
        """Generate additional information for a given topic.

        Pipeline: retrieve relevant chunks → generate info via LLM → format as dict.

        Args:
            topic: The topic to generate additional info for.

        Returns:
            Dict with keys: "applications", "industry_uses",
            "common_mistakes", "interview_questions". Each value is a list[str].
        """
        logger.info(f"Generating additional info for topic='{topic}'")

        # Step 1: Retrieve relevant context
        chunks = self._retrieve(topic)
        logger.info(f"Retrieved {len(chunks)} chunks for context")

        # Step 2: Generate additional info via LLM
        raw_output = self._generate(topic, chunks)
        logger.info("LLM generated additional info")

        # Step 3: Format into validated dict
        result = self._format(raw_output)
        logger.info(
            f"Formatted result: {len(result['applications'])} applications, "
            f"{len(result['industry_uses'])} industry uses, "
            f"{len(result['common_mistakes'])} common mistakes, "
            f"{len(result['interview_questions'])} interview questions"
        )

        return result

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _retrieve(self, topic: str) -> list[dict]:
        """Step 1: Retrieve relevant chunks from the knowledge base.

        Uses semantic search to find relevant content for the topic.

        Args:
            topic: Topic to search for.

        Returns:
            List of chunk dicts with id, content, score, metadata.
        """
        return self.retriever.semantic_search(query=topic, top_k=8)

    def _generate(self, topic: str, chunks: list[dict]) -> _AdditionalInfoOutput:
        """Step 2: Generate additional info using the LLM.

        Uses enhanced prompts for maximum quality output.

        Args:
            topic: The topic for generation.
            chunks: Retrieved context chunks.

        Returns:
            Parsed _AdditionalInfoOutput from LLM.
        """
        context = self._build_context(chunks)

        # Build the enhanced user prompt
        user_prompt = ADDITIONAL_INFO_USER_PROMPT_TEMPLATE.format(
            topic=topic,
            context=context,
        )

        output, usage = self.llm_client.generate_json(
            prompt=user_prompt,
            response_model=_AdditionalInfoOutput,
            system_prompt=ADDITIONAL_INFO_SYSTEM_PROMPT,
            temperature=0.7,  # Slightly creative for real-world examples
            max_tokens=2048,  # Room for detailed responses
        )

        logger.debug(f"LLM usage: {usage}")
        return output

    def _format(self, raw_output: _AdditionalInfoOutput) -> dict:
        """Step 3: Format raw LLM output into a validated dict.

        Ensures each list has between 3 and 5 items (truncates if needed).

        Args:
            raw_output: Parsed _AdditionalInfoOutput from LLM.

        Returns:
            Dict with keys: applications, industry_uses, common_mistakes,
            interview_questions.
        """
        return {
            "applications": raw_output.applications[:5],
            "industry_uses": raw_output.industry_uses[:5],
            "common_mistakes": raw_output.common_mistakes[:5],
            "interview_questions": raw_output.interview_questions[:5],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(chunks: list[dict], max_chars: int = 4000) -> str:
        """Build a context string from retrieved chunks.

        Concatenates chunk content up to a character limit to fit
        within LLM context windows.

        Args:
            chunks: List of chunk dicts with 'content' key.
            max_chars: Maximum total characters for context.

        Returns:
            Concatenated context string.
        """
        parts: list[str] = []
        total = 0
        for chunk in chunks:
            content = chunk.get("content", "")
            if total + len(content) > max_chars:
                remaining = max_chars - total
                if remaining > 100:
                    parts.append(content[:remaining])
                break
            parts.append(content)
            total += len(content)

        return "\n\n---\n\n".join(parts) if parts else "No context available."
