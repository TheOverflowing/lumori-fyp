"""Replay R5 candidates, rankings and quality from archived code; no API calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(run, output):
    run=run.resolve();output=output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    before={str(p.relative_to(run)):digest(p) for p in run.rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    freeze=read(run/'freeze.json')
    names=set(freeze['files_sha256']) | {'freeze.json','document-vectors.npz',
        'document-vector-manifest.json','translations.json','query-embeddings.json',
        'dev-rerank.json','test-rerank.json','selection-lock.json'}
    for name in names:
        shutil.copyfile(run/name,output/name)
    shutil.copytree(run/'responses',output/'responses')
    script=run/'code/scripts/r5_experiment.py'
    checks={}
    # Test ranking is only allowed with the frozen dev lock. Dev replay precedes
    # test replay so the runner's held-out exposure guard remains intact.
    for split in ('dev','test'):
        for stage in ('rank','metrics'):
            subprocess.run([sys.executable,'-B',str(script),stage,'--run',str(output),'--split',split],check=True)
        candidate=lambda d:{k:{field:v for field,v in value.items() if field!='ranking_ms'} for k,value in d.items()}
        quality=lambda rows:[{k:v for k,v in r.items() if k not in ('ranking_ms','stage_sum_estimate_ms')} for r in rows]
        checks[split]={
            'candidate_requests_and_ids_equal':candidate(read(run/(split+'-candidates.json')))==candidate(read(output/(split+'-candidates.json'))),
            'rankings_equal':read(run/(split+'-rankings.json'))==read(output/(split+'-rankings.json')),
            'quality_and_context_equal':quality(read(run/(split+'-per-query.json')))==quality(read(output/(split+'-per-query.json'))),
            'rows':len(read(output/(split+'-per-query.json')))}
        if not all(v for k,v in checks[split].items() if k!='rows'):
            raise ValueError('Replay mismatch: '+split)
    unchanged=all(digest(run/name)==value for name,value in before.items())
    if not unchanged:raise ValueError('Original run changed during replay.')
    result={'original_run':str(run),'replay_directory':str(output),'verified_at':datetime.now(timezone.utc).isoformat(),
        'checks':checks,'original_files_unchanged':unchanged,'new_api_calls':0,
        'timing_exclusions':['ranking_ms','stage_sum_estimate_ms'],
        'method':'Archived source, frozen document vectors and full provider responses; recomputed candidates, reranking order and span metrics.'}
    for destination in (run/'replay-verification.json',output/'verification.json'):
        destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();replay(args.run,args.output)
