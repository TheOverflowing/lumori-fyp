# MLQA 中英计算机知识子集

本子集含 81 个真实 Wikipedia 片段、92 条中英文问题，来自 46 个双语问题 family。使用原 MLQA 的人工问题与答案位置，没有让模型写问题或打相关性标签。它是计算机知识补充评测，**不是大学课程讲义，也不是穷尽人工检索 qrels**。

## 来源与许可

原作者：Patrick Lewis、Barlas Oğuz、Ruty Rinott、Sebastian Riedel、Holger Schwenk。来源：[作者仓库](https://github.com/facebookresearch/MLQA)、[ACL 2020 论文](https://aclanthology.org/2020.acl-main.653/)、[官方 MLQA_V1.zip](https://dl.fbaipublicfiles.com/MLQA/MLQA_V1.zip)。原文档源自相应语言 Wikipedia，逐片段保留 title、来源 URL 和原始数据成员路径。

数据许可为 [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)。本子集及派生标签沿用该数据许可，保留以上归属、来源和转换说明；作者仓库代码许可证不能替代数据许可。

论文 §2.2 说明英文众包人员编写问题、选择答案位置，并额外收集答案用于检查；§2.3 说明专业译者翻译问题并标注目标语言答案。自然 Wikipedia 段落由自动平行句挖掘配对，问题与答案标注有人参与，不应把整个数据构建流程称为全人工。

## 转换与冻结

在本子集首次向量或排名运行前，由助手只按主题选择 33 个计算机相关文章标题白名单；每篇最多保留 3 个具有原生英文/中文人工标注对应关系的 family，按原问题 ID 的 SHA256 排序。未查看检索结果来筛选问题。每一处 answer_start 都与原始 context 的答案子串核对，缺少中文人工对应的问题不翻译补造。所有候选的纳入、缺少中文配对或篇内限额原因见 selection-v1.json。

保留官方 dev/test。当前 dev 12 查询（6 family）、test 80 查询（40 family），同 family 不跨划分；翻译问题不能算 92 个独立信息需求。语料为选中问题对应的 81 个唯一段落，按文本哈希去重；保留原文，不重新切片或把答案、标题追加到检索文本。

冻结数据 SHA-256：`f086a455ca1f2638f789e7d7675af284438fbaed9cfbb854fb9b87c4a8bec21e`。官方压缩包 SHA-256：`246e8089933d13007fe80684d5c5c0713d6834cf8b3b4a0ec7c66f0a0d2baac8`。

## 指标如何解释

每条问题把其人工英文和中文答案所在的两个段落设为已知正例，放进一个“二者任选其一”的证据组。于是 Recall@k 表示已知答案来源覆盖，all_evidence@k 在此只等于 Hit@k。其他段落未经这个问题的穷尽相关性判断，不是人类确认的负例。

查询在中英混合片段库中检索；既能找同语言也能找另一语言，不是强制跨语言检索。这个任务不同于原 MLQA 的答案跨度 F1/EM，不能与官方榜单分数比较。还需考虑小样本、相关翻译问题、子集选择与公开数据可能进入模型训练的未知情况。

## 复现

构建脚本为 scripts/build_mlqa_cs_benchmark.py；只用标准库解析已下载的 zip，不调用模型。默认主程序拒绝覆盖已有冻结数据；纯函数 `build(archive_path)` 返回数据与选择记录，可用于离线一致性核验。source-manifest.json 保存原始压缩包、生成数据、选择记录和构建代码快照的校验值。

实验使用 [R2 固定协议](../../../../docs/rag/EXTERNAL_DATA_PROTOCOL_V1.md)，不与原自编 pilot 合并统计。
