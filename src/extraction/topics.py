"""NeuroForge — Topic & Concept Extraction.

Extracts topics, concepts, and relationships from document chunks
using LLM-powered structured output generation.

Features:
- Topic/subtopic extraction from chunk text
- Concept extraction with definitions, difficulty, prerequisites, keywords
- Batch processing (chunks processed in groups to respect context limits)
- Deduplication of concepts across chunks
- JSON output validated against Pydantic models
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from models import Chunk, Concept, ConceptRelationship, Difficulty, KnowledgeExtraction
from src.llm import LLMClient, LLMProvider

logger = logging.getLogger("neuroforge.extraction.topics")

# ---------------------------------------------------------------------------
# Internal response models for LLM structured output
# ---------------------------------------------------------------------------


class TopicListResponse(BaseModel):
    """LLM response model for topic extraction."""

    topics: list[str] = Field(
        ..., description="Main topics and subtopics identified in the text"
    )


class ConceptResponse(BaseModel):
    """A single concept extracted by the LLM."""

    name: str = Field(..., min_length=1, description="Concept name")
    definition: str = Field(..., min_length=1, description="Clear definition")
    topics: list[str] = Field(
        ..., min_length=1, description="Topics this concept belongs to"
    )
    difficulty: str = Field(
        ..., description="Difficulty level: easy, medium, or hard"
    )
    keywords: list[str] = Field(
        default_factory=list, description="Associated keywords"
    )
    prerequisites: list[str] = Field(
        default_factory=list, description="Prerequisite concept names"
    )


class ConceptListResponse(BaseModel):
    """LLM response model for concept extraction."""

    concepts: list[ConceptResponse] = Field(
        ..., description="List of extracted concepts"
    )


class RelationshipResponse(BaseModel):
    """A single relationship between two concepts."""

    source: str = Field(..., description="Source concept name")
    target: str = Field(..., description="Target concept name")
    relationship_type: str = Field(
        ..., description="Type: prerequisite, related, or part_of"
    )


class RelationshipListResponse(BaseModel):
    """LLM response model for relationship extraction."""

    relationships: list[RelationshipResponse] = Field(
        ..., description="List of concept relationships"
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

TOPIC_EXTRACTION_PROMPT = """Analyze the following text chunks and identify the main topics and subtopics covered.

TEXT:
{chunk_text}

Extract ALL distinct topics and subtopics. Be specific but concise.
Return a JSON object with a single key "topics" containing a list of topic strings.

Example output:
{{"topics": ["Machine Learning", "Supervised Learning", "Neural Networks", "Backpropagation"]}}
"""

CONCEPT_EXTRACTION_PROMPT = """Given the following text and known topics, extract key concepts with their definitions.

KNOWN TOPICS: {topics}

TEXT:
{chunk_text}

For each concept, provide:
- name: A concise name for the concept
- definition: A clear, complete definition (1-3 sentences)
- topics: Which of the known topics this concept belongs to
- difficulty: One of "easy", "medium", or "hard"
- keywords: Related keywords for search/retrieval
- prerequisites: Names of other concepts that should be understood first

Return a JSON object with a single key "concepts" containing a list of concept objects.

Example output:
{{"concepts": [{{"name": "Gradient Descent", "definition": "An optimization algorithm that iteratively adjusts parameters in the direction of steepest descent of the loss function.", "topics": ["Machine Learning", "Optimization"], "difficulty": "medium", "keywords": ["optimization", "learning rate", "loss function"], "prerequisites": ["Calculus", "Linear Algebra"]}}]}}
"""

RELATIONSHIP_EXTRACTION_PROMPT = """Given the following concepts, identify relationships between them.

CONCEPTS:
{concept_names}

Relationship types:
- "prerequisite": source must be understood before target
- "related": concepts are related but neither is prerequisite
- "part_of": source is a component/subtopic of target

Return a JSON object with a single key "relationships" containing a list of relationship objects.
Each relationship has: "source" (concept name), "target" (concept name), "relationship_type".

Only include relationships where there is a clear connection. Do not force relationships.

