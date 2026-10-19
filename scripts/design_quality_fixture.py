"""Isolated, synthetic Chinese course for design and browser QA.

Run: .venv/bin/python -m scripts.design_quality_fixture --port 8767
Account: ui-fixture@example.test / Fixture browser password 2026!
Audit: /__ui/design-quality-state

Each launch creates a temporary database. All provider requests use MockTransport;
the course, source documents, generation, and approval states are synthetic. An
approved fixture is not evidence of teacher review or learner outcomes.
"""

import json
from pathlib import Path
import runpy
from tempfile import mkdtemp

from fastapi.testclient import TestClient
import httpx

from app.config import Endpoint, Settings
from app.main import create_app
from app.providers import ApiProviders


EMAIL = 'ui-fixture@example.test'
PASSWORD = 'Fixture browser password 2026!'
COURSE_NAME = '生成式 AI 与知识检索'
EVIDENCE_NOTE = '此内容为隔离环境中的人工编写界面示例；课程、生成记录与审核状态均为合成测试数据。'
DOCUMENTS = (
    ('01_从课程资料到有据可查的回答.md', '''# 从课程资料到有据可查的回答

> 合成教学示例，仅用于界面验证。

检索增强生成（RAG）在回答前检索外部资料，将相关片段作为上下文提供给语言模型。
一个基础流程包含资料导入、文本切分、向量编码、相关片段检索和基于片段生成回答。
向量编码将文本转为数值表示，帮助系统寻找语义相关的片段；它不会更新语言模型的参数。

检索结果为回答提供依据，但相关性不等于正确性。教师仍应检查原文是否支持回答，
并在资料不足时补充材料或暂缓发布。保留文档名称、片段位置和引用关系有助于回查。
'''),
    ('02_切分与检索的设计选择.md', '''# 切分与检索的设计选择

> 合成教学示例，仅用于界面验证。

文本切分需要保留概念与例子之间的联系。过短的片段可能丢失上下文，过长的片段可能
包含大量无关内容。相邻片段适度重叠可以保留跨边界信息，但也会增加存储和检索重复。

语义检索通过向量表示寻找与问题相关的资料，并不保证第一个结果就是正确答案。
评估检索时，可以检查所需证据是否被召回、片段能否支持问题，以及是否有重复或噪声。
若课程问题需要比较两种方法，应检查上下文是否同时包含两种方法及其适用条件。
'''),
    ('03_引用核对与教师审核.md', '''# 引用核对与教师审核

> 合成教学示例，仅用于界面验证。

引用标记只是把一句话关联到来源，不能自动证明该来源支持结论。审核时应打开原文，
检查结论是否超出材料范围、限定条件是否被遗漏，以及不同来源是否相互矛盾。

假设材料只说“检索提供参考资料”，回答却说“检索保证答案正确”，该引用没有支持
回答中的保证性结论。可以改为“检索提供参考资料，回答仍需核对”，或补充可靠证据。

在发布测验前，教师还应独立检查题干是否清晰、参考答案能否由材料推出、选择题是否
只有一个最优答案。对于证据不足的题目，应补充资料、修订问题或暂缓发布。
'''),
)


