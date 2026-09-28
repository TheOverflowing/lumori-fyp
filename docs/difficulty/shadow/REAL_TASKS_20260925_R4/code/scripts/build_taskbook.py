from pathlib import Path
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
from hashlib import sha256
from lxml import etree as E
from PIL import Image, ImageDraw, ImageFont

ROOT=Path('/Users/theoverflow/Downloads/FYP')
REF=Path('/Users/theoverflow/.codex/plugins/cache/openai-curated-remote/openai-templates/0.1.1/skills/artifact-template-system-design/assets/reference.docx')
OUT=ROOT/'output/FYP_Single_Student_Taskbook_and_System_Design_v0.1.docx'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';NS={'w':W}; Q=lambda n:'{'+W+'}'+n
with ZipFile(REF) as z: parts={n:z.read(n) for n in z.namelist()}
root=E.fromstring(parts['word/document.xml']); body=root.find(Q('body')); original=list(body); ps=body.findall(Q('p')); ts=body.findall(Q('tbl')); sect=deepcopy(body.find(Q('sectPr')))

def el(tag,**attrs): return E.Element(Q(tag),{Q(k):str(v) for k,v in attrs.items()})
def prop(parent,tag,**attrs):
 n=parent.find(Q(tag))
 if n is None:n=E.SubElement(parent,Q(tag))
 for k,v in attrs.items():n.set(Q(k),str(v))
 return n

def replace_p(p,text,black=False):
 rp=p.find('w:r/w:rPr',NS)
 if rp is None: rp=E.Element(Q('rPr'))
 else:rp=deepcopy(rp)
 prop(rp,'rFonts',eastAsia='Hiragino Sans GB')
 if black:prop(rp,'color',val='000000')
 for c in list(p):
  if c.tag!=Q('pPr'):p.remove(c)
 r=E.SubElement(p,Q('r'));r.append(rp)
 for i,line in enumerate(text.split('\n')):
  if i:E.SubElement(r,Q('br'))
  t=E.SubElement(r,Q('t'));t.text=line;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
 return p

def para(text,kind='body',page=False):
 idx={'body':22,'h':21,'sub':35,'list':40,'caption':33}[kind]
 p=replace_p(deepcopy(ps[idx]),text,kind in ['h','sub','caption'])
 pp=p.find(Q('pPr'))
 if kind=='sub':prop(pp,'pStyle',val='Heading2')
 if page:prop(pp,'pageBreakBefore',val='1' if text.startswith('1 ') else '0')
 if kind in ['body','caption']:prop(pp,'keepNext',val='0')
 if kind in ['h','sub']:prop(pp,'keepNext',val='1')
 if kind=='body':prop(pp,'widowControl',val='1')
 body.append(p);return p

def table(headers,rows,widths):
 template=ts[7] if len(headers)==3 else (ts[3] if len(headers)==4 else ts[2])
 t=deepcopy(template)
 for c in list(t):
  if c.tag==Q('tr'):t.remove(c)
 grid=t.find(Q('tblGrid'))
 for c in list(grid):grid.remove(c)
 for wi in widths:grid.append(el('gridCol',w=wi))
 tp=t.find(Q('tblPr'));prop(tp,'tblW',w=sum(widths),type='dxa');prop(tp,'tblInd',w=0,type='dxa');prop(tp,'tblLayout',type='fixed')
 source_rows=template.findall(Q('tr'))
 for i,row in enumerate([headers]+rows):
  tr=deepcopy(source_rows[0 if i==0 else 1+(i-1)%2]);trp=tr.find(Q('trPr'))
  if trp is None:trp=E.SubElement(tr,Q('trPr'))
  for hh in trp.findall(Q('trHeight')):trp.remove(hh)
  prop(trp,'cantSplit')
  if i==0:prop(trp,'tblHeader')
  for c,text,wi in zip(tr.findall(Q('tc')),row,widths):
   cp=c.find(Q('tcPr'));prop(cp,'tcW',w=wi,type='dxa')
   bord=prop(cp,'tcBorders')
   for side in ['top','left','bottom','right']:prop(bord,side,color='D9D9D9',sz='4',val='single')
   p=c.find(Q('p'));replace_p(p,text)
   for extra in list(c):
    if extra.tag!=Q('tcPr') and extra is not p:c.remove(extra)
   pp=p.find(Q('pPr'));prop(pp,'keepNext',val='0')
   for rp in p.findall('w:r/w:rPr',NS):prop(rp,'sz',val=20);prop(rp,'szCs',val=20)
  t.append(tr)
 body.append(t)
 p=para('');prop(p.find(Q('pPr')),'spacing',after=50,line=80,lineRule='auto')
 return t

