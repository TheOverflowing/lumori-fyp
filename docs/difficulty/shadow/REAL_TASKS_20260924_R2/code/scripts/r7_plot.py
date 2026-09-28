"""Create publication figures from a frozen R7 decision.json; no API calls.

Usage: PYTHONPATH=/tmp/lumori-r7-plot-deps .venv/bin/python scripts/r7_plot.py --run RUN

Read panels A-C from L0 (canonical wording) to L3 (strong but recoverable
paraphrase). Colors identify the same four query policies in every panel.
A/B describe candidate ranking before shared reranking; C describes final
budgeted evidence, so candidate improvements need not raise C. Panel D keeps
L4 ambiguity separate: greater L4 detection is useful only together with a
low false-clarification rate on L0-L3. Original has no clarification module;
its D entry is N/A, not a measured zero-performance classifier. The figure
shows descriptive held-out point estimates, not confidence intervals,
independent user samples, or production end-to-end performance. The CSV/JSON
report supplies paired document-component uncertainty and exact counts.

The script reads only decision.json from the run and writes PNG/PDF/SVG.
It does not recompute metrics, alter the frozen run inputs, or access a model.
"""
import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

ARMS = ('original', 'conservative', 'normalize', 'dual')
LABELS = {'original': 'Original', 'conservative': 'Conservative rewrite',
          'normalize': 'Terminology normalization', 'dual': 'Original + normalization'}
SHORT = {'original': 'Original', 'conservative': 'Conservative', 'normalize': 'Normalization', 'dual': 'Dual'}
COLORS = {'original': '#60656F', 'conservative': '#0072B2', 'normalize': '#D55E00', 'dual': '#009E73'}
MARKERS = {'original': 's', 'conservative': 'o', 'normalize': '^', 'dual': 'D'}
LEVELS = ('L0', 'L1', 'L2', 'L3')


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Missing or invalid probability: ' + label)
    return float(value)


