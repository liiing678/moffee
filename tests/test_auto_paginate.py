import pytest
import warnings
from moffee.compositor import composite
from moffee.pagination import split_blocks, estimate_height, paginate_text


def make_long_code_doc(lines=30):
    code = "\n".join(f"line {i}" for i in range(lines))
    return f"""
## Deep Dive

Some intro text.

```python
{code}
```
"""


def test_code_block_not_split_by_default():
    pages = composite(make_long_code_doc())
    code_pages = [p for p in pages if "```" in p.raw_md]
    assert len(code_pages) == 1
    # the whole block stays on one page, closing fence included
    assert "line 29" in code_pages[0].raw_md
    assert code_pages[0].raw_md.count("```") == 2


def test_oversized_block_warns():
    with pytest.warns(UserWarning, match="exceeds the page budget"):
        composite(make_long_code_doc())


def test_split_code_when_allowed():
    doc = "---\nsplit_code: true\n---\n" + make_long_code_doc()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pages = composite(doc)
    assert not [w for w in caught if "exceeds the page budget" in str(w.message)]
    code_pages = [p for p in pages if "```" in p.raw_md]
    assert len(code_pages) > 1
    for page in code_pages:
        # every part is a valid fenced block again
        assert page.raw_md.count("```") == 2
    joined = "\n".join(p.raw_md for p in code_pages)
    for i in range(30):
        assert f"line {i}" in joined


def test_table_not_split_by_default():
    rows = "\n".join(f"| r{i} | v{i} |" for i in range(20))
    doc = f"""
## Data

| name | value |
| ---- | ----- |
{rows}
"""
    with pytest.warns(UserWarning):
        pages = composite(doc)
    table_pages = [p for p in pages if "| name |" in p.raw_md]
    assert len(table_pages) == 1
    assert "| r19 | v19 |" in table_pages[0].raw_md


def test_split_table_repeats_header():
    rows = "\n".join(f"| r{i} | v{i} |" for i in range(20))
    doc = f"""---
split_tables: true
---
## Data

| name | value |
| ---- | ----- |
{rows}
"""
    pages = composite(doc)
    table_pages = [p for p in pages if "| name |" in p.raw_md]
    assert len(table_pages) > 1
    for page in table_pages:
        # header and delimiter are repeated on every part
        assert "| ---- | ----- |" in page.raw_md


def test_ordered_list_numbering_continuous():
    items = "\n".join(f"{i}. item {i}" for i in range(1, 21))
    doc = f"""
## Steps

{items}
"""
    pages = composite(doc)
    assert len(pages) > 1
    first_page_items = pages[0].raw_md.count(". item")
    # continuation page resumes numbering where the previous page stopped
    expected = first_page_items + 1
    second_lines = pages[1].raw_md.splitlines()
    assert second_lines[0].startswith(f"{expected}. ")


def test_unordered_list_split_at_item_boundary():
    items = "\n".join(f"- bullet {i}" for i in range(20))
    doc = f"""
## Bullets

{items}
"""
    pages = composite(doc)
    assert len(pages) > 1
    for page in pages:
        for line in page.raw_md.splitlines():
            assert line.startswith("- "), f"list split mid-item: {line!r}"


def test_continued_flags():
    items = "\n".join(f"- bullet {i}" for i in range(20))
    doc = f"""
## Bullets

{items}
"""
    pages = composite(doc)
    assert pages[0].continues is True
    assert pages[0].continued is False
    assert pages[-1].continues is False
    assert pages[-1].continued is True
    for page in pages[1:]:
        # continuation pages inherit the section title
        assert page.h2 == "Bullets"


def test_auto_paginate_disabled():
    items = "\n".join(f"- bullet {i}" for i in range(20))
    doc = f"""---
auto_paginate: false
---
## Bullets

{items}
"""
    pages = composite(doc)
    assert len(pages) == 1


def test_local_deco_override():
    items = "\n".join(f"- bullet {i}" for i in range(20))
    doc = f"""
## Bullets
@(auto_paginate=false)

{items}
"""
    pages = composite(doc)
    assert len(pages) == 1


def test_paragraphs_pack_greedily():
    para = "word " * 30  # ~4 estimated lines per paragraph
    doc = "\n\n".join([para] * 8)
    pages = composite(doc)
    assert len(pages) > 1
    for page in pages:
        blocks = split_blocks(page.raw_md)
        total = sum(estimate_height(b) for b in blocks)
        assert total <= pages[0].option.page_budget + 1e-6


def test_small_document_untouched():
    doc = """
## Title

Short text.

- one
- two
"""
    pages = composite(doc)
    assert len(pages) == 1
    assert pages[0].continues is False
    assert pages[0].continued is False


def test_paginate_text_empty():
    assert paginate_text("", budget=12) == []
    assert paginate_text("   \n\n  ", budget=12) == []


def test_single_unsplittable_item_warns():
    huge_item = "- " + "word " * 200
    with pytest.warns(UserWarning):
        pages = paginate_text(huge_item, budget=12)
    assert len(pages) == 1
    assert pages[0] == huge_item


if __name__ == "__main__":
    pytest.main()
