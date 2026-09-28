"""Disposable continuity/navigation browser QA; synthetic data, no provider calls.

Run: .venv/bin/python -m uvicorn scripts.frontend_continuity_fixture:create_fixture --factory --host 127.0.0.1 --port 8777
Main account: fixture@example.test / Fixture browser password 2026!
Main courses: Continuity · Machine Learning; Continuity · Algorithms
Other account: continuity-other@example.test / Fixture browser password 2026!
Other course: Continuity · Other account
Long review: /#content/continuity-long-content (20 questions and two sections)
Main list: 35 new entries plus the inherited citation lesson. The long review
appears near entry 27, allowing an open-and-return test well below the fold.
Secondary content IDs: continuity-algorithms-content, continuity-other-content.

Reuses citation_progress_fixture_server's fresh temporary database and account.
All additional rows are inserted only into that temporary database; no real data
or provider configuration is loaded. Content, approval states and timings are UI
fixtures, not generation/evaluation evidence. Automatic exploration is disabled.
The original /__ui/progress simulated-animation fixture remains available.
"""

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from tempfile import gettempdir

from app.auth import hash_password
from app.models import GenerateRequest, LearningAsset
from app.store import dumps
from scripts.citation_progress_fixture_server import (
    EMAIL, PASSWORD, create_fixture as create_citation_fixture,
)

LONG_CONTENT_ID = 'continuity-long-content'
OTHER_EMAIL = 'continuity-other@example.test'
OTHER_USER_ID = 'continuity-other-user'
ALGORITHMS_COURSE_ID = 'continuity-algorithms-course'
OTHER_COURSE_ID = 'continuity-other-course'
COURSE_NAMES = ('Continuity · Machine Learning', 'Continuity · Algorithms',
                'Continuity · Other account')

SOURCE_TEXT = (
    'Synthetic UI fixture note. A training set supplies examples used to fit a model. '
    'A test set is held apart to evaluate performance on examples that were not used '
    'for fitting. Comparing training and test performance can reveal poor generalization. '
    'These sentences and the associated questions are deterministic interface fixtures, '
    'not the output of a model or a record of an educational experiment.'
)


def _asset(title, source_id, *, long=False, material='quiz'):
    question_count = 0 if material == 'lesson' else 20 if long else 1
    questions = []
    for number in range(1, question_count + 1):
        mcq = number % 2 == 1
        questions.append({
            'slot_id': f'q{number}', 'difficulty': 'medium',
            'difficulty_design': {'cognitive_process': 'apply',
                                  'concepts': ['training data', 'test data'],
                                  'expected_steps': ['Identify the evaluation data.',
                                                     'Explain why it must be kept separate.']},
            'kind': 'mcq' if mcq else 'short_answer',
            'stem': (f'Navigation scenario {number}: a student fits a model using a collection '
                     'of labelled examples, then wants to estimate how it will perform on '
                     'new examples. Which evaluation choice keeps the test independent of '
                     'the fitting process?' if mcq else
                     f'Navigation scenario {number}: a model performs well on its training '
                     'examples but less well on a separate test set. Explain the purpose '
                     'of keeping these sets separate and what this difference suggests.'),
            'options': ['Use a held-out test set.', 'Fit again on all the test examples.',
                        'Report only training performance.', 'Remove every difficult test example.'] if mcq else [],
            'answer': 'A' if mcq else ('Keeping test examples separate measures performance on unseen data. '
                                      'The difference can suggest poor generalization.'),
            'explanation': ('The held-out test set provides examples that were not used to fit the model. '
                            'This explanation is synthetic content for testing reading and editing controls.'),
            'difficulty_reason': 'UI fixture label only; no student difficulty measurement was performed.',
            'citation_ids': [source_id],
        })
    sections = []
    if long or material == 'lesson':
        sections = [
            {'heading': 'Training and evaluation', 'text': SOURCE_TEXT,
             'citation_ids': [source_id]},
            {'heading': 'Reading this practice set',
             'text': ('Each numbered scenario is an independent synthetic item. Use the section and '
                      'question navigation to move through this long review. Answers and explanations '
                      'are deliberately present so that expanding, editing and returning to the list '
                      'can be exercised without waiting for any model service.'),
             'citation_ids': [source_id]},
        ]
    return LearningAsset.model_validate({
        'title': title, 'evidence_sufficient': True,
        'evidence_note': 'Synthetic UI fixture; not generation quality or human-review evidence.',
        'learning_objectives': ['Practice navigating and reviewing a long assessment.'],
        'section_scope': 'shared', 'sections': sections, 'questions': questions,
        'visual_prompt': '',
    }).model_dump()


