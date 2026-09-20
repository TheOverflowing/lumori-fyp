# Document export rendering verification

Date: 2026-09-20. These are isolated QA fixtures, not user content or research
results. The example.edu source entries are placeholders used to verify citation
formatting. No model calls or normal user database mutations were performed.

## Final outputs

| File | Pages | Check |
| --- | --- | --- |
| lesson-en.pdf | 1 | English lesson, Chinese bibliography, Greek/math symbols and code |
| lesson-en.docx | 1 | Same material, editable Word text, embedded fonts |
| quiz-zh.pdf | 2 | Chinese lesson/questions on page 1; answer key and sources on page 2 |
| quiz-zh.docx | 2 | Same separation with a Word page break before the answer heading |
| quiz-zh-questions-only.pdf | 2 | Questions followed by sources; no answer text or empty answer page |

All eight final page images were opened and visually inspected by the AI
assistant. Chinese text, math symbols including θ, η, ∇, ∑ and xᵢ, code indentation,
page numbers, titles and source records are visible. No clipped content,
overlapping text or missing Chinese glyphs were observed. Word's title is black
without an inherited blue rule. Multisource citations use ordinary numbered
text; a Word layout engine may wrap a citation group at a line ending.

The `final-*` directories contain the authoritative latest renderings. Earlier
`render-*` directories are debugging iterations and are not completion evidence.
The fixture source is `generate_samples.py`; output hashes, sizes and page counts
are in `manifest.json`.

## Rendering and regression verification

PDFs were rendered using bundled Poppler. Word files were rendered using the
required documents skill's `render_docx.py` and the bundled LibreOffice binary:
`/Users/theoverflow/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/MacOS/soffice`.
The user's desktop LibreOffice installation was not used. Artifact-start markers
were run before the first sample creation. The final dedicated export suite
passed 23 tests in 3.57 seconds.

Actual rendering exposed a defect that text extraction did not detect: a
standard unembedded Chinese CID font required viewer language resources, and a
Word font-family name alone did not supply Chinese glyphs. The implementation now
bundles Noto Sans, SC, Math and Mono fonts from official repositories. PDF embeds
used glyph subsets; Word embeds the required complete fonts so recipients can
edit additional characters. See `app/fonts/README.md`, license files and font
checksums for provenance. Chinese Word samples are approximately 7.2 MB because
they include editable fonts; sample PDFs are approximately 70–101 KB.

## Limits

This verifies exported file content and layout. It does not establish that every
browser saves the response to disk. The root task separately observed successful
PDF saving and an IAB-specific unresolved Word download limitation despite a
successful HTTP response; that delivery result must remain distinct from this
file-rendering result.

The renderer exports authored textual mathematics, not LaTeX equation objects.
Characters outside the supplied fonts' full coverage are shown explicitly as
`[U+XXXX]`, never silently omitted; saved material is unchanged. Audio/video
content and media-download APIs are outside this document-rendering subtask.
