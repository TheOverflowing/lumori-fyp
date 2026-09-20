# Machine-learning discovery: independent AI content review

Reviewed on 2026-09-20. Reviewer: Codex, using the saved request, generated asset, coverage decisions and final source excerpts. **This is AI-assisted review, not human annotation, a learner study, or a measured accuracy score.** No new provider calls were made for this review. No source JSON or production code was changed.

The review concerns these exact snapshots, including failures. Subsequent implementation changes and reruns must be reported separately.

| Snapshot | SHA-256 | Recorded result |
| --- | --- | --- |
| [after-en-05.json](after-en-05.json) | `feceb4dcb8be8d204d2b6b5095532a167ef9bbf4757a41e8816854c53c977395` | `succeeded`; exploration `sources_sufficient` |
| [after-zh-03.json](after-zh-03.json) | `759f3761facce97d84c8ba0a758628ec93fa86ab90e6b4c495e5162a7cc40b38` | `insufficient_evidence`; exploration `search_budget` |

Both requests use the same English objective, “Could u give me a brief introduction about machine learning?”, with output language `en` and `zh` respectively. This is not a comparison between independently authored English and Chinese user questions.

## English snapshot: operational success, incomplete teaching coverage

The system fetched and saved a real reference, retrieved source context, and produced an English lesson. The accepted source is the author-maintained *Dive into Deep Learning* introduction in its public repository. All section citation IDs resolve to the 14 recorded final sources. All final coverage quotations occur exactly in their referenced source excerpts. These checks establish reference integrity, **not semantic sufficiency**.

The principal unresolved issue is the treatment of learning categories:

- `exploration.assessments[0].requirements[1]` freezes `g2` as the main types of machine learning, explicitly naming supervised, unsupervised and reinforcement learning.
- `exploration.assessments[1].requirements[1].covered` is nevertheless `true`. Its four supports discuss supervised learning, give a general introduction to categories, discuss classification, and quote only the heading `### Reinforcement Learning`.
- The heading-only support is exactly `exploration.assessments[1].requirements[1].supports[3]`, a 26-character quote. The corresponding raw choice is passage `p26` in `structured_model_outputs[2]`.
- None of the 14 `evidence.sources` explains unsupervised learning. None of the eight `asset.sections` explains or names it. Manual reading also finds no equivalent explanation through unlabelled data or clustering. Thus the frozen `g2` requirement is not fully satisfied, despite the positive coverage decision and `asset.evidence_sufficient=true`.

This does **not** mean that the generated reinforcement-learning section is supported only by a title. `evidence.sources[12]`, ID `context_b46caa06fd509aa4fc69077de9aa6b6a`, contains the full paragraph about agents, environments, actions and examples. `asset.sections[6]` follows that paragraph. The defect is the sufficiency judgment and omission of a required category; most visible lesson explanations have identifiable supporting prose.

The response also underserves the word “brief”. It contains eight sections, seven learning objectives and approximately 870 body words. The reproducible count is 869 matches using `re.findall(r'\b[\w-]+\b', section['text'])`, summed over `asset.sections`; this includes citation-ID tokens. No explicit user word limit was set, so excessive length is a style/intent concern rather than a failed numerical constraint.

**Review disposition:** usable evidence acquisition and traceability demonstrated; the artifact needs revision before being described as fully covering its own frozen teaching requirements. Do not label this snapshot “content quality passed” solely because the job succeeded.

## Chinese-output snapshot: sources found, generation correctly withheld

This run accepted and saved one real reference, so it must not be described as “no network material found”. Its final outcome was `insufficient_evidence` with no generated asset.

- `exploration.assessments[0].requirements` contains four frozen requirements. In addition to the definition, three learning categories and basic workflow, `g4` requires overfitting, underfitting **and their remedies**.
- This detailed `g4` was added by the system's initial interpretation; the user only asked for a brief introduction. The reviewer considers that scope unnecessarily demanding for the original request. Once frozen, however, omitting it silently would make the audit inconsistent.
- `exploration.assessments[1]` remains `missing_knowledge`: `g1` and `g3` are covered, while `g2` and `g4` are not. The last coverage model input is preserved in `structured_model_outputs[3].input.sources`; it is intermediate evidence, not a successfully published final source set.
- `exploration.search_calls` is 6, matching this smoke run's configured search limit. `exploration.rounds` is 2 and `exploration.reason` is `search_budget`. The rejection log also records several `fetch_failed` downloads and a redundant `no_new_coverage` candidate.

