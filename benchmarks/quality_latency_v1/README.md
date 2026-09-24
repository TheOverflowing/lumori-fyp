# Q1 quality / latency DEV dataset

24 single-question generation tasks: 12 bilingual paired learning needs across operating systems, databases, and networking. Each course has 8 tasks; each difficulty has 8; both question types and languages have 12 each.

This is an **AI-prepared provisional development pilot**, not a human-annotated or unseen benchmark. Original material is English; EN and ZH prompts share the same source pool per course. The assessment rubric is private to evaluation, not the generation pipeline.

- `dataset.json`: inline source text, prompt fields, private evidence anchors / review criteria.
- `manifest.json`: dataset, source, license and builder SHA-256; balanced task counts.
- `sources/download-manifest.json`: original official URLs, retrieval time, raw HTML hashes.
- `sources/*.html`: original text snapshots, never executed.
- `sources/*.txt`: selected plain-text excerpts and required source license notices.
- `build_dataset.py`, `extract_paragraphs.py`: deterministic, offline extraction and dataset builder.
- Protocol: `docs/evaluation/Q1_QUALITY_LATENCY_PROTOCOL.md`.

Rebuild from the repository root:

```sh
.venv/bin/python benchmarks/quality_latency_v1/build_dataset.py
.venv/bin/python benchmarks/quality_latency_v1/validate_dataset.py
```

Rebuilding intentionally regenerates the freeze manifest; ordinary integrity validation never rewrites the frozen files. Preserve a run's original manifest when comparing experiments.

Generation input allowlist: `course`, `language`, `difficulty`, `question_type`, `topic`, `learner_profile`. **Never pass** `source_ids`, `expected_evidence`, `review_criteria`, or `grading_expectations` to author/solver/reviewer prompts. Index and retrieve the entire course corpus, not just the expected source. Source IDs are evaluation labels, not filters.

## Attribution and transformation

- MIT xv6 book by Russ Cox, Frans Kaashoek, and Robert Morris, Massachusetts Institute of Technology. [Official book](https://mit-pdos.github.io/xv6-riscv-book/). MIT license, archived in `sources/xv6-license.txt`.
- PostgreSQL 18 documentation by The PostgreSQL Global Development Group. [Official documentation](https://www.postgresql.org/docs/18/). PostgreSQL license, archived in `sources/postgres-license.txt`.
- *Computer Networks: A Systems Approach* by Larry Peterson and Bruce Davie, copyright Elsevier, 2012. [Official book](https://book.systemsapproach.org/) / [source repository](https://github.com/SystemsApproach/book). Creative Commons Attribution 4.0, archived in `sources/systems-approach-license.txt`.

Selected complete HTML paragraph and heading blocks were extracted, entities decoded and whitespace normalized. Excerpts may omit intervening paragraphs. Figures, code blocks, tables and displayed equations are excluded. These changes are identified in each source's provenance; the original snapshots allow inspection. A repository revision attached to a license identifies that license snapshot only, not an assumed build revision of the live HTML.

Dataset learning needs, bilingual input text and provisional rubrics were prepared by the AI assistant for this project. They are not original teacher-authored questions, verified human translations, or empirical difficulty labels. All cases remain `split=dev`.
