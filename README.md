# 黑柩 Wiki（一个站点 · 四个站）

《黑柩》的四套整理，**同一个站点、四套独立导航、内容性质各不相同**。纯静态，发布目录是 `docs/`，
可直接托管在 GitHub Pages。

```
docs/
├─ index.html      联合首页：四站入口 + 「四个站的关系」
├─ assets/         共享样式与脚本（style.css / app.js / joint.css / lore.css / report.css）
├─ huaxu/          花絮站：作者的短篇作品（210 篇 / 346 标签 / 57 分类页）
├─ trpg/           跑团站：跑团实录（主线 12 季 + 短团 4 个 / 152 场 / 时间轴）
├─ lore/           设定站：作者的原典（13 卷 / 81 节 / 555 词条）
└─ report/         分析站：读者解读（10 份研究报告 / 126 张表）
```

四站按「**原典 → 实录 → 花絮 → 解读**」的顺序展开：

| 站 | 性质 | 内容 |
|---|---|---|
| **设定站** `/lore/` | **原典** | 作者写的《黑柩设定集·1.1版》。**要确认设定是什么，以这里为准** |
| **跑团站** `/trpg/` | **实录** | 真实发生的跑团记录，按主线／短团、场次、现实时间整理 |
| **花絮站** `/huaxu/` | **花絮与画外音** | 作者的短篇体裁作品，按人物／组织／地理／主题等维度整理 |
| **分析站** `/report/` | **读者解读** | 基于设定集的专题研究报告。⚠️ **全部由 AI 撰写，不是作者设定** |

**四站页面顶部都有跨站菜单**（可互跳）**与各自的首页**。
**标签体系各自独立**——跑团含平行世界与 if 线，同名不一定是同一实体。

**互链情况**：跑团站里的名词会链到**花絮站**的标签页（只链结构化名单字段，剧情摘要正文不链）；
**设定站暂不外链**（设定集仍在演进），但它本身接受别站链接；
分析站引用设定集，**凡与设定冲突处一律以设定为准**。

## 花絮站（`/huaxu/`）

* **210 篇**（站点 193 + docx 17），约 67.6 万字
* **一套受控标签体系**（12 个维度），共 **346 个标签**，其中若干是跨维度标签（⋈）
* 每篇一页（`huaxu/entry/<id>-<slug>.html`）；每个标签一页（`huaxu/tag/<slug>.html`）；
  **每个子分类也有一页**（`huaxu/cat/<维度>-<分类>.html`）
* 首页：**12 个栏目** + 按维度分组的全部标签（人物/组织/地理/设施已按子分类折叠，
  **所有子分类默认展开**）+ 分类浏览 + 标题与标签的轻量搜索
* **标签↔文章 相关性分级**（红/橙/蓝，见下文）
* **画外音**（平行世界线）与**楔子**（未来可能／为未来铺垫）在页面顶部有显著提示条

## 设定站（`/lore/`）

* **13 卷 / 81 节 / 555 个词条**，60.2 万汉字（源：`黑柩设定集·1.1版·DSH版.docx`）
* 页面：设定站首页、前言与编纂说明、13 个卷页、81 个节页、**555 个词条页**
* **词条页分三层**：【概述】一句话定义 →【详述】正文 →【异说】与正文不一致的说法；
  【源】与【收录范围】收在页尾折叠区
* **每卷页末尾**有「编纂备注」独立折叠区（过程记录，非设定内容）
* **跨卷同名主题**（13 组、28 处）自动加「另见」标注，两处保留、不合并
* **警告只在站首页**：剧透警告 + 吃书警告 + 版本警告（子页面不重复）
* **暂不与花絮站/跑团站互链**（设定集仍在演进），但保留回联合首页的入口

### 设定站的文件与命令

| 路径 | 作用 |
|---|---|
| `E:\黑柩\黑柩小说花絮\黑柩设定集·1.1版·DSH版.docx` | **内容源**（不随仓库分发） |
| `lore-data/` | 解析产物（**不进 git**） |
| `lore-data/versions/` | 版本归档：结构差异报告、旧 overrides |
| `tools/parse_lore.py` | docx → JSON（样式映射、页码剥离、slug 唯一化、跨卷同名自动标注） |
| `tools/lore_report.py` | 结构校验报告（目录 vs 样式交叉校验） |
| `tools/lore_diff_11.py` | **移动感知**的版本结构比对 |
| `tools/build_lore.py` | 生成设定站 |

