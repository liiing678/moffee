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
| paging | How to handle content taller than one slide | scale | scale, auto, none |
| split_lists | Allow lists to break across slides when `paging: auto` | true | true, false |
| split_code | Allow code blocks to break across slides at line boundaries | false | true, false |
| split_tables | Allow tables to break across slides at row boundaries | false | true, false |

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

## Pagination

By default (`paging: scale`), content taller than one slide is shrunk to fit. For long
code blocks, tables, or lists this quickly becomes unreadable. With `paging: auto`,
overflowing content is instead split into continuation slides at block boundaries:

```yaml
---
paging: auto
---
```

The rules are predictable:

- **Blocks stay intact.** Block-level elements (code blocks, tables, figures,
  admonitions, ...) are moved to the next slide as a whole and are never broken
  apart, unless you explicitly allow it with `split_code` / `split_tables`.
  Tables split at row boundaries repeat their header row on the next slide.
- **Lists keep numbering.** Lists may break at item boundaries (`split_lists: true`
  by default); ordered lists continue numbering on the next slide. Set
  `split_lists: false` to keep lists atomic.
- **Continuation markers.** A slide that spills shows a "Continued →" marker at its
  footer, and the continuation slide shows a matching marker at the top. Slide
  numbers are updated automatically.
- **Overflow is reported, not hidden.** A single block taller than one slide (e.g. a
  huge code block with `split_code: false`) is kept intact and flagged with a red
  overflow badge instead of being silently clipped.

Pagination can also be toggled per slide with a local decorator:

```markdown
## A slide with a long table
@(paging=auto, split_tables=true)
```

Use `paging: none` to disable both scaling and pagination for a slide or document.

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
