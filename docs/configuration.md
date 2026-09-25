# Configuration

## Front Matter Options

moffee's behavior can be customized using front matter at the beginning of your document. Here's a comprehensive table of available options:

| Option | Description | Default Value | Available Options |
|--------|-------------|---------------|-------------------|
| [theme](theme.md) | Visual theme for the presentation | default | default, beam, robo, blue, gaia |
| layout | HTML template for slide layout | content | content, centered |
| resource_dir | Base directory for relative URLs | . (current directory) | Any valid directory path |
| default_h1 | Inherit H1 from previous slides if not defined | false | true, false |
| default_h2 | Inherit H2 from previous slides if not defined | true | true, false |
| default_h3 | Inherit H3 from previous slides if not defined | true | true, false |
| aspect_ratio | Aspect ratio of the slides | "16:9" | "16:9", "4:3" |
| slide_width | Width of the slides | 720 | Any number |
| slide_height | Height of the slides | 405 | Any number |
| auto_paginate | Split oversized slides at block boundaries | true | true, false |
| page_budget | Maximum estimated content lines per slide | 12 | Any number >= 4 |
| split_lists | Allow lists to break at item boundaries | true | true, false |
| split_code | Allow fenced code blocks to split across pages | false | true, false |
| split_tables | Allow tables to split across pages (header repeats) | false | true, false |
| continued_marker | Footer marker on pages that continue on the next slide | "→ continued" | Any string, "" to hide |

### Default Front Matter

```yaml
---
theme: default
layout: content
resource_dir: "."
default_h1: false
default_h2: true
default_h3: true
aspect_ratio: "16:9"
slide_width: 720
slide_height: 405
---
```

## Custom CSS Properties

You can set any CSS property in the front matter to apply it globally to all slides. For example:

```yaml
---
layout: content
background-color: darkgray
color: white
---
```

## Local Style Decorators

moffee supports local style decorators for individual slides using the syntax `@(property=value)`. These can be used within the document to set attributes for specific slides.

### Example:

```markdown
# A refined landing page
Our journey begins here
@(layout=content, background-image='url("https://placehold.co/600x400")')
```

## Auto Pagination

When a slide's content exceeds `page_budget` estimated lines, moffee splits it
into multiple slides at block boundaries instead of letting it overflow or
shrink to an unreadable size. The rules are deliberately predictable:

- Content is parsed into block-level elements: paragraphs, headings, fenced
  code blocks, tables and lists. Heights are estimated in lines (a CJK
  character counts as two columns) and blocks are packed greedily into pages.
- **Blocks are never split** unless you opt in: `split_lists` (default on)
  breaks lists at item boundaries, `split_code` and `split_tables` (default
  off) break code blocks and tables. Split tables repeat their header row,
  and split ordered lists keep their numbering continuous across pages.
- A block that does not fit on a page of its own and may not be split is
  placed on a dedicated slide and moffee prints a **warning** naming the
  page and the block, so the overflow is never silent.
- Pages that continue on the next slide show `continued_marker` in the
  footer; continuation slides inherit the current section titles.

All options work globally in the front matter and per slide via decorators:

```yaml
---
page_budget: 14
split_code: true
continued_marker: "→ continued on next page"
---
```

```markdown
## A slide that must stay on one page
@(auto_paginate=false)
```
