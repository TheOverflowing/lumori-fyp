"""Download public, revision-pinned research weights/tokenizers into this workspace."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.rag-models'
os.environ['HF_HOME'] = str(BASE / 'hub-cache')
os.environ['HF_HUB_DISABLE_XET'] = '1'
from huggingface_hub import HfApi, snapshot_download


def main():
    BASE.mkdir(exist_ok=True)
    manifest_path = BASE / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name, repository, weights in (
        ('embedding-tokenizer', 'Qwen/Qwen3-Embedding-8B', False),
        ('qwen-reranker', 'Qwen/Qwen3-Reranker-0.6B', True),
    ):
        revision = manifest.get(name, {}).get('revision') or HfApi(token=False).model_info(repository).sha
        patterns = ['config.json', 'tokenizer.json', 'tokenizer_config.json', 'vocab.json', 'merges.txt',
                    'special_tokens_map.json', 'generation_config.json', 'README.md', 'LICENSE']
        if weights:
            patterns.append('*.safetensors')
        path = snapshot_download(repository, revision=revision, token=False, allow_patterns=patterns,
                                 local_dir=BASE / name, max_workers=2)
        hashes = {}
        for p in sorted(Path(path).iterdir()):
            if p.is_file():
                h = hashlib.sha256()
                with p.open('rb') as f:
                    for block in iter(lambda: f.read(1024 * 1024), b''):
                        h.update(block)
                hashes[p.name] = h.hexdigest()
        manifest[name] = {'repository': repository, 'revision': revision, 'files_sha256': hashes,
                          'bytes': sum(p.stat().st_size for p in Path(path).iterdir() if p.is_file())}
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(name, revision, manifest[name]['bytes'], flush=True)


if __name__ == '__main__':
    main()
