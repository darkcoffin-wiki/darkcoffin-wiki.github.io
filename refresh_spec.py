"""Refresh 项目说明书.md sections 2 and 3 so the handoff is accurate:
replace the stale md-based parsing rules with the final site+docx rules."""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

P = r"E:\DSHwork\heijiu\wiki\项目说明书.md"
t = open(P, encoding="utf-8").read()

# ---------- replace section 二 ----------
i = t.index("## 二、Phase 1 已完成的工作")
j = t.index("## 三、解析规则")
new2 = """## 二、Phase 1 已完成的工作（**已收官**）

### 2.1 语料：**210 篇**

| 项 | 值 |
|---|---:|
| 总篇数 | **210** |
| 总字数 | 约 67.6 万字 |
| 中位篇长 | 2,997 字 |
| 最长 | 12,918 字 |
| 重复标题 | 0 |
| 正文 <200 字 | 0 |

**来源构成**

| 来源 | 篇数 | 说明 |
|---|---:|---|
| **站点** darkcoffin.hubingsf.cn | **193** | 已发布定稿，标题与正文同源，**权威** |
| **docx** | **17** | 《黑柩-长歌总集篇二》整份尚未发布 |

**按类型**：花絮 107｜楔子 36｜画外音 33｜长歌 20｜四格 7｜剧情花絮 3｜特别环节 2｜特别内容 2

### 2.2 已产出的文件

```
E:\\DSHwork\\heijiu\\wiki\\
├─ source\\                  210 个 md（一篇一文件）+ _INDEX.md
├─ data\\
│   ├─ entries.json         210 篇元数据
│   ├─ site_pieces.json     站点解析结果（193 篇，按合集）
│   ├─ site_titles.json     站点权威标题
│   ├─ docx_sources.json    12 份 docx 的标题清单
│   └─ site_vs_docx.json    docx↔站点对表、未发布清单
├─ _site_raw\\               11 篇站点文章 HTML 快照（不再联网）
├─ parse_site_all.py        站点解析（八词法）
├─ merge_corpus.py          站点 + 未发布 docx → 最终语料
├─ qa_final.py              终检
├─ build_v6.py              docx 解析（样式标记法）
├─ 项目说明书.md              本文件
└─ 语料交接.md               切分阶段的交接
```

**每篇 md 的头部**：

```markdown
---
id: hx-001
title: "花絮：叶心与红樱的谈话"
kind: 花絮
collection: 总集篇一
origin: site
chars: 2094
---
```

"""
t = t[:i] + new2 + t[j:]

# ---------- replace section 三 ----------
i = t.index("## 三、解析规则")
j = t.index("## 四、标签体系")
new3 = """## 三、解析规则（**定稿，增量必须复用**）

### 3.1 数据源优先级（已定）

1. **站点为首选**——已发布定稿，标题与正文天然对齐
2. **docx 只用于站点上没有的**（未发布内容）
3. **合并 md（`黑柩花絮截止2026.10.md`）已弃用**——三种标题风格混排、含假切分

### 3.2 标题识别：八词 + 冒号

**词汇**：`剧情花絮｜特别内容｜特别环节｜四格漫画｜四格｜长歌｜花絮｜楔子｜画外音`

**规则**：段落**首行**以某词汇紧跟 `:` 或 `：` 开头，且：
- 不是**图例行**（`花絮：表示在……` 这类定义句）
- 长度 < 80 字

**已验证的坑（务必不要重犯）**：

| 坑 | 后果 |
|---|---|
| 加「长句或句末标点就丢弃」的启发式 | **误删真标题**（如《花絮：苍鬼会为自己的老公做什么？》），站点从 195 掉到 188 |
| 用「编号（一、二、）+ 类型词」当标记 | 不可靠 |
| 让图例行通过 | 凭空多出条目，且与真标题同名 |

**唯一需要显式排除的定义句**：
`剧情花絮：专门为黑柩TRPG主线剧情服务的花絮，真正意义上的花絮。`

### 3.3 docx 的标题标记（仅用于未发布部分）

- **段落样式 `w:pStyle=2` 即标题**（多份 docx 一致）
- **例外**：`黑柩TRPG-花絮总集篇二.docx` 无样式，标题是行内 `#黑柩<类型>`，**正文接在同一行**

### 3.4 增量更新流程

1. 新花絮发布后 → 用 `parse_site_all.py` 的规则解析该文章（把 aid 加进 `ARTICLES`）
2. 或直接给新 docx → 用 `build_v6.py` 的样式规则解析
3. 按标题归一化去重后**追加**到 `source/`
4. **只对新增条目打标**（用 `source_hash` 判新旧）
5. 重建受影响页面

**⚠️ id 纪律**：id 现为顺序编号（`hx-NNN`）。**追加时延续编号，不要重排**，否则既有链接失效。

"""
t = t[:i] + new3 + t[j:]

# ---------- refresh section 九 / 十 lightly ----------
t = t.replace("## 九、Phase 2 待办清单", "## 九、Phase 2 待办清单（当前状态）")
t = t.replace("1. ☐ 清理 `vocabulary.json` 的人名噪声（约 30 个非人名）",
              "1. ☐ **按 210 篇重抽人名**（现有 `vocabulary.json` 是从弃用的 md 抽的，已过时）")
t = t.replace("2. ☐ 编写 `tag_entries.py`：对 144 篇打标",
              "2. ☐ 编写 `tag_entries.py`：对 **210 篇**打标")

open(P, "w", encoding="utf-8").write(t)
print("updated", P)
print("chars:", len(t))
for pat in ["144", "213", "182"]:
    print(f"  残留 {pat}: {t.count(pat)}")
