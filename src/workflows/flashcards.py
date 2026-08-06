"""Flashcard Generation Workflow for NeuroForge.

Implements a sequential pipeline (retrieve → generate → format) that produces
concise Q/A flashcards from retrieved knowledge concepts. Uses the Retriever
for context gathering and LLMClient for generation with structured output.

Enhanced with expert-level prompts for maximum quality output.

Pipeline steps:
1. Retrieve: Query the knowledge base for relevant concepts
2. Generate: Use LLM to produce concise flashcard Q/A pairs
3. Format: Validate and structure output as Flashcard models
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from models.knowledge import Difficulty
from models.output import Flashcard
from src.llm import LLMClient
from src.retrieval import Retriever
from src.prompts.enhanced import FLASHCARD_SYSTEM_PROMPT, FLASHCARD_USER_PROMPT_TEMPLATE

logger = logging.getLogger("neuroforge.workflows.flashcards")


# ---------------------------------------------------------------------------
# Internal schema for LLM structured output
# ---------------------------------------------------------------------------


class _FlashcardItem(BaseModel):
    """Schema for a single flashcard from LLM output."""

    question: str = Field(..., description="Front of the card (question/prompt)")
    answer: str = Field(..., description="Back of the card (1-10 words)")
    hint: Optional[str] = Field(default=None, description="Hint for difficult cards")
    mnemonic: Optional[str] = Field(default=None, description="Mnemonic device")
    related_topics: list[str] = Field(
        default_factory=list, description="Related topic names"
    )
    difficulty: str = Field(default="medium", description="easy, medium, or hard")


class _FlashcardBatch(BaseModel):
    """Schema for a batch of flashcards from LLM output."""

    flashcards: list[_FlashcardItem] = Field(
        ..., description="List of generated flashcards"
    )


# ---------------------------------------------------------------------------
# Prompts - Now using enhanced prompts from prompts module
# ---------------------------------------------------------------------------

# Keep for reference but use enhanced versions
_FLASHCARD_SYSTEM_PROMPT_LEGACY = """You are an expert study assistant creating flashcards for students."""


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class FlashcardWorkflow:
    """Generates flashcards using a retrieve → generate → format pipeline.

    Args:
        retriever: Retriever instance for fetching relevant concepts.
        llm_client: LLMClient instance for generation.
    """

    def __init__(self, retriever: Retriever, llm_client: LLMClient) -> None:
        """Initialize the FlashcardWorkflow.

        Args:
            retriever: Initialized Retriever for knowledge base queries.
            llm_client: Initialized LLMClient for text generation.
        """
        self.retriever = retriever
        self.llm_client = llm_client

    def generate(
        self,
        topic: str,
        difficulty: Optional[str] = None,
        num_cards: int = 10,
    ) -> list[Flashcard]:
        """Generate flashcards for a given topic.

        Pipeline: retrieve relevant chunks → generate cards via LLM → format as Flashcard models.

        Args:
            topic: The topic to generate flashcards for.
            difficulty: Optional difficulty filter (easy, medium, hard).
            num_cards: Number of flashcards to generate (default 10).

        Returns:
            List of validated Flashcard model instances.
        """
        logger.info(
            f"Generating {num_cards} flashcards for topic='{topic}', "
            f"difficulty={difficulty}"
        )

        # Step 1: Retrieve relevant context
        chunks = self._retrieve(topic, difficulty)
        logger.info(f"Retrieved {len(chunks)} chunks for context")

        # Step 2: Generate flashcards via LLM
        raw_cards = self._generate(topic, difficulty, num_cards, chunks)
        logger.info(f"LLM generated {len(raw_cards)} raw flashcard items")

        # Step 3: Format into validated Flashcard models
        flashcards = self._format(raw_cards, chunks)
        logger.info(f"Formatted {len(flashcards)} validated flashcards")

        return flashcards

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _retrieve(
        self, topic: str, difficulty: Optional[str] = None
    ) -> list[dict]:
        """Step 1: Retrieve relevant chunks from the knowledge base.

        Uses filtered search if difficulty is specified, otherwise
        falls back to semantic search.

        Args:
            topic: Topic to search for.
            difficulty: Optional difficulty filter.

        Returns:
            List of chunk dicts with id, content, score, metadata.
        """
        if difficulty:
            results = self.retriever.filtered_search(
                query=topic, top_k=10, difficulty=difficulty
            )
        else:
            results = self.retriever.semantic_search(query=topic, top_k=10)

        return results

    def _generate(
        self,
        topic: str,
        difficulty: Optional[str],
        num_cards: int,
        chunks: list[dict],
    ) -> list[_FlashcardItem]:
        """Step 2: Generate flashcards using the LLM.

        Uses enhanced prompts for maximum quality output.
        """
        # Build context from chunks
        context = self._build_context(chunks)

        # Build difficulty instruction
        if difficulty:
            difficulty_instruction = (
                f"All cards should be at '{difficulty.upper()}' difficulty level."
            )
        else:
            difficulty_instruction = (
                "Mix difficulty levels: include 30% easy, 50% medium, and 20% hard cards."
            )

        # Format the enhanced user prompt
        user_prompt = FLASHCARD_USER_PROMPT_TEMPLATE.format(
            num_cards=num_cards,
            topic=topic,
            difficulty_instruction=difficulty_instruction,
            context=context,
        )

        # Call LLM with structured output and enhanced system prompt
        batch, usage = self.llm_client.generate_json(
            prompt=user_prompt,
            response_model=_FlashcardBatch,
            system_prompt=FLASHCARD_SYSTEM_PROMPT,
            temperature=0.6,  # Slightly lower for consistent quality
            max_tokens=3072,  # More tokens for better mnemonics
        )

        logger.debug(f"LLM usage: {usage}")
        return batch.flashcards

    def _format(
        self,
        raw_cards: list[_FlashcardItem],
        chunks: list[dict],
    ) -> list[Flashcard]:
        """Step 3: Format raw LLM output into validated Flashcard models.

        Assigns unique IDs, maps difficulty strings to enums, and links
        source chunk IDs for traceability.

        Args:
            raw_cards: Raw flashcard items from the LLM.
            chunks: The source chunks used for generation.

        Returns:
            List of validated Flashcard instances.
        """
        # Collect source chunk IDs for traceability
        source_chunk_ids = [chunk["id"] for chunk in chunks if "id" in chunk]

        flashcards: list[Flashcard] = []
        for card in raw_cards:
            # Map difficulty string to enum
            try:
                diff = Difficulty(card.difficulty.lower())
            except ValueError:
                diff = Difficulty.MEDIUM

            flashcard = Flashcard(
                id=f"fc-{uuid.uuid4().hex[:8]}",
                question=card.question,
                answer=card.answer,
                hint=card.hint,
                mnemonic=card.mnemonic,
                related_topics=card.related_topics,
                difficulty=diff,
                source_chunk_ids=source_chunk_ids,
            )
            flashcards.append(flashcard)

        return flashcards

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
                # Include partial content if we have room
                remaining = max_chars - total
                if remaining > 100:
                    parts.append(content[:remaining])
                break
            parts.append(content)
            total += len(content)

        return "\n\n---\n\n".join(parts) if parts else "No context available."
