"""Isolated MinerU 4 experiment. Does not change application parsing or P1 outputs."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_document_parsing import aggregate, text_metrics, sha256, wilson_interval

MANIFEST = ROOT / 'docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json'
RUNTIME = ROOT / 'tmp/mineru-runtime'
VARIANTS = ['native_pdf', 'image_only_pdf', 'degraded_image']


class _HtmlText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def content_text(value):
    """Read original MiddleJson spans, without adding Markdown or asset paths.

    List order is parser order. No ground-truth-dependent cleanup, spelling
    correction, dehyphenation, case folding, or header/footer removal is applied.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ''.join(content_text(v) for v in value)
    if isinstance(value, dict):
        result = content_text(value.get('content', ''))
        if value.get('type') == 'table_body' and result:
            parser = _HtmlText()
            parser.feed(result)
            return ' '.join(parser.parts)
        return result
    if value is None:
        return ''
    raise ValueError('Unsupported MiddleJson content value.')


def extract_pages(document):
    if document.get('schema') != 'docvortex.middle' or document.get('schema_version') != '2.0':
        raise ValueError('Unsupported document schema; refusing to guess text fields.')
    pages = document.get('pages')
    if not isinstance(pages, list):
        raise ValueError('Missing document pages.')
    return ['\n'.join(content_text(block) for block in page['blocks']) for page in pages]


def isolated_environment(model_source='local'):
    allowed = ('PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'SYSTEMROOT')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update(MINERU_HOME=str(RUNTIME), MINERU_CONFIG=str(RUNTIME/'config.yaml'),
        HF_HOME=str(RUNTIME/'hf-cache'), MINERU_MODEL_SOURCE=model_source,
        MINERU_MODEL_SMALL_BACKEND='onnx', MINERU_MODEL_VLM_ENGINE='llama-cpp',
        MINERU_INTRA_OP_NUM_THREADS='4', MINERU_INTER_OP_NUM_THREADS='1',
        OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', TOKENIZERS_PARALLELISM='false',
        HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1', HF_HUB_DISABLE_XET='1',
        PYTHONUNBUFFERED='1')
    return env


def prepare_runtime():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    config = RUNTIME/'config.yaml'
    expected = ('model:\n  base_dir: '+str(RUNTIME/'models')+'\n  source: local\n'
        '  small_backend: onnx\n  vlm:\n    engine: llama-cpp\n    max_concurrency: 2\n'
        'llm_aided:\n  features:\n    title_leveling: false\n    cross_page_table_cell_merge: false\n')
    if config.exists() and config.read_text() != expected:
        raise ValueError('Existing experiment runtime configuration differs.')
    config.write_text(expected)


def worker(source, tier, output):
    from mineru.parser import parse
    from mineru.parser.writer import FileBasedDataWriter
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    assert importlib.metadata.version('mineru') == '4.0.2'
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    result = parse(source, tier=tier, ocr_mode='auto', image_analysis=True)
    parse_seconds = time.perf_counter()-started
    # This writes JSON/Markdown/image assets, not a newly authored PDF.
    result.save(FileBasedDataWriter(str(output)))
    raw = json.loads((output/'middle_json.json').read_text())
    pages = extract_pages(raw)
    if len(pages) != 1:
        raise ValueError(f'Expected one page; got {len(pages)}.')
    (output/'prediction.txt').write_text(pages[0])
    info = {'tier_requested':tier, 'extension':raw.get('extensions',{}).get('mineru'),
        'producer':raw.get('metadata',{}).get('producer'), 'parse_seconds':parse_seconds,
        'worker_max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'rss_platform':'macOS ru_maxrss is bytes; subprocess/library accelerator allocation may differ',
        'top_level_block_types':dict(Counter(b['type'] for p in raw['pages'] for b in p['blocks'])),
        'assets':[{'path':str(p.relative_to(output)),'bytes':p.stat().st_size,'sha256':sha256(p)}
                  for p in sorted((output/'images').rglob('*')) if p.is_file()]}
    (output/'worker.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')


def run_case(source, tier, folder, timeout):
    log = folder.with_suffix('.log')
    command = [str(ROOT/'.venv-mineru/bin/python'),str(Path(__file__).resolve()),
        '--worker',str(source),'--tier',tier,'--output',str(folder)]
    started = time.perf_counter()
    with log.open('w') as stream:
        proc = subprocess.Popen(command, env=isolated_environment(),stdout=stream,
                                stderr=subprocess.STDOUT,start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
            error = None if code == 0 else {'type':'WorkerError','exit_code':code,'log':log.name}
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL)
            proc.wait()
            error = {'type':'TimeoutError','seconds':timeout,'log':log.name}
    elapsed = time.perf_counter()-started
    prediction = (folder/'prediction.txt').read_text() if not error else ''
    return prediction, elapsed, error


