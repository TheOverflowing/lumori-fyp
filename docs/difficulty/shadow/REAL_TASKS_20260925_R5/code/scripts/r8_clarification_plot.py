"""Publication figure from completed R8B metrics; no model or retrieval calls.

Run only after scripts/r8_clarification_report.py has completed:
PYTHONPATH=/tmp/lumori-r7-plot-deps MPLCONFIGDIR=/tmp/lumori-r7-matplotlib \
  .venv/bin/python scripts/r8_clarification_plot.py --run RUN

The two panels intentionally keep sufficient queries and underspecified queries
separate. The latter measures alignment to a specified simulated-user intent,
not universal correctness of every other plausible interpretation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ARMS = ('original', 'normalize', 'selective')
LABELS = {'original': 'Original', 'normalize': 'Normalization', 'selective': 'Selective clarification'}
COLORS = {'original': '#737D88', 'normalize': '#0072B2', 'selective': '#009E73'}
CLARITIES = ('sufficient', 'underspecified')
METRICS = ('pre_hit5', 'pre_mrr20')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def validate(summary, query_rows):
    rows = [r for r in summary if r['split'] == 'test' and r['language'] == 'all' and r['style'] == 'all']
    grid = {(r['clarity'], r['arm']): r for r in rows}
    if len(grid) != 6 or len(rows) != 6 or set(grid) != {(c, a) for c in CLARITIES for a in ARMS}:
        raise ValueError('Expected three strategies in two distinct clarity groups.')
    for clarity in CLARITIES:
        for arm in ARMS:
            summary_row = grid[clarity, arm]
            per_query = [r for r in query_rows if r['split'] == 'test' and r['clarity'] == clarity and r['arm'] == arm]
            if len(per_query) != 24 or len({r['query_id'] for r in per_query}) != 24:
                raise ValueError('This figure requires 24 unique test inputs per clarity group.')
            if len({r['family_id'] for r in per_query}) != 6 or summary_row['families'] != 6 or summary_row['n'] != 24:
                raise ValueError('Expected six held-out test families with 24 inputs per group.')
            interpretation = 'unambiguous_evidence' if clarity == 'sufficient' else 'target_conditioned_alignment'
            if any(r['score_interpretation'] != interpretation for r in per_query):
                raise ValueError('Clarity-group score semantics changed.')
            for metric in METRICS:
                value = summary_row[metric]
                if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError('Invalid '+metric)
                if abs(value-statistics.mean(r[metric] for r in per_query)) > 1e-12:
                    raise ValueError('Summary disagrees with per-query metrics.')
            for key in ('asked', 'resolved', 'unknown', 'fallback', 'embedding_failed'):
                if summary_row[key] != sum(r[key] for r in per_query):
                    raise ValueError('Summary disagrees with per-query '+key)
            for row in per_query:
                if row['resolved'] and (not row['asked'] or row['unknown']):
                    raise ValueError('Inconsistent resolved/asked/unknown flags.')
                if row['unknown'] and not row['asked']:
                    raise ValueError('Unknown reply without a clarification request.')
    return grid


def plot(run):
    run = Path(run)
    summary_path, queries_path = run/'summary.json', run/'per-query.json'
    grid = validate(read(summary_path), read(queries_path))
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 12,
                         'axes.labelsize': 10, 'xtick.labelsize': 10, 'ytick.labelsize': 9,
                         'figure.facecolor': 'white', 'axes.facecolor': 'white', 'savefig.facecolor': 'white',
                         'text.color': '#20252B', 'axes.labelcolor': '#30363D', 'xtick.color': '#414852',
                         'ytick.color': '#414852', 'axes.edgecolor': '#AAB1BA',
                         'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(1, 2, figsize=(14.2, 8.2))
    fig.suptitle('Selective clarification and first-stage retrieval',
                 x=.075, y=.958, ha='left', fontsize=19, fontweight='bold')
    fig.text(.075, .910, 'R8B · held-out questions on previously seen textbooks · simulated user replies',
             fontsize=11, color='#58616C')
    fig.legend(handles=[Patch(facecolor=COLORS[a], label=LABELS[a]) for a in ARMS],
               loc='upper left', bbox_to_anchor=(.069, .883), ncol=3, frameon=False,
               fontsize=10, columnspacing=3, handlelength=1.5)
    width = .23
    for ax, clarity in zip(axes, CLARITIES):
        for index, arm in enumerate(ARMS):
            values = [grid[clarity, arm][metric] for metric in METRICS]
            xs = [group+(index-1)*width for group in range(2)]
            ax.bar(xs, values, width=width*.87, color=COLORS[arm], zorder=3)
            for x, value in zip(xs, values):
                ax.text(x, value+.025, f'{value:.3f}', ha='center', va='bottom', fontsize=9.1)
        if clarity == 'sufficient':
            title, subtitle = 'A   Sufficient input', 'Unambiguous evidence alignment'
        else:
            title, subtitle = 'B   Underspecified input', 'Target-conditioned alignment (simulated user)'
        ax.set_title(title, loc='left', fontweight='bold', pad=30)
        ax.text(0, 1.022, subtitle, transform=ax.transAxes, fontsize=9.8, color='#58616C')
        ax.set_xticks([0, 1], ['Evidence Hit@5', 'MRR@20'])
        ax.set_xlim(-.53, 1.53)
        ax.set_ylim(0, 1.135)
        ax.set_yticks([0, .2, .4, .6, .8, 1])
        ax.set_ylabel('Metric value')
        ax.grid(axis='y', color='#E3E7EB', linewidth=.7, zorder=0)
        ax.spines[['top', 'right']].set_visible(False)
        ax.text(.5, -.125, 'n = 24 inputs · 6 question families', transform=ax.transAxes,
                ha='center', va='top', fontsize=9.4, color='#58616C')
    fig.subplots_adjust(left=.075, right=.97, top=.756, bottom=.337, wspace=.21)
    fig.text(.075, .245, 'Selective policy: clarification decisions', fontsize=10.7, fontweight='bold')
    for line, clarity in enumerate(CLARITIES):
        row = grid[clarity, 'selective']
        label = 'Sufficient inputs' if clarity == 'sufficient' else 'Underspecified inputs'
        text = (f"{label}: asked {row['asked']}/24; resolved {row['resolved']}; "
                f"unknown {row['unknown']}; unresolved asks {row['asked']-row['resolved']}.")
        fig.text(.075, .213-line*.029, text, fontsize=10, color='#414852')
    notes = [
        '48 held-out inputs in total; six families contribute to both groups. Languages and formal/colloquial styles remain in each denominator.',
        'AI-authored inputs, AI-reviewed evidence labels, and simulated replies; this is not a real-student or teacher-gold evaluation.',
        'Resolved is model-reported; unknown replies are a subset of unresolved asks. All unresolved, fallback, and failure cases are retained.',
        'Panels use different interpretations and must not be pooled as a single accuracy score. Point estimates; paired intervals are in the report.',
        'First-stage retrieval only, at most 20 candidates per policy. No reranking, answer generation, or end-to-end outcome measurement.'
    ]
    for index, note in enumerate(notes):
        fig.text(.075, .139-index*.020, note, fontsize=8.2, color='#58616C', va='top')
    paths = []
    for extension in ('png', 'pdf', 'svg'):
        path = run/f'figure-selective-clarification.{extension}'
        fig.savefig(path, dpi=300, facecolor='white')
        paths.append(path)
    plt.close(fig)
    manifest = dict(status='derived_figure_no_new_model_or_retrieval_calls',
                    plotter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (summary_path, queries_path)},
                    output_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (run/'figure-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    for path in plot(args.run):
        print(path)
