# 前端响应与滚动优化 · 2026-09-23

采用 apple-design 的即时响应与 emil-design-eng 的减少无效动画/布局工作原则。保持原有界面结构，通过代码检查、隔离浏览器对照和行为回归定位具体开销；没有调用模型或修改用户课程资料。

| Before | After | Why |
| --- | --- | --- |
| 自动增高文本框在边缘阻止滚动传递 | 允许滚动继续传递给页面，弹窗边界保留隔离 | 修复鼠标/手指停在输入框上时页面不动的体验 |
| 每次输入、点击都会重新测量全部文本框 | 只测量值/宽度变化的字段；批量读写布局 | 避免长编辑表单中反复触发同步布局 |
| 单条资料变化重建整个列表 | 按稳定 ID 保留未变化行，只替换变化行 | 减少 DOM、布局与绘制工作，保留未变化控件和焦点 |
| 导航立即清空页面；旧读请求继续进行 | 快请求直接替换结果，超过 120 ms 才显示加载状态；离开时中止请求 | 减少短暂闪屏与无效网络工作；导航仍可随时再次切换 |
| fixed 背景、大面积工具栏模糊、按钮/弹窗多层模糊 | 独立静态背景层、渐变工具栏、小范围侧栏模糊、清晰内容表面 | 降低滚动经过浮层时的绘制压力 |
| 引用浮层每次 scroll 都测量/定位 | 每帧最多定位一次；不重复写入未变化尺寸 | 防止高频滚动事件反复触发布局 |
| 每一行日期都新建格式化器；键盘模式反复写全局属性 | 复用按语言创建的格式化器，只在输入方式改变时更新属性 | 减少列表渲染与连续输入时的样式工作 |
| 所有静态资源 no-store | 公共静态资源 ETag 强制重新校验，可返回 304；账号数据继续 no-store | 减少刷新时重复传输，同时防止长期使用旧代码 |

## 浏览器对照

使用 `scripts/frontend_performance_fixture.py`：虚构 80 条资料和独立的 80 字段表单；旧版静态文件保存在 `/private/tmp/lumori-frontend-before-20260923/static`。原始测量和前后源码 SHA-256 见 [measurements.json](frontend-performance-20260923/measurements.json)。

- 修改一个字段：`scrollHeight` 布局读取 **80 → 1**。
- 单条资料被后台轮询更新：替换行数 **80 → 1**；移除/加入的元素数分别为 **1922 → 24**。
- 390 × 844 视口，从学习目标输入框内部同一位置向下滚动：原 `contain` 样式下页面 scrollTop 为 0；改为 `auto` 后 scrollTop 为 844。检查到的页面宽度为 390，无水平溢出。
- 检查浅色、深色、中文、英文、设置弹窗、连续导航、草稿保留。实际本地工作区重新加载后样式和按 ID 更新的条目已生效，未观察到控制台错误。

这些是固定样本的工作量与行为验证，不是生产环境速度百分比。前后样本均未出现大于 50 ms 的长任务，rAF 间隔 P95 约 17–18 ms，不能据此声称帧率提升。轮询触发时刻和自动化调用耗时不同，未比较这些时长。未执行真实触屏或低端设备性能评测。

## 回归与部署

- `node --test tests/frontend*.test.mjs`：240 通过。包含输入布局批处理、稳定行身份/重排、导航取消、后台读取消、引用滚动合并。
- `.venv/bin/python -m pytest -q tests/test_deployment.py tests/test_account_isolation.py`：67 通过。
- 新增缓存测试验证静态文件 304 和空响应体，同时 HTML、账号会话、API、静态资源 404 保持 no-store。
- 本地服务在无 queued/running 任务时重启，`/healthz` 返回 ready。仅修改静态资源与公共缓存策略，不运行生成任务。

隔离复现：

```bash
.venv/bin/python scripts/frontend_performance_fixture.py --port 8775 --static-dir /private/tmp/lumori-frontend-before-20260923/static
.venv/bin/python scripts/frontend_performance_fixture.py --port 8776
```

打开 `/#documents` 或 `/__perf/form`，使用测试浮层的 Start sample / Read sample 记录计数。Change one source 只修改该进程内的虚构资料。该测试服务必须仅绑定 localhost，不用于正式部署。
