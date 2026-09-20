"""Frozen-context prompt contracts, without providers or API credentials."""
import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.difficulty import DIFFICULTY_RUBRIC, RUBRIC_VERSION, validate_difficulty_design
from app.models import LearningAsset
from scripts.difficulty_prompts import (
    BASELINE_SYSTEM, DifficultyJudgeResult, PROMPT_VERSION, STRATEGIES,
    build_generation_messages, build_judge_messages, make_request,
)


@pytest.fixture
def case():
    return {
        'id': 'PRIVATE_CASE_ID', 'topic_id': 'PRIVATE_TOPIC_ID',
        'split': 'development', 'pilot': True, 'language': 'en',
        'target_difficulty': 'hard', 'question_type': 'short_answer',
        'topic': 'PRIVATE_AUTHOR_TOPIC',
        'learner_profile': 'CS undergraduates who know linear and binary search.',
        'sources': [{
            'id': 's1', 'text': 'Binary search requires sorted input; linear search does not.',
            'document_name': 'PRIVATE_SOURCE_NAME', 'page': 1,
            'url': 'https://fixture.invalid/PRIVATE_SOURCE_URL',
        }],
        'provenance': {'note': 'PRIVATE_PROVENANCE'},
    }


@pytest.fixture
def asset():
    return {
        'title': 'PRIVATE_TITLE', 'evidence_sufficient': True,
        'learning_objectives': ['PRIVATE_OBJECTIVE'],
        'sections': [{'heading': 'PRIVATE_HEADING', 'text': 'PRIVATE_SECTION', 'citation_ids': ['s1']}],
        'questions': [{
            'slot_id': 'q1', 'difficulty': 'hard', 'kind': 'short_answer',
            'stem': 'Choose a search method for unsorted input that cannot be reordered and justify it.',
            'options': [], 'answer': 'Use linear search.',
            'explanation': 'Binary search requires sorted input.',
            'difficulty_reason': 'PRIVATE_AUTHOR_REASON', 'citation_ids': ['s1'],
            'difficulty_design': {
                'cognitive_process': 'evaluate', 'concepts': ['PRIVATE_AUTHOR_CONCEPT'],
                'expected_steps': ['PRIVATE_STEP_1', 'PRIVATE_STEP_2', 'PRIVATE_STEP_3'],
            },
        }],
        'visual_prompt': 'PRIVATE_VISUAL_PROMPT',
    }


def contract(messages):
    assert [message['role'] for message in messages] == ['system', 'user']
    return json.loads(messages[1]['content'])


def test_baseline_is_current_production_system_and_schema(case):
    # Compare against the actual literal, not a second copy of the prompt in tests.
    tree = ast.parse((Path(__file__).parents[1] / 'app/pipeline.py').read_text())
    generate = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.AsyncFunctionDef) and node.name == 'generate')
    literal = next(node.value.value for node in ast.walk(generate)
                   if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                   and any(isinstance(target, ast.Name) and target.id == 'system' for target in node.targets))
    messages = build_generation_messages(case, 'baseline')
    assert messages[0]['content'] == literal == BASELINE_SYSTEM
    data = contract(messages)
    assert data['rubric'] == DIFFICULTY_RUBRIC
    assert data['rubric_version'] == RUBRIC_VERSION
    assert data['difficulty_plan'] == [{'slot_id': 'q1', 'difficulty': 'hard'}]
    assert data['question_count'] == data['schema']['properties']['questions']['maxItems'] == 1
    required = data['schema']['$defs']['Question']['required']
    for field in ('slot_id', 'difficulty', 'difficulty_design'):
        assert field in required
        assert 'anyOf' not in data['schema']['$defs']['Question']['properties'][field]
    assert '冻结资料' in STRATEGIES['baseline']['note']
    assert '单次调用' in STRATEGIES['baseline']['note']


@pytest.mark.parametrize('language', ['zh', 'en'])
@pytest.mark.parametrize('question_type', ['mcq', 'short_answer'])
@pytest.mark.parametrize('level', ['easy', 'medium', 'hard'])
def test_all_candidates_change_only_system_suffix(case, language, question_type, level):
    case.update(language=language, question_type=question_type, target_difficulty=level)
    before = deepcopy(case)
    baseline = build_generation_messages(case, 'baseline')
    expected = contract(baseline)
    assert len(STRATEGIES) == 6
    for strategy, metadata in STRATEGIES.items():
        messages = build_generation_messages(case, strategy)
        assert messages[1] == baseline[1]
        assert messages[0]['content'].startswith(BASELINE_SYSTEM)
        assert set(metadata) == {'label', 'family', 'reference_urls', 'note'}
        assert contract(messages) == expected
    request = make_request(case)
    assert (request.language, request.question_type, request.difficulty) == (language, question_type, level)
    assert request.count == 1 and request.material == 'quiz'
    assert request.course_id == 'difficulty-experiment'
    assert expected['reference_chunks'] == [case['sources'][0] | {'heading_path': []}]
    assert 'request_key' not in expected['request']
    assert case == before


def test_generation_schema_references_resolve_and_match_model(case, asset):
    schema = contract(build_generation_messages(case, 'baseline'))['schema']

    def check(value):
        if isinstance(value, dict):
            if '$ref' in value:
                ref = value['$ref']
                assert ref.startswith('#/$defs/')
                assert ref.removeprefix('#/$defs/') in schema['$defs']
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    check(schema)
    validated = LearningAsset.model_validate(asset)
    validate_difficulty_design(validated, make_request(case))
    for name, definition in LearningAsset.model_json_schema()['$defs'].items():
        if name != 'Question':
            assert schema['$defs'][name] == definition