def plot(run):
    run = Path(run)
    data = json.loads((run / 'decision.json').read_text(encoding='utf-8'))
    rows = [r for r in data['summaries']['test'] if r['language'] == 'all' and r['level'] in LEVELS]
    indexed = {(r['arm'], r['level']): r for r in rows}
    if len(indexed) != len(rows) or set(indexed) != {(a, level) for a in ARMS for level in LEVELS}:
        raise ValueError('A complete, unique four-arm by four-level test grid is required')
    counts = {r['quality_rows'] for r in rows}
    if len(counts) != 1 or next(iter(counts)) != 16:
        raise ValueError('This R7 publication figure expects 16 held-out bilingual queries per level')
    components = data['source_component_counts']['test']
    if components != 6:
        raise ValueError('This R7 publication figure expects six held-out document components')
    gates = [r for r in data['clarification']['test'] if r['language'] == 'all']
    gate_index = {r['arm']: r for r in gates}
    if len(gates) != 4 or set(gate_index) != set(ARMS):
        raise ValueError('Four clarification diagnostics are required')
    if gate_index['original'].get('module_status') != 'not_implemented':
        raise ValueError('Original clarification-module status changed; update the figure labels')
    if any(gate_index[a]['ambiguous'] != 16 or gate_index[a]['unambiguous'] != 64 for a in ARMS):
        raise ValueError('Unexpected ambiguity denominators')

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 11.5,
                         'axes.labelsize': 10, 'xtick.labelsize': 9, 'ytick.labelsize': 9,
                         'figure.facecolor': 'white', 'axes.facecolor': 'white', 'savefig.facecolor': 'white',
                         'text.color': '#20252B', 'axes.labelcolor': '#30363D', 'xtick.color': '#414852',
                         'ytick.color': '#414852', 'axes.edgecolor': '#AAB1BA',
                         'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(2, 2, figsize=(13, 9.3))
    panels = [('pre_hit5', 'A   Candidate evidence Hit@5', 'Evidence hit rate'),
              ('pre_mrr20', 'B   Candidate MRR@20', 'Mean reciprocal rank'),
              ('post_hit', 'C   Evidence within the final token budget', 'Budgeted evidence hit rate')]
    x = list(range(4))
    tick_labels = ['L0\nCanonical', 'L1\nConversational', 'L2\nEveryday terms', 'L3\nStrong paraphrase']
    for ax, (metric, title, ylabel) in zip(axes.flat, panels):
        for arm in ARMS:
            y = [number(indexed[arm, level][metric], arm + '/' + level + '/' + metric) for level in LEVELS]
            # Hollow markers retain visibility when policy curves overlap exactly.
            ax.plot(x, y, color=COLORS[arm], marker=MARKERS[arm], linewidth=1.75,
                    markersize=5.8, markerfacecolor='white', markeredgewidth=1.25,
                    label=LABELS[arm], zorder=3 + ARMS.index(arm) / 10)
        ax.set_title(title, loc='left', pad=12, fontweight='semibold')
        ax.set_xticks(x, tick_labels)
        ax.set_xlim(-.45, 3.45)
        ax.set_ylim(0, 1.065)
        ax.set_yticks([0, .2, .4, .6, .8, 1])
        if metric != 'pre_mrr20':
            ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.set_ylabel(ylabel)
        ax.grid(axis='y', color='#E3E7EB', linewidth=.7, zorder=0)
        ax.spines[['top', 'right']].set_visible(False)
        ax.tick_params(axis='both', length=3)

    ax = axes[1, 1]
    width = .31
    for pos, arm in enumerate(ARMS):
        if arm == 'original':
            ax.text(pos, .18, 'N/A\nNo clarification\nmodule', ha='center', va='center',
                    fontsize=8.6, color=COLORS[arm], linespacing=1.3)
            continue
        detection = number(gate_index[arm]['clarification_rate'], arm + '/clarification_rate')
        false_positive = number(gate_index[arm]['false_clarification_rate'], arm + '/false_clarification_rate')
        ax.bar(pos - width / 2, detection, width, color=COLORS[arm], edgecolor=COLORS[arm], linewidth=.8, zorder=3)
        ax.bar(pos + width / 2, false_positive, width, facecolor='white', edgecolor=COLORS[arm],
               hatch='////', linewidth=1.1, zorder=3)
        for offset, val in ((-width/2, detection), (width/2, false_positive)):
            label=f'{val*100:.2f}'.rstrip('0').rstrip('.')+'%'
            ax.text(pos + offset, val + .025, label, ha='center', va='bottom', fontsize=8, color='#30363D')
    ax.set_title('D   Clarification decisions: ambiguity kept separate', loc='left', pad=12, fontweight='semibold')
    ax.set_xticks(x, [SHORT[a] for a in ARMS])
    ax.set_xlim(-.6,3.55)
    ax.set_ylim(0, 1.16)
    ax.set_yticks([0, .2, .4, .6, .8, 1])
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_ylabel('Clarification request rate')
    ax.grid(axis='y', color='#E3E7EB', linewidth=.7, zorder=0)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(handles=[Patch(facecolor='#687280', edgecolor='#687280', label='L4: ambiguity detected (n = 16)'),
                       Patch(facecolor='white', edgecolor='#687280', hatch='////', label='L0–L3: false clarification (n = 64)')],
              loc='upper left', fontsize=8, frameon=False, bbox_to_anchor=(0, 1.02), borderaxespad=0)

    fig.suptitle('Query reformulation across increasing colloquiality', x=.067, y=.985,
                 ha='left', fontsize=18, fontweight='bold')
    fig.text(.067, .937, 'R7 held-out comparison · fixed retrieval budgets · descriptive point estimates',
             fontsize=10.6, color='#58616C')
    handles = [Line2D([0], [0], color=COLORS[a], marker=MARKERS[a], markersize=5.5,
                      markerfacecolor='white', linewidth=1.7, label=LABELS[a]) for a in ARMS]
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.06, .920), ncol=4,
               frameon=False, fontsize=9.4, columnspacing=2.0, handletextpad=.6)
    fig.subplots_adjust(left=.075, right=.965, top=.837, bottom=.173, hspace=.43, wspace=.25)
    notes = [
        'Held-out set: 8 question families, 16 bilingual queries per level, 6 document components from two textbooks.',
        'AI-authored variants and AI-reviewed labels; local document/topic holdout, not unseen-textbook or real-user validation.',
        'A–C exclude L4. D evaluates ambiguity separately. Point estimates only; paired component intervals are in the report.',
        'C uses one shared reranking request over the candidate union; each policy retains at most 20 candidates and a 1,024-token budget.',
        'Shared scoring is a controlled experiment, not a production request-budget or end-to-end latency measurement.'
    ]
    for index, text in enumerate(notes):
        fig.text(.075, .119 - index * .0188, text, fontsize=8.2, color='#58616C', ha='left', va='top')
    paths = []
    for extension in ('png', 'pdf', 'svg'):
        path = run / ('figure-query-severity.' + extension)
        fig.savefig(path, dpi=300, bbox_inches=None, facecolor='white')
        paths.append(str(path))
    plt.close(fig)
    return paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    for output in plot(args.run):
        print(output)
