# Golden Set

Add one real `input.pdf` to each document-type directory before running regression benchmarks. Do not delete originals, renders, crops, ASTs, or logs produced from these documents; they are the platform regression boundary and future training data.

Each directory contains:

- `input.pdf.README`: instructions for the real source document.
- `expected_markdown.md`: expected parse output.
- `expected_ast.json`: expected block structure with bboxes.
- `expected_extraction.json`: expected extracted fields with citations.
