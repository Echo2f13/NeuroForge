# NeuroForge Architecture

## System Overview

NeuroForge follows a modular, pipeline-based architecture designed for local-first operation with optional cloud LLM support.

```
┌────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Web (Next.js)│  │Desktop(Tauri)│  │   Mobile (React Native)  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
└─────────┼─────────────────┼────────────────────────┼────────────────┘
          │                 │                        │
          └─────────────────┼────────────────────────┘
                            │
                     ┌──────▼──────┐
                     │  REST API   │
                     │  (FastAPI)  │
                     └──────┬──────┘
                            │
┌───────────────────────────┼───────────────────────────────────────┐
│                     BACKEND SERVICES                               │
│  ┌─────────────┐  ┌───────▼───────┐  ┌─────────────────────────┐  │
│  │  Document   │  │   Workflow    │  │      LLM Client         │  │
│  │  Processor  │──│  Orchestrator │──│  (Groq/OpenRouter/Local)│  │
│  └─────────────┘  └───────┬───────┘  └─────────────────────────┘  │
│                           │                                        │
│  ┌─────────────┐  ┌───────▼───────┐  ┌─────────────────────────┐  │
│  │   Chunker   │  │   Retriever   │  │   Enhanced Prompts      │  │
│  │  (Semantic) │  │   (Hybrid)    │  │   (Expert Personas)     │  │
│  └─────────────┘  └───────┬───────┘  └─────────────────────────┘  │
└───────────────────────────┼───────────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────────┐
│                      DATA LAYER                                    │
│  ┌─────────────┐  ┌───────▼───────┐  ┌─────────────────────────┐  │
│  │  ChromaDB   │  │  Knowledge    │  │    Learning State       │  │
│  │  (Vectors)  │  │  Graph (NX)   │  │    (Spaced Rep)         │  │
│  └─────────────┘  └───────────────┘  └─────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Document Processing Pipeline

```
PDF/DOCX/TXT → Extract Text → Semantic Chunking → Embeddings → Store
                    │              │                   │
                    ▼              ▼                   ▼
              Page Mapping   Chunk Metadata      ChromaDB
```

**Files:**
- `src/ingestion/` — Document loaders (PDF, DOCX, TXT, images)
- `src/processing/` — Text cleaning, chunking strategies
- `src/store/vector_store.py` — ChromaDB wrapper

**Chunking Strategy:**
- Semantic chunking based on topic coherence
- Preserve paragraph boundaries
- Store metadata: page number, character offsets, source file

### 2. Knowledge Extraction

```
Chunks → LLM Extraction → Concepts + Relations → Knowledge Graph
              │                    │
              ▼                    ▼
        Enhanced Prompts      NetworkX Graph
```

**Files:**
- `src/extraction/` — Concept and relation extraction
- `src/extraction/robust_extractor.py` — JSON parsing with fallbacks
- `src/store/knowledge_graph.py` — NetworkX-based graph storage

### 3. Retrieval System

```
User Query → Embed Query → Vector Search ─┐
                                          ├─→ Hybrid Merge → Ranked Results
              Graph Query → Related Nodes ─┘
```

**Files:**
- `src/retrieval/retriever.py` — Hybrid retrieval (semantic + graph)
- `src/retrieval/reranker.py` — Result reranking

**Retrieval Modes:**
- `semantic_search()` — Pure vector similarity
- `filtered_search()` — Vector + metadata filters
- `graph_retrieval()` — Knowledge graph traversal
- `hybrid_retrieval()` — Combined approach

### 4. Generation Workflows

Each learning output type has a dedicated workflow:

| Workflow | File | Output |
|----------|------|--------|
| Quiz | `src/workflows/quiz.py` | MCQ, short answer, true/false |
| Flashcards | `src/workflows/flashcards.py` | Q/A pairs with mnemonics |
| Revision Notes | `src/workflows/revision_notes.py` | Hierarchical notes |
| Solutions | `src/workflows/solutions.py` | Model answers with marking schemes |
| Chat Tutor | `src/workflows/chat_tutor.py` | RAG-powered Q&A |
| Additional Info | `src/workflows/additional_info.py` | Industry applications, interview Qs |
| Mind Map | `src/workflows/mind_map.py` | Visual concept maps |

**Workflow Pattern:**
```python
class XWorkflow:
    def generate(self, topic, **params):
        # 1. Retrieve relevant context
        chunks = self.retriever.hybrid_retrieval(topic)
        
        # 2. Build prompt with enhanced templates
        prompt = TEMPLATE.format(context=chunks, topic=topic)
        
        # 3. Generate via LLM
        result = self.llm_client.generate_json(prompt, ResponseModel)
        
        # 4. Validate and return
        return result
