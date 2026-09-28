"""Publication figure from saved R8A metrics; no reranking or model calls.

PYTHONPATH=/tmp/lumori-r7-plot-deps MPLCONFIGDIR=/tmp/lumori-r7-matplotlib \
  .venv/bin/python scripts/r8_fusion_plot.py --run docs/rag/r8a-experiments/RUN
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ARMS = ('original', 'normalize', 'rrf60', 'vector_a030')
LABELS = {'original': 'Original', 'normalize': 'Normalization', 'rrf60': 'RRF (k = 60)',
          'vector_a030': 'Vector fusion (rewrite weight = 0.30)'}
COLORS = {'original': '#60656F', 'normalize': '#D55E00', 'rrf60': '#0072B2', 'vector_a030': '#009E73'}
MARKERS = {'original': 's', 'normalize': '^', 'rrf60': 'o', 'vector_a030': 'D'}
LEVELS = ('L0', 'L1', 'L2', 'L3')


def plot(run):
    run = Path(run)
    metric_path, changes_path = run/'metrics.json', run/'changes-summary.csv'
    metrics = json.loads(metric_path.read_text(encoding='utf-8'))
    rows = [r for r in metrics if r['split'] == 'test' and r['language'] == 'all' and r['level'] in LEVELS and r['arm'] in ARMS]
    grid = {(r['arm'], r['level']): r for r in rows}
    if len(grid) != 16 or len(rows) != 16 or any(r['n'] != 16 for r in rows):
        raise ValueError('Expected unique 4-arm × 4-level test grid with 16 inputs per cell.')
    if any(not 0 <= r['pre_mrr20'] <= 1 or r['pre_hit5'] != 1 for r in rows):
        raise ValueError('Metric bounds or fixed Hit@5 caption no longer match.')
    with changes_path.open(encoding='utf-8', newline='') as handle:
        movements = {r['arm']: r for r in csv.DictReader(handle)
                     if r['split'] == 'test' and r['level'] == 'all' and r['arm'] in ARMS[1:]}
    if set(movements) != set(ARMS[1:]):
        raise ValueError('Missing paired movement counts.')
    for row in movements.values():
        if int(row['n']) != 64 or sum(int(row[x]) for x in ('wins', 'ties', 'losses')) != 64:
            raise ValueError('Paired counts must sum to 64.')

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 12,
                         'axes.labelsize': 10, 'xtick.labelsize': 9, 'ytick.labelsize': 9,
                         'figure.facecolor': 'white', 'axes.facecolor': 'white', 'savefig.facecolor': 'white',
                         'text.color': '#20252B', 'axes.labelcolor': '#30363D', 'xtick.color': '#414852',
                         'ytick.color': '#414852', 'axes.edgecolor': '#AAB1BA',
                         'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(1, 2, figsize=(14.2, 7.1), gridspec_kw={'width_ratios': [1.08, 1]})
    fig.suptitle('Fixed-rewrite retrieval fusion: ranking gains and regressions',
                 x=.067, y=.962, ha='left', fontsize=18, fontweight='bold')
    fig.text(.067, .906, 'R8A offline exploration · reused R7 test partition · not a new independent holdout',
             fontsize=11, color='#58616C')
    handles = [Line2D([0], [0], color=COLORS[a], marker=MARKERS[a], markerfacecolor='white',
                      linewidth=1.8, markersize=5.5, label=LABELS[a]) for a in ARMS]
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.061, .882), ncol=4,
               frameon=False, fontsize=9.4, columnspacing=2.3)

    ax = axes[0]
    for arm in ARMS:
        ax.plot(range(4), [grid[arm, level]['pre_mrr20'] for level in LEVELS],
                color=COLORS[arm], marker=MARKERS[arm], markerfacecolor='white',
                markeredgewidth=1.4, markersize=7, linewidth=1.85,
                linestyle='--' if arm == 'vector_a030' else '-', zorder=3+ARMS.index(arm)/10)
    ax.set_title('A   First-stage MRR@20 by wording level', loc='left', fontweight='semibold', pad=16)
    ax.set_ylabel('Mean reciprocal rank')
    ax.set_xticks(range(4), ['L0\nCanonical', 'L1\nConversational', 'L2\nEveryday terms', 'L3\nStrong paraphrase'])
    ax.set_xlim(-.3, 3.3)
    ax.set_ylim(0, 1.065)
    ax.set_yticks([0, .2, .4, .6, .8, 1.0])
    ax.grid(axis='y', color='#E3E7EB', linewidth=.7, zorder=0)
    ax.spines[['top', 'right']].set_visible(False)
    ax.text(.02, .05, 'n = 16 bilingual inputs per level\nAll displayed arms: Hit@5 = 100%',
            transform=ax.transAxes, fontsize=9, color='#58616C', linespacing=1.65)

    ax = axes[1]
    change_colors = {'wins': '#1D8D72', 'ties': '#DCE1E6', 'losses': '#CC6545'}
    for y, arm in enumerate(ARMS[1:]):
        left = 0
        row = movements[arm]
        for key in ('wins', 'ties', 'losses'):
            value = int(row[key])
            ax.barh(y, value, left=left, height=.52, color=change_colors[key], edgecolor='white', linewidth=.7, zorder=3)
            left += value
        ax.text(66, y, f"{row['wins']} / {row['ties']} / {row['losses']}", va='center', ha='left', fontsize=9.2)
    ax.text(66, -.55, 'Win / Tie / Loss', ha='left', va='center', fontsize=8.4, color='#58616C')
    ax.set_title('B   Paired changes versus original', loc='left', fontweight='semibold', pad=16)
    ax.set_yticks(range(3), ['Normalization', 'RRF (k = 60)', 'Vector fusion\n(rewrite weight = 0.30)'])
    ax.set_ylim(2.85, -.88)
    ax.set_xlim(0, 84)
    ax.set_xticks([0, 16, 32, 48, 64])
    ax.set_xlabel('Number of inputs (n = 64)')
    ax.grid(axis='x', color='#E3E7EB', linewidth=.7, zorder=0)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.tick_params(axis='y', length=0, pad=8)
    ax.legend(handles=[Patch(facecolor=change_colors[key], label=label) for key, label in
                       [('wins', 'Higher MRR'), ('ties', 'Unchanged'), ('losses', 'Lower MRR')]],
              loc='lower left', bbox_to_anchor=(0, .005), ncol=3, frameon=False,
              fontsize=8.2, handlelength=1.1, columnspacing=1.2, borderaxespad=0)

    fig.subplots_adjust(left=.075, right=.97, top=.76, bottom=.255, wspace=.36)
    notes = [
        'Same archived rewrite text, query embeddings, 380 chunks, and hybrid dense–lexical retrieval; at most 20 output candidates per arm.',
        'Eight question families; AI-authored bilingual variants and AI-reviewed labels. L4 ambiguous inputs are excluded from retrieval scoring.',
        'Descriptive point estimates only. The reused partition is exploratory, not fresh validation or a basis for choosing a production winner.',
        'First-stage retrieval only: no reranking, answer generation, or latency comparison. New model/API calls: 0; new API cost: USD 0.',
        'α = 0.30 mixes 70% original and 30% rewrite unit vectors; its lexical query remains original. Complete seven-arm results are in the report.'
    ]
    for index, note in enumerate(notes):
        fig.text(.075, .174-index*.025, note, fontsize=8.2, color='#58616C', va='top')
    paths = []
    for extension in ('png', 'pdf', 'svg'):
        output = run/f'figure-fixed-rewrite-fusion.{extension}'
        fig.savefig(output, dpi=300, facecolor='white')
        paths.append(output)
    plt.close(fig)
    manifest = dict(plotter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (metric_path, changes_path)},
                    output_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                    status='derived_publication_figure_no_new_ranking')
    (run/'figure-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    for path in plot(args.run):
        print(path)
