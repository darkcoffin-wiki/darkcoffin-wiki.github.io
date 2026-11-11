# -*- coding: utf-8 -*-
"""把「创作时间」写进 249 篇花絮的 frontmatter 与 entries.json。

数据源：`_xx\\花絮时间\\花絮时间.csv`（编号 → 创作时间 / 证据等级）。
· A/B 档：`date` 精确到秒，展示时只取到日。
· D 档（5 篇）：CSV 里是 `起 ~ 止`，拆成 `date` / `date_end`，展示时写区间并标「推定」。

幂等：已有 `date` 的不重复写（`--force` 可覆盖）。
用法：python add_huaxu_dates.py [--dry] [--force]
"""
import csv
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = r"E:\DSHwork\heijiu\wiki"
SRC = os.path.join(W, "source")
ENT = os.path.join(W, "data", "entries.json")
CSV = r"E:\DSHwork\heijiu\_xx\花絮时间\花絮时间.csv"
DRY = "--dry" in sys.argv
FORCE = "--force" in sys.argv

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def split_range(v):
    """'2023-10-18 11:27:33 ~ 2023-10-27 23:02:23' → (起, 止)。"""
    parts = [x.strip() for x in v.split("~")]
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ""


rows = {}
with io.open(CSV, encoding="utf-8-sig", newline="") as fh:
    for r in csv.DictReader(fh):
        if r.get("编号"):
            rows[r["编号"].strip()] = r

print("CSV 行数：%d" % len(rows))

ents = json.load(io.open(ENT, encoding="utf-8"))
by_id = {e["id"]: e for e in ents["entries"]}

missing = [eid for eid in by_id if eid not in rows]
extra = [eid for eid in rows if eid not in by_id]
print("entries 有、CSV 无：%s" % (missing or "无"))
print("CSV 有、entries 无：%s" % (extra or "无"))

stats = {"A": 0, "B": 0, "D": 0, "已有": 0, "跳过": 0}
touched = 0
for eid, e in sorted(by_id.items()):
    r = rows.get(eid)
    if not r:
        stats["跳过"] += 1
        continue
    path = os.path.join(SRC, e["file"])
    if not os.path.exists(path):
        print("!! 缺源文件：%s" % e["file"])
        continue
    raw = io.open(path, encoding="utf-8").read()
    m = FM_RE.match(raw)
    if not m:
        print("!! frontmatter 解析失败：%s" % e["file"])
        continue
    fm = m.group(1)
    if "date:" in fm and not FORCE:
        stats["已有"] += 1
        continue

    start, end = split_range(r["创作时间"])
    level = (r.get("证据等级") or "").strip() or "A"
    # 旧的三个字段先删掉再写，保证 --force 重跑不会重复
    fm2 = "\n".join(ln for ln in fm.split("\n")
                    if not ln.startswith(("date:", "date_level:", "date_end:")))
    add = ["date: %s" % start, "date_level: %s" % level]
    if end:
        add.append("date_end: %s" % end)
    fm2 = fm2.rstrip("\n") + "\n" + "\n".join(add)
    raw2 = raw[:m.start(1)] + fm2 + raw[m.end(1):]

    if not DRY:
        io.open(path, "w", encoding="utf-8", newline="\n").write(raw2)
    e["date"] = start
    e["date_level"] = level
    if end:
        e["date_end"] = end
    else:
        e.pop("date_end", None)
    e["date_note"] = (r.get("备注") or "").strip()
    stats[level] = stats.get(level, 0) + 1
    touched += 1

if not DRY:
    io.open(ENT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(ents, ensure_ascii=False, indent=1) + "\n")

print("写入 %d 篇（A %d / B %d / D %d）；已有日期跳过 %d；无数据 %d"
      % (touched, stats["A"], stats["B"], stats["D"], stats["已有"], stats["跳过"]))
if DRY:
    print("（dry run，未写盘）")
