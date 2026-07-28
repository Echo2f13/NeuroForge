# NeuroForge — System Design

## Architecture Overview

The system follows a pipeline architecture where material flows through discrete stages. Each stage is implemented as a notebook first, then extracted into a module.

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                                │
│  PDF │ PPTX │ DOCX │ Image │ YouTube │ Text │ Markdown          │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DOCUMENT PROCESSOR                              │
│  Extract → Clean → Chunk → Structure Metadata                    │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                 KNOWLEDGE EXTRACTOR (LLM)                         │
│  Topics │ Definitions │ Relationships │ Difficulty │ Keywords    │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE STORE                                │
│  ChromaDB (vectors) │ NetworkX (graph) │ JSON (metadata)         │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PLANNER (LangGraph)                             │
│  Intent Classification → Route to Workflow                       │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│               SPECIALIZED WORKFLOWS                              │
│  Quiz │ Flashcard │ Solution │ Notes │ MindMap │ Chat            │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LEARNING MEMORY                                  │
│  Progress │ Weak Topics │ Spaced Repetition │ Adaptation         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Models (Pydantic)

### Core Document Model

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class InputFormat(str, Enum):
    PDF = "pdf"
    PPTX = "pptx"
    DOCX = "docx"
    IMAGE = "image"
    YOUTUBE = "youtube"
    TEXT = "text"
    MARKDOWN = "markdown"

class DocumentMetadata(BaseModel):
    source: str                          # file path or URL
    format: InputFormat
    title: Optional[str] = None
    total_pages: Optional[int] = None
    author: Optional[str] = None
    created_at: Optional[str] = None

class Document(BaseModel):
    content: str                         # full extracted text
    metadata: DocumentMetadata
    sections: list["Section"] = []       # structural breakdown

class Section(BaseModel):
    heading: Optional[str] = None
    content: str
    level: int = 1                       # heading level (1=top)
    page_number: Optional[int] = None
```

### Chunk Model

```python
class Chunk(BaseModel):
    id: str                              # unique chunk ID
    content: str                         # chunk text
    document_id: str                     # parent document
    chunk_index: int                     # position in document
    metadata: "ChunkMetadata"

class ChunkMetadata(BaseModel):
    section_heading: Optional[str] = None
    page_number: Optional[int] = None
    token_count: int
    start_char: int
    end_char: int
```

### Knowledge Models

```python
class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class Concept(BaseModel):
    id: str
    name: str
    definition: str
    topics: list[str]
    difficulty: Difficulty
    prerequisites: list[str] = []
    keywords: list[str] = []
    source_chunk_ids: list[str] = []     # traceability

class ConceptRelationship(BaseModel):
    source_concept: str
    target_concept: str
    relationship_type: str               # prerequisite, related, part_of

class KnowledgeExtraction(BaseModel):
    concepts: list[Concept]
    relationships: list[ConceptRelationship]
    formulae: list["Formula"] = []
    examples: list["Example"] = []
    key_dates: list["KeyDate"] = []
    key_people: list["KeyPerson"] = []

class Formula(BaseModel):
    expression: str
    description: str
    context: str
    source_chunk_id: str

class Example(BaseModel):
    title: str
    content: str
    related_concepts: list[str]
    source_chunk_id: str

class KeyDate(BaseModel):
    date: str
    event: str
    significance: str
    source_chunk_id: str

class KeyPerson(BaseModel):
    name: str
    role: str
    contribution: str
    source_chunk_id: str
```

### Output Models

```python
class QuizQuestion(BaseModel):
    id: str
    question: str
    question_type: str                   # mcq, short_answer, true_false
    options: Optional[list[str]] = None  # for MCQ
    correct_answer: str
    explanation: str
    topic: str
    difficulty: Difficulty
    source_chunk_ids: list[str]

class Flashcard(BaseModel):
    id: str
    question: str
    answer: str
    hint: Optional[str] = None
    mnemonic: Optional[str] = None
    related_topics: list[str] = []
    difficulty: Difficulty
    source_chunk_ids: list[str]

class Solution(BaseModel):
    question: str
    marks: int
    answer: str
    marking_scheme: list[str]
    key_points: list[str]
    topic: str

class RevisionNote(BaseModel):
    topic: str
    subtopics: list["SubtopicNote"]
    key_terms: list[str]
    formulae: list[str]
    mnemonics: list[str]

class SubtopicNote(BaseModel):
    title: str
    points: list[str]
    importance: str                      # high, medium, low

class MindMapNode(BaseModel):
    id: str
    label: str
    type: str                            # topic, subtopic, concept, example
    parent_id: Optional[str] = None

class MindMap(BaseModel):
    nodes: list[MindMapNode]
    edges: list[dict]                    # {source, target, label}
```

### Learning State Model

```python
class TopicProgress(BaseModel):
    topic: str
    quiz_scores: list[float] = []
    average_score: float = 0.0
    attempts: int = 0
    mastery_level: str = "not_started"   # not_started, learning, familiar, mastered
    last_attempted: Optional[str] = None

class LearningState(BaseModel):
    user_id: str = "default"
    uploaded_materials: list[str] = []
    topic_progress: dict[str, TopicProgress] = {}
    weak_topics: list[str] = []
    strong_topics: list[str] = []
    flashcard_review_queue: list[str] = []  # flashcard IDs
    total_quizzes_taken: int = 0
    total_study_time_minutes: float = 0.0
