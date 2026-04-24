---
name: example-docx
description: Creates .docx (Microsoft Word) files from user prompts. Use whenever the user asks to produce a Word document, edit a .docx, or export text to Word format.
---

# example-docx

Creates and edits Word documents with `python-docx`.

## When to use

Use this skill when the user's request involves:
- Producing a `.docx` file
- Editing an existing Word document
- Exporting structured text to Word

## How to use

1. Install `python-docx`: `pip install python-docx`
2. Build the document with headings, paragraphs, and tables as needed.
3. Save to a file path the user requested.

## Example

```python
from docx import Document

doc = Document()
doc.add_heading("Title", level=1)
doc.add_paragraph("Body text.")
doc.save("output.docx")
```
