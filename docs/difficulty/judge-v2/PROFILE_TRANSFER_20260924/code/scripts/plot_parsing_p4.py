"""Publication-exportable plots from audited P4 aggregate data, no inference."""
from pathlib import Path
import json
import os
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1]/'tmp/p4-matplotlib-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
P4 = ROOT/'docs/parsing/experiments/P4-candidate-expansion-20260918'
LABELS = {'adaptive_local_v1': 'Adaptive baseline', 'mineru_4_0_2_basic_onnx': 'MinerU Basic',
          'mineru_4_0_2_standard_onnx': 'MinerU Standard', 'mineru_4_0_2_advanced_onnx': 'MinerU Advanced',
          'docling_2_128_tesseract_tableformer_v2': 'Docling + Tesseract',
          'docling_2_128_granite_258m_mlx': 'GraniteDocling MLX', 'paddleocr_3_7_vl16_mlx': 'PaddleOCR-VL 1.6 MLX',
          'paddleocr_3_7_vl16_mlx_unmerged': 'PaddleOCR-VL 1.6, unmerged',
          'paddleocr_3_7_vl16_mlx_unmerged_xycut': 'PaddleOCR-VL + XY-cut order'}


def main():
    doc = json.loads((P4/'comparison.json').read_text())
    assert json.loads((P4/'audit.json').read_text())['all_passed']
    dest = P4/'figures'; dest.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none',
                         'axes.spines.top': False, 'axes.spines.right': False})
    for split, source_count in [('development', 6), ('confirmation', 8)]:
        rows = [r for r in doc['summary'] if r['split'] == split and r['language'] == 'all']
        strategies = list(dict.fromkeys(r['strategy'] for r in rows))
        y = np.arange(len(strategies)); fig, ax = plt.subplots(figsize=(10, 1.2+len(strategies)*.68))
        for i, (variant, label, color) in enumerate([('native_pdf','Original PDF','#247c8d'),
                    ('image_only_pdf','Image-only PDF','#db9839'),('degraded_image','Synthetic degradation','#9361a8')]):
            values = [next(r['macro_cer']*100 for r in rows if r['strategy'] == s and r['variant'] == variant) for s in strategies]
            bars = ax.barh(y+(i-1)*.24, values, height=.22, color=color, label=label)
            ax.bar_label(bars, labels=[f'{v:.1f}' for v in values], padding=3, fontsize=8)
        ax.set_yticks(y, [LABELS[s] for s in strategies]); ax.invert_yaxis()
        ax.set_xlabel('Macro character error rate (%) — lower is better; failures retained')
        ax.set_title(f'{split.title()} · {source_count} text source pages · 3 paired conditions', loc='left', weight='bold')
        ax.grid(axis='x', alpha=.18); ax.set_axisbelow(True); ax.margins(x=.14)
        ax.legend(loc='lower right', fontsize=9)
        fig.text(.99,.01,'Project pilot, not an official OmniDocBench score. Variants are not independent documents.',ha='right',fontsize=8,color='#555555')
        fig.tight_layout(rect=(0,.04,1,1))
        for extension in ['png','svg']:
            fig.savefig(dest/f'{split}-cer.{extension}',dpi=200,bbox_inches='tight')
        plt.close(fig)
    intervals = [doc[key] for key in ['confirmation_interval', 'geometry_confirmation_interval',
                                      'additional_finalist_interval', 'paired_ordering_effect']]
    names = ['Standard → Advanced', 'Standard → Paddle + XY-cut',
             'Advanced → Paddle + XY-cut', 'Paddle raw → same output + XY-cut']
    centers = np.array([i['mean_cer_reduction']*100 for i in intervals])
    lower = np.array([i['percentile_interval_95'][0]*100 for i in intervals])
    upper = np.array([i['percentile_interval_95'][1]*100 for i in intervals])
    fig, ax = plt.subplots(figsize=(10, 3.8))
    ax.errorbar(centers, np.arange(len(names)), xerr=[centers-lower, upper-centers],
                fmt='o', color='#247c8d', ecolor='#247c8d', capsize=4, linewidth=2)
    ax.axvline(0, color='#777777', linestyle='--', linewidth=1)
    ax.set_yticks(np.arange(len(names)), names); ax.invert_yaxis()
    ax.set_ylim(len(names)-.55, -.45)
    ax.set_xlabel('CER reduction (percentage points); positive favors the candidate on the right')
    ax.set_title('Confirmation uncertainty · exploratory 95% intervals', loc='left', weight='bold')
    ax.grid(axis='x', alpha=.18)
    fig.text(.99,.015,'20,000 stratified paired source-page resamples · 8 text pages · no multiplicity correction',
             ha='right',fontsize=8,color='#555555')
    fig.tight_layout(rect=(0,.04,1,1))
    for extension in ['png', 'svg']:
        fig.savefig(dest/f'confirmation-uncertainty.{extension}',dpi=200,bbox_inches='tight')
    plt.close(fig)
    print(dest)


if __name__ == '__main__':
    main()
