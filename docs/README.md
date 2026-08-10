# NeuroForge Documentation

Welcome to the NeuroForge documentation. This folder contains all project documentation, vision, architecture, and roadmap information.

## Contents

| Document | Description |
|----------|-------------|
| [VISION.md](./VISION.md) | Project vision, goals, and philosophy |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Technical architecture and system design |
| [ROADMAP.md](./ROADMAP.md) | Development roadmap and milestones |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute to the project |
| [API.md](./API.md) | API reference documentation |
| [ISSUES.md](./ISSUES.md) | Planned features and known issues |

## Quick Links

- **GitHub Repository:** [Echo2f13/NeuroForge](https://github.com/Echo2f13/NeuroForge)
- **Issue Tracker:** [GitHub Issues](https://github.com/Echo2f13/NeuroForge/issues)

## What is NeuroForge?

NeuroForge is an AI-powered adaptive learning engine that transforms study materials into personalized learning experiences. Upload your documents, and NeuroForge will generate quizzes, flashcards, revision notes, and more — all powered by LLMs and designed for offline, local-first usage.

## Core Philosophy

1. **Local-First:** Your data stays on your device. No cloud dependency required.
2. **Privacy-Focused:** Study materials never leave your machine.
3. **Adaptive Learning:** Spaced repetition and personalized content generation.
4. **Open Source:** Free to use, modify, and contribute to.

---

## User Guide

### Getting Started

1. **Start the backend:** `python -m uvicorn main:app --reload --port 8000`
2. **Start the frontend:** `cd frontend && npm run dev`
3. **Open your browser:** Navigate to http://localhost:3000

### Subject Management

Subjects help you organize your study materials into separate, isolated collections. Each subject has its own knowledge base, flashcards, quizzes, and progress tracking.

#### Creating a Subject

1. Click the **subject selector** in the header (shows current subject name)
2. Click **"Create New Subject"**
3. Enter a name for your subject (e.g., "Physics", "History", "Programming")
4. Optionally add a description, choose a color, and select an icon
5. Click **Create**

#### Switching Subjects

1. Click the subject selector in the header
2. Select the subject you want to switch to
3. All content (documents, quizzes, flashcards) will now show data for that subject

#### Managing Subjects

- **Edit:** Click the edit icon on a subject card to change name, description, color, or icon
- **Archive:** Archive subjects you're not currently studying to hide them from the main list
- **Restore:** View archived subjects and restore them when needed
- **Delete:** Permanently remove a subject and all its data (cannot delete the default "General" subject)

#### Default Subject

When you first use NeuroForge, a default "General" subject is created. This is where materials go if you haven't selected a specific subject. You cannot delete the General subject, but you can rename it.

#### Cross-Subject Search

By default, searches are limited to the current subject. To search across all subjects:
1. Enable "Cross-Subject Search" in settings
2. Search results will include materials from all your subjects
3. Results are tagged with their source subject

### Uploading Documents

1. Select the subject where you want to add materials
2. Click **Upload** or drag and drop files
3. Supported formats: PDF, DOCX, TXT
4. Wait for processing to complete (progress shown in real-time)

### Generating Content

After uploading documents to a subject:

- **Quizzes:** Generate MCQ, short answer, and true/false questions on any topic
- **Flashcards:** Create study cards with hints and mnemonics
- **Revision Notes:** Get hierarchical summaries of key concepts
- **Solutions:** Generate model answers for exam questions
- **Mind Maps:** Visualize concept relationships

All generated content is scoped to the current subject.

### Spaced Repetition

NeuroForge tracks your flashcard reviews using the SM-2 algorithm:

1. Review cards when they're due (shown on dashboard)
2. Rate your recall (0-5 scale)
3. Cards are rescheduled based on your performance
4. Progress is tracked per-subject

### Source Attribution

NeuroForge tracks where all generated content comes from. When quizzes, flashcards, notes, or chat responses are generated, they include links back to the original source material.

#### Viewing Citations

1. Generate any content (quiz, flashcards, notes, or chat)
2. Look for the **"Sources"** section below the generated content
3. Click on a citation to expand it and see the excerpt
4. Click **"View in Document"** to open the inline document viewer

#### Citation Information

Each citation shows:
- **Document name:** The original file
- **Page number:** For PDFs, the specific page
- **Excerpt:** A brief quote from the source
- **Relevance score:** How closely the source matches (0-100%)

#### Document Viewer

The document viewer shows the original source with highlighting:

**Desktop:**
- Opens as a sidebar panel (right side)
- Can switch to bottom panel or modal view
- Resize by dragging the divider

**Mobile/Tablet:**
- Opens as a full-screen modal
- Swipe down to dismiss
- Pinch to zoom on PDFs

**Viewer Controls:**
- **Zoom:** Use +/- buttons or pinch gestures
- **Navigation:** Use arrow buttons or scroll
- **Position:** Switch between right sidebar, bottom panel, or modal
- **Download:** Download the original file

#### Supported Formats

| Format | Features |
|--------|----------|
| PDF | Page navigation, bounding box highlights, zoom |
| DOCX | Character offset highlights (download for full view) |
| TXT | Line number display, character highlights |

#### Tips for Better Citations

1. **Upload original documents:** PDFs work best for citation accuracy
2. **Use clear formatting:** Well-structured documents yield better citations
3. **Check relevance scores:** Higher scores (>80%) indicate better matches
4. **Explore related citations:** Multiple sources may cover the same topic

### Migration from Earlier Versions

If you're upgrading from a version without subject support:

1. Your existing data is automatically migrated to the "General" subject
2. No action required — everything continues to work
3. You can now create new subjects to organize future materials
4. Optionally move documents from General to new subjects