```bash
python tools/parse_lore.py       # 解析（需先有源 docx）
python tools/lore_report.py      # 结构校验报告
python tools/lore_diff_11.py     # 与第一版比对结构（换版时用）
python tools/build_lore.py       # 生成设定站
```

> **换版方法**：新版 docx 只要沿用同一套 heading 样式即可直接解析
> （改 `parse_lore.py` 的 `DEFAULT_SRC` 与 `SOURCE_VERSION`）；
> 结构改动若已内建在 docx 里，`overrides.json` 保持空指令即可。

## 分析站（`/report/`）

* **10 份研究报告**，39.3 万汉字，**126 张表**（源：`E:\黑柩\黑柩报告\*.docx`）
* 每份一页，按「制度与法律 / 意识形态 / 北沙专题 / 集团与人物」四组分列；
  页内有**目录**、**面包屑**、**返回链接**、**站内搜索**、**回到顶部**
* **富文本保真**：标题层级（H1–H4）、表格、粗体/斜体、列表全部还原。
  报告里没有图片、高亮、底色、彩色字、脚注、批注、超链接，故无需处理
  （`齐藤优子传` 起初没用 Word 标题样式，已由设定集侧修正；解析器仍保留
  「整行加粗 + 编号」的推断兜底）
* **宽表优化**：表头行与首列**固定**，横向拖动时行列标题始终可见
* **所有报告由 AI 撰写**，站首页三条警告 + 每份报告页顶部警告条 + 页脚声明

### 分析站的文件与命令

| 路径 | 作用 |
|---|---|
| `E:\黑柩\黑柩报告\*.docx` | **内容源**（不随仓库分发） |
| `report-data/` | 解析产物（Markdown 子集，**可人工核对**；**不进 git**） |
| `data/report_site.json` | 报告目录：分组、系列编号、标题副标题、站名与警告语 |
| `tools/parse_report.py` | docx → Markdown 中间产物（含粗体/斜体/表格/列表） |
| `tools/build_report.py` | 生成分析站（含本站搜索索引） |
| `tools/audit_reports.py` | 审计 10 份 docx 的富文本构成（换版时用） |

```bash
python tools/parse_report.py     # 解析（需先有源 docx）
python tools/build_report.py     # 生成分析站
python tools/audit_reports.py    # 富文本构成审计
```

## 跑团站（`/trpg/`）

* **16 份剧情志**（**主线 12 季 + 短团 4 个**）/ **152 场** / 81.7 万汉字
* 页面：跑团首页、时间轴、16 个季/团志页、**152 个场次卡页**
* 首页与时间轴都**分「主线 / 短团」两组**——短团与主季分开归类
* 每场一张卡（**12 个字段**）：现实时间／游戏内时间／世界层／地点／在场／剧情摘要
  ／关键决策点／骰点／伤亡退场／收场状态／伏笔钩子／出处
* 季志固定十节：概览／场次索引／季摘要／登场人物／势力与组织动态／主要冲突与结局
  ／骰点统计／本季新增设定／未收伏笔汇总／完整度与存疑
  （短团用「**本团**概览」措辞，解析时归一化）
* **所有标题带分层序号**（`一、` / `（一）` / `1.` / `(1)`）；季摘要按小节折叠
* **跨站互链**：只对**结构化名单字段**（在场／地点／登场人物／场次索引）链接到花絮站标签页，
  **剧情摘要正文一律不链**。白名单 184 个标签 → 落地 1,857 条链接
* **时间轴**按现实时间排列，世界层（主世界／多层／未明）可筛选

## 四个站的关系

（联合首页也有一节同内容的说明）

* 四站共用一套视觉与导航，**内容性质不同**，按「原典 → 实录 → 花絮 → 解读」逐层展开。
* 跑团站 → 花絮站的跨站链接：只链结构化名单字段，剧情摘要正文不链。
* 设定站暂不外链（设定集仍在演进）。
* 分析站引用设定集，冲突处一律以设定为准。

## 目录

