# 黑柩花絮 Wiki

《黑柩》花絮、楔子与画外音的整理站。**纯静态**，发布目录是 `docs/`，可直接托管在 GitHub Pages。

* **210 篇**（站点 193 + docx 17），约 67.6 万字
* **一套受控标签体系**（12 个维度），共 **338 个标签**，其中 **7 个是跨维度标签**（⋈）
* 每篇一页（`docs/entry/<id>-<slug>.html`）；每个标签一页（`docs/tag/<slug>.html`）；
  **每个子分类也有一页**（`docs/cat/<维度>-<分类>.html`）
* 首页：**12 个栏目** + 按维度分组的全部标签（人物/组织/地理/设施已按子分类折叠）
  + 分类浏览 + 标题与标签的轻量搜索
* **画外音**（平行世界线）与**楔子**（未来可能／为未来铺垫）在页面顶部有显著提示条

### 叙事层级的定义（作者 2026-10-14 定稿）

> **楔子 = 未来可能发生的事情，或已经发生并为未来做铺垫的事情。**
> 画外音 = 平行世界线中可能发生的剧情。花絮 = 已经发生或很可能发生的剧情。

### 跨维度标签（⋈）

一个标签可以同时属于多个维度，**不做收敛**——同一标签在不同视角下身份不同：

| 标签 | 维度 | 篇数 |
|---|---|---:|
| 中分山 / 日本街 / 走廊区 | 地理 + 剧情线 | 38 / 32 / 14 |
| 富贵集团 / 光胜集团 | 组织 + 剧情线 | 29 / 14 |
| 长歌 | 文类 + 剧情线 | 31 |
| 背叛 | 关系 + 主题词 | 7 |

首页有专门的「跨维度标签」区块，各维度分组下这些标签也会带 ⋈ 出现。

## 目录

| 路径 | 作用 |
|---|---|
| `source/` | 210 个 md，一篇一文件（**唯一的内容源**） |
| `data/` | 元数据与词表（见下） |
| `tools/` | 全部脚本（打标、建站、增量、自检） |
| `docs/` | **生成物**，GitHub Pages 发布目录（可随时删除重建） |
| `_site_raw/`、`_site_text/` | 站点 HTML 快照与解析后的全文（切分阶段的中间物，保留备查） |

## 三个命令

```bash
python tools/tag_entries.py      # 210 篇 → data/tags.json、data/slugs.json、data/tag_report.md
python tools/build_site.py       # → docs/（幂等：内容没变就不重写，保住 mtime）
python tools/check_site.py       # 自检：页面齐全、无死链、客户端聚合一致
python tools/tag_audit.py        # 打标自检：挑出「可能漏标」的篇目 → data/tag_audit.md
python tools/check_subcategories.py  # 子分类校验：错名/跨维度错放（错误）、漏项/多分类（提示）
```

本地预览（任选）：

```bash
python -m http.server 8000 --directory docs
```

## 增量更新

作者发布新花絮后：

```bash
python tools/update.py --check   # 先看有哪些新文件
python tools/update.py           # 登记（延续编号）+ 只对新增条目打标 + 重建站点
```

**id 纪律**：新条目延续 `hx-NNN` 编号，**绝不重排既有编号**，否则旧链接失效。

## 数据文件说明

| 文件 | 内容 | 谁生成 |
|---|---|---|
| `entries.json` | 210 篇元数据（id/标题/类型/合集/来源/字数/哈希） | `fix_hashes.py` / `update.py` |
| `tags.json` | 条目→标签、标签→条目（**打标结果的主文件**） | `tag_entries.py` |
| `slugs.json` | 中文标签 → 英文 slug | `tag_entries.py` |
| `vocab_people.json` | 受控人名词表（178 person + 477 剔除项） | 生成后**人工审核**，不要随意重跑 |
| `vocab_entities.json` | 组织/地理/设施/剧情线词表 | 同上 |
| `vocab_dimensions.json` | 主题/事件/关系/基调/时间 的关键词表 | 同上 |
| `taxonomy_overrides.json` | **归并表**：异写 → 规范写法、噪声剔除、同名降级、分面顺序 | **人工维护**，改它就能改打标结果 |
| `pinyin_overrides.json` | **多音字读音覆盖**（长歌→chang-ge，长老→zhang-lao） | **人工维护**，影响 slug |
| `subcategories.json` | **子分类定义**（维度 → 子分类 → 标签） | **人工维护**，未列出的标签自动进「未分类」 |
| `featured.json` | 首页栏目（名称/介绍语/精选） | **作者圈定** |
| `pinyin_table.json` | 汉字→拼音（来自 Unihan kMandarin，用于 slug） | `build_pinyin.py` |

