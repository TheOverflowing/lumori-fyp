"""Post hoc descriptive join of the query-only AI audit and frozen R7 results.

Does not change the preregistered denominator, labels, selection, or metrics.
The audit was completed without retrieval results; its dispositions are AI
judgments, not human gold. No network calls or production configuration access.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def analyze(run):
    run=Path(run)
    read=lambda name:json.loads((run/name).read_text())
    rows=read('test-per-query.json');raw_audit=read('rewrite-semantic-audit.json')
    audit={r['key']:r for r in raw_audit}
    if len(audit)!=len(raw_audit):raise ValueError('Duplicate audit key.')
    base={r['query_id']:r for r in rows if r['arm']=='original'}
    groups=defaultdict(list)
    for row in rows:
        if row['arm']!='normalize' or row['level']=='L4':continue
        disposition=audit[row['query_id']+':normalize']['disposition']
        for level in ('all',row['level']):groups[level,disposition].append((base[row['query_id']],row))
    out=[]
    for (level,category),pairs in groups.items():
        out.append(dict(level=level,disposition=category,rows=len(pairs),
            original_mrr=statistics.mean(a['pre_mrr20'] for a,b in pairs),normalize_mrr=statistics.mean(b['pre_mrr20'] for a,b in pairs),
            net_mrr_sum=sum(b['pre_mrr20']-a['pre_mrr20'] for a,b in pairs),
            gains=sum(b['pre_mrr20']>a['pre_mrr20'] for a,b in pairs),losses=sum(b['pre_mrr20']<a['pre_mrr20'] for a,b in pairs)))
    result={'method':'Post hoc AI query-only dispositions joined to test outcomes; descriptive sensitivity analysis only, never replaces preregistered denominator or proves human semantic correctness.',
            'input_sha256':{n:hashlib.sha256((run/n).read_bytes()).hexdigest() for n in ('test-per-query.json','rewrite-semantic-audit.json')},'rows':out}
    (run/'semantic-sensitivity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);args=p.parse_args()
    result=analyze(args.run);print('Descriptive sensitivity groups:',len(result['rows']))
