"""Small public-input live contract check; not a retrieval or learner benchmark."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.models import GenerateRequest
from app.providers import ApiProviders
from app.store import Store, now
from app.generation_preparation import prepare
from app.query_clarification import PROMPT_VERSION

CASES = [
    ('zh_clear', 'zh', '想学一下那个像排队买饭，谁先来谁先走的数据结构，帮我讲明白入队和出队。', 'ready'),
    ('en_clear', 'en', 'Explain the data thing that behaves like a pile of plates: I add on top and take the last plate off first.', 'ready'),
    ('zh_general', 'zh', '请讲解二分查找，并举例说明。', 'ready'),
    ('zh_instance', 'zh', '我正在做二分查找，这一步下一次应该留哪一半呀？', 'clarification_required'),
    ('zh_avl', 'zh', '这个 AVL 树有个点歪了，先往哪边拧才能扶正呀？', 'clarification_required'),
    ('en_components', 'en', 'My undirected graph has separate pieces. I visited everything reachable from my starting point, but other vertices remain. Is my traversal task finished or should I continue?', 'clarification_required'),
]


async def run(output):
    settings = Settings.from_env()
    settings.text.require('text')
    output.mkdir(parents=True, exist_ok=False)
    records = {'scope': 'Six hand-selected public-input runtime smoke cases; no retrieval, generation or learner outcomes.',
               'prompt_version': PROMPT_VERSION, 'model': settings.text.model,
               'cases': [{'id': i, 'language': lang, 'topic': q, 'expected_for_smoke_only': expected} for i, lang, q, expected in CASES],
               'code_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                              ('app/query_clarification.py', 'app/generation_preparation.py', 'app/providers.py', 'app/models.py')},
               'outputs': [], 'calls': []}
    def save():
        (output/'smoke.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
    save()
    with tempfile.TemporaryDirectory(prefix='lumori-clarification-smoke-') as tmp:
        store = Store(Path(tmp))
        store.execute('INSERT INTO users VALUES(?,?,?,?,?)', ('public-fixture', 'public-fixture@example.invalid', 'unused-not-a-login', 'Public smoke fixture', now()))
        providers = ApiProviders(settings, store)
        try:
            for case_id, lang, topic, expected in CASES:
                request = GenerateRequest(course_id='public-course', topic=topic, material='lesson', language=lang,
                                          learner_profile='Computer science undergraduate', request_key='smoke-'+case_id)
                response = await prepare(store, providers, request, 'public-fixture')
                evidence = store.one('SELECT evidence FROM job_evidence WHERE job_id=?', (response['preparation_id'],))
                records['outputs'].append({'id': case_id, 'response': response,
                                           'evidence': json.loads(evidence['evidence']) if evidence else None})
                records['calls'] = store.all('SELECT capability,model,status,usage,http_status,response_model,duration_ms FROM calls ORDER BY rowid')
                for item in records['calls']: item['usage'] = json.loads(item['usage'])
                save()
                print(case_id, response['status'], flush=True)
        finally:
            await providers.close()
    print(output/'smoke.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Authorize at most six text calls, using configured credentials.')
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({'cases': CASES, 'maximum_new_text_calls': len(CASES)}, ensure_ascii=False, indent=2))
    else:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        asyncio.run(run(ROOT/'docs/rag/clarification-runtime'/stamp))
