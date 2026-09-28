"""Isolated adjusted-difficulty, request-recovery and export toolbar UI fixture.

Run: .venv/bin/python -m scripts.difficulty_export_fixture_server --port 8769
Account: fixture@example.test / Fixture browser password 2026!
Everything added here is synthetic test data; no provider calls or real user edits.
"""
import json
from app.models import GenerateRequest
from app.difficulty import build_difficulty_plan, difficulty_acceptance
from app.store import dumps
from scripts.review_export_fixture_server import create_fixture as create_review_fixture, QUIZ_ID

def create_fixture():
    app = create_review_fixture()
    app.state.settings.auth_cookie_name = 'lumori_difficulty_export_fixture'
    app.title = 'Lumori · isolated difficulty and export fixture'
    store = app.state.store
    content = store.one('SELECT * FROM contents WHERE id=?', (QUIZ_ID,))
    config = json.loads(content['config'])
    request = GenerateRequest.model_validate({key: value for key, value in config.items()
        if key in GenerateRequest.model_fields} | {
        'topic': 'Compare database locking and thread locking. / 比较数据库锁与线程锁。',
        'difficulty': 'hard', 'difficulty_distribution': {'easy': 0, 'medium': 0, 'hard': 2},
        'learner_profile': 'Second-year CS students who know SQL and threads. / 已学 SQL 与线程的计算机大二学生。',
        'query_fusion': True, 'auto_explore': True,
        'request_key': 'difficulty-export-fixture-recovery',
    })
    config.update(request.model_dump(), difficulty_plan=build_difficulty_plan(request))
    config['difficulty_acceptance'] = difficulty_acceptance([
        {'slot_id': 'q1', 'assessed_difficulty': 'easy', 'confidence': 'high'},
        {'slot_id': 'q2', 'assessed_difficulty': 'medium', 'confidence': 'high'},
    ], config['difficulty_plan'], rounds=3, accepted_attempt=2)
    asset = json.loads(content['asset'])
    for question in asset['questions']:
        question['difficulty'] = 'hard'
    store.execute('UPDATE contents SET asset=?,config=? WHERE id=?', (dumps(asset), dumps(config), QUIZ_ID))
    store.execute('UPDATE revisions SET asset=? WHERE content_id=? AND version=1', (dumps(asset), QUIZ_ID))
    owner = store.one('SELECT user_id FROM course_owners WHERE course_id=?', (request.course_id,))['user_id']
    job, _ = store.job(request.request_key, 'generate', request.model_dump(), owner_id=owner)
    # Use the generated ID: unrelated tables may have foreign-key references.
    app.state.recovery_job_id = job['id']
    store.execute("UPDATE jobs SET status='failed',error=? WHERE id=?", ('Synthetic provider interruption for request recovery UI verification.', job['id']))
    assert store.one('SELECT COUNT(*) AS n FROM calls')['n'] == 0

    @app.get('/__ui/difficulty-state', include_in_schema=False)
    async def state():
        return {'fixture': True, 'quiz_id': QUIZ_ID, 'failed_job_id': job['id'],
                'request': request.model_dump(exclude={'request_key'}),
                'provider_calls': store.one('SELECT COUNT(*) AS n FROM calls')['n']}
    return app

if __name__ == '__main__':
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8769)
    uvicorn.run(create_fixture(), host='127.0.0.1', port=parser.parse_args().port)
