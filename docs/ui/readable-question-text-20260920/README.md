# Readable question text — 2026-09-20

The reported reinforcement-learning questions contained several premises in one continuous heading. HTML collapsed authored newlines, and inline `(1)…(2)…` / `Claim 1…Claim 2…` sequences had no visual separation.

| Before | After | Reason |
| --- | --- | --- |
| Entire long stem rendered as a heading | Separate question number and body text with a readable line height | Distinguish navigation headings from the question itself |
| Consecutive claims/numbered premises ran together | Conservative sequence detection creates separate list items with hanging labels | Make each premise easy to scan without rewriting it |
| Newlines collapsed in stems and choices | Preserve authored newlines and blank paragraphs across stems, choices, answers and explanations | Respect the author's intended structure |
| New content had no shared layout guidance | Agent, legacy author and CPU conceptual-composition prompts share paragraph guidance | Encourage well-structured output without a new rejection gate |

`app/static/readable-text.js` is a presentation-only adapter used by the shared content renderer. It requires consecutive numbering, an explicit introductory boundary and substantial item text before inferring lists. Unlabelled numbers additionally require sentence punctuation or a newline between items. Code/math spans, URLs, ordinary equation references and nonconsecutive numbers remain unmodified. Exact wording, labels, citation IDs and saved assets are preserved; no HTML supplied by a model is interpreted. A clear final question after a list gets its own paragraph. Ambiguous structures remain as authored.

Question headings retain accessible “Question N” labels. Review and learning views use the same presentation. Answer disclosure and citation controls keep their existing behavior. Existing files and export data are not rewritten; future generation is prompted to include real decoded line breaks in its existing JSON text fields.

## Verification

- **219 frontend tests passed**, including six focused tests covering English and Chinese lists, paragraph/newline preservation, code indentation, math/reference false positives, HTML escaping, citations, saved-asset immutability and answer hiding. [Test output](frontend-tests.txt).
- **172 existing backend tests passed** for author contracts, Agent/legacy generation, optional introductions, CPU and flexible workflows. The only warnings were two existing dependency deprecations. Changed backend files passed compilation checks.
- Browser fixture uses production CSS, content rendering and citation controls, with text transcribed from the supplied screenshots. It uses no database and makes no model calls. Desktop and 390 px layouts were inspected in light/dark themes. On the narrow view, `scrollWidth == innerWidth == 390`; all 10 premises across three questions remained distinct.
- Expanded an answer, verified its paragraph and single-line breaks, opened its citation preview, then verified the learning view had three lists, zero answer panels and zero citation controls. No browser warnings/errors were observed.
- [Desktop screenshot](desktop.png) and [mobile screenshot](mobile.png). The samples are UI fixtures, not evaluated educational outputs.

Reproduce with `.venv/bin/python -m uvicorn scripts.readable_text_fixture_server:create_fixture --factory --host 127.0.0.1 --port 8772`; use `/` for review rendering and `/?view=learning` for hidden-answer rendering.
