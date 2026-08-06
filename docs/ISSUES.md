# NeuroForge - Planned Issues

This document contains all planned GitHub issues for the NeuroForge project. Copy these to create issues on GitHub.

---

## Issue #1: Mobile App (React Native / Flutter)

**Labels:** `enhancement` `mobile` `high-priority`

### Title
Build cross-platform mobile app for offline learning

### Description
Create a mobile application that allows users to run NeuroForge entirely on their device without requiring a hosted server.

**Requirements:**
- Cross-platform support (iOS + Android)
- Offline-first architecture — all processing happens locally
- Local LLM integration (Ollama, llama.cpp, or on-device models)
- Local vector database (SQLite + vector extension or similar)
- PDF/document viewer with annotation support
- Push notifications for spaced repetition reminders
- Sync capabilities between devices (optional, user-controlled)

**Technical Considerations:**
- React Native with Expo OR Flutter for cross-platform
- On-device ML: ONNX Runtime, TensorFlow Lite, or CoreML/ML Kit
- Storage: SQLite for structured data, local file system for documents
- Consider smaller LLMs that can run on mobile (Phi-3, Gemma 2B, etc.)

**Acceptance Criteria:**
- [ ] App runs completely offline after initial setup
- [ ] Can upload and process documents locally
- [ ] Quiz, flashcard, and chat features work without internet
- [ ] Spaced repetition notifications work in background

---

## Issue #2: Desktop Application (Electron / Tauri)

**Labels:** `enhancement` `desktop` `high-priority`

### Title
Build downloadable desktop application for local-only usage

### Description
Package NeuroForge as a standalone desktop application that users can download and run locally without any server deployment or cloud dependency.

**Requirements:**
- Single installer for Windows, macOS, Linux
- Bundled Python backend (or compiled binary)
- Bundled local LLM (Ollama integration or embedded model)
- No internet required after installation (except for optional LLM API fallback)
- Auto-updates (optional)
- System tray integration for quick access

**Technical Options:**
1. **Tauri + Rust** — Lightweight, secure, uses system webview
2. **Electron** — Heavier but easier React/Next.js integration
3. **PyInstaller + WebView** — Bundle Python directly

**Architecture:**
```
Desktop App
├── Frontend (Tauri/Electron webview)
├── Backend (Bundled FastAPI or compiled Python)
├── Local LLM (Ollama or llama.cpp)
└── Local Storage (SQLite + ChromaDB files)
```

**Acceptance Criteria:**
- [ ] One-click installer for each OS
- [ ] Works completely offline
- [ ] < 500MB installer size (excluding LLM models)
- [ ] First-run wizard to download/configure local LLM

---

## Issue #3: Subject/Session Management System

**Labels:** `enhancement` `feature` `needs-discussion`

### Title
Universal aggregation with subject/session-based organization

### Description
Implement a session/subject management system that allows users to organize their learning materials by topic, maintaining separate knowledge bases for each subject.

**User Story:**
> As a student, I want to create separate study sessions for each subject (e.g., "Engineering Materials", "Calculus II", "Organic Chemistry") so that quizzes and flashcards are generated from the relevant materials only.

**Proposed Features:**
- Create/rename/delete subjects/sessions
- Upload multiple documents to a subject over time
- Each subject has isolated:
  - Vector store (ChromaDB collection)
  - Knowledge graph
  - Learning state (spaced repetition progress)
  - Generated content history
- Cross-subject search (optional)
- Subject templates (e.g., "Exam Prep", "Research Project", "Course Notes")
- Progress dashboard per subject

**Data Model (Draft):**
```
Subject
├── id, name, description, created_at
├── documents[] (uploaded materials)
├── vector_collection (ChromaDB)
├── knowledge_graph (NetworkX)
├── learning_state (SR progress)
└── settings (difficulty preference, etc.)
```

**Needs Discussion:**
- How to handle cross-subject concepts?
- Should users be able to merge subjects?
- Archive vs delete subjects?
- Import/export subject data?

**Acceptance Criteria:**
- [ ] CRUD operations for subjects
- [ ] Documents scoped to subjects
- [ ] All generation features work within subject context
- [ ] UI for switching between subjects

---

## Issue #4: Source Attribution with Document Viewer

**Labels:** `enhancement` `feature` `ux`

### Title
Show detailed source attribution with inline document viewer

