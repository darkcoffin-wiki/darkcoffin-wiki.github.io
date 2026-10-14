#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为词表重建准备素材（给子代理与人工审核用）。

产出：
    data/vocab_prep.md      一份自足的任务简报：现状、旧词表、n-gram 证据、分类口径
    data/tab_old_people.txt 旧表 289 名 × 覆盖篇数（已由 vocab_tables.py 生成）
    data/tab_ng_orgs.txt    n-gram 专名候选 × 覆盖篇数
"""
import glob
import json
import os
import re

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(W, "source")
DATA = os.path.join(W, "data")


def body_of(t):
    if t.startswith("---"):
        e = t.find("\n---", 3)
        if e != -1:
            return t[e + 4:]
    return t


def main():
    entries = json.load(open(os.path.join(DATA, "entries.json"), encoding="utf-8"))["entries"]
    old = json.load(open(os.path.join(DATA, "vocabulary.json"), encoding="utf-8"))
    cand = json.load(open(os.path.join(DATA, "entity_candidates.json"), encoding="utf-8"))

    bodies = {}
    for f in sorted(glob.glob(os.path.join(SRC, "hx-*.md"))):
        eid = "-".join(os.path.basename(f).split("-")[:2])
        bodies[eid] = body_of(open(f, encoding="utf-8").read())

    # 覆盖篇数：对每个候选算「出现在多少篇」
    def cover(tag):
        return sum(1 for t in bodies.values() if tag in t)

    lines = []
    lines.append("# 词表重建素材包（自足）\n")
    lines.append("## 0. 语料现状\n")
    lines.append("- `source/` 下 210 个 md，一篇一文件，命名 `hx-NNN-标题.md`\n")
    lines.append("- 每篇结构：YAML frontmatter（id/title/kind/collection/origin/chars）"
                 " + 空行 + 正文散文与对白\n")
    lines.append("- 正文中**没有** `**角色名**：` 这类发言人标签——直接写「叶心说：……」，"
                 "所以人名只能靠正文匹配来统计\n")
    kinds = {}
    cols = {}
    for e in entries:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        cols[e["collection"]] = cols.get(e["collection"], 0) + 1
    lines.append("- 类型分布：" + "　".join("%s=%d" % kv for kv in
                                       sorted(kinds.items(), key=lambda r: -r[1])) + "\n")
    lines.append("- 合集分布：" + "　".join("%s=%d" % kv for kv in
                                       sorted(cols.items(), key=lambda r: -r[1])) + "\n")

    lines.append("\n## 1. 旧词表 `people`（289 条，来自旧语料的发言人标签，**含噪声**）\n")
    lines.append("格式：名×总行数。**这份表需要按 210 篇重抽 + 去噪 + 归并。**\n\n")
    lines.append("　".join("%s×%d" % (p["tag"], p["lines"]) for p in old["people"]) + "\n")

    lines.append("\n## 2. 旧表人名的新语料覆盖篇数（已排序）\n")
    tab = open(os.path.join(DATA, "tab_old_people.txt"), encoding="utf-8").read()
    lines.append(tab.split("\n", 2)[2] + "\n")

    lines.append("\n## 3. n-gram 专名候选（机构/地名/设施线索）\n")
    orgs = [r for r in cand["proper_candidates"] if r["count"] >= 12 and r["entropy"] >= 2.4][:400]
    lines.append("　".join("%s:%d" % (r["tag"], r["count"]) for r in orgs) + "\n")

    lines.append("\n## 4. 旧 `taxonomy`（要保留并扩展的受控类别）\n")
    lines.append("```json\n" + json.dumps(old["taxonomy"], ensure_ascii=False, indent=1) + "\n```\n")
    lines.append("\n## 5. 旧 `variant_map`\n")
    lines.append("```json\n" + json.dumps(old["variant_map"], ensure_ascii=False, indent=1) + "\n```\n")

    lines.append("\n## 6. 明确要剔除的噪声（旧表里混进来的发言人标签）\n")
    lines.append("职务/群体/匿名/网名，示例：`受审者`、`喽啰`、`牧师`、`店主`、`长老`、"
                 "`众人`、`议员`、`总统`、`大主教`、`将军`、`士兵`、`两人`、`民众`、`人群`、"
                 "`老板`、`仆人`、`队员`、`队员们`、`工人们`、`员工们`、`贫民们`、`宪兵们`、"
                 "`受害者们`、`下属`、`下属甲`、`下属乙`、`队员A`、`队员B`、`队员C`、"
                 "`保安A`、`保安B`、`保安C`、`保安们`、`工人A`、`工人B`、`工人G`、`工人甲`、"
                 "`女生A`~`女生D`、`贫民A`~`贫民F`、`俘虏甲`~`俘虏丁`、`囚犯甲`、`囚犯乙`、"
                 "`教士A`、`教士B`、`教徒A`~`教徒D`、`主教A`~`主教C`、`企业家A`~`企业家C`、"
                 "`护卫A`~`护卫C`、`警员A`、`警员B`、`记者甲`、`记者乙`、`军人甲`、`军人乙`、"
                 "`歹徒甲`、`歹徒乙`、`室友A`、`室友们`、`同事A`、`同事B`、`同学甲`、`某员工`、"
                 "`某股东`、`路人`、`旁观者`、`神秘人`、`远处的声音`、`房间里的声音`、`大厅喇叭`、"
                 "`带头的`、`瘦军官`、`胖军官`、`清洁工`、`狱警`、`小卖部大妈`、`玩网大手子`、"
                 "`路过的好人`、`平安是福`、`平安喜乐`、`舞墨书生`、`打倒一切牛鬼蛇神`、"
                 "`不升职誓不改名`、`两脚漂亮羊`、`我推的叶心`、`夜访吸血鬼`、`可爱的曼波`、"
                 "`可爱的曼巴`、`智人TV`、`青山在`、`行得正站得直`、`革命之龙卷八级风`、"
                 "`请客吃饭`、`亲爱的路絮`、`亲爱的希联人民`、`亲爱的`、`新知高仿号`、"
                 "`衣食住行计划官方`、`对反动派专用叶家枪`、`至高无上帝国皇帝的亲卫队`、"
                 "`独断千古帝国皇帝的禁林军`、`南星都唱片行老板`、`吸血鬼殿下的绝世妃子`\n")
    lines.append("\n注意：`宪兵`、`天使们`、`自由民`、`罪人`、`民众`、`人群` 等是**群体**，"
                 "不是具体角色，不应进人名表（可作为组织/群体标签）。\n")

    with open(os.path.join(DATA, "vocab_prep.md"), "w", encoding="utf-8") as fh:
        fh.write("".join(lines))
    print("wrote data/vocab_prep.md",
          os.path.getsize(os.path.join(DATA, "vocab_prep.md")), "bytes")


if __name__ == "__main__":
    main()
