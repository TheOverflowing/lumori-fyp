"""Reproducible academic figures. Published values are read from archived tables."""
from pathlib import Path
import json, re, subprocess, sys, os
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

ROOT=Path(__file__).resolve().parents[1]
os.environ['FONTCONFIG_FILE']=str(ROOT/'tmp/thesis/fonts.conf')
OUT=ROOT/'docs/thesis/figures/v0.4'
POP=Path(sys.executable).parents[2]/'bin/override/pdftoppm'
def raster(name):
    subprocess.run([str(POP),'-png','-scale-to','2200','-singlefile',str(OUT/f'{name}.pdf'),str(OUT/name)],check=True)
def graph(name, body):
    source='digraph G { graph [bgcolor="white", pad="0.25", nodesep="0.38", ranksep="0.5", fontname="Helvetica", fontsize=13]; node [shape=box, style="filled", fillcolor="#F5F7F9", color="#384651", fontname="Helvetica", fontsize=12, margin="0.14,0.10"]; edge [color="#384651", fontname="Helvetica", fontsize=10, arrowsize=0.7];\n'+body+'\n}'
    (OUT/f'{name}.dot').write_text(source)
    subprocess.run(['/opt/homebrew/bin/dot','-Tpdf',str(OUT/f'{name}.dot'),'-o',str(OUT/f'{name}.pdf')],check=True)
    raster(name)

def diagrams():
    graph('supervisor-reference', '''
rankdir=TB;
subgraph cluster_host {label="HOST CONTROLLER"; style=dashed; color="#82909A";
slots [label="Slots + targets + evidence"];
plan [label="Main agent\nplan briefs", fillcolor="#E9EEF2"];
valid [label="Valid plan?", shape=diamond]; stop [label="Stop + record"];
dispatch [label="Freeze plan\nserial dispatch"];
all [label="All slots\naccepted?", shape=diamond];
assembly [label="Deterministic assembly"];
slots -> plan -> valid; valid -> stop [label="no"]; valid -> dispatch [label="yes"];
all -> dispatch [label="no", constraint=false]; all -> assembly [label="yes"];
}
subgraph cluster_worker {label="ISOLATED SUBAGENT q_i"; style=dashed; color="#82909A";
author [label="Author"]; solver [label="Blind solver"]; review [label="Reviewer"];
accept [label="Accept?",shape=diamond]; budget [label="Repair budget?",shape=diamond];
checkpoint [label="Accepted checkpoint"]; fail [label="Retain failure"];
{rank=same;author;solver;review;accept;}
author -> solver -> review -> accept;
accept -> checkpoint [label="yes"]; accept -> budget [label="no"];
budget -> author [label="yes: feedback",constraint=false]; budget -> fail [label="no"];
}
dispatch -> author [label="brief + source IDs"]; checkpoint -> all;
assembly -> draft [label="complete set"]; draft [label="Versioned draft"];
''')
    graph('retrieval-reference', '''
rankdir=LR;
q [label="Original query"];
rewrite [label="Optional rewrite",style="filled,dashed"];
original [label="Original-query retrieval"];
second [label="Rewritten-query retrieval",style="filled,dashed"];
merge [label="RRF60 fusion",style="filled,dashed"];
rerank [label="Rerank"];
context [label="Bounded evidence"];
index [label="Owned course index",shape=cylinder];
q -> original; q -> rewrite [style=dashed]; rewrite -> second [style=dashed];
index -> original; index -> second [style=dashed];
original -> rerank [label="fusion off / fallback"];
original -> merge [style=dashed]; second -> merge [style=dashed];
merge -> rerank [style=dashed]; rerank -> context;
''')
    graph('review-export-reference', '''
rankdir=TB;
draft [label="Saved version"];
review [label="Review + evidence"];
edit [label="Edit content"]; next [label="New version"];
approve [label="Approve text"];
rating [label="Version rating\ninsert or update"];
export [label="Export blocks\nsource-level references"];
files [label="PDF / Word / Markdown"];
future [label="Future media output\nversion-bound artifacts",style="filled,dashed"];
draft -> review; review -> edit -> next; next -> review [constraint=false];
review -> approve; draft -> rating; draft -> export -> files;
approve -> future [style=dashed];
''')
    graph('account-scope', '''
rankdir=LR;
login [label="Register / log in"];
session [label="Opaque session"];
auth [label="Authenticate"];
scope [label="Owner + course scope"];
mutation [label="CSRF check\nfor mutations"];
objects [label="Sources / vectors\njobs / versions"];
reject [label="Reject request"];
login -> session -> auth; auth -> scope [label="valid"]; auth -> reject [label="invalid"];
scope -> objects [label="owned reads"]; scope -> mutation -> objects;
scope -> reject [label="not owned"]; mutation -> reject [label="invalid token"];
''')
    graph('chunk-provenance', '''
rankdir=TB;
page [label="Parsed page text"];
units [label="Structural units\nheadings / paragraphs / protected blocks"];
fits [label="Within budget?",shape=diamond];
split [label="Finer boundaries\nsentence / line / word / fallback"];
chunks [label="Exact source slices"];
meta [label="Page + heading path\ncharacter bounds + chunk hash"];
embed [label="Title context + chunk text\ncompatible embedding"];
page -> units -> fits; fits -> chunks [label="yes"]; fits -> split [label="no"];
split -> fits [label="recheck",constraint=false]; chunks -> meta -> embed;
''')
    graph('evaluation-protocol', '''
rankdir=LR;
freeze [label="Freeze corpus + policy"];
group [label="Group related needs\nseparate development / test"];
arms [label="Paired retrieval arms"];
rank [label="Hit@k / MRR@k"];
audit [label="Semantic audit\nintent / answer leakage"];
ledger [label="Calls / failures / costs"];
claim [label="Bounded conclusions\nretain negative results"];
freeze -> group -> arms; arms -> rank; arms -> audit; arms -> ledger;
rank -> claim; audit -> claim; ledger -> claim;
''')

