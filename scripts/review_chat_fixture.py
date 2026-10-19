"""Isolated browser fixture for the Review conversation workflow.

Run: .venv/bin/python -m scripts.review_chat_fixture --port 8776
Account: review-chat@example.test / Fixture browser password 2026!
State: GET /__ui/review-chat-state

Every launch uses a temporary database. All provider requests use MockTransport;
the normal application routes, job workers, revision checks and persistence run.
Send “模拟失败” to exercise a provider failure without changing the material.
"""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import runpy
from tempfile import mkdtemp

from fastapi.testclient import TestClient
import httpx

from app.config import Endpoint, Settings
from app.main import create_app
from app.providers import ApiProviders


EMAIL = 'review-chat@example.test'
PASSWORD = 'Fixture browser password 2026!'
COURSE_NAME = '生成式 AI 与知识检索'
SOURCE = '''# 检索增强生成与资料核对

检索增强生成（RAG）在生成回答前，从课程资料中寻找相关片段，并将片段提供给语言模型。
检索结果为回答提供参考资料，但检索本身不能保证答案正确，也不会更新语言模型的参数。
教师应核对原文是否支持生成内容，检查引用、答案与解析是否一致。

文本切分需要保留概念与例子之间的联系。片段过短可能丢失必要上下文；相邻片段适度重叠
可以保留跨越切分边界的信息，同时会增加存储和重复内容。切分不能替代答案核对。
'''
QUESTIONS = (
    ('检索增强生成中的检索步骤，主要起什么作用？',
     ['为生成回答提供相关课程资料', '保证生成的每个答案都正确', '直接更新语言模型的参数', '代替教师审核答案'],
     '检索为生成提供相关资料，但答案仍需对照原文核对。'),
    ('切分课程讲义时，相邻片段适度重叠有什么作用？',
     ['保留跨越切分边界的上下文', '保证所有答案都正确', '让每个片段都包含整本讲义', '取消教师对答案的审核'],
     '适度重叠可以保留跨边界的信息，同时需要考虑存储和重复内容的代价。'),
)


def response(body):
    return httpx.Response(200, json={'choices': [
        {'finish_reason': 'stop', 'message': {'content': json.dumps(body, ensure_ascii=False)}}]})


def quality_fields(contract):
    properties = contract['schema'].get('properties', {})
    result = {}
    if 'question_checks' in properties:
        result['question_checks'] = {'condition_issues': [], 'option_checks': [
            {'label': chr(65 + index), 'verdict': 'correct' if index == 0 else 'incorrect',
             'reason': '该选项与给定课程资料的支持范围一致。' if index == 0 else '该选项超出了给定资料的支持范围。'}
            for index, _ in enumerate(contract['question'].get('options', []))]}
    if 'explanation_issues' in properties:
        result['explanation_issues'] = []
    return result


