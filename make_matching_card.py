"""Emit the matching sheet as a fill-in markdown card for the author."""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
ms = json.load(open(os.path.join(WIKI, "data", "match_sheet.json"), encoding="utf-8"))
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")

by_id = {e["id"]: e for e in ents}
VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"


def opening(e, n=110):
    a = e["source_line"] - 1
    i = ents.index(e)
    b = ents[i + 1]["source_line"] - 1 if i + 1 < len(ents) else len(lines)
    txt = " ".join(x.strip() for x in lines[a + 1:b] if x.strip())
    txt = re.sub(r"\*+", "", txt)
    txt = re.sub(r"^#*\s*", "", txt)
    return txt[:n]


need = ms["need_title"]
unmatched = ms["unmatched_site_titles"]

out = []
out.append("# 黑柩花絮 Wiki · 标题连连看\n")
out.append(f"**怎么用**：下面是 **{len(need)} 个「md 里有、我拟不出标题」的片段**，和 "
           f"**{len(unmatched)} 个「站点上有、md 里对不上」的标题**。\n")
out.append("请在每个片段下的 `【连】` 后面写上对应的站点标题编号（如 `【连】S07`）。"
           "对不上的写 `未发布`。\n")
out.append("若某片段其实**在站上用的是别的标题**（不在这 22 个里），直接写标题即可。\n")
out.append("\n---\n\n## 甲、待命名的片段\n")

for k, e in enumerate(need, 1):
    ent = by_id[e["id"]]
    out.append(f"### 片 {k:02d}　`{e['id']}`　{e['kind']}　{e['chars']} 字　（源行 L{e['line']}）\n")
    out.append(f"**开头**：{opening(ent)}\n")
    out.append(f"**我暂拟**：{e['title']}\n")
    out.append("**【连】**：\n")
    out.append("")

out.append("\n---\n\n## 乙、站点上有、md 里对不上的标题\n")
for k, t in enumerate(unmatched, 1):
    out.append(f"- **S{k:02d}**　{t}")
out.append("")
out.append("\n---\n\n## 丙、前缀不一致（按你的规则，以站点为准）\n")
out.append("| md id | md 用的前缀 | 站点用的前缀 | 站点标题 |")
out.append("|---|---|---|---|")
for d in ms["kind_differences"]:
    out.append(f"| {d['md_id']} | {d['md_kind']} | {d['site_kind']} | {d['site']} |")
out.append("\n如果你觉得其中某个应以 md 为准，请注明。\n")

out.append("\n---\n\n## 丁、另外 25 个「md 里有、站点目录没有」的（非碎片，标题正常）\n")
out.append("这些不是碎片，标题来自 md 原文，只是站点目录里找不到。**可能都属未发布。**"
           "若其中有在站上发布过的，请指出。\n")
extra = [e for e in ms["no_site_counterpart"] if not e["auto"]]
for e in extra:
    out.append(f"- `{e['id']}`　{e['kind']}　{e['chars']} 字　{e['title']}")
out.append("")

path = os.path.join(WIKI, "问答卡-标题连连看.md")
open(path, "w", encoding="utf-8").write("\n".join(out))
print("wrote", path)
print(f"fragments {len(need)}  candidate titles {len(unmatched)}  kind-diffs {len(ms['kind_differences'])}  plain-extra {len(extra)}")

# print the openings so they are visible here too
print("\n--- openings ---")
for k, e in enumerate(need, 1):
    ent = by_id[e["id"]]
    print(f"片{k:02d} {e['id']} ({e['kind']}, {e['chars']}字): {opening(ent, 90)}")
