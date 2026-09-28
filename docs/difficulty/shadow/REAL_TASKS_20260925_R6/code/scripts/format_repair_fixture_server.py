"""Isolated format-repair progress UI. Every displayed outcome is synthetic.

Run: .venv/bin/python -m scripts.format_repair_fixture_server --port 8771
Account: assessment.library@example.test / Fixture browser password 2026!
Progress: /#progress/format-repair-fixture-failed
Audit: /__ui/format-repair-state

The inherited fixture has a fresh temporary database and rejects all generation,
resume, indexing and media submissions. No provider calls are allowed. This file
seeds frozen configurations through the real initializer with an offline source
adapter, then supplies synthetic candidate and timeline records for browser QA.
It does not represent a model evaluation or a successful live repair.
"""

import asyncio
from copy import deepcopy
import json

from app import job_progress
from app.generation_agent import GenerationAgent
from app.models import GenerateRequest
from app.store import dumps, now
from scripts.assessment_library_fixture_server import (
    EMAIL, PASSWORD, create_fixture as create_library_fixture,
)
from scripts.review_export_fixture_server import QUIZ_ID


FAILED_JOB = 'format-repair-fixture-failed'
SUCCEEDED_JOB = 'format-repair-fixture-complete'


def create_fixture():
    app = create_library_fixture()
    app.title = 'Lumori · isolated format repair progress fixture'
    app.state.settings.auth_cookie_name = 'lumori_format_repair_fixture'
    app.state.settings.generation_workflow = 'agent_v1'
    store, pipeline = app.state.store, app.state.pipeline
    content = store.one('SELECT * FROM contents WHERE id=?', (QUIZ_ID,))
    sources, asset = json.loads(content['sources']), json.loads(content['asset'])
    config = json.loads(content['config'])
    owner = store.one('SELECT user_id FROM course_owners WHERE course_id=?', (content['course_id'],))['user_id']

    async def offline_sources(request, job_id, *, with_trace=False):
        assert job_id in (FAILED_JOB, SUCCEEDED_JOB)
        result = deepcopy(sources)
        return (result, {'ui_fixture': True, 'method': 'copied_offline_excerpts'}) if with_trace else result

    original_retrieve = pipeline.retrieve
    pipeline.retrieve = offline_sources
    try:
        for job_id in (FAILED_JOB, SUCCEEDED_JOB):
            request = GenerateRequest.model_validate({
                key: value for key, value in config.items() if key in GenerateRequest.model_fields
            } | {'request_key': job_id, 'auto_explore': False, 'query_fusion': False})
            timestamp = now()
            with store.connect() as db:
                db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', (
                    job_id, request.request_key, 'generate', dumps(request.model_dump()),
                    'failed', None, None, timestamp, timestamp))
                db.execute('INSERT INTO job_owners VALUES(?,?)', (job_id, owner))
            job_progress.begin(store, job_id, ['retrieval', 'writing', 'saving'], total=2)
            agent = GenerationAgent(pipeline, request, job_id)
            asyncio.run(agent.initialize())
            first, second = agent.state['slots']
            first_asset = deepcopy(asset) | {'questions': [deepcopy(asset['questions'][0])]}
            second_asset = deepcopy(asset) | {'questions': [deepcopy(asset['questions'][1])]}
            first.update(status='passed', accepted_asset=first_asset, verification='synthetic_ui_fixture',
                         attempts=[{'number': 1, 'status': 'passed', 'author': {'response': deepcopy(first_asset), 'history': []}}])
            second.update(status='failed', attempts=[])
            for attempt in (1, 2, 3):
                raw = deepcopy(second_asset)
                raw['questions'][0]['difficulty_design']['concepts'] = [f'Fixture concept {n}' for n in range(1, 8)]
                second['attempts'].append({'number': attempt, 'status': 'rejected',
                    'author': {'response': raw, 'history': []},
                    'feedback': {'issues': ['author_contract_invalid'],
                                 'validation': {'rule': 'schema_validation'}}})
            agent.state.update(status='quality_failed', phase='review', current_slot='q2')
            agent.evidence['ui_fixture'] = 'Synthetic progress only; no model validation occurred.'
            agent.save()
            job_progress.update(store, job_id, 'retrieval', complete=True)
            job_progress.update(store, job_id, 'writing', activity='writing', completed=1)
            job_progress.event(store, job_id, 'writing', 'question_passed', number=1, completed=1, total=2)
            job_progress.event(store, job_id, 'writing', 'question_started', number=2, total=2)
            for attempt in (1, 2, 3):
                if attempt > 1:
                    job_progress.event(store, job_id, 'writing', 'question_repair', number=2, attempt=attempt)
                job_progress.event(store, job_id, 'writing', 'question_check_failed',
                                   number=2, attempt=attempt, reason='format')
            job_progress.event(store, job_id, 'writing', 'question_format_adapting', number=2)
            job_progress.event(store, job_id, 'writing', 'question_format_adapted', number=2, level='compatible')
            job_progress.update(store, job_id, 'writing', activity='reviewing')
            if job_id == FAILED_JOB:
                second['attempts'][-1]['feedback'] = {'issues': ['answer_correct']}
                agent.save()
                job_progress.event(store, job_id, 'writing', 'question_check_failed',
                                   number=2, attempt=3, reason='quality')
                store.execute('UPDATE jobs SET error=? WHERE id=?',
                    ('第 2 题仍需修正内容，已完成的题目已保留。', job_id))
                job_progress.finish(store, job_id, 'failed')
            else:
                second.update(status='passed', accepted_asset=second_asset, verification='synthetic_ui_fixture')
                second['attempts'][-1]['status'] = 'passed'
                agent.state['status'] = 'completed'
                agent.save()
                job_progress.event(store, job_id, 'writing', 'question_passed', number=2, completed=2, total=2)
                job_progress.update(store, job_id, 'writing', complete=True, completed=2)
                job_progress.update(store, job_id, 'saving', activity='saving')
                store.execute('UPDATE jobs SET status=?,result=? WHERE id=?',
                              ('succeeded', dumps({'content_id': QUIZ_ID}), job_id))
                job_progress.finish(store, job_id, 'succeeded')
    finally:
        pipeline.retrieve = original_retrieve

    assert not store.all('SELECT id FROM calls')
    assert not any(getattr(app.state.settings, name).configured for name in ('text', 'embedding', 'speech', 'image', 'vision'))

    @app.get('/__ui/format-repair-state', include_in_schema=False)
    async def fixture_state():
        return {
            'fixture': True, 'evidence': 'Synthetic UI records only; no live generation or review.',
            'account': EMAIL, 'course_id': content['course_id'],
            'jobs': {'failed': FAILED_JOB, 'complete': SUCCEEDED_JOB}, 'content_id': QUIZ_ID,
            'provider_calls': store.one('SELECT COUNT(*) AS n FROM calls')['n'],
            'requests': app.state.assessment_library_requests,
        }

    return app


if __name__ == '__main__':
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8771)
    uvicorn.run(create_fixture(), host='127.0.0.1', port=parser.parse_args().port)
