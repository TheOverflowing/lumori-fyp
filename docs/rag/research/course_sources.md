# 真实本科计算机课程材料来源核验

核验日期：2026-09-12。范围是可以保存、分段和用于本项目非商业研究的真实教材文本；免费浏览本身不作为再利用许可。

## 本轮已选择的中英文来源

| 来源 | 学科与语言 | 可核实许可 | 人工检索标注现状 |
|---|---|---|---|
| [Hello 算法作者仓库](https://github.com/krahets/hello-algo) | 中文数据结构与算法入门教材，覆盖搜索、哈希、树、栈、图、排序。它是作者维护的公开教材，不将其称为某大学官方课程。 | 仓库 README 明确说明文本、代码、图片等采用 CC BY-NC-SA 4.0；保存 LICENSE，保留作者署名、来源、非商业和相同方式共享条件。 | 查看的官方仓库提供教材与练习，但未找到发布的 query → relevant passage 人工相关性标签。状态为 pending human review。 |
| [Virginia Tech OpenDSA](https://opendsa.cs.vt.edu/) / [官方内容仓库](https://github.com/OpenDSA/OpenDSA) | 英文课程电子教材，面向数据结构和算法教学，含模块、可视化及练习，适合补充独立于中文教材的表述与例子。 | [官方许可页](https://opendsa.cs.vt.edu/home/license) 明确同时覆盖 content source；下载的 MIT-license.txt 以及具体 RST 文件头均声明 MIT。保存原始许可和文件内作者声明。 | 有教师编写的练习与答案机制，不能据此推断存在检索 qrels。查看的官方材料未提供所需的段落级人工 gold，状态为 pending human review。 |

固定版本与逐文件 SHA-256 见 [源材料 manifest](../../../benchmarks/rag/course_sources/manifest.json)。本轮只导入每种语言各 6 篇原始文本，未下载学生记录、作答历史或个人数据。只应就这些已核实文件的许可作出判断，不把一个根许可证自动延伸到仓库包含的所有第三方素材。

## 可复现的最低下载方式

无需爬取整站，也无需安装两套教材的构建系统。按固定 commit 下载单个 UTF-8 文本，保存原始字节和 SHA-256 即可：

- Hello 算法 commit：`28c1e74c1d3594fca7cc41b78a6bd18b700c5ce9`。例如 [二分查找 Markdown 原文](https://raw.githubusercontent.com/krahets/hello-algo/28c1e74c1d3594fca7cc41b78a6bd18b700c5ce9/docs/chapter_searching/binary_search.md)。
- OpenDSA commit：`347b2872a70eb4b10e20f2a91ffd131656de8266`。例如 [Insertion Sort RST 原文](https://raw.githubusercontent.com/OpenDSA/OpenDSA/347b2872a70eb4b10e20f2a91ffd131656de8266/RST/en/Sorting/InsertionSort.rst)。
- 每个文件的确切下载地址、仓库路径、本地路径、长度和校验值都在 manifest 中。两份许可证与原文一同保存。

这些是文本来源；Markdown 中的图片、代码导入宏，以及 RST 中的图示、交互练习、代码导入指令并没有自动展开。因此本批次只支持由导入文字本身充分回答的问题。标注者不能根据网页中未导入的图示给某个文本片段判为充分证据。

## 人工标签必须另行建立

真实作者写的教材、练习题或答案，并不自动构成“问题与检索证据之间的人工标签”。本批次没有导入现成 qrels，也没有让模型扮演人工标注者。

后续使用 [人工标注说明](../../../benchmarks/rag/course_sources/ANNOTATION_GUIDE.md) 中的空白模板。由真人写问题、阅读冻结的全部候选文本、给出相关性等级与必要证据组，并记录标注者、时间和分歧处理。冻结 corpus、问题和标签后，再划分开发/测试集、运行正式比较。由助手提出的问题或建议标签必须单独记录其来源，经真人复核前不能标为 human-reviewed。

## 未选入但已核实的英文备选

[Think Python, 3rd Edition](https://allendowney.github.io/ThinkPython/chap00.html) 是 Allen B. Downey 的编程入门教材，作者网站公开 HTML/Jupyter notebooks；文本为 CC BY-NC-SA 4.0，代码为 MIT。适合下一轮扩展 Python 程序设计课程。其练习解答同样不等于段落检索人工标签。本轮不下载，避免在首批样本中同时混入过多课程与预处理方式。

## 证据来源

- Hello Algo [原始 README 许可声明](https://raw.githubusercontent.com/krahets/hello-algo/main/README.md) 与 [LICENSE](https://github.com/krahets/hello-algo/blob/main/LICENSE)。
- OpenDSA [官方许可页](https://opendsa.cs.vt.edu/home/license)、[原始 MIT 许可](https://raw.githubusercontent.com/OpenDSA/OpenDSA/master/MIT-license.txt)、[课程使用介绍](https://opendsa.cs.vt.edu/)。
- OpenDSA [模块与 RST 源目录说明](https://opendsa.readthedocs.io/en/latest/GettingStarted.html)。

本记录中的“未找到”限于本次核查范围，不主张证明这些项目的所有历史版本都不存在相关标注。