Example output:
{{"relationships": [{{"source": "Linear Algebra", "target": "Neural Networks", "relationship_type": "prerequisite"}}]}}
"""

# ---------------------------------------------------------------------------
# Default batch size
# ---------------------------------------------------------------------------

DEFAULT_BATCH_SIZE = 5


# ---------------------------------------------------------------------------
# TopicExtractor
# ---------------------------------------------------------------------------


class TopicExtractor:
    """Extracts topics, concepts, and relationships from document chunks.

    Uses an LLM client for structured output generation with JSON validation
    against Pydantic models. Processes chunks in batches to stay within
    context limits.

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

    def extract_topics(self, chunks: list[Chunk]) -> list[str]:
        """Extract main topics and subtopics from a set of chunks.

        Processes chunks in batches, extracts topics from each batch,
        then deduplicates the combined topic list.

        Args:
            chunks: List of document chunks to analyze.

        Returns:
            Deduplicated list of topic strings.
        """
        if not chunks:
            return []

        all_topics: list[str] = []

        for batch in self._batch_chunks(chunks):
            chunk_text = self._combine_chunk_text(batch)
            prompt = TOPIC_EXTRACTION_PROMPT.format(chunk_text=chunk_text)

            try:
                result, _usage = self.llm_client.generate_json(
                    prompt=prompt,
                    response_model=TopicListResponse,
                    provider=self.provider,
                    temperature=0.3,
                )
                all_topics.extend(result.topics)
            except Exception as e:
                logger.warning(f"Topic extraction failed for batch: {e}")
                continue

        # Deduplicate topics (case-insensitive)
        seen: set[str] = set()
        unique_topics: list[str] = []
        for topic in all_topics:
            key = topic.lower().strip()
            if key not in seen:
                seen.add(key)
                unique_topics.append(topic.strip())

        return unique_topics

    def extract_concepts(
        self, chunks: list[Chunk], topics: list[str]
    ) -> list[Concept]:
        """Extract concepts with definitions from chunks given known topics.

        Processes chunks in batches, extracts concepts from each batch,
        then deduplicates across all batches.

        Args:
            chunks: List of document chunks to analyze.
            topics: Known topics to guide extraction.

        Returns:
            Deduplicated list of Concept instances.
        """
        if not chunks or not topics:
            return []

        all_concepts: list[Concept] = []
        topics_str = ", ".join(topics)

        for batch in self._batch_chunks(chunks):
            chunk_text = self._combine_chunk_text(batch)
            chunk_ids = [c.id for c in batch]
            prompt = CONCEPT_EXTRACTION_PROMPT.format(
                topics=topics_str, chunk_text=chunk_text
            )

            try:
                result, _usage = self.llm_client.generate_json(
                    prompt=prompt,
                    response_model=ConceptListResponse,
                    provider=self.provider,
                    temperature=0.3,
                    max_tokens=4096,
                )
                for concept_resp in result.concepts:
                    concept = self._response_to_concept(concept_resp, chunk_ids)
                    all_concepts.append(concept)
            except Exception as e:
                logger.warning(f"Concept extraction failed for batch: {e}")
                continue

        return self.deduplicate_concepts(all_concepts)

    def extract_batch(self, chunks: list[Chunk]) -> KnowledgeExtraction:
        """Full extraction pipeline: topics → concepts → relationships.

        Args:
            chunks: List of document chunks to process.

        Returns:
            KnowledgeExtraction with concepts and relationships populated.
        """
        if not chunks:
            return KnowledgeExtraction()

        # Step 1: Extract topics
        topics = self.extract_topics(chunks)
        logger.info(f"Extracted {len(topics)} topics")

        # Step 2: Extract concepts
        concepts = self.extract_concepts(chunks, topics)
        logger.info(f"Extracted {len(concepts)} concepts")

        # Step 3: Extract relationships between concepts
        relationships = self._extract_relationships(concepts)
        logger.info(f"Extracted {len(relationships)} relationships")

        return KnowledgeExtraction(
            concepts=concepts,
            relationships=relationships,
        )

    def deduplicate_concepts(self, concepts: list[Concept]) -> list[Concept]:
        """Merge duplicate concepts (same name, case-insensitive).

        When merging duplicates:
        - Keep the most complete definition (longest)
        - Merge keywords (deduplicated)
        - Merge source_chunk_ids (deduplicated)
        - Keep the first occurrence's other fields

        Args:
            concepts: List of concepts that may contain duplicates.

        Returns:
            Deduplicated list of concepts.
        """
        if not concepts:
            return []

        merged: dict[str, Concept] = {}

        for concept in concepts:
            key = concept.name.lower().strip()

            if key not in merged:
                merged[key] = concept
            else:
                existing = merged[key]
                # Keep the longer (more complete) definition
                if len(concept.definition) > len(existing.definition):
                    new_definition = concept.definition
                else:
                    new_definition = existing.definition

                # Merge keywords (deduplicated)
                all_keywords = list(
                    dict.fromkeys(existing.keywords + concept.keywords)
                )

                # Merge source_chunk_ids (deduplicated)
                all_chunk_ids = list(
                    dict.fromkeys(
                        existing.source_chunk_ids + concept.source_chunk_ids
                    )
                )

                # Merge topics (deduplicated)
                all_topics = list(
                    dict.fromkeys(existing.topics + concept.topics)
                )

                merged[key] = Concept(
                    id=existing.id,
                    name=existing.name,
                    definition=new_definition,
                    topics=all_topics,
                    difficulty=existing.difficulty,
                    prerequisites=existing.prerequisites,
                    keywords=all_keywords,
                    source_chunk_ids=all_chunk_ids,
                )

        return list(merged.values())

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _batch_chunks(self, chunks: list[Chunk]) -> list[list[Chunk]]:
        """Split chunks into batches of self.batch_size."""
        batches = []
        for i in range(0, len(chunks), self.batch_size):
            batches.append(chunks[i : i + self.batch_size])
        return batches

    def _combine_chunk_text(self, chunks: list[Chunk]) -> str:
        """Combine chunk contents into a single text block."""
        parts = []
        for chunk in chunks:
            parts.append(f"[Chunk {chunk.id}]:\n{chunk.content}")
        return "\n\n".join(parts)

    def _response_to_concept(
        self, resp: ConceptResponse, source_chunk_ids: list[str]
    ) -> Concept:
        """Convert an LLM ConceptResponse into a Concept model instance."""
        # Map difficulty string to enum
        difficulty_map = {
            "easy": Difficulty.EASY,
            "medium": Difficulty.MEDIUM,
            "hard": Difficulty.HARD,
        }
        difficulty = difficulty_map.get(
            resp.difficulty.lower(), Difficulty.MEDIUM
        )

        return Concept(
            id=f"concept-{uuid.uuid4().hex[:8]}",
            name=resp.name,
            definition=resp.definition,
            topics=resp.topics,
            difficulty=difficulty,
            prerequisites=resp.prerequisites,
            keywords=resp.keywords,
            source_chunk_ids=source_chunk_ids,
        )

    def _extract_relationships(
        self, concepts: list[Concept]
    ) -> list[ConceptRelationship]:
        """Extract relationships between extracted concepts using LLM.

        Args:
            concepts: List of concepts to find relationships between.

        Returns:
            List of ConceptRelationship instances.
        """
        if len(concepts) < 2:
            return []

        concept_names = [c.name for c in concepts]
        concept_id_map = {c.name.lower(): c.id for c in concepts}

        prompt = RELATIONSHIP_EXTRACTION_PROMPT.format(
            concept_names=", ".join(concept_names)
        )

        try:
            result, _usage = self.llm_client.generate_json(
                prompt=prompt,
                response_model=RelationshipListResponse,
                provider=self.provider,
                temperature=0.3,
            )
        except Exception as e:
            logger.warning(f"Relationship extraction failed: {e}")
            return []

        relationships: list[ConceptRelationship] = []
        for rel in result.relationships:
            source_id = concept_id_map.get(rel.source.lower())
            target_id = concept_id_map.get(rel.target.lower())

            if source_id and target_id and rel.relationship_type in {
                "prerequisite",
                "related",
                "part_of",
            }:
                relationships.append(
                    ConceptRelationship(
                        source_concept=source_id,
                        target_concept=target_id,
                        relationship_type=rel.relationship_type,
                    )
                )

        return relationships
