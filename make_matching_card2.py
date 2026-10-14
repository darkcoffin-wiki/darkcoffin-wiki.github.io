"""Fix opening extraction: include inline text that shares the marker line."""
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

HASH = re.compile(r"^\s*#\s*黑柩\s*(?:#\s*)?(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)\s*#?\s*")


def opening(e, n=120):
    a = e["source_line"] - 1
    inline = HASH.match(lines[a])
    seg = [(lines[a][inline.end():] if inline else "")]
    i = ents.index(e)
    b = ents[i + 1]["source_line"] - 1 if i + 1 < len(ents) else len(lines)
    seg += lines[a + 1:b]
    txt = " ".join(x.strip() for x in seg if x.strip())
    txt = re.sub(r"\*+", "", txt)
    txt = re.sub(r"^(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)\s*[:：#]*\s*", "", txt)
    txt = re.sub(r"^#*\s*", "", txt)
    return txt[:n]


need = ms["need_title"]
unmatched = ms["unmatched_site_titles"]

out = ["# 黑柩花絮 Wiki · 标题连连看\n",
       f"**怎么用**：下面是 **{len(need)} 个「md 里有、我拟不出标题」的片段**，和 "
       f"**{len(unmatched)} 个「站点上有、md 里对不上」的标题**。\n",
       "在每个片段下的 `【连】` 后写上对应的站点编号（如 `S07`）。对不上的写 `未发布`。\n",
       "若某片段在站上用的是**别的标题**（不在这 22 个里），直接把标题写上去。\n",
       "\n---\n\n## 甲、待命名的片段\n"]

for k, e in enumerate(need, 1):
    ent = by_id[e["id"]]
    out.append(f"### 片 {k:02d}　`{e['id']}`　{e['kind']}　{e['chars']} 字　（源行 L{e['line']}）\n")
    out.append(f"**开头**：{opening(ent)}\n")
    out.append(f"**我暂拟**：{e['title']}\n")
    out.append("**【连】**：\n")

out.append("\n---\n\n## 乙、站点上有、md 里对不上的标题\n")
for k, t in enumerate(unmatched, 1):
    out.append(f"- **S{k:02d}**　{t}")

out.append("\n\n---\n\n## 丙、前缀不一致（按你的规则以站点为准，请确认）\n")
out.append("| md id | md 前缀 | 站点前缀 | 站点标题 |")
out.append("|---|---|---|---|")
for d in ms["kind_differences"]:
    out.append(f"| {d['md_id']} | {d['md_kind']} | {d['site_kind']} | {d['site']} |")

out.append("\n\n---\n\n## 丁、25 个标题正常、但站点目录里找不到的\n")
out.append("**可能都属未发布。** 若其中有已在站上发布的，请指出。\n")
for e in [x for x in ms["no_site_counterpart"] if not x["auto"]]:
    out.append(f"- `{e['id']}`　{e['kind']}　{e['chars']} 字　{e['title']}")

path = os.path.join(WIKI, "问答卡-标题连连看.md")
open(path, "w", encoding="utf-8").write("\n".join(out))
print("wrote", path, f"({len(''.join(out))} chars)\n")

print("--- openings (for the reply) ---")
for k, e in enumerate(need, 1):
    ent = by_id[e["id"]]
    print(f"片{k:02d} | {e['id']} | {e['kind']} | {e['chars']}字 | {opening(ent, 88)}")