def create_fixture():
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_workflow.py'))

    class DesignWire(helpers['Wire']):
        """Reuse the contract fixture's transport and supply hand-authored content."""

        def __call__(self, request):
            if request.url.path.endswith('/chat/completions'):
                instruction = json.loads(json.loads(request.content)['messages'][1]['content'])
                if instruction.get('task') == 'content_ai_review':
                    self.calls += 1
                    assert request.headers['authorization'] == 'Bearer test-key-not-real'
                    sources = {source['id']:source['text'] for source in instruction['sources']}
                    report = {
                        'summary':'隔离界面示例：所有检查项返回通过；此模拟结果不代表真实 AI 或教师审核。',
                        'checks':[{'key':key,'status':'pass','rationale':'合成审核响应，仅用于验证界面与状态流转。'}
                                  for key in ('correctness','groundedness','answerability','clarity','objective_alignment')],
                        'items':[{'id':unit['id'],'status':'pass','rationale':'合成审核响应，已保留来源定位。',
                                  'source_ids':unit['citation_ids'],
                                  'evidence':[{'source_id':sid,'quote':sources[sid][:160]}
                                              for sid in unit['citation_ids']]}
                                 for unit in instruction['units']],
                        'findings':[],
                    }
                    return httpx.Response(200,json={'choices':[{'finish_reason':'stop',
                        'message':{'content':json.dumps(report,ensure_ascii=False)}}]})
            response = super().__call__(request)
            if not request.url.path.endswith('/chat/completions'):
                return response
            instruction = json.loads(json.loads(request.content)['messages'][1]['content'])
            if instruction.get('task') == 'difficulty_assessment':
                return response
            payload = response.json()
            asset = json.loads(payload['choices'][0]['message']['content'])
            material = instruction['request']['material']
            references = [instruction['reference_chunks'][0]['id']]
            asset['evidence_note'] = EVIDENCE_NOTE
            asset['visual_prompt'] = ''
            if material == 'lesson':
                asset['title'] = '从课程资料，到有据可查的回答'
                asset['learning_objectives'] = ['说明 RAG 的基础流程', '区分资料相关性与回答正确性']
                asset['sections'] = [
                    {'heading':'让回答从课程资料出发',
                     'text':'检索增强生成（RAG）先从课程资料中寻找相关片段，再将这些片段提供给语言模型。资料导入、文本切分、向量编码、检索与生成，共同构成一条可以回查的工作流程。',
                     'citation_ids':references},
                    {'heading':'有引用，也要读懂引用',
                     'text':'向量编码帮助系统寻找语义相关的文本，并不会更新语言模型的参数。检索提供参考资料，不能保证回答正确；教师仍应检查原文是否支持结论，在证据不足时补充材料或暂缓发布。',
                     'citation_ids':references},
                ]
            elif material == 'quiz':
                asset['title'] = '切分与检索：三个关键判断'
                questions = (
                    ('课程讲义中的片段过短，最可能带来什么问题？',
                     ['丢失理解概念所需的上下文','自动更新语言模型参数','保证检索结果完全正确','消除所有重复信息'],
                     '过短的片段可能把概念与例子分开，丢失必要的上下文。'),
                    ('为什么有时让相邻片段适度重叠？',
                     ['保留跨越切分边界的信息','让每个片段包含整本讲义','替代教师审核','保证只返回一个检索结果'],
                     '适度重叠有助于保留边界信息，同时需要考虑存储与重复内容的代价。'),
                    ('问题要求比较两种方法时，首先应检查检索上下文的哪一点？',
                     ['是否同时包含两种方法及其适用条件','是否只包含排名第一的片段','是否比原始文档更长','是否完全没有引用标记'],
                     '比较需要两侧的信息；只检索到一种方法不足以支持完整比较。'),
                )
                for question, (stem, options, explanation) in zip(asset['questions'], questions):
                    question.update(stem=stem, options=options, answer='A', explanation=explanation)
                    question['difficulty_design']['concepts'] = ['文本切分', '检索上下文']
            else:
                asset['title'] = '引用是否支持结论？一次证据核对练习'
                questions = (
                    ('资料说“检索提供参考资料”，回答却写“检索保证答案正确”。指出问题并给出一版有依据的改写。',
                     '“保证答案正确”超出了来源的支持范围。可改为：检索提供参考资料，回答仍需核对。',
                     '先比较回答与原文，再去除原文未支持的保证性结论。'),
                    ('一份测验带有引用标记，但部分参考答案无法从原文推出。教师在发布前应如何处理？请说明两项具体行动。',
                     '打开原文核对参考答案与限定条件；对证据不足的题目补充资料、修订问题或暂缓发布。',
                     '引用关系本身不能证明答案成立，审核需要实际检查来源支持和题目可回答性。'),
                )
                for question, (stem, answer, explanation) in zip(asset['questions'], questions):
                    question.update(kind='short_answer', stem=stem, options=[], answer=answer, explanation=explanation)
                    question['difficulty_design']['concepts'] = ['引用支持', '教师审核']
            payload['choices'][0]['message']['content'] = json.dumps(asset, ensure_ascii=False)
            return httpx.Response(200, json=payload)

    settings = Settings(
        data_dir=Path(mkdtemp(prefix='fyp-design-quality-')),
        auth_cookie_name='fyp_design_quality_session',
        exploration_enabled=False,
        document_auto_index=False,
    )
    for capability, path in [('text','/chat/completions'), ('embedding','/embeddings'),
                             ('speech','/audio/speech'), ('image','/images/generations')]:
        setattr(settings, capability, Endpoint('https://test.invalid/v1','test-key-not-real','fixture-model',path))
    wire = DesignWire()
    providers = lambda config, store: ApiProviders(
        config, store, httpx.AsyncClient(transport=httpx.MockTransport(wire)))
    documents = []
    contents = {}
    with TestClient(create_app(settings, providers)) as client:
        helpers['authenticate'](client, email=EMAIL, password=PASSWORD)
        response = client.post('/api/courses', json={'name':COURSE_NAME})
        assert response.status_code == 201, response.text
        course = response.json()['id']
        for filename, source in DOCUMENTS:
            response = client.post('/api/documents', data={'course_id':course},
                                   files={'file':(filename,source.encode('utf-8'))})
            assert response.status_code == 201, response.text
            document = response.json()['id']
            job = helpers['done'](client, client.post('/api/documents/'+document+'/index'))
            assert job['status'] == 'succeeded', job
            documents.append(document)
        for index, (material, topic, count, kind, approved) in enumerate((
            ('lesson','RAG 的基础流程与引用边界',1,'mcq',True),
            ('quiz','文本切分与检索上下文',3,'mcq',False),
            ('assignment','引用支持与教师审核',2,'short_answer',False),
        )):
            request = helpers['request'](course, 'design-quality-'+material) | {
                'topic':topic, 'material':material, 'count':count, 'question_type':kind,
                'document_ids':[documents[index]], 'include_explanations':material == 'lesson',
                'difficulty':'medium', 'language':'zh', 'use_subagents':False,
            }
            job = helpers['done'](client, client.post('/api/generations', json=request))
            assert job['status'] == 'succeeded', job
            content = job['result']['content_id']
            contents[material] = content
            if approved:
                response = client.post('/api/contents/'+content+'/review', json={'version':1,'action':'approve'})
                assert response.status_code == 200, response.text

    app = create_app(settings, providers)
    app.title = 'Lumori · isolated design quality fixture'

    @app.get('/__ui/design-quality-state', include_in_schema=False)
    async def fixture_state():
        store = app.state.store
        return {
            'fixture':True, 'evidence':EVIDENCE_NOTE, 'network':'MockTransport only',
            'account':EMAIL, 'course_id':course, 'course_name':COURSE_NAME,
            'document_ids':documents, 'contents':contents,
            'counts':{table:store.one('SELECT COUNT(*) AS n FROM '+table)['n']
                      for table in ('courses','documents','contents')},
            'mock_provider_calls':wire.calls,
        }

    return app


if __name__ == '__main__':
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    uvicorn.run(create_fixture(), host='127.0.0.1', port=parser.parse_args().port)
