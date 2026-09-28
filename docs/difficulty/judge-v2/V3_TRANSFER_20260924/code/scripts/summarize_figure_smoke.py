"""Derive small-sample integration metrics without claiming general accuracy."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_document_parsing import normalize_text,edit_distance

root=Path(__file__).resolve().parents[1]
archive=root/'docs/parsing/integration/I1-mineru-docling-20260918'
run=archive/'run-05'
benchmark=root/'docs/parsing/benchmarks/omnidocbench-pilot-v1/samples/p06'
reference=normalize_text((benchmark/'reference.txt').read_text())
results=json.loads((run/'results.json').read_text())
metrics={'scope':'One public development page only; not a course-level or held-out benchmark',
    'source_sha256':results['sha256'],'normalization':'NFKC, whitespace removed, case sensitive',
    'ground_truth_characters':len(reference),'parser':{}}
for tier in ('standard','advanced'):
    report=json.loads((run/(tier+'-report.json')).read_text())
    prediction=normalize_text(report['pages'][0]['text'])
    edits=edit_distance(reference,prediction)
    metrics['parser'][tier]={'edits':edits,'cer':edits/len(reference),'pages_with_text':1,'input_pages':1,
        'seconds':next(r['seconds'] for r in results['stages'] if r['stage']=='mineru_'+tier)}
with sqlite3.connect(run/'runtime/studio.sqlite3') as db:
    report=json.loads(db.execute('SELECT report FROM document_parsing').fetchone()[0])
annotation=json.loads((benchmark/'annotation.json').read_text());info=annotation['page_info']
truth=[]
for item in annotation['layout_dets']:
    if item['category_type']!='figure' or item.get('ignore'):continue
    xs=item['poly'][0::2];ys=item['poly'][1::2]
    truth.append([min(xs)/info['width'],min(ys)/info['height'],max(xs)/info['width'],max(ys)/info['height']])
pred=[a['bbox'] for a in report['assets'] if a['kind']=='figure']
def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/union if union>0 else 0
pairs=sorted([(iou(a,b),i,j) for i,a in enumerate(pred) for j,b in enumerate(truth)],reverse=True)
used_p=set();used_t=set();matches=[]
for score,i,j in pairs:
    if score>=.5 and i not in used_p and j not in used_t:
        used_p.add(i);used_t.add(j);matches.append({'prediction':i,'truth':j,'iou':score})
metrics['figure_detection']={'tp':len(matches),'predicted':len(pred),'ground_truth':len(truth),
    'precision':len(matches)/len(pred) if pred else None,'recall':len(matches)/len(truth) if truth else None,'matches':matches,
    'limitation':'One page with three figures; not an aggregate detection claim.'}
metrics['caption_binding']={'matched':sum(bool(a.get('original_caption')) for a in report['assets']),
    'total':len(report['assets']),'basis':'same-page MinerU image block IoU >= 0.5; not manually verified'}
first=next(s for s in results['stages'] if s['stage']=='docling_vision_embedding')
retry=next(s for s in results['stages'] if s['stage']=='cached_retry')
cache=json.loads((run/'final-cache-verification.json').read_text())
metrics['semantic_processing']={'initial':first['result'],'initial_completion_rate':first['result']['succeeded']/first['result']['total'],
    'explicit_retry':retry['result'],'retry_api_calls':retry['new_api_calls'],'final_cached_pass':cache,
    'limitation':'Completion counts transport, schema validation and embeddings, not factual accuracy.'}
retrieval=next(s for s in results['stages'] if s['stage']=='retrieval')
metrics['retrieval']={'query':retrieval['trace']['query'],'results':len(retrieval['sources']),
    'figure_results':sum(r['metadata'].get('source_kind')=='figure' for r in retrieval['sources']),
    'context_tokens':retrieval['trace'].get('context_tokens'),'recall_at_k':None,'relevance_labels_available':False}
metrics['call_ledger']={'runs':{},'known_cost_usd':0,'unknown_cost_calls':0}
for folder in [archive,archive/'run-02',archive/'run-03',archive/'run-04',run]:
    database=folder/'runtime/studio.sqlite3'
    if not database.exists():continue
    with sqlite3.connect(database) as db:
        rows=db.execute('SELECT capability,status,usage,http_status FROM calls').fetchall()
    ledger=[]
    for cap,status,usage,http_status in rows:
        usage=json.loads(usage);cost=usage.get('cost')
        metrics['call_ledger']['known_cost_usd']+=cost or 0
        metrics['call_ledger']['unknown_cost_calls']+=cost is None
        ledger.append(dict(capability=cap,status=status,http_status=http_status,usage=usage))
    metrics['call_ledger']['runs'][str(folder.relative_to(archive))]=ledger
metrics['call_ledger']['limitation']='Known cost excludes calls without reported currency cost; not the total bill.'
(run/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in metrics.items() if k!='call_ledger'},ensure_ascii=False,indent=2))
