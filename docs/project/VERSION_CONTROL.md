# 版本管理与恢复

## 提交范围

Git 保存应用代码、测试、脚本、依赖清单、文档、报告、评测标注和可分享的实验产物。历史实验目录保留原文件与哈希；纠错通过新增说明或新实验轮次记录。

以下文件仅保留在本机，不上传 GitHub：`.env`/密钥、真实账号和课程数据库、所有 runtime 目录、虚拟环境、模型权重、tmp/备份、下载的上游大体积 zip/parquet 文件。忽略文件不会从本地删除。

因此 GitHub 是**代码和研究进度备份**，不是个人账号/资料或全部模型环境的灾备。完整恢复另需本地 `.env`、data/、模型及独立运行环境的安全备份。数据库 backup/restore 应使用 SQLite backup API，不在运行时简单复制可能尚有 WAL 的数据库文件。

原始档案中的清单可能列出本地 runtime 或下载数据；克隆后的工作区不保证这些被忽略文件存在。按来源 manifest 与准备脚本重建；不要改写旧清单来假装文件从未存在。

## 分支与标签

- `main` 保存已检查的可用状态。
- 新功能使用 `feature/<topic>`，修复使用 `fix/<topic>`；完成测试后合并。
- 当前基线：`checkpoint-2026-09-18`。标签是不可变的历史定位点，不代表全部 FYP 要求已完成。
- Git 日志从本次首次提交开始；以前的开发过程以实验记录为准。

```sh
git status
git switch -c feature/figure-retrieval-evaluation
# 修改、运行对应测试，然后只添加确实需要提交的文件
git add app tests docs
git diff --cached --stat
git commit -m "Improve figure retrieval evaluation"
git push -u origin feature/figure-retrieval-evaluation
```

修改 `.env`、data/ 等不会进入提交。不要使用 `git add -f` 强行提交这些文件。发布前仍需检查待提交内容，`.gitignore` 不能代替密钥检查。

## 验证

GitHub Actions 配置只运行无需真实 API/模型权重的认证、账号隔离、provider 和流程测试，以及前端 Node 测试。完整文档解析、RAG 对照和 live API 实验应在明确配置的本地环境运行，费用和原始证据单独归档。

```sh
.venv/bin/python -m pytest -q
node --test tests/frontend_*.test.mjs
```

新机器先参照 README 安装基础环境。MinerU、Docling 和本地 tokenizer/模型需另外准备，不能把基础依赖安装成功理解为全部研究实验可立即重现。