# Template cover, preserving its recurring structure.
cover=[]
for c in original:
 if c.tag==Q('p') and ''.join(c.itertext()).find('1.  Abstract')>=0:break
 cover.append(deepcopy(c))
for c in list(body):body.remove(c)
# Remove two of the empty cover spacer paragraphs to accommodate a real project title.
removed=0
for c in cover:
 if c.tag==Q('p') and not ''.join(c.xpath('.//w:t/text()',namespaces=NS)) and removed<2:removed+=1;continue
 body.append(c)
cp=body.findall(Q('p'))
for p in cp:
 txt=''.join(p.xpath('.//w:t/text()',namespaces=NS))
 if txt=='System Name':replace_p(p,'教育内容生成',True)
 elif txt=='Title of Proposal':replace_p(p,'任务书与系统设计',True)
ct=body.findall(Q('tbl'))
for c,text in zip(ct[0].findall('.//'+Q('tc')),['文档状态\n单人方案 待导师确认','','实施人数\n1 人','','更新日期\n2026年9月11日']):
 pp=c.findall(Q('p'));replace_p(pp[0],text)
 for p in pp[1:]:c.remove(p)
coverrows=[['项目名称','AI-Powered Multimodal Content & Assessment Generation for Educational Applications'],['指导教师','Mehul Motani'],['项目周期','AY 2026/2027  2026年10月至2027年5月'],['方案范围','一门课程的 RAG 内容与考核生成  含系统设计和评估计划']]
for tr,row in zip(ct[1].findall(Q('tr')),coverrows):
 for c,txt in zip(tr.findall(Q('tc')),row):replace_p(c.find(Q('p')),txt)

# Page 2
para('1 项目任务与单人范围','h',True)
para('本项目拟开发一个面向教师和学生的教学辅助网页应用。系统以指定课程资料为依据，生成学习讲解、练习题、参考答案和解析，并支持难度设置及多模态呈现。重点验证生成结果是否正确、是否有资料支持，以及难度是否符合约定标准。')
para('原选题按两人分工设计；现按一名学生实施进行规划。本方案为导师讨论版本。课程、技术路线、样本量、工作量及验收阈值均为建议值，须在项目启动时确认；原题要求与拟调整范围分别列示。')
table(['事项','原选题要求 [1]','单人实施提案'],[
['核心生成','学习材料与测验、作业；控制难度','一门课程约 3 个章节；讲解、选择题和简答题；基础与进阶两档'],
['资料依据','集成 RAG','限定可提取文字的 PDF 或文本；保留文件、页码和段落出处'],
['多模态','文字转换为至少两种其他模态','语音和受限概念图均纳入拟定范围；概念图是否满足要求须确认'],
['界面','面向教师和学生的网页','教师生成与审核视图、学生只读学习视图；不建设完整教学管理平台'],
['阶段成果','CA1 为调研、设计及 RAG 文本原型；CA2 为完整多模态应用','保留两阶段主线；具体日期以课程通知为准'],
],[1600,3500,5100])
para('拟定交付成果','sub')
para('交付可运行网页原型、内容生成与检索流程、源代码及部署说明、测试材料与评估记录、完整项目报告和演示材料。原型需演示资料导入、生成、检查与审核、学习浏览、语音播放和视觉展示的完整流程。')
para('范围调整原则','sub')
para('优先争取限定课程、资料格式、题型和图表类型。若仍超出单人工作量，再申请将第二种额外模态转为扩展项；未获得导师确认前，不能把仅有文字和语音视为满足原题。暂不纳入模型训练、扫描件 OCR、视频生成、自动评分、学生画像、正式考试及大规模并发服务。')