| 路径 | 作用 |
|---|---|
| `source/` | 210 个 md，一篇一文件（**花絮站的唯一内容源**） |
| `data/` | 元数据与词表（见下） |
| `tools/` | 全部脚本（打标、建站、增量、自检） |
| `docs/` | **生成物**，GitHub Pages 发布目录（可随时删除重建） |
| `trpg-data/` | 跑团解析产物（中间物，**不进 git**） |
| `lore-data/` | 设定集解析产物（中间物，**不进 git**） |
| `report-data/` | 报告解析产物（中间物，**不进 git**） |
| `trpg-src/` | 短团整理的输入包与中间稿（**不进 git**） |

## 常用命令

```powershell
# 全站一键构建（推荐）
python tools/build_all.py            # 四站 + 联合首页
python tools/build_all.py --clean    # 先清空 docs/
python tools/check_all.py            # 全站自检（1447 页 / 跨站链接 / 幂等）

# 花絮站单独
python tools/tag_entries.py          # 210 篇 → data/tags.json（含相关性分级）
python tools/build_site.py           # → docs/huaxu/（幂等：内容没变就不重写，保住 mtime）
python tools/check_site.py           # 花絮站自检：页面齐全、无死链、客户端聚合一致
python tools/tag_audit.py            # 打标自检：挑出「可能漏标」的篇目 → data/tag_audit.md
python tools/check_subcategories.py  # 子分类校验：错名/跨维度错放（错误）、漏项/多分类（提示）

# 跑团站单独
python tools/parse_trpg.py           # 剧情志 md → trpg-data/
python tools/build_trpg.py           # → docs/trpg/

# 设定站单独
python tools/parse_lore.py           # 设定集 docx → lore-data/
python tools/build_lore.py           # → docs/lore/

# 分析站单独
python tools/parse_report.py         # 报告 docx → report-data/
python tools/build_report.py         # → docs/report/
```

本地预览（任选）：

```powershell
python -m http.server 8000 --directory docs
# 然后打开 http://localhost:8000/        联合首页
#                  http://localhost:8000/huaxu/
#                  http://localhost:8000/trpg/
#                  http://localhost:8000/lore/
#                  http://localhost:8000/report/
```

> **搜索功能需要 HTTP**（用 `fetch` 读索引），直接双击 `.html` 打开时搜索不可用，其余功能正常。

## 增量更新

```powershell
# 只重建花絮站（改了某篇 md 或词表后）
python tools/build_site.py

# 只在打标规则/词表变动后需要
python tools/tag_entries.py && python tools/build_site.py

# 跑团 / 设定 / 报告：源在 E:\黑柩\ 下，改了源之后
python tools/parse_trpg.py   && python tools/build_trpg.py
python tools/parse_lore.py   && python tools/build_lore.py
python tools/parse_report.py && python tools/build_report.py
```

四个站的构建都是**幂等**的：内容没变就不重写文件（保住 mtime），所以可以放心反复跑。

## 数据文件说明

| 文件 | 内容 |
|---|---|
| `data/tags.json` | **核心**：346 个标签的定义、维度、所属子分类、篇目归属与相关性分级 |
| `data/subcategories.json` | 每个维度的子分类（人物 38 / 组织 9 / 地理 4 / 设施 6） |
| `data/site.json` | 站名、副标题、域名、免责声明、**友情链接** |
| `data/report_site.json` | 分析站的报告目录（分组、系列编号、标题副标题、站名与警告语） |
| `data/vocab_*.json` | 各维度的词表（打标用） |
| `data/taxonomy_overrides.json` | 人工覆盖的分类修正 |
| `data/featured.json` | 首页精选（12 个栏目） |
| `data/classmap.txt` | 分类映射的文本视图（可手改，见「怎么快速改归类」） |

## 标签体系与防漂移

标签体系是**受控词表**：只有 `data/vocab_*.json` 与 `data/tags.json` 里登记过的名字才会成为标签，
避免同义词漂移（例如「进盟」与「进化者同盟」是两个不同的写法，分别登记）。

### 调参位置

| 想改什么 | 改哪里 |
|---|---|
| 某个标签属于哪个子分类 | `data/subcategories.json` 或 `data/classmap.txt` |
| 某个标签归到哪一篇 | `data/tags.json` 的 `entries` |
| 相关性分级（红/橙/蓝）的阈值 | `tools/grading.py` |
| 首页栏目 | `data/featured.json` |

