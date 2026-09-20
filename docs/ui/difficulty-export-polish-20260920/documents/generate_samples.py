"""Re-render saved public smoke materials; no provider calls or database writes."""
from pathlib import Path
import json
import hashlib
import sys

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root))
from app.content_exports import export_material, _material_blocks
out = Path(__file__).resolve().parent
records = root / 'docs/rag/auto-exploration/ml-discovery-20260920'
samples = []
for name, filename, language in [('real-lesson-en','after-en-08.json','en'),('real-lesson-zh','after-zh-07.json','zh')]:
    record = json.loads((records / filename).read_text())
    row = {'asset':record['asset'], 'sources':record['evidence']['sources'], 'version':1}
    samples.append((name, row, language, filename))
first, second, third = ['context_' + str(number)*32 for number in (1,2,3)]
quiz = {'version':2, 'sources':[
    {'id':first,'document_id':'qa-model-evaluation','document_name':'模型评估讲义.pdf','page':1,
     'external_source':{'title':'模型评估讲义','attribution':'课程教学组','url':'https://example.edu/model-evaluation.pdf','license':'CC BY 4.0'}},
    {'id':second,'document_id':'qa-model-evaluation','document_name':'模型评估讲义.pdf','page':2,
     'external_source':{'title':'模型评估讲义','attribution':'课程教学组','url':'https://example.edu/model-evaluation.pdf','license':'CC BY 4.0'}},
    {'id':third,'document_id':'qa-optimization','document_name':'优化算法讲义.pdf','page':7},
], 'asset':{
    'title':'机器学习基础练习与参考答案',
    'learning_objectives':['区分训练集、验证集与测试集的用途。','解释梯度下降中的学习率与参数更新。'],
    'sections':[
        {'heading':'模型评估', 'text':f'训练集用于学习参数，验证集用于选择模型或调整超参数，测试集用于最终评估。合理划分数据可以减少测试信息进入训练过程带来的偏差 [{first}, {second}]。\n\n过拟合可能表现为训练准确率持续提高，而验证准确率下降。分析时应同时考虑数据质量、模型复杂度和训练过程 [{second}]。', 'citation_ids':[first,second]},
        {'heading':'参数更新', 'text':f'梯度下降更新可写为 θ ← θ − η∇L(θ)。学习率 η 控制更新幅度。符号 ∑ xᵢ 表示将相关元素相加 [{third}]。', 'citation_ids':[third]},
    ],
    'questions':[
        {'stem':f'模型选择完成后，哪组数据最适合估计泛化表现？[{first}]','options':['训练集','测试集','重复使用的验证集','训练日志'],'answer':'B','explanation':f'测试集应保留到模型选择完成后再使用 [{second}]。','citation_ids':[second]},
        {'stem':'训练准确率提高但验证准确率下降时，可以考虑什么原因？','options':[],'answer':'可能发生了过拟合。','explanation':f'模型可能逐渐记住训练样本中的偶然特征。可结合验证误差，考虑正则化、模型复杂度和训练轮次 [{first}, {second}]。','citation_ids':[first,second]},
    ]}}
samples.append(('grouped-quiz-zh', quiz, 'zh', 'isolated-layout-fixture'))
summary=[]
for name, row, language, source in samples:
    original=json.dumps(row,ensure_ascii=False,sort_keys=True)
    bibliography=[block.text for block in _material_blocks(row,True,language)[2] if block.kind=='bibliography']
    for format in ('pdf','docx'):
        result=export_material(row, format, language=language)
        (out / f'{name}.{format}').write_bytes(result.data)
    assert json.dumps(row,ensure_ascii=False,sort_keys=True)==original
    summary.append({'sample':name,'input':source,'source_chunks':len(row['sources']),
                    'document_references':len(bibliography),'references':bibliography,
                    'input_sha256':hashlib.sha256(original.encode()).hexdigest(),'source_unchanged':True})
(out / 'source-grouping.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{k:v for k,v in item.items() if k!='references'} for item in summary],ensure_ascii=False,indent=2))
