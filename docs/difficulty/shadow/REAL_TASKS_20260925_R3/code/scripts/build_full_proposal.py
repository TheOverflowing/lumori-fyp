from pathlib import Path
from proposal_content import SECTIONS
source=Path(__file__).with_name('build_taskbook.py').read_text()
header=source.split('# Page 2')[0]
header=header.replace('FYP_Single_Student_Taskbook_and_System_Design_v0.1.docx','FYP_Full_Scope_Research_Proposal_API_First_v0.2.docx').replace('任务书与系统设计','课题研究方案').replace('单人方案 待导师确认','全量范围 API 优先').replace('一门课程的 RAG 内容与考核生成  含系统设计和评估计划','完整四项要求  含研究设计与提前开发计划')
exec(header)
# Keep API budget guidance with quality control to avoid a one-paragraph spill page.
SECTIONS[5][1].append(SECTIONS[4][1].pop())
md=['# 教育内容生成课题研究方案\n\n全量范围 · API 优先 · v0.2 · 2026-09-11\n']
for title,blocks in SECTIONS:
 p=para(title,'h');prop(p.find(Q('pPr')),'pageBreakBefore',val='1')
 md.append('\n## '+title+'\n')
 for block in blocks:
  kind=block[0]
  if kind=='p':
   p=para(block[1])
   if title.startswith('10 '):prop(p.find(Q('pPr')),'jc',val='left')
   md.append(block[1]+'\n')
  elif kind=='sub':para(block[1],'sub');md.append('### '+block[1]+'\n')
  elif kind=='table':
   table(block[1],block[2],[1800,4200,2200]);md.append('| '+' | '.join(block[1])+' |\n| --- | --- | --- |\n'+'\n'.join('| '+' | '.join(row)+' |' for row in block[2])+'\n')
  elif kind=='image':
   imgp=next(p for p in ps if p.find('.//'+Q('drawing')) is not None)
   body.append(deepcopy(imgp));para('图 1 全量范围的本地开发架构','caption')
   md.append('```mermaid\nflowchart LR\n  UI[教师与学生网页] --> API[API 与任务控制]\n  API --> RAG[检索与生成]\n  RAG --> Model[文字 嵌入 语音 图片 API]\n  API --> DB[(课程 任务 版本 评价)]\n  RAG --> Index[(课程片段与索引)]\n  RAG --> Review[文字审核]\n  Review --> Media[媒体生成与审核]\n  Media --> Learn[学习展示]\n```\n')
footer=source[source.index('body.append(sect)'):]
footer=footer.replace('单机原型架构','API 优先架构').replace('语音 TTS 接口','语音与图片 API').replace('受限概念图渲染','配图 API 与媒体审核').replace('参数和权限校验','参数与来源校验').replace('边界：一门课程  现有模型接口  小规模用户  不承诺生产级高可用','开发起点：课程试点  四类 API  本地原型  独立评估').replace('Single Student System Design | v0.1','Full Scope Research Proposal | v0.2').replace('单人范围调整须由导师确认。','正式验收标准须与导师确认。').replace('tmp/taskbook/architecture.png','tmp/taskbook/full_architecture.png').replace('tmp/taskbook/content.txt','tmp/taskbook/full_content.txt')
exec(footer)
(ROOT/'docs/Full_Scope_Research_Proposal.md').write_text('\n'.join(md))
