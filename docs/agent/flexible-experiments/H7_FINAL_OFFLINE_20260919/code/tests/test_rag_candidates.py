import pytest
from app.rag_candidates import token_chunks, assemble_context, query_input, title_input


class Characters:
    def count(self, value):
        return len(value)


def leaf(pid, text, a, b):
    return {'id': f'{pid}:{a}:{b}', 'parent_id': pid, 'text': text[a:b], 'source_start': a, 'source_end': b}


@pytest.mark.parametrize('text', [
    '# 树\n\n二叉搜索树的左子树键值较小。查找复杂度受树高影响。' * 5,
    'An invariant must hold. This proof includes a loop.\n\nAnother paragraph. ' * 5,
    '# Code\n\n```python\ndef f(x):\n    return x + 1\n```\n\nExplanation. ' * 3,
    'x' * 199, '算法😀' * 99,
])
def test_token_slices_preserve_source_without_overlap(text):
    chunks = token_chunks({'id': 'p', 'text': text}, Characters(), 32)
    seen = set()
    for c in chunks:
        a, b = c['source_start'], c['source_end']
        assert c['text'] == text[a:b]
        assert len(c['text']) <= 32
        assert not seen.intersection(range(a, b))
        seen.update(range(a, b))
    assert all(i in seen for i, ch in enumerate(text) if not ch.isspace())


def test_context_merges_overlap_counts_final_serialization():
    text = 'abcdefghijklmnopqrstuvwxyz'
    selected, used = assemble_context([leaf('p', text, 0, 12), leaf('p', text, 8, 18)],
                                       {'p': {'text': text}}, Characters(), budget=18)
    assert used == 18
    assert selected[0]['text'] == text[:18]
    assert len(selected) == 1


def test_expansion_keeps_other_hits_and_falls_back():
    parents = {'p': {'text': 'a' * 50}, 'q': {'text': 'b' * 50}}
    hits = [leaf('p', parents['p']['text'], 0, 10), leaf('q', parents['q']['text'], 0, 10)]
    result, count = assemble_context(hits, parents, Characters(), budget=22, expansion='parent')
    assert count == 22 and len(result) == 2
    assert {r['parent_id'] for r in result} == {'p', 'q'}


def test_parent_expands_only_within_section_and_uses_original_text():
    text = '# First\n123456789\n# Second\nabcdefgh'
    c = leaf('p', text, 9, 13)
    result, count = assemble_context([c], {'p': {'text': text}}, Characters(), 100, 'parent')
    assert result[0]['text'] == text[:text.index('# Second')]
    assert 'Second' not in result[0]['text']


def test_title_and_query_formats_are_separate_from_sources():
    assert title_input('body', 'Course', ['Course', 'Section']) == 'Course > Section\nbody'
    assert query_input('问题') == '问题'
    assert query_input('问题', True).endswith('\nQuery: 问题')


def test_invalid_limits():
    with pytest.raises(ValueError):
        token_chunks({'id': 'p', 'text': 'hello'}, Characters(), 0)
    with pytest.raises(ValueError):
        assemble_context([], {}, Characters(), -1)


def test_choose_is_quality_first_and_prefers_no_reranker_on_tie():
    from scripts.r4_experiment import choose
    a = dict(group='all', budget_hit=0.9, mrr5=0.8, context_tokens=300)
    assert choose([dict(a, arm='baseline'), dict(a, arm='rerank_none')]) == 'baseline'
    assert choose([dict(a, arm='baseline'), dict(a, arm='title', budget_hit=0.95)]) == 'title'


def test_heldout_family_and_context_disjoint():
    from scripts.r4_experiment import build_dataset
    from scripts.chunk_experiment import gold_spans
    ds, decisions = build_dataset()
    gold_spans(ds)
    by_split = {s: [q for q in ds['queries'] if q['split'] == s] for s in ('dev', 'test')}
    assert len(by_split['dev']) == 92 and len(by_split['test']) == 84
    assert not {q['family_id'] for q in by_split['dev']} & {q['family_id'] for q in by_split['test']}
    assert not {q['original_context_id'] for q in by_split['dev']} & {q['original_context_id'] for q in by_split['test']}