**Review disposition:** real source acquisition succeeded, and the final coverage check withheld unsupported output. The user still received no introductory lesson. This illustrates a remaining scope-planning and evidence-coverage limitation, not a successful Chinese teaching artifact.

## How to report these observations

Keep operational completion, source-reference integrity, content completeness and user-intent fit as separate outcomes. These two traces support diagnosis of specific weaknesses: a heading can be mistaken for substantive evidence; a multi-part requirement can be marked complete while a named part is absent; a brief request can acquire unnecessary mandatory subtopics. They do not establish recall, citation precision, learner benefit, or a language-specific success rate.

Later fixes may remove headings from selectable evidence or constrain initial scope. They do not retroactively change either snapshot's recorded result or this review's findings.

## Follow-up review: EN06 and ZH04

This section records later snapshots independently. The previous EN05/ZH03 findings remain unchanged. The same AI-review limitations apply.

| Snapshot | SHA-256 | Recorded result | Elapsed time / ledger operations |
| --- | --- | --- | --- |
| [after-en-06.json](after-en-06.json) | `4035ff4ad25cf7f9a2b7e7767ee32bc4cf92147977d8760b3e94e7b9e453ee21` | `succeeded`; `sources_sufficient` | 48,042 ms / 19 |
| [after-zh-04.json](after-zh-04.json) | `d9fe24ff4bf4d4b7c66229f4f94557e45694fc8dc5722a7ba8e42db89e6b04d3` | `insufficient_evidence`; `search_budget` | 56,103 ms / 18 |

Ledger operations include local directory searches; these counts must not be presented as counts of paid model calls. The elapsed times are observations from individual runs with different requirement plans, not a controlled performance comparison.

### EN06: this run's three requirements are supported

`exploration.assessments[0].requirements` contains three requirements: a concise definition (`g1`), learning from data rather than manually specifying the input/output mapping (`g2`), and a simple example (`g3`). The category taxonomy and challenges required in EN05 are **not** frozen requirements for this new run.

- The final `g1` support includes the substantive definition in `context_1acdc2cdfb08d547bd96e71342a38740`. `asset.sections[0]` explains it.
- The final `g2` support includes the description of selecting model parameters from labelled wake-word data in `context_54e3fc2d195ae1c3d8f6b91c032be535`, plus the programming-with-data explanation in `context_41df63913f1d39bf550d03b87eea052d`. `asset.sections[2]` conveys that distinction.
- The same wake-word example and the actual training steps in `context_53afef624abe10681bc1b026f6ec924b` support `g3`; `asset.sections[2:4]` gives the example and process.

All final coverage quotations are contiguous text in their cited sources, all section citation IDs resolve to the seven final sources, and no final coverage support consists solely of a Markdown heading. Reading the generated explanations against those sources, the reviewer finds this run's three planned requirements covered. Omitting unsupervised learning is therefore not the EN05 defect repeated against EN06's different plan.

The lesson still contains five sections, five objectives and 399 body-word tokens under the same counting convention used above. This is shorter and more focused than EN05, though an ordinary conversational “brief introduction” could be more compact. **Disposition: the saved English artifact covers its three recorded requirements under this AI review; no general accuracy or teaching-effectiveness claim follows.**

### ZH04: relevant material exists, but the required passage was missed

ZH04 freezes four requirements: definition, the three main learning categories, basic workflow, and a simple example. Its final assessment covers `g1`, `g3` and `g4`, leaves `g2` uncovered, and stops at the search budget without publishing an asset. It does not repeat ZH03's requirement for underfitting and remedies.

The missing unsupervised-learning explanation exists in the accepted source. The selection input `structured_model_outputs[1].input.passages` contains passage `p2`, whose source ID is `chunk_a75fd556e918fc0a6ec4fa3ff7f4a38b550895d8dc4c93fe4436fae47f22c6d5`. It begins with the unsupervised/self-supervised section title, but the following paragraph is a recap of **supervised** learning. The real unsupervised explanation comes in the next paragraph and was not among the selected candidate passages. The final coverage input, `structured_model_outputs[2].input.sources`, mentions unsupervised learning only in a general discussion of offline interaction, without supplying its defining explanation.