def create_fixture():
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_workflow.py'))

    class ReviewChatWire(helpers['Wire']):
        def __init__(self):
            self.calls = 0
            self.tasks = Counter()
            self.chat_inputs = []
            self.revision_inputs = []

        def __call__(self, request):
            assert request.url.host == 'test.invalid'
            assert request.headers['authorization'] == 'Bearer test-key-not-real'
            if not request.url.path.endswith('/chat/completions'):
                return super().__call__(request)
            contract = json.loads(json.loads(request.content)['messages'][1]['content'])
            task = contract.get('task', 'generation')
            self.tasks[task] += 1
            if task == 'review_chat':
                self.calls += 1
                return self.chat_response(contract)
            if task == 'content_ai_review':
                self.calls += 1
                sources = {source['id']: source['text'] for source in contract['sources']}
                return response({'summary': '题目、答案和解析与课程资料一致。',
                    'checks': [{'key': key, 'status': 'pass', 'rationale': '内容与给定资料一致。'}
                        for key in ('correctness', 'groundedness', 'answerability', 'clarity', 'objective_alignment')],
                    'items': [{'id': unit['id'], 'status': 'pass', 'rationale': '可以依据引用资料作答。',
                        'source_ids': unit['citation_ids'], 'evidence': [
                            {'source_id': sid, 'quote': sources[sid][:160]} for sid in unit['citation_ids']]}
                        for unit in contract['units']], 'findings': []})
            if task in ('agent_author', 'agent_solve', 'agent_review'):
                self.calls += 1
                return self.revision_response(contract)
            result = super().__call__(request)
            if task == 'difficulty_assessment':
                return result
            asset = json.loads(result.json()['choices'][0]['message']['content'])
            asset.update(title='检索与切分：两个关键判断', visual_prompt='',
                learning_objectives=['说明检索的作用与边界', '说明切分重叠的作用'])
            refs = [contract['reference_chunks'][0]['id']]
            asset['sections'] = [{'heading': '先找到资料，再核对答案',
                'text': 'RAG 先检索相关课程资料，再将资料提供给语言模型。检索提供参考，回答仍需核对；适度重叠的切分有助于保留边界上下文。',
                'citation_ids': refs}]
            for question, (stem, options, explanation) in zip(asset['questions'], QUESTIONS):
                question.update(stem=stem, options=options, answer='A', explanation=explanation)
                question['difficulty_design']['concepts'] = ['课程检索', '资料核对']
            return response(asset)

        def chat_response(self, contract):
            message = contract['message']
            self.chat_inputs.append({'message': message, 'version': contract['current_version'],
                'selected_slot_id': contract['selected_slot_id'], 'history_count': len(contract['history']),
                'stems': [question['stem'] for question in contract['asset']['questions']]})
            if '模拟失败' in message or 'simulate failure' in message.lower():
                return httpx.Response(503, text='Fixture provider unavailable')
            explicit = re.search(r'第\s*([一二12])\s*题', message)
            slot = ('q' + {'一': '1', '二': '2', '1': '1', '2': '2'}[explicit[1]]
                if explicit else contract['selected_slot_id'])
            if not slot:
                slot = next((entry.get('slot_id') for entry in reversed(contract['history'])
                    if entry.get('slot_id') and entry.get('status') == 'succeeded'), None)
            edit = any(word in message for word in ('改', '再简单', '补充', '加上', '增加', '详细一点'))
            if not edit:
                return response({'action': 'answer', 'text': 'A 对应检索的实际作用：为生成回答提供相关课程资料。其他选项把检索说成保证正确、更新模型参数或代替审核，均超出了资料支持的范围。',
                    'slot_id': slot, 'instruction': '', 'difficulty': None})
            if not slot:
                return response({'action': 'clarify', 'text': '你想修改第一题还是第二题？',
                    'slot_id': None, 'instruction': '', 'difficulty': None})
            explanation = '解析' in message or 'explanation' in message.lower()
            action = 'explanation' if explanation else 'rewrite'
            return response({'action': action, 'text': '已补充解析步骤，题干、选项和答案保持原样。' if explanation
                else '已按你的要求改写题目，并保留原来的学习目标。',
                'slot_id': slot, 'instruction': message, 'difficulty': None})

        def revision_response(self, contract):
            task = contract['task']
            if task == 'agent_author':
                revision = contract['revision']
                original = deepcopy(revision['original_question'])
                instruction = revision['instruction']
                self.revision_inputs.append({'slot_id': revision['target_slot'], 'mode': revision['mode'],
                    'instruction': instruction, 'original_stem': original['stem'],
                    'original_explanation': original['explanation']})
                if revision['mode'] == 'explanation':
                    explanation = ('第一步，定位被切分边界分开的内容。第二步，通过片段重叠保留前后文。因此选 A；重叠可以保留边界信息，但不能保证答案正确或代替教师审核。'
                        if '重叠' in original['stem'] else
                        '第一步，检索找出与问题相关的课程片段，为回答提供依据。第二步，对照原文检查答案是否成立。因此应选 A；检索不能保证正确、更新模型参数或代替教师核对。')
                    return response({'explanation': explanation})
                if '重叠' in original['stem']:
                    original['stem'] = '小林将讲义分成若干片段。让相邻片段适度重叠，可以帮助保留什么？'
                    original['explanation'] = '相邻片段的适度重叠可以保留跨越切分边界的上下文，因此选 A。'
                elif '简单' in instruction or 'simpl' in instruction.lower():
                    original['stem'] = '小林用课程助手查找讲义。检索步骤帮助他做什么？'
                    original['explanation'] = '检索帮小林找到相关讲义，作为回答的参考；答案还需要核对。'
                else:
                    original['stem'] = '小林正在准备课堂展示，课程助手先检索讲义，再生成回答。在这个场景中，检索的主要作用是什么？'
                    original['explanation'] = '课程助手检索讲义，是为了把相关资料提供给生成步骤；这些资料仍需用于核对最终答案。'
                original['slot_id'] = 'q1'
                return response({'title': '检索与切分：两个关键判断', 'evidence_sufficient': True,
                    'learning_objectives': [], 'sections': [], 'questions': [original]})
            if task == 'agent_solve':
                return response({'answerable': True, 'ambiguity_free': True,
                    'assessed_difficulty': 'medium', 'confidence': 'high', 'answer': 'A',
                    'explanation': '检索提供相关课程资料，生成的答案仍应核对。',
                    'requires_calculation': False, 'tool_requests': [], **quality_fields(contract)})
            return response({'answer_correct': True, 'explanation_correct': True, 'source_supported': True,
                'ambiguity_free': True, 'tool_inputs_match_question': True, 'calculations_verified': True,
                'distinct_from_previous': True, 'confidence': 'high', 'issues': [],
                'feedback': '题目与解析符合课程资料，改写保留了检索作用这一学习目标。',
                'revision_instructions_followed': True, 'original_learning_focus_preserved': True,
                **quality_fields(contract)})

    settings = Settings(data_dir=Path(mkdtemp(prefix='fyp-review-chat-')),
        auth_cookie_name='fyp_review_chat_session', exploration_enabled=False,
        document_auto_index=False, max_daily_calls=1000)
    for capability, path in [('text', '/chat/completions'), ('embedding', '/embeddings'),
                             ('speech', '/audio/speech'), ('image', '/images/generations')]:
        setattr(settings, capability, Endpoint('https://test.invalid/v1', 'test-key-not-real', 'fixture-model', path))
    wire = ReviewChatWire()
    providers = lambda config, store: ApiProviders(
        config, store, httpx.AsyncClient(transport=httpx.MockTransport(wire)))
    with TestClient(create_app(settings, providers)) as client:
        user = helpers['authenticate'](client, email=EMAIL, password=PASSWORD)
        created = client.post('/api/courses', json={'name': COURSE_NAME})
        assert created.status_code == 201, created.text
        course = created.json()['id']
        uploaded = client.post('/api/documents', data={'course_id': course},
            files={'file': ('检索增强生成与资料核对.md', SOURCE.encode('utf-8'))})
        assert uploaded.status_code == 201, uploaded.text
        document = uploaded.json()['id']
        indexed = helpers['done'](client, client.post('/api/documents/' + document + '/index'))
        assert indexed['status'] == 'succeeded', indexed
        generated = helpers['done'](client, client.post('/api/generations', json={
            **helpers['request'](course, 'review-chat-initial-material'),
            'topic': '检索增强生成与资料核对', 'material': 'quiz', 'count': 2,
            'document_ids': [document], 'language': 'zh', 'difficulty': 'medium',
            'use_subagents': False, 'auto_review': False}))
        assert generated['status'] == 'succeeded', generated
        content = generated['result']['content_id']

    app = create_app(settings, providers)

    @app.get('/__ui/review-chat-state', include_in_schema=False)
    async def fixture_state():
        current = app.state.store.one('SELECT version,status FROM contents WHERE id=?', (content,))
        return {'fixture': True, 'network': 'MockTransport only', 'account': EMAIL,
            'user_id': user['id'], 'course_id': course, 'course_name': COURSE_NAME,
            'document_ids': [document], 'contents': {'quiz': content}, 'content_id': content,
            'version': current['version'], 'status': current['status'],
            'mock_provider_calls': wire.calls, 'provider_tasks': dict(wire.tasks),
            'chat_inputs': deepcopy(wire.chat_inputs),
            'revision_inputs': deepcopy(wire.revision_inputs)}

    return app


if __name__ == '__main__':
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8776)
    uvicorn.run(create_fixture(), host='127.0.0.1', port=parser.parse_args().port)
