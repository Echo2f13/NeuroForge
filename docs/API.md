# NeuroForge API Reference

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)

---

## Table of Contents

- [Health & Status](#health--status)
- [Document Management](#document-management)
- [Quiz Generation](#quiz-generation)
- [Flashcard Generation](#flashcard-generation)
- [Revision Notes](#revision-notes)
- [Solution Generation](#solution-generation)
- [Chat Tutor](#chat-tutor)
- [Additional Info](#additional-info)
- [Mind Map](#mind-map)
- [Spaced Repetition](#spaced-repetition)

---

## Health & Status

### GET /
Welcome message and API info.

**Response:**
```json
{
  "message": "Welcome to NeuroForge API",
  "version": "0.1.0",
  "docs": "/docs"
}
```

### GET /health
System health check.

**Response:**
```json
{
  "status": "healthy",
  "message": "All components operational",
  "components": {
    "llm_client": true,
    "vector_store": true,
    "knowledge_graph": true,
    "retriever": true
  }
}
```

### GET /stats
Usage statistics.

**Response:**
```json
{
  "documents_processed": 5,
  "total_chunks": 234,
  "concepts_extracted": 45,
  "quizzes_generated": 12,
  "flashcards_generated": 89
}
```

---

## Document Management

### POST /upload
Upload a document for processing.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` (PDF, DOCX, or TXT)

**Response:**
```json
{
  "document_id": "doc_abc123",
  "filename": "engineering-materials.pdf",
  "status": "processing",
  "message": "Document uploaded successfully. Processing started."
}
```

### GET /documents
List all uploaded documents.

**Response:**
```json
{
  "documents": [
    {
      "id": "doc_abc123",
      "filename": "engineering-materials.pdf",
      "status": "completed",
      "chunks": 156,
      "uploaded_at": "2026-08-06T12:00:00Z"
    }
  ]
}
```

### GET /progress/{document_id}
Get processing progress for a document.

**Response:**
```json
{
  "document_id": "doc_abc123",
  "status": "processing",
  "progress": 65,
  "stage": "extracting_concepts",
  "message": "Extracting knowledge concepts..."
}
```

**Status values:** `pending`, `processing`, `completed`, `failed`

---

## Quiz Generation

### POST /quiz/generate
Generate quiz questions for a topic.

**Request:**
```json
{
  "topic": "Heat Treatment of Steel",
  "difficulty": "medium",
  "num_questions": 10,
  "question_types": ["mcq", "short_answer", "true_false"]
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| topic | string | Yes | - | Topic to generate questions about |
| difficulty | string | No | "medium" | "easy", "medium", or "hard" |
| num_questions | int | No | 10 | Number of questions (1-50) |
| question_types | array | No | all types | Types to include |

**Response:**
```json
{
  "questions": [
    {
      "id": "q-001",
      "question": "What microstructure forms when steel is rapidly cooled from above the critical temperature?",
      "question_type": "mcq",
      "options": [
        "Pearlite",
        "Martensite",
        "Austenite",
        "Bainite"
      ],
      "correct_answer": "Martensite",
      "explanation": "Rapid cooling (quenching) prevents diffusion, causing austenite to transform to martensite through a shear mechanism.",
      "topic": "Heat Treatment of Steel",
      "difficulty": "medium",
      "cognitive_level": "application",
      "source_chunk_ids": ["e2dc90d3_0047", "e2dc90d3_0048"]
    }
  ],
  "metadata": {
    "generated_at": "2026-08-06T12:00:00Z",
    "model": "llama-3.3-70b-versatile",
    "tokens_used": 1523
  }
}
```

---

## Flashcard Generation

### POST /flashcards/generate
Generate flashcards for a topic.

**Request:**
```json
{
  "topic": "Composite Materials",
  "difficulty": "medium",
  "num_cards": 15
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| topic | string | Yes | - | Topic for flashcards |
| difficulty | string | No | null | "easy", "medium", "hard", or null (mixed) |
| num_cards | int | No | 10 | Number of cards (1-50) |

**Response:**
```json
{
  "flashcards": [
    {
      "id": "fc-001",
      "question": "Composite materials combine two or more materials to achieve ___",
      "answer": "combined strengths",
      "hint": "Think about why we combine materials",
      "mnemonic": "COMPosite = COMbined Powers",
      "related_topics": ["Matrix", "Reinforcement", "Fibers"],
      "difficulty": "easy",
      "source_chunk_ids": ["e2dc90d3_0180"]
    }
  ]
}
```

---

## Revision Notes

### POST /notes/generate
Generate hierarchical revision notes.

**Request:**
```json
{
  "topic": "Corrosion"
}
```

**Response:**
```json
{
  "topic": "Corrosion",
  "subtopics": [
    {
      "title": "Types of Corrosion",
      "key_points": [
        "Uniform corrosion affects entire surface evenly",
        "Galvanic corrosion occurs between dissimilar metals",
        "Pitting corrosion creates localized holes",
        "Crevice corrosion occurs in confined spaces"
      ],
      "importance": "high"
    }
  ],
  "key_terms": [
    "Oxidation: Loss of electrons by a metal",
    "Reduction: Gain of electrons",
    "Passivation: Protective oxide layer formation"
  ],
  "formulae": [
    "Corrosion rate = (K × W) / (A × T × D)",
    "where K=constant, W=weight loss, A=area, T=time, D=density"
  ],
  "mnemonics": [
    "OIL RIG: Oxidation Is Loss, Reduction Is Gain (of electrons)"
  ]
}
```

---

## Solution Generation

### POST /solution/generate
Generate a model answer for an exam question.

**Request:**
```json
{
  "question": "Explain the process of heat treatment of steel and its effects on mechanical properties.",
  "topic": "Heat Treatment",
  "marks": 10
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| question | string | Yes | - | The exam question |
| topic | string | Yes | - | Subject area |
| marks | int | No | 5 | Mark allocation (affects depth) |

**Response:**
```json
{
  "question": "Explain the process of heat treatment...",
  "marks": 10,
  "answer": "Heat treatment is a controlled process of heating and cooling metals to alter their physical and mechanical properties without changing their shape...",
  "marking_scheme": [
    "1 mark: Define heat treatment correctly",
    "1 mark: Mention controlled heating and cooling",
    "2 marks: Explain annealing process and purpose",
    "2 marks: Explain quenching and tempering",
    "2 marks: Describe effects on hardness and ductility",
    "2 marks: Provide relevant examples"
  ],
  "key_points": [
    "Definition of heat treatment",
    "Types: annealing, normalizing, quenching, tempering",
    "Effect on microstructure",
    "Effect on mechanical properties",
    "Industrial applications"
  ],
  "topic": "Heat Treatment"
}
```

---

## Chat Tutor

### POST /chat
Ask the AI tutor a question.

**Request:**
```json
{
  "message": "What is the difference between annealing and normalizing?"
}
```

**Response:**
```json
{
  "answer": "**Annealing** involves heating steel above the critical temperature and then cooling it slowly (usually in the furnace) [Source: e2dc90d3_0052]. This produces a soft, ductile microstructure.\n\n**Normalizing** also heats above the critical temperature but cools in still air [Source: e2dc90d3_0053]. This produces a finer grain structure and slightly higher strength than annealing.\n\nWould you like me to explain when you'd use each process?",
  "sources": ["e2dc90d3_0052", "e2dc90d3_0053", "e2dc90d3_0054"],
  "is_grounded": true
}
```

### POST /chat/reset
Clear conversation history.

**Response:**
```json
{
  "message": "Chat history cleared"
}
```

---

## Additional Info

### POST /additional-info
Generate real-world supplementary information.

**Request:**
```json
{
  "topic": "Steel Alloys"
}
```

**Response:**
```json
{
  "applications": [
    "Automotive body panels using high-strength low-alloy steel (Automotive Industry)",
    "Surgical instruments from martensitic stainless steel (Medical Devices)",
    "Bridge cables using high-carbon steel wire (Civil Engineering)"
  ],
  "industry_uses": [
    "Aerospace: Landing gear components require high-strength steel alloys",
    "Oil & Gas: Pipeline steels resist corrosion in harsh environments",
    "Tool Manufacturing: Tool steels maintain hardness at high temperatures"
  ],
  "common_mistakes": [
    "Confusing steel grades: Using wrong alloy designation → Component failure",
    "Incorrect heat treatment: Wrong temperature or cooling rate → Poor properties",
    "Ignoring carbon content: Assuming all steels weld the same → Cracking"
  ],
  "interview_questions": [
    "What is the difference between carbon steel and alloy steel? (Difficulty: basic)",
    "How does chromium content affect stainless steel properties? (Difficulty: intermediate)",
    "Design a heat treatment process for a gear requiring high surface hardness but tough core. (Difficulty: advanced)"
  ]
}
```

---

## Mind Map

### GET /mindmap/{topic}
Generate a mind map structure for visualization.

**Response:**
```json
{
  "nodes": [
    {"id": "root", "label": "Steel Alloys", "level": 0},
    {"id": "n1", "label": "Carbon Steels", "level": 1},
    {"id": "n2", "label": "Alloy Steels", "level": 1},
    {"id": "n1a", "label": "Low Carbon (<0.3%)", "level": 2},
    {"id": "n1b", "label": "Medium Carbon", "level": 2},
    {"id": "n1c", "label": "High Carbon (>0.6%)", "level": 2}
  ],
  "edges": [
    {"source": "root", "target": "n1"},
    {"source": "root", "target": "n2"},
    {"source": "n1", "target": "n1a"},
    {"source": "n1", "target": "n1b"},
    {"source": "n1", "target": "n1c"}
  ]
}
```

---

## Spaced Repetition

### GET /review/due
Get flashcards due for review.

**Response:**
```json
{
  "due_cards": [
    {
      "card_id": "fc-001",
      "question": "Martensite forms when steel is cooled ___",
      "due_date": "2026-08-06",
      "ease_factor": 2.5,
      "interval_days": 3
    }
  ],
  "total_due": 5,
  "reviewed_today": 12
}
```

### POST /review/record
Record a review result.

**Request:**
```json
{
  "card_id": "fc-001",
  "quality": 4
}
```

| Quality | Meaning |
|---------|---------|
| 0 | Complete blackout |
| 1 | Incorrect, remembered after seeing answer |
| 2 | Incorrect, but answer seemed easy to recall |
| 3 | Correct with serious difficulty |
| 4 | Correct with hesitation |
| 5 | Perfect recall |

**Response:**
```json
{
  "card_id": "fc-001",
  "next_review": "2026-08-10",
  "new_interval": 4,
  "new_ease_factor": 2.6
}
```

---

## Dashboard

### GET /dashboard
Get comprehensive learning progress dashboard data.

**Response:**
```json
{
  "streak": {
    "current_streak": 12,
    "longest_streak": 25,
    "total_cards_reviewed": 347
  },
  "overall": {
    "total_quizzes": 45,
    "total_topics": 8,
    "average_score": 78.5,
    "study_time_minutes": 420,
    "weak_count": 2,
    "strong_count": 5
  },
  "weekly": {
    "reviews_this_week": 34,
    "quizzes_this_week": 5,
    "total_this_week": 39
  },
  "monthly": {
    "reviews_this_month": 156,
    "quizzes_this_month": 23,
    "total_this_month": 179
  },
  "due_cards": {
    "today": 15,
    "this_week": 47,
    "this_month": 89,
    "card_ids_today": ["fc-001", "fc-002", "fc-003"]
  },
  "topic_mastery": [
    {
      "topic": "Heat Treatment",
      "mastery_percent": 95.0,
      "mastery_level": "mastered",
      "attempts": 12,
      "last_attempted": "2026-08-06T14:30:00Z"
    },
    {
      "topic": "Corrosion",
      "mastery_percent": 70.0,
      "mastery_level": "familiar",
      "attempts": 8,
      "last_attempted": "2026-08-05T10:15:00Z"
    }
  ],
  "heatmap": [
    {"date": "2026-08-01", "count": 5, "level": 2},
    {"date": "2026-08-02", "count": 12, "level": 4},
    {"date": "2026-08-03", "count": 0, "level": 0}
  ],
  "exam_readiness": {
    "score": 72.5,
    "level": "good",
    "message": "Good progress! Focus on weak topics to improve further.",
    "breakdown": {
      "mastery": 78.5,
      "consistency": 80.0,
      "coverage": 62.5,
      "recency": 57.1
    }
  },
  "learning_velocity": [
    {"week": "Week 1", "week_start": "2026-06-17", "average_score": 65.0, "quizzes": 3},
    {"week": "Week 2", "week_start": "2026-06-24", "average_score": 72.0, "quizzes": 4},
    {"week": "Week 8", "week_start": "2026-08-05", "average_score": 85.0, "quizzes": 5}
  ]
}
```

**Dashboard Components:**

| Component | Description |
|-----------|-------------|
| `streak` | Current and longest streaks, total reviews |
| `overall` | Aggregate stats across all activity |
| `weekly/monthly` | Activity summaries for time periods |
| `due_cards` | Cards due for spaced repetition |
| `topic_mastery` | Per-topic progress with mastery levels |
| `heatmap` | Daily activity for GitHub-style calendar (365 days) |
| `exam_readiness` | Predicted readiness score (0-100) with breakdown |
| `learning_velocity` | Weekly score trends (8 weeks) |

**Exam Readiness Calculation:**
- 40% — Average mastery across topics
- 30% — Consistency (streak factor, max at 30 days)
- 20% — Coverage (mastered topics / total topics)
- 10% — Recency (activity in last 7 days)

**Mastery Levels:**
| Level | Average Score |
|-------|---------------|
| `not_started` | No attempts |
| `learning` | < 60% |
| `familiar` | 60-84% |
| `mastered` | ≥ 85% |

**Heatmap Levels:**
| Level | Activity Count |
|-------|----------------|
| 0 | 0 activities |
| 1 | 1-2 activities |
| 2 | 3-5 activities |
| 3 | 6-10 activities |
| 4 | 11+ activities |

### POST /dashboard/record-review
Record a flashcard review with streak tracking.

Use this instead of `/review/record` to track reviews for dashboard metrics.

**Request Parameters:**
- `card_id` (string): Flashcard ID
- `quality` (int): Review quality 0-5

**Response:**
```json
{
  "status": "success",
  "card_id": "fc-001",
  "quality": 4,
  "next_review": "2026-08-10",
  "interval_days": 4,
  "current_streak": 13
}
```

---

## Error Responses

All endpoints may return these error formats:

### 400 Bad Request
```json
{
  "detail": "topic is required"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "num_questions"],
      "msg": "ensure this value is less than or equal to 50",
      "type": "value_error.number.not_le"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "LLM generation failed after 3 retries"
}
```

---

## Rate Limits

When using cloud LLM providers:
- **Groq:** ~30 requests/minute (free tier)
- **OpenRouter:** Varies by model

The API automatically handles rate limiting with retries and fallback.

---

## WebSocket (Future)

Real-time streaming responses planned for:
- `/ws/chat` — Streaming chat responses
- `/ws/progress` — Real-time processing updates