def test_v2_shared_schema_exposes_existing_cross_field_requirements(case, asset):
    assert PROMPT_VERSION == 'difficulty-experiment-v2'
    data = contract(build_generation_messages(case, 'baseline'))
    conditional, = data['schema']['allOf']
    assert conditional['if'] == {'properties': {'evidence_sufficient': {'const': True}},
                                  'required': ['evidence_sufficient']}
    assert set(conditional['then']['required']) == {'sections', 'questions'}
    assert conditional['then']['properties'] == {
        'sections': {'minItems': 1}, 'questions': {'minItems': 1, 'maxItems': 1}}
    assert conditional['else']['properties'] == {
        'sections': {'maxItems': 0}, 'questions': {'maxItems': 0}}
    assert '至少一段学习讲解' in data['output_contract']['evidence_sufficient_true']
    assert '为空数组' in data['output_contract']['evidence_sufficient_false']

    # The historical experimental prompt still requires context. The production
    # data model now also represents explicitly requested questions-only assets;
    # its request-specific contract is enforced by validate_asset.
    assert LearningAsset.model_validate(asset).evidence_sufficient is True
    assert LearningAsset.model_validate(asset | {'sections': []}).questions
    with pytest.raises(ValidationError, match='材料必须包含学习讲解或题目'):
        LearningAsset.model_validate(asset | {'sections': [], 'questions': []})
    refused = asset | {'evidence_sufficient': False, 'sections': [], 'questions': []}
    assert LearningAsset.model_validate(refused).evidence_sufficient is False
    for field in ('sections', 'questions'):
        with pytest.raises(ValidationError, match='证据不足时不得返回教学结论或题目'):
            LearningAsset.model_validate(refused | {field: asset[field]})


def test_judge_uses_allowlist_without_targets_or_author_metadata(case, asset):
    before = deepcopy((case, asset))
    messages = build_judge_messages(case, asset)
    data = contract(messages)
    serialized = json.dumps(messages, ensure_ascii=False)
    assert 'PRIVATE_' not in serialized
    assert set(data) == {'learner_profile', 'rubric_version', 'rubric', 'rubric_note',
                         'question', 'reference_chunks', 'schema'}
    assert set(data['question']) == {'stem', 'options', 'answer', 'explanation'}
    assert data['reference_chunks'] == [{'id': 's1', 'text': case['sources'][0]['text']}]
    assert data['learner_profile'] == case['learner_profile']
    assert data['rubric'] == DIFFICULTY_RUBRIC
    assert messages == build_judge_messages(case, LearningAsset.model_validate(asset))
    assert (case, asset) == before


def test_judge_is_invariant_to_case_target_strategy_and_author_design(case, asset):
    original = build_judge_messages(case, asset)
    case.update(id='changed', topic_id='changed', topic='changed topic',
                target_difficulty='easy', strategy='contrastive', split='holdout')
    asset['questions'][0].update(difficulty='easy', difficulty_reason='changed author reason',
                                  difficulty_design={'anything': 'changed'}, slot_id='q99')
    asset.update(title='changed title', sections=[], learning_objectives=['changed'])
    assert build_judge_messages(case, asset) == original


def test_judge_schema_allows_uncertainty_and_enforces_boolean_quality():
    result = dict(assessed_difficulty='uncertain', correctness=False, grounded=False,
                  answerable=False, ambiguity_free=False,
                  rationale='The source does not specify the necessary assumptions.', confidence='low')
    assert DifficultyJudgeResult.model_validate(result).assessed_difficulty == 'uncertain'
    for field in ('correctness', 'grounded', 'answerable', 'ambiguity_free'):
        with pytest.raises(ValidationError):
            DifficultyJudgeResult.model_validate(result | {field: 'false'})
    with pytest.raises(ValidationError):
        DifficultyJudgeResult.model_validate(result | {'target_difficulty': 'hard'})
    with pytest.raises(ValidationError):
        DifficultyJudgeResult.model_validate(result | {'rationale': ' '})


@pytest.mark.parametrize('count', [0, 2])
def test_judge_does_not_silently_select_from_invalid_question_count(case, asset, count):
    asset['questions'] *= count
    with pytest.raises(ValueError, match='exactly one'):
        build_judge_messages(case, asset)


@pytest.mark.parametrize('sources', [[], [{'id': '', 'text': 'content'}],
                                   [{'id': 's1', 'text': 'content'}, {'id': 's1', 'text': 'other'}]])
def test_invalid_frozen_sources_are_rejected(case, asset, sources):
    case['sources'] = sources
    with pytest.raises(ValueError):
        build_generation_messages(case, 'baseline')
    with pytest.raises(ValueError):
        build_judge_messages(case, asset)


def test_unknown_strategy_is_not_silently_replaced(case):
    with pytest.raises(ValueError, match='Unknown difficulty strategy'):
        build_generation_messages(case, 'typo')


def test_strategy_provenance_does_not_claim_paper_replication_or_calibration():
    for strategy in ('backward_design', 'contrastive', 'verify_before_emit'):
        assert STRATEGIES[strategy]['reference_urls']
        assert '不是' in STRATEGIES[strategy]['note']
        assert '论文复现' in STRATEGIES[strategy]['note']
    assert '未经人工校准' in STRATEGIES['contrastive']['note']
    assert '同一次生成内自检' in STRATEGIES['verify_before_emit']['note']
