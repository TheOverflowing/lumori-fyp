"""Original thesis diagrams and a licensed crop; no model or application calls."""
from pathlib import Path
import hashlib, json, math, subprocess, sys
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / 'docs/thesis/figures'
POP = Path(sys.executable).parents[2] / 'bin/override/pdftoppm'
INK, LINE, FILL = '#172e42', '#536d80', '#f3f6f8'

class Diagram:
    def __init__(self, name, height=390):
        self.name, self.h = name, height
        self.c = canvas.Canvas(str(FIG / f'{name}.pdf'), pagesize=(640, height))
        self.c.setTitle(name.replace('-', ' '))
    def label(self, x, y, lines, size=11, bold=False):
        c = self.c; c.setFillColor(HexColor(INK))
        c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        for i, s in enumerate(lines.split('\n')): c.drawCentredString(x, self.h-y-i*(size+5), s)
    def box(self, x, y, w, h, title, body='', dashed=False):
        c=self.c; c.setStrokeColor(HexColor(LINE)); c.setFillColor(HexColor(FILL)); c.setLineWidth(.8)
        c.setDash([4,3] if dashed else [])
        c.roundRect(x,self.h-y-h,w,h,5,fill=1,stroke=1);c.setDash([])
        self.label(x+w/2,y+21,title,11,True)
        if body: self.label(x+w/2,y+42,body,10)
    def arrow(self, pts, text='', tx=0, ty=0, dashed=False):
        c=self.c;c.setStrokeColor(HexColor(LINE));c.setLineWidth(1.1);c.setDash([4,3] if dashed else [])
        p=c.beginPath();p.moveTo(pts[0][0],self.h-pts[0][1])
        for x,y in pts[1:]:p.lineTo(x,self.h-y)
        c.drawPath(p);c.setDash([])
        (x0,y0),(x,y)=pts[-2:];a=math.atan2(y-y0,x-x0)
        for b in [-.5,.5]:c.line(x,self.h-y,x-7*math.cos(a+b),self.h-(y-7*math.sin(a+b)))
        if text:self.label(tx,ty,text,9)
    def save(self):
        self.c.showPage();self.c.save()
        subprocess.run([str(POP),'-png','-scale-to','2200','-singlefile',str(FIG/f'{self.name}.pdf'),str(FIG/self.name)],check=True)