```

### 5. LLM Client

**Files:**
- `src/llm.py` — Multi-provider LLM client

**Supported Providers:**
```python
class LLMProvider(Enum):
    GROQ = "groq"           # Primary (fast, free tier)
    OPENROUTER = "openrouter"  # Fallback (more models)
    OLLAMA = "ollama"       # Local (planned)
```

**Features:**
- Automatic fallback chain
- Retry with exponential backoff
- JSON mode with Pydantic validation
- Token usage tracking

### 6. Enhanced Prompts

**Files:**
- `src/prompts/enhanced.py` — Expert-crafted prompt templates

**Prompt Engineering Techniques:**
- Role assignment (Dr. ExamCraft, MemoryMaster, etc.)
- Chain-of-thought reasoning
- Few-shot examples
- Output structure enforcement
- Quality criteria specification

### 7. Spaced Repetition

**Files:**
- `src/learning/spaced_repetition.py` — SM-2 algorithm implementation
- `learning_state.json` — Persistent learning progress

**Algorithm:** SM-2 (SuperMemo 2)
- Tracks ease factor per card
- Calculates optimal review intervals
- Adjusts based on recall performance

## API Endpoints

```
FastAPI Application (main.py)
│
├── GET  /                    — Welcome message
├── GET  /health              — System health check
├── GET  /stats               — Usage statistics
│
├── POST /upload              — Upload document
├── GET  /documents           — List documents
├── GET  /progress/{doc_id}   — Processing progress
│
├── POST /quiz/generate       — Generate quiz
├── POST /flashcards/generate — Generate flashcards
├── POST /notes/generate      — Generate revision notes
├── POST /solution/generate   — Generate model answer
├── POST /additional-info     — Generate supplementary info
│
├── POST /chat                — Chat with tutor
├── POST /chat/reset          — Reset chat history
│
├── GET  /mindmap/{topic}     — Generate mind map
├── GET  /review/due          — Get cards due for review
└── POST /review/record       — Record review result
```

## Data Models

### Pydantic Models (`models/`)

```python
# Document & Chunk
Document(id, filename, content, metadata, chunks)
Chunk(id, content, embedding, metadata)

# Knowledge
Concept(id, name, definition, related_concepts)
Relation(source, target, relation_type)

# Output
QuizQuestion(id, question, options, correct_answer, explanation)
Flashcard(id, question, answer, hint, mnemonic, difficulty)
RevisionNote(topic, subtopics, key_terms, formulae, mnemonics)
Solution(question, marks, answer, marking_scheme, key_points)
```

## Directory Structure

```
NeuroForge/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── pytest.ini              # Test configuration
│
├── src/
│   ├── ingestion/          # Document loaders
│   ├── processing/         # Text processing, chunking
│   ├── extraction/         # Knowledge extraction
│   ├── store/              # Vector store, knowledge graph
│   ├── retrieval/          # Hybrid retrieval system
│   ├── workflows/          # Generation workflows
│   ├── prompts/            # Enhanced prompt templates
│   ├── learning/           # Spaced repetition
│   ├── llm.py              # LLM client
│   └── cache.py            # In-memory caching
│
├── models/                 # Pydantic data models
├── tests/                  # Test suite
├── notebooks/              # Jupyter notebooks (development)
│
├── frontend/               # Next.js web application
│   ├── src/app/            # App router pages
│   └── src/lib/            # API client
│
└── docs/                   # Documentation
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | Next.js 16, React, Tailwind CSS | Web UI |
| API | FastAPI, Pydantic | REST API |
| LLM | Groq, OpenRouter, (Ollama planned) | Text generation |
| Embeddings | Sentence Transformers | Vector embeddings |
| Vector DB | ChromaDB | Similarity search |
| Graph DB | NetworkX | Knowledge graph |
| Document Processing | PyMuPDF, python-docx | File parsing |

