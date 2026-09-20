# Document citation grouping — 20 September 2026

PDF and Word now show one bibliography entry for each referenced document. Every inline, section, question and answer citation uses the same document number. Exporting leaves saved assets, chunk identifiers, source positions and JSON evidence unchanged.

## Matching and numbering

- An explicit document ID defines a document. Distinct IDs remain separate even when filenames or URLs match.
- Without an ID, matching safe external URLs can identify the same document. URL fragments, hostname case and default ports are normalized; different paths, query strings and non-default ports remain distinct.
- Filenames alone never cause grouping. Unknown sources stay visibly unavailable.
- Numbers follow the saved source order, compacted to documents used by the exported content. Answer-only sources disappear when answers are excluded.
- Repeated group numbers inside one citation are removed. A separate Sources footer is omitted when inline citations already cover its document, while all declared referenced chunk pages still contribute to the bibliography page range.
- Each bibliography entry includes its title, distinct referenced pages, attribution, source URL and license information once. Word keeps each entry together to avoid an orphaned license line on the next page.

## Test and rendering evidence

`tests/test_content_exports.py`: **38 passed in 3.70 seconds**. Cases cover shared IDs and page aggregation, different documents sharing filenames, conservative URL fallback, unknown sources, repeated markers, redundant footers, answer exclusion, compact numbering and the existing bilingual/export safety cases.

| Sample | Input chunks | Exported references | PDF pages | Word pages |
| --- | ---: | ---: | ---: | ---: |
| Saved English ML lesson | 10 | 1 | 3 | 3 |
| Saved Chinese ML lesson | 11 | 1 | 3 | 3 |
| Isolated Chinese quiz | 3 | 2 | 2 | 2 |

All **16 rendered pages** were visually inspected. The final Word bibliography pagination correction was re-rendered and rechecked. English/Chinese text and the quiz's Greek letters, gradient, summation and subscript glyphs are readable. The real lessons show D2L Introduction exactly once in the bibliography. The quiz combines pages 1 and 2 into `第 1-2 页`, retains the second document as reference 2, and starts its answer key on a fresh page. No raw context identifiers, clipped text or overlapping content appeared in the inspected final outputs.

The longer Chinese lesson naturally has its bibliography on a short final page. PDF and Word pagination may differ for arbitrary content. Authored formulas remain text, rather than editable Word equation objects.

## Reproduction and boundaries

`generate_samples.py` reads the existing `after-en-08.json` and `after-zh-07.json` under `docs/rag/auto-exploration/ml-discovery-20260920`, plus an isolated quiz fixture. It calls the production exporter and asserts that the input is unchanged. The example.edu URL and the quiz attributions are synthetic layout fixtures, not externally verified teaching references.

Artifacts were created using the bundled Python runtime. Word was rendered through the bundled headless LibreOffice using the documents skill renderer; PDFs were rendered using bundled Poppler. No model calls, network downloads or normal database mutations were required. Earlier QA records were preserved.

This is export correctness and visual formatting evidence. It does not re-evaluate the factual or pedagogical quality of historical generated lessons, establish retrieval improvements, or prove browser download delivery. Existing source page metadata is preserved; the D2L text records use page 1 and do not imply a newly verified printed-page index.

`source-grouping.json` records exact input hashes, grouped bibliography text and unchanged-source assertions. `manifest.json` records final artifact hashes, sizes, page counts, rendered page hashes and the exporter revision hash. The six PDF/DOCX files and their `final-*` rendering directories are the final QA outputs for this change.
