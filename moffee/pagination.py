"""
Predictable, block-aware auto-pagination for oversized slides.

The rules are deliberately simple so users can reason about them:

- Content is parsed into block-level elements (paragraphs, headings,
  fenced code blocks, tables and lists).
- Every block has an estimated height measured in "lines" (a CJK character
  counts as two columns). Blocks are packed greedily into pages of at most
  ``budget`` lines.
- A block is never split across pages unless the corresponding
  ``split_*`` option allows it:
    - lists may split at top-level item boundaries (ordered lists keep
      their numbering continuous across pages),
    - fenced code blocks split at line boundaries, keeping the fence,
    - tables split at row boundaries, repeating the header row.
- A block that does not fit on a page of its own and may not be split
  triggers a clear warning and is placed on a dedicated page.
"""

import math
import re
import unicodedata
import warnings
from dataclasses import dataclass
from typing import List, Optional

# Estimated number of half-width characters that fit on one content line.
CHARS_PER_LINE = 40
# Vertical whitespace accounted to every block (margins between blocks).
BLOCK_MARGIN = 0.5

LIST_ITEM_RE = re.compile(r"^(\s*)(?:[-*+]|\d{1,9}[.)])\s+")
ORDERED_ITEM_RE = re.compile(r"^(\s*)(\d{1,9})([.)])(\s+)")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)(.*)$")
HEADING_RE = re.compile(r"^#{1,6}\s")
TABLE_DELIM_RE = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")


