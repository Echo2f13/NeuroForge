"""Tests for the StructureExtractor module."""

import pytest

from models import Chunk, ChunkMetadata, Document, DocumentMetadata, InputFormat
from src.processing.structure import (
    CodeBlock,
    DocumentStructure,
    ListBlock,
    SectionNode,
    StructureExtractor,
    TableBlock,
)


@pytest.fixture
def extractor():
    return StructureExtractor()


@pytest.fixture
def sample_document():
    content = """# Introduction

This is the introduction paragraph.

## Background

Some background information here.

### Details

More detailed information in this subsection.

## Methods

Description of methods used.

# Results

The results of our study.
"""
    return Document(
        content=content,
        metadata=DocumentMetadata(source="test.md", format=InputFormat.MARKDOWN),
    )


# --- Section Tree Tests ---


class TestBuildSectionTree:
    def test_basic_heading_hierarchy(self, extractor, sample_document):
        tree = extractor.build_section_tree(sample_document)

        # Should have 2 top-level sections: Introduction and Results
        assert len(tree) == 2
        assert tree[0].heading == "Introduction"
        assert tree[0].level == 1
        assert tree[1].heading == "Results"
        assert tree[1].level == 1

    def test_nested_children(self, extractor, sample_document):
        tree = extractor.build_section_tree(sample_document)

        # Introduction has 2 children: Background and Methods
        intro = tree[0]
        assert len(intro.children) == 2
        assert intro.children[0].heading == "Background"
        assert intro.children[0].level == 2
        assert intro.children[1].heading == "Methods"
        assert intro.children[1].level == 2

    def test_deeply_nested(self, extractor, sample_document):
        tree = extractor.build_section_tree(sample_document)

        # Background has 1 child: Details
        background = tree[0].children[0]
        assert len(background.children) == 1
        assert background.children[0].heading == "Details"
        assert background.children[0].level == 3

    def test_content_positions(self, extractor, sample_document):
        tree = extractor.build_section_tree(sample_document)

        # content_start should be after the heading line
        intro = tree[0]
        assert intro.content_start > 0
        assert intro.content_end > intro.content_start

    def test_no_headings(self, extractor):
        doc = Document(
            content="Just plain text without any headings.",
            metadata=DocumentMetadata(source="plain.txt", format=InputFormat.TEXT),
        )
        tree = extractor.build_section_tree(doc)
        assert tree == []

    def test_single_heading(self, extractor):
        doc = Document(
            content="# Only One\n\nSome content here.",
            metadata=DocumentMetadata(source="one.md", format=InputFormat.MARKDOWN),
        )
        tree = extractor.build_section_tree(doc)
        assert len(tree) == 1
        assert tree[0].heading == "Only One"
        assert tree[0].children == []


# --- Table Detection Tests ---


class TestDetectTables:
    def test_pipe_delimited_table(self, extractor):
        text = """Some text before.

| Name | Age | City |
|------|-----|------|
| Alice | 30 | NYC |
| Bob | 25 | LA |

Some text after.
"""
        tables = extractor.detect_tables(text)
        assert len(tables) == 1
        assert tables[0].columns == 3
        assert tables[0].rows == 3  # header + 2 data rows

    def test_pipe_table_positions(self, extractor):
        text = "Before\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nAfter"
        tables = extractor.detect_tables(text)
        assert len(tables) == 1
        assert tables[0].start_char > 0
        assert tables[0].end_char > tables[0].start_char

    def test_no_tables(self, extractor):
        text = "This is just plain text with no tables at all."
        tables = extractor.detect_tables(text)
        assert tables == []

    def test_whitespace_aligned_table(self, extractor):
        text = """Some text before.

Name      Age    City
Alice     30     NYC
Bob       25     LA

Some text after.
"""
        tables = extractor.detect_tables(text)
        assert len(tables) == 1
        assert tables[0].rows == 3
        assert tables[0].columns >= 2


# --- List Detection Tests ---


