"""Isolated Docling candidates, using the frozen P1 text metric contract."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_document_parsing import text_metrics,sha256
from scripts.evaluate_mineru_parsing import VARIANTS,summarize

PILOT=ROOT/'docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json'
MODELS=ROOT/'tmp/p4-models'
STRATEGIES={'docling_tess_v2':'docling_2_128_tesseract_tableformer_v2',
            'granite_mlx':'docling_2_128_granite_258m_mlx'}


def environment(offline=True):
    env={k:os.environ[k] for k in ('PATH','TMPDIR','LANG','LC_ALL','SYSTEMROOT') if k in os.environ}
    env.update(HF_HOME=str(MODELS/'hf-cache'),HF_HUB_DISABLE_IMPLICIT_TOKEN='1',
        HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_XET='1',DO_NOT_TRACK='1',
        TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',
        PYTHONUNBUFFERED='1',XDG_CACHE_HOME=str(MODELS/'cache'),DOCLING_CACHE_DIR=str(MODELS/'docling-cache'))
    if offline:env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    return env


def docling_content(document):
    """Preserve model tree order, all content layers, without Markdown wrappers."""
    from docling_core.types.doc import TextItem,TableItem,PictureItem,ContentLayer
    items=[];seen=set()
    for item,_ in document.iterate_items(traverse_pictures=True,included_content_layers=set(ContentLayer)):
        if item.self_ref in seen:continue
        seen.add(item.self_ref)
        text=''
        if isinstance(item,TextItem):text=item.text
        elif isinstance(item,TableItem):text='\n'.join(cell.text for cell in item.data.table_cells)
        boxes=[]
        for prov in getattr(item,'prov',[]):
            page=document.pages[prov.page_no];box=prov.bbox.to_top_left_origin(page.size.height)
            boxes.append({'page_no':prov.page_no,'bbox':[box.l/page.size.width,box.t/page.size.height,box.r/page.size.width,box.b/page.size.height]})
        items.append({'id':item.self_ref,'type':str(item.label.value),'text':text,'boxes':boxes,'is_picture':isinstance(item,PictureItem),
            'table_html':item.export_to_html(doc=document) if isinstance(item,TableItem) else None})
    return items


def make_converter(strategy):
    from docling.datamodel.accelerator_options import AcceleratorOptions,AcceleratorDevice
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (PdfPipelineOptions,TesseractCliOcrOptions,
        TableStructureV2Options,VlmPipelineOptions,VlmConvertOptions)
    from docling.datamodel.vlm_engine_options import MlxVlmEngineOptions
    from docling.document_converter import DocumentConverter,PdfFormatOption,ImageFormatOption
    from docling.pipeline.vlm_pipeline import VlmPipeline
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    common={'artifacts_path':MODELS,'generate_page_images':True,'generate_picture_images':True,
            'images_scale':2.0,'enable_remote_services':False,'allow_external_plugins':False,
            'accelerator_options':AcceleratorOptions(device=AcceleratorDevice.CPU,num_threads=4)}
    if strategy=='docling_tess_v2':
        options=PdfPipelineOptions(**common,
            ocr_options=TesseractCliOcrOptions(lang=['chi_sim','eng'],psm=3),
            table_structure_options=TableStructureV2Options(do_cell_matching=True))
        pipeline=StandardPdfPipeline
    elif strategy=='granite_mlx':
        vlm=VlmConvertOptions.from_preset('granite_docling',engine_options=MlxVlmEngineOptions())
        options=VlmPipelineOptions(**common,vlm_options=vlm)
        pipeline=VlmPipeline
    else:raise ValueError(strategy)
    converter=DocumentConverter(allowed_formats=[InputFormat.PDF,InputFormat.IMAGE],format_options={
        InputFormat.PDF:PdfFormatOption(pipeline_cls=pipeline,pipeline_options=options),
        InputFormat.IMAGE:ImageFormatOption(pipeline_cls=pipeline,pipeline_options=options)})
    config=options.model_dump(mode='json',serialize_as_any=True)
    config['pipeline_class']=pipeline.__name__
    config['ocr_class']=type(options.ocr_options).__name__ if hasattr(options,'ocr_options') else None
    config['table_class']=type(options.table_structure_options).__name__ if hasattr(options,'table_structure_options') else None
    return converter,config


def worker(source,strategy,out):
    import torch
    torch.set_num_threads(4)
    from docling_core.types.doc import PictureItem,ImageRefMode,ContentLayer
    from docling.datamodel.base_models import ConversionStatus
    assert importlib.metadata.version('docling')=='2.128.0'
    out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();converter,config=make_converter(strategy)
    (out/'options.json').write_text(json.dumps(config,indent=2)+'\n')
    result=converter.convert(source,raises_on_error=False)
    document=result.document
    document.save_as_json(out/'document.json',image_mode=ImageRefMode.PLACEHOLDER)
    (out/'document.md').write_text(document.export_to_markdown())
    if result.status!=ConversionStatus.SUCCESS:raise RuntimeError(f'Docling conversion status: {result.status}, errors={result.errors}')
    if len(document.pages)!=1:raise ValueError(f'Expected one page, received {len(document.pages)}')
    items=docling_content(document)
    (out/'items.json').write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n')
    (out/'prediction.txt').write_text('\n'.join(i['text'] for i in items))
    (out/'images').mkdir()
    for item,_ in document.iterate_items(traverse_pictures=True,included_content_layers=set(ContentLayer)):
        if isinstance(item,PictureItem):
            pic=item.get_image(document)
            if pic is not None:pic.save(out/'images'/f'picture_{item.self_ref.rsplit("/",1)[-1]}.png')
    for number,page in document.pages.items():
        if page.image:page.image.pil_image.save(out/'images'/f'page_{number}.png')
    info={'strategy':strategy,'versions':{name:importlib.metadata.version(name) for name in ('docling','docling-core','torch','transformers')},
        'status':result.status.value,'parse_seconds':time.perf_counter()-started,
        'worker_max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'block_types':dict(Counter(i['type'] for i in items)),
        'picture_boxes':[p for i in items if i['is_picture'] for p in i['boxes']],
        'assets':[{'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted((out/'images').iterdir())]}
    (out/'worker.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')


def run_case(source,strategy,out,timeout):
    started=time.perf_counter()
    with out.with_suffix('.log').open('w') as log:
        proc=subprocess.Popen([str(ROOT/'.venv-docling/bin/python'),str(Path(__file__).resolve()),
            '--worker',str(source),'--strategy',strategy,'--output',str(out)],
            env=environment(),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            code=proc.wait(timeout=timeout);error=None if code==0 else {'type':'WorkerError','exit_code':code}
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait();error={'type':'TimeoutError','timeout':timeout}
    prediction='' if error else (out/'prediction.txt').read_text()
    return prediction,time.perf_counter()-started,error


def evaluate(strategy,manifest_path,out,timeout):
    manifest=json.loads(manifest_path.read_text());out.mkdir(parents=True,exist_ok=False);(out/'outputs').mkdir()
    files=['scripts/evaluate_parsing_candidates.py','scripts/evaluate_document_parsing.py','scripts/evaluate_mineru_parsing.py']
    config={'started_at_utc':datetime.now(timezone.utc).isoformat(),'strategy_key':strategy,'strategies':[STRATEGIES[strategy]],
        'manifest_path':str(manifest_path.relative_to(ROOT)),'manifest_sha256':sha256(manifest_path),
        'variants':VARIANTS,'timeout_seconds':timeout,'metric_contract':manifest['metric_contract'],
        'adapter':'Docling tree order; all ContentLayers; TextItem.text, table-cell text for non-prose only; no Markdown wrapper or answer-based cleanup.',
        'execution':'isolated cold subprocess per input; all exceptions/timeouts included as empty predictions; local offline weights; no API keys inherited',
        'source_sha256':{name:sha256(ROOT/name) for name in files}}
    (out/'configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    for name in files:
        dest=out/'source-snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    rows=[]
    for sample in manifest['samples']:
        ref=manifest_path.parent/sample['reference'];assert sha256(ref)==sample['reference_sha256']
        for variant in VARIANTS:
            entry=sample['files'][variant];source=manifest_path.parent/entry['path'];assert sha256(source)==entry['sha256']
            stem=f'{STRATEGIES[strategy]}--{sample["id"]}--{variant}'
            prediction,elapsed,error=run_case(source,strategy,out/'outputs'/stem,timeout)
            row={'sample_id':sample['id'],'strategy':STRATEGIES[strategy],'variant':variant,
                'language':sample['language'],'stratum':sample['stratum'],'completed_without_exception':error is None,
                'elapsed_seconds':elapsed,'error_type':error['type'] if error else None,
                **text_metrics(ref.read_text(),prediction,sample['language'],sample['cer_eligible'])}
            raw={'case':row,'prediction':prediction,'error':error,'input_sha256':entry['sha256']}
            (out/'outputs'/(stem+'.json')).write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
            rows.append(row);(out/'rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
            print(f'{stem}: success={not error}, CER={row["cer"]}, seconds={elapsed:.2f}',flush=True)
    summarize(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--strategy',required=True,choices=STRATEGIES)
    parser.add_argument('--worker',type=Path);parser.add_argument('--manifest',type=Path,default=PILOT)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--timeout',type=int,default=240)
    args=parser.parse_args()
    if args.worker:worker(args.worker,args.strategy,args.output)
    else:evaluate(args.strategy,args.manifest.resolve(),args.output.resolve(),args.timeout)