```

---

## LLM Integration Strategy

### Provider Abstraction

```python
class LLMProvider(str, Enum):
    GROQ = "groq"              # Primary — Llama 4 Scout, fast
    OPENROUTER = "openrouter"  # Fallback — Mistral Small 3.2
    GITHUB = "github"          # Lightweight — GPT-4.1-nano

class LLMConfig(BaseModel):
    provider: LLMProvider
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048
    api_key_env: str           # env var name holding the key
```

### Task-to-Model Mapping

| Task | Best Model | Reasoning |
|------|-----------|-----------|
| Knowledge extraction | Groq — Llama 4 Scout 17B | Good at structured JSON output, fast |
| Quiz generation | Groq — Llama 4 Scout 17B | Needs reasoning + structure |
| Flashcard generation | OpenRouter — Mistral Small 3.2 | Good at concise output |
| Intent classification | GitHub — GPT-4.1-nano | Lightweight task, save quota |
| Chat tutor | Groq — Llama 4 Scout 17B | Needs context + reasoning |
| Solution writing | Groq — Llama 4 Scout 17B | Needs depth and structure |
| Summary generation | OpenRouter — Mistral Small 3.2 | Good at condensation |
| Quality review | GitHub — GPT-4.1-nano | Binary judgment, save quota |

### Rate Limit Strategy

- Groq free tier: 30 requests/min, 14,400 requests/day
- OpenRouter free models: varies, ~20 requests/min
- GitHub Models: 150 requests/day for GPT-4.1-nano
- Strategy: Use Groq as primary, OpenRouter as overflow, GitHub for lightweight tasks only
- Implement exponential backoff + provider fallback

---

## Knowledge Store Design

### ChromaDB Collections

```
Collection: "document_chunks"
  - id: chunk_id
  - document: chunk text
  - embedding: all-MiniLM-L6-v2 vector
  - metadata: {document_id, section, page, topic, difficulty, keywords}

Collection: "concepts"
  - id: concept_id
  - document: concept definition
  - embedding: concept embedding
  - metadata: {topics, difficulty, prerequisites, source_chunks}
```

### NetworkX Knowledge Graph

```
Nodes: Concepts (with attributes: difficulty, definition, topics)
Edges: Relationships (prerequisite, related_to, part_of, example_of)
```

### Retrieval Strategy

1. **Semantic search** — embed query, find top-k similar chunks/concepts in ChromaDB
2. **Graph traversal** — for a concept, find prerequisites and related concepts via NetworkX
3. **Metadata filter** — filter by topic, difficulty, or chapter before semantic search
4. **Hybrid** — combine semantic results with graph neighbors for richer context

---

## LangGraph Workflow Design

### Main Orchestrator Graph

```python
# States
class OrchestratorState(TypedDict):
    user_input: str
    intent: str                    # quiz, flashcard, notes, explain, etc.
    parameters: dict               # topic, difficulty, count, marks
    retrieved_context: list[str]
    generated_output: Any
    review_result: str
    final_output: Any

# Nodes
# 1. classify_intent — determine what user wants
# 2. extract_parameters — parse topic, difficulty, count
# 3. retrieve_context — get relevant chunks/concepts
# 4. route_to_workflow — branch to specialized graph
# 5. review_output — quality check
# 6. update_memory — track progress
```

### Quiz Workflow Graph

```python
class QuizState(TypedDict):
    topic: str
    difficulty: str
    num_questions: int
    concepts: list[dict]
    questions: list[dict]
    reviewed: bool

# Nodes: retrieve_concepts → generate_questions → validate_answers → format_output
```

### Flashcard Workflow Graph

```python
class FlashcardState(TypedDict):
    topic: str
    concepts: list[dict]
    cards: list[dict]
    reviewed: bool

# Nodes: retrieve_concepts → generate_cards → add_hints → add_mnemonics → format_output
```

---

## Notebook Structure

```
notebooks/
├── 00_setup.ipynb                    # Environment setup, API key validation
├── 01_document_ingestion.ipynb       # All loaders, format detection
├── 02_text_processing.ipynb          # Cleaning, chunking, structure extraction
├── 03_knowledge_extraction.ipynb     # LLM-based extraction pipeline
├── 04_knowledge_store.ipynb          # ChromaDB + NetworkX setup and storage
├── 05_retrieval.ipynb                # Semantic search, graph traversal, hybrid
├── 06_quiz_generation.ipynb          # Quiz workflow
├── 07_flashcard_generation.ipynb     # Flashcard workflow
├── 08_solution_generation.ipynb      # Solution workflow
├── 09_revision_notes.ipynb           # Revision notes workflow
├── 10_mind_map.ipynb                 # Mind map generation
├── 11_additional_info.ipynb          # Applications, interview Qs, etc.
├── 12_chat_tutor.ipynb               # RAG-based chat
├── 13_learning_memory.ipynb          # Progress tracking, adaptation
├── 14_planner_orchestrator.ipynb     # LangGraph main orchestrator
├── 15_multi_agent.ipynb              # Full multi-agent demo
└── 16_end_to_end_demo.ipynb          # Complete pipeline demo
```

---

## Error Handling Strategy

1. **LLM failures** — retry with exponential backoff, fall back to next provider
2. **Malformed JSON from LLM** — use LangChain output parsers with retry
3. **Document parsing errors** — return partial results with warnings, don't crash
4. **Empty extraction** — flag to user, suggest different material
5. **Rate limits** — queue requests, switch providers, surface wait time to user

---

## Security Considerations (Notebook Phase)

- API keys stored in `.env`, never committed (`.gitignore` already covers this)
- No user auth needed for notebook phase
- Material stays local — no uploads to third-party storage
- ChromaDB data stored locally in `./chroma_db/`
