"""Chat Tutor Workflow for NeuroForge.

Implements a RAG-powered conversational tutor:
- question → retrieve relevant chunks → generate grounded answer
- Maintains conversation history (last 5 exchanges)
- Cites source chunk IDs in answers
- Handles follow-up questions using conversation context
- Handles out-of-scope questions gracefully
"""

from __future__ import annotations

import logging
from typing import Any

from src.llm import LLMClient
from src.retrieval.retriever import Retriever

logger = logging.getLogger("neuroforge.workflows.chat_tutor")

# Maximum number of exchanges (user + assistant pairs) to keep in memory
MAX_HISTORY_EXCHANGES = 5


class ChatTutor:
    """RAG-powered conversational tutor with memory.

    Orchestrates retrieval and generation to produce grounded answers
    that cite their sources. Maintains conversation history to handle
    follow-up questions naturally.

    Args:
        retriever: Initialized Retriever instance for knowledge lookup.
        llm_client: Initialized LLMClient instance for answer generation.
    """

    def __init__(self, retriever: Retriever, llm_client: LLMClient) -> None:
        """Initialize the ChatTutor.

        Args:
            retriever: Retriever instance with access to the knowledge base.
            llm_client: LLMClient instance for generating responses.
        """
        self.retriever = retriever
        self.llm_client = llm_client
        self._history: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(self, question: str) -> dict[str, Any]:
        """Ask the tutor a question and get a grounded answer.

        RAG pipeline: retrieve → generate → return answer with sources.

        Args:
            question: The user's question.

        Returns:
            Dict with keys:
                - "answer" (str): The generated answer with source citations.
                - "sources" (list[str]): Chunk IDs used as sources.
                - "is_grounded" (bool): Whether the answer is grounded in
                  retrieved material.
        """
        # Stage 1: Retrieve relevant chunks
        chunks = self._retrieve(question)
        source_ids = [chunk["id"] for chunk in chunks]

        # Stage 2: Generate answer using LLM with context
        answer, is_grounded = self._generate(question, chunks)

        # Stage 3: Store exchange in history
        self._add_to_history(question, answer)

        return {
            "answer": answer,
            "sources": source_ids,
            "is_grounded": is_grounded,
        }

    def reset(self) -> None:
        """Clear conversation history."""
        self._history = []

    @property
    def history(self) -> list[dict[str, str]]:
        """Return list of past exchanges.

        Returns:
            List of dicts with "role" and "content" keys.
        """
        return list(self._history)

    # ------------------------------------------------------------------
    # Pipeline Stages
    # ------------------------------------------------------------------

    def _retrieve(self, question: str) -> list[dict]:
        """Stage 1: Retrieve relevant chunks from the knowledge base.

        Uses conversation history to enrich the query for follow-up
        questions.
        """
        # Build an enriched query using recent history context
        enriched_query = self._build_retrieval_query(question)

        try:
            chunks = self.retriever.semantic_search(
                query=enriched_query, top_k=5
            )
        except Exception as e:
            logger.warning(f"Retrieval failed: {e}. Proceeding with no context.")
            chunks = []

        return chunks

    def _generate(
        self, question: str, chunks: list[dict]
    ) -> tuple[str, bool]:
        """Stage 2: Generate an answer grounded in retrieved chunks.

        Args:
            question: The user's question.
            chunks: Retrieved chunks to ground the answer in.

        Returns:
            Tuple of (answer_text, is_grounded).
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(question, chunks)

        try:
            response_text, _usage = self.llm_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.4,
                max_tokens=1024,
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return (
                "I'm sorry, I encountered an error generating a response. "
                "Please try again.",
                False,
            )

        # Determine if the answer is grounded based on chunk availability
        # and whether the LLM indicated out-of-scope
        is_grounded = len(chunks) > 0 and not self._is_out_of_scope(response_text)

        return response_text, is_grounded

    # ------------------------------------------------------------------
    # History Management
    # ------------------------------------------------------------------

    def _add_to_history(self, question: str, answer: str) -> None:
        """Add an exchange to conversation history, maintaining the limit."""
        self._history.append({"role": "user", "content": question})
        self._history.append({"role": "assistant", "content": answer})

        # Trim to last MAX_HISTORY_EXCHANGES exchanges (each exchange = 2 messages)
        max_messages = MAX_HISTORY_EXCHANGES * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]

    # ------------------------------------------------------------------
    # Prompt Construction
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the tutor persona."""
        return (
            "You are a knowledgeable and friendly tutor. Your role is to help "
            "students understand topics from their study materials.\n\n"
            "Rules:\n"
            "1. ONLY answer based on the provided source material. If the "
            "material doesn't cover the topic, say so clearly.\n"
            "2. Cite your sources using [Source: chunk_id] format at the end "
            "of relevant statements.\n"
            "3. Be conversational and acknowledge previous context from the "
            "conversation history.\n"
            "4. For follow-up questions, reference what was discussed before.\n"
            "5. If you cannot answer from the provided material, respond with: "
            "'I don't have information about that in the available study "
            "materials. This topic might not be covered in the current "
            "knowledge base.'\n"
            "6. Keep answers concise but thorough."
        )

    def _build_user_prompt(self, question: str, chunks: list[dict]) -> str:
        """Build the user prompt with context and conversation history."""
        parts: list[str] = []

        # Add conversation history for context
        if self._history:
            parts.append("=== Conversation History ===")
            # Include recent history for follow-up context
            recent = self._history[-(MAX_HISTORY_EXCHANGES * 2):]
            for msg in recent:
                role_label = "Student" if msg["role"] == "user" else "Tutor"
                parts.append(f"{role_label}: {msg['content']}")
            parts.append("")

        # Add retrieved source material
        if chunks:
            parts.append("=== Source Material ===")
            for chunk in chunks:
                chunk_id = chunk.get("id", "unknown")
                content = chunk.get("content", "")
                if content:
                    parts.append(f"[{chunk_id}]: {content}")
            parts.append("")
        else:
            parts.append("=== Source Material ===")
            parts.append("No relevant material found in the knowledge base.")
            parts.append("")

        # Add the current question
        parts.append(f"=== Current Question ===")
        parts.append(f"Student: {question}")
        parts.append("")
        parts.append(
            "Please answer the student's question using ONLY the source "
            "material above. Cite sources using [Source: chunk_id] format."
        )

        return "\n".join(parts)

    def _build_retrieval_query(self, question: str) -> str:
        """Enrich the question with conversation context for better retrieval.

        For follow-up questions that might be short or use pronouns,
        combines recent context with the current question.
        """
        if not self._history:
            return question

        # Get the last exchange for context
        recent_messages = self._history[-4:]  # Last 2 exchanges
        context_parts = []
        for msg in recent_messages:
            if msg["role"] == "user":
                context_parts.append(msg["content"])

        # Combine recent user questions with current question
        if context_parts:
            context_summary = " ".join(context_parts[-2:])
            return f"{context_summary} {question}"

        return question

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_out_of_scope(response: str) -> bool:
        """Detect if the response indicates the topic is out of scope.

        Looks for phrases that indicate the material doesn't cover the topic.
        """
        out_of_scope_indicators = [
            "don't have information about that",
            "not covered in the current",
            "not be covered in",
            "no relevant material",
            "outside the scope",
            "not available in the study materials",
            "cannot find information",
        ]
        response_lower = response.lower()
        return any(indicator in response_lower for indicator in out_of_scope_indicators)