# Page 3
para('2 功能需求与验收映射','h',True)
para('本页将任务拆成可演示、可检查的需求。R1 至 R8 为拟定核心范围；R6 的视觉形式需要导师认可。所有生成材料先作为草稿保存，审核后的版本才进入学生视图。')
table(['编号','功能及边界','完成证据'],[
['R1','导入单门课程的 PDF 或文本；展示解析状态和来源页码','正常文件可检索；空白、损坏或扫描件得到明确提示；失败文件不进入就绪索引'],
['R2','按章节与知识点检索资料，返回相关片段','保存检索片段 ID、资料版本和排名；越界请求不混用其他课程资料'],
['R3','生成知识讲解和两类练习，附答案、解析及引用','输出遵循字段结构；选择题只有一个正确选项；无依据内容可标记并拒绝发布'],
['R4','支持基础与进阶两档，返回难度设计理由','按统一规则人工复核；记录目标档位与实际评定档位，而非只读取模型标签'],
['R5','将已审核讲解转换成语音，保留文字稿','可播放、可重试；专业术语抽查；失败不影响文字学习'],
['R6','将适用讲解转换成受限概念关系图','节点和关系可校验、可显示；不适用时说明原因；与原文一致性有评估记录'],
['R7','支持编辑、审核、浏览与导出','修改生成新版本；旧媒体失效；学生响应不包含未开放答案；导出材料可阅读'],
['R8','记录任务状态、运行配置和测试结果','成功、失败、证据不足均有终态；可重现测试配置并统计耗时和调用量'],
],[900,4750,4550])
para('规模与质量约束','sub')
para('初始规模建议为 10 份以内资料、合计不超过 300 页、单次最多生成 5 道题，最多 2 个生成任务并行。以上是控制开发范围的提案，不是性能实测值。长任务应返回任务编号和状态；是否达到可接受响应时间由小规模试运行确定。')
para('典型验收场景','sub')
para('正常资料生成并审核后学习；检索无依据时停止出题；模型输出字段缺失时有限修复；语音服务失败时保留文本；已审核文本修改后要求重新审核并更新媒体；重复提交与程序重启不把同一结果重复发布。')

