"""NeuroForge — Robust Knowledge Extraction.

A more reliable extraction system that:
- Uses simpler, more focused prompts
- Extracts fewer items per call (better JSON reliability)
- Has multiple fallback parsing strategies
- Handles partial failures gracefully
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from models import Chunk, Concept, ConceptRelationship, Difficulty, KnowledgeExtraction
from src.llm import LLMClient, LLMProvider

logger = logging.getLogger("neuroforge.extraction.robust")


# ---------------------------------------------------------------------------
# Simpler response models (more reliable JSON generation)
# ---------------------------------------------------------------------------

class SimpleConcept(BaseModel):
    """Simplified concept for more reliable extraction."""
    name: str
    definition: str
    difficulty: str = "medium"
    keywords: list[str] = Field(default_factory=list)


class SimpleConceptList(BaseModel):
    """List of simplified concepts."""
    concepts: list[SimpleConcept] = Field(default_factory=list)


class SimpleRelationship(BaseModel):
    """Simplified relationship."""
    source: str
    target: str
    type: str = "related"


class SimpleRelationshipList(BaseModel):
    """List of relationships."""
    relationships: list[SimpleRelationship] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Simpler, more focused prompts
# ---------------------------------------------------------------------------

CONCEPT_PROMPT = """Extract 3-5 key concepts from this educational text.

TEXT:
{text}

For each concept provide:
- name: Short name (2-5 words)
- definition: One clear sentence
- difficulty: "easy", "medium", or "hard"
- keywords: 2-3 related terms

Respond with ONLY valid JSON:
{{"concepts": [{{"name": "Example", "definition": "A clear definition.", "difficulty": "medium", "keywords": ["term1", "term2"]}}]}}
"""

RELATIONSHIP_PROMPT = """Given these concepts, identify relationships between them.

CONCEPTS: {concepts}

Types: "prerequisite" (A needed before B), "related" (connected), "part_of" (A is subset of B)

