# NeuroForge Roadmap

## Current Status: v0.1.0 (Alpha)

Core learning engine functional with web interface. Ready for local development and testing.

---

## Phase 1: Foundation & Polish (Current → v1.0)

### Milestone 1.1: Core Stability ✅
- [x] FastAPI backend with all endpoints
- [x] Document upload and processing
- [x] Quiz generation with multiple types
- [x] Flashcard generation with mnemonics
- [x] Revision notes generation
- [x] Chat tutor with RAG
- [x] Mind map generation
- [x] Spaced repetition algorithm
- [x] Next.js frontend
- [x] Enhanced LLM prompts

### Milestone 1.2: Quality & UX (In Progress)
- [x] Fix chat tutor prompt leakage
- [x] Improve response formatting
- [ ] **Source Attribution UI** — Show exact source locations (#4)
- [ ] **Document Viewer** — Display PDFs with highlights (#4)
- [ ] Loading states and error handling improvements
- [ ] Mobile-responsive design polish
- [ ] Keyboard shortcuts

### Milestone 1.3: Subject Management
- [ ] **Subject/Session System** (#3)
  - [ ] Create/edit/delete subjects
  - [ ] Scoped document uploads
  - [ ] Isolated knowledge bases per subject
  - [ ] Subject switching UI
  - [ ] Progress tracking per subject

### Milestone 1.4: Developer Experience
- [ ] **CI/CD Pipeline** (#5)
  - [ ] GitHub Actions for tests
  - [ ] Linting (ruff, black)
  - [ ] PR templates
  - [ ] CONTRIBUTING.md
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Development setup script

---

## Phase 2: Desktop Application (v1.1 - v1.5)

### Milestone 2.1: Desktop MVP (#2)
- [ ] Choose framework (Tauri vs Electron)
- [ ] Package backend with app
- [ ] Basic installer (Windows first)
- [ ] Auto-update mechanism

### Milestone 2.2: Local LLM Integration
- [ ] Ollama integration
- [ ] Model download UI
- [ ] Model selection settings
- [ ] Fallback to cloud APIs (optional)

### Milestone 2.3: Cross-Platform
- [ ] macOS build & installer
- [ ] Linux AppImage/deb/rpm
- [ ] Platform-specific optimizations
- [ ] Code signing

### Milestone 2.4: Desktop Features
- [ ] System tray integration
- [ ] Global hotkey for quick capture
- [ ] File association (.pdf opens in NeuroForge)
- [ ] Native notifications for review reminders

---

## Phase 3: Mobile Application (v2.0)

### Milestone 3.1: Mobile MVP (#1)
- [ ] Choose framework (React Native vs Flutter)
- [ ] Core UI components
- [ ] Document upload from device
- [ ] Basic quiz/flashcard features

### Milestone 3.2: On-Device AI
- [ ] Embedded LLM (TensorFlow Lite / ONNX)
- [ ] Model optimization for mobile
- [ ] Background processing
- [ ] Battery optimization

### Milestone 3.3: Mobile-Specific Features
- [ ] Push notifications for spaced repetition
- [ ] Widget for daily review
- [ ] Offline-first sync
- [ ] Camera capture for notes/documents
- [ ] Voice input for chat tutor

### Milestone 3.4: Cross-Device Sync (Optional)
- [ ] Local network sync (no cloud)
- [ ] Export/import data bundles
- [ ] QR code pairing

---

## Phase 4: Advanced Features (v2.5+)

### Learning Analytics
- [ ] Spaced repetition dashboard (#6)
- [ ] Learning streaks and gamification
- [ ] Predicted exam readiness score
- [ ] Weak topic identification
- [ ] Study time tracking

### Export & Sharing (#7)
- [ ] Anki deck export (.apkg)
- [ ] PDF export for notes
- [ ] Markdown export
- [ ] Print-friendly quiz sheets
- [ ] Share via file/link

### Multi-Language Support (#8)
- [ ] Non-English document processing
- [ ] UI internationalization (i18n)
- [ ] Content generation in user's language

### Accessibility (#10)
- [ ] Screen reader support
- [ ] Keyboard navigation
- [ ] High contrast mode
- [ ] Dyslexia-friendly fonts
- [ ] WCAG 2.1 AA compliance

---

## Phase 5: Ecosystem (v3.0+)

### Collaborative Features (#9)
- [ ] Share subjects with others
- [ ] Study groups
- [ ] Challenge/quiz each other
- [ ] Shared flashcard decks

### Plugin System
- [ ] Plugin API specification
- [ ] Custom workflow plugins
- [ ] Custom UI components
- [ ] Plugin marketplace

### Integrations
- [ ] Notion import
- [ ] Obsidian plugin
- [ ] Zotero integration
- [ ] LMS integrations (Canvas, Moodle)

---

## Technical Debt & Maintenance

Ongoing tasks not tied to specific versions:

- [ ] Remove Docker files (#11)
- [ ] Increase test coverage to 80%+
- [ ] Performance profiling and optimization
- [ ] Security audit
- [ ] Dependency updates
- [ ] Documentation improvements

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| v0.1.0 | Aug 2026 | Initial alpha — core features, web UI |
| v1.0.0 | TBD | Stable release — subject management, source attribution |
| v1.5.0 | TBD | Desktop app (Windows, macOS, Linux) |
| v2.0.0 | TBD | Mobile app (iOS, Android) |
| v2.5.0 | TBD | Analytics, export, accessibility |
| v3.0.0 | TBD | Collaboration, plugins, integrations |

---

## How to Contribute

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

**Priority areas for contribution:**
1. Source attribution & document viewer (#4)
2. CI/CD pipeline (#5)
3. Test coverage
4. Documentation
5. Accessibility

---

## Feedback

Have ideas for the roadmap? Open an issue or discussion on GitHub!

[GitHub Issues](https://github.com/Echo2f13/NeuroForge/issues)
