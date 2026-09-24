# Lumori interim thesis Part I

Current English manuscript: **v0.5, 43 pages**. Formal single-column thesis layout with continuous flow through the main study, a contents page, figure list, literature review, system design, implementation, evaluation and three evidence appendices. Earlier deliverables and source snapshots remain preserved.

- [Editable manuscript](Manuscript.md)
- [Word](../../output/Lumori_Thesis_Part_I_v0.5.docx)
- [PDF](../../output/Lumori_Thesis_Part_I_v0.5.pdf)
- [Verified literature data and permissions](literature/v0.3/Source_Ledger.md)
- [Bibliography](references.json), [figure manifest](figure_manifest.json)
- [Stable evidence IDs, original paths and chronology](evidence_index_v05.json)
- [AI-assisted content audit](review/AI_Content_Review.md)

## Changes in v0.5

The main study flows continuously instead of reserving a separate page for most subsections and figures. Figure dimensions, captions and surrounding paragraphs are coordinated to reduce unnecessary blank space while retaining readable diagrams. The manuscript retains 21 numbered figures, including the existing four light-mode screenshots and archived experimental charts.

Twelve module diagrams are redrawn deterministically with vector source assets, consistent typography, restrained color and explicit control-flow branches. The diagram changes concern presentation; experimental values, denominators, evidence boundaries and conclusions are unchanged. No new model calls or retrieval experiments are part of this revision.

Reader-facing development dates are replaced by experiment rounds, implementation states and version labels. The original dates, repository paths and baseline identity remain available through `evidence_index_v05.json`; no archived run is renamed or rewritten. Published research years and source versions remain accurate. The internal course project brief is removed from the scholarly bibliography, leaving 24 references with synchronized in-text numbering. Requirements remain explicitly attributed to the course project brief, whose original reference is retained in the evidence index.

The v0.4 source and builder snapshot is preserved in `versions/v0.4/`, alongside the earlier v0.4 Word/PDF outputs. The historical notes below describe those versions rather than the current layout.

## Historical v0.4

The v0.4 manuscript had 52 pages and 21 numbered figures (22 pictures, because Figure 15 paired two screenshots). Four light-mode captures showed difficulty allocation, source citations, settings and exports. Formal white-background diagrams added account boundaries, recursive chunking, main-agent/subagent control flow, versioned review/export and the evaluation protocol. Optional paths, feedback loops and future media extensions were explicitly distinguished.

Four charts reproduced archived R7/R8A/R8B tables: a wording-level line chart, aggregate strategy bars, paired outcome counts and grouped sufficiency comparisons. No new retrieval or generation experiments were run. Three diagrams were refined with the built-in image tool from checked graph specifications; the tool did not expose a model identifier. These historical assets and their prompts, source graphs, hashes, screenshot provenance and chart data remain in `figures/v0.4/`.

The v0.3 DOCX/PDF and source/builders are preserved (`versions/v0.3/`).

## Historical v0.3

The v0.3 literature review introduced quantitative comparisons from DPR, semantic chunking, educational objective planning and query/clarification research. Each published value was attached to its task, metric and source location. One CC BY 4.0 chart was reproduced from Liu et al.; six original flow diagrams explained ingestion, query preparation, per-question generation, difficulty acceptance, exploration and job delivery. That version contained 11 figures in total, including the light-mode interface captures and R4 chart.

R6, R7, R8A and R8B are incorporated with their original denominators and negative results. R8A's exposed grouping, R8B's simulated-reply defects, incomplete provider billing and the distinction between ranking and hit rate remain explicit. The exploration development trials are not treated as a fixed-policy success-rate experiment.

The implementation descriptions were expanded to cover 1–50 question slots, native sequential Agent roles, optional fusion, real-user clarification, temporary source indexing, three-round strict difficulty attempts, adjusted-draft acceptance, checkpoint continuation, version ratings and Word/PDF exports. That version used dated source descriptions; old experimental policies were not retrospectively changed. Multimodal output and learner evaluation remained future work. The original v0.2 Word/PDF and source/builder snapshot are also preserved in `versions/v0.2/`.

## Evidence identity

The archived content audit is AI-assisted, non-blind and based on five historical assets: 15 explanatory sections and eight short-answer questions. Ten units received revision recommendations. The report revision does not create human review, teacher approval, new student outcomes or new model evaluations. No production courses, ratings or generated assets were changed.

## Rebuilding

Use the bundled Codex workspace Python runtime with python-docx, Pillow, ReportLab, pypdf and bundled Poppler. Run `scripts/build_thesis_visuals_v05.py` to rebuild the deterministic module diagrams. Archived charts, light-mode screenshots and the licensed external crop remain stored assets.

Then run `scripts/build_thesis_report.py`; it reads `Manuscript.md`, the authoritative `references.json` and the checked `page_map.json`. The report builder no longer automatically rebuilds older figures and makes no model/API calls. Render the DOCX with the documents skill's `render_docx.py --emit_pdf`, inspect every page and update the contents and figure page map from the rendered PDF when pagination changes. Rebuild, render and check again before copying the accepted PDF into `output/`.

Vector companions preserve the current programmatic diagrams and archived charts for later reuse. Their rendered versions are inserted into Word. Historical image-assisted graphics remain in the v0.4 archive. The numerical ledger and original downloaded papers allow later verification. The build manifest records input/output hashes; it does not represent a new frozen runtime release. `build_thesis_review.py` serializes prior judgments and is not a fresh independent evaluation.

Institutional formatting and declarations remain to be confirmed against the official submission template.