COLORS=['#283E51','#718D9F','#ADB9C2']
def rows(path):
    return [[c.strip() for c in line.strip().strip('|').split('|')] for line in (ROOT/path).read_text().splitlines() if line.startswith('|')]
def number(value): return float(value.replace('**',''))
def chart(name,title,draw):
    c=canvas.Canvas(str(OUT/f'{name}.pdf'),pagesize=(640,370));c.setTitle(title)
    c.setFillColor(HexColor('#202B33'));c.setFont('Helvetica-Bold',14);c.drawString(60,345,title)
    draw(c);c.showPage();c.save();raster(name)
def axes(c,label,lo=0,hi=1):
    c.setFont('Helvetica',10)
    for j in range(5):
        val=lo+(hi-lo)*j/4;y=75+240*j/4
        c.setStrokeColor(HexColor('#DDE2E5'));c.setLineWidth(.5);c.line(65,y,610,y)
        c.setFillColor(HexColor('#202B33'));c.drawRightString(55,y-3,f'{val:.2f}')
    c.saveState();c.translate(16,195);c.rotate(90);c.drawCentredString(0,0,label);c.restoreState()
    return lambda v:75+(v-lo)/(hi-lo)*240
def legend(c,labels,y=28):
    x=65
    for col,label in zip(COLORS,labels):
        c.setFillColor(HexColor(col));c.rect(x,y,10,8,fill=1,stroke=0)
        c.setFillColor(HexColor('#202B33'));c.setFont('Helvetica',10);c.drawString(x+16,y,label);x+=170
