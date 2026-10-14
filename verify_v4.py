"""Verify v4: reconcile against the official title list, and show the biggest
entries (all should be under 15000 now)."""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
official = json.load(open(os.path.join(WIKI, "data", "site_titles.json"), encoding="utf-8"))["titles"]
text = open(SRC, encoding="utf-8", errors="ignore").read()


def norm(s):
    s = re.sub(r"^#{1,6}\s*", "", s)
    s = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", s)
    s = re.sub(r"^\d+[、.．]\s*", "", s)
    s = s.replace("*", "")
    s = re.sub(r"[\s\u3000]", "", s)
    s = re.sub(r"[（）()【】\[\]「」『』“”\"'‘’、，,。.！!？?：:]", "", s)
    s = s.replace("——", "").replace("—", "").replace("-", "")
    return s


md_norm = {norm(e["title"]): e for e in ents}
missing = []
matched = 0
for t in official:
    k = norm(t)
    if k in md_norm:
        matched += 1
        continue
    fz = [e for e in ents if norm(e["title"]).startswith(k) or k.startswith(norm(e["title"]))]
    if fz:
        matched += 1
    else:
        missing.append(t)

print(f"official titles : {len(official)}")
print(f"matched         : {matched}")
print(f"NOT in markdown : {len(missing)}  (= 未发布 / 站点标题与 md 不同)")
for t in missing:
    print(f"   {t}")

print(f"\nmd entries      : {len(ents)}")
unpub = len(ents) - matched
print(f"md-only entries : {unpub}  (= 站点没有的，可能未发布或标题不同)")

# which md entries are not matched
claimed = set()
for t in official:
    k = norm(t)
    if k in md_norm:
        claimed.add(md_norm[k]["id"])
    else:
        fz = [e for e in ents if norm(e["title"]).startswith(k) or k.startswith(norm(e["title"]))]
        if fz:
            claimed.add(fz[0]["id"])
extra = [e for e in ents if e["id"] not in claimed]
print(f"\n=== {len(extra)} md-only entries ===")
for e in extra:
    print(f"  {e['id']} {e['chars']:>6} {e['kind']:<5} {e['title'][:60]}")

print("\n=== 10 largest entries now ===")
for e in sorted(ents, key=lambda x: -x["chars"])[:10]:
    print(f"  {e['id']} {e['chars']:>6}  {e['title'][:62]}")

print(f"\n>15000: {sum(1 for e in ents if e['chars'] > 15000)}")
print(f">10000: {sum(1 for e in ents if e['chars'] > 10000)}")
