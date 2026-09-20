"""Post hoc descriptive join with R7's existing AI rewrite audit. No new scoring."""
import csv
import hashlib
import json
from pathlib import Path
import statistics

run = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
freeze = read(run/'freeze.json')
audit_path = Path(freeze['source'])/'rewrite-semantic-audit.json'
if hashlib.sha256(audit_path.read_bytes()).hexdigest() != freeze['original_file_hashes']['rewrite-semantic-audit.json']:
    raise ValueError('R7 semantic audit changed.')
audit = {r['key']: r['disposition'] for r in read(audit_path)}
rows = read(run/'per-query.json')
result = []
for split in ('dev', 'test'):
    dispositions = sorted({audit[r['query_id']+':normalize'] for r in rows if r['split'] == split})
    for disposition in dispositions:
        for arm in freeze['arms']:
            selected = [r for r in rows if r['split'] == split and r['arm'] == arm
                        and audit[r['query_id']+':normalize'] == disposition]
            result.append(dict(split=split, normalize_disposition=disposition, arm=arm, n=len(selected),
                               pre_mrr20=statistics.mean(r['pre_mrr20'] for r in selected)))
with (run/'semantic-strata.csv').open('w', encoding='utf-8', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(result[0]))
    writer.writeheader()
    writer.writerows(result)
(run/'semantic-strata.json').write_text(json.dumps(dict(
    status='post_hoc_descriptive_not_new_ground_truth',
    audit_source=str(audit_path),
    audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),
    r8a_per_query_sha256=hashlib.sha256((run/'per-query.json').read_bytes()).hexdigest(),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    rows=result), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
