# D1 development screening

AI-judged frozen-context prompt comparison. No human or student calibration; no production change.

| Strategy | Requested | Valid output | Judged | Difficulty matched | Qualified |
| --- | ---: | ---: | ---: | ---: | ---: |
| backward_design | 1 | 1 | 1 | 1 | 1 (100.0%) |
| baseline | 1 | 1 | 1 | 1 | 1 (100.0%) |
| contrastive | 1 | 1 | 1 | 1 | 1 (100.0%) |
| rubric_axes | 1 | 1 | 1 | 1 | 1 (100.0%) |
| scaffold_control | 1 | 0 | 0 | 0 | 0 (0.0%) |
| verify_before_emit | 1 | 1 | 1 | 1 | 1 (100.0%) |

API attempts: 11. Reported cost: $0.001255 on 5 responses; 6 omit cost.

These tiny development counts do not establish a strongest strategy. Keep source/model/prompt snapshots and failed cases; evaluate shortlisted prompts on untouched topics with repeats and human calibration.
