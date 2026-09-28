"""Isolated rating/export browser QA; no production data or model calls.

Run: .venv/bin/python -m scripts.review_export_fixture_server
Default: http://127.0.0.1:8769/ (override with --port)
Account: fixture@example.test / Fixture browser password 2026!
Quiz: /#content/review-export-fixture-quiz
Audit: /__ui/review-state (fixture-only counts and saved rating)

The base fixture supplies the historical lesson and saved source excerpts. This
wrapper adds a hand-authored two-question UI fixture and 100 ms of synthetic
silence. Its approved state is test data, not an AI/human review claim. Every
start gets a fresh temporary SQLite database and a distinct session cookie.
"""

from copy import deepcopy
import json
import wave

from fastapi import HTTPException

from app.content_evaluations import current_evaluation
from app.difficulty import build_difficulty_plan
from app.models import GenerateRequest, LearningAsset
from app.pipeline import validate_asset
from app.store import dumps, now
from scripts.citation_progress_fixture_server import (
    CONTENT_ID as LESSON_ID,
    create_fixture as create_citation_fixture,
)


QUIZ_ID = 'review-export-fixture-quiz'
MEDIA_ID = 'review-export-fixture-audio'


def create_fixture():
    app = create_citation_fixture()
    app.state.settings.auth_cookie_name = 'lumori_review_export_fixture'
    app.title = 'Lumori · isolated review and export fixture'
    store = app.state.store
    lesson = store.one('SELECT * FROM contents WHERE id=?', (LESSON_ID,))
    sources = json.loads(lesson['sources'])
    source_ids = [
        'context_34304f16e5a07c568954c9dcbd680367',
        'context_fcaee519b4ba436c1bec8b533716efe5',
    ]
    selected = [deepcopy(source) for id_ in source_ids for source in sources if source['id'] == id_]
    assert len(selected) == 2, 'The saved source fixture must contain both teaching excerpts.'
    first, second = source_ids
    request = GenerateRequest(
        course_id=lesson['course_id'], topic='Machine learning basics / 机器学习基础',
        material='quiz', count=2, question_type='mixed', difficulty='medium',
        include_explanations=True,
        difficulty_distribution={'easy':1,'medium':1,'hard':0},
        learner_profile='Undergraduates learning machine learning / 初学机器学习的本科生',
        language='en', document_ids=list(dict.fromkeys(source['document_id'] for source in selected)),
        request_key='review-export-fixture-seed',
    )
    asset = LearningAsset.model_validate({
        'title':'Machine learning essentials · 机器学习基础',
        'evidence_sufficient':True,
        'evidence_note':'Hand-authored UI test fixture; no empirical learner evaluation.',
        'learning_objectives':['Explain learning from experience and recognize supervised learning. / 理解从经验学习并识别监督学习。'],
        'sections':[{
            'heading':'Learning from examples · 从实例学习',
            'text':f'Machine learning studies algorithms that learn from experience. 机器学习研究从经验中学习的算法。[{first}]\n\n'
                   f'In supervised learning, examples pair known inputs with target labels. 监督学习的样本包含输入与目标标签。[{second}]',
            'citation_ids':[first,second],
        }],
        'questions':[
            {
                'slot_id':'q1','difficulty':'easy','kind':'mcq',
                'stem':'Which description matches machine learning? / 哪项描述符合机器学习？',
                'options':[
                    'Learning from experience / 从经验中学习',
                    'Always following unchanged rules / 始终遵循不变规则',
                    'Replacing every software developer / 替代所有软件开发者',
                    'Only increasing hardware capacity / 仅增加硬件容量',
                ],
                'answer':'A',
                'explanation':'The defining idea is learning from experience, often represented as data. 核心是从经验中学习，经验通常以数据形式呈现。',
                'difficulty_reason':'Recognize one stated concept. 识别一个明确概念。',
                'difficulty_design':{'cognitive_process':'understand','concepts':['Learning from experience'],
                                     'expected_steps':['Identify the defining role of experience.']},
                'citation_ids':[first],
            },
            {
                'slot_id':'q2','difficulty':'medium','kind':'short_answer',
                'stem':'A wake-word dataset pairs audio clips with yes/no labels. Why is this supervised learning? / 唤醒词数据集为音频片段配有“是／否”标签，为什么这属于监督学习？',
                'options':[],
                'answer':'The audio clips are inputs and the yes/no values are known target labels. 音频片段是输入，“是／否”是已知目标标签。',
                'explanation':'Identify both the input and its supplied label, then connect this pairing to the definition of supervised learning. 先识别输入与标签，再将其对应到监督学习的定义。',
                'difficulty_reason':'Apply the concept to a concrete dataset. 将概念应用到具体数据集。',
                'difficulty_design':{'cognitive_process':'apply','concepts':['Inputs','Target labels','Supervised learning'],
                                     'expected_steps':['Identify the audio inputs and yes/no labels.','Connect the labeled pairs to supervised learning.']},
                'citation_ids':[second],
            },
        ],
        'visual_prompt':'',
    })
    validate_asset(asset,request,selected,enforce_difficulty=True)
    config = request.model_dump() | {'difficulty_plan':build_difficulty_plan(request),'ui_fixture':True}
    timestamp = now()
    owner = store.one('SELECT user_id FROM course_owners WHERE course_id=?', (lesson['course_id'],))['user_id']
    with store.connect() as db:
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', (
            'review-export-fixture-job',request.request_key,'generate',dumps(config),
            'succeeded',dumps({'content_id':QUIZ_ID}),None,timestamp,timestamp,
        ))
        db.execute('INSERT INTO job_owners VALUES(?,?)', ('review-export-fixture-job',owner))
        db.execute('INSERT INTO contents VALUES(?,?,?,?,?,?,?,?,?)', (
            QUIZ_ID,lesson['course_id'],'review-export-fixture-job',1,'approved',dumps(asset.model_dump()),
            dumps(selected),dumps(config),timestamp,
        ))
        db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (QUIZ_ID,1,dumps(asset.model_dump()),timestamp))
    media_directory = app.state.settings.data_dir / 'media'
    media_directory.mkdir(exist_ok=True)
    with wave.open(str(media_directory / 'synthetic-ui-fixture.wav'),'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b'\x00\x00' * 2400)
    store.execute('INSERT INTO media VALUES(?,?,?,?,?,?,?,?,?)', (
        MEDIA_ID,QUIZ_ID,1,'audio','synthetic-ui-fixture.wav','audio/wav','approved',
        dumps({'ui_fixture':True,'duration_ms':100,'description':'Synthetic silence for attachment UI testing; not model-generated.'}),timestamp,
    ))
    assert not store.all('SELECT id FROM calls'), 'Fixture setup must not call model providers.'

    @app.get('/__ui/review-state',include_in_schema=False)
    async def review_state(content_id: str = QUIZ_ID):
        if content_id not in (QUIZ_ID,LESSON_ID):
            raise HTTPException(404,'Unknown fixture material')
        content = store.one('SELECT version FROM contents WHERE id=?',(content_id,))
        version = content['version']
        count = lambda sql: store.one(sql,(content_id,))['n']
        return {
            'fixture':True,'content_id':content_id,'version':version,
            'evaluation_count':count('SELECT COUNT(*) AS n FROM evaluations WHERE content_id=?'),
            'current_evaluation_count':count('SELECT COUNT(*) AS n FROM current_evaluations WHERE content_id=?'),
            'history_count':count('SELECT COUNT(*) AS n FROM evaluation_history h JOIN evaluations e ON e.id=h.evaluation_id WHERE e.content_id=?'),
            'evaluation':current_evaluation(store,content_id,version),
            'provider_calls':store.one('SELECT COUNT(*) AS n FROM calls')['n'],
        }

    return app


if __name__ == '__main__':
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8769)
    args = parser.parse_args()
    uvicorn.run(create_fixture(),host='127.0.0.1',port=args.port)
