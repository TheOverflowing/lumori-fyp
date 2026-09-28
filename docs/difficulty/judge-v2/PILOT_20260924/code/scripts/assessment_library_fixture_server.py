"""Isolated assessment options / course library browser fixture, with no live calls.

Run: .venv/bin/python -m scripts.assessment_library_fixture_server --port 8770
Account: assessment.library@example.test / Fixture browser password 2026!
Metadata and request log: /__ui/assessment-library-state

Every launch uses a new temporary database and a separate session cookie. Source
excerpts are copied from the existing offline fixture. All content states and
the failed job below are synthetic UI cases, not generated evaluation results.
"""

from copy import deepcopy
import json

from fastapi.responses import JSONResponse

from app.difficulty import build_difficulty_plan
from app.models import GenerateRequest, LearningAsset
from app.pipeline import validate_asset
from app.store import dumps, now
from scripts.review_export_fixture_server import (
    LESSON_ID, QUIZ_ID, create_fixture as create_review_fixture,
)


EMAIL = 'assessment.library@example.test'
PASSWORD = 'Fixture browser password 2026!'
TITLE = 'Machine learning practice / 机器学习练习'
ASSIGNMENT_ID = 'assessment-library-assignment'
COURSE_B = 'assessment-library-course-b'
COURSE_EMPTY = 'assessment-library-empty-course'
COURSE_B_CONTENT = 'assessment-library-course-b-content'
FAILED_JOB = 'assessment-library-course-b-failed'


