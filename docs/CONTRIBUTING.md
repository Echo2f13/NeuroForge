# Contributing to NeuroForge

Thank you for your interest in contributing to NeuroForge! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

---

## Code of Conduct

By participating in this project, you agree to maintain a welcoming, inclusive, and harassment-free environment. Be respectful, constructive, and collaborative.

---

## Getting Started

### Find Something to Work On

1. **Good First Issues:** Look for issues labeled `good-first-issue`
2. **Help Wanted:** Check issues labeled `help-wanted`
3. **Roadmap:** See [ROADMAP.md](./ROADMAP.md) for planned features
4. **Your Ideas:** Open an issue to discuss new features before implementing

### Before You Start

1. Check if an issue already exists for your idea
2. Comment on the issue to claim it
3. For major changes, discuss the approach first

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Git

### Clone and Setup

```bash
# Clone the repository
git clone https://github.com/Echo2f13/NeuroForge.git
cd NeuroForge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install ruff black isort mypy pytest

# Setup frontend
cd frontend
npm install
cd ..
```

### Environment Variables

```bash
# Copy template
cp .env.template .env

# Edit .env with your API keys
# GROQ_API_KEY=your_key_here
# OPENROUTER_API_KEY=your_key_here
```

### Running Locally

```bash
# Terminal 1: Backend
python -m uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Visit http://localhost:3000

---

## Making Changes

### Branch Naming

```
feature/short-description    # New features
fix/issue-number-description # Bug fixes
docs/what-changed            # Documentation
refactor/what-changed        # Code refactoring
test/what-tested             # Test additions
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

feat(quiz): add true/false question support
fix(chat): prevent prompt leakage in responses
docs(readme): update installation instructions
refactor(llm): simplify provider fallback logic
test(api): add endpoint validation tests
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Making a Change

```bash
# Create a branch
git checkout -b feature/my-feature

# Make changes...

# Run tests
pytest tests/ -v

# Run linters
ruff check .
black --check .

# Commit
git add .
git commit -m "feat(scope): description"

# Push
git push -u origin feature/my-feature
```

---

## Pull Request Process

### Before Submitting

- [ ] Tests pass locally (`pytest tests/ -v`)
- [ ] Linters pass (`ruff check .` and `black --check .`)
- [ ] Frontend builds (`cd frontend && npm run build`)
- [ ] Documentation updated if needed
- [ ] Commit messages follow convention

### PR Template

When opening a PR, include:

```markdown
## Description
Brief description of changes.

## Related Issue
Closes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe how you tested the changes.

## Screenshots (if applicable)
Add screenshots for UI changes.
```

### Review Process

1. Maintainer reviews within 48-72 hours
2. Address feedback and push updates
3. Once approved, maintainer merges
4. Your contribution is live! 🎉

---

## Coding Standards

### Python

```python
# Use type hints
def generate_quiz(topic: str, num_questions: int = 10) -> list[QuizQuestion]:
    ...

# Use docstrings (Google style)
def process_document(file_path: str) -> Document:
    """Process a document and extract text content.
    
    Args:
        file_path: Path to the document file.
        
    Returns:
        A Document instance with extracted content.
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    ...

# Use Pydantic for data models
class QuizQuestion(BaseModel):
    id: str
    question: str
    correct_answer: str
```

**Tools:**
- `ruff` — Linting
- `black` — Formatting
- `isort` — Import sorting
- `mypy` — Type checking (optional)

### TypeScript/React

```typescript
// Use TypeScript interfaces
interface QuizQuestion {
  id: string;
  question: string;
  options: string[] | null;
  correctAnswer: string;
}

// Use functional components
export function QuizCard({ question }: { question: QuizQuestion }) {
  return (
    <div className="p-4 border rounded">
      <p>{question.question}</p>
    </div>
  );
}
```

**Tools:**
- `eslint` — Linting
- `prettier` — Formatting (via eslint)

### File Organization

```
# Python: Group imports
import json                          # Standard library
from typing import Optional

import chromadb                       # Third-party
from pydantic import BaseModel

from src.llm import LLMClient         # Local imports
from models.output import QuizQuestion
```

---

## Testing

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific file
pytest tests/test_api.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Writing Tests

```python
# tests/test_example.py
import pytest
from src.workflows.quiz import QuizWorkflow

class TestQuizWorkflow:
    """Tests for QuizWorkflow."""
    
    def test_generate_returns_questions(self, mock_llm):
        """Should return a list of quiz questions."""
        workflow = QuizWorkflow(llm_client=mock_llm, retriever=mock_retriever)
        result = workflow.generate("Engineering", num_questions=5)
        
        assert len(result) == 5
        assert all(isinstance(q, QuizQuestion) for q in result)
    
    def test_generate_with_invalid_type_raises(self, mock_llm):
        """Should raise ValueError for invalid question types."""
        workflow = QuizWorkflow(llm_client=mock_llm, retriever=mock_retriever)
        
        with pytest.raises(ValueError, match="Invalid question type"):
            workflow.generate("Topic", question_types=["invalid"])
```

### Test Categories

- **Unit tests:** Test individual functions/classes
- **Integration tests:** Test component interactions
- **API tests:** Test HTTP endpoints
- **E2E tests:** Test full user flows (future)

---

## Documentation

### What to Document

- New features → Update README or create guide
- API changes → Update API.md
- Architecture changes → Update ARCHITECTURE.md
- New dependencies → Update requirements.txt with comment

### Docstring Format

```python
def function_name(param1: str, param2: int = 10) -> ReturnType:
    """Short description of function.
    
    Longer description if needed. Explain what the function does,
    any important behavior, and edge cases.
    
    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to 10.
        
    Returns:
        Description of return value.
        
    Raises:
        ValueError: When param1 is empty.
        
    Example:
        >>> result = function_name("hello", 5)
        >>> print(result)
    """
```

---

## Questions?

- **Discord:** (Coming soon)
- **Discussions:** [GitHub Discussions](https://github.com/Echo2f13/NeuroForge/discussions)
- **Issues:** [GitHub Issues](https://github.com/Echo2f13/NeuroForge/issues)

---

Thank you for contributing to NeuroForge! 🚀
