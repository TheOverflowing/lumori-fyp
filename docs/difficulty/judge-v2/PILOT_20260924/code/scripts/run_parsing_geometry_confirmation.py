"""Run the additional, predeclared geometry candidate without tuning on confirmation."""
from pathlib import Path
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import evaluate_paddle_unmerged as unmerged
from scripts.derive_parsing_reading_order import derive, STRATEGY
from scripts.evaluate_document_parsing import sha256

P4 = ROOT/'docs/parsing/experiments/P4-candidate-expansion-20260918'
DEV = ROOT/'docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json'
CONF = ROOT/'docs/parsing/benchmarks/omnidocbench-confirmation-v1/manifest.json'


def main():
    frozen = json.loads((P4/'geometry-rule-freeze.json').read_text())
    assert sha256(ROOT/'scripts/parsing_reading_order.py') == frozen['source_sha256']
    while not (P4/'runs/paddle-unmerged/summary.json').exists():
        time.sleep(10)
    derive(P4/'runs/paddle-unmerged', P4/'runs/paddle-xycut', DEV)
    # Keep all heavy inference sequential after the original three finalists.
    while not (P4/'confirmation/challenger/summary.json').exists():
        time.sleep(10)
    challenger = P4/'confirmation/challenger'
    config = json.loads((challenger/'configuration.json').read_text())
    if config['strategies'] == [unmerged.STRATEGY]:
        raw = challenger
        mode = 'Reuse exact same unmerged inference; paired ordering ablation, no additional calls.'
    else:
        raw = P4/'confirmation/geometry-raw'
        unmerged.evaluate(CONF, raw, 240)
        mode = 'Fresh unmerged inference on all confirmation cases, then fixed geometry rule.'
    assert sha256(ROOT/'scripts/parsing_reading_order.py') == frozen['source_sha256']
    derive(raw, P4/'confirmation/geometry', CONF)
    (P4/'confirmation/geometry-evidence.json').write_text(json.dumps({'candidate': STRATEGY,
        'rule_freeze_sha256': sha256(P4/'geometry-rule-freeze.json'), 'preregistration_sha256': sha256(P4/'geometry-preregistration.json'),
        'inference_source': str(raw.relative_to(ROOT)), 'execution': mode,
        'parameter_changes_after_confirmation_started': []}, indent=2)+'\n')
    print('Additional prespecified geometry confirmation complete', flush=True)


if __name__ == '__main__':
    main()
