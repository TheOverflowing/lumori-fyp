"""Read-only, exhaustive checks for the frozen four-case diagnostic.

Uses only Python's standard library. No provider calls or generated artifacts.
This verifies explicit answers and numeric claims, not difficulty labels.
"""

from fractions import Fraction
from functools import lru_cache
import hashlib
import itertools
import json
from pathlib import Path
import re


DATASET = Path(__file__).with_name('solver_holdout_20260926_v2.json')
FROZEN_SHA256 = '9490963e03c0f65542ce24df0988318f1ee004ba78214e9a4c9c8acd64154bed'


def exact_reference(case, answer, explanation):
    """Full-string equality also covers every numeric token in both references."""
    assert case['reference_answer'] == answer, (case['id'], 'answer differs from oracle rendering')
    assert case['reference_explanation'] == explanation, (case['id'], 'explanation differs from oracle rendering')
    for key, expected in [('reference_answer', answer), ('reference_explanation', explanation)]:
        assert re.findall(r'\d+', case[key]) == re.findall(r'\d+', expected)


def glyph_check(case):
    source = next(s['text'] for s in case['sources'] if s['id'] == 'glyph_complete_table')
    table = {name: int(code) for name, code in re.findall(r'([^；。\s]+)→(\d+)', source)}
    target = re.search(r'标注“([^”]+)”', case['student_visible_text']).group(1)
    code = table[target]
    exact_reference(case,
        f'{code}；表项是“{target}→{code}”。',
        f'查码表直接给出“{target}→{code}”，题目要求的代码就是{code}；不需要从其他表项计算。')
    return {'reference_correct': True, 'lookup': target, 'code': code}


def pair_text(pairs):
    return '、'.join(f'({a},{b})' for a, b in pairs)


def probability_check(case):
    draw = next(s['text'] for s in case['sources'] if s['id'] == 'token_draw_rule')
    signal = next(s['text'] for s in case['sources'] if s['id'] == 'token_signal_rule')
    labels = tuple(map(int, re.search(r'标为([\d、]+)的', draw).group(1).split('、')))
    threshold = int(re.search(r'大于(\d+)', signal).group(1))
    assert '不放回' in draw and '奇数' in signal and len(labels) == len(set(labels))
    outcomes = list(itertools.permutations(labels, 2))
    conditional = [(a, b) for a, b in outcomes if (a + b) % 2 == 1]
    good = [(a, b) for a, b in conditional if a * b > threshold]
    bad = [(a, b) for a, b in conditional if a * b <= threshold]
    probability = Fraction(len(good), len(conditional))
    fraction = f'{probability.numerator}/{probability.denominator}'
    assert len(bad) == 2 and len({a * b for a, b in bad}) == 1
    bad_product = bad[0][0] * bad[0][1]
    n, total, numerator = len(conditional), len(outcomes), len(good)
    exact_reference(case,
        f'条件概率为{fraction}。亮灯后的条件样本共有{n}个有序结果，其中乘积大于{threshold}的有{numerator}个，'
        f'所以{numerator}/{n}={fraction}；不满足的结果恰为{pair_text(bad)}。',
        f'原抽取共有{total}个等可能有序结果。亮灯条件下只保留{pair_text(conditional)}，共{n}个，'
        f'它们条件下仍等可能。两个不满足结果的乘积均为{bad_product}，其余{numerator}个的乘积大于{threshold}；'
        f'因此分母为{n}而非{total}，概率为{numerator}/{n}={fraction}。')
    return {'reference_correct': True, 'initial_outcomes': total,
            'condition_outcomes': n, 'favourable_outcomes': numerator,
            'probability': fraction, 'counterexamples': bad}


