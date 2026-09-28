"""Prepare source-disjoint confirmation pages without inspecting parser predictions."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import prepare_parsing_benchmark as base

PILOT=base.DEFAULT
OUTPUT=ROOT/'docs/parsing/benchmarks/omnidocbench-confirmation-v1'


def source_group(name):
    # Only IDs with explicit PDF provenance can establish document separation.
    return name.split('.pdf_')[0] if '.pdf_' in name else None


def choose(data, original_names):
    old=json.loads((PILOT/'manifest.json').read_text())
    excluded={source_group(s['source_page_id']) for s in old['samples']}
    pool=[]
    for page in data:
        info=page['page_info'];attrs=info['page_attribute'];name=info['image_path']
        group=source_group(name)
        if not group or group in excluded or Path(name).stem not in original_names:continue
        if attrs['data_source'] not in base.ALLOWED_SOURCES or attrs['language'] not in ('english','simplified_chinese'):continue
        if any('mask' in b['category_type'] or b.get('ignore') for b in page['layout_dets']):continue
        text=base.reference_text(page)
        if len(''.join(text.split()))<200:continue
        cats={b['category_type'] for b in page['layout_dets']}
        prose=not cats.intersection({'table','figure','equation_isolated'}) and '$' not in text and '\\' not in text
        pool.append((page,prose,group))
    pool.sort(key=lambda x:hashlib.sha256(('p4-confirmation-v1:'+x[0]['page_info']['image_path']).encode()).hexdigest())
    selected=[];used=set(excluded)
    for lang in ('english','simplified_chinese'):
        for stratum,count in [('prose',4),('complex',2)]:
            found=[]
            for page,prose,group in pool:
                if group in used or page['page_info']['page_attribute']['language']!=lang or prose!=(stratum=='prose'):continue
                found.append((stratum,page));used.add(group)
                if len(found)==count:break
            if len(found)!=count:raise ValueError(f'Not enough source-disjoint {lang}/{stratum}: {len(found)}')
            selected+=found
    return selected


def main():
    OUTPUT.mkdir(parents=True,exist_ok=False)
    for name in ['upstream-OmniDocBench.json','upstream-README.md','upstream-old-tree.json']:
        shutil.copy2(PILOT/name,OUTPUT/name)
    data=json.loads((OUTPUT/'upstream-OmniDocBench.json').read_text())
    tree=json.loads((OUTPUT/'upstream-old-tree.json').read_text())
    names={Path(x['rfilename']).stem for x in tree['siblings'] if x['rfilename'].startswith('ori_pdfs/')}
    selected=choose(data,names)
    plan={'selection':'12 source-disjoint PDF groups; 4 prose + 2 complex pages per language. Explicit .pdf_ provenance only, no repeats within or against P1/P3. SHA256 salt p4-confirmation-v1, then fixed eligibility predicates; not selected from parser scores.',
          'source_ids':[p['page_info']['image_path'] for _,p in selected],
          'source_groups':[source_group(p['page_info']['image_path']) for _,p in selected],
          'primary_metric':'Equal-weight CER across 8 prose source pages and 3 paired conditions, with language/condition disaggregation. Failure predictions empty.',
          'scope':'General academic/book/exam source pages. Not representative CS courses and not unseen to upstream model training. Independent only of this project\'s development pages.',
          'finalists':'Incumbent MinerU Standard + lowest-development-CER feasible new candidate (stable lexical strategy id for exact ties) + existing adaptive baseline. Freeze IDs before any confirmation prediction.'}
    (OUTPUT/'selection-before-download.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    base.choose_pages=choose
    manifest=base.prepare(OUTPUT)
    manifest['schema_version']='document-parsing-confirmation-v1'
    manifest['selection']=plan['selection'];manifest['confirmation_plan']=plan
    for sample in manifest['samples']:sample['source_document_group']=source_group(sample['source_page_id'])
    (OUTPUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
