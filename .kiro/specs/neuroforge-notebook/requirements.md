# NeuroForge — Notebook-First Development Requirements

## Overview

Build the complete NeuroForge adaptive learning engine as a series of Jupyter notebooks, proving each pipeline phase before extracting into production modules. Use free-tier LLMs and tools wherever possible.

---

## Functional Requirements

### FR-1: Document Ingestion Layer
- **FR-1.1**: Accept PDF files and extract text with layout awareness (PyMuPDF/pdfplumber)
- **FR-1.2**: Accept PPTX files and extract text + speaker notes (python-pptx)
- **FR-1.3**: Accept DOCX files and extract text with heading structure (python-docx)
- **FR-1.4**: Accept images and extract text via OCR (PaddleOCR or Tesseract — both free)
- **FR-1.5**: Accept YouTube URLs and extract transcripts (youtube-transcript-api, free)
- **FR-1.6**: Accept plain text and markdown directly
- **FR-1.7**: Detect input format automatically based on file extension or URL pattern
- **FR-1.8**: Return a unified `Document` object with text, metadata (source, pages, timestamps), and structure hints

### FR-2: Document Understanding & Normalization
- **FR-2.1**: Clean extracted text — remove headers/footers, page numbers, garbage characters
- **FR-2.2**: Chunk documents intelligently — respect paragraph/section boundaries, not just token count
- **FR-2.3**: Preserve document structure (headings, lists, tables) in chunk metadata
- **FR-2.4**: Support configurable chunk sizes (default ~500 tokens with 50-token overlap)
- **FR-2.5**: Generate a document-level summary using LLM

### FR-3: Knowledge Extraction
- **FR-3.1**: Extract topics and subtopics from chunks using LLM
- **FR-3.2**: Extract definitions, key terms, and their explanations
- **FR-3.3**: Extract formulae, equations, and their contexts
- **FR-3.4**: Extract examples and illustrations
- **FR-3.5**: Extract important dates, people, and events
- **FR-3.6**: Identify concept relationships (prerequisite, related-to, part-of)
- **FR-3.7**: Assign difficulty levels (Easy, Medium, Hard) to each concept
- **FR-3.8**: Identify prerequisites for each topic
- **FR-3.9**: Output structured JSON for each extracted element

### FR-4: Knowledge Store
- **FR-4.1**: Store document chunks as vector embeddings in ChromaDB (free, local)
- **FR-4.2**: Store structured metadata (topic, difficulty, chapter, estimated_time, concepts) alongside embeddings
- **FR-4.3**: Store concept relationships as a lightweight graph (NetworkX for dev — free)
- **FR-4.4**: Store document-level and chunk-level summaries
- **FR-4.5**: Store extracted keywords per chunk
- **FR-4.6**: Support retrieval by topic, difficulty, concept, or semantic similarity
- **FR-4.7**: Use free embedding models — HuggingFace sentence-transformers (all-MiniLM-L6-v2) or Nomic Embed

### FR-5: Planner (Intent Router)
- **FR-5.1**: Accept user intent (quiz, flashcard, notes, explain, compare, roadmap, mind map)
- **FR-5.2**: Route to the appropriate specialized workflow
- **FR-5.3**: Accept optional parameters — topic filter, difficulty preference, number of items
- **FR-5.4**: Implement as a LangGraph state machine

### FR-6: Specialized Workflows

#### FR-6.1: Quiz Generation
- **FR-6.1.1**: Retrieve relevant concepts from knowledge store based on topic/difficulty
- **FR-6.1.2**: Generate MCQ questions with 4 options
- **FR-6.1.3**: Generate short-answer questions
- **FR-6.1.4**: Generate true/false questions
- **FR-6.1.5**: Include explanations for correct answers
- **FR-6.1.6**: Tag each question with topic, difficulty, and concept
- **FR-6.1.7**: Support configurable quiz length (default 10 questions)

#### FR-6.2: Flashcard Generation
- **FR-6.2.1**: Generate question-answer flashcards from concepts
- **FR-6.2.2**: Include hints for difficult cards
- **FR-6.2.3**: Include mnemonics where applicable
- **FR-6.2.4**: Link related topics for cross-referencing
- **FR-6.2.5**: Support spaced repetition metadata (ease factor, interval, next review)

#### FR-6.3: Solution Generation
- **FR-6.3.1**: Accept a question/topic and marks allocation
- **FR-6.3.2**: Scale answer depth based on marks (2-mark = brief, 10-mark = detailed)
- **FR-6.3.3**: Include relevant diagrams/structure hints
- **FR-6.3.4**: Include marking scheme breakdown

