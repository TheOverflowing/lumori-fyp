"""Standalone R5 quality figures from observed held-out results."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def make(run):
    records=json.loads((run/'test-summary.json').read_text())
    rows={(r['arm'],r['group']):r for r in records}
    groups=['cross:en','cross:zh','mode:mixed']
    labels=['English query\nChinese sources (n=31)','Chinese query\nEnglish sources (n=31)','Mixed-language sources\n(n=62)']
    arms=['original','translated','dual'];names=['Original query','Translated query','Dual query (total 20)']
    colors=['#176778','#e09b38','#73599d'];x=np.arange(3);width=.24
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(11.8,5.1),layout='constrained')
    for ax,metric,title in zip(axes,['budget_hit','mrr5'],['Answer-span hit within 1,024 source tokens','MRR@5']):
        for index,(arm,name,color) in enumerate(zip(arms,names,colors)):
            values=[rows[arm,g][metric] for g in groups]
            bars=ax.bar(x+(index-1)*width,values,width,label=name,color=color)
            ax.bar_label(bars,labels=[f'{v:.1%}' if metric=='budget_hit' else f'{v:.3f}' for v in values],fontsize=8,padding=3)
        ax.set_xticks(x,labels);ax.set_ylim(0,1.10);ax.set_yticks(np.arange(0,1.01,.2));ax.set_title(title,pad=15)
        ax.set_axisbelow(True);ax.yaxis.grid(alpha=.18)
    handles,legend=axes[0].get_legend_handles_labels()
    fig.legend(handles,legend,loc='outside lower center',ncol=3,frameon=False)
    fig.suptitle('R5: Query translation on new public bilingual QA\n31 question families · fixed top-20 reranking pool · failures included',fontsize=14)
    for ext in ('png','pdf'):
        fig.savefig(run/('r5-heldout-quality.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)
    print(run/'r5-heldout-quality.png')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    make(p.parse_args().run)
