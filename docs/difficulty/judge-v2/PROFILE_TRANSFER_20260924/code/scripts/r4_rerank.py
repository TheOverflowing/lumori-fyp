"""Offline Qwen3 reranking of label-free requests, with exact scores/checkpoints."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
from app.rag_candidates import QUERY_INSTRUCTION
from scripts.r4_experiment import save, load, canonical, sha


def run_scores(run, split, max_requests=None):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    torch.set_num_threads(4)
    requests = load(run / (split + '-rerank-requests.json'))
    path = run / (split + '-rerank-scores.json')
    results = load(path) if path.exists() else {}
    model_path = ROOT / '.rag-models/qwen-reranker'
    expected = load(run / 'models.json')['qwen-reranker']
    for name, digest in expected['files_sha256'].items():
        h = hashlib.sha256()
        with (model_path / name).open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        if h.hexdigest() != digest:
            raise ValueError('Model files differ from frozen identity.')
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    dtype = torch.float16 if device == 'mps' else torch.float32
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_path, padding_side='left', local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(model_path, dtype=dtype, attn_implementation='sdpa',
                                                local_files_only=True, trust_remote_code=False).to(device).eval()
    prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
    suffix = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
    pre = tokenizer.encode(prefix, add_special_tokens=False)
    post = tokenizer.encode(suffix, add_special_tokens=False)
    yes, no = tokenizer.convert_tokens_to_ids(['yes', 'no'])

    def sync():
        if device == 'mps':
            torch.mps.synchronize()

    def score(request):
        began = time.perf_counter()
        inputs, truncated, token_lengths = [], 0, []
        for doc in request['documents']:
            value = f"<Instruct>: {QUERY_INSTRUCTION}\n<Query>: {request['query']}\n<Document>: {doc['text']}"
            ids = tokenizer.encode(value, add_special_tokens=False)
            token_lengths.append(len(ids) + len(pre) + len(post))
            truncated += len(ids) > 1024 - len(pre) - len(post)
            inputs.append(pre + ids[:1024 - len(pre) - len(post)] + post)
        scores = []
        with torch.inference_mode():
            for offset in range(0, len(inputs), 4):
                batch = tokenizer.pad({'input_ids': inputs[offset:offset + 4]}, padding=True, return_tensors='pt')
                batch = {k: v.to(device) for k, v in batch.items()}
                logits = model(**batch, logits_to_keep=1).logits[:, -1]
                values = (logits[:, yes].float() - logits[:, no].float()).cpu().tolist()
                if not all(math.isfinite(v) for v in values):
                    raise ValueError('Nonfinite reranker logits.')
                scores.extend(values)
        sync()
        return {'request_sha256': sha(canonical(request)), 'scores': scores,
                'duration_ms': (time.perf_counter() - began) * 1000,
                'truncated_documents': truncated, 'input_tokens_before_truncation': token_lengths,
                'device': device, 'dtype': str(dtype), 'model_revision': expected['revision']}

    sync()
    load_ms = (time.perf_counter() - started) * 1000
    warm_start = time.perf_counter()
    score({'query': 'Which data structure follows FIFO?', 'documents': [{'id': 'warm', 'text': 'A queue follows first-in, first-out ordering.'}]})
    sync()
    save(run / (split + '-rerank-runtime.json'), {'device': device, 'torch': torch.__version__,
         'dtype': str(dtype), 'load_ms': load_ms, 'warmup_ms': (time.perf_counter() - warm_start) * 1000,
         'max_tokens': 1024, 'batch_size': 4, 'attention': 'sdpa', 'score': 'yes_logit_minus_no_logit',
         'model_revision': expected['revision'], 'started_at_unix': time.time()})
    completed = 0
    for key, request in requests.items():
        if key in results:
            if results[key]['request_sha256'] != sha(canonical(request)):
                raise ValueError('Stored rerank request identity changed.')
            continue
        if max_requests is not None and completed >= max_requests:
            break
        results[key] = score(request)
        completed += 1
        save(path, results)
        if completed % 10 == 0 or completed == 1:
            print(split, f'{len(results)}/{len(requests)}', 'last_ms', round(results[key]['duration_ms']), flush=True)
    print('Rerank saved', len(results), '/', len(requests), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--split', choices=('dev', 'test'), required=True)
    p.add_argument('--max-requests', type=int)
    a = p.parse_args()
    run_scores(a.run, a.split, a.max_requests)
