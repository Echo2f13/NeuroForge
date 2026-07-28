"""NeuroForge — Formula, Example, Date, People Extraction.

Extracts structured knowledge elements from document chunks using LLM-powered
structured output generation:
- Formulae/equations with context
- Illustrative examples with related concepts
- Key dates/events with significance
- Key people with roles and contributions

All extraction links results to source chunk IDs for traceability.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from models import Chunk, Example, Formula, KeyDate, KeyPerson
from src.llm import LLMClient, LLMProvider

logger = logging.getLogger("neuroforge.extraction.elements")

# ---------------------------------------------------------------------------
# Internal response models for LLM structured output
# ---------------------------------------------------------------------------


class FormulaItem(BaseModel):
    """A single formula extracted by the LLM."""

    expression: str = Field(..., description="The formula expression (LaTeX or plain text)")
    description: str = Field(..., description="What the formula represents")
    context: str = Field(..., description="Context in which the formula is used")


class FormulaListResponse(BaseModel):
    """LLM response model for formula extraction."""

    formulae: list[FormulaItem] = Field(
        default_factory=list, description="List of extracted formulae"
    )


class ExampleItem(BaseModel):
    """A single example extracted by the LLM."""

    title: str = Field(..., description="Short title for the example")
    content: str = Field(..., description="Full example content")
    related_concepts: list[str] = Field(
        default_factory=list, description="Related concept names"
    )


class ExampleListResponse(BaseModel):
    """LLM response model for example extraction."""

    examples: list[ExampleItem] = Field(
        default_factory=list, description="List of extracted examples"
    )


class DateItem(BaseModel):
    """A single key date extracted by the LLM."""

    date: str = Field(..., description="The date (flexible format)")
    event: str = Field(..., description="What happened on this date")
    significance: str = Field(..., description="Why this date matters")


class DateListResponse(BaseModel):
    """LLM response model for date extraction."""

    dates: list[DateItem] = Field(
        default_factory=list, description="List of extracted dates"
    )


class PersonItem(BaseModel):
    """A single key person extracted by the LLM."""

    name: str = Field(..., description="Person's name")
    role: str = Field(..., description="Their role or title")
    contribution: str = Field(..., description="Key contribution or significance")


class PersonListResponse(BaseModel):
    """LLM response model for people extraction."""

    people: list[PersonItem] = Field(
        default_factory=list, description="List of extracted people"
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

FORMULA_EXTRACTION_PROMPT = """Extract all mathematical formulae, equations, or quantitative expressions from the following text chunks.

For each formula, provide:
- expression: The formula itself (use LaTeX notation where possible, or plain text)
- description: What the formula represents or calculates
- context: The context in which the formula is used or discussed

Only extract actual formulae, equations, or quantitative relationships. Do not invent formulae that are not present in the text.
If no formulae are found, return an empty list.

TEXT:
{chunk_text}

Return a JSON object with a key "formulae" containing a list of formula objects.

Example output:
{{"formulae": [{{"expression": "E = mc^2", "description": "Mass-energy equivalence formula", "context": "Discussed in the context of special relativity and nuclear physics"}}]}}
"""

EXAMPLE_EXTRACTION_PROMPT = """Extract all illustrative examples, case studies, or demonstrations from the following text chunks.

For each example, provide:
- title: A short descriptive title for the example
- content: The full example content or description
- related_concepts: A list of concept names that this example illustrates

Only extract actual examples, demonstrations, or case studies present in the text. Do not invent examples.
If no examples are found, return an empty list.

TEXT:
{chunk_text}

Return a JSON object with a key "examples" containing a list of example objects.

Example output:
{{"examples": [{{"title": "Binary Search on Sorted Array", "content": "Given a sorted array [1, 3, 5, 7, 9], to find element 7, we compare with the middle element 5, then search the right half.", "related_concepts": ["Binary Search", "Algorithm Complexity", "Divide and Conquer"]}}]}}
"""

DATE_EXTRACTION_PROMPT = """Extract all important dates, time periods, or historical events mentioned in the following text chunks.

For each date, provide:
- date: The date or time period (flexible format: "1905", "March 14, 1879", "1940s", etc.)
- event: What happened or what is associated with this date
- significance: Why this date matters in the context of the material

Only extract dates that are explicitly mentioned in the text. Do not invent dates.
If no significant dates are found, return an empty list.

