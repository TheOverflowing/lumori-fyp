from pathlib import Path
from ca1_content import INTRO,LITERATURE,DESIGN,REFERENCES
import json,csv,hashlib,re
ROOT=Path(__file__).resolve().parent.parent
source=(ROOT/'scripts/build_taskbook.py').read_text()
# Reuse the retained OOXML template helpers; the reference and old outputs are unchanged.
base=source.split('# Page 2')[0]
base=base.replace("elif txt=='Title of Proposal':replace_p(p,'任务书与系统设计',True)","elif txt=='Title of Proposal':replace_p(p,DOC_TITLE,True)")
base=base.replace("'教育内容生成'","'AI for Education'")
base=base.replace('文档状态\\n单人方案 待导师确认','Document status\\nWorking draft').replace('实施人数\\n1 人','Implementation\\nOne student').replace('更新日期\\n2026年9月11日','Updated\\n11 September 2026')
base=base.replace("'项目名称'","'Project'").replace("'指导教师'","'Supervisor'").replace("'项目周期'","'Period'").replace("'方案范围'","'Focus'")
base=base.replace('AY 2026/2027  2026年10月至2027年5月','AY 2026/2027  October 2026 to May 2027').replace('一门课程的 RAG 内容与考核生成  含系统设计和评估计划','CA1  Literature review and course-grounded text generation')
footer=source[source.index('body.append(sect)'):]
translations={
'教学内容生成系统  单机原型架构':'Educational content generation  CA1 architecture',
'教师与学生网页':'Browser interface','资料与生成表单':'Import and author','审核与学习展示':'Review and learning',
'API 与任务控制':'API and task control','参数和权限校验':'Input validation','任务状态与版本管理':'Task state and versions',
'检索与生成流程':'Retrieval and generation','课程资料检索':'Course-level retrieval','难度约束与结果校验':'Demand and schema checks',
'模型能力适配':'Provider adapters','嵌入与文本生成':'Embeddings and text','语音 TTS 接口':'Media interfaces for CA2',
'持久化数据':'Persistent records','SQLite 任务与内容':'SQLite tasks and content','资料和媒体文件':'Documents and media',
'资料索引':'Source index','片段与来源页码':'Chunks and source pages','可重建向量索引':'Rebuildable vectors',
'审核后多模态':'Review and evidence','审核文本生成语音':'Approved text versions','受限概念图渲染':'Source evidence export',
'审核后的内容版本':'Reviewed content version',
'文字校验与人工审核完成后，再触发媒体转换；媒体失败不阻断文字浏览。':'CA1: text generation with course evidence and human review. Media validation follows in CA2.',
'边界：一门课程  现有模型接口  小规模用户  不承诺生产级高可用':'Local development  |  API-based models  |  No live model results claimed',
'Single Student System Design | v0.1':'CA1 Progress Report | Working Draft',
'单人范围调整须由导师确认。':'Formal submission requirements remain subject to supervisor confirmation.',
"tmp/taskbook/architecture.png":"tmp/ca1/architecture.png",
"tmp/taskbook/content.txt":"tmp/ca1/document-text.txt",
"font=f(32)":"font=f(25)","font=f(25)":"font=f(22)","font=f(40)":"font=f(36)","font=f(30)":"font=f(27)"}
for a,b in translations.items():footer=footer.replace(a,b)
footer=footer.replace("node.set('descr','单人教学内容生成系统架构，包含网页、API、检索生成、模型接口、数据库、资料索引和多模态输出。')", "node.set('descr','CA1 architecture showing the browser, task service, retrieval and generation, model APIs, source index and evidence export.')")
refs=[]
for start,end in [(0,8),(8,len(REFERENCES))]:
 refs.append(('References'+(' continued' if start else ''), [('p',f'[{i+1}] {REFERENCES[i][1]}\n{REFERENCES[i][2]}') for i in range(start,end)]))
for kind,title,sections in [('Progress_Report','CA1 Progress Report',INTRO+LITERATURE+DESIGN+refs),('Literature_Review','Literature Review',LITERATURE+refs)]:
 filename='FYP_CA1_'+kind+'_English_v0.1.docx'
 env={'DOC_TITLE':title};exec(base.replace('FYP_Single_Student_Taskbook_and_System_Design_v0.1.docx',filename),env)
 para=env['para'];prop=env['prop'];Q=env['Q'];E=env['E'];body=env['body'];ps=env['ps'];deepcopy=env['deepcopy']
 md=['# '+title+'\n\nAI-Powered Multimodal Content & Assessment Generation for Educational Applications\n\nWorking draft · 11 September 2026\n']
 for number,(heading,blocks) in enumerate(sections,1):
  heading=f'{number} {heading}'
  p=para(heading,'h');prop(p.find(Q('pPr')),'pageBreakBefore',val='1');md.append('\n## '+heading+'\n')
  for block in blocks:
   if block[0]=='p':
    p=para(block[1]);prop(p.find(Q('pPr')),'jc',val='left');md.append(block[1]+'\n')
   elif block[0]=='sub':para(block[1],'sub');md.append('### '+block[1]+'\n')
   elif block[0]=='table':
    env['table'](block[1],block[2],[2200,3400,2600]);md.append('| '+' | '.join(block[1])+' |\n| --- | --- | --- |\n'+'\n'.join('| '+' | '.join(row)+' |' for row in block[2])+'\n')
   elif block[0]=='image':
    imgp=next(p for p in ps if p.find('.//'+Q('drawing')) is not None);body.append(deepcopy(imgp));para('Figure 1  CA1 architecture and extension points','caption')
    md.append('```mermaid\nflowchart LR\n UI[Browser] --> API[API and task control]\n API --> RAG[Retrieval and generation]\n RAG --> Models[Text and embedding APIs]\n API --> DB[(Tasks and revisions)]\n RAG --> Index[(Course sources and vectors)]\n RAG --> Evidence[Review and evidence export]\n```\n')
 exec(footer.replace('CA1 Progress Report | Working Draft',title+' | Working Draft'),env)
 (ROOT/'docs/ca1'/(kind+'.md')).write_text('\n'.join(md))
 print(title, sum(len(b[1].split()) for _,blocks in sections for b in blocks if b[0]=='p'),'prose and reference words')
# Reference index: source records, not fabricated screening counts.
manifest=json.loads((ROOT/'docs/ca1/literature/download_manifest.json').read_text())
by_id={r['id']:r for r in manifest}
with (ROOT/'docs/ca1/literature/reference_index.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['reference','key','citation','url','local_pdf','sha256','access_date'])
 for i,(key,citation,url) in enumerate(REFERENCES,1):
  p=ROOT/'docs/ca1/literature/papers'/(key+'.pdf');w.writerow([i,key,citation,url,str(p.relative_to(ROOT)) if p.exists() else '',hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else '', '2026-09-11'])
