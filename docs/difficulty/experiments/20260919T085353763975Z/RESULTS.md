# D1 development screening

AI-judged frozen-context prompt comparison. No human or student calibration; no production change.

| Strategy | Requested | Valid output | Judged | Difficulty matched | Qualified |
| --- | ---: | ---: | ---: | ---: | ---: |
| backward_design | 6 | 0 | 0 | 0 | 0 (0.0%) |
| baseline | 6 | 1 | 1 | 1 | 1 (16.7%) |
| contrastive | 6 | 4 | 4 | 4 | 4 (66.7%) |
| rubric_axes | 6 | 2 | 2 | 2 | 2 (33.3%) |
| scaffold_control | 6 | 1 | 1 | 0 | 0 (0.0%) |
| verify_before_emit | 6 | 1 | 1 | 1 | 1 (16.7%) |

API attempts: 45. Reported cost: $0.002287 on 9 responses; 36 omit cost.

These tiny development counts do not establish a strongest strategy. Keep source/model/prompt snapshots and failed cases; evaluate shortlisted prompts on untouched topics with repeats and human calibration.