def summarize(output):
    rows = json.loads((output/'rows.json').read_text())
    config = json.loads((output/'configuration.json').read_text())
    summary = []
    for strategy in config['strategies']:
        for variant in VARIANTS:
            for language in ('all','english','simplified_chinese'):
                selected = [r for r in rows if r['strategy']==strategy and r['variant']==variant
                            and (language=='all' or r['language']==language)]
                if not selected: continue
                agg = aggregate(selected)
                agg['usable_page_wilson_95']=wilson_interval(agg['usable_pages'],agg['accuracy_eligible_cases'])
                summary.append({'strategy':strategy,'variant':variant,'language':language,**agg})
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    for name,items in [('rows',rows),('summary',summary)]:
        fields=list(dict.fromkeys(key for item in items for key in item))
        with (output/(name+'.csv')).open('w') as handle:
            writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(items)
    return summary


def evaluate(output, tiers, timeout):
    prepare_runtime()
    manifest=json.loads(MANIFEST.read_text())
    output.mkdir(parents=True,exist_ok=False);(output/'outputs').mkdir()
    files=['scripts/evaluate_mineru_parsing.py','scripts/evaluate_document_parsing.py']
    config={'started_at_utc':datetime.now(timezone.utc).isoformat(),'mineru':'4.0.2',
        'strategies':['mineru_4_0_2_'+t+'_onnx' for t in tiers],'tiers':tiers,'timeout_seconds':timeout,
        'manifest_path':str(MANIFEST.relative_to(ROOT)),'manifest_sha256':sha256(MANIFEST),
        'variants':VARIANTS,'metric_contract':manifest['metric_contract'],
        'normalization':'nfkc-whitespace-strip-case-sensitive-v1',
        'input_format_adapter':'ordered MiddleJson content spans, all blocks including headers/footers; no added Markdown; table HTML text only for non-CER complex pages',
        'source_sha256':{p:sha256(ROOT/p) for p in files},
        'runtime_config':(RUNTIME/'config.yaml').read_text(),
        'execution':'sequential isolated cold worker per input; models predownloaded, local source only; no API keys or remote inference; all failures count; not strict P1 speed comparison'}
    (output/'configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    for name in files:
        dest=output/'source-snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    rows=[]
    for tier in tiers:
        strategy='mineru_4_0_2_'+tier+'_onnx'
        for sample in manifest['samples']:
            ref=MANIFEST.parent/sample['reference'];assert sha256(ref)==sample['reference_sha256']
            reference=ref.read_text()
            for variant in VARIANTS:
                entry=sample['files'][variant];source=MANIFEST.parent/entry['path'];assert sha256(source)==entry['sha256']
                stem=f'{strategy}--{sample["id"]}--{variant}'
                prediction,elapsed,error=run_case(source,tier,output/'outputs'/stem,timeout)
                row={'sample_id':sample['id'],'strategy':strategy,'variant':variant,
                     'language':sample['language'],'stratum':sample['stratum'],
                     'completed_without_exception':error is None,'elapsed_seconds':elapsed,
                     'error_type':error['type'] if error else None,
                     **text_metrics(reference,prediction,sample['language'],sample['cer_eligible'])}
                result={'case':row,'prediction':prediction,'error':error,'input_sha256':entry['sha256']}
                (output/'outputs'/(stem+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
                rows.append(row);(output/'rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
                print(f'{stem}: success={not error}, CER={row["cer"]}, seconds={elapsed:.2f}',flush=True)
    summarize(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',type=Path)
    parser.add_argument('--tier',choices=['flash','basic','standard','advanced'],default='basic')
    parser.add_argument('--tiers',nargs='+',choices=['basic','standard','advanced'],default=['basic','standard'])
    parser.add_argument('--output',type=Path)
    parser.add_argument('--timeout',type=int,default=240)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--summarize',action='store_true')
    args=parser.parse_args()
    if args.prepare:prepare_runtime()
    elif not args.output:parser.error('--output required')
    elif args.worker:worker(args.worker,args.tier,args.output)
    elif args.summarize:summarize(args.output)
    else:evaluate(args.output,args.tiers,args.timeout)