#### FR-6.4: Revision Notes
- **FR-6.4.1**: Generate concise bullet-point summaries per topic
- **FR-6.4.2**: Highlight key terms and definitions
- **FR-6.4.3**: Include formulae and mnemonics
- **FR-6.4.4**: Organize hierarchically (topic → subtopic → points)

#### FR-6.5: Mind Map Generation
- **FR-6.5.1**: Generate hierarchical concept maps from extracted relationships
- **FR-6.5.2**: Output as structured JSON (nodes + edges) for visualization
- **FR-6.5.3**: Support filtering by topic or chapter

#### FR-6.6: Additional Information
- **FR-6.6.1**: Generate real-world applications for each concept
- **FR-6.6.2**: Generate industry use cases
- **FR-6.6.3**: Generate common mistakes and misconceptions
- **FR-6.6.4**: Generate interview questions per topic

#### FR-6.7: Chat Tutor
- **FR-6.7.1**: Accept free-form questions about the material
- **FR-6.7.2**: Retrieve relevant context from knowledge store (RAG)
- **FR-6.7.3**: Generate grounded answers citing source material
- **FR-6.7.4**: Maintain conversation history within a session

### FR-7: User Learning Memory
- **FR-7.1**: Track quiz scores per topic
- **FR-7.2**: Identify weak topics (score < 60%) and strong topics (score > 85%)
- **FR-7.3**: Adjust quiz difficulty based on performance history
- **FR-7.4**: Track flashcard review history (spaced repetition)
- **FR-7.5**: Generate personalized revision recommendations
- **FR-7.6**: Store learning state persistently (JSON or SQLite for notebook phase)

### FR-8: Multi-Agent Orchestration
- **FR-8.1**: Implement Planner Agent — routes intent
- **FR-8.2**: Implement Document Agent — handles ingestion and knowledge extraction
- **FR-8.3**: Implement Teacher Agent — explains concepts
- **FR-8.4**: Implement Examiner Agent — creates quizzes and assessments
- **FR-8.5**: Implement Reviewer Agent — validates output quality
- **FR-8.6**: Implement Memory Agent — updates learning progress
- **FR-8.7**: Orchestrate agents using LangGraph

---

## Non-Functional Requirements

### NFR-1: Cost
- All LLM calls must use free-tier APIs: Groq (Llama 4 Scout, Gemma 2), OpenRouter free models (Mistral Small 3.2), or GitHub Models (GPT-4.1-nano)
- Embeddings must be free: local sentence-transformers or Nomic Embed free tier
- Vector DB must be free and local: ChromaDB
- No paid services required for notebook development

### NFR-2: Performance
- Document ingestion for a 50-page PDF should complete within 60 seconds
- Quiz generation should return results within 15 seconds
- Flashcard generation should return results within 10 seconds
- Chat tutor response should return within 5 seconds

### NFR-3: Quality
- Generated quizzes must have factually correct answers grounded in source material
- Flashcards must be concise (answers 1-10 words)
- Solutions must scale appropriately with marks
- All outputs must cite source chunks

### NFR-4: Modularity
- Each notebook must be self-contained and runnable independently
- Code must be organized for easy extraction into Python modules later
- Use consistent data models (Pydantic) across all notebooks

### NFR-5: Observability
- Log all LLM calls with input/output for debugging
- Track token usage per call
- Use LangSmith free tier for tracing (optional but recommended)

---

## Technology Choices (All Free)

| Component | Tool | Why |
|-----------|------|-----|
| LLM (primary) | Groq API — Llama 4 Scout 17B | Free, fast inference, good quality |
| LLM (fallback) | OpenRouter — Mistral Small 3.2 24B | Free tier, good at structured output |
| LLM (lightweight) | GitHub Models — GPT-4.1-nano | Free, good for classification tasks |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Free, local, no API calls |
| Vector DB | ChromaDB | Free, local, Python-native |
| Graph | NetworkX | Free, in-memory, good for dev |
| Workflow | LangGraph | Free, Python, state machines |
| LLM Framework | LangChain | Free, integrates with everything |
| OCR | PaddleOCR or Tesseract | Both free and local |
| YouTube | youtube-transcript-api | Free, no API key needed |
| Notebooks | Jupyter | Free |
| Data Models | Pydantic | Free, type-safe |
| Observability | LangSmith free tier | 5000 traces/month free |
