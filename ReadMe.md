# NeuroForge — Adaptive Learning Engine

> **🔒 Local-First:** Your study materials never leave your device. All processing happens locally.

## Overview

NeuroForge is an intelligent learning platform that transforms raw study material into structured, personalized learning experiences. Upload any document — PDF, DOCX, or plain text — and NeuroForge builds a knowledge graph, then generates quizzes, flashcards, solutions, revision notes, mind maps, and more, all adapted to your learning progress.

**Key Principles:**
- 🏠 **Local-First** — All data stays on your machine
- 🔐 **Privacy-Focused** — No cloud uploads, no tracking
- 📴 **Offline Capable** — Works without internet (with local LLM)
- 🆓 **Open Source** — Free to use and modify

---

## Features

| Feature | Description |
|---------|-------------|
| **Quiz Generation** | MCQ, short answer, true/false with explanations |
| **Flashcards** | With hints, mnemonics, and spaced repetition |
| **Revision Notes** | Hierarchical, exam-focused summaries |
| **Solutions** | Model answers with marking schemes |
| **Mind Maps** | Visual concept relationships |
| **Chat Tutor** | RAG-powered Q&A grounded in your materials |
| **Adaptive Learning** | Tracks progress, adjusts difficulty |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+ (for frontend)

### Installation

```bash
# Clone the repository
git clone https://github.com/Echo2f13/NeuroForge.git
cd NeuroForge

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# Install Python dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.template .env
# Edit .env with your API keys (Groq, OpenRouter)

# Run the backend
python -m uvicorn main:app --reload --port 8000
```

### Frontend (Optional)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

---

## LLM Configuration

NeuroForge supports multiple LLM providers:

| Provider | Model | Notes |
|----------|-------|-------|
| **Groq** (Primary) | llama-3.3-70b-versatile | Fast, free tier available |
| **OpenRouter** (Fallback) | nvidia/nemotron-3-super-120b | More models, pay-as-you-go |
| **Ollama** (Planned) | Local models | Fully offline |

Configure in `.env`:
```env
GROQ_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
```

---

## Project Structure

```
NeuroForge/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── src/
│   ├── ingestion/       # Document loaders
│   ├── processing/      # Text chunking
│   ├── extraction/      # Knowledge extraction
│   ├── store/           # Vector DB, knowledge graph
│   ├── retrieval/       # Hybrid search
│   ├── workflows/       # Quiz, flashcard, notes generation
│   ├── prompts/         # Enhanced LLM prompts
│   └── learning/        # Spaced repetition
├── models/              # Pydantic data models
├── frontend/            # Next.js web UI
├── tests/               # Test suite
├── notebooks/           # Jupyter development notebooks
└── docs/                # Documentation
```

---

## API Reference

### Health & Status
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check |
| `/stats` | GET | Usage statistics |

### Document Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload` | POST | Upload document (PDF, DOCX, TXT) |
| `/documents` | GET | List uploaded documents |

### Content Generation
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/quiz/generate` | POST | Generate quiz questions |
| `/flashcards/generate` | POST | Generate flashcards |
| `/notes/generate` | POST | Generate revision notes |
| `/solution/generate` | POST | Generate model answer |
| `/chat` | POST | Chat with AI tutor |

### Spaced Repetition
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/review/due` | GET | Get cards due for review |
| `/review/record` | POST | Record review result |

Full API docs: http://localhost:8000/docs

---

## Roadmap

- [x] Core learning engine
- [x] Web interface
- [x] Enhanced LLM prompts
- [ ] Desktop app (Tauri) — [Issue #2](https://github.com/Echo2f13/NeuroForge/issues/2)
- [ ] Mobile app — [Issue #1](https://github.com/Echo2f13/NeuroForge/issues/1)
- [ ] Subject management — [Issue #3](https://github.com/Echo2f13/NeuroForge/issues/3)
- [ ] Source attribution UI — [Issue #6](https://github.com/Echo2f13/NeuroForge/issues/6)

See [full roadmap](./docs/ROADMAP.md) and [open issues](https://github.com/Echo2f13/NeuroForge/issues).

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./docs/CONTRIBUTING.md) for guidelines.

**Good first issues:**
- [CI/CD Pipeline (#7)](https://github.com/Echo2f13/NeuroForge/issues/7)
- Documentation improvements
- Test coverage

---

## Documentation

| Document | Description |
|----------|-------------|
| [VISION.md](./docs/VISION.md) | Project goals and philosophy |
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Technical system design |
| [ROADMAP.md](./docs/ROADMAP.md) | Development milestones |
| [CONTRIBUTING.md](./docs/CONTRIBUTING.md) | Contribution guidelines |
| [API.md](./docs/API.md) | Full API reference |

---

## License

MIT — Free to use, modify, and distribute.

---

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) — Backend framework
- [Next.js](https://nextjs.org/) — Frontend framework
- [ChromaDB](https://www.trychroma.com/) — Vector database
- [Groq](https://groq.com/) — LLM inference
- [LangChain](https://langchain.com/) — LLM tooling
