# Implementation Plan

## Overview

Build the complete NeuroForge adaptive learning engine as a series of Jupyter notebooks (17 total), proving each pipeline phase before extracting into production modules. All tools and APIs are free/open-source. Tasks are ordered by dependency — each phase builds on the previous.

## Tasks

- [x] 1. Environment Setup — Create `notebooks/00_setup.ipynb`. Install and validate all dependencies (langchain, langgraph, chromadb, sentence-transformers, pdfplumber, python-pptx, python-docx, paddleocr, youtube-transcript-api, groq, networkx, pydantic). Create `.env` template with API keys (GROQ_API_KEY, OPENROUTER_API_KEY, GITHUB_TOKEN). Validate each API connection with a test call. Validate local tools load correctly. Create `requirements.txt`. Document free-tier limits.
- [x] 2. Data Models — Create `models/` directory. Implement all Pydantic models from design doc: Document, DocumentMetadata, Section, Chunk, ChunkMetadata, Concept, ConceptRelationship, KnowledgeExtraction, Formula, Example, KeyDate, KeyPerson, QuizQuestion, Flashcard, Solution, RevisionNote, SubtopicNote, MindMap, MindMapNode, TopicProgress, LearningState. Add validation rules and serialization helpers.
- [x] 3. LLM Provider Abstraction — Create unified LLM client supporting Groq (Llama 4 Scout 17B), OpenRouter (Mistral Small 3.2 24B free), and GitHub Models (GPT-4.1-nano). Implement provider fallback chain with exponential backoff. Implement structured JSON output parsing with retry. Add logging for all calls (model, tokens, latency). Test across all three providers.
- [x] 4. PDF Loader — Create `notebooks/01_document_ingestion.ipynb`. Implement PDF text extraction using pdfplumber with PyMuPDF fallback. Extract page-level text with page numbers. Extract heading structure from font sizes. Handle multi-column layouts. Detect scanned PDFs and route to OCR. Test with sample PDFs.
- [x] 5. PPTX Loader — Implement PPTX extraction using python-pptx. Extract slide text (titles, bullets, text boxes), speaker notes. Maintain slide ordering. Handle embedded images. Test with sample presentations.
- [x] 6. DOCX Loader — Implement DOCX extraction using python-docx. Extract text with heading hierarchy. Extract tables as structured text. Extract lists with nesting. Test with sample documents.
- [x] 7. Image/OCR Loader — Implement OCR using PaddleOCR (Tesseract fallback). Support PNG, JPG, JPEG, BMP, TIFF. Handle handwritten text best-effort. Note diagram presence in metadata. Test with whiteboard photos and textbook scans.
- [x] 8. YouTube Transcript Loader — Implement transcript extraction using youtube-transcript-api. Handle auto-generated and manual captions. Extract video metadata (title, duration). Add timestamps as structure markers. Handle unavailable transcripts gracefully. Test with educational videos.
- [x] 9. Plain Text & Markdown Loader — Implement direct text ingestion. Parse markdown structure (headings, lists, code blocks). Detect and preserve code snippets. Test with sample files.
- [x] 10. Format Detection & Unified Interface — Implement automatic format detection (extension, URL pattern, MIME type). Create unified `ingest(source) -> Document` function. Handle errors gracefully. Test with mix of all formats.
- [x] 11. Text Cleaning — Create `notebooks/02_text_processing.ipynb`. Remove headers/footers, page numbers, garbage characters. Fix OCR artifacts. Normalize whitespace. Preserve meaningful formatting (bullets, numbered lists). Test on noisy and clean outputs.
- [x] 12. Intelligent Chunking — Implement section-aware chunking (split at headings first). Implement paragraph-aware chunking. Token-based chunking with configurable size (default 500 tokens, 50 overlap). Assign chunk IDs, maintain ordering. Preserve metadata per chunk. Compare strategies on sample documents.
- [x] 13. Structure Extraction — Detect document structure (TOC, sections, subsections). Build section tree from headings. Identify tables and lists with nesting. Identify code blocks. Preserve in chunk metadata.
- [x] 14. Topic & Concept Extraction — Create `notebooks/03_knowledge_extraction.ipynb`. Design prompts for topic/subtopic extraction and concept/definition extraction. Implement batch processing. Deduplicate concepts across chunks. Validate JSON output matches Concept model. Test extraction quality.
- [x] 15. Relationship Extraction — Design prompt for relationship extraction (prerequisite, part-of, related-to). Build relationship graph from extracted pairs. Validate no circular prerequisites. Test and visualize relationships.
- [x] 16. Difficulty & Metadata Assignment — Design prompt for difficulty classification (Easy/Medium/Hard). Estimate study time per concept. Extract keywords per chunk (top 5-10). Generate chunk-level summaries (1-2 sentences). Generate document-level summary. Test assignments.
- [x] 17. Formula, Example, Date, People Extraction — Design prompts for each type. Extract formulae with context. Extract examples with related concepts. Extract dates with significance. Extract people with contributions. Link to source chunk IDs. Test on varied material.
- [ ] 18. ChromaDB Setup & Storage — Create `notebooks/04_knowledge_store.ipynb`. Initialize persistent ChromaDB client (./chroma_db/). Create `document_chunks` collection with sentence-transformers (all-MiniLM-L6-v2) embedding function. Create `concepts` collection. Implement chunk and concept insertion with metadata. Batch insertion. Verify persistence across sessions.
- [ ] 19. NetworkX Knowledge Graph — Create NetworkX directed graph. Add concept nodes with attributes (difficulty, definition, topics). Add relationship edges. Implement graph serialization (save/load JSON). Implement queries (prerequisites, related concepts). Visualize sample topic. Test integrity.
- [ ] 20. Retrieval Implementation — Create `notebooks/05_retrieval.ipynb`. Implement semantic search (query → top-k chunks). Implement metadata-filtered search (topic, difficulty, chapter). Implement graph-based retrieval (concept + prerequisites + related). Implement hybrid retrieval. Optional re-ranking. Test quality, tune thresholds.
- [ ] 21. Quiz Generation — Create `notebooks/06_quiz_generation.ipynb`. Design quiz prompt (concepts → questions). Implement MCQ (4 options), short-answer, true/false generation. Difficulty-aware and topic-filtered. Configurable length. Validate correct answers. Implement as LangGraph workflow (retrieve → generate → validate → format). Test various topics.
- [ ] 22. Flashcard Generation — Create `notebooks/07_flashcard_generation.ipynb`. Design flashcard prompt (concept → concise Q/A). Generate cards with hints and mnemonics. Link related topics. Add spaced repetition metadata. Implement as LangGraph workflow. Test conciseness (1-10 word answers).
- [ ] 23. Solution Generation — Create `notebooks/08_solution_generation.ipynb`. Design solution prompt with marks-based depth control. Implement depth scaling (2-mark brief to 10-mark detailed). Include marking scheme and key points. Implement as LangGraph workflow. Test various marks.
- [ ] 24. Revision Notes Generation — Create `notebooks/09_revision_notes.ipynb`. Design revision notes prompt (hierarchical bullets). Per-topic summaries. Highlight key terms, formulae, mnemonics. Organize hierarchically (topic → subtopic → points). Implement as LangGraph workflow. Test readability.
- [ ] 25. Mind Map Generation — Create `notebooks/10_mind_map.ipynb`. Extract concept hierarchy from knowledge graph. Generate node-edge JSON structure. Topic-level filtering and depth control. Visualize with matplotlib or pyvis. Implement as LangGraph workflow. Test complex topics.
- [ ] 26. Additional Information — Create `notebooks/11_additional_info.ipynb`. Design prompts for real-world applications, industry uses, common mistakes, interview questions. Generate per-topic. Implement as LangGraph workflow. Test relevance and accuracy.
- [ ] 27. Chat Tutor (RAG) — Create `notebooks/12_chat_tutor.ipynb`. Implement RAG pipeline (question → retrieve → generate grounded answer). Maintain conversation history (last 5 exchanges). Cite sources. Handle follow-ups and out-of-scope. Implement as LangGraph workflow with memory. Test conversational flows.
- [ ] 28. Progress Tracking — Create `notebooks/13_learning_memory.ipynb`. Record quiz scores per topic. Calculate running averages and mastery levels. Identify weak (<60%) and strong (>85%) topics. Track attempts and time. Store state in JSON file. Test with simulated sequences.
- [ ] 29. Adaptive Difficulty — Implement difficulty adjustment (mastery <40% → easier, 40-70% → maintain, >70% → harder). Feed preference into quiz/flashcard generation. Test adaptation over multiple rounds.
- [ ] 30. Spaced Repetition — Implement SM-2 algorithm for flashcard scheduling. Track ease factor, interval, next review date per card. Generate review queue (cards due today). Update stats after review. Test over simulated days.
- [ ] 31. Personalized Recommendations — Generate study recommendations from weak topics. Suggest next topics by prerequisite completion. Suggest revision timing from spaced repetition. Test with various learning states.
- [ ] 32. Planner (Intent Router) — Create `notebooks/14_planner_orchestrator.ipynb`. Design intent classification prompt. Detect intent (quiz, flashcard, notes, explain, compare, roadmap, mind map, chat). Extract parameters (topic, difficulty, count, marks). Implement LangGraph orchestrator. Route to workflows. Test natural language inputs.
- [ ] 33. Multi-Agent System — Create `notebooks/15_multi_agent.ipynb`. Implement Planner, Document, Teacher, Examiner, Reviewer, and Memory agents. Wire together using LangGraph. Test multi-agent collaboration on full workflow.
- [ ] 34. End-to-End Demo — Create `notebooks/16_end_to_end_demo.ipynb`. Demo: PDF → knowledge → quiz. Demo: YouTube → flashcards. Demo: chat tutor Q&A. Demo: quiz → progress → recommendations. Demo: revision notes for weak topics. Verify all components work together. Document issues.
- [ ] 35. Code Organization — Extract shared utilities into `src/` modules: models.py, llm.py, ingestion.py, processing.py, extraction.py, store.py, retrieval.py, workflows/, memory.py. Ensure notebooks import from `src/` cleanly.
- [ ] 36. Testing & Validation — Test full pipeline with 3+ document types. Validate quiz, flashcard, and retrieval quality. Document limitations and edge cases. Performance benchmarks (50-page PDF timing).
- [ ] 37. Documentation — Update README with notebook descriptions and running instructions. Document API key setup. Document free-tier limits. Create sample test material in `test_data/`. Document architecture decisions.

## Notes

- All LLM providers are free-tier: Groq (Llama 4 Scout 17B), OpenRouter (Mistral Small 3.2 24B free), GitHub Models (GPT-4.1-nano)
- All embeddings are local and free: sentence-transformers (all-MiniLM-L6-v2)
- Vector DB is free and local: ChromaDB
- Knowledge graph is free and in-memory: NetworkX
- Workflow orchestration is free: LangGraph
- OCR is free and local: PaddleOCR or Tesseract
- YouTube transcripts are free: youtube-transcript-api (no API key)
- Everything runs in Jupyter notebooks during this phase
- Each notebook is self-contained and independently runnable
- Pydantic models ensure type safety and consistent data contracts across all phases

## Task Dependency Graph

```json
{
  "waves": [
    [1],
    [2],
    [3],
    [4, 5, 6, 7, 8, 9],
    [10],
    [11],
    [12],
    [13],
    [14],
    [15],
    [16],
    [17],
    [18],
    [19],
    [20],
    [21, 22, 23, 24, 25, 26, 27],
    [28],
    [29],
    [30],
    [31],
    [32],
    [33],
    [34],
    [35],
    [36],
    [37]
  ]
}
```
