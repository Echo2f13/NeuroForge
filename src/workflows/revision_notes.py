"""Revision Notes Workflow for NeuroForge.

Implements a sequential pipeline (retrieve → generate → format) that produces
hierarchical revision notes for a given topic. Uses the Retriever to fetch
relevant content chunks and the LLMClient to generate structured notes
validated against Pydantic models.
"""

from __future__ import annotations

import logging
from typing import Optional

from models.output import RevisionNote, SubtopicNote
from src.llm import LLMClient, LLMProvider
from src.retrieval import Retriever

logger = logging.getLogger("neuroforge.workflows.revision_notes")


# ---------------------------------------------------------------------------
# Prompt Template
# ---------------------------------------------------------------------------

REVISION_NOTES_SYSTEM_PROMPT = """\
You are an expert study assistant that creates comprehensive, hierarchical \
revision notes. Your notes should be well-organized, concise, and optimized \
for exam preparation and quick review.

Guidelines:
- Organize content as topic → subtopics → bullet points
- Highlight key terms and their definitions
- Include relevant formulae with clear notation
- Provide mnemonics or memory aids where helpful
- Assign importance levels (high/medium/low) to each subtopic
- Keep bullet points concise but informative
- Focus on exam-relevant content
"""

REVISION_NOTES_USER_PROMPT = """\
Create detailed hierarchical revision notes for the topic: "{topic}"

Use the following source material to inform your notes:

---
{context}
---

Generate revision notes with:
1. Multiple subtopics, each with:
   - A clear title
   - Concise bullet points covering key information
   - An importance level (high, medium, or low)
2. A list of key terms with brief definitions
3. Relevant formulae (use plain text notation)
4. Helpful mnemonics or memory aids

Respond with valid JSON only.
"""


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class RevisionNotesWorkflow:
    """Sequential workflow for generating hierarchical revision notes.

    Pipeline: retrieve relevant chunks → generate notes via LLM → validate output.

    Args:
        retriever: Retriever instance for fetching relevant content.
        llm_client: LLMClient instance for generating notes.
        top_k: Number of chunks to retrieve for context.
        provider: Preferred LLM provider (optional).
    """

    def __init__(
        self,
        retriever: Retriever,
        llm_client: LLMClient,
        top_k: int = 8,
        provider: Optional[LLMProvider] = None,
    ) -> None:
        """Initialize the revision notes workflow.

        Args:
            retriever: Retriever instance for semantic/hybrid search.
            llm_client: LLMClient for structured generation.
            top_k: Number of context chunks to retrieve.
            provider: Preferred LLM provider.
        """
        self.retriever = retriever
        self.llm_client = llm_client
        self.top_k = top_k
        self.provider = provider

    def generate(self, topic: str) -> RevisionNote:
        """Generate hierarchical revision notes for a topic.

        Pipeline steps:
        1. Retrieve: Fetch relevant chunks using hybrid retrieval.
        2. Generate: Prompt the LLM for structured revision notes.
        3. Format: Validate output against RevisionNote Pydantic model.

        Args:
            topic: The topic to generate revision notes for.

        Returns:
            A validated RevisionNote instance with subtopics, key terms,
            formulae, and mnemonics.

        Raises:
            LLMError: If all LLM providers fail.
            JSONParsingError: If the LLM output cannot be parsed.
        """
        logger.info(f"Generating revision notes for topic: {topic}")

        # Step 1: Retrieve relevant context
        context = self._retrieve_context(topic)
        logger.info(f"Retrieved {len(context)} chunks for context")

        # Step 2: Generate structured notes via LLM
        revision_note = self._generate_notes(topic, context)
        logger.info(
            f"Generated notes with {len(revision_note.subtopics)} subtopics"
        )

        return revision_note

    def _retrieve_context(self, topic: str) -> str:
        """Retrieve and format relevant chunks for the topic.

        Uses hybrid retrieval to combine semantic and graph-based results.

        Args:
            topic: The topic to search for.

        Returns:
            Concatenated text from retrieved chunks.
        """
        results = self.retriever.hybrid_retrieval(
            query=topic, top_k=self.top_k
        )

        if not results:
            # Fall back to semantic search if hybrid returns nothing
            results = self.retriever.semantic_search(
                query=topic, top_k=self.top_k
            )

        # Format chunks into context string
        context_parts: list[str] = []
        for i, chunk in enumerate(results, 1):
            content = chunk.get("content", "").strip()
            if content:
                context_parts.append(f"[{i}] {content}")

        return "\n\n".join(context_parts) if context_parts else f"Topic: {topic}"

    def _generate_notes(self, topic: str, context: str) -> RevisionNote:
        """Generate revision notes using the LLM client.

        Args:
            topic: The topic name.
            context: Retrieved context text.

        Returns:
            Validated RevisionNote instance.
        """
        user_prompt = REVISION_NOTES_USER_PROMPT.format(
            topic=topic, context=context
        )

        revision_note, usage = self.llm_client.generate_json(
            prompt=user_prompt,
            response_model=RevisionNote,
            system_prompt=REVISION_NOTES_SYSTEM_PROMPT,
            provider=self.provider,
            temperature=0.5,
            max_tokens=4096,
        )

        logger.info(
            f"LLM usage: {usage.get('total_tokens', 0)} tokens, "
            f"provider: {usage.get('provider', 'unknown')}"
        )

        return revision_note