### 子分类

人物 / 组织 / 地理 / 设施四个维度有子分类，**每个子分类有独立页面**（`huaxu/cat/…`）。
作者在 `tools/sorter.html` 里手工归类（可拖拽、支持一个标签进多个袋子）。

### 分类器（石头扔袋子）

`tools/sorter.html` 是一个**离线可用的网页工具**：拖石头进袋子、按数字键扔进对应袋子、
拖到视口边缘自动滚屏、Ctrl/Alt + 拖 = 复制（一个标签进多个袋子）。
结果导出为 JSON，再用 `tools/apply_sorter_export.py` 落回 `data/`。

见 [`石头扔袋子-说明.md`](石头扔袋子-说明.md)。

### ⚠️ 「帝国」是两个不同的政体（务必区分）

| 名称 | 指什么 |
|---|---|
| **神圣希望帝国**（`帝国`） | 希联夜都军政府独立而成，AI「机皇」与帝国议会共掌 |
| **斯卡雷特帝国** | 原星在星都旧土上建立的血族政权 |

两者**不是同一个实体**，标签与链接都分开。

### 一个标签可以属于多个子分类

例如「启示录教团」既是宗教团体、也出现在政党袋里。
`tools/check_subcategories.py` 会校验错名与跨维度错放。

### 标签 ↔ 文章 相关性分级（红 / 橙 / 蓝）

**只给实体类标签**（人物／组织／地理／设施）分级，**确定性公式、零模型调用**：

| 级别 | 含义 |
|---|---|
| 🔴 **红** | 该标签是这篇文章的**核心**（标题级或高频主体） |
| 🟠 **橙** | **重要配角**（有实质戏份，但不是主线） |
| 🔵 **蓝** | **提及**（只出现名字或一笔带过） |

判定依据：出现频次 / 占全文比例 / 在该篇内的排序 / 说话人命中次数。
实现见 `tools/grading.py`。

## 怎么快速改归类（不用编辑 JSON）

```powershell
# 双击 tools/sorter.html 用浏览器打开（离线可用）：
#   · 拖石头进袋子 / 先点石头再点袋子 / 按数字键 1-9 扔进对应袋子
#   · 拖到视口上下边缘会**自动滚屏**（能拖到屏幕外的袋子）
#   · 点袋子名 = 改名；「+ 新建袋子」= 加类目；拖石头到虚线框 = 建新袋子并放进去
#   · Ctrl/Alt + 拖 = 复制（一个标签进多个袋子，石头上显示 ⧉）
#   · 「+ 新建石头」= 加一个还没有篇目的标签；拖到底部 🗑 = 从所有袋子拿出
#   · 自动存在浏览器本地，关掉再开能接着弄；有撤销、连击、进度条
#   · 弄完点「导出/复制结果」或「下载 JSON」
```

也可以直接改文本：

```powershell
# 打开 data/classmap.txt，把行首数字改掉（0＝未分类），只改要动的行也行
python tools/apply_classmap.py
```

## GitHub Pages

**本仓库没有配置 GitHub Actions**（无 `.github/` 目录），所以**推送不会触发任何工作流**。

发布方式是「**本地构建 → 提交 `docs/` → 从 `main` 分支直接发布**」：

| 项 | 值 |
|---|---|
| 仓库 | `darkcoffin-wiki.github.io`（**用户主页仓库**，推送即发布，无需配 Pages 的 Source/Branch） |
| 发布目录 | `main` 分支的 `/docs` |
| 兜底文件 | `docs/CNAME`（自定义域名）、`docs/.nojekyll`（让 GitHub 不跑 Jekyll） |

> 站内链接全部是**相对路径**，所以无论走默认网址还是自定义域名，都不会有路径问题。

## 部署

**方式**：本地构建 → 提交 `docs/` → 从 `main` 分支发布。
用**用户主页仓库** `darkcoffin-wiki.github.io`，推送即发布。

| 网址 | 值 |
|---|---|
| 默认 | `https://darkcoffin-wiki.github.io/` |
| 正式（阿里云域名） | `https://darkcoffin-wiki.hubingsf.cn/` |