### Description
When displaying any generated content (quiz answers, flashcards, revision notes, chat responses), show exactly where in the source material the information was extracted from, with the ability to view that section of the document.

**Current State:**
- We show `[Source: chunk_id]` citations
- No way to see the actual source document

**Proposed Solution:**

**1. Enhanced Citation Display:**
```
Q: What is martensite?
A: A hard, brittle microstructure formed by rapid cooling...

📄 Source: ENGINEERING-MATERIALS.pdf
   Page 47, Paragraph 3
   "Martensite is a body-centered tetragonal structure..."
   [View in Document →]
```

**2. Split-View Document Viewer:**
- Left panel: Generated content (quiz, flashcard, etc.)
- Right panel: Source document with highlighted relevant section
- Click citation → jumps to that location in document
- Support for: PDF, DOCX, TXT, images of text (OCR)

**3. Technical Requirements:**
- Store page numbers and character offsets during chunking
- PDF.js or react-pdf for document rendering
- Highlight API to mark source passages
- Responsive: collapsible on mobile

**Chunk Metadata Enhancement:**
```python
{
  "chunk_id": "e2dc90d3_0047",
  "content": "...",
  "source_file": "ENGINEERING-MATERIALS.pdf",
  "page_number": 47,
  "start_char": 1523,
  "end_char": 1892,
  "bounding_box": [x1, y1, x2, y2]  # For PDFs
}
```

**Acceptance Criteria:**
- [ ] All generated content shows expandable source citations
- [ ] Clicking citation opens document at exact location
- [ ] Source text is highlighted in document view
- [ ] Works for PDF, DOCX, TXT formats
- [ ] Mobile-friendly (modal or bottom sheet)

---

## Issue #5: CI/CD Pipeline for Contributors

**Labels:** `enhancement` `devops` `good-first-issue`

### Title
Set up GitHub Actions CI/CD pipeline for contributors

### Description
Implement automated testing, linting, and quality checks that run on every pull request to maintain code quality and make contributing easier.

**Proposed Workflow (.github/workflows/ci.yml):**
```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install ruff black isort mypy
      - name: Run linters
        run: |
          ruff check .
          black --check .
          isort --check-only .

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/ -v --tb=short
      
  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ./frontend
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npm run lint
      - run: npm run build
```

**Additional Files Needed:**
- `CONTRIBUTING.md` — Contribution guidelines ✅ (created in docs/)
- `pyproject.toml` — Linter/formatter configuration
- `.pre-commit-config.yaml` — Local pre-commit hooks (optional)
- Issue/PR templates

**Acceptance Criteria:**
- [ ] CI runs on all PRs to main/develop
- [ ] Python linting (ruff/black/isort)
- [ ] Python tests (pytest)
- [ ] Frontend linting and build check
- [ ] Status checks required before merge
- [ ] CONTRIBUTING.md with setup instructions

---

## Issue #6: Spaced Repetition Dashboard

**Labels:** `enhancement` `feature`

### Title
Visual dashboard for spaced repetition progress

### Description
Show users their learning progress with statistics, streaks, and upcoming review schedules.

**Features:**
- Daily/weekly review streak counter
- Cards due today, this week, this month
- Mastery percentage per topic
- Heatmap calendar (like GitHub contributions)
- Predicted exam readiness score
- Charts showing learning velocity over time

**UI Mockup:**
```
┌─────────────────────────────────────────────────────┐
│  🔥 12-day streak!                    85% mastery   │
├─────────────────────────────────────────────────────┤
│  Today: 15 cards due    This week: 47 cards        │
├─────────────────────────────────────────────────────┤
│  [Heatmap calendar showing daily reviews]          │
├─────────────────────────────────────────────────────┤
│  Topics:                                            │
│  ██████████ Heat Treatment (95%)                   │
│  ███████░░░ Corrosion (70%)                        │
│  █████░░░░░ Composites (50%)                       │
└─────────────────────────────────────────────────────┘
```

**Acceptance Criteria:**
- [ ] Dashboard page showing all stats
- [ ] Streak tracking with persistence
- [ ] Per-topic mastery calculation
- [ ] Visual heatmap or chart component

---

## Issue #7: Export & Sharing

**Labels:** `enhancement` `feature`

### Title
Export generated content to various formats

### Description
Allow users to export quizzes, flashcards, and notes for use in other tools or sharing with classmates.

