"""Disposable task-controls and question-revision UI fixture. No provider calls.

Synthetic responses exercise UI contracts, not generation quality or backend
cancellation. Launch on port 8773; account assessment.library@example.test /
Fixture browser password 2026!; start /#progress/task-controls-fixture-running.
Metadata /__ui/task-revision-state records synthetic submissions and call count.
"""
from copy import deepcopy
import json
from fastapi.responses import JSONResponse
from scripts.assessment_library_fixture_server import create_fixture as base_fixture
from scripts.review_export_fixture_server import QUIZ_ID
from app.store import dumps

RUNNING = 'task-controls-fixture-running'
REVISION = 'task-controls-fixture-revision'


def create_fixture():
    app = base_fixture()
    app.state.settings.auth_cookie_name = 'lumori_task_revision_fixture'
    app.middleware_stack = None
    store = app.state.store
    original = store.one('SELECT * FROM contents WHERE id=?', (QUIZ_ID,))
    original_asset = json.loads(original['asset'])
    sources = json.loads(original['sources'])
    operations = []
    state = {'status': 'running', 'cancel_requested': False, 'revision_created': False}

    def job(job_id):
        revision = job_id == REVISION
        status = 'succeeded' if revision else state['status']
        return {
            'id': job_id, 'kind': 'revise_question' if revision else 'generate',
            'status': status, 'course_id': original['course_id'],
            'cancellable': not revision and status == 'running',
            'cancel_requested': state['cancel_requested'] if not revision else False,
            'partial_available': not revision,
            'progress': {'resumable': not revision and status == 'cancelled', 'completed': 1, 'total': 2},
            'result': {'content_id': QUIZ_ID, 'version': 2} if revision else None,
            'timeline': {
                'recorded': True, 'active_stage': None if status != 'running' else 'writing',
                'activity': 'reviewing', 'completed': 1 if not revision else 2,
                'total': 2, 'unit': 'questions', 'elapsed_ms': 23000,
                'timing_complete': status != 'running',
                'stages': [
                    {'id': 'retrieval', 'kind': 'retrieval', 'status': 'completed', 'elapsed_ms': 2400, 'timing_complete': True},
                    {'id': 'writing', 'kind': 'writing', 'status': 'completed' if revision else 'active' if status == 'running' else 'cancelled', 'elapsed_ms': 20600, 'timing_complete': status != 'running'},
                    {'id': 'saving', 'kind': 'saving', 'status': 'completed' if revision else 'pending'},
                ],
                'events': [],
            },
        }

    @app.middleware('http')
    async def contracts(request, call_next):
        path = request.url.path
        if path == f'/api/jobs/{RUNNING}/cancel' and request.method == 'POST':
            state['cancel_requested'] = True
            operations.append({'action': 'cancel'})
            return JSONResponse({'id': RUNNING, 'status': 'running', 'cancel_requested': True})
        if path == f'/api/jobs/{RUNNING}' and request.method == 'GET':
            result = job(RUNNING)
            if state['cancel_requested']:
                state['status'] = 'cancelled'
            return JSONResponse(result)
        if path == f'/api/jobs/{REVISION}' and request.method == 'GET':
            return JSONResponse(job(REVISION))
        if path == f'/api/jobs/{RUNNING}/partial-content':
            return JSONResponse({'asset': original_asset | {'questions': [original_asset['questions'][0]]},
                                 'sources': sources, 'config': json.loads(original['config']),
                                 'completed': 1, 'total': 2, 'partial': True})
        if request.method == 'POST' and '/questions/' in path and path.endswith('/revise'):
            body = await request.json()
            operations.append({'action': 'revise', 'path': path, 'payload': body})
            asset = deepcopy(original_asset)
            slot = path.split('/questions/')[1].split('/')[0]
            index = next(i for i, q in enumerate(asset['questions']) if q['slot_id'] == slot)
            previous = deepcopy(asset['questions'][index])
            if body['mode'] == 'rewrite':
                asset['questions'][index]['stem'] = 'A spam filter learns from labelled messages. Which description explains its learning? / 垃圾邮件过滤器从已标记邮件中学习，哪种描述符合其学习过程？'
                if body.get('difficulty'):
                    asset['questions'][index]['difficulty'] = body['difficulty']
            asset['questions'][index]['explanation'] = 'The program improves from examples of messages and their labels. / 程序通过邮件实例及标签改进判断。'
            config = json.loads(original['config']) | {'question_revision': {
                'slot_id': slot, 'mode': body['mode'], 'instruction': body['instruction'],
                'base_version': 1, 'version': 2, 'previous_question': previous,
            }}
            store.execute('UPDATE contents SET asset=?,config=?,version=2,status=? WHERE id=?',
                          (dumps(asset), dumps(config), 'draft', QUIZ_ID))
            state['revision_created'] = True
            return JSONResponse({'job_id': REVISION})
        return await call_next(request)

    @app.get('/__ui/task-revision-state', include_in_schema=False)
    async def audit():
        return {'fixture': True, 'provider_calls': store.one('SELECT COUNT(*) AS n FROM calls')['n'],
                'evidence': 'Synthetic UI contract responses; no actual generation, review or cancellation.',
                'state': state, 'operations': operations, 'content_id': QUIZ_ID}

    return app


if __name__ == '__main__':
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8773)
    uvicorn.run(create_fixture(), host='127.0.0.1', port=parser.parse_args().port)