def create_fixture():
    app = create_review_fixture()
    app.title = 'Lumori · isolated assessment and course library fixture'
    app.state.settings.auth_cookie_name = 'lumori_assessment_library_fixture'
    store = app.state.store
    quiz = store.one('SELECT * FROM contents WHERE id=?', (QUIZ_ID,))
    course_a = quiz['course_id']
    owner = store.one('SELECT user_id FROM course_owners WHERE course_id=?', (course_a,))['user_id']
    store.execute('UPDATE users SET email=?,display_name=? WHERE id=?', (EMAIL, 'Assessment UI fixture', owner))
    store.execute('UPDATE courses SET name=? WHERE id=?', ('A · Machine Learning', course_a))
    timestamp = now()
    with store.connect() as db:
        for id_, name in ((COURSE_B, 'B · Operating Systems'), (COURSE_EMPTY, 'C · Empty course')):
            db.execute('INSERT INTO courses VALUES(?,?,?)', (id_, name, timestamp))
            db.execute('INSERT INTO course_owners VALUES(?,?)', (id_, owner))

    original_asset = json.loads(quiz['asset'])
    original_sources = json.loads(quiz['sources'])
    original_config = json.loads(quiz['config'])

    def request_for(**values):
        fields = {key:value for key,value in original_config.items() if key in GenerateRequest.model_fields}
        return GenerateRequest.model_validate(fields | values)

    def save_content(content_id, job_id, request, asset, sources, status, *, replace=False):
        parsed = LearningAsset.model_validate(asset)
        validate_asset(parsed, request, sources, enforce_difficulty=True)
        config = request.model_dump() | {'difficulty_plan':build_difficulty_plan(request), 'ui_fixture':True}
        with store.connect() as db:
            if replace:
                db.execute('UPDATE contents SET status=?,asset=?,sources=?,config=? WHERE id=?',
                           (status, dumps(asset), dumps(sources), dumps(config), content_id))
                db.execute('UPDATE revisions SET asset=? WHERE content_id=? AND version=1', (dumps(asset), content_id))
                db.execute('UPDATE jobs SET payload=? WHERE id=?', (dumps(config), job_id))
            else:
                db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', (
                    job_id, request.request_key, 'generate', dumps(config), 'succeeded',
                    dumps({'content_id':content_id}), None, timestamp, timestamp))
                db.execute('INSERT INTO job_owners VALUES(?,?)', (job_id, owner))
                db.execute('INSERT INTO contents VALUES(?,?,?,?,?,?,?,?,?)', (
                    content_id, request.course_id, job_id, 1, status, dumps(asset),
                    dumps(sources), dumps(config), timestamp))
                db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (content_id, 1, dumps(asset), timestamp))

    # Three different task types intentionally share the same title in course A.
    lesson = store.one('SELECT * FROM contents WHERE id=?', (LESSON_ID,))
    lesson_asset = json.loads(lesson['asset']) | {'title':TITLE}
    lesson_request = request_for(material='lesson', include_explanations=False,
                                 difficulty_distribution=None, request_key='assessment-lesson')
    save_content(LESSON_ID, lesson['job_id'], lesson_request, lesson_asset,
                 json.loads(lesson['sources']), 'approved', replace=True)

    question_asset = deepcopy(original_asset) | {
        'title':TITLE, 'learning_objectives':[], 'sections':[], 'section_scope':'shared', 'visual_prompt':'',
    }
    question_request = request_for(material='quiz', include_explanations=False, request_key='assessment-question-only')
    save_content(QUIZ_ID, quiz['job_id'], question_request, question_asset, original_sources, 'draft', replace=True)

    assignment_asset = deepcopy(original_asset) | {'title':TITLE}
    assignment_request = request_for(material='assignment', include_explanations=True, request_key='assessment-with-intro')
    save_content(ASSIGNMENT_ID, 'assessment-library-assignment-job', assignment_request,
                 assignment_asset, original_sources, 'approved')

    # Course B owns its own copies of both the documents and excerpt identifiers.
    sources_b = deepcopy(original_sources)
    id_map = {}
    with store.connect() as db:
        for index, document_id in enumerate(dict.fromkeys(source['document_id'] for source in sources_b), 1):
            document = store.one('SELECT * FROM documents WHERE id=?', (document_id,))
            document_b = f'assessment-library-document-b-{index}'
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?)', (
                document_b, COURSE_B, document['name'], document['sha256'], 'parsed', document['pages'], timestamp))
            for source in sources_b:
                if source['document_id'] != document_id:
                    continue
                old_id = source['id']
                source['id'] = 'assessment-b-' + old_id
                source['document_id'] = document_b
                id_map[old_id] = source['id']
                db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)', (
                    source['id'], document_b, source['page'], source['text'], None, None))
    asset_b = deepcopy(question_asset) | {'title':'Only in course B · 独立课程记录'}
    for question in asset_b['questions']:
        question['citation_ids'] = [id_map[id_] for id_ in question['citation_ids']]
    request_b = request_for(course_id=COURSE_B, document_ids=list(dict.fromkeys(source['document_id'] for source in sources_b)),
                            material='quiz', include_explanations=False, request_key='assessment-course-b')
    save_content(COURSE_B_CONTENT, 'assessment-library-course-b-job', request_b, asset_b, sources_b, 'draft')

    with store.connect() as db:
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', (
            FAILED_JOB, 'assessment-course-b-failed-seed', 'generate', dumps(request_b.model_dump()),
            'failed', None, 'Only in course B · Synthetic interrupted task for isolation testing.', timestamp, timestamp))
        db.execute('INSERT INTO job_owners VALUES(?,?)', (FAILED_JOB, owner))

    assert not store.all('SELECT id FROM calls'), 'Fixture setup must never call model providers.'
    assert not any(getattr(app.state.settings, name).configured for name in ('text','embedding','speech','image','vision'))
    app.state.assessment_library_requests = []
    # The base fixture's setup TestClient has already closed. Rebuild the stack
    # on the next startup so this fixture-only guard wraps the existing app.
    app.middleware_stack = None

    @app.middleware('http')
    async def isolated_requests(request, call_next):
        path = request.url.path
        # Root QA visits real forms but must not submit to providers or the network.
        blocked = request.method == 'POST' and (
            path.startswith('/api/generations') or path.endswith(('/index','/parse','/media','/resume')))
        response = JSONResponse({'detail':'Provider execution is disabled in this isolated UI fixture.'}, status_code=409) if blocked else await call_next(request)
        if path.startswith('/api/'):
            app.state.assessment_library_requests.append({
                'method':request.method, 'path':path, 'query':str(request.url.query), 'status':response.status_code,
            })
            del app.state.assessment_library_requests[:-150]
        return response

    @app.get('/__ui/assessment-library-state', include_in_schema=False)
    async def fixture_state():
        return {
            'fixture':True, 'evidence':'Synthetic UI states with copied offline source excerpts; not a live generation result.',
            'account':EMAIL, 'courses':{'a':course_a,'b':COURSE_B,'empty':COURSE_EMPTY},
            'contents':{'lesson':LESSON_ID,'quiz':QUIZ_ID,'assignment':ASSIGNMENT_ID,'course_b':COURSE_B_CONTENT},
            'failed_job_id':FAILED_JOB, 'shared_title':TITLE,
            'provider_calls':store.one('SELECT COUNT(*) AS n FROM calls')['n'],
            'requests':app.state.assessment_library_requests,
        }

    return app


if __name__ == '__main__':
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8770)
    uvicorn.run(create_fixture(), host='127.0.0.1', port=parser.parse_args().port)