**Export Formats:**
- **Anki deck (.apkg)** for flashcards — import into Anki app
- **PDF** for revision notes — print-friendly formatting
- **Markdown (.md)** for all content — universal format
- **CSV/JSON** for data portability
- **Print-friendly quiz sheets** — formatted for paper tests

**Implementation:**
```python
# Export endpoints
POST /export/anki      → .apkg file
POST /export/pdf       → .pdf file  
POST /export/markdown  → .md file
POST /export/json      → .json file
```

**Acceptance Criteria:**
- [ ] Anki export with proper deck structure
- [ ] PDF export with clean formatting
- [ ] Markdown export for notes
- [ ] UI buttons to trigger exports

---

## Issue #8: Multi-Language Support

**Labels:** `enhancement` `i18n` `future`

### Title
Support for non-English documents and UI

### Description
Enable NeuroForge to work with documents in multiple languages and generate content in the user's preferred language.

**Features:**
- Process documents in: Spanish, French, German, Chinese, Japanese, etc.
- Generate quizzes/flashcards in the document's language
- UI translation (i18n)
- Language auto-detection
- Cross-language features (e.g., English UI, Spanish content)

**Technical Considerations:**
- Multilingual embedding models (e.g., multilingual-e5)
- LLM language capabilities
- i18n framework for frontend (next-intl)

**Acceptance Criteria:**
- [ ] Documents in non-English languages process correctly
- [ ] Content generated in same language as source
- [ ] UI supports at least 3 languages

---

## Issue #9: Collaborative Learning

**Labels:** `enhancement` `feature` `future`

### Title
Share study materials and quiz each other

### Description
Enable social learning features for study groups and classmates.

**Features:**
- Share subjects/sessions with friends (via link or code)
- Challenge mode: quiz each other on shared materials
- Leaderboards for study groups
- Shared flashcard decks
- Study room: real-time collaborative review

**Privacy Considerations:**
- All sharing is opt-in
- Users control what is shared
- Option to keep everything private (default)

**Acceptance Criteria:**
- [ ] Share subject via link
- [ ] Challenge a friend to quiz
- [ ] Basic leaderboard for shared subjects
- [ ] Privacy controls for all sharing

---

## Issue #10: Accessibility (a11y)

**Labels:** `enhancement` `accessibility`

### Title
Improve accessibility for screen readers and keyboard navigation

### Description
Ensure NeuroForge is usable by everyone, including users with disabilities.

**Requirements:**
- WCAG 2.1 AA compliance
- Full keyboard navigation for all features
- Screen reader announcements for dynamic content
- Focus management for modals and dialogs
- Skip links for navigation
- High contrast mode option
- Dyslexia-friendly font option (OpenDyslexic)
- Reduced motion option

**Testing:**
- Test with VoiceOver (macOS), NVDA (Windows)
- axe DevTools audit
- Manual keyboard-only testing

**Acceptance Criteria:**
- [ ] All interactive elements keyboard accessible
- [ ] Proper ARIA labels and roles
- [ ] Color contrast ratios meet WCAG AA
- [ ] High contrast mode toggle
- [ ] Dyslexia font toggle

---

## Issue #11: Remove Docker Files

**Labels:** `chore` `cleanup`

### Title
Remove Docker deployment files (local-only focus)

### Description
Since the project will focus on local desktop/mobile apps rather than hosted deployment, remove Docker-related files to reduce confusion.

**Files to Remove:**
- `Dockerfile`
- `docker-compose.yml`
- `frontend/Dockerfile`

**Note:** Keep this issue low priority until desktop app is ready, in case Docker is useful for development.

**Acceptance Criteria:**
- [ ] Docker files removed
- [ ] README updated to reflect local-only focus
- [ ] Any Docker references in docs removed

---

## Priority Matrix

| Priority | Issues |
|----------|--------|
| **High** | #2 Desktop App, #3 Subject Management, #4 Source Attribution |
| **Medium** | #1 Mobile App, #5 CI/CD, #6 Dashboard, #7 Export |
| **Low** | #8 i18n, #9 Collaboration, #10 Accessibility, #11 Docker Cleanup |

---

## How to Create These Issues on GitHub

1. Go to https://github.com/Echo2f13/NeuroForge/issues
2. Click "New issue"
3. Copy the title and description for each issue above
4. Add appropriate labels
5. Submit

Or install GitHub CLI and run:
```bash
gh issue create --title "Title" --body "Description" --label "enhancement"
```
