# R5 offline reproduction

Use Python 3.12 with requirements-runtime.lock.txt. The plotting helper additionally requires matplotlib; the experiment does not require it.

From the project root, run the archived helper. Choose a new output directory; an existing directory is rejected. No external API is called.

```sh
.venv/bin/python -B docs/rag/r5-experiments/20260912T085156100010Z/code/scripts/r5_replay.py --run docs/rag/r5-experiments/20260912T085156100010Z --output docs/rag/r5-replays/new-offline-check
```

The helper copies frozen inputs and saved provider responses, then executes the archived experiment code. It compares all 660 candidate requests, rankings and per-scenario quality/context records, allowing only locally measured ranking time and its stage-sum estimate to vary. Original input files must remain unchanged during replay. Results are stored in the new directory and replay-verification.json; this is verification, not a new independent experiment.

The original archive keeps freeze.json for prospective algorithm/input hashes and postprocessing-code-manifest.json for helpers added after results. The final artifacts-manifest.json seals the complete archive. Running a helper that regenerates reports or verification changes those outputs and requires a new postprocessing manifest; use a copy when retaining the original seal.
