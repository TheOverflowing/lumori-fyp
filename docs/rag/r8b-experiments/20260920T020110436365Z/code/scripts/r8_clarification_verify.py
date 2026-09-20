"""Replay R8B in an isolated copy with all network connections disabled."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import socket
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.r5_experiment import load, save, sha
from scripts import r8_clarification as experiment
from scripts import r8_clarification_report as report


def hashes(directory):
    return {p.relative_to(directory).as_posix():sha(p.read_bytes()) for p in directory.rglob('*') if p.is_file()}


def without_timing(rows):
    return [{k:v for k,v in r.items() if k!='ranking_ms'} for r in rows]


def verify(run):
    experiment.verify(run)
    before=hashes(run)
    def blocked(*args,**kwargs):
        raise AssertionError('Network is disabled during R8B replay')
    old_connect,old_connect_ex,old_create=socket.socket.connect,socket.socket.connect_ex,socket.create_connection
    old_remote=experiment.r7.Remote
    checks={}
    try:
        socket.socket.connect=socket.socket.connect_ex=socket.create_connection=blocked
        experiment.r7.Remote=blocked
        with tempfile.TemporaryDirectory(prefix='lumori-r8b-replay-') as folder:
            replay=Path(folder)/'run'
            shutil.copytree(run,replay)
            experiment.rank(replay)
            report.report(replay)
            checks['rankings_exact']=load(run/'rankings.json')==load(replay/'rankings.json')
            checks['all_rows_equal_except_local_ranking_ms']=without_timing(load(run/'per-query.json'))==without_timing(load(replay/'per-query.json'))
            for name in ('summary.json','paired-intervals.json','costs.json','metrics.csv','report.md','query-only-audit-inputs.json','reply-support-audit-inputs.json'):
                checks[name+'_bytes_equal']=(run/name).read_bytes()==(replay/name).read_bytes()
            checks['copied_calls_unchanged']=sha((replay/'calls.json').read_bytes())==before['calls.json']
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection=old_connect,old_connect_ex,old_create
        experiment.r7.Remote=old_remote
    after=hashes(run)
    checks['original_files_unchanged']=before==after
    result={'status':'passed' if all(checks.values()) else 'failed', 'checks':checks,
            'verified_at':datetime.now(timezone.utc).isoformat(), 'input_files_checked':len(before),
            'rows':len(load(run/'per-query.json')), 'network_disabled':True, 'new_api_calls':0,
            'exclusions':['ranking_ms'], 'verifier_sha256':sha(Path(__file__).read_bytes()),
            'interpretation':'Reproduces archived local computation; not fresh model behavior or human evaluation.'}
    save(run/'offline-verification.json',result)
    if not all(checks.values()):
        raise ValueError('R8B replay mismatch: '+str(checks))
    print(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    args=parser.parse_args()
    verify(args.run)