class TestDetectLists:
    def test_bullet_list(self, extractor):
        text = """Here is a list:

- Item one
- Item two
- Item three

End of section.
"""
        lists = extractor.detect_lists(text)
        assert len(lists) == 1
        assert lists[0].items == 3
        assert lists[0].nesting_depth == 1

    def test_nested_list(self, extractor):
        text = """Items:

- Item one
  - Sub-item A
  - Sub-item B
- Item two
"""
        lists = extractor.detect_lists(text)
        assert len(lists) == 1
        assert lists[0].items == 4
        assert lists[0].nesting_depth > 1

    def test_numbered_list(self, extractor):
        text = """Steps:

1. First step
2. Second step
3. Third step
"""
        lists = extractor.detect_lists(text)
        assert len(lists) == 1
        assert lists[0].items == 3

    def test_no_lists(self, extractor):
        text = "This paragraph has no lists. Just text."
        lists = extractor.detect_lists(text)
        assert lists == []

    def test_multiple_lists(self, extractor):
        text = """# Section 1

- Apple
- Banana

# Section 2

1. Step one
2. Step two
"""
        lists = extractor.detect_lists(text)
        assert len(lists) == 2


# --- Code Block Detection Tests ---


class TestDetectCodeBlocks:
    def test_fenced_code_block(self, extractor):
        text = """Some text.

```python
def hello():
    print("Hello, world!")
```

More text.
"""
        blocks = extractor.detect_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert "def hello():" in blocks[0].content

    def test_code_block_no_language(self, extractor):
        text = """Text before.

```
some code here
```

Text after.
"""
        blocks = extractor.detect_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language is None
        assert "some code here" in blocks[0].content

    def test_multiple_code_blocks(self, extractor):
        text = """First block:

```javascript
console.log("hi");
```

Second block:

```python
print("hi")
```
"""
        blocks = extractor.detect_code_blocks(text)
        assert len(blocks) == 2
        assert blocks[0].language == "javascript"
        assert blocks[1].language == "python"

    def test_no_code_blocks(self, extractor):
        text = "Just regular text, no code blocks."
        blocks = extractor.detect_code_blocks(text)
        assert blocks == []

    def test_code_block_positions(self, extractor):
        text = "Before\n\n```\ncode\n```\n\nAfter"
        blocks = extractor.detect_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].start_char == text.index("```")
        assert blocks[0].end_char > blocks[0].start_char


# --- Full Extract Tests ---


class TestExtract:
    def test_extract_returns_document_structure(self, extractor, sample_document):
        structure = extractor.extract(sample_document)
        assert isinstance(structure, DocumentStructure)
        assert len(structure.sections) > 0

    def test_extract_complex_document(self, extractor):
        content = """# Main Title

Introduction text.

## Section A

Some content with a table:

| Col1 | Col2 |
|------|------|
| A    | B    |

And a list:

- Item 1
- Item 2

## Section B

```python
x = 42
```

The end.
"""
        doc = Document(
            content=content,
            metadata=DocumentMetadata(source="complex.md", format=InputFormat.MARKDOWN),
        )
        structure = extractor.extract(doc)

        assert len(structure.sections) == 1  # 1 top-level
        assert len(structure.tables) == 1
        assert len(structure.lists) == 1
        assert len(structure.code_blocks) == 1


# --- Annotate Chunks Tests ---


class TestAnnotateChunks:
    def test_annotate_adds_structure_info(self, extractor):
        content = """# Title

- Item 1
- Item 2

```python
code()
```
"""
        doc = Document(
            content=content,
            metadata=DocumentMetadata(source="test.md", format=InputFormat.MARKDOWN),
        )
        structure = extractor.extract(doc)

        # Create a chunk that spans the whole document
        chunk = Chunk(
            id="test_0000",
            content=content,
            document_id="test",
            chunk_index=0,
            metadata=ChunkMetadata(
                token_count=50,
                start_char=0,
                end_char=len(content),
            ),
        )

        annotated = extractor.annotate_chunks([chunk], structure)
        assert len(annotated) == 1

        info = annotated[0].metadata.__dict__.get("structure_info")
        assert info is not None
        assert "sections" in info
        assert "lists" in info
        assert "code_blocks" in info

    def test_annotate_no_overlap(self, extractor):
        content = """# Title

Content here.

---

```python
code()
```
"""
        doc = Document(
            content=content,
            metadata=DocumentMetadata(source="test.md", format=InputFormat.MARKDOWN),
        )
        structure = extractor.extract(doc)

        # Create a chunk that only covers the heading area
        chunk = Chunk(
            id="test_0000",
            content="# Title\n\nContent here.",
            document_id="test",
            chunk_index=0,
            metadata=ChunkMetadata(
                token_count=10,
                start_char=0,
                end_char=25,
            ),
        )

        annotated = extractor.annotate_chunks([chunk], structure)
        info = annotated[0].metadata.__dict__.get("structure_info", {})

        # Should have sections but not code_blocks
        assert "sections" in info
        assert "code_blocks" not in info