## 标签体系与防漂移

12 个维度：文类 / 叙事层级 / 人物 / 组织 / 地理 / 设施 / 剧情线 / 主题 / 事件类型 / 关系 / 主题词 / 时间 / 篇幅。

其中 **文类、叙事层级、篇幅是机械提取**（零歧义）；**人物/组织/地理/设施/剧情线走受控词表匹配**；
**主题/事件/关系/基调/时间走受控关键词表**。

防漂移的三层：

1. **受控词表**（`vocab_*.json`）——标签只能来自词表，脚本不会自创标签；
   跑完 `tag_entries.py --report` 会列出「词表外标签」，当前为 **0 个**。
2. **归并表**（`taxonomy_overrides.json`）——`乙醇→余烬`、`伊森→三井伊森`、`齐藤→齐藤优子`、
   `北沙镇→北沙`、`临时政府→戡乱政府` 这类都在这里，是**可审的显式决定**，不是藏在代码里的规则。
3. **人名判别**（`tools/name_audit.py`）——用「是否出现在 `名字：` 发言位」区分真名与同形词
   （如 `容易`、`望风` 被识别为普通词并剔除）。

### 调参位置

* 想改某篇的标签 → 改 `taxonomy_overrides.json`，重跑 `tag_entries.py`
* 想调维度命中阈值 → `tools/tag_entries.py` 里 `tag_one()` 的 `floor` 与 `auto_min()`
* 想加新标签 → 加进对应 `vocab_*.json`（并把规范写法与异写填好），重跑即可
* 想让某标签同时属于多个维度 → 在两个维度的词表里都写上它（会显示为 ⋈）
* 想让某标签在某个维度上不出现 → `taxonomy_overrides.json` 的「同名降级」
* slug 读音不对（多音字） → 改 `pinyin_overrides.json`，然后
  `python tools/tag_entries.py && python tools/build_site.py --clean`
* 想加子分类 → 改 `subcategories.json`，重跑 `build_site.py`

### 子分类

`data/subcategories.json` 声明「维度 → 子分类 → 标签」。首页该维度会变成可折叠的子分类块，
**没列出的标签自动落到「未分类」**——所以加新标签不会漏，你看到「未分类」里有东西再归类即可。

目前做了 **4 个维度、33 个子分类**：

| 维度 | 子分类 |
|---|---|
| 人物（171） | **19 组**：主角团队／斯卡雷特家族与斯卡雷特帝国／希共与希联政府／北沙政权与社会／日本街／中分山／通雷帮与第一特区／惊虎帮／天堂物流／富贵集团／光胜集团／希联军警与治安／教团国·教皇与十三圣人／蚀血教与人造血族／黑旗·蛛眼小队／神圣希望帝国／深黑军团／玩家与穿越者／其他与客串 |
| 组织（58） | 政党／政府机构／军队与准军事／企业／宗教团体／帮派／家族／媒体与文艺／神圣希望帝国与深黑军团 |
| 地理（24） | 国家与政体／城市／区域／自然地物 |
| 设施（24） | 院校与科研／商业与娱乐／政务与公共 |

### ⚠️ 「帝国」是两个不同的政体（务必区分）

作者明确要求区分，正文里简称都写作「帝国」：

| 标签 | 篇数 | 匹配写法 | 有这些角色 |
|---|---:|---|---|
| **神圣希望帝国** | 68 | `帝国`、`神圣希望帝国`、`夜都帝国` | 机皇、俾斯麦、谢尔盖 |
| **斯卡雷特帝国** | 23 | `斯卡雷特帝国`、`前斯卡雷特帝国` | 李伊、原星、风薰、原知、亚顿 |

裸「帝国」归**神圣希望帝国**（设定集卷五写明「帝国＝神圣希望帝国／夜都帝国」，且帝国议会、
帝国首相、帝国机皇都是它的）。原先那个含混的 `帝国` 标签已不存在。

**人物分组按作者官方口径**，来源是两份权威材料结合（以站点为主干，因其更细且贴合篇目）：

