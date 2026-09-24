#!/usr/bin/env python3
"""Read-only integrity and evidence validation for the frozen Q1 pilot."""
import hashlib
import json
from pathlib import Path
from build_dataset import validate

PACK=Path(__file__).resolve().parent
ROOT=PACK.parents[1]

def main():
    manifest=json.loads((PACK/'manifest.json').read_text())
    for name,expected in manifest['files'].items():
        p=(ROOT/name).resolve()
        if ROOT not in p.parents:
            raise ValueError('Manifest path escapes the repository')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise ValueError(f'Frozen file changed: {name}')
    path=PACK/'dataset.json'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['dataset_sha256']:
        raise ValueError('Dataset hash differs from the freeze manifest')
    d=json.loads(path.read_text());validate(d)
    if set(d['generation_field_allowlist']) & set(d['review_only_fields']):
        raise ValueError('Private grading field included in generation allowlist')
    for source in d['source_documents']:
        if (ROOT/source['path']).read_text()!=source['text']+'\n':
            raise ValueError(f'Text sidecar mismatch: {source["id"]}')
    print(json.dumps({'valid':True,'cases':len(d['cases']),'needs':len({c['need_id'] for c in d['cases']}),'source_documents':len(d['source_documents']),'verified_evidence_quotes':sum(len(c['expected_evidence']) for c in d['cases']),'dataset_sha256':manifest['dataset_sha256'],'label_status':d['label_status']},ensure_ascii=False))

if __name__=='__main__':main()