The reviewer also checked this run's existing temporary database read-only. The accepted document `4aadc15b21c1437c88fd6072830ebcde` has original SHA-256 `fa8e9a8cbe58a2dcb2e7e8a45b86b05c3b45ee0ba370ea4777fbd8856c045db5`. In its saved parsed page 1, character range `[43742, 44373)` contains the missing introductory paragraph. The next indexed leaf, ID `e94f2b8005f0bf7e200ee4da4c64b902`, includes that explanation and a clustering example. These coordinates refer to the saved parsed text, not raw Markdown bytes; the temporary database may not remain available indefinitely.

**Disposition: source discovery and parsing found useful material, but passage retrieval/context selection omitted a needed adjacent explanation. The final insufficiency decision is appropriate for the supplied context; it does not establish that the source document lacks the knowledge.** A later same-section neighbour expansion is a new implementation to test, not evidence that ZH04 succeeded. No Chinese teaching artifact can be scored from this run because none was produced.

## Follow-up review: ZH07 after neighbour expansion and DNS compatibility repair

This is an independent review of [after-zh-07.json](after-zh-07.json), SHA-256 `f366f5f780cadbac6f26f12e6a60b71f3cd2951a3cec178e28d51fdf693241f0`. The recorded result is `succeeded`, with exploration reason `sources_sufficient`, total elapsed time 69,787 ms, and 19 ledger operations. The prior failures and reviews remain unchanged. Review used the saved artifact, source excerpts and controller decisions without new provider calls; this remains AI review, not human annotation or a measured accuracy score.

The user objective is still the same English sentence with Chinese output selected. The run freezes four requirements: a concise definition, learning patterns from data, the main supervised/unsupervised/reinforcement categories, and a simple example. Candidate retrieval indexed all 94 leaves, retained 13 seeds and added 10 same-section neighbours; the selector received 35 passages from 23 leaves. This is an actual online run, unlike the earlier deterministic replay.

### What is supported in this snapshot

- The definition is present in `context_659a613fa52be4d13048f4fe0cd9b01a` and the source summary, and is expressed in `asset.sections[0]`.
- Training with data and “programming with data” are present in `context_2f80bc0cd444e9b75e424118f5e95744` and `context_bbe4b1f7c94fbf4b37dabbc99d9d3eaa`; `asset.sections[1:3]` explain the example and training process.
- The three categories now have substantive support: supervised learning in `context_4bf7a47c70b1d42ad77cdb35d0828dbc`, unsupervised learning and clustering in `context_5b4222ae34d991c27388e4c90c45e435`, and reinforcement learning in `context_11ead511b986a5d6ceef278b8f999ffc`. These appear in `asset.sections[3:6]`. The previously missed unsupervised explanation is actually included; the review does not infer coverage from the section heading alone.
- The smartphone/wake-word example is present in `context_1d6869a0150cb760fb98c09fe1e869ba` and the programming-with-data passage, and is explained in `asset.sections[1]`.

All 10 final coverage quotations occur contiguously in their referenced source excerpts; none is solely a Markdown heading. All section citation IDs and inline `context_...` IDs resolve to the 11 saved final sources. These deterministic checks establish reference integrity. Reading the artifact confirms expression of the four frozen requirements, which is a separate AI judgment with the limitations stated above.

### Remaining teaching and presentation issues

1. **Brevity.** The asset contains 8 sections and 4 learning objectives. Concatenating only section bodies, removing inline citation IDs with optional surrounding parentheses, then removing whitespace gives 1,767 characters, including 1,558 basic CJK characters. This is a reproducible character count, not an English word count or tokenizer measurement. There was no explicit user word limit, but the result is expansive for a brief introduction and adds a deep-learning summary beyond the four frozen requirements.
2. **Self-supervised heading exceeds the explanation.** `asset.sections[4].heading` combines unsupervised and self-supervised learning, and the objectives also mention both. Its body explains unsupervised exploration and clustering but does not explain how self-supervised targets are derived from data. The original source section title also combines these topics; inheriting that title does not make the generated explanation complete for both. This does not negate coverage of the three categories actually required by the frozen plan, but the heading and objective promise more than the lesson delivers.
3. **Reward/loss wording needs clarification.** `asset.sections[5]` says that an environment's reward may be exactly equal to the original supervised loss. This closely follows `context_3bb94b1ed360960e97f545acfd557fcc`; it is not an invented statement without a source. However, neither the generated passage nor this excerpt clarifies the optimization direction or sign convention. For learners, equating reward and loss without that qualification can be misleading. Source fidelity alone is insufficient to resolve this pedagogical ambiguity.
4. **Technical extraction detail interrupts the lesson.** The training section tells the learner that `fig_ml_loop` was not transcribed as an understandable image. The statement is consistent with the recorded extraction limitation, but internal reference syntax is distracting in an introductory lesson. The saved `visual_prompt` is only text; this run does not establish that an illustration was generated or inspected.