* **站点「人物介绍」**（darkcoffin.hubingsf.cn/characters）的 21 个分组
* **设定集卷八「人物志」**的 8 个分组（用于补漏与交叉验证）

每个分类页都会显示自己的**分组依据**（如「站点『小说宇宙主角团队』+ 设定集卷八·一」）。
分组表可复现：`python tools/rebuild_people_groups.py`。

### 一个标签可以属于多个子分类

有些标签在不同视角下身份不同，可以同时出现在多个子分类里（作者裁定）。当前有 4 个：

* `苏小青` = 主角团队 + 黑旗·蛛眼小队
* `鸣十三` = 中分山（鸣家）+ 光胜集团（她的雇主）
* `苍鬼` = 天堂物流 + 青都帮派地区
* `玉轮` = 惊虎帮 + 青都帮派地区

首页会在每个所属组下都列出它；条目页的「所属分类」会合并去重后展示最多 6 个。
`tools/check_subcategories.py` 把这种情况当**提示**而不是错误。

> 自动聚类试过（`tools/subcategory_prototype.py`）**不可用**：人物维度 173 个标签会聚成一组
> （篇目交织度太高），组织维度只分 3 组且 28 个未归类。所以子分类只能人工声明。

**子分类也是可点的入口**：每个子分类都有一页 `docs/cat/<维度>-<分类>.html`，
列出「组内所有标签的篇目并集」（如「地理 › 城市」＝173 篇）。首页有「分类浏览」区块，
条目页也会显示「所属分类」。分类页从 `subcategories.json` **推导**，不新增标签、不改打标结果。

`python tools/check_subcategories.py` 会校验：重复归类、拼错的名字、漏归类。当前是全绿的。

### 怎么快速改归类（不用编辑 JSON）

```bash
python tools/classmap.py            # 生成下面四个文件
# 打开 data/classmap.txt，把行首数字改掉（0＝未分类），只改要动的行也行
python tools/apply_classmap.py      # 写回 subcategories.json 并校验
python tools/build_site.py          # 重建（分类页与首页一起更新）
```

| 文件 | 用途 |
|---|---|
| `data/classmap.txt` | **推荐**：一行一个标签一个数字，最快 |
| `data/classmap.md` | 问答卡式表格（编号/类目/标签/篇数），适合边看边判 |
| `data/classmap.csv` | Excel 友好（带 BOM，可做下拉验证） |
| `data/classmap_groups.md` | 类目编号表 |

`apply_classmap.py` 的安全保证：**没提到的标签保持原归属**（除非加 `--reset`）；
标签名打错、编号不存在、同一标签重复出现，都会**拒绝写入并报错**，不会静默弄坏。

> 自动聚类试过（`tools/subcategory_prototype.py`）**不可用**：人物维度 172 个标签会聚成一组
> （篇目交织度太高），组织维度只分 3 组且 28 个未归类。所以子分类只能人工声明。

## GitHub Pages

仓库公开 + Pages 发布（已选方案）。两种方式：

* **A. Actions 自动构建**（推荐）：`.github/workflows/pages.yml` 已就绪，
  推送后在仓库 Settings → Pages 里把 Source 选为 **GitHub Actions** 即可。
* **B. 直接发布 `docs/`**：Settings → Pages → Source 选 **Deploy from a branch**，
  分支选 `main`、目录选 `/docs`。

因为生成物在 `wiki/docs/`，若仓库根不是 `wiki/`，请把 workflow 里的
`working-directory: wiki` 与 `path: wiki/docs` 按实际结构调整。

## 部署

**方式**：本地构建 → 提交 `docs/` → 从 `main` 分支发布。
用**用户主页仓库** `darkcoffin-wiki.github.io`，推送即发布，**不用**配 Pages 的 Source/Branch。

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

已就位的配套文件：`docs/CNAME`（构建时自动生成）、`docs/.nojekyll`、
`.github/workflows/pages.yml`（**只跑自检**，不参与发布）。

> 站内链接全部是相对路径，所以无论走默认网址还是自定义域名，都不会有路径问题。

## 数据来源与许可

内容来自《黑柩》花絮的已发布站点文章与作者提供的未发布 docx。**版权归原作者**；
本仓库只做索引、打标与排版，不含设定集内容（设定集仅用于人名的规范写法参考）。

> **免责声明**：本网站由 AI 生成，内容准确性无法完全保证。
> （作者要求标注；已显示在全站每一页的页脚与首页显眼处。）
