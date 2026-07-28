"""NeuroForge — Difficulty & Metadata Extraction.

Provides metadata enrichment for document chunks and concepts:
- Difficulty classification (Easy/Medium/Hard) per chunk
- Study time estimation per concept
- Keyword extraction (5-10 per chunk)
- Chunk-level summaries (1-2 sentences)
- Document-level summaries (3-5 sentences)

All extraction is powered by the LLMClient with structured JSON output.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from models import Chunk, Concept, Difficulty, Document
from src.llm import LLMClient, LLMProvider

logger = logging.getLogger("neuroforge.extraction.metadata")

# ---------------------------------------------------------------------------
# Internal response models for LLM structured output
# ---------------------------------------------------------------------------


class DifficultyItem(BaseModel):
    """Single chunk difficulty classification."""

    chunk_id: str = Field(..., description="ID of the chunk")
    difficulty: str = Field(
        ..., description="Difficulty level: easy, medium, or hard"
    )


class DifficultyResponse(BaseModel):
    """LLM response model for difficulty classification."""

    classifications: list[DifficultyItem] = Field(
        ..., description="Difficulty classification per chunk"
    )


class KeywordsItem(BaseModel):
    """Keywords extracted for a single chunk."""

    chunk_id: str = Field(..., description="ID of the chunk")
    keywords: list[str] = Field(
        ..., description="5-10 keywords extracted from the chunk"
    )


class KeywordsResponse(BaseModel):
    """LLM response model for keyword extraction."""

    results: list[KeywordsItem] = Field(
        ..., description="Keywords per chunk"
    )


class SummaryItem(BaseModel):
    """Summary for a single chunk."""

    chunk_id: str = Field(..., description="ID of the chunk")
    summary: str = Field(..., description="1-2 sentence summary of the chunk")


class ChunkSummariesResponse(BaseModel):
    """LLM response model for chunk summaries."""

    summaries: list[SummaryItem] = Field(
        ..., description="Summary per chunk"
    )


class DocumentSummaryResponse(BaseModel):
    """LLM response model for document-level summary."""

    summary: str = Field(
        ..., description="3-5 sentence document summary"
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

DIFFICULTY_CLASSIFICATION_PROMPT = """Classify the difficulty level of each text chunk below.

Consider these factors when classifying:
- Easy: Introductory concepts, simple definitions, basic facts, no prerequisites needed.
- Medium: Moderate complexity, requires some background knowledge, involves processes or multi-step ideas.
- Hard: Advanced material, requires significant prerequisite knowledge, involves complex theory, abstract reasoning, or specialized formulas.

CHUNKS:
{chunk_text}

For each chunk, assign a difficulty level: "easy", "medium", or "hard".
Return a JSON object with a key "classifications" containing a list of objects with "chunk_id" and "difficulty".

Example output:
{{"classifications": [{{"chunk_id": "chunk-001", "difficulty": "medium"}}, {{"chunk_id": "chunk-002", "difficulty": "hard"}}]}}
"""

KEYWORD_EXTRACTION_PROMPT = """Extract the most important keywords from each text chunk below.

Extract 5-10 keywords per chunk that capture the core concepts, terminology, and key ideas.
Keywords should be specific and useful for search and retrieval.

CHUNKS:
{chunk_text}

Return a JSON object with a key "results" containing a list of objects with "chunk_id" and "keywords" (list of strings).

Example output:
{{"results": [{{"chunk_id": "chunk-001", "keywords": ["neural networks", "activation function", "backpropagation", "gradient descent", "loss function"]}}]}}
"""

CHUNK_SUMMARY_PROMPT = """Write a concise 1-2 sentence summary for each text chunk below.

Each summary should capture the main point or key information in the chunk.
Be specific and informative, not vague.

CHUNKS:
{chunk_text}

Return a JSON object with a key "summaries" containing a list of objects with "chunk_id" and "summary".

Example output:
{{"summaries": [{{"chunk_id": "chunk-001", "summary": "Explains the backpropagation algorithm and how gradients are computed through the network layers."}}]}}
"""

DOCUMENT_SUMMARY_PROMPT = """Write a comprehensive 3-5 sentence summary of the following document.