TEXT:
{chunk_text}

Return a JSON object with a key "dates" containing a list of date objects.

Example output:
{{"dates": [{{"date": "1687", "event": "Publication of Newton's Principia Mathematica", "significance": "Established the foundations of classical mechanics and introduced the law of universal gravitation"}}]}}
"""

PEOPLE_EXTRACTION_PROMPT = """Extract all important people mentioned in the following text chunks.

For each person, provide:
- name: The person's full name
- role: Their role, title, or profession
- contribution: Their key contribution or significance as described in the text

Only extract people who are explicitly mentioned in the text. Do not invent people.
If no significant people are found, return an empty list.

TEXT:
{chunk_text}

Return a JSON object with a key "people" containing a list of person objects.

Example output:
{{"people": [{{"name": "Alan Turing", "role": "Mathematician and computer scientist", "contribution": "Developed the concept of the Turing machine, laying the theoretical foundation for modern computing"}}]}}
"""

# ---------------------------------------------------------------------------
# Default batch size
# ---------------------------------------------------------------------------

DEFAULT_BATCH_SIZE = 4


# ---------------------------------------------------------------------------
# ElementExtractor
# ---------------------------------------------------------------------------


class ElementExtractor:
    """Extracts formulae, examples, dates, and people from document chunks.

    Uses an LLM client for structured output generation with JSON validation
    against Pydantic models. Processes chunks in batches to stay within
    context limits. All results are linked to source chunk IDs.

    Args:
        llm_client: An LLMClient instance for LLM calls.
        batch_size: Number of chunks to process per batch (default 4).
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

    def extract_formulae(self, chunks: list[Chunk]) -> list[Formula]:
        """Extract mathematical formulae/equations from chunks.

        Processes chunks in batches and links each formula to its
        source chunk ID.

        Args:
            chunks: List of document chunks to analyze.

        Returns:
            List of Formula instances with source_chunk_id populated.
        """
        if not chunks:
            return []

        all_formulae: list[Formula] = []

        for batch in self._batch_chunks(chunks):
            chunk_text = self._format_chunks(batch)
            chunk_ids = [c.id for c in batch]
            prompt = FORMULA_EXTRACTION_PROMPT.format(chunk_text=chunk_text)

            try:
                result, _usage = self.llm_client.generate_json(
                    prompt=prompt,
                    response_model=FormulaListResponse,
                    provider=self.provider,
                    temperature=0.3,
                    max_tokens=4096,
                )
                for item in result.formulae:
                    # Determine source chunk by checking which chunk text
                    # contains the formula expression
                    source_id = self._find_source_chunk(
                        item.expression, batch, chunk_ids
                    )
                    all_formulae.append(
                        Formula(
                            expression=item.expression,
                            description=item.description,
                            context=item.context,
                            source_chunk_id=source_id,
                        )
                    )
            except Exception as e:
                logger.warning(f"Formula extraction failed for batch: {e}")
                continue

        return all_formulae

    def extract_examples(self, chunks: list[Chunk]) -> list[Example]:
        """Extract illustrative examples from chunks.

        Processes chunks in batches and links each example to its
        source chunk ID.

        Args:
            chunks: List of document chunks to analyze.

        Returns:
            List of Example instances with source_chunk_id populated.
        """
        if not chunks:
            return []

        all_examples: list[Example] = []

        for batch in self._batch_chunks(chunks):
            chunk_text = self._format_chunks(batch)
            chunk_ids = [c.id for c in batch]
            prompt = EXAMPLE_EXTRACTION_PROMPT.format(chunk_text=chunk_text)

            try:
                result, _usage = self.llm_client.generate_json(
                    prompt=prompt,
                    response_model=ExampleListResponse,
                    provider=self.provider,
                    temperature=0.3,
                    max_tokens=4096,
                )
                for item in result.examples:
                    source_id = self._find_source_chunk(
                        item.content, batch, chunk_ids
                    )
                    all_examples.append(
                        Example(
                            title=item.title,
                            content=item.content,
                            related_concepts=item.related_concepts,
                            source_chunk_id=source_id,
                        )
                    )
            except Exception as e:
                logger.warning(f"Example extraction failed for batch: {e}")
                continue

        return all_examples

    def extract_dates(self, chunks: list[Chunk]) -> list[KeyDate]:
        """Extract important dates/events from chunks.

        Processes chunks in batches and links each date to its
        source chunk ID.

        Args:
            chunks: List of document chunks to analyze.

        Returns:
            List of KeyDate instances with source_chunk_id populated.
        """
        if not chunks:
            return []

        all_dates: list[KeyDate] = []

        for batch in self._batch_chunks(chunks):
            chunk_text = self._format_chunks(batch)
            chunk_ids = [c.id for c in batch]
            prompt = DATE_EXTRACTION_PROMPT.format(chunk_text=chunk_text)

            try:
                result, _usage = self.llm_client.generate_json(
                    prompt=prompt,
                    response_model=DateListResponse,
                    provider=self.provider,
                    temperature=0.3,
                    max_tokens=4096,
                )
                for item in result.dates:
                    source_id = self._find_source_chunk(
                        item.date, batch, chunk_ids
                    )
                    all_dates.append(
                        KeyDate(
                            date=item.date,
                            event=item.event,
                            significance=item.significance,
                            source_chunk_id=source_id,
                        )
                    )
            except Exception as e:
                logger.warning(f"Date extraction failed for batch: {e}")
                continue

        return all_dates

    def extract_people(self, chunks: list[Chunk]) -> list[KeyPerson]:
        """Extract important people with roles and contributions from chunks.

        Processes chunks in batches and links each person to their
        source chunk ID.

        Args:
            chunks: List of document chunks to analyze.

        Returns:
            List of KeyPerson instances with source_chunk_id populated.
        """
        if not chunks:
            return []

        all_people: list[KeyPerson] = []

        for batch in self._batch_chunks(chunks):
            chunk_text = self._format_chunks(batch)
            chunk_ids = [c.id for c in batch]
            prompt = PEOPLE_EXTRACTION_PROMPT.format(chunk_text=chunk_text)

            try:
                result, _usage = self.llm_client.generate_json(
                    prompt=prompt,
                    response_model=PersonListResponse,
                    provider=self.provider,
                    temperature=0.3,
                    max_tokens=4096,
                )
                for item in result.people:
                    source_id = self._find_source_chunk(
                        item.name, batch, chunk_ids
                    )
                    all_people.append(
                        KeyPerson(
                            name=item.name,
                            role=item.role,
                            contribution=item.contribution,
                            source_chunk_id=source_id,
                        )
                    )
            except Exception as e:
                logger.warning(f"People extraction failed for batch: {e}")
                continue

        return all_people

    def extract_all(self, chunks: list[Chunk]) -> dict:
        """Extract all element types from chunks.

        Runs formula, example, date, and people extraction sequentially
        and returns combined results.

        Args:
            chunks: List of document chunks to process.

        Returns:
            Dictionary with keys 'formulae', 'examples', 'dates', 'people',
            each containing the corresponding list of extracted elements.
        """
        if not chunks:
            return {
                "formulae": [],
                "examples": [],
                "dates": [],
                "people": [],
            }

        logger.info(f"Starting element extraction on {len(chunks)} chunks")

        formulae = self.extract_formulae(chunks)
        logger.info(f"Extracted {len(formulae)} formulae")

        examples = self.extract_examples(chunks)
        logger.info(f"Extracted {len(examples)} examples")

        dates = self.extract_dates(chunks)
        logger.info(f"Extracted {len(dates)} dates")

        people = self.extract_people(chunks)
        logger.info(f"Extracted {len(people)} people")

        return {
            "formulae": formulae,
            "examples": examples,
            "dates": dates,
            "people": people,
        }

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

    def _find_source_chunk(
        self,
        search_text: str,
        batch: list[Chunk],
        chunk_ids: list[str],
    ) -> str:
        """Find which chunk most likely contains the extracted element.

        Uses simple substring matching. Falls back to the first chunk
        in the batch if no match is found.

        Args:
            search_text: Text to search for in chunk contents.
            batch: The batch of chunks being processed.
            chunk_ids: Corresponding chunk IDs.

        Returns:
            The ID of the most likely source chunk.
        """
        search_lower = search_text.lower()
        for chunk in batch:
            if search_lower in chunk.content.lower():
                return chunk.id

        # Fallback: return the first chunk in the batch
        return chunk_ids[0] if chunk_ids else "unknown"