**Disposition: this snapshot completes the online source-to-generation workflow and expresses its four frozen requirements with substantive source support, including all three learning categories. It still needs editorial improvement for brevity, heading scope and reward/loss clarity. Do not describe it as defect-free, human-reviewed, or evidence of general learning effectiveness.**

## Follow-up review: EN08 on the same DNS-patched implementation

The reviewed snapshot is [after-en-08.json](after-en-08.json), SHA-256 `2d654d4990bfa66d64a44428c81ac572a071817d82957f8365ff62376088b65c`. It records `succeeded` / `sources_sufficient`, total elapsed time 35,067 ms, and 19 ledger operations. All 10 saved implementation fingerprints match `implementation-dns-v2/manifest.json`, as do ZH07's fingerprints. No new provider calls were made for this AI review.

This run freezes three requirements: a definition, supervised/unsupervised/reinforcement categories, and a simple example. It indexes 94 candidate leaves and supplies the selector with 24 passages from 10 original seeds plus 8 same-section neighbours. The final generation context contains 10 leaves and 1,713 serialized source tokens. All 8 recorded support anchors are preserved, compared with 3 in the initial global retrieval. These are run-specific counts, not a measured recall improvement over a labelled test set.

The generated explanations cover the recorded plan under this review:

- `asset.sections[0]` explains the definition from `context_34304f16e5a07c568954c9dcbd680367` and the summary passage `context_74da6a39fe2da9665aa3a686996a0261`.
- Supervised learning is defined in `asset.sections[3]` using `context_fcaee519b4ba436c1bec8b533716efe5`. Unsupervised learning and clustering are explained in `asset.sections[4]` using `context_0c649b676e3e65bf71295815c19bf99c`, while the same section explains reinforcement learning using `context_fcda6202a9f30286d8945a6c7abd469a`. All three categories therefore have actual explanatory prose rather than only headings.
- `asset.sections[1:3]` use labelled wake-word audio, adjustable model parameters and an iterative training sequence to explain the simple example. The cited passages `context_4883d26fe45c6db712a27fecdb1d5540`, `context_b0f1efe675afb79706a638bc9685d76c` and `context_55e4a934392798d03fee6928207334ad` contain those details.

All 8 final coverage quotations occur contiguously in the corresponding source excerpts, none consists solely of a Markdown heading, and all section citation IDs resolve to the 10 final sources. The actual asset supports the three frozen requirements in this AI reading; matching IDs and quotations by themselves would not establish that conclusion.

The main remaining weakness is brevity. The asset has 6 sections and 6 learning objectives. Under the same earlier counting convention—summing `re.findall(r'\b[\w-]+\b', section['text'])` across section bodies—it contains 985 word matches, including citation-ID tokens. The lengthy training explanation, separate key-components section and deep-learning summary exceed what is necessary to answer the frozen brief-introduction plan. There was no explicit numeric length constraint, so this is a user-intent and editorial concern rather than a failed word-limit test. The category comparison is also split across two sections instead of presented compactly together.

Unlike ZH07, this artifact does not promise a self-supervised-learning explanation in the category heading and does not repeat the reward-equals-loss example. The saved visual prompt is only a proposed diagram description, not evidence of a generated or reviewed image. Its extraction note accurately separates available text from uninterpreted figures; it must not be used to claim verified multimodal parsing.

**Disposition: this English run completes the same online workflow and expresses all three frozen requirements with substantive source support, but the answer remains too expansive for the conversational request. The two final language runs have different requirement plans and independent provider timings; neither their latency difference nor their success establishes a general language effect, overall success rate or teaching-effectiveness score.**