def identification_check(case):
    source = next(s['text'] for s in case['sources'] if s['id'] == 'pair_game_objects')
    labels = tuple(re.search(r'恰为([^，]+)之一', source).group(1).split('、'))
    assert labels == tuple('ABCDEFGH')
    rule = next(s['text'] for s in case['sources'] if s['id'] == 'pair_query_rule')
    assert '恰好两个不同对象名' in rule and '允许再次使用已排除' in rule
    queries = tuple(itertools.combinations(labels, 2))
    query_masks = tuple(sum(1 << labels.index(x) for x in query) for query in queries)
    full_mask = (1 << len(labels)) - 1

    @lru_cache(None)
    def optimal_worst_depth(mask):
        if mask.bit_count() <= 1:
            return 0
        alternatives = []
        for query in query_masks:
            yes, no = mask & query, mask & ~query
            if yes and no:  # A non-informative query cannot improve a finite minimum.
                alternatives.append(1 + max(optimal_worst_depth(yes), optimal_worst_depth(no)))
        assert alternatives
        return min(alternatives)

    minimum = optimal_worst_depth(full_mask)
    # Verify every nonempty candidate state, not just the states on one policy.
    depth_by_state = {mask: optimal_worst_depth(mask) for mask in range(1, full_mask + 1)}
    assert len(depth_by_state) == 255
    reference_traces = {}
    for hidden in labels:
        remaining = set(labels)
        transcript = []

        def ask(query):
            nonlocal remaining
            assert len(query) == 2 and len(set(query)) == 2 and set(query) <= set(labels)
            answer = hidden in query
            remaining = remaining & set(query) if answer else remaining - set(query)
            assert hidden in remaining
            transcript.append((query, answer))
            return answer

        # Exact branch strategy printed in the reference answer.
        if ask(('A', 'B')):
            identified = 'A' if ask(('A', 'C')) else 'B'
        elif ask(('C', 'D')):
            identified = 'C' if ask(('C', 'A')) else 'D'
        elif ask(('E', 'F')):
            identified = 'E' if ask(('E', 'A')) else 'F'
        else:
            identified = 'G' if ask(('G', 'A')) else 'H'
        assert identified == hidden and remaining == {hidden}
        reference_traces[hidden] = len(transcript)
    assert max(reference_traces.values()) == minimum

    proposed_smaller_depth = minimum - 1
    survivors = [len(set(labels) - set(itertools.chain.from_iterable(sequence)))
                 for sequence in itertools.product(queries, repeat=proposed_smaller_depth)]
    # Every all-no path of this depth remains possible and has multiple candidates.
    assert min(survivors) == 2
    max_removed = 2 * proposed_smaller_depth
    assert len(labels) - max_removed == min(survivors)
    exact_reference(case,
        f'最少的最坏询问次数是{minimum}。先问{{A,B}}：若是，再问{{A,C}}，是则A，否则B。'
        '若首次为否，再问{C,D}：若是，再问{C,A}，是则C，否则D；若否，再问{E,F}：'
        f'若是，再问{{E,A}}，是则E，否则F；若否，再问{{G,A}}，是则G，否则H。各终点都唯一，最多询问{minimum}次。',
        '每次恰好询问两个不同名字，已排除的名字仍可使用：首次回答是时C已排除，首次回答否时A已排除，'
        f'所以后续分支中的补充名字合法且不会引入额外候选。要证明至少{minimum}次，考虑连续{proposed_smaller_depth}次都回答否的分支：'
        f'每次否最多排除2个对象，{proposed_smaller_depth}次最多排除{max_removed}个，初始{len(labels)}个中仍至少剩{min(survivors)}个；'
        f'这一分支与至少一个真实隐藏对象相容，尚不能停止。给出的策略在每个隐藏对象上都正确，最坏为{minimum}次，故达到下界。')
    return {'reference_correct': True, 'candidate_states_checked': len(depth_by_state),
            'queries_available': len(queries), 'all_no_sequences_checked': len(survivors),
            'optimal_worst_queries': minimum, 'reference_queries_by_hidden_object': reference_traces,
            'minimum_survivors_after_three_no_answers': min(survivors)}


def exchange_check(case):
    rule = next(s['text'] for s in case['sources'] if s['id'] == 'crystal_exchange_rule')
    initial = next(s['text'] for s in case['sources'] if s['id'] == 'crystal_initial_state')
    bundle = int(re.search(r'每凑满(\d+)枚', rule).group(1))
    starting = int(re.search(r'只有(\d+)枚', initial).group(1))
    assert '未满一组的余筹码只能保留，不能兑换' in rule
    quotient, remainder = divmod(starting, bundle)
    feasible = [n for n in range(starting + 1) if n * bundle <= starting]
    assert max(feasible) == quotient and 0 < remainder < bundle
    erroneous_extra = 1
    erroneous_total = quotient + erroneous_extra
    assert erroneous_total * bundle > starting
    # This deliberately wrong key is fixed before review. Verify the exact defect,
    # not merely an expectation label: it spends more tokens than exist.
    exact_reference(case,
        f'最多{erroneous_total}枚水晶；{starting}枚筹码拆成{quotient}组，每组{bundle}枚，余下{remainder}枚；'
        f'余筹码再换{erroneous_extra}枚水晶。',
        f'{starting}={quotient}×{bundle}+{remainder}。完整组可换{quotient}枚水晶；虽然余下{remainder}枚不足一组，'
        f'也额外计{erroneous_extra}枚，所以共{erroneous_total}枚。')
    return {'reference_correct': False, 'question_answerable': True,
            'correct_maximum': quotient, 'remainder': remainder,
            'claimed_maximum': erroneous_total, 'claimed_result_requires_tokens': erroneous_total * bundle,
            'available_tokens': starting, 'defect': 'An incomplete remainder cannot buy an extra crystal.'}


def main():
    payload = DATASET.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    assert digest == FROZEN_SHA256, 'Frozen dataset bytes changed; create a new version.'
    data = json.loads(payload)
    cases = {case['id']: case for case in data['cases']}
    assert len(cases) == 4 and all(c['split'] == 'heldout' for c in cases.values())
    assert all(c['label_provenance'] == 'AI_authored_development_expectation_not_human_gold'
               for c in cases.values())
    checks = {
        'glyph_table_lookup_v2': glyph_check,
        'odd_sum_conditional_draw_v2': probability_check,
        'adaptive_pair_identification_v2': identification_check,
        'whole_bundle_wrong_key_v2': exchange_check,
    }
    assert set(checks) == set(cases)
    results = {identity: function(cases[identity]) for identity, function in checks.items()}
    for identity, result in results.items():
        expected = cases[identity]['expected']
        assert expected['eligibility'] == 'eligible'
        assert expected['content_status'] == ('pass' if result['reference_correct'] else 'fail')
    print(json.dumps({'status': 'oracle_checks_passed', 'dataset_sha256': digest,
                      'case_count': len(cases), 'provider_calls': 0,
                      'difficulty_labels_validated': False, 'cases': results},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