@dataclass
class Block:
    kind: str  # "paragraph" | "heading" | "code" | "table" | "list"
    lines: List[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _text_width(s: str) -> int:
    """Display width of a string; CJK wide/fullwidth chars count as 2."""
    return sum(
        2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s
    )


def _wrap_lines(s: str) -> int:
    return max(1, math.ceil(_text_width(s) / CHARS_PER_LINE))


def estimate_height(block: Block) -> float:
    """Estimated block height in lines, including inter-block margin."""
    if block.kind == "code":
        return len(block.lines) + 1 + BLOCK_MARGIN
    if block.kind == "table":
        return len(block.lines) + 1 + BLOCK_MARGIN
    if block.kind == "heading":
        return 2 + BLOCK_MARGIN
    if block.kind == "list":
        return (
            sum(_wrap_lines(line.strip()) for line in block.lines if line.strip())
            + BLOCK_MARGIN
        )
    # paragraph
    return _wrap_lines(" ".join(l.strip() for l in block.lines)) + BLOCK_MARGIN


def _is_table_start(lines: List[str], i: int) -> bool:
    if i + 1 >= len(lines):
        return False
    return (
        "|" in lines[i]
        and bool(TABLE_DELIM_RE.match(lines[i + 1]))
        and "-" in lines[i + 1]
    )


def _consume_list(lines: List[str], i: int) -> int:
    """Return the index one past the last line of the list starting at i."""
    j = i
    while j < len(lines):
        line = lines[j]
        if line.strip() == "":
            # The list continues only if the next non-blank line is an
            # item or an indented continuation.
            k = j
            while k < len(lines) and lines[k].strip() == "":
                k += 1
            if k < len(lines) and (
                LIST_ITEM_RE.match(lines[k])
                or lines[k].startswith("  ")
                or lines[k].startswith("\t")
            ):
                j = k
                continue
            break
        if (
            LIST_ITEM_RE.match(line)
            or line.startswith("  ")
            or line.startswith("\t")
        ):
            j += 1
            continue
        break
    return j


def split_blocks(text: str) -> List[Block]:
    """Split markdown text into block-level elements."""
    lines = text.split("\n")
    blocks: List[Block] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.strip() == "":
            i += 1
            continue
        fence = FENCE_RE.match(line)
        if fence:
            j = i + 1
            while j < n and not FENCE_RE.match(lines[j]):
                j += 1
            j = min(j + 1, n)  # include closing fence (or EOF)
            blocks.append(Block("code", lines[i:j]))
            i = j
        elif _is_table_start(lines, i):
            j = i + 2
            while j < n and "|" in lines[j] and lines[j].strip():
                j += 1
            blocks.append(Block("table", lines[i:j]))
            i = j
        elif LIST_ITEM_RE.match(line):
            j = _consume_list(lines, i)
            blocks.append(Block("list", lines[i:j]))
            i = j
        elif HEADING_RE.match(line):
            blocks.append(Block("heading", [line]))
            i += 1
        else:
            j = i
            while (
                j < n
                and lines[j].strip() != ""
                and not FENCE_RE.match(lines[j])
                and not HEADING_RE.match(lines[j])
            ):
                j += 1
            blocks.append(Block("paragraph", lines[i:j]))
            i = j
    return blocks


def _list_items(lines: List[str]) -> List[List[str]]:
    """Group list lines into top-level items (with their continuations)."""
    base = len(LIST_ITEM_RE.match(lines[0]).group(1))
    items: List[List[str]] = []
    for line in lines:
        m = LIST_ITEM_RE.match(line)
        if m and len(m.group(1)) <= base:
            items.append([line])
        elif items:
            items[-1].append(line)
        else:
            items.append([line])
    return items


def _renumber(items: List[List[str]], start: int) -> List[str]:
    """Render items, rewriting top-level ordered markers from ``start``."""
    out: List[str] = []
    number = start
    for item in items:
        m = ORDERED_ITEM_RE.match(item[0])
        if m:
            head = f"{m.group(1)}{number}{m.group(3)}{m.group(4)}"
            item = [head + item[0][m.end():]] + item[1:]
        out.extend(item)
        number += 1
    return out


def _split_list(block: Block, budget: float) -> Optional[List[Block]]:
    items = _list_items(block.lines)
    if len(items) < 2:
        return None
    limit = budget - BLOCK_MARGIN
    heights = [
        sum(_wrap_lines(line.strip()) for line in item if line.strip())
        for item in items
    ]
    if any(h > limit for h in heights):
        return None  # a single item does not fit; leave the list whole
    ordered = ORDERED_ITEM_RE.match(block.lines[0])
    start = int(ordered.group(2)) if ordered else None
    parts: List[List[List[str]]] = []
    current: List[List[str]] = []
    used = 0.0
    for item, h in zip(items, heights):
        if current and used + h > limit:
            parts.append(current)
            current, used = [], 0.0
        current.append(item)
        used += h
    if current:
        parts.append(current)
    if len(parts) < 2:
        return None
    blocks: List[Block] = []
    number = start
    for part in parts:
        if start is not None:
            lines = _renumber(part, number)
            number += len(part)
        else:
            lines = [line for item in part for line in item]
        blocks.append(Block("list", lines))
    return blocks


def _split_code(block: Block, budget: float) -> Optional[List[Block]]:
    if len(block.lines) < 3:
        return None
    opening, closing = block.lines[0], block.lines[-1]
    body = block.lines[1:-1]
    # part height = body lines + 2 fences + 1 padding + margin
    per_part = max(1, int(budget - 3 - BLOCK_MARGIN))
    if len(body) <= per_part:
        return None
    blocks = []
    for i in range(0, len(body), per_part):
        chunk = body[i : i + per_part]
        blocks.append(Block("code", [opening] + chunk + [closing]))
    return blocks


def _split_table(block: Block, budget: float) -> Optional[List[Block]]:
    if len(block.lines) < 3:
        return None
    header, rows = block.lines[:2], block.lines[2:]
    # part height = rows + 2 header lines + 1 padding + margin
    per_part = max(1, int(budget - 3 - BLOCK_MARGIN))
    if len(rows) <= per_part:
        return None
    return [
        Block("table", header + rows[i : i + per_part])
        for i in range(0, len(rows), per_part)
    ]


def _split_block(
    block: Block,
    budget: float,
    split_lists: bool,
    split_code: bool,
    split_tables: bool,
) -> Optional[List[Block]]:
    if block.kind == "list" and split_lists:
        return _split_list(block, budget)
    if block.kind == "code" and split_code:
        return _split_code(block, budget)
    if block.kind == "table" and split_tables:
        return _split_table(block, budget)
    return None


def paginate_text(
    text: str,
    budget: float,
    split_lists: bool = True,
    split_code: bool = False,
    split_tables: bool = False,
    page_label: str = "untitled",
) -> List[str]:
    """
    Split markdown text into page-sized segments.

    Returns a list with the original text when everything fits on one page.
    """
    budget = max(4, budget)
    blocks = split_blocks(text)
    if not blocks:
        return []

    pages: List[str] = []
    current: List[Block] = []
    used = 0.0

    def flush():
        nonlocal current, used
        if current:
            pages.append("\n\n".join(b.text for b in current))
            current, used = [], 0.0

    for block in blocks:
        height = estimate_height(block)
        if height > budget:
            parts = _split_block(
                block, budget, split_lists, split_code, split_tables
            )
            if parts is None:
                warnings.warn(
                    f"moffee: a {block.kind} block (~{height:.0f} lines) exceeds "
                    f"the page budget ({budget} lines) on page "
                    f"'{page_label}' and may not be split; it will overflow "
                    f"its slide. Allow splitting (split_lists/split_code/"
                    f"split_tables) or shorten the block.",
                    UserWarning,
                    stacklevel=2,
                )
                flush()
                pages.append(block.text)
                continue
            for part in parts:
                part_height = estimate_height(part)
                if current and used + part_height > budget:
                    flush()
                current.append(part)
                used += part_height
            continue
        if current and used + height > budget:
            flush()
        current.append(block)
        used += height
    flush()
    return pages