def build():
    d=Diagram('query-routing',355)
    d.box(180,8,280,57,'Original learning objective','Learner profile and language')
    d.box(180,100,280,70,'Optional clarification','One question; use actual user reply')
    d.arrow([(320,65),(320,100)])
    d.box(20,213,270,63,'Original query','Always retained as an explicit route')
    d.box(350,213,270,63,'Optional faithful rewrite','Fusion off by default; no invented answers')
    d.arrow([(250,170),(250,190),(155,190),(155,213)])
    d.arrow([(390,170),(390,190),(485,190),(485,213)],dashed=True)
    d.arrow([(155,276),(155,305)])
    d.arrow([(485,276),(485,305)],dashed=True)
    d.box(45,305,550,43,'Hybrid candidates -> optional RRF60 -> rerank -> evidence')
    d.save()
    d=Diagram('ingestion-flow',310)
    for x,t,b in [(20,'Source file','Text / Markdown / PDF / image'),(345,'Optional figures','Docling crop + model description')]:d.box(x,10,275,70,t,b)
    d.box(20,120,275,70,'Parse and preserve','Native text or MinerU Standard / Advanced')
    d.box(345,120,275,70,'Traceable source metadata','Document / page / heading / original image')
    d.arrow([(157,80),(157,120)]);d.arrow([(482,80),(482,120)],dashed=True)
    d.arrow([(295,155),(345,155)])
    d.box(130,230,380,65,'Recursive chunks and compatible vectors','256 body tokens; title context; account and course scope')
    d.arrow([(157,190),(157,211),(260,211),(260,230)])
    d.arrow([(482,190),(482,211),(380,211),(380,230)])
    d.save()
    d=Diagram('question-agent',430)
    d.box(130,8,380,60,'Freeze plan and source snapshot','q1 ... qN; exact difficulty counts; fixed order')
    d.box(20,105,260,72,'Author one question','Question, answer, explanation, citations')
    d.box(360,105,260,72,'Solve independently','Author answer and target label hidden')
    d.arrow([(320,68),(320,88),(150,88),(150,105)])
    d.arrow([(280,142),(360,142)])
    d.box(360,214,260,70,'Review answer and support','Whitelisted calculation tools where supported')
    d.arrow([(490,177),(490,214)])
    d.box(20,214,260,70,'Policy decision','Strict match / adjusted draft / repair / stop')
    d.arrow([(360,249),(280,249)])
    d.arrow([(70,214),(70,177)],'repair',95,199)
    d.box(20,332,260,65,'Save accepted slot','Keep its checks, attempts and source links')
    d.box(360,332,260,65,'Assemble complete draft','Only after every slot has an accepted result')
    d.arrow([(150,284),(150,332)])
    d.arrow([(280,365),(360,365)],'all slots',320,351)
    d.arrow([(20,365),(7,365),(7,90),(150,90),(150,105)],dashed=True)
    d.label(320,420,'Native runtime is sequential; role separation does not imply independent model families.',10)
    d.save()
    d=Diagram('difficulty-decision',405)
    d.box(170,7,300, 60,'Candidate after other quality checks','Keep only otherwise eligible candidates')
    d.box(170,105,300,60,'Does assessed demand match target?','The requested target is never relabeled')
    d.arrow([(320,67),(320,105)])
    d.box(20,212,260,60,'Strict acceptance','Record strict_passed = true')
    d.box(360,212,260,60,'Continue ordinary attempts','Stop early on strict match; normally 3 rounds')
    d.arrow([(245,165),(245,185),(150,185),(150,212)],'yes',210,178)
    d.arrow([(395,165),(395,185),(490,185),(490,212)],'no',430,178)
    d.box(360,320,260,60,'Select closest eligible candidate','Adjacent level first; then any level')
    d.arrow([(490,272),(490,320)],'rounds exhausted',543,300)
    d.box(20,320,260,60,'Adjusted draft or no candidate','Adjusted is not a strict difficulty success')
    d.arrow([(360,350),(280,350)])
    d.label(320,400,'Provider failures and task / account quotas remain separate stopping conditions.',10)
    d.save()
    d=Diagram('exploration-flow',415)
    rows=[('Detect evidence gaps','Freeze the missing concepts and scope'),('Discover and fetch permitted sources','Curated catalog by default; optional search provider'),('Build task-private index','Parse full text -> chunks -> embeddings'),('Retrieve for the gaps and reassess coverage','Bounded evidence; selective same-section neighbors'),('Promote accepted sources into owned course','Reuse compatible vectors and preserve provenance')]
    for i,(a,b) in enumerate(rows):
        y=7+i*78;d.box(115,y,410,60,a,b)
        if i:d.arrow([(320,y-18),(320,y)])
    d.arrow([(525,270),(606,270),(606,115),(525,115)],'remaining\ngaps',579,184,dashed=True)
    d.label(320,407,'Each loop is bounded by time, source, search and model-call limits; unresolved gaps stop generation.',9)
    d.save()
    d=Diagram('job-lifecycle',335)
    d.box(20,12,260,70,'Generation request','Persist inputs, owner and configuration')
    d.box(360,12,260,70,'Running job','Durable events and per-stage elapsed time')
    d.arrow([(280,47),(360,47)])
    d.box(360,130,260,70,'Interrupted or rejected step','Retain completed slots and failed attempts')
    d.arrow([(490,82),(490,130)])
    d.arrow([(620,165),(633,165),(633,47),(620,47)],dashed=True)
    d.box(20,130,260,70,'Complete draft version','Explicit open-result action; review remains pending')
    d.arrow([(400,82),(400,104),(150,104),(150,130)])
    d.box(20,250,260,65,'Review and export','Version rating; PDF / Word; grouped references')
    d.arrow([(150,200),(150,250)])
    d.box(360,250,260,65,'Resume or edit request','Same checkpoint, or restore inputs for a new job')
    d.arrow([(490,200),(490,250)])
    d.save()
    # Reproduce only the chart area of Figure 1, including axes and legend.
    src=ROOT/'docs/thesis/literature/v0.3/papers/middle.pdf'
    page=PdfReader(src).pages[1]; w=float(page.mediabox.width);h=float(page.mediabox.height)
    # Fractions measured from the inspected 1132 x 1600 full-page render.
    crop=[.115*w,.682*h,.492*w,.938*h]
    page.cropbox.lower_left=crop[:2];page.cropbox.upper_right=crop[2:]
    out=PdfWriter();out.add_page(page)
    with (FIG/'literature-middle.pdf').open('wb') as f:out.write(f)
    subprocess.run([str(POP),'-cropbox','-png','-scale-to','1800','-singlefile',str(FIG/'literature-middle.pdf'),str(FIG/'literature-middle')],check=True)
    meta={'source':'https://aclanthology.org/2024.tacl-1.9.pdf','authors':'Nelson F. Liu et al.','original_figure':1,'printed_page':158,'pdf_page':2,'license':'CC BY 4.0','license_url':'https://creativecommons.org/licenses/by/4.0/','license_evidence':'PDF first-page copyright notice and ACL Anthology footer','modification':'Cropped to chart, axes and legend; original caption replaced with attributed thesis caption. No data modified.','crop_points':crop,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'verified_on':'2026-09-20'}
    (FIG/'literature-middle-provenance.json').write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__':build()