# Page 4
para('3 系统架构与技术方案','h',True)
para('采用单体应用与模块化后端，在一个部署环境内完成主要流程。外部模型能力通过适配接口调用；数据库保存任务和内容，文件目录保存原始资料和媒体，小规模向量索引保存可重建的检索数据。')
# Reuse source architecture drawing and replace its image bytes below.
imgp=next(p for p in ps if p.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing') is not None)
body.append(deepcopy(imgp));para('图 1 单人原型的组件与数据流','caption')
table(['模块','拟用方案','职责和取舍'],[
['网页与 API','服务端模板网页 + FastAPI','共用一个项目；资料导入、生成表单、审核和学习页面；避免额外维护复杂前端框架'],
['检索与生成','现有嵌入模型、文本模型和本地向量索引','按课程筛选检索片段；规则化输出与引用；先不训练模型'],
['任务与存储','SQLite + 本地文件 + 有界任务执行器','适合小规模单机原型 [3]；任务状态落盘，重启后标记中断并允许重试'],
['多模态','现有 TTS 接口 + 受限图表渲染','语音来自审核文本；图表来自结构化节点与关系，不执行模型生成的任意代码'],
],[1700,3400,5100])
para('任务执行器负责超时和并发控制；它不是分布式队列。仅用框架的后台回调不能视为持久队列或崩溃恢复机制 [4]。若导师要求本地模型推理，需先确认 GPU、模型许可与部署条件，再调整估算。')

# Page 5
para('4 资料流程与生成方法','h',True)
para('资料入库','sub')
para('上传后计算文件指纹并保存资料版本，按页提取文字，记录标题和页码。按段落或小节切块，初始候选为每块 400 至 700 tokens、相邻重叠约 80 tokens；在开发集上调整。向量与 chunk_id 对应，索引准备完成后才将该资料版本标记为可用。')
para('一次生成请求的处理顺序','sub')
for s in [
'读取用户选择的课程、章节、知识点、题型、难度和数量；验证范围后先创建持久化任务记录，并固定资料版本及生成配置。',
'以知识点和学习目标检索候选片段，按当前课程和资料版本过滤。先尝试 top_k 为 5；记录检索结果，开发集上校准证据不足的判定规则。',
'把难度规则、允许引用的片段及输出字段交给模型。要求输出讲解、题干、答案、解析、引用 ID 和难度理由；资料中的指令只作为资料文本处理。',
'程序校验字段、题目数量、选项和答案关系，以及引用 ID 是否来自本次检索。字段通过不代表语义正确；关键结论是否被资料支持仍需人工检查。',
'校验失败可修复一次；仍不合格则保留失败原因，不冒充成功。证据不足时请求补充资料或更换知识点，不用无依据答案填满题目数量。',
'保存待审核版本。教师编辑或确认后形成已审核版本；再按需生成语音和概念图。媒体与文本版本绑定，供学习页面读取。',
]:para(s,'list')
para('难度控制的可检验定义','sub')
table(['档位','设计规则','人工检查要点'],[
['基础','围绕单个概念的识别、解释或直接应用；所需前提可从资料获取','是否只需一个主要知识点；题干清楚且答案可支持'],
['进阶','对同一章节内概念作应用、比较或组合推理；明确必要条件','是否需要额外推理而非仅把句子写长；不得用超纲知识人为增加难度'],
],[1300,4500,4400])
para('上述档位是本项目的操作性定义，不等同于经学生作答校准的心理测量难度。RAG 提供检索依据 [2]，但不保证事实正确；难度理由也不是有效性的证明，两者都需独立评价。')

# Page 6
para('5 数据模型与接口约定','h',True)
para('数据关系以内容版本为中心。资料形成片段，任务生成内容版本，内容版本关联引用和媒体；评估记录绑定具体版本，避免修改后的文本继续沿用旧评分或旧语音。')
table(['实体','关键字段','关系与规则'],[
['Course / Document','id、course_id、file_hash、version、status','课程包含资料；只检索 ready 资料；每个新资料版本单独建立索引'],
['Chunk','id、document_id、page、text、index_version','一个资料对应多个片段；检索结果可以回到原文；更新后不混用旧索引'],
['GenerationJob','id、request_key、config、status、error','记录模型、提示词和资料版本、用量、耗时；同键同参数返回原任务'],
['Content / Revision','content_id、revision_id、job_id、payload、review_status','编辑创建新 revision；payload 含题型、题干、答案、解析和难度理由'],
['Citation / Media','revision_id、chunk_id 或 media_uri、status','引用关联片段；媒体记录来源文本哈希、语音或图表参数和失败原因'],
['Evaluation','revision_id、rubric_version、reviewer、scores','保存评价规则与匿名评审标识；模型评分和人工评分分开'],
],[2000,3400,4800])
para('主要接口','sub')
table(['方法与路径','输入','响应与状态'],[
['POST /documents','course_id 和文件','202 + job_id；后台解析；无效格式返回 400'],
['POST /generations','章节、知识点、题型、档位、数量、request_key','202 + job_id；重复键且参数冲突返回 409'],
['GET /jobs/{id}','任务编号','任务状态、结果 ID 或错误码；不存在返回 404'],
['GET /contents/{id}','视图权限及版本','教师取完整草稿；学生只取已审核且允许展示的字段'],
['POST /contents/{id}/revisions','base_revision_id、编辑内容或审核动作','返回新版本或审核状态；版本冲突返回 409'],
['POST /media','revision_id、audio 或 diagram','202 + job_id；只接受已审核文本；成功返回媒体位置'],
],[3200,2900,4100])
para('生成状态建议为 queued、running、succeeded、failed、insufficient_evidence。内容审核状态独立记录为 draft 或 approved。接口错误统一包含 code、message 和 retryable；“引用字段存在”与“引用确实支持结论”分别检查。')

# Page 7
para('6 多模态与用户交互设计','h',True)
para('语音转换','sub')
para('以已审核讲解及解析为输入，生成可播放音频并保留可见文字稿。公式先转换成经过检查的口语表达，术语建立小型发音表。长文本按段处理；缓存键包含内容版本、声音和语速。语音失败允许单独重试，文字结果仍可使用。')
para('视觉转换','sub')
para('第一版只支持概念关系图。模型输出 nodes 和 edges 的 JSON，程序校验唯一节点、关系端点、数量上限和文字长度，再用固定布局生成图像。建议上限为 12 个节点、18 条边。图示必须附文字说明；不适合概念图的内容允许跳过，不把所有题目强行画图。')
para('“图表是否属于原题认可的额外模态”需导师明确。如果只输出绘图提示词，不能自行认定已经完成视觉转换。若后续改成图片生成模型，需要重新估算调用成本、准确性评估和实现时间。')
para('页面与交互','sub')
table(['页面','主要操作','关键反馈'],[
['资料页','导入、查看解析结果、选择课程和章节','显示可检索状态；定位失败文件和来源页码'],
['生成页','选择知识点、题型、档位和数量','展示任务进度、失败原因及补充资料建议'],
['审核页','并排查看题目、解析和引用；编辑或确认','保留版本；未审核不得进入学生视图；修改使旧媒体失效'],
['学习页','浏览已审核材料、展开解析、播放语音和查看图示','文字始终可访问；媒体有状态；答案开放由服务端控制'],
],[1500,4600,4100])
para('运行与数据保护','sub')
para('演示版建议限制访问，教师端具备最小认证；学生只读接口不返回隐藏答案字段。仅使用获准处理的课程资料，不采集真实学生成绩。外部模型调用前确认资料使用许可和传输范围，密钥只保存在服务端配置，日志不记录密钥或整份讲义。')
para('同一 request_key 加唯一约束防止重复创建；外部调用已发生但结果未知时，不承诺精确一次计费。单次模型调用拟设置 90 秒超时、最多一次重试和输出长度上限。启动时将遗留 running 标记为中断，由用户决定重试；记录每天用量并按确认后的预算上限暂停新任务。')

# Page 8
para('7 评价方案与验收标准','h',True)
para('评价回答两个问题：检索依据能否改善内容的可核查性；明确的难度规则能否提高档位匹配度。所有实验均为计划，尚无结果。重点形成可复查的小规模证据，不据此宣称提高学生成绩或适用于所有课程。')
para('样本与对照设计','sub')
para('建议先用 10 个独立知识点作为开发集，调整切块、检索参数和提示词；冻结配置后，另用 20 个不重合的知识点作为测试集。每个测试知识点生成基础和进阶各 1 题，共 40 题／条件；在知识点间平衡选择题与简答题。')
para('设置三个条件：A 为无 RAG 且仅提供简单难度标签；B 为加入 RAG、仍使用简单标签；C 为 RAG 加明确难度规则。固定模型、输出预算、生成参数和题型分配，总计 120 次计划出题。B 对 A 考察加入检索的影响，C 对 B 考察难度规则的影响。所有条件均用相同课程资料作为评价依据。')
table(['指标','统计方法','拟定验收或报告方式'],[
['流程可靠性','40 次有效请求中，完成的次数／请求数；保留失败与重试','目标 ≥95%；固定输入上字段和引用 ID 校验均有效；这是工程目标'],
['内容正确性','已生成题目中，题干、答案及解析无实质错误的比例','人工逐题标注；同时报告正确题数／全部计划题数，防止拒答抬高比例'],
['资料支持度','被所引片段支持的关键结论数／待核查结论数','区分“有引用”和“引用支持”；记录无依据、错引和超纲案例'],
['难度匹配','人工档位与目标档位一致的题数／已评题数','给出两档混淆表；初始质量目标可讨论为 ≥80%，校准后再冻结'],
['检索命中','20 个测试知识点中，top_k 包含人工标注依据的比例','记录准确来源；与生成质量分开分析'],
['多模态一致性','从 C 抽取 10 份音频和 10 份适用图示检查','逐项检查术语、概念关系和文本一致性；样本有限，不推断总体提升'],
],[1900,4600,3700])
para('人工评价与复现','sub')
para('评审时隐藏条件标签并随机排列结果；建议由熟悉课程者独立复核至少 20% 样本。若仅由开发者自评，报告中说明偏差。模型自评只作辅助。记录模型标识、提示词、资料和索引版本、耗时及调用量；外部模型可能更新，配置可复现不代表输出逐字一致。')
para('内容正确率建议先讨论 ≥90% 的目标，再在开发阶段与导师校准并锁定，不得看完测试结果后修改标准。真实学生试用和学习效果研究不在当前默认范围；若需要，应单独安排招募、相应审批与时间。')

# Page 9
para('8 进度安排与工作量估算','h',True)
para('以下日期是以 2026年10月至2027年5月 为项目窗口的建议安排，不代表学校公布的 CA 截止日期。需求确认后先冻结核心范围；每两周保留一次可运行演示与问题记录，新增需求同时评估替换项和延期影响。')
table(['阶段与时间','任务及交付','阶段完成条件'],[
['准备 2026年9月至10月上旬','与导师确认范围、课程资料、资源和评价标准','形成确认记录；获得可用样例资料；核对正式 CA 日程'],
['M1 10月','文献调研、资料解析、检索验证','完成相关工作初稿；10 个开发知识点可追溯到原文'],
['M2 11月至12月','RAG 文本生成、难度规则、最简网页','可运行文本原型及系统设计；具备 CA1 所需材料'],
['M3 2027年1月至2月','审核版本、语音、受限概念图和页面整合','两种额外模态可演示；错误和重试路径可检查'],
['M4 3月','冻结模型与参数、运行对照实验','测试集隔离；完成 120 次计划出题及评估记录'],
['M5 4月','修复、复核、部署、报告与答辩准备','完整应用、代码、报告和演示；对齐 CA2 正式要求'],
['缓冲 5月','处理导师反馈和最终提交','保留可运行版本与复现说明；不主动增加新功能'],
],[2300,4200,3700])
para('单人投入的初步估算','sub')
para('按现有模型接口、限定资料和简单网页估算：需求与调研 25–35 小时；资料与检索 35–50 小时；生成与难度控制 45–65 小时；网页与审核 30–45 小时；语音与图表 30–45 小时；评估与修复 35–50 小时；报告与演示 30–40 小时。合计约 230–330 小时，另预留约 20% 缓冲后为 280–400 小时。')
para('若分布在约 28 个有效工作周，平均约每周 10–14 小时，集成和交付阶段可能更集中。这是用于讨论的粗估，不是课程规定或工期保证；若要求训练模型、复杂图像生成或正式学生实验，应重新估算。')
para('主要风险与调整顺序','sub')
para('资料质量不足时缩小到可解析章节；生成质量不足时减少题型和知识点；媒体质量不足时收窄图表类型。连续两个迭代未达目标时，与导师协商调整。第二种额外模态只能经确认后降为扩展项。')

# Page 10
para('9 导师确认事项与启动任务','h',True)
para('建议在第一次项目沟通中先确认下面六项，并据此形成 v1.0 任务书。学生姓名、学号及学校正式任务书表格由学生后续补入；本方案不代替课程官方表格或导师审批。')
table(['待确认事项','建议方案','对实施的影响'],[
['课程及输入范围','一门课约 3 个章节；文本型 PDF 和文本；主语言固定一种','决定解析难度、出题目标和测试材料'],
['多模态验收','语音加受限概念图；确认图表是否满足第二种模态','若要求图像生成或视频，需调整工期和评估'],
['模型及算力','允许现有模型接口；不把训练或微调设为必需项','原题列有 GPU 要求；需确认是否必须本地推理及资源来源'],
['效果评价','小规模对照实验和人工评价；不默认正式学生研究','确认评审支持、样本量和质量阈值'],
['CA 时间与个人成果','按单人完整原型和报告验收；核对两次 CA 日期','重排内部里程碑并锁定必须交付项'],
['预算和资料许可','明确接口费用承担、月度上限和课程资料处理范围','无可用接口或许可时不能照原方案推进'],
],[2100,4700,3400])
para('确认后首两周的执行安排','sub')
para('第 1 周：选定样例章节，标注 10 个开发知识点及来源，建立代码仓库与资料目录，验证提取和检索。第 2 周：用最小生成流程产出一份讲解和两道练习，人工核查答案与引用，形成演示与问题清单。先验证端到端链路，再扩展题型、界面和媒体。')
para('初始参考资料','sub')
para('[1] CEG 311 FYP选题介绍 AY2026-2027，第 27 页。本项目名称、导师、两人配置、原始范围和 CA 要求的依据。文件：CEG 311 FYP选题介绍 AY2026-2027.pdf。')
para('[2] Lewis et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS 2020. https://arxiv.org/abs/2005.11401')
para('[3] SQLite. Appropriate Uses For SQLite. https://www.sqlite.org/whentouse.html')
para('[4] FastAPI. Background Tasks. https://fastapi.tiangolo.com/tutorial/background-tasks/')

body.append(sect)

# Template-derived architecture image, same aspect ratio.
w,h=2000,1025; im=Image.new('RGB',(w,h),'#f6f9fc'); dr=ImageDraw.Draw(im)
font='/System/Library/Fonts/Hiragino Sans GB.ttc'
def f(size):return ImageFont.truetype(font,size)
navy='#0b2c49';blue='#376e96';ink='#233447'
def box(x,y,ww,hh,title,lines):
 dr.rounded_rectangle((x,y,x+ww,y+hh),radius=9,fill='white',outline=navy,width=3)
 dr.text((x+22,y+22),title,font=f(32),fill=navy)
 for i,t in enumerate(lines):dr.text((x+22,y+82+i*42),t,font=f(25),fill=ink)
def arrow(a,b):
 dr.line((a,b),fill=blue,width=5)
 import math
 ang=math.atan2(b[1]-a[1],b[0]-a[0]); L=20
 dr.polygon([b,(b[0]-L*math.cos(ang-.5),b[1]-L*math.sin(ang-.5)),(b[0]-L*math.cos(ang+.5),b[1]-L*math.sin(ang+.5))],fill=blue)
dr.rectangle((0,0,w,130),fill=navy);dr.text((48,33),'教学内容生成系统  单机原型架构',font=f(40),fill='white')
box(55,230,350,205,'教师与学生网页',['资料与生成表单','审核与学习展示'])
box(530,230,370,205,'API 与任务控制',['参数和权限校验','任务状态与版本管理'])
box(1025,230,400,205,'检索与生成流程',['课程资料检索','难度约束与结果校验'])
box(1550,230,395,205,'模型能力适配',['嵌入与文本生成','语音 TTS 接口'])
for a,b in [((405,330),(530,330)),((900,330),(1025,330)),((1425,330),(1550,330))]:arrow(a,b)
box(530,600,370,205,'持久化数据',['SQLite 任务与内容','资料和媒体文件'])
box(1025,600,400,205,'资料索引',['片段与来源页码','可重建向量索引'])
box(1550,600,395,205,'审核后多模态',['审核文本生成语音','受限概念图渲染'])
arrow((715,435),(715,600));arrow((1225,435),(1225,600))
dr.line(((1400,435),(1400,510),(1740,510)),fill=blue,width=5);arrow((1740,510),(1740,600))
dr.text((1450,533),'审核后的内容版本',font=f(23),fill=ink)
dr.text((60,880),'文字校验与人工审核完成后，再触发媒体转换；媒体失败不阻断文字浏览。',font=f(30),fill=ink)
dr.rectangle((0,968,w,h),fill='#dce8f3');dr.text((48,980),'边界：一门课程  现有模型接口  小规模用户  不承诺生产级高可用',font=f(25),fill=blue)
imgpath=ROOT/'tmp/taskbook/architecture.png';im.save(imgpath)
# Replace source drawing alt text and all inserted Chinese font fallbacks.
for node in root.xpath('.//*[local-name()="docPr"]'):node.set('descr','单人教学内容生成系统架构，包含网页、API、检索生成、模型接口、数据库、资料索引和多模态输出。')
for p in root.findall('.//'+Q('p')):
 for rp in p.findall('.//'+Q('rPr')):prop(rp,'rFonts',eastAsia='Hiragino Sans GB')
for idx,p in enumerate(root.findall('.//'+Q('p'))):
 for a in list(p.attrib):
  if 'paraId' in a:p.set(a,f'{idx+1:08X}')
parts['word/document.xml']=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
parts['word/media/image1.png']=imgpath.read_bytes()
footer=E.fromstring(parts['word/footer1.xml'])
for t in footer.findall('.//'+Q('t')):
 if 'Organization' in (t.text or ''):t.text='CEG 311 FYP | Single Student System Design | v0.1'
parts['word/footer1.xml']=E.tostring(footer,xml_declaration=True,encoding='UTF-8',standalone=True)
foot=E.fromstring(parts['word/footnotes.xml'])
for t in foot.findall('.//'+Q('t')):t.text='单人范围调整须由导师确认。' if t.text and 'Use footnotes' in t.text else t.text
parts['word/footnotes.xml']=E.tostring(foot,xml_declaration=True,encoding='UTF-8',standalone=True)
OUT.parent.mkdir(exist_ok=True)
with ZipFile(OUT,'w',ZIP_DEFLATED) as z:
 for n,data in parts.items():z.writestr(n,data)
with ZipFile(REF) as a,ZipFile(OUT) as b:
 changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
 print('Changed parts',changed)
 assert set(changed)<={'word/document.xml','word/media/image1.png','word/footer1.xml','word/footnotes.xml'}
 assert E.tostring(E.fromstring(a.read('word/document.xml')).find('w:body/w:sectPr',NS))==E.tostring(root.find('w:body/w:sectPr',NS))
text='\n'.join(root.xpath('//w:t/text()',namespaces=NS))
assert '[Describe' not in text and '[Name' not in text
(ROOT/'tmp/taskbook/content.txt').write_text(text)
print(OUT)
