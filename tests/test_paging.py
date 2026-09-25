import json
import os
import re

import pytest

from moffee.builder import paging_config, render_jinja2
from moffee.compositor import PageOption, composite, parse_frontmatter


def template_dir(name="base"):
    return os.path.join(os.path.dirname(__file__), "..", "moffee", "templates", name)


def test_paging_defaults():
    option = PageOption()
    assert option.paging == "scale"
    assert option.split_lists is True
    assert option.split_code is False
    assert option.split_tables is False


def test_paging_frontmatter():
    doc = """
---
paging: auto
split_code: true
split_tables: true
split_lists: false
---
# Title
Content
"""
    _, options = parse_frontmatter(doc)
    assert options.paging == "auto"
    assert options.split_code is True
    assert options.split_tables is True
    assert options.split_lists is False
    # paging options must not leak into CSS styles
    assert options.styles == {}


def test_paging_deco():
    doc = """
# Title
Content
@(paging=auto, split_code=true)
"""
    pages = composite(doc)
    assert pages[0].option.paging == "auto"
    assert pages[0].option.split_code is True
    assert pages[0].option.split_tables is False


def test_paging_config_invalid_mode_falls_back():
    option = PageOption(paging="bogus")
    assert paging_config(option)["mode"] == "scale"


def test_paging_config_serialization():
    option = PageOption(paging="auto", split_code=True)
    cfg = paging_config(option)
    assert cfg == {
        "mode": "auto",
        "splitLists": True,
        "splitCode": True,
        "splitTables": False,
    }
    json.dumps(cfg)


def test_render_emits_paging_attributes():
    doc = """
---
paging: auto
split_lists: false
---
# Title
Content
---
## Second
@(paging=none)
More
"""
    html = render_jinja2(doc, template_dir())
    modes = re.findall(r'data-paging-mode="(\w+)"', html)
    assert modes == ["auto", "none"]

    payloads = re.findall(r"data-paging='([^']+)'", html)
    assert len(payloads) == 2
    first = json.loads(payloads[0])
    assert first["mode"] == "auto"
    assert first["splitLists"] is False
    assert first["splitCode"] is False
    second = json.loads(payloads[1])
    assert second["mode"] == "none"


def test_render_includes_paginate_script():
    html = render_jinja2("# Title\nContent", template_dir())
    assert 'src="js/paginate.js"' in html
    # paginate.js must load before main.js so pagination runs before auto-scaling
    assert html.index("paginate.js") < html.index("main.js")


if __name__ == "__main__":
    pytest.main()
