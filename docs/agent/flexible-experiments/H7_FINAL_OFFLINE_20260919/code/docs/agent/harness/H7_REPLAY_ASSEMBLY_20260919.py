"""Replay only H7B material grouping locally; no generation or publication."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from app.assessment_assembly import assemble_question_sections
from app.models import GenerateRequest, LearningAsset
from app.pipeline import validate_asset


def main():
    source = ROOT / 'docs/agent/flexible-experiments/H7B_20260919/supervisor_v2__humanities_en.json'
    raw = source.read_bytes()
    data = json.loads(raw)
    slots = data['evidence']['agent']['slots']
    pieces = [slot['accepted_asset'] for slot in slots]
    original = data['published_content']['asset']
    asset = copy.deepcopy(original)
    asset['sections'] = assemble_question_sections(pieces, language='en',
        allowed_sources_by_slot={s['slot_id']: s['worker']['source_ids'] for s in slots})
    asset['section_scope'] = 'per_question'
    asset = LearningAsset.model_validate(asset)
    # Evidence intentionally omits request_key. This validation-only value is
    # never submitted to a job store, network or provider.
    request = GenerateRequest.model_validate(data['evidence']['request'] | {'request_key': 'offline-assembly-replay'})
    validate_asset(asset, request, data['evidence']['sources'], enforce_difficulty=True)
    assert asset.model_dump()['questions'] == original['questions']
    assert len(asset.sections) == 2
    assert all(section['text'] in bundle.text and section['heading'] in bundle.text
               for piece, bundle in zip(pieces, asset.sections) for section in piece['sections'])
    output = ROOT / 'docs/agent/harness/H7B_ASSEMBLY_REPLAY_20260919.json'
    output.write_text(json.dumps({
        'kind': 'offline_assembly_replay', 'actual_api_calls': 0,
        'source_archive': str(source.relative_to(ROOT)),
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'workspace_revision': 'assessment-contracts-v4-20260919',
        'preserved_questions': 2, 'preserved_original_sections': 4, 'material_bundles': 2,
        'validation': 'Question fields unchanged; all original section headings/text retained in the correct question bundle; asset citation and difficulty structure validated.',
        'limitations': 'Grouping corrects cross-question labels only. Does not repair absent clues inside q1, overlong answers, reasoning defects or learner difficulty; no model re-evaluation or publication.',
        'asset': asset.model_dump()}, ensure_ascii=False, indent=2) + '\n')
    assert source.read_bytes() == raw
    print(json.dumps({'output': str(output.relative_to(ROOT)), 'api_calls': 0,
                      'questions_unchanged': 2, 'original_sections_preserved': 4}))


if __name__ == '__main__':
    main()