The summary should:
- Identify the main subject/topic of the document
- Highlight the key concepts or arguments presented
- Mention the scope and level of detail
- Note any practical applications or conclusions

DOCUMENT CONTENT:
{document_text}

Return a JSON object with a single key "summary" containing the 3-5 sentence summary string.

Example output:
{{"summary": "This document covers the fundamentals of machine learning, focusing on supervised learning techniques. It explains key algorithms including linear regression, decision trees, and neural networks. The material progresses from basic concepts to advanced optimization methods, assuming familiarity with linear algebra and calculus. Practical examples demonstrate model training and evaluation using real-world datasets."}}
"""

# ---------------------------------------------------------------------------
# Study time estimation constants
# ---------------------------------------------------------------------------

# Base study time ranges per difficulty (in minutes)
STUDY_TIME_RANGES: dict[Difficulty, tuple[float, float]] = {
    Difficulty.EASY: (5.0, 10.0),
    Difficulty.MEDIUM: (15.0, 30.0),
    Difficulty.HARD: (30.0, 60.0),
}

# Additional minutes per prerequisite
PREREQ_TIME_BONUS = 3.0

# Maximum additional time from prerequisites
MAX_PREREQ_BONUS = 15.0

# Default batch size for chunk processing
DEFAULT_BATCH_SIZE = 5


# ---------------------------------------------------------------------------
# MetadataExtractor
# ---------------------------------------------------------------------------


class MetadataExtractor:
    """Extracts metadata and difficulty classifications from chunks and concepts.

    Uses an LLM client for structured output generation to:
    - Classify difficulty per chunk
    - Estimate study time per concept
    - Extract keywords per chunk
    - Generate chunk-level and document-level summaries

    Args:
        llm_client: An LLMClient instance for LLM calls.
        batch_size: Number of chunks to process per batch (default 5).
        provider: Preferred LLM provider (optional).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        batch_size: int = DEFAULT_BATCH_SIZE,
        provider: Optional[LLMProvider] = None,
    ):
        self.llm_client = llm_client
        self.batch_size = batch_size
        self.provider = provider

    def classify_difficulty(
        self, chunks: list[Chunk]
    ) -> dict[str, Difficulty]:
        """Assign a difficulty level to each chunk using LLM classification.

        Args:
            chunks: List of document chunks to classify.

        Returns:
            Dictionary mapping chunk IDs to Difficulty enum values.
        """
        if not chunks:
            return {}

        difficulty_map: dict[str, Difficulty] = {}
        enum_lookup = {
            "easy": Difficulty.EASY,
            "medium": Difficulty.MEDIUM,
            "hard": Difficulty.HARD,
        }

        for batch in self._batch_chunks(chunks):
            chunk_text = self._format_chunks(batch)
            prompt = DIFFICULTY_CLASSIFICATION_PROMPT.format(chunk_text=chunk_text)

            try:
                result, _usage = self.llm_client.generate_json(
                    prompt=prompt,
                    response_model=DifficultyResponse,
                    provider=self.provider,
                    temperature=0.3,
                )
                for item in result.classifications:
                    difficulty = enum_lookup.get(
                        item.difficulty.lower().strip(), Difficulty.MEDIUM
                    )
                    difficulty_map[item.chunk_id] = difficulty
            except Exception as e:
                logger.warning(f"Difficulty classification failed for batch: {e}")
                # Default to MEDIUM for failed chunks
                for chunk in batch:
                    difficulty_map[chunk.id] = Difficulty.MEDIUM

        return difficulty_map

    def estimate_study_time(
        self, concepts: list[Concept]
    ) -> dict[str, float]:
        """Estimate study time in minutes for each concept.

        Uses a heuristic based on difficulty level and prerequisite count:
        - Easy: 5-10 minutes base
        - Medium: 15-30 minutes base
        - Hard: 30-60 minutes base
        - Additional time per prerequisite (capped)

        Args:
            concepts: List of concepts to estimate study time for.

        Returns:
            Dictionary mapping concept IDs to estimated minutes.
        """
        if not concepts:
            return {}

        study_times: dict[str, float] = {}

        for concept in concepts:
            min_time, max_time = STUDY_TIME_RANGES[concept.difficulty]

            # Base time is the midpoint of the range
            base_time = (min_time + max_time) / 2.0

            # Add time for prerequisites (more prereqs = more complex)
            prereq_count = len(concept.prerequisites)
            prereq_bonus = min(
                prereq_count * PREREQ_TIME_BONUS, MAX_PREREQ_BONUS
            )

            total_time = round(base_time + prereq_bonus, 1)
            study_times[concept.id] = total_time

        return study_times

    def extract_keywords(
        self, chunks: list[Chunk]
    ) -> dict[str, list[str]]:
        """Extract 5-10 keywords per chunk using LLM.

        Args:
            chunks: List of document chunks for keyword extraction.

        Returns:
            Dictionary mapping chunk IDs to lists of keywords.
        """
        if not chunks:
            return {}

        keywords_map: dict[str, list[str]] = {}

        for batch in self._batch_chunks(chunks):
            chunk_text = self._format_chunks(batch)
            prompt = KEYWORD_EXTRACTION_PROMPT.format(chunk_text=chunk_text)

            try:
                result, _usage = self.llm_client.generate_json(
                    prompt=prompt,
                    response_model=KeywordsResponse,
                    provider=self.provider,
                    temperature=0.3,
                )
                for item in result.results:
                    keywords_map[item.chunk_id] = item.keywords
            except Exception as e:
                logger.warning(f"Keyword extraction failed for batch: {e}")
                # Return empty keywords for failed chunks
                for chunk in batch:
                    keywords_map[chunk.id] = []

        return keywords_map

    def generate_chunk_summaries(
        self, chunks: list[Chunk]
    ) -> dict[str, str]:
        """Generate 1-2 sentence summaries per chunk using LLM.

        Args:
            chunks: List of document chunks to summarize.

        Returns:
            Dictionary mapping chunk IDs to summary strings.
        """
        if not chunks:
            return {}

        summaries_map: dict[str, str] = {}

        for batch in self._batch_chunks(chunks):
            chunk_text = self._format_chunks(batch)
            prompt = CHUNK_SUMMARY_PROMPT.format(chunk_text=chunk_text)

            try:
                result, _usage = self.llm_client.generate_json(
                    prompt=prompt,
                    response_model=ChunkSummariesResponse,
                    provider=self.provider,
                    temperature=0.5,
                )
                for item in result.summaries:
                    summaries_map[item.chunk_id] = item.summary
            except Exception as e:
                logger.warning(f"Chunk summary generation failed for batch: {e}")
                # Return empty summaries for failed chunks
                for chunk in batch:
                    summaries_map[chunk.id] = ""

        return summaries_map

    def generate_document_summary(self, document: Document) -> str:
        """Generate a 3-5 sentence summary for an entire document.

        Args:
            document: The Document object to summarize.

        Returns:
            A 3-5 sentence summary string. Returns empty string on failure.
        """
        if not document.content:
            return ""

        # Truncate content if too long (keep first ~3000 chars for context window)
        content = document.content[:3000]
        if len(document.content) > 3000:
            content += "\n\n[... content truncated for summary generation ...]"

        prompt = DOCUMENT_SUMMARY_PROMPT.format(document_text=content)

        try:
            result, _usage = self.llm_client.generate_json(
                prompt=prompt,
                response_model=DocumentSummaryResponse,
                provider=self.provider,
                temperature=0.5,
                max_tokens=512,
            )
            return result.summary
        except Exception as e:
            logger.warning(f"Document summary generation failed: {e}")
            return ""

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _batch_chunks(self, chunks: list[Chunk]) -> list[list[Chunk]]:
        """Split chunks into batches of self.batch_size."""
        batches = []
        for i in range(0, len(chunks), self.batch_size):
            batches.append(chunks[i : i + self.batch_size])
        return batches

    def _format_chunks(self, chunks: list[Chunk]) -> str:
        """Format chunks into labeled text blocks for prompts."""
        parts = []
        for chunk in chunks:
            parts.append(f"[Chunk ID: {chunk.id}]\n{chunk.content}")
        return "\n\n---\n\n".join(parts)