Respond with ONLY valid JSON:
{{"relationships": [{{"source": "Concept A", "target": "Concept B", "type": "related"}}]}}
"""


# ---------------------------------------------------------------------------
# JSON Parsing Utilities
# ---------------------------------------------------------------------------

def extract_json_from_text(text: str) -> Optional[dict]:
    """Try multiple strategies to extract JSON from LLM response."""
    
    # Strategy 1: Direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Remove markdown code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        cleaned = "\n".join(lines)
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Find JSON object in text
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Strategy 4: Find JSON array in text
    array_match = re.search(r'\[[\s\S]*\]', text)
    if array_match:
        try:
            arr = json.loads(array_match.group())
            # Wrap in expected format
            if arr and isinstance(arr[0], dict):
                if "name" in arr[0]:
                    return {"concepts": arr}
                elif "source" in arr[0]:
                    return {"relationships": arr}
        except json.JSONDecodeError:
            pass
    
    return None


def parse_concepts_flexible(text: str) -> list[SimpleConcept]:
    """Flexibly parse concepts from LLM response."""
    data = extract_json_from_text(text)
    if not data:
        return []
    
    concepts = data.get("concepts", [])
    if not concepts and isinstance(data, list):
        concepts = data
    
    result = []
    for c in concepts:
        if isinstance(c, dict) and "name" in c:
            try:
                result.append(SimpleConcept(
                    name=c.get("name", "Unknown"),
                    definition=c.get("definition", c.get("name", "")),
                    difficulty=c.get("difficulty", "medium"),
                    keywords=c.get("keywords", [])
                ))
            except Exception:
                continue
    
    return result


def parse_relationships_flexible(text: str) -> list[SimpleRelationship]:
    """Flexibly parse relationships from LLM response."""
    data = extract_json_from_text(text)
    if not data:
        return []
    
    rels = data.get("relationships", [])
    if not rels and isinstance(data, list):
        rels = data
    
    result = []
    for r in rels:
        if isinstance(r, dict) and "source" in r and "target" in r:
            try:
                result.append(SimpleRelationship(
                    source=r["source"],
                    target=r["target"],
                    type=r.get("type", r.get("relationship_type", "related"))
                ))
            except Exception:
                continue
    
    return result


# ---------------------------------------------------------------------------
# Robust Extractor
# ---------------------------------------------------------------------------

class RobustExtractor:
    """More reliable knowledge extraction with better error handling.
    
    Key improvements over TopicExtractor:
    - Simpler prompts that produce more reliable JSON
    - Multiple JSON parsing fallback strategies  
    - Extracts fewer items per call (3-5 vs unlimited)
    - Better handling of partial failures
    - Detailed logging for debugging
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        provider: Optional[LLMProvider] = None,
        max_concepts_per_batch: int = 5,
    ):
        self.llm_client = llm_client
        self.provider = provider
        self.max_concepts_per_batch = max_concepts_per_batch
    
    def extract(self, chunks: list[Chunk]) -> KnowledgeExtraction:
        """Extract concepts and relationships from chunks.
        
        Args:
            chunks: Document chunks to process.
            
        Returns:
            KnowledgeExtraction with concepts and relationships.
        """
        if not chunks:
            return KnowledgeExtraction()
        
        logger.info(f"Starting extraction from {len(chunks)} chunks")
        
        # Process chunks in small batches for reliability
        all_concepts: list[Concept] = []
        batch_size = 3  # Small batches for better JSON reliability
        
        for i in range(0, min(len(chunks), 15), batch_size):  # Limit to first 15 chunks
            batch = chunks[i:i + batch_size]
            batch_text = "\n\n".join([c.content[:1500] for c in batch])  # Limit text size
            chunk_ids = [c.id for c in batch]
            
            concepts = self._extract_concepts(batch_text, chunk_ids)
            all_concepts.extend(concepts)
            logger.info(f"Batch {i//batch_size + 1}: extracted {len(concepts)} concepts")
        
        # Deduplicate concepts
        unique_concepts = self._deduplicate_concepts(all_concepts)
        logger.info(f"Total unique concepts: {len(unique_concepts)}")
        
        # Extract relationships between concepts
        relationships = []
        if len(unique_concepts) >= 2:
            relationships = self._extract_relationships(unique_concepts)
            logger.info(f"Extracted {len(relationships)} relationships")
        
        return KnowledgeExtraction(
            concepts=unique_concepts,
            relationships=relationships,
        )
    
    def _extract_concepts(self, text: str, chunk_ids: list[str]) -> list[Concept]:
        """Extract concepts from a text block."""
        prompt = CONCEPT_PROMPT.format(text=text[:4000])  # Limit prompt size
        
        try:
            response, _usage = self.llm_client.generate(
                prompt=prompt,
                system_prompt="You are a knowledge extraction assistant. Output ONLY valid JSON.",
                provider=self.provider,
                temperature=0.2,  # Lower temperature for more consistent output
                max_tokens=1500,
            )
            
            simple_concepts = parse_concepts_flexible(response)
            
            return [
                self._to_concept(sc, chunk_ids)
                for sc in simple_concepts
            ]
            
        except Exception as e:
            logger.warning(f"Concept extraction failed: {e}")
            return []
    
    def _extract_relationships(self, concepts: list[Concept]) -> list[ConceptRelationship]:
        """Extract relationships between concepts."""
        if len(concepts) < 2:
            return []
        
        # Limit to first 20 concepts for relationship extraction
        concept_names = [c.name for c in concepts[:20]]
        concept_id_map = {c.name.lower(): c.id for c in concepts}
        
        prompt = RELATIONSHIP_PROMPT.format(concepts=", ".join(concept_names))
        
        try:
            response, _usage = self.llm_client.generate(
                prompt=prompt,
                system_prompt="You are a knowledge extraction assistant. Output ONLY valid JSON.",
                provider=self.provider,
                temperature=0.2,
                max_tokens=1500,
            )
            
            simple_rels = parse_relationships_flexible(response)
            
            relationships = []
            for rel in simple_rels:
                source_id = concept_id_map.get(rel.source.lower())
                target_id = concept_id_map.get(rel.target.lower())
                
                if source_id and target_id:
                    rel_type = rel.type.lower()
                    if rel_type not in {"prerequisite", "related", "part_of"}:
                        rel_type = "related"
                    
                    relationships.append(ConceptRelationship(
                        source_concept=source_id,
                        target_concept=target_id,
                        relationship_type=rel_type,
                    ))
            
            return relationships
            
        except Exception as e:
            logger.warning(f"Relationship extraction failed: {e}")
            return []
    
    def _to_concept(self, simple: SimpleConcept, chunk_ids: list[str]) -> Concept:
        """Convert SimpleConcept to full Concept model."""
        difficulty_map = {
            "easy": Difficulty.EASY,
            "medium": Difficulty.MEDIUM,
            "hard": Difficulty.HARD,
        }
        
        return Concept(
            id=f"concept-{uuid.uuid4().hex[:8]}",
            name=simple.name,
            definition=simple.definition,
            topics=[],  # Will be inferred from chunk metadata
            difficulty=difficulty_map.get(simple.difficulty.lower(), Difficulty.MEDIUM),
            prerequisites=[],
            keywords=simple.keywords,
            source_chunk_ids=chunk_ids,
        )
    
    def _deduplicate_concepts(self, concepts: list[Concept]) -> list[Concept]:
        """Remove duplicate concepts, keeping the most complete version."""
        if not concepts:
            return []
        
        merged: dict[str, Concept] = {}
        
        for concept in concepts:
            key = concept.name.lower().strip()
            
            if key not in merged:
                merged[key] = concept
            else:
                existing = merged[key]
                # Keep longer definition
                if len(concept.definition) > len(existing.definition):
                    new_def = concept.definition
                else:
                    new_def = existing.definition
                
                # Merge keywords and chunk IDs
                all_keywords = list(dict.fromkeys(existing.keywords + concept.keywords))
                all_chunk_ids = list(dict.fromkeys(
                    existing.source_chunk_ids + concept.source_chunk_ids
                ))
                
                merged[key] = Concept(
                    id=existing.id,
                    name=existing.name,
                    definition=new_def,
                    topics=list(dict.fromkeys(existing.topics + concept.topics)),
                    difficulty=existing.difficulty,
                    prerequisites=existing.prerequisites,
                    keywords=all_keywords,
                    source_chunk_ids=all_chunk_ids,
                )
        
        return list(merged.values())
