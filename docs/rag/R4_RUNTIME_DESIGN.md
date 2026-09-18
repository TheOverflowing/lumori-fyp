# R4 选定策略的后端接入

已于 2026-09-12 激活 `api8b_none`：开发集选择与新保留集门槛通过，534 项测试及真实双语检索通过。结果见 [R4 报告](R4_RESULTS_20260912.md)，服务状态见 [激活校验](r4-experiments/20260912T072619024568Z/activation-service-verification.json)。

## 兼容与索引身份

默认配置类保留原有字符递归切分与 raw 编码，已保存内容的 sources 继续作为不可变快照使用。
新增 token 切分候选复用与实验相同的 `token_chunks` 实现：原文片段、同节合并、无重叠、256 token 正文上限。
tokenizer 文件 SHA 进入切分配置；标题编码版本进入文档嵌入签名。修改文档表示需要重建向量，单独修改查询指令不需要。
重建必须在全部嵌入批次成功后替换索引，失败继续保留旧向量。跨课程同一文件仍生成独立片段 ID。

## 原文与模型输入

文档嵌入可使用“文件名主干 → 原文标题路径 → 原文片段”；正文、来源页码和原文字符坐标保持独立。
MLQA 实验的标题来自文章元数据，而实际应用使用上传文件名和可提取标题。这是应用映射差异，需后续课程标注验证，不能直接宣称相同收益。
查询指令使用实验冻结的英文 CS 证据检索描述，并在生成任务证据中记录编码版本。

上下文装配读取 SHA 校验通过的原始文件，基于原文页坐标去重合并。生成引用使用新的上下文 ID，并保存对应检索片段 ID 和实际起止位置。
1024 token 上限计量的是 Qwen tokenizer 下用双换行连接的原文证据，不包含其他提示词，不宣称为 DeepSeek 服务端计费 token。
模型收到正文与必要标题，完整算法诊断保留在任务证据中。

## 当前应用配置

```dotenv
CHUNK_STRATEGY=recursive_token_v1
CHUNK_MAX_TOKENS=256
CHUNK_OVERLAP_CHARS=0
RETRIEVAL_DOCUMENT_ENCODING=title_path_v1
RETRIEVAL_QUERY_ENCODING=cs_instruction_v1
RETRIEVAL_STRATEGY=hybrid_dense_lexical_v1
RETRIEVAL_CANDIDATE_K=20
RETRIEVAL_TOP_K=5
RETRIEVAL_CONTEXT_TOKENS=1024
RETRIEVAL_EXPANSION=none
RERANK_BASE_URL=https://openrouter.ai/api/v1
RERANK_MODEL=qwen/qwen3-reranker-8b
RERANK_PATH=/rerank
RERANK_USE_EMBEDDING_KEY=true
```

准确分词需要 tokenizers==0.22.2 与已冻结的 Qwen tokenizer 文件；研究用 Torch/Transformers 在独立 `.venv-rag` 中。
应用调用真实的 OpenRouter `/rerank`，严格校验返回索引、数量和有限数值，再取重排后的 Top5。使用同一网关复用嵌入密钥，拒绝跨网关复用。调用状态、HTTP 状态、实际模型名、耗时与白名单用量写入原有 calls 表；失败不自动重试。本轮保留集重排平均 700.1 ms。

新环境运行 `.venv/bin/python scripts/prepare_rag_tokenizer.py` 即可下载并校验固定 tokenizer，应用不需要 Torch 或本地重排权重。修改标题编码或 tokenizer 切分需要重新建立文档索引；只改查询指令不改变文档向量身份。

## 验证要点

- 文档编码变更使旧索引过期；查询指令变更不错误触发重建。
- 每个上下文的实际文本等于对应原文页切片，且总 token 数不超预算。
- tokenizer 变化使 token 切分配置过期，不能把旧向量误标为新配置。
- 异常配置在调用外部模型之前失败；索引失败不删除旧索引。
- 旧内容引用快照、资料归属与课程过滤保持有效。
- 实验排名在冻结代码下重放；应用代码接入后不能用新实现冒充原冻结运行。