def charts():
    a=rows('docs/rag/R8A_FUSION_RESULTS_20260920.md')
    level=[next(r for r in a if r[0].startswith(level+' ')) for level in ['L0','L1','L2','L3']]
    r7=[[number(r[i]) for r in level] for i in [1,2,3]]
    def line(c):
        yy=axes(c,'MRR@20',.70,1.02)
        for k,(values,col) in enumerate(zip(r7,COLORS)):
            c.setStrokeColor(HexColor(col));c.setFillColor(HexColor(col));c.setLineWidth(1.8);c.setDash([5,3] if k==1 else ([2,3] if k==2 else []))
            pts=[(100+i*155,yy(v)) for i,v in enumerate(values)]
            p=c.beginPath();p.moveTo(*pts[0])
            for xy in pts[1:]:p.lineTo(*xy)
            c.drawPath(p);c.setDash([])
            for x,y in pts:c.circle(x,y,3.2,fill=1,stroke=0)
        c.setFillColor(HexColor('#202B33'));c.setFont('Helvetica',10)
        for i,l in enumerate(['L0 Formal','L1 Mild','L2 Substitution','L3 Strong']):c.drawCentredString(100+i*155,55,l)
        legend(c,['Original','Normalize','Interleave'])
    chart('r7-colloquial-line','R7  Ranking across wording levels',line)
    total=next(r for r in a if r[0]=='总体')
    vals=[number(total[i]) for i in [1,2,3,4,6]]
    def bars(c):
        yy=axes(c,'MRR@20')
        for i,(label,v) in enumerate(zip(['Original','Normalize','Interleave','RRF60','Vector 0.30'],vals)):
            x=87+i*108;c.setFillColor(HexColor(COLORS[0] if i==0 else COLORS[1]));c.rect(x,75,62,yy(v)-75,fill=1,stroke=0)
            c.setFillColor(HexColor('#202B33'));c.setFont('Helvetica',10);c.drawCentredString(x+31,yy(v)+7,f'{v:.4f}');c.drawCentredString(x+31,55,label)
        c.drawString(65,25,'Same exposed R7 inputs (n = 64); all arms Hit@5 = 1.00')
    chart('r8a-strategy-bars','R8A  Fixed-rewrite fusion comparison',bars)
    deltas=[]
    for key in ['normalize','interleave','rrf60','vector α=.30']:
        r=next(r for r in a if r[0]==key and len(r)==5)
        deltas.append([int(v.strip()) for v in r[4].split('/')])
    def stacks(c):
        left=150;scale=430/64
        for j,(label,values) in enumerate(zip(['Normalize','Interleave','RRF60','Vector 0.30'],deltas)):
            y=280-j*52;x=left;c.setFont('Helvetica',11);c.setFillColor(HexColor('#202B33'));c.drawRightString(left-12,y+8,label)
            for col,v in zip(['#536F82','#D9DFE3','#5C4848'],values):
                c.setFillColor(HexColor(col));c.rect(x,y,v*scale,27,fill=1,stroke=0)
                if v>=3:c.setFillColor(HexColor('#FFFFFF' if col!='#D9DFE3' else '#202B33'));c.setFont('Helvetica',10);c.drawCentredString(x+v*scale/2,y+8,str(v))
                x+=v*scale
            c.setFillColor(HexColor('#202B33'));c.setFont('Helvetica',9);c.drawString(150,y-13,' / '.join(map(str,values))+'  improved / unchanged / harmed')
        c.setFont('Helvetica',11);c.drawString(150,45,'Each bar contains the same 64 paired inputs.')
    chart('r8a-paired-outcomes','R8A  Per-input rank changes relative to original',stacks)
    b=rows('docs/rag/R8B_RESULTS_20260920.md')
    selected=[r for r in b if len(r)==6 and r[0] in ['信息充分','信息不足、指定意图']]
    valsb=[[number(r[3]) for r in selected[:3]],[number(r[3]) for r in selected[3:]]]
    def grouped(c):
        yy=axes(c,'MRR@20')
        for group,values in enumerate(valsb):
            for k,v in enumerate(values):
                x=115+group*265+k*59;c.setFillColor(HexColor(COLORS[k]));c.rect(x,75,45,yy(v)-75,fill=1,stroke=0)
                c.setFillColor(HexColor('#202B33'));c.setFont('Helvetica',10);c.drawCentredString(x+22,yy(v)+8,f'{v:.4f}')
            c.drawCentredString(196+group*265,55,['Sufficient (n = 24)','Insufficient (n = 24)'][group])
        legend(c,['Original','Normalize','Selective'])
    chart('r8b-grouped-bars','R8B  Held-out results by information sufficiency',grouped)
    (OUT/'chart_data.json').write_text(json.dumps({'r7':r7,'r8a_mrr':vals,'r8a_changes':deltas,'r8b_mrr':valsb,'sources':['docs/rag/R8A_FUSION_RESULTS_20260920.md','docs/rag/R8B_RESULTS_20260920.md'],'note':'R8A repeats R7 original/normalize/interleave exact values; no new experiment.'},indent=2))
if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);diagrams();charts()