**完整流程见 [`发布指引.md`](发布指引.md)**（含建仓库 → 推送 → DNS → 自定义域名 → HTTPS → 排查）。
摘要：

| 步骤 | 在哪做 |
|---|---|
| 建公开仓库 `darkcoffin-wiki.github.io`（名字要一字不差） | GitHub 网页 |
| `git init/add/commit/push`（认证用浏览器授权） | 本地 |
| 加 CNAME 记录：`darkcoffin-wiki` → `darkcoffin-wiki.github.io` | 阿里云云解析 |
| Custom domain 填 `darkcoffin-wiki.hubingsf.cn`，证书签好后勾 Enforce HTTPS | 仓库 Settings → Pages |

推送（**会把本地攒的所有提交一次性推上去**）：

```powershell
python tools/check_all.py
git add -A
git commit -m "改动说明"
git push
```

> `trpg-data/`、`lore-data/`、`report-data/`、`trpg-src/` 都在 `.gitignore` 里，
> `git add -A` **不会**把中间产物提交进去。
>
> 若遇到 `dubious ownership`（`.git` 属主与当前用户不一致）：
> `git config --global --add safe.directory E:/DSHwork/heijiu/wiki`

## 其他文档

| 文档 | 状态 | 内容 |
|---|---|---|
| [`发布指引.md`](发布指引.md) | **现行** | 建仓库 → 推送 → DNS → 自定义域名 → HTTPS → 排查 |
| [`本地检查清单.md`](本地检查清单.md) | **现行** | 每次改完该看什么（四站版，约 5 分钟） |
| [`石头扔袋子-说明.md`](石头扔袋子-说明.md) | **现行** | 分类器工具 `tools/sorter.html` 的用法 |
| [`Phase2-交接.md`](Phase2-交接.md) | 历史 + 决策记录 | 各阶段决策记录仍有参考价值；**开头数字是当时的**，以本 README 为准 |
| [`交接操作指引.md`](交接操作指引.md) | 历史 | 早期阶段的操作指引 |
| [`语料交接.md`](语料交接.md) | 历史 | 语料切分阶段的交接 |
| [`项目说明书.md`](项目说明书.md) | 历史 | 早期版本的项目说明 |
| [`问答卡-标题连连看.md`](问答卡-标题连连看.md) / [`问答卡-第1批.md`](问答卡-第1批.md) | 素材 | 早期人工核对用的问答卡 |
| [`legacy-scripts-removed.md`](legacy-scripts-removed.md) | 归档清单 | 已删除的 52 个根目录早期脚本清单（便于找回） |

> **判断「现行 / 历史」的简单标准**：提到「一个站点四个站」和 `/report/` 的是现行；
> 只提「两个区」「两站」「12 季 / 113 场」的是历史。

### 根目录已清理（2026-10-16）

原先根目录有 **52 个早期一次性脚本**（`build_v5.py`、`parse_v3.py`、`match_autos3.py`、
`probe_*.py`、`fix_*.py` 等，约 171 KB），是开发早期的调试/试验脚本。
它们**没有任何一个被 `tools/` 引用**，当前站点也完全不依赖，已**全部删除**。

删除清单留在 [`legacy-scripts-removed.md`](legacy-scripts-removed.md)，需要时可从 git 历史找回：

```powershell
git log --diff-filter=D --name-only        # 看哪些文件被删过
git show <旧commit>:<文件名> > 恢复的文件   # 取回某个文件
```

现在根目录只保留：`.gitignore`、`README.md`、几份 `.md` 文档、
`push-with-token.ps1`，以及 `tools/` `data/` `source/` `docs/` 四个目录。

## 数据来源与许可

内容来自《黑柩》的花絮、跑团记录与设定集，以及作者提供的 docx。**版权归原作者**；
本仓库只做索引、打标与排版，**不含设定集全文**。

四站的内容源都在本地 `E:\黑柩\` 下，仓库里只保留**解析器与生成器**（谁需要谁重跑）。

> **免责声明**：本网站由 AI 生成，内容准确性无法完全保证。
> （作者要求标注；已显示在全站每一页的页脚与首页显眼处。）
>
> **分析站另有一层声明**：该站全部报告由 AI 撰写，属**读者分析**，**不是作者设定原文**。
