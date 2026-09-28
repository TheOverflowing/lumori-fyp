"""Render a standalone, exploratory paired-difference research figure."""
import argparse
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(run, metric='budget_hit'):
    rows = json.loads((run / 'test-per-query.json').read_text())
    selected = json.loads((run / 'selection-lock.json').read_text())['selected_arm']
    baseline = {(r['query_id'], r['mode']): r for r in rows if r['arm'] == 'baseline'}
    arms = list(dict.fromkeys(r['arm'] for r in rows if r['arm'] != 'baseline'))
    means, lower, upper = [], [], []
    for arm in arms:
        families = defaultdict(list)
        for r in rows:
            if r['arm'] == arm:
                families[r['family_id']].append(r[metric] - baseline[(r['query_id'], r['mode'])][metric])
        values = np.array([np.mean(v) for _, v in sorted(families.items())])
        rng = np.random.default_rng(20260912)
        samples = rng.choice(values, (2000, len(values)), replace=True).mean(axis=1) * 100
        lo, hi = np.percentile(samples, [2.5, 97.5])
        means.append(values.mean() * 100); lower.append(lo); upper.append(hi)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(figsize=(9.0, 7.2))
    y = np.arange(len(arms))
    for i, arm in enumerate(arms):
        color = '#0369a1' if arm == selected else '#64748b'
        ax.plot([lower[i], upper[i]], [i, i], color=color, linewidth=2)
        ax.plot(means[i], i, 'o', color=color, markersize=7 if arm == selected else 5)
    ax.axvline(0, color='#9ca3af', linestyle='--', linewidth=1)
    ax.set_yticks(y, [arm + (' *' if arm == selected else '') for arm in arms])
    ax.invert_yaxis()
    ax.set_xlabel('Difference in known-answer-span Hit (percentage points)' if metric == 'budget_hit'
                  else 'Difference in MRR@5 (x 100)')
    ax.set_title('R4 held-out evaluation: difference from the original dense baseline', loc='left', pad=15)
    ax.grid(axis='x', alpha=.16)
    fig.text(.02, .055, '84 queries / 42 bilingual families; mixed + forced cross-language retrieval.\n'
             'Budget: 1,024 Qwen tokenizer tokens of source text. Bars: paired family bootstrap 95% intervals.\n'
             '* Selected on dev before held-out evaluation. Exploratory intervals; no multiple-comparison correction.\n'
             'Source: public MLQA CS-related Wikipedia slice; not course-specific evidence annotations.', fontsize=8, color='#475569')
    fig.tight_layout(rect=(0, .16, 1, 1))
    name = 'paired-hit-differences' if metric == 'budget_hit' else 'paired-mrr5-differences'
    for extension in ('png', 'pdf'):
        fig.savefig(run / (name + '.' + extension), dpi=200, bbox_inches='tight')
    print(run / (name + '.png'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--metric', choices=('budget_hit', 'mrr5'), default='budget_hit')
    args = parser.parse_args()
    main(args.run, args.metric)
