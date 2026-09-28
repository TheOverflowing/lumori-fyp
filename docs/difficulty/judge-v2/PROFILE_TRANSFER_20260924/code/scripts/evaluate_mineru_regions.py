"""Figure localization pilot: native/scan variants only, IoU>=0.5, one-to-one.

This is not image semantic accuracy, TEDS, or the official OmniDocBench metric.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_document_parsing import sha256


def iou(a,b):
    overlap=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    area=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-overlap
    return overlap/area if area>0 else 0.0


def match_regions(gold,predicted,threshold=.5):
    """Maximum-cardinality bipartite matching prevents double counting."""
    edges=[[p for p,box in enumerate(predicted) if iou(truth,box)>=threshold] for truth in gold]
    assigned={}
    def assign(g,seen):
        for p in edges[g]:
            if p in seen:continue
            seen.add(p)
            if p not in assigned or assign(assigned[p],seen):
                assigned[p]=g;return True
        return False
    for g in range(len(gold)):assign(g,set())
    return [{'gold':g,'prediction':p,'iou':iou(gold[g],predicted[p])} for p,g in sorted(assigned.items())]


def evaluate(run):
    path=ROOT/'docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json'
    manifest=json.loads(path.read_text());config=json.loads((run/'configuration.json').read_text())
    assert sha256(path)==config['manifest_sha256']
    rows=[]
    for strategy in config['strategies']:
        for variant in ['native_pdf','image_only_pdf']:
            for sample in manifest['samples']:
                annotation=path.parent/sample['annotation'];assert sha256(annotation)==sample['annotation_sha256']
                doc=json.loads(annotation.read_text());w=doc['page_info']['width'];h=doc['page_info']['height']
                gold=[]
                for block in doc['layout_dets']:
                    if block['category_type']=='figure':
                        poly=block['poly'];gold.append([min(poly[::2])/w,min(poly[1::2])/h,max(poly[::2])/w,max(poly[1::2])/h])
                stem=f'{strategy}--{sample["id"]}--{variant}'
                result=json.loads((run/'outputs'/(stem+'.json')).read_text())
                predictions=[];asset_count=0
                if not result['error']:
                    middle=json.loads((run/'outputs'/stem/'middle_json.json').read_text())
                    for page in middle['pages']:
                        for block in page['blocks']:
                            if block['type'] in ('image','chart') and block.get('bbox'):
                                predictions.append(block['bbox'])
                    asset_count=len(json.loads((run/'outputs'/stem/'worker.json').read_text())['assets'])
                matches=match_regions(gold,predictions)
                rows.append({'strategy':strategy,'variant':variant,'sample_id':sample['id'],
                    'gold_boxes':gold,'predicted_boxes':predictions,'matches':matches,
                    'gold_count':len(gold),'predicted_count':len(predictions),'matched_count':len(matches),
                    'saved_assets':asset_count,'parse_failed':bool(result['error'])})
    summaries=[]
    for strategy in config['strategies']:
        for variant in ['native_pdf','image_only_pdf']:
            selected=[r for r in rows if r['strategy']==strategy and r['variant']==variant]
            g=sum(r['gold_count'] for r in selected);p=sum(r['predicted_count'] for r in selected);m=sum(r['matched_count'] for r in selected)
            summaries.append({'strategy':strategy,'variant':variant,'pages':len(selected),'gold_regions':g,'predicted_regions':p,
                'matched_regions':m,'recall':m/g if g else None,'precision':m/p if p else None})
    result={'protocol':'figure-bbox-iou50-one-to-one-v1','threshold':.5,
        'predicted_classes':['image','chart'],'gold_class':'figure',
        'coordinate_basis':'normalized x0,y0,x1,y1; gold polygon envelope/page image dimensions; MinerU shared-schema normalized bbox',
        'scope':'all 12 source pages; native/scan only. Degraded rotation requires separate coordinate registration and is excluded before scoring.',
        'limits':'Small development pilot. Native PDF revision/rendering may differ from annotation canvas. Bounding-box localization only, no semantic interpretation claim. Saved image count is not recall.',
        'source_sha256':sha256(Path(__file__)),'rows':rows,'summary':summaries}
    (run/'figure-regions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return summaries


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    print(json.dumps(evaluate(parser.parse_args().run),indent=2))
