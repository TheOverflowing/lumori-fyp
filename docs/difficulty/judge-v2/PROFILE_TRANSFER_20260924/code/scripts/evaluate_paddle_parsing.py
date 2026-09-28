"""PaddleOCR-VL 1.6 full pipeline: CPU PP-DocLayoutV3 + local MLX VLM.

Official Apple Silicon route. Each timed input owns its server process, so a
timeout kills both client and inference and cannot contaminate the next case.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_parsing_candidates import MODELS, PILOT, environment
from scripts.evaluate_document_parsing import text_metrics, sha256
from scripts.evaluate_mineru_parsing import VARIANTS, summarize

STRATEGY = 'paddleocr_3_7_vl16_mlx'
PICTURE_LABELS = {'image', 'chart', 'header_image', 'footer_image'}


def paddle_environment():
    env = environment()
    env.update(PADDLE_PDX_CACHE_HOME=str(ROOT/'tmp/p4-paddle-runtime'),
               PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True', PADDLE_PDX_MODEL_SOURCE='huggingface',
               MLX_VLM_MODEL_DISCOVERY='served', OMP_NUM_THREADS='1')
    return env


def items_from_result(data):
    w, h = data['width'], data['height']
    items = []
    for block in data['parsing_res_list']:
        x0, y0, x1, y1 = block['block_bbox']
        label = block['block_label']
        content = block['block_content']
        text = content if label not in PICTURE_LABELS else ''
        if label == 'table' and content:
            from lxml import html
            text = html.fromstring(content).text_content()
        items.append({'id': block['block_id'], 'type': label, 'text': text,
                      'boxes': [{'page_no': 1, 'bbox': [x0/w, y0/h, x1/w, y1/h]}],
                      'is_picture': label in PICTURE_LABELS,
                      'table_html': content if label == 'table' else None})
    return items


def worker(source, out):
    out.mkdir(parents=True, exist_ok=False)
    assert importlib.metadata.version('paddleocr') == '3.7.0'
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    command = [str(ROOT/'.venv-docling/bin/python'), '-m', 'mlx_vlm.server', '--host', '127.0.0.1',
               '--port', str(port), '--model', str(MODELS/'paddleocr-vl16'), '--model-discovery', 'served',
               '--vision-cache-size', '0', '--max-tokens', '8192']
    config = {'pipeline_version': 'v1.6', 'layout_detection_model_dir': str(MODELS/'paddle-layout-v3'),
              'vl_rec_backend': 'mlx-vlm-server', 'vl_rec_server_url': f'http://127.0.0.1:{port}/',
              'vl_rec_api_model_name': str(MODELS/'paddleocr-vl16'), 'vl_rec_max_concurrency': 1,
              'use_doc_orientation_classify': False, 'use_doc_unwarping': False, 'use_queues': False,
              'device': 'cpu', 'cpu_threads': 4, 'enable_mkldnn': False}
    (out/'options.json').write_text(json.dumps({'client': config, 'server_command': command,
                                              'predict': {'max_new_tokens': 8192, 'temperature': 0}}, indent=2)+'\n')
    with (out/'server.log').open('w') as server_log:
        server = subprocess.Popen(command, env=paddle_environment(), stdout=server_log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 90
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f'MLX server exited: {server.returncode}')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/models', timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError('MLX server did not become ready within 90s')
                time.sleep(.25)
            from paddleocr import PaddleOCRVL
            pipeline = PaddleOCRVL(**config)
            results = list(pipeline.predict(str(source), max_new_tokens=8192, temperature=0))
            if len(results) != 1:
                raise ValueError(f'Expected one page; received {len(results)}')
            result = results[0]
            data = result.json['res']
            (out/'document.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
            items = items_from_result(data)
            (out/'items.json').write_text(json.dumps(items, ensure_ascii=False, indent=2)+'\n')
            (out/'prediction.txt').write_text('\n'.join(i['text'] for i in items))
            result.save_to_markdown(str(out))
            import cv2
            from PIL import Image
            page = Image.fromarray(cv2.cvtColor(result['doc_preprocessor_res']['output_img'], cv2.COLOR_BGR2RGB))
            images = out/'images'; images.mkdir(exist_ok=True)
            page.save(images/'page_1.png')
            for block in data['parsing_res_list']:
                if block['block_label'] in PICTURE_LABELS:
                    page.crop(tuple(block['block_bbox'])).save(images/f'picture_{block["block_id"]}.png')
            info = {'versions': {n: importlib.metadata.version(n) for n in ('paddleocr', 'paddlepaddle', 'paddlex')},
                    'assets': [{'path': str(p.relative_to(out)), 'sha256': sha256(p)} for p in sorted(images.iterdir())]}
            (out/'worker.json').write_text(json.dumps(info, indent=2)+'\n')
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait()


def run_case(source, out, timeout):
    started = time.perf_counter()
    with out.with_suffix('.log').open('w') as log:
        process = subprocess.Popen([str(ROOT/'.venv-paddle/bin/python'), str(Path(__file__).resolve()),
                                    '--worker', str(source), '--output', str(out)],
                                   env=paddle_environment(), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
            error = None if code == 0 else {'type': 'WorkerError', 'exit_code': code}
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL); process.wait()
            error = {'type': 'TimeoutError', 'timeout': timeout}
    return '' if error else (out/'prediction.txt').read_text(), time.perf_counter()-started, error


def evaluate(manifest_path, out, timeout):
    manifest = json.loads(manifest_path.read_text())
    out.mkdir(parents=True, exist_ok=False); (out/'outputs').mkdir()
    sources = ['scripts/evaluate_paddle_parsing.py', 'scripts/evaluate_parsing_candidates.py',
               'scripts/evaluate_document_parsing.py', 'scripts/evaluate_mineru_parsing.py']
    config = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'strategies': [STRATEGY],
              'manifest_path': str(manifest_path.relative_to(ROOT)), 'manifest_sha256': sha256(manifest_path),
              'timeout_seconds': timeout, 'variants': VARIANTS, 'metric_contract': manifest['metric_contract'],
              'execution': 'cold full pipeline + owned MLX server per input; group timeout includes startup and export',
              'adapter': 'raw parsing_res_list order; all text furniture retained, pictures excluded from prose; tables plain cell text and preserved HTML',
              'source_sha256': {s: sha256(ROOT/s) for s in sources}}
    (out/'configuration.json').write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n')
    for source in sources:
        dest = out/'source-snapshot'/source; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/source, dest)
    rows = []
    for sample in manifest['samples']:
        ref = manifest_path.parent/sample['reference']; assert sha256(ref) == sample['reference_sha256']
        for variant in VARIANTS:
            entry = sample['files'][variant]; source = manifest_path.parent/entry['path']; assert sha256(source) == entry['sha256']
            stem = f'{STRATEGY}--{sample["id"]}--{variant}'
            prediction, elapsed, error = run_case(source, out/'outputs'/stem, timeout)
            row = {'sample_id': sample['id'], 'strategy': STRATEGY, 'variant': variant, 'language': sample['language'],
                   'stratum': sample['stratum'], 'completed_without_exception': error is None, 'elapsed_seconds': elapsed,
                   'error_type': error['type'] if error else None,
                   **text_metrics(ref.read_text(), prediction, sample['language'], sample['cer_eligible'])}
            raw = {'case': row, 'prediction': prediction, 'error': error, 'input_sha256': entry['sha256']}
            (out/'outputs'/(stem+'.json')).write_text(json.dumps(raw, ensure_ascii=False, indent=2)+'\n')
            rows.append(row); (out/'rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
            print(f'{stem}: success={not error}, CER={row["cer"]}, seconds={elapsed:.2f}', flush=True)
    summarize(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--manifest', type=Path, default=PILOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker.resolve(), args.output.resolve())
    else:
        evaluate(args.manifest.resolve(), args.output.resolve(), args.timeout)