def _source(db, course_id, suffix, stamp):
    document_id, chunk_id = f'continuity-source-{suffix}', f'continuity-chunk-{suffix}'
    name = 'Synthetic continuity note.md'
    db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?)',
               (document_id, course_id, name, hashlib.sha256(SOURCE_TEXT.encode()).hexdigest(),
                'parsed', 1, stamp))
    db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',
               (chunk_id, document_id, 1, SOURCE_TEXT, None, None))
    return {'id': chunk_id, 'document_id': document_id, 'document_name': name,
            'page': 1, 'text': SOURCE_TEXT, 'score': 1.0}


def _content(db, *, content_id, owner, course_id, source, title, stamp, material='quiz', long=False):
    asset = _asset(title, source['id'], long=long, material=material)
    config = GenerateRequest(course_id=course_id, topic=title, material=material,
                             count=len(asset['questions']) or 1, language='en',
                             learner_profile='Undergraduates · isolated UI fixture',
                             request_key=f'fixture-{content_id}',
                             include_explanations=bool(asset['sections'])).model_dump()
    config['ui_fixture'] = True
    job_id = f'job-{content_id}'
    db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
               (job_id, f'fixture-{content_id}', 'generate', dumps(config), 'succeeded',
                dumps({'content_id': content_id}), None, stamp, stamp))
    db.execute('INSERT INTO job_owners VALUES(?,?)', (job_id, owner))
    db.execute('INSERT INTO contents VALUES(?,?,?,?,?,?,?,?,?)',
               (content_id, course_id, job_id, 1, 'draft', dumps(asset),
                dumps([source]), dumps(config), stamp))
    db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (content_id, 1, dumps(asset), stamp))


def create_fixture():
    app = create_citation_fixture()
    store = app.state.store
    # Fail closed if the reused factory ever stops creating disposable storage.
    directory = store.path.resolve().parent
    assert directory.is_relative_to(Path(gettempdir()).resolve())
    assert directory.name.startswith('lumori-citation-progress-ui-')
    app.state.settings.exploration_enabled = False
    assert not any(getattr(app.state.settings, capability).configured for capability in
                   ('text', 'embedding', 'rerank', 'speech', 'image', 'vision'))
    user = store.one('SELECT id FROM users WHERE email=?', (EMAIL,))
    course = store.one('SELECT course_id FROM course_owners WHERE user_id=?', (user['id'],))
    course_id = course['course_id']
    clock = datetime.now(timezone.utc)
    stamp = clock.isoformat()
    with store.connect() as db:
        db.execute('UPDATE courses SET name=? WHERE id=?', (COURSE_NAMES[0], course_id))
        db.execute('INSERT INTO users VALUES(?,?,?,?,?)',
                   (OTHER_USER_ID, OTHER_EMAIL, hash_password(PASSWORD), 'Other UI fixture', stamp))
        for cid, name, owner in [(ALGORITHMS_COURSE_ID, COURSE_NAMES[1], user['id']),
                                 (OTHER_COURSE_ID, COURSE_NAMES[2], OTHER_USER_ID)]:
            db.execute('INSERT INTO courses VALUES(?,?,?)', (cid, name, stamp))
            db.execute('INSERT INTO course_owners VALUES(?,?)', (cid, owner))
        source = _source(db, course_id, 'main', stamp)
        for number in range(1, 36):
            long = number == 26
            material = 'quiz' if long else ('lesson', 'quiz', 'assignment')[(number-1) % 3]
            title = ('Long assessment · 20 navigation scenarios' if long else
                     f'Practice {number:02d} · Training and evaluation')
            _content(db, content_id=LONG_CONTENT_ID if long else f'continuity-content-{number:02d}',
                     owner=user['id'], course_id=course_id, source=source, title=title,
                     stamp=(clock-timedelta(minutes=number)).isoformat(), material=material, long=long)
        for cid, owner, suffix, title in [
                (ALGORITHMS_COURSE_ID, user['id'], 'algorithms', 'Algorithm practice · separate course'),
                (OTHER_COURSE_ID, OTHER_USER_ID, 'other', 'Private practice · other account')]:
            _content(db, content_id=f'continuity-{suffix}-content', owner=owner, course_id=cid,
                     source=_source(db, cid, suffix, stamp), title=title, stamp=stamp)
    assert not store.all('SELECT id FROM calls'), 'UI fixture must not call any provider'
    app.state.continuity_fixture = {'primary_course': course_id,
                                    'secondary_course': ALGORITHMS_COURSE_ID,
                                    'other_course': OTHER_COURSE_ID,
                                    'long_content': LONG_CONTENT_ID}
    return app