## Subject Management System

### Overview

The subject system provides isolation between different study areas, allowing users to organize materials by course, topic, or any logical grouping. Each subject maintains completely separate:

- ChromaDB collections for chunks and concepts
- Isolated knowledge graph
- Independent learning state and progress tracking
- Own spaced repetition card pool

### Components

| Component | File | Purpose |
|-----------|------|---------|
| `SubjectManager` | `src/subjects/manager.py` | Central CRUD operations and component factories |
| `SubjectStorage` | `src/subjects/storage.py` | Directory structure and path utilities |
| `SubjectScopedVectorStore` | `src/subjects/vector_store.py` | Subject-namespaced vector operations |
| `SubjectRetriever` | `src/subjects/retriever.py` | Subject-scoped RAG retrieval |

### Data Model

```python
class Subject:
    id: str              # Unique identifier
    name: str            # Display name
    description: str     # Optional description
    color: str           # UI color (hex)
    icon: str            # Emoji icon
    is_default: bool     # True for "General" subject
    is_archived: bool    # Hidden but preserved
    created_at: datetime
    updated_at: datetime
```

### Data Flow

```
User selects/creates subject
         │
         ▼
┌─────────────────────┐
│   SubjectManager    │
│   - CRUD operations │
│   - Factory methods │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                 Subject-Scoped Components                │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │  VectorStore    │  │  KnowledgeGraph │              │
│  │  (ChromaDB)     │  │  (NetworkX)     │              │
│  │  Collection:    │  │  File:          │              │
│  │  subj_{id}_     │  │  kg_{id}.json   │              │
│  │  chunks         │  │                 │              │
│  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │  LearningState  │  │  Retriever      │              │
│  │  File:          │  │  Searches only  │              │
│  │  ls_{id}.json   │  │  subject's data │              │
│  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────┘
           │
           ▼
    Content generation uses subject's retriever
    Progress tracked per-subject
```

### Storage Structure

```
data/
└── subjects/
    ├── subjects.json           # Subject metadata
    ├── general/                # Default subject
    │   ├── chroma_db/          # Vector collections
    │   ├── knowledge_graph.json
    │   └── learning_state.json
    └── {subject_id}/           # User-created subjects
        ├── chroma_db/
        ├── knowledge_graph.json
        └── learning_state.json
```

### Cross-Subject Search

When enabled, retrieval queries multiple subject collections and merges results:

```python
def cross_subject_search(query: str, subject_ids: List[str]) -> List[Chunk]:
    results = []
    for subject_id in subject_ids:
        retriever = subject_manager.get_retriever(subject_id)
        results.extend(retriever.search(query))
    return merge_and_rerank(results)
```

### Migration

Existing single-subject installations are automatically migrated:
1. Default "General" subject created
2. Existing data moved to General's directory
3. Collection names prefixed with subject ID
4. Learning state associated with General subject

## Security Considerations

1. **Local-First:** Default mode processes everything locally
2. **API Keys:** Stored in `.env`, never committed
3. **No Telemetry:** No usage data sent anywhere
4. **Input Validation:** Pydantic models validate all inputs
5. **File Upload:** Size limits, type validation

## Performance Optimizations

1. **Caching:** In-memory cache for repeated queries (`src/cache.py`)
2. **Background Processing:** Document ingestion runs async
3. **Batch Embeddings:** Embed multiple chunks at once
4. **Lazy Loading:** Components initialized on first use
5. **Connection Pooling:** Reuse LLM client connections

## Future Architecture (Desktop/Mobile)

```
┌─────────────────────────────────────────┐
│           Desktop/Mobile App            │
├─────────────────────────────────────────┤
│  UI Layer (Tauri/React Native)          │
├─────────────────────────────────────────┤
│  Embedded Backend (FastAPI or Rust)     │
├─────────────────────────────────────────┤
│  Local LLM (Ollama/llama.cpp)           │
├─────────────────────────────────────────┤
│  Local Storage (SQLite + ChromaDB)      │
└─────────────────────────────────────────┘
```

Key changes for local apps:
- Bundle Python runtime or compile to binary
- Embed lightweight LLM (Phi-3, Gemma 2B)
- Replace ChromaDB with SQLite + vector extension
- Add model download/management UI
