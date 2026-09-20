# Thesis v0.3 delivery QA

Date: 20 September 2026. This is an AI-assisted document review, not independent human or pedagogical validation.

- Built Word from the updated manuscript and figure builders using the bundled Python runtime.
- Rendered the final Word through LibreOffice to a 43-page PDF and full-page PNGs.
- Visually inspected all 43 pages. Corrected orphaned paragraphs, crowded figures and a converging-arrow ambiguity. Final pages 19 and 43 were re-inspected; all other release page PNGs are byte-identical to the individually inspected checked-render pages.
- Verified all table-of-contents heading pages and all eleven figure-caption page mappings against extracted final PDF text.
- Verified eleven embedded Word pictures and sequential bibliography entries 1–25. No unresolved template tokens or API-key-pattern matches in extracted PDF text.
- Checked captions, tables, wrapping, page boundaries, references and appendix paths. No observed clipping or overlapping content remains.
- Published the exact checked PDF to output alongside the editable Word file. Output and source hashes are in build_manifest_v0.3.json.
- Preserved the v0.2 Word/PDF and source snapshot. This update does not run new paid model experiments or change application records.

## Evidence boundaries

Published data retain their dataset, metric, model and table context in the manuscript and literature/v0.3/Source_Ledger.md. The reproduced Lost in the Middle chart has attribution, a CC BY 4.0 license link and crop provenance. The two light-mode interface screenshots are dated 19 September, not fresh captures. Existing R1–R8 records, historical regression checks, simulated replies and AI-assisted judgments remain separately labeled; none is presented as human learner validation. Multimodal generation remains future work.

Pagination was verified using the bundled renderer; editing the Word document or using different fonts can change page numbers. Rebuild and update page_map.json when the manuscript changes.
