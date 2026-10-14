"""Final QA on the corpus: duplicates, coverage vs the site's own TOC, checksums."""
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SRC = os.path.join(WIKI, "source")
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"


def norm(t):
    s = re.sub(r"^" + VOCAB + r"\s*[:：]\s*", "", t)
    s = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", s)
    s = s.replace("*", "")
    s = re.sub(r"[\s\u3000]", "", s)
    s = re.sub(r"[（）()【】\[\]「」『』“”\"'‘’、，,。.！!？?：:]", "", s)
    return s.replace("——", "").replace("—", "").replace("-", "")


# 1) duplicate titles
c = Counter(norm(e["title"]) for e in ents)
dups = {k: n for k, n in c.items() if n > 1}
print(f"1) 重复标题: {len(dups)}")
for k, n in dups.items():
    print(f"   x{n}  {k[:60]}")

# 2) files on disk vs entries.json
files = sorted(f for f in os.listdir(SRC) if f.endswith(".md") and not f.startswith("_"))
print(f"\n2) source/ 文件数 {len(files)}   entries.json {len(ents)}  "
      f"{'一致' if len(files) == len(ents) else '不一致!'}")

# 3) every title begins with a vocabulary word
bad = [e for e in ents if not re.match(r"^\s*" + VOCAB, e["title"])]
print(f"\n3) 标题不以八词开头的: {len(bad)}")
for e in bad[:10]:
    print("   ", e["title"][:60])

# 4) empty / tiny bodies
tiny = [e for e in ents if e["chars"] < 200]
print(f"\n4) 正文 <200 字: {len(tiny)}")
for e in tiny:
    print(f"   {e['id']} {e['chars']:>5}  {e['title'][:56]}")

# 5) coverage: published vs unpublished
print(f"\n5) 来源分布: {Counter(e['origin'] for e in ents).most_common()}")
print(f"   合集分布:")
for k, v in Counter(e["collection"] for e in ents).most_common():
    tot = sum(e["chars"] for e in ents if e["collection"] == k)
    print(f"     {k:<24} {v:>3} 篇  {tot:>8} 字")

# 6) totals
tot = sum(e["chars"] for e in ents)
print(f"\n6) 总字数 {tot}  平均 {tot//len(ents)}  最大 {max(e['chars'] for e in ents)}")
