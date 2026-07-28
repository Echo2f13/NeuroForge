"""Structure Extraction Module for NeuroForge.

Detects document structure (TOC, sections, subsections, tables, lists, code blocks)
and builds a section tree from headings. Preserves structural metadata in chunks.

Uses regex and pattern matching — no LLM calls required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from models import Chunk, Document


@dataclass
class SectionNode:
    """A node in the document section tree.

    Attributes:
        heading: The heading text.
        level: Heading level (1-6).
        children: Nested sub-sections.
        content_start: Starting character index of the section content.
        content_end: Ending character index of the section content.
    """

    heading: str
    level: int
    children: list["SectionNode"] = field(default_factory=list)
    content_start: int = 0
    content_end: int = 0


@dataclass
class TableBlock:
    """A detected table region in the document text.

    Attributes:
        start_char: Starting character index of the table.
        end_char: Ending character index of the table.
        rows: Number of rows detected.
        columns: Number of columns detected.
    """

    start_char: int
    end_char: int
    rows: int
    columns: int


@dataclass
class ListBlock:
    """A detected list region in the document text.

    Attributes:
        start_char: Starting character index of the list.
        end_char: Ending character index of the list.
        items: Number of list items.
        nesting_depth: Maximum nesting level (1 = flat list).
    """

    start_char: int
    end_char: int
    items: int
    nesting_depth: int


@dataclass
class CodeBlock:
    """A detected fenced code block in the document text.

    Attributes:
        start_char: Starting character index of the code block.
        end_char: Ending character index of the code block.
        language: Programming language if specified in the fence.
        content: The code content within the fences.
    """

    start_char: int
    end_char: int
    language: Optional[str]
    content: str


@dataclass
class DocumentStructure:
    """Complete structural analysis of a document.

    Attributes:
        sections: Hierarchical section tree.
        tables: Detected table regions.
        lists: Detected list regions.
        code_blocks: Detected fenced code blocks.
    """

    sections: list[SectionNode] = field(default_factory=list)
    tables: list[TableBlock] = field(default_factory=list)
    lists: list[ListBlock] = field(default_factory=list)
    code_blocks: list[CodeBlock] = field(default_factory=list)


class StructureExtractor:
    """Extracts structural elements from document text.

    Detects headings, tables, lists, and code blocks using regex and
    pattern matching. Builds a hierarchical section tree and annotates
    chunks with structural metadata.
    """

    # Markdown heading pattern: # Heading
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    # Fenced code block pattern: ```language ... ```
    CODE_FENCE_PATTERN = re.compile(
        r"^(`{3,})([\w\-+#.]*)\s*\n(.*?)^\1\s*$",
        re.MULTILINE | re.DOTALL,
    )

    # Pipe-delimited table pattern (header | sep | rows)
    PIPE_TABLE_PATTERN = re.compile(
        r"^(\|.+\|)\s*\n(\|[\s\-:|]+\|)\s*\n((?:\|.+\|\s*\n?)+)",
        re.MULTILINE,
    )

    # Whitespace-aligned table: lines with 2+ columns separated by 2+ spaces
    ALIGNED_TABLE_PATTERN = re.compile(
        r"(^(?:\S.+?  +\S.+)\n(?:(?:\S.+?  +\S.+)\n){1,})",
        re.MULTILINE,
    )

    # Bullet list item: -, *, + or • with content
    BULLET_ITEM_PATTERN = re.compile(
        r"^(?P<indent>[ \t]*)(?P<marker>[-*+•])\s+\S", re.MULTILINE
    )

    # Numbered list item: 1. or 1) with content
    NUMBERED_ITEM_PATTERN = re.compile(
        r"^(?P<indent>[ \t]*)(?P<marker>\d+[.\)])\s+\S", re.MULTILINE
    )

    def extract(self, document: Document) -> DocumentStructure:
        """Main entry point: extract all structural elements from a document.

        Args:
            document: The Document object to analyze.

        Returns:
            DocumentStructure with sections, tables, lists, and code blocks.
        """
        text = document.content

        sections = self.build_section_tree(document)
        tables = self.detect_tables(text)
        lists = self.detect_lists(text)
        code_blocks = self.detect_code_blocks(text)

        return DocumentStructure(
            sections=sections,
            tables=tables,
            lists=lists,
            code_blocks=code_blocks,
        )

    def build_section_tree(self, document: Document) -> list[SectionNode]:
        """Build a hierarchical section tree from heading structure.

        Parses markdown-style headings and organizes them into a tree
        where lower-level headings become children of higher-level ones.

        Args:
            document: The Document object to analyze.

        Returns:
            List of top-level SectionNode objects with nested children.
        """
        text = document.content
        matches = list(self.HEADING_PATTERN.finditer(text))

        if not matches:
            return []

        # Build flat list of nodes with positions
        nodes: list[SectionNode] = []
        for i, match in enumerate(matches):
            level = len(match.group(1))
            heading = match.group(2).strip()
            content_start = match.end()
            content_end = (
                matches[i + 1].start() if i + 1 < len(matches) else len(text)
            )

            node = SectionNode(
                heading=heading,
                level=level,
                content_start=content_start,
                content_end=content_end,
            )
            nodes.append(node)

        # Build tree using a stack-based approach
        root_nodes: list[SectionNode] = []
        stack: list[SectionNode] = []

        for node in nodes:
            # Pop from stack until we find a parent (lower level number)
            while stack and stack[-1].level >= node.level:
                stack.pop()

            if stack:
                # This node is a child of the top of the stack
                stack[-1].children.append(node)
            else:
                # This is a top-level node
                root_nodes.append(node)

            stack.append(node)

        return root_nodes

    def detect_tables(self, text: str) -> list[TableBlock]:
        """Detect table regions in text.

        Supports:
        - Pipe-delimited markdown tables (| col1 | col2 |)
        - Whitespace-aligned tables (columns separated by 2+ spaces)

        Args:
            text: The document text to scan.

        Returns:
            List of TableBlock objects for each detected table.
        """
        tables: list[TableBlock] = []

        # Detect pipe-delimited tables
        for match in self.PIPE_TABLE_PATTERN.finditer(text):
            start_char = match.start()
            end_char = match.end()

            # Count columns from header row
            header_row = match.group(1)
            columns = len(
                [c.strip() for c in header_row.strip("|").split("|") if c.strip()]
            )

            # Count rows (header + data rows)
            data_rows = match.group(3).strip().splitlines()
            rows = 1 + len(data_rows)  # header + data rows

            tables.append(
                TableBlock(
                    start_char=start_char,
                    end_char=end_char,
                    rows=rows,
                    columns=columns,
                )
            )

        # Detect whitespace-aligned tables
        for match in self.ALIGNED_TABLE_PATTERN.finditer(text):
            block_text = match.group(0)
            start_char = match.start()
            end_char = match.end()

            # Skip if this region overlaps with a pipe table
            if any(
                t.start_char <= start_char < t.end_char
                or t.start_char < end_char <= t.end_char
                for t in tables
            ):
                continue

            lines = [l for l in block_text.splitlines() if l.strip()]
            rows = len(lines)

            # Estimate columns from first line by splitting on 2+ spaces
            if lines:
                columns = len(re.split(r"  +", lines[0].strip()))
            else:
                columns = 0

            if rows >= 2 and columns >= 2:
                tables.append(
                    TableBlock(
                        start_char=start_char,
                        end_char=end_char,
                        rows=rows,
                        columns=columns,
                    )
                )

        # Sort by position
        tables.sort(key=lambda t: t.start_char)
        return tables

    def detect_lists(self, text: str) -> list[ListBlock]:
        """Detect list regions with nesting levels.

        Supports bullet lists (-, *, +, •) and numbered lists (1., 2), etc.).
        Groups consecutive list items into a single ListBlock.

        Args:
            text: The document text to scan.

        Returns:
            List of ListBlock objects for each detected list.
        """
        # Find all list item positions
        items: list[tuple[int, int, int]] = []  # (start, end_of_line, indent_level)

        for pattern in (self.BULLET_ITEM_PATTERN, self.NUMBERED_ITEM_PATTERN):
            for match in pattern.finditer(text):
                indent = match.group("indent")
                indent_level = len(indent.replace("\t", "    "))
                line_start = match.start()

                # Find end of this list item (next newline that's not continuation)
                line_end = text.find("\n", line_start)
                if line_end == -1:
                    line_end = len(text)

                items.append((line_start, line_end, indent_level))

        if not items:
            return []

        # Sort by position
        items.sort(key=lambda x: x[0])

        # Group consecutive items into list blocks
        lists: list[ListBlock] = []
        group_start = items[0][0]
        group_end = items[0][1]
        group_count = 1
        max_indent = items[0][2]

        for i in range(1, len(items)):
            item_start, item_end, indent_level = items[i]

            # Check if this item is close enough to be part of the same list
            # Allow up to 2 blank lines between items
            gap = text[group_end:item_start]
            if gap.count("\n") <= 2 and not self.HEADING_PATTERN.search(gap):
                group_end = item_end
                group_count += 1
                max_indent = max(max_indent, indent_level)
            else:
                # Close current group and start new one
                nesting = (max_indent // 2) + 1 if max_indent > 0 else 1
                lists.append(
                    ListBlock(
                        start_char=group_start,
                        end_char=group_end,
                        items=group_count,
                        nesting_depth=nesting,
                    )
                )
                group_start = item_start
                group_end = item_end
                group_count = 1
                max_indent = indent_level

        # Don't forget the last group
        nesting = (max_indent // 2) + 1 if max_indent > 0 else 1
        lists.append(
            ListBlock(
                start_char=group_start,
                end_char=group_end,
                items=group_count,
                nesting_depth=nesting,
            )
        )

        return lists

    def detect_code_blocks(self, text: str) -> list[CodeBlock]:
        """Detect fenced code blocks (``` delimited).

        Args:
            text: The document text to scan.

        Returns:
            List of CodeBlock objects for each detected fenced code block.
        """
        code_blocks: list[CodeBlock] = []

        for match in self.CODE_FENCE_PATTERN.finditer(text):
            language = match.group(2).strip() or None
            content = match.group(3)
            start_char = match.start()
            end_char = match.end()

            code_blocks.append(
                CodeBlock(
                    start_char=start_char,
                    end_char=end_char,
                    language=language,
                    content=content,
                )
            )

        return code_blocks

    def annotate_chunks(
        self, chunks: list[Chunk], structure: DocumentStructure
    ) -> list[Chunk]:
        """Add structure info to chunk metadata.

        For each chunk, determines which structural elements it contains
        or overlaps with, and adds that information to the chunk's metadata.

        Args:
            chunks: List of Chunk objects to annotate.
            structure: The DocumentStructure extracted from the document.

        Returns:
            List of Chunk objects with updated metadata (structure_info field).
        """
        for chunk in chunks:
            start = chunk.metadata.start_char
            end = chunk.metadata.end_char
            annotations: dict = {}

            # Find overlapping sections
            sections = self._find_overlapping_sections(
                structure.sections, start, end
            )
            if sections:
                annotations["sections"] = sections

            # Find overlapping tables
            tables = [
                {"rows": t.rows, "columns": t.columns}
                for t in structure.tables
                if self._overlaps(t.start_char, t.end_char, start, end)
            ]
            if tables:
                annotations["tables"] = tables

            # Find overlapping lists
            lists = [
                {"items": l.items, "nesting_depth": l.nesting_depth}
                for l in structure.lists
                if self._overlaps(l.start_char, l.end_char, start, end)
            ]
            if lists:
                annotations["lists"] = lists

            # Find overlapping code blocks
            code_blocks = [
                {"language": cb.language}
                for cb in structure.code_blocks
                if self._overlaps(cb.start_char, cb.end_char, start, end)
            ]
            if code_blocks:
                annotations["code_blocks"] = code_blocks

            # Store annotations in chunk metadata via model_extra or a dict field
            if annotations:
                # Use the chunk's metadata model_dump and reconstruct with extra
                chunk.metadata.__dict__["structure_info"] = annotations

        return chunks

    def _find_overlapping_sections(
        self,
        sections: list[SectionNode],
        start: int,
        end: int,
    ) -> list[dict]:
        """Recursively find sections that overlap with the given range.

        Args:
            sections: List of SectionNode to search.
            start: Start character position.
            end: End character position.

        Returns:
            List of dicts with heading and level for overlapping sections.
        """
        results: list[dict] = []

        for section in sections:
            if self._overlaps(section.content_start, section.content_end, start, end):
                results.append(
                    {"heading": section.heading, "level": section.level}
                )
                # Also check children
                child_results = self._find_overlapping_sections(
                    section.children, start, end
                )
                results.extend(child_results)

        return results

    @staticmethod
    def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
        """Check if two character ranges overlap.

        Args:
            a_start: Start of range A.
            a_end: End of range A.
            b_start: Start of range B.
            b_end: End of range B.

        Returns:
            True if the ranges overlap.
        """
        return a_start < b_end and b_start < a_end
