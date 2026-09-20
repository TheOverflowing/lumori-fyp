from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from app.content_exports import export_material

out = Path(__file__).resolve().parent
out.mkdir(parents=True, exist_ok=True)
first = 'context_' + '1' * 32
second = 'context_' + '2' * 32
sources = [
    {'id':first, 'document_name':'Lecture notes.pdf', 'page':4, 'external_source':{'title':'Learning from data', 'reading_url':'https://example.edu/course/learning-from-data', 'attribution':'Course teaching team', 'license':'CC BY 4.0'}},
    {'id':second, 'document_name':'机器学习课程讲义.pdf', 'page':12, 'external_source':{'title':'模型评估与数据划分', 'attribution':'课程教学组', 'license':'CC BY 4.0'}},
]
lesson = {'version':2, 'sources':sources, 'asset':{
    'title':'Machine Learning Foundations',
    'learning_objectives':['Describe how training examples support prediction.', 'Explain why test data must remain separate from training data.'],
    'sections':[
        {'heading':'Learning from examples', 'text':f'A machine learning model learns patterns from examples. Its training procedure adjusts model parameters to reduce a chosen loss. The resulting model can then produce predictions for new inputs [{first}].\n\nA training set provides the examples used to update parameters. A validation set supports model selection. The test set is reserved for the final estimate of generalization.', 'citation_ids':[first]},
        {'heading':'A gradient update', 'text':f'Gradient descent: θ ← θ − η∇L(θ); a sum may be written as ∑ xᵢ.\n\nThe learning rate η controls the size of each update. A lower training loss does not by itself establish better performance on unseen data ({first}, {second}).\n\n```python\nfor sample in training_data:\n    prediction = model(sample.features)\n    loss = criterion(prediction, sample.target)\n    parameters = parameters - learning_rate * gradient(loss)\n```', 'citation_ids':[first,second]},
        {'heading':'Remember the distinction', 'text':f'Training optimizes the model. Evaluation estimates how well it performs on examples it has not used for training. Keep a record of the split and the metric used [{second}].', 'citation_ids':[second]},
    ], 'questions':[]}}
quiz = {'version':3, 'sources':sources, 'asset':{
    'title':'机器学习基础与模型评估',
    'learning_objectives':['区分训练集、验证集和测试集的用途。', '结合具体情境解释过拟合与泛化能力。'],
    'sections':[
        {'heading':'从数据到模型', 'text':f'机器学习通过训练样本调整模型，使模型能够对新输入作出预测。训练集用于学习参数，验证集用于选择模型或调整超参数，测试集用于最终评估。三者应当合理划分，避免测试信息进入训练过程（{first}；{second}）。\n\n例如，学生可以使用历史作业数据训练一个模型，再用未参与训练的作业数据评估预测效果。评估结果依赖数据划分、任务定义和评价指标，不能只根据训练损失判断模型的实际表现。', 'citation_ids':[first,second]},
        {'heading':'理解参数更新', 'text':f'梯度下降更新可以表示为 θ ← θ − η∇L(θ)。其中 θ 表示参数，η 表示学习率，∇L(θ) 表示损失函数的梯度。求和符号 ∑ xᵢ 表示将相应元素相加。\n\n过大的学习率可能导致训练不稳定；过小的学习率可能让训练进展缓慢。需要结合验证表现和训练过程分析问题 [{first}]。', 'citation_ids':[first]},
    ],
    'questions':[
        {'stem':'在模型选择完成后，哪一组数据最适合用于估计模型的泛化表现？','options':['训练集','测试集','已用于调整超参数的验证集','所有训练日志'],'answer':'B','explanation':f'测试集应保留到模型选择完成后再使用，以减少在开发过程中反复查看测试结果造成的偏差 [{second}]。','citation_ids':[second]},
        {'stem':'某模型的训练准确率不断提高，但验证准确率开始下降。请解释可能发生了什么，并提出一个合理的改进方向。','options':[],'answer':'可能发生过拟合。可以尝试适当正则化、降低模型复杂度或使用更多具有代表性的训练数据。','explanation':f'模型可能逐渐记住训练数据中的噪声或偶然特征，而未能学到可以推广到新数据的规律。应结合数据质量、训练轮次和验证误差一起判断 [{first}, {second}]。','citation_ids':[first,second]},
    ]}}
for name, row, language in [('lesson-en',lesson,'en'),('quiz-zh',quiz,'zh')]:
    for format in ['pdf','docx']:
        item=export_material(row,format,language=language)
        path=out/f'{name}.{format}'
        path.write_bytes(item.data)
        print(path)
item=export_material(quiz,'pdf',include_answers=False,language='zh')
path=out/'quiz-zh-questions-only.pdf'
path.write_bytes(item.data)
print(path)
